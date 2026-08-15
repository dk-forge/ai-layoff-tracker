"""One seam between the digest and whoever carries it.

WHY A SEAM RATHER THAN A VENDOR.

At this list size every provider's free tier covers the sending for months, so
picking one now is a decision made without the data that would settle it. What
would actually cost money later is welding the digest to one vendor's SDK and
paying to unpick it. So the digest builds a `Message` and hands it to a
`Transport`, and which transport runs is one environment variable.

  DIGEST_TRANSPORT=dryrun   render to stdout, send nothing. THE DEFAULT.
  DIGEST_TRANSPORT=resend   Resend's HTTP API. Needs RESEND_API_KEY.
  DIGEST_TRANSPORT=smtp     any SMTP relay: Brevo, SES-SMTP, Postmark, Mailgun.
                            Needs DIGEST_SMTP_HOST + DIGEST_SMTP_USER +
                            DIGEST_SMTP_PASSWORD.

SES's own HTTP API is deliberately NOT built. SES-SMTP reaches the same service
through the smtp path with no new code, and a speculative second AWS client is
code nobody has run. Add it when a measured bill says it is worth an AWS
signing implementation, not before.

THE PRIVACY PROMISE IS A PROPERTY OF THE MESSAGE, NOT OF THE PROVIDER.

The published privacy note says "No images, no tracking pixels", and it says we
cannot tell whether you opened an email. That is a promise about what leaves
here, so it is enforced on the MESSAGE, in `assert_message_is_clean`, called by
the base class immediately before any transport does its work. A new provider
cannot opt out of it: `Transport.send` is not the method a provider overrides.

The one thing this file cannot enforce is a provider rewriting our message
after we hand it over. Resend and most relays offer account-level open and
click tracking, which injects exactly the pixel we promised not to send. That
switch lives in their dashboard, so it is an owner step in the RUNBOOK, not a
line of code here. Nothing in this repo can verify it, so nothing here claims
to: `tracking_note()` states the requirement rather than a verdict.
"""
from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, parseaddr

RESEND_ENDPOINT = "https://api.resend.com/emails"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"


class DigestPolicyError(RuntimeError):
    """The message breaks a promise we published. Never sent, never retried."""


class TransportError(RuntimeError):
    """The provider refused or could not be reached. One recipient's problem."""


@dataclass
class Message:
    """One digest, addressed to one person.

    `to` is the only field holding personal data. It is never printed by
    anything in this package: `redacted()` is what goes in a log line.
    """

    to: str
    subject: str
    html: str
    text: str
    from_addr: str
    reply_to: str = ""
    headers: dict = field(default_factory=dict)

    def redacted(self) -> str:
        """A stable, non-reversing label for logs. Never the address."""
        local, _, domain = self.to.partition("@")
        keep = local[:1] if local else "?"
        return f"{keep}***@{domain or '?'}"


# ---------------------------------------------------------------------------
# The policy
# ---------------------------------------------------------------------------

# Tags that make a mail client fetch something from a server, which is how open
# tracking works whatever it is called. A digest is text and links, so the whole
# family is refused rather than the one tag people remember.
_REMOTE_TAGS = ("img", "picture", "source", "video", "audio", "iframe",
                "object", "embed", "svg", "link", "script", "style")
_TAG_RE = re.compile(r"<\s*(/?)([a-zA-Z][a-zA-Z0-9]*)")
_ATTR_RE = re.compile(r"\b(src|srcset|background|poster|data-src)\s*=", re.I)
_CSS_URL_RE = re.compile(r"url\s*\(", re.I)
_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']*)["\']', re.I)


