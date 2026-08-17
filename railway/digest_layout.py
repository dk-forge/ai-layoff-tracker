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
# THE ONE NAME, and it is the same string the sender identity uses. The owner
# saw the masthead read "AskTheRecruiter Trackers" in iCloud while the From
# line read "AskTheRecruiter.com", which is two names for one brand inside a
# single message. digest_transport.SENDER_NAME is the authority; this reads it
# so the two cannot drift, and the import is local to keep the layout module
# free of a hard dependency on the transport at import time.
def _brand():
    try:
        from digest_transport import SENDER_NAME
        return SENDER_NAME
    except Exception:
        return "AskTheRecruiter.com"


BRAND = _brand()

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
    "h2": (f"margin:0 0 12px;font-family:{FONT};font-size:19px;line-height:1.25;"
           f"font-weight:700;letter-spacing:-0.01em;color:{INK};"),
    "h3": (f"margin:22px 0 2px;font-family:{FONT};font-size:14px;line-height:1.3;"
           f"font-weight:700;letter-spacing:0.01em;color:{INK};"),
    "p": (f"margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;"
          f"color:{INK};"),
    "ul": "margin:0 0 16px;padding:0 0 0 20px;",
    "ol": "margin:0 0 16px;padding:0 0 0 20px;",
    "li": (f"margin:0 0 9px;font-family:{FONT};font-size:15px;line-height:1.55;"
           f"color:{INK};"),
    "a": f"color:{LINK};text-decoration:underline;font-weight:600;",
    "strong": f"font-weight:700;color:{INK};",
    "em": f"font-style:italic;color:{INK};",
    # The ranked lists. A bullet list cannot align a column of figures, and an
    # unaligned column is the thing a reader has to work at. Two cells, the
    # number right aligned by the `align` ATTRIBUTE rather than by CSS, because
    # Word honours the attribute and ignores half the properties.
    "table": ("width:100%;border-collapse:collapse;margin:0 0 14px;"
              "mso-table-lspace:0;mso-table-rspace:0;"),
    "tr": "",
    "td": (f"padding:7px 0;font-family:{FONT};font-size:15px;line-height:1.4;"
           f"color:{INK};border-bottom:1px solid {RULE};vertical-align:top;"),
}

# ---------------------------------------------------------------------------
# Variants: the site says WHAT a line is, this file says how it looks
#
# The composer marks a line with `data-alt="stat"` and never with a colour or
# a size. So the one place that decides what a headline figure looks like is
# this file, and the one place that decides which figure is a headline is the
# site. The attribute is REMOVED once it has been read: it has no meaning in a
# mail client, and an attribute nobody consumes is a loose end a reader's
# client gets to interpret.
#
# `tabular-nums` is a hint, not a mechanism. Word ignores it and the columns
# still line up, because the alignment is done by the table.
# ---------------------------------------------------------------------------
VARIANT_STYLES = {
    # The eyebrow over a headline figure. Uppercase and letterspaced is how a
    # newspaper marks a label without a rule, a weight change or an image.
    ("p", "kicker"): (f"margin:0 0 4px;font-family:{FONT};font-size:11px;"
                      f"line-height:1.3;font-weight:700;letter-spacing:0.09em;"
                      f"text-transform:uppercase;color:{MUTED};"),
    # The number itself. Nothing else in the message is this size.
    ("p", "stat"): (f"margin:0 0 5px;font-family:{FONT};font-size:34px;"
                    f"line-height:1.1;font-weight:700;letter-spacing:-0.02em;"
                    f"color:{INK};font-variant-numeric:tabular-nums;"),
    # What that number covers. Never optional, because a figure whose scope
    # sits somewhere else stops being true the moment somebody quotes it.
    ("p", "scope"): (f"margin:0 0 16px;font-family:{FONT};font-size:13px;"
                     f"line-height:1.5;color:{MUTED};"),
    # A caption directly under a block heading, same job at list scale.
    ("p", "caption"): (f"margin:0 0 10px;font-family:{FONT};font-size:12px;"
                       f"line-height:1.5;color:{MUTED};"),
    # WHERE THE ROWS BEHIND A FIGURE CAME FROM. Deliberately the same size and
    # the same grey as `scope`, because it is the same kind of fact: it
    # qualifies the figure rather than adding one. Under a headline the two
    # stack as a pair, which is how a newspaper or a Statista chart carries a
    # Note line and a Source line, and it is why this has a name of its own
    # instead of borrowing `scope`: a future session can restyle the sourcing
    # without touching what a figure covers, and the composer still chooses
    # neither.
    ("p", "source"): (f"margin:0 0 16px;font-family:{FONT};font-size:13px;"
                      f"line-height:1.5;color:{MUTED};"),
    # The small print a block earns: a reconciliation, a definition, a basis.
    ("p", "note"): (f"margin:0 0 14px;font-family:{FONT};font-size:13px;"
                    f"line-height:1.55;color:{MUTED};"),
    # The row label and the row figure. Same cell style, different weight and
    # a narrower measure, so a long company name wraps and the number does not.
    ("td", "label"): (f"padding:7px 10px 7px 0;font-family:{FONT};font-size:15px;"
                      f"line-height:1.4;color:{INK};border-bottom:1px solid "
                      f"{RULE};vertical-align:top;"),
    ("td", "figure"): (f"padding:7px 0;font-family:{FONT};font-size:15px;"
                       f"line-height:1.4;font-weight:700;color:{INK};"
                       f"border-bottom:1px solid {RULE};vertical-align:top;"
                       f"white-space:nowrap;font-variant-numeric:tabular-nums;"),
    # The last row of a table drops its rule, so the block does not end on a
    # line that looks like the start of another one.
    ("td", "label-last"): (f"padding:7px 10px 7px 0;font-family:{FONT};"
                           f"font-size:15px;line-height:1.4;color:{INK};"
                           f"vertical-align:top;"),
    ("td", "figure-last"): (f"padding:7px 0;font-family:{FONT};font-size:15px;"
                            f"line-height:1.4;font-weight:700;color:{INK};"
                            f"vertical-align:top;white-space:nowrap;"
                            f"font-variant-numeric:tabular-nums;"),
}

