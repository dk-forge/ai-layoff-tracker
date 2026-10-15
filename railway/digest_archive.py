"""A cleaned public copy of each SENT digest edition, for the Email Archive.

asktherecruiter.com/email-archive renders these files (owner approved
2026-10-11, "start fresh": nothing before the first archived send is
backfilled). Nothing stored past editions before this, so a reader who missed
a morning had nowhere to read it.

THE COPY IS PUBLIC AND THE EMAIL IS NOT, so everything that belongs to one
reader comes out before a byte is written:

  - the unsubscribe and preferences links, which are signed per reader and
    would let anybody act on that reader's subscription, and the sentences
    that introduce them;
  - the measurement paragraph, which describes how THIS email is counted and
    is false of a web page;
  - every e-mail address, every image (the digest carries none by policy, so
    any image is foreign: a pixel a relay added), and any link that carries a
    token or signature in its query string.

The postal-address line stays: it is the sender's, not a reader's.

DETERMINISTIC ON PURPOSE. The same payload writes the same bytes and the index
is rebuilt sorted, so a re-run of the same slot commits nothing.

Only daily and weekly editions are archived (the scope the owner approved).
"""
from __future__ import annotations

import json
import os
import re
from html import escape

import digest_layout

ARCHIVED_KINDS = ("daily", "weekly")

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_IMG = re.compile(r"<img\b[^>]*>", re.I)
_ANCHOR = re.compile(r'<a\b[^>]*\bhref="([^"]*)"[^>]*>(.*?)</a>', re.I | re.S)
# A link whose job is to identify a reader or act on a subscription.
_PRIVATE_HREF = re.compile(
    r"unsub|preferences|manage|mailto:|[?&](?:t|token|sig|signature|key|"
    r"email|e|uid|rid)=", re.I)
_UNSUB_SENTENCE = re.compile(r"[^.<>]*unsubscrib[^.<>]*\.?", re.I)
_EMPTY_P = re.compile(r"<p\b[^>]*>\s*</p>", re.I)


def _private_sentences() -> list:
    """Footer sentences that only make sense inside one reader's inbox."""
    out = []
    for key, sentences, _anchor in digest_layout.FOOTER_BLOCKS:
        if key in ("unsub", "manage"):
            out.extend(sentences)
    out.extend(digest_layout.tracking_sentences(True))
    out.extend(digest_layout.tracking_sentences(False))
    # Longest first, so a sentence is never half-removed by a shorter one.
    return sorted({escape(s) for s in out}, key=len, reverse=True)


_CID_IMG = re.compile(r'^<img src="cid:chart-[1-9]"[^>]*>$', re.I)


def sanitize_html(html: str, secrets=(), keep_charts: bool = False) -> str:
    """The public form of one rendered message. Pure and deterministic.

    `keep_charts` keeps the message's OWN inline chart images (src="cid:
    chart-N", nothing else); the site's archive route serves those bytes from
    our own domain. Every other image, a relay pixel above all, still goes.
    """
    out = html or ""
    for secret in secrets:
        if secret:
            out = out.replace(secret, "")
    out = _IMG.sub(lambda m: m.group(0) if keep_charts and _CID_IMG.match(m.group(0))
                   else "", out)

    def _anchor(match):
        href, inner = match.group(1), match.group(2)
        return inner if (not href or _PRIVATE_HREF.search(href)) else match.group(0)

    out = _ANCHOR.sub(_anchor, out)
    for sentence in _private_sentences():
        out = out.replace(sentence, "")
    out = _UNSUB_SENTENCE.sub("", out)
    out = _EMAIL.sub("", out)
    out = _EMPTY_P.sub("", out)
    return out


def _richest_recipient(payload: dict):
    """The reader whose edition carries the most sections; ties go to the
    lowest id, so the choice is stable run to run."""
    recipients = [r for r in (payload.get("recipients") or [])
                  if str(r.get("unsub_url") or "").startswith("https://")]
    if not recipients:
        return None
    return sorted(recipients, key=lambda r: (-len(r.get("lists") or []),
                                             int(r.get("id") or 0)))[0]