def assert_message_is_clean(message: Message) -> None:
    """Refuse to send anything that breaks the published privacy note.

    Raises DigestPolicyError. This is not a warning: a message that would carry
    a pixel is not sent in a degraded form, it is not sent.
    """
    if not isinstance(message, Message):
        raise DigestPolicyError("not a Message")
    if "@" not in (message.to or ""):
        raise DigestPolicyError("no recipient address")
    if not (message.subject or "").strip():
        raise DigestPolicyError("no subject")

    html = message.html or ""
    lowered = html.lower()

    # 1. Nothing that fetches from a server when the message is opened.
    for _, tag in ((m.group(1), m.group(2).lower()) for m in _TAG_RE.finditer(html)):
        if tag in _REMOTE_TAGS:
            raise DigestPolicyError(
                f"the rendered digest contains a <{tag}> tag. The privacy note "
                f"promises no images and no tracking pixels, and every tag that "
                f"fetches from a server is an open tracker whatever it is called")
    if _ATTR_RE.search(html):
        raise DigestPolicyError(
            "the rendered digest carries a src or background attribute, which "
            "makes the reader's mail client fetch a remote file")
    if _CSS_URL_RE.search(html):
        raise DigestPolicyError(
            "the rendered digest carries a CSS url() value, which is a remote "
            "fetch wearing a stylesheet")

    # 2. A plain text part, and a real one. A single space would satisfy a
    #    truthiness check and satisfy no reader.
    text = (message.text or "").strip()
    if len(text) < 20:
        raise DigestPolicyError("the message has no usable plain text part")
    if "<" in text and ">" in text:
        raise DigestPolicyError("the plain text part contains markup")

    # 3. RFC 8058 one-click unsubscribe, in the headers AND reachable in both
    #    bodies. A header alone leaves a reader without a client that honours it
    #    with no way out.
    lu = _header(message, "List-Unsubscribe")
    lup = _header(message, "List-Unsubscribe-Post")
    if not lu:
        raise DigestPolicyError("List-Unsubscribe header is missing")
    if not re.fullmatch(r"\s*<https://[^>]+>\s*", lu):
        raise DigestPolicyError(
            f"List-Unsubscribe must be one https URL in angle brackets, got {lu!r}")
    if (lup or "").strip() != "List-Unsubscribe=One-Click":
        raise DigestPolicyError(
            "List-Unsubscribe-Post must be exactly List-Unsubscribe=One-Click "
            "(RFC 8058), or mailbox providers will not offer the one-click button")
    unsub_url = lu.strip()[1:-1]
    if unsub_url not in html:
        raise DigestPolicyError("the HTML part carries no unsubscribe link")
    if unsub_url not in text:
        raise DigestPolicyError("the plain text part carries no unsubscribe link")

    # 4. Every link is http(s). javascript: and data: in a mail body are only
    #    ever an attack, and a relative href in an email resolves to nothing.
    for href in _HREF_RE.findall(html):
        if not href.lower().startswith(("http://", "https://", "mailto:")):
            raise DigestPolicyError(f"link {href!r} is not an absolute http(s) URL")

    # 5. A From and, when set, a Reply-To that parse as addresses.
    if "@" not in parseaddr(message.from_addr or "")[1]:
        raise DigestPolicyError("From is not a usable address")
    if message.reply_to and "@" not in parseaddr(message.reply_to)[1]:
        raise DigestPolicyError("Reply-To is set but is not a usable address")

    # 6. And the address itself never travels in a link. The whole token design
    #    exists so it does not, and a composer bug is the way it would.
    if message.to.lower() in lowered or message.to.lower() in text.lower():
        raise DigestPolicyError(
            "the recipient's address appears in the message body, where it "
            "would end up in a URL or a forwarded copy")


def _header(message: Message, name: str) -> str:
    for key, value in (message.headers or {}).items():
        if str(key).lower() == name.lower():
            return str(value)
    return ""


def tracking_note() -> str:
    """What we cannot check from here, stated as a requirement not a verdict."""
    return ("Open and click tracking must be OFF in the provider's dashboard. "
            "Nothing in this repo can read that setting, so this is a stated "
            "requirement and not a passing check. A provider that injects a "
            "pixel makes the published privacy note false.")


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------

class Transport:
    """Base class. Providers implement `_deliver`, never `send`.

    That split is the whole point: the policy check lives in `send`, so a
    provider added in five years cannot skip it by forgetting to call it.
    """

    name = "base"
    sends = False          # does this transport put a message on the wire?

    def send(self, message: Message) -> str:
        assert_message_is_clean(message)
        return self._deliver(message)

    def _deliver(self, message: Message) -> str:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name