_OPEN_TAG = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>")
_STYLE_ATTR = re.compile(r"\s*style\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
_DEAD_ATTR = re.compile(r"\s*(class|id)\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
_VARIANT_ATTR = re.compile(r"\s*data-alt\s*=\s*\"([^\"]*)\"", re.I)


def restyle(fragment: str) -> str:
    """Put every rule this fragment relies on onto the element itself.

    Also drops `class` and `id`: in an email neither can be styled except from
    a block a forward deletes, so carrying one is carrying the promise of a
    design that will not arrive. `data-alt` is read for its variant and then
    dropped for the same reason.

    An UNKNOWN variant falls back to the plain style for the tag rather than to
    no style at all. A typo in the site's markup should cost a design detail,
    never the readability of a paragraph in a forwarded copy.
    """
    def rewrite(match):
        tag = match.group(1).lower()
        raw = match.group(2)
        variant = ""
        found = _VARIANT_ATTR.search(raw)
        if found:
            variant = found.group(1).strip().lower()
            raw = _VARIANT_ATTR.sub("", raw)
        attrs = _DEAD_ATTR.sub("", _STYLE_ATTR.sub("", raw)).strip()
        style = VARIANT_STYLES.get((tag, variant), TAG_STYLES.get(tag))
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
    """The section's own summary sentence: the line under its heading.

    A list item is NOT a summary, and neither is the continuation line under
    one. The blog section is a heading followed straight by bullets, and
    reading into that list put one article title, and then one article's
    blurb, into the inbox snippet as though it were the digest's headline. So
    this takes only an UNINDENTED prose line, which is the shape a summary
    has in every section that writes one. A section without one has no lead,
    and that is a real answer.
    """
    lines = (text_part or "").splitlines()
    seen_heading = False
    for line in lines:
        if not line.strip():
            continue
        if not seen_heading:
            seen_heading = True
            continue
        if line[:1].isspace() or line.lstrip().startswith(("-", "*", "\u2022")):
            continue
        return line.strip()
    return ""


def part_text(part) -> str:
    """The plain-text half of a section, whatever arity the tuple has.

    Parts gained a fourth member (the section's own preheader) on 2026-08-17.
    Everything here reads by INDEX rather than by unpacking, so a caller
    holding the old three-member shape still works and an older plugin build
    that sends no preheader is a missing member rather than a crash.
    """
    return part[2] if len(part) > 2 else ""


def part_preheader(part) -> str:
    """The one-line inbox snippet the SITE composed for this section.

    Empty when the plugin predates it, which is a real state and not an error:
    preheader_text falls back deliberately.
    """
    return (part[3] if len(part) > 3 else "") or ""


def leading_part(parts):
    """The section the subject names first.

    THIS EXISTS SO TWO THINGS CANNOT DISAGREE. The subject line names sections
    in order and skips any that cannot name themselves; the preheader has to
    describe the section the subject leads with, or the inbox shows a heading
    about one tracker beside a figure from another. Both callers now ask this
    function, so the property is structural rather than a coincidence that
    holds until somebody edits one of them.
    """
    for part in (parts or []):
        if section_heading(part_text(part)):
            return part
    return None


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
    names = [section_heading(part_text(part)) for part in (parts or [])]
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

    WHY THIS NO LONGER BORROWS A SENTENCE FROM THE BODY. It used to walk every
    section and take the first summary sentence that fitted 130 characters.
    That was always a compromise: it borrows a line written for a different
    job, in a different place, under no length budget at all. On 2026-08-17 it
    failed exactly the way a compromise does. The layoff lede grew a measured
    geography clause and reached 143 characters, so this walked past it and
    took the TALENT section's sentence, and the live digest went out with the
    subject leading "AI Layoff Tracker" beside a snippet reading "1,332 new
    hiring signals". The subject and the snippet are the two things every
    recipient sees before deciding whether to open, and they described
    different trackers.

    Nothing was wrong with the fallback: it did what it says. The mechanism
    was wrong. A preheader has one purpose and one hard ceiling, so the SITE
    now composes one for that ceiling out of the same figures the lede uses,
    and the body clause is free to be as long as it needs to be where there is
    room for it.

    THE SECTION IS NOT A CHOICE. It is leading_part(), the same function the
    subject line uses, so the snippet cannot describe a different tracker than
    the subject names first.

    NO FIGURE IS COMPOSED HERE, which is this module's standing rule. Every
    rung of the ladder below is either a string the site handed us or a
    sentence with no number in it at all.

    The ladder, in order, and each rung is deliberate:
      1. the section's own purpose-built preheader;
      2. its summary sentence, when that fits, which is what an older plugin
         build gives us and is still a good line;
      3. its heading plus a plain clause, which carries no figure but does
         name the right tracker.
    A snippet is never truncated: cutting one mid figure publishes a wrong
    number in the one line of the message most people ever read.
    """
    part = leading_part(parts)
    if part is None:
        return "What changed on the trackers this period."

    composed = part_preheader(part).strip()
    if composed and len(composed) <= PREHEADER_MAX:
        return composed

    text = part_text(part)
    lead = section_lead(text)
    if lead and len(lead) <= PREHEADER_MAX:
        return lead

    return f"{section_heading(text)}: what changed this period."


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


# ---------------------------------------------------------------------------
# What we tell a reader about measurement
#
# THE SENTENCE THAT WAS FALSE. Until 2026-08-16 the footer said "We send no
# images and no tracking pixels, so we cannot tell whether you opened this."
# That was true of the message this file builds, and untrue of the message the
# reader received. The owner turned open and click tracking ON in Brevo, and
# Brevo injects its pixel and rewrites the links AT THE RELAY, after we have
# handed the message over. So the digest carried a promise its own delivery
# broke, in the footer, under our name.
#
# The answer is not to delete the sentence. A reader who was told we could not
# measure them is owed the correction, and a service that measures opens and
# clicks should say so in the email doing the measuring. Deleting it would
# leave us tracking people and volunteering nothing, which is worse than
# either honest position.
#
# WHY assert_message_is_clean IS UNCHANGED AND MUST STAY UNCHANGED. Our own
# message still embeds no image, no pixel, no url() and no remote fetch of any
# kind, and that check still refuses to send one that does. The distinction is
# worth keeping: because the tracking is entirely the provider's, switching
# provider removes it, rather than sending us back through our own templates
# unpicking pixels we baked in.
#
# THIS COPY IS COUPLED TO A SETTING NOBODY IN THIS REPO CAN READ. If the owner
# turns tracking off again in the Brevo dashboard, these strings become false
# in the other direction. The places that have to change together are listed
# in docs/RUNBOOK.md under "Open and click tracking".
# ---------------------------------------------------------------------------
TRACKING_SENTENCES = (
    "Our mail provider records whether you open this email and which links "
    "you follow.",
    "We read it to see which sections are worth keeping.",
    "Unsubscribing stops the email and the measuring together.",
)


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
            f'line-height:1.6;color:{MUTED};">'
            + escape(" ".join(TRACKING_SENTENCES)) + '</p>')


def render_html(parts, *, subject: str, preheader: str, kicker: str,
                unsub_url: str, manage_url: str) -> str:
    """The whole message. Inline styles only, tables only, no style block."""
    rows = []
    for index, part in enumerate(parts):
        section_html = part[1]
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
    for index, part in enumerate(parts):
        if index:
            body.append(thin)
        body.append(_reflow(part_text(part)))
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
    footer.append(_reflow(" ".join(TRACKING_SENTENCES)))
    return "\n".join(head + [rule, ""] + body + [""] + footer) + "\n"