def edition_from_payload(payload: dict, freq: str):
    """The archive record for this send, or None when there is nothing to keep."""
    kind = str(freq or "").strip().lower()
    if kind not in ARCHIVED_KINDS:
        return None
    recipient = _richest_recipient(payload)
    if recipient is None:
        return None
    import digest_send  # local: digest_send imports this module
    message = digest_send.build_message(payload, recipient, "archive@invalid",
                                        "archive@invalid")
    if message is None:
        return None
    date = str(payload.get("to") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return None
    secrets = (str(recipient.get("email") or ""),
               str(recipient.get("unsub_url") or ""),
               str(recipient.get("manage_url") or ""))
    sections = [name for name in sorted((payload.get("sections") or {}).keys())
                if name in (recipient.get("lists") or [])]
    return {
        "date": date,
        "kind": kind,
        "slug": f"{date}-{kind}",
        "subject": _EMAIL.sub("", message.subject),
        "period": {"from": str(payload.get("from") or "")[:10], "to": date},
        "sections": sections,
        "counts": {"sections": len(sections)},
        "html": sanitize_html(message.html, secrets),
    }


def _dump(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_edition(root: str, edition: dict) -> str:
    """Write the edition's .html + .json and fold it into index.json."""
    year, month = edition["date"][:4], edition["date"][5:7]
    rel = f"{year}/{month}/{edition['slug']}"
    meta = {k: v for k, v in edition.items() if k != "html"}
    meta["path"] = rel + ".html"
    _dump(os.path.join(root, rel + ".html"), edition["html"])
    _dump(os.path.join(root, rel + ".json"),
          json.dumps(meta, indent=2, sort_keys=True) + "\n")

    index_path = os.path.join(root, "index.json")
    entries = []
    if os.path.exists(index_path):
        try:
            with open(index_path, encoding="utf-8") as fh:
                entries = json.load(fh).get("editions") or []
        except (OSError, ValueError):
            entries = []
    entries = [e for e in entries if e.get("slug") != edition["slug"]]
    entries.append({k: meta[k] for k in
                    ("slug", "date", "kind", "subject", "path", "sections")})
    # Newest first; weekly before daily on a shared date, then by slug.
    entries.sort(key=lambda e: (e["date"], e["kind"] == "weekly", e["slug"]),
                 reverse=True)
    _dump(index_path, json.dumps({"editions": entries}, indent=2,
                                 sort_keys=True) + "\n")
    return rel


def archive_sent_edition(payload: dict, freq: str, root: str | None = None):
    """Called after a real send. Never raises: the archive must not cost a send.

    Writes nowhere unless DIGEST_ARCHIVE_DIR (or `root`) says where. The
    workflow sets it to data/email_archive; a test or a laptop run that sends
    through a fake transport leaves the repo's data untouched.
    """
    root = root or os.environ.get("DIGEST_ARCHIVE_DIR", "").strip()
    if not root:
        return None
    try:
        edition = edition_from_payload(payload, freq)
        if edition is None:
            return None
        rel = write_edition(root, edition)
        print(f"digest archive: saved {rel}")
        return rel
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::digest archive copy not saved ({type(exc).__name__}: {exc})")
        return None


# ---------------------------------------------------------------------------
# The site's own archive: /blog/ai-layoff-tracker/digest/YYYY-MM-DD/
# (owner decision 2026-10-15). Saved at send time through the keyed API, the
# same door every other write uses. The record holds the cleaned body, a
# cleaned plain-text copy and the chart PNGs; nothing that names a reader.
# ---------------------------------------------------------------------------
_BODY = re.compile(r"<body\b[^>]*>(.*)</body>", re.I | re.S)
_HIDDEN = re.compile(r'<div style="display:none;[^"]*">.*?</div>', re.S)


def sanitize_text(text: str, secrets=()) -> str:
    """The plain-text copy with every reader-specific line removed."""
    out = []
    private = [s for s in _private_sentences()]
    for line in (text or "").splitlines():
        if any(sec and sec in line for sec in secrets):
            continue
        if _PRIVATE_HREF.search(line) and "http" in line:
            continue
        out.append(line)
    flat = "\n".join(out)
    for sentence in private:
        flat = flat.replace(sentence.replace("&amp;", "&"), "")
    flat = _UNSUB_SENTENCE.sub("", flat)
    flat = _EMAIL.sub("", flat)
    return re.sub(r"\n{3,}", "\n\n", flat).strip() + "\n"


def _public_text(payload: dict, recipient: dict) -> str:
    """The sections as plain text, under a public footer. No reader footer is
    ever rendered, so there is nothing of a reader's to strip back out."""
    import digest_send
    parts = digest_send.usable_sections(payload, recipient.get("lists") or [])
    body = [digest_layout._reflow(digest_layout.plain_dashes(
        digest_layout.part_text(p))) for p in parts]
    rule = "=" * digest_layout.TEXT_WIDTH
    return "\n".join(
        [digest_layout.product_name(parts), rule, ""]
        + ["\n\n".join(body), "", rule,
           "Get this digest by email, free: " + digest_layout.SIGNUP_URL, ""])


def public_record(payload: dict, freq: str):
    """The archive record for /digest/<date>/, or None when nothing is kept."""
    import base64
    kind = str(freq or "").strip().lower()
    if kind not in ARCHIVED_KINDS:
        return None
    recipient = _richest_recipient(payload)
    if recipient is None:
        return None
    import digest_send  # local: digest_send imports this module
    message = digest_send.build_message(payload, recipient, "archive@invalid",
                                        "archive@invalid")
    if message is None:
        return None
    date = str(payload.get("to") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return None
    secrets = (str(recipient.get("email") or ""),
               str(recipient.get("unsub_url") or ""),
               str(recipient.get("manage_url") or ""))
    clean = sanitize_html(message.html, secrets, keep_charts=True)
    body = _BODY.search(clean)
    body_html = _HIDDEN.sub("", body.group(1) if body else clean).strip()
    return {
        "date": date,
        "kind": kind,
        "period_from": str(payload.get("from") or "")[:10],
        "subject": _EMAIL.sub("", message.subject),
        "html": body_html,
        "text": sanitize_text(_public_text(payload, recipient), secrets),
        "charts": [{"n": int(img["cid"].split("-")[1]),
                    "alt": img["alt"],
                    "png": base64.b64encode(bytes(img["png"])).decode("ascii")}
                   for img in message.images],
    }


def assert_public(record: dict) -> None:
    """Refuse a record that could carry anything belonging to one reader."""
    blob = (record.get("html") or "") + "\n" + (record.get("text") or "")
    low = blob.lower()
    if _EMAIL.search(blob):
        raise ValueError("an e-mail address survived into the archive copy")
    for token in ("unsub", "alt_digest_", "preferences/", "mailto:"):
        if token in low:
            raise ValueError(f"a private link marker ({token}) survived")
    for img in _IMG.findall(record.get("html") or ""):
        if not _CID_IMG.match(img):
            raise ValueError("an image other than our own chart survived")
    if re.search(r"[?&](?:t|token|sig|signature|key|uid|rid)=", blob):
        raise ValueError("a signed query string survived")


def post_public_record(payload: dict, freq: str, call=None):
    """Called after a real send. Never raises: the archive must not cost a send."""
    try:
        record = public_record(payload, freq)
        if record is None:
            return None
        assert_public(record)
        if call is None:
            import digest_send
            call = digest_send._call
        result = call("digest-archive", payload=record)
        print(f"digest archive: published {record['date']} ({record['kind']})")
        return result
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::digest archive page not saved ({type(exc).__name__})")
        return None