class DryRunTransport(Transport):
    """Renders the exact message to stdout and sends nothing.

    This is the DEFAULT, and it is also what an absent key falls back to, so
    the failure mode of a misconfiguration is a printed email rather than an
    unintended one.
    """

    name = "dryrun"
    sends = False

    def __init__(self, reason: str = "", stream=None):
        self.reason = reason
        self.stream = stream
        self.rendered: list[Message] = []

    def _deliver(self, message: Message) -> str:
        self.rendered.append(message)
        out = self.stream
        write = (out.write if out is not None
                 else (lambda s: print(s, end="")))
        lines = [
            "\n" + "=" * 68,
            f"\nDRY RUN, nothing sent. Recipient {message.redacted()}",
            f"\nFrom:    {message.from_addr}",
            f"\nReply-To: {message.reply_to or '(none)'}",
            f"\nSubject: {message.subject}",
        ]
        for key, value in (message.headers or {}).items():
            lines.append(f"\n{key}: {value}")
        lines.append("\n" + "-" * 68 + "\nPLAIN TEXT PART\n" + "-" * 68 + "\n")
        lines.append(message.text.rstrip() + "\n")
        lines.append("-" * 68 + "\nHTML PART\n" + "-" * 68 + "\n")
        lines.append(message.html.rstrip() + "\n")
        lines.append("=" * 68 + "\n")
        write("".join(lines))
        return "dryrun"

    def describe(self) -> str:
        return f"dryrun ({self.reason})" if self.reason else "dryrun"


