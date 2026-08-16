"""How the digest looks when it lands, and when it is passed on.

THE ONE CONSTRAINT EVERYTHING ELSE FOLLOWS FROM.

Gmail, Outlook.com and most webmail delete `<head>` and every `<style>` block
when a message is forwarded or quoted. A digest read by recruiters and
journalists gets forwarded constantly, so a design that lives in a stylesheet
is a design that exists only in the first inbox it reaches. Every rule below
is one inline style attribute on the element that needs it, and this module
emits NO style block at all. There is nothing for a forward to take away.

That is not a preference, it is checkable, and
tests/test_digest_email_layout.py deletes the head and every style block and
asserts the message is byte for byte the same one.

WHY TABLES.

Outlook on Windows renders mail through Word. Word has no flexbox, no grid and
no CSS positioning. So the shell is two nested presentational tables: an outer
one that paints the page, and an inner one that is `width="100%"` with a
`max-width:600px` cap. That is fluid on a phone and capped on a desktop
without a media query. Media queries also die on a forward, so none of them
may be load bearing here, and none are used.

WHAT THIS MODULE MAY NOT DO.

It may not produce a number. Every figure in a digest is composed by the site
through its own public endpoints (includes/subscribe.php), and a second place
that derives one is a second place that can be wrong. This file receives
already rendered section parts and gives them typography, a shell, a
preheader and a subject. Where it needs a word of its own it takes it from the
section's own first line, rather than from a table of names kept here that
could drift from what the site calls things.

The privacy promise is unchanged: no image, no pixel, no CSS url(), no remote
asset of any kind. `digest_transport.assert_message_is_clean` enforces it, and
this module is written to pass it unmodified rather than to be excused from it.
"""
from __future__ import annotations

import datetime
import re
import textwrap
from html import escape

# ---------------------------------------------------------------------------
# The palette
#
# Every colour is declared on the element, never inherited. Many clients
# invert a light message, so each pair has to work twice: the test checks
# 4.5:1 against the card AND against the inverted card. That is why the muted
# grey is darker than it first looks. A mid grey that reads well on white is
# still a mid grey once the background turns black.
# ---------------------------------------------------------------------------
PAGE_BG = "#eef1f5"
CARD_BG = "#ffffff"
RULE = "#d5dae1"
INK = "#15181d"
MUTED = "#54585f"
LINK = "#0b4f9c"

FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',"
        "Arial,sans-serif")

WIDTH_PX = 600
TEXT_WIDTH = 72
BRAND = "AskTheRecruiter Trackers"

MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")

# The longest preheader a phone shows. A snippet longer than this is REPLACED
# rather than cut, because cutting one mid figure publishes a wrong number in
# the one line of the message most people ever read.
PREHEADER_MAX = 130

# ---------------------------------------------------------------------------
# Typography for the parts the site composed
#
# The site emits its own small inline margins. These replace them, so the two
# do not have to agree and a change here does not need a plugin deploy. Only
# the presentation is touched: no text, no figure and no href is rewritten.
# ---------------------------------------------------------------------------
TAG_STYLES = {
    "h2": (f"margin:0 0 10px;font-family:{FONT};font-size:19px;line-height:1.25;"
           f"font-weight:700;letter-spacing:-0.01em;color:{INK};"),
    "h3": (f"margin:18px 0 8px;font-family:{FONT};font-size:15px;line-height:1.3;"
           f"font-weight:700;color:{INK};"),
    "p": (f"margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;"
          f"color:{INK};"),
    "ul": "margin:0 0 16px;padding:0 0 0 20px;",
    "ol": "margin:0 0 16px;padding:0 0 0 20px;",
    "li": (f"margin:0 0 9px;font-family:{FONT};font-size:15px;line-height:1.55;"
           f"color:{INK};"),
    "a": f"color:{LINK};text-decoration:underline;font-weight:600;",
    "strong": f"font-weight:700;color:{INK};",
    "em": f"font-style:italic;color:{INK};",
}

_OPEN_TAG = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>")
_STYLE_ATTR = re.compile(r"\s*style\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
_DEAD_ATTR = re.compile(r"\s*(class|id)\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)


def restyle(fragment: str) -> str:
    """Put every rule this fragment relies on onto the element itself.

    Also drops `class` and `id`: in an email neither can be styled except from
    a block a forward deletes, so carrying one is carrying the promise of a
    design that will not arrive.
    """
    def rewrite(match):
        tag = match.group(1).lower()
        attrs = _DEAD_ATTR.sub("", _STYLE_ATTR.sub("", match.group(2)))
        attrs = attrs.strip()
        style = TAG_STYLES.get(tag)
        head = f"<{tag}" + (f" {attrs}" if attrs else "")
        return head + (f' style="{style}">' if style else ">")

    return _OPEN_TAG.sub(rewrite, fragment or "")


# ---------------------------------------------------------------------------
# The words this module is allowed to choose
# ---------------------------------------------------------------------------

def section_heading(text_part: str) -> str:
    """What the SITE calls this section. Its own first line, nothing else."""
    for line in (text_part or "").splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def section_lead(text_part: str) -> str:
    """The section's own summary sentence: the line under its heading."""
    lines = [line.strip() for line in (text_part or "").splitlines()]
    lines = [line for line in lines if line]
    return lines[1] if len(lines) > 1 else ""


def period_phrase(payload: dict) -> str:
    """A reader facing date for the window the site already chose.

    Returns an empty string when the payload carries a date this cannot read,
    and every caller treats that as "fall back", never as "guess".
    """
    raw = str((payload or {}).get("to") or "").strip()[:10]
    try:
        day = datetime.date.fromisoformat(raw)
    except ValueError:
        return ""
    stamp = f"{day.day} {MONTHS[day.month - 1]} {day.year}"
    freq = str((payload or {}).get("freq") or "").strip().lower()
    if freq == "weekly":
        return f"the week to {stamp}"
    return stamp


def subject_line(payload: dict, parts) -> str:
    """A subject that says what changed, not that something did.

    "Your digest" tells a reader nothing they cannot see from the sender, and
    in a crowded inbox it is the reason a good email goes unopened. This names
    the trackers that actually have a section in THIS message, using the
    site's own headings, and dates the window. It carries no figure: a number
    in a subject line is a number nobody can correct once it is sent.

    Falls back to the subject the site sent whenever it cannot do better.
    """
    fallback = str((payload or {}).get("subject") or "Tracker digest").strip()
    names = [section_heading(text) for _, _, text in (parts or [])]
    names = [name for name in names if name]
    phrase = period_phrase(payload)
    if not names or not phrase:
        return fallback

    if len(names) == 1:
        joined = names[0]
    else:
        joined = ", ".join(names[:-1]) + " and " + names[-1]
    subject = f"{joined}: {phrase}"
    if len(subject) > 78:
        # Too long to read in a list. Lead with the first and count the rest,
        # which is honest and stays short however many sections there are.
        subject = f"{names[0]} and {len(names) - 1} more: {phrase}"
    return subject if len(subject) <= 78 else fallback


def preheader_text(parts) -> str:
    """The snippet the inbox shows beside the subject.

    With none, the client grabs the first text it finds, which in a careful
    email is usually the unsubscribe line. This uses the leading section's own
    summary sentence, verbatim. When that sentence is too long for the slot it
    is REPLACED by a plain line rather than truncated, because a snippet cut
    mid figure is a wrong number in the inbox.
    """
    for _, _, text in (parts or []):
        lead = section_lead(text)
        if lead and len(lead) <= PREHEADER_MAX:
            return lead
    for _, _, text in (parts or []):
        heading = section_heading(text)
        if heading:
            return f"{heading}: this period's verified figures, inside."
    return "This period's verified figures, inside."


# ---------------------------------------------------------------------------
# The HTML message
# ---------------------------------------------------------------------------

def _cell(inner: str, *, padding: str, top_rule: bool = False) -> str:
    border = f"border-top:1px solid {RULE};" if top_rule else ""
    return (f'<tr><td style="padding:{padding};background-color:{CARD_BG};'
            f'{border}">{inner}</td></tr>')


def _masthead(kicker: str) -> str:
    brand = (f'<p style="margin:0;font-family:{FONT};font-size:17px;'
             f'line-height:1.3;font-weight:700;letter-spacing:0.01em;'
             f'color:{INK};">{escape(BRAND)}</p>')
    if not kicker:
        return brand
    return brand + (f'<p style="margin:6px 0 0;font-family:{FONT};'
                    f'font-size:12px;line-height:1.4;letter-spacing:0.06em;'
                    f'text-transform:uppercase;color:{MUTED};">'
                    f'{escape(kicker)}</p>')


def _footer(unsub_url: str, manage_url: str) -> str:
    small = (f'margin:0 0 8px;font-family:{FONT};font-size:12px;'
             f'line-height:1.6;color:{MUTED};')
    link = f'color:{LINK};text-decoration:underline;'
    manage = ""
    if manage_url:
        manage = (f' You can also <a href="{manage_url}" style="{link}">'
                  f'Manage your subscriptions</a> to change which of these '
                  f'you get.')
    return (f'<p style="{small}">You get this because you confirmed a digest '
            f'subscription at asktherecruiter.com.</p>'
            f'<p style="{small}"><a href="{unsub_url}" style="{link}">'
            f'Unsubscribe with one click</a>, which stops everything at once.'
            f'{manage}</p>'
            f'<p style="margin:0;font-family:{FONT};font-size:12px;'
            f'line-height:1.6;color:{MUTED};">We send no images and no '
            f'tracking pixels, so we cannot tell whether you opened this.</p>')


def render_html(parts, *, subject: str, preheader: str, kicker: str,
                unsub_url: str, manage_url: str) -> str:
    """The whole message. Inline styles only, tables only, no style block."""
    rows = []
    for index, (_, section_html, _) in enumerate(parts):
        padding = "22px 28px 8px" if index else "24px 28px 8px"
        rows.append(_cell(restyle(section_html), padding=padding,
                          top_rule=bool(index)))
    rows.append(_cell(_footer(unsub_url, manage_url),
                      padding="18px 28px 26px", top_rule=True))

    # Hidden, and first, so it is the snippet the client picks up. The colour
    # matches the page for the clients that ignore display:none.
    hidden = (f'<div style="display:none;max-height:0;max-width:0;'
              f'overflow:hidden;opacity:0;font-size:1px;line-height:1px;'
              f'color:{PAGE_BG};mso-hide:all;">{escape(preheader)}</div>')

    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f"<title>{escape(subject)}</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background-color:{PAGE_BG};'
        f'color:{INK};font-family:{FONT};">'
        + hidden
        + f'<table role="presentation" width="100%" cellpadding="0" '
          f'cellspacing="0" border="0" style="width:100%;border-collapse:'
          f'collapse;background-color:{PAGE_BG};">'
          f'<tr><td align="center" style="padding:24px 12px;'
          f'background-color:{PAGE_BG};">'
          f'<table role="presentation" width="{WIDTH_PX}" cellpadding="0" '
          f'cellspacing="0" border="0" align="center" style="width:100%;'
          f'max-width:{WIDTH_PX}px;border-collapse:collapse;'
          f'background-color:{CARD_BG};border:1px solid {RULE};'
          f'border-radius:10px;">'
        + _cell(_masthead(kicker), padding="24px 28px 18px")
        + "".join(rows)
        + "</table></td></tr></table></body></html>")


# ---------------------------------------------------------------------------
# The plain text message
# ---------------------------------------------------------------------------

def _wrap(line: str) -> list:
    """Wrap one line to a terminal width without ever splitting a token.

    A URL is left whole however long it is: a broken link is worse than a
    long line, and a figure must never be split across two lines either.
    """
    stripped = line.strip()
    if not stripped:
        return [""]
    if " " not in stripped:
        return [line.rstrip()]
    indent = len(line) - len(line.lstrip())
    lead = line[:indent]
    hanging = lead
    if stripped.startswith("- "):
        hanging = lead + "  "
    return textwrap.wrap(stripped, width=TEXT_WIDTH, initial_indent=lead,
                         subsequent_indent=hanging, break_long_words=False,
                         break_on_hyphens=False) or [""]


def _reflow(block: str) -> str:
    out = []
    for line in (block or "").rstrip().splitlines():
        out.extend(_wrap(line))
    return "\n".join(out)


def render_text(parts, *, kicker: str, unsub_url: str, manage_url: str) -> str:
    """A real alternative, not a stripped tag byproduct.

    Every figure, every entry and both ways out are here, because for a text
    only client and for every screen reader fallback this IS the message.
    """
    rule = "=" * TEXT_WIDTH
    thin = "-" * TEXT_WIDTH
    head = [BRAND.upper()]
    if kicker:
        head.append(kicker)
    body = []
    for index, (_, _, section_text) in enumerate(parts):
        if index:
            body.append(thin)
        body.append(_reflow(section_text))
    footer = [rule]
    footer.append(_reflow("You get this because you confirmed a digest "
                          "subscription at asktherecruiter.com."))
    footer.append("")
    footer.append("Unsubscribe with one click, which stops everything at once:")
    footer.append(unsub_url)
    if manage_url:
        footer.append("")
        footer.append("Manage your subscriptions, to change which of these "
                      "you get:")
        footer.append(manage_url)
    footer.append("")
    footer.append(_reflow("We send no images and no tracking pixels, so we "
                          "cannot tell whether you opened this."))
    return "\n".join(head + [rule, ""] + body + [""] + footer) + "\n"