class ResendTransport(Transport):
    """Resend's HTTP API. One request per message, no SDK, no new dependency.

    Chosen as the first real provider because it is the least setup: an
    account, two DNS records, one key. Its free tier covers this list for
    months. It is not the cheapest at volume, which is why the seam exists.
    """

    name = "resend"
    sends = True

    def __init__(self, api_key: str, timeout: int = 25, opener=None):
        if not api_key:
            raise ValueError("ResendTransport needs an API key")
        self.api_key = api_key
        self.timeout = timeout
        self.opener = opener or urllib.request.urlopen

    def _deliver(self, message: Message) -> str:
        payload = {
            "from": message.from_addr,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
            "headers": dict(message.headers or {}),
        }
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        request = urllib.request.Request(
            RESEND_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": UA,
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:  # noqa: BLE001
                pass
            # The address can appear in a provider error. It must not reach a
            # log, so the message id is what is quoted, never the body verbatim.
            raise TransportError(f"resend returned HTTP {exc.code}: "
                                 f"{_scrub(detail)}") from None
        except Exception as exc:  # noqa: BLE001
            raise TransportError(f"resend unreachable: {_scrub(str(exc))}") from None
        try:
            return str(json.loads(body).get("id") or "sent")
        except Exception:  # noqa: BLE001
            return "sent"


class SmtpTransport(Transport):
    """Any SMTP relay: Brevo, SES-SMTP, Postmark, Mailgun, a mailbox provider.

    One code path covers every provider that speaks SMTP, which is nearly all
    of them, so switching relay is a change of four environment variables and
    no code. The connection is opened per message rather than held: this sends
    to a list measured in hundreds, so a reused socket buys nothing worth the
    reconnection logic it costs.
    """

    name = "smtp"
    sends = True

    def __init__(self, host: str, port: int, user: str, password: str,
                 timeout: int = 30, factory=None):
        if not host:
            raise ValueError("SmtpTransport needs DIGEST_SMTP_HOST")
        self.host = host
        self.port = int(port or 587)
        self.user = user
        self.password = password
        self.timeout = timeout
        self.factory = factory

    def _build(self, message: Message) -> EmailMessage:
        mail = EmailMessage()
        mail["From"] = message.from_addr
        mail["To"] = message.to
        mail["Subject"] = message.subject
        if message.reply_to:
            mail["Reply-To"] = message.reply_to
        for key, value in (message.headers or {}).items():
            mail[key] = value
        mail.set_content(message.text)
        mail.add_alternative(message.html, subtype="html")
        return mail

    def _deliver(self, message: Message) -> str:
        mail = self._build(message)
        try:
            if self.factory is not None:
                client = self.factory(self.host, self.port, timeout=self.timeout)
            elif self.port == 465:
                client = smtplib.SMTP_SSL(self.host, self.port,
                                          timeout=self.timeout,
                                          context=ssl.create_default_context())
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                client.starttls(context=ssl.create_default_context())
            with client:
                if self.user:
                    client.login(self.user, self.password)
                client.send_message(mail)
        except Exception as exc:  # noqa: BLE001
            raise TransportError(f"smtp {self.host}: {_scrub(str(exc))}") from None
        return "smtp"


def _scrub(text: str) -> str:
    """Take any address out of a provider's error before it reaches a log."""
    return re.sub(r"[\w.+-]+@[\w.-]+\.\w+", "[address]", str(text))


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def resolve_transport(env=None, stream=None):
    """Pick a transport from the environment. Returns (transport, notice).

    DORMANT BY CONSTRUCTION. The default is dryrun, and a named provider
    missing its credential falls BACK to dryrun with a notice naming the exact
    secret. There is no configuration that sends by accident, and no
    configuration that turns a missing key into a red run.
    """
    env = os.environ if env is None else env
    choice = (env.get("DIGEST_TRANSPORT") or "dryrun").strip().lower()

    if env.get("DIGEST_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}:
        return DryRunTransport("DIGEST_DRY_RUN is set", stream), (
            "DRY RUN requested: the exact messages are printed and nothing is sent.")

    if choice in {"", "dryrun", "none", "off"}:
        return DryRunTransport("DIGEST_TRANSPORT is not set to a provider", stream), (
            "DORMANT: DIGEST_TRANSPORT is not set to a provider, so nothing "
            "sends. Set DIGEST_TRANSPORT=resend and add the RESEND_API_KEY "
            "repository secret to start sending.")

    if choice == "resend":
        key = env.get("RESEND_API_KEY", "").strip()
        if not key:
            return DryRunTransport("RESEND_API_KEY is not set", stream), (
                "DORMANT: DIGEST_TRANSPORT=resend but the RESEND_API_KEY secret "
                "is not present in this run, so nothing sends. Add RESEND_API_KEY "
                "as a repository secret once the Resend domain is verified.")
        return ResendTransport(key), f"sending through Resend. {tracking_note()}"

    if choice == "smtp":
        host = env.get("DIGEST_SMTP_HOST", "").strip()
        password = env.get("DIGEST_SMTP_PASSWORD", "").strip()
        if not (host and password):
            return DryRunTransport("DIGEST_SMTP_HOST or DIGEST_SMTP_PASSWORD is not set",
                                   stream), (
                "DORMANT: DIGEST_TRANSPORT=smtp but DIGEST_SMTP_HOST or "
                "DIGEST_SMTP_PASSWORD is not present in this run, so nothing sends.")
        return SmtpTransport(host, env.get("DIGEST_SMTP_PORT", 587),
                             env.get("DIGEST_SMTP_USER", ""), password), (
            f"sending through the SMTP relay at {host}. {tracking_note()}")

    # An unknown name is a typo, and a typo must not silently send through a
    # default provider. It sends nothing and says what it did not recognise.
    return DryRunTransport(f"DIGEST_TRANSPORT={choice!r} is not a known transport",
                           stream), (
        f"DORMANT: DIGEST_TRANSPORT={choice!r} is not one of dryrun, resend or "
        f"smtp, so nothing sends. Fix the value rather than adding a fallback.")


def sender_identity(env=None) -> tuple[str, str]:
    """From and Reply-To, on the verified domain.

    DIGEST_FROM overrides, but the default is a real mailbox on the domain the
    DNS records are added for. A From on any other domain fails DKIM alignment
    and lands in spam, which is why this is not a free-text field in practice.
    """
    env = os.environ if env is None else env
    from_addr = (env.get("DIGEST_FROM") or "").strip()
    if not from_addr:
        from_addr = formataddr(("AskTheRecruiter Trackers",
                                "digest@asktherecruiter.com"))
    reply_to = (env.get("DIGEST_REPLY_TO") or "info@asktherecruiter.com").strip()
    return from_addr, reply_to
