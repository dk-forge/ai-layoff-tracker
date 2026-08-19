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
    # ------------------------------------------------------------------
    # The edition furniture, added 2026-08-19 when the weekly digest was
    # rebuilt as an edition. The owner read a live send and said the whole
    # thing was confusing, and the fault was that it had no editorial spine:
    # it opened on a figure, not on a story, and nothing told a reader what had
    # happened before it started qualifying it.
    #
    # DATELINE, LEAD, WHY. A newspaper's grammar, and each has a different job,
    # so each gets a different weight. The dateline is small print that says
    # which edition this is. The lead is the biggest body text in the message,
    # because it is the two lines a reader is allowed to stop after. The "why
    # it matters" line is Axios's, and it is set in ink rather than grey with a
    # rule above it so a skimmer's eye stops on it.
    # ------------------------------------------------------------------
    ("p", "dateline"): (f"margin:0 0 14px;font-family:{FONT};font-size:12px;"
                        f"line-height:1.5;letter-spacing:0.04em;"
                        f"text-transform:uppercase;color:{MUTED};"),
    ("p", "lead"): (f"margin:0 0 10px;font-family:{FONT};font-size:18px;"
                    f"line-height:1.45;color:{INK};"),
    # A section's own opening line, below the lead's weight. It frames a block
    # rather than opening the edition.
    ("p", "standfirst"): (f"margin:0 0 10px;font-family:{FONT};font-size:15px;"
                          f"line-height:1.5;color:{INK};"),
    ("p", "why"): (f"margin:0 0 20px;padding:10px 0 0;font-family:{FONT};"
                   f"font-size:14px;line-height:1.55;color:{INK};"
                   f"border-top:1px solid {RULE};"),
    # A single derived observation that earns its own line rather than a clause
    # at the end of another sentence. "Technology is ninth, at 1%" was set as
    # grey small print inside the composition note; the owner picked it out of
    # the delivered email as the most striking thing in it.
    ("p", "finding"): (f"margin:0 0 14px;font-family:{FONT};font-size:15px;"
                       f"line-height:1.5;font-weight:700;color:{INK};"),
    # ------------------------------------------------------------------
    # TWO HEADLINE FIGURES SIDE BY SIDE. The owner asked for the United States
    # and worldwide together rather than one of them, so they are two cells of
    # one presentational table at 50% each: equals, not a total and a subtotal.
    #
    # 28px AND NOT THE 34px OF A LONE STAT. At 375px the card is about 295px
    # wide inside its padding, so each cell is roughly 147px, and a seven
    # character figure at 34px does not fit that. This is measured against the
    # widest figure the tracker has ever published rather than against the
    # current week.
    # ------------------------------------------------------------------
    ("td", "pair-left"): (f"padding:6px 12px 10px 0;font-family:{FONT};"
                          f"vertical-align:top;width:50%;"),
    ("td", "pair-right"): (f"padding:6px 0 10px 12px;font-family:{FONT};"
                           f"vertical-align:top;width:50%;"),
    ("p", "stat-pair"): (f"margin:0 0 4px;font-family:{FONT};font-size:28px;"
                         f"line-height:1.1;font-weight:700;"
                         f"letter-spacing:-0.02em;color:{INK};"
                         f"font-variant-numeric:tabular-nums;"),
    # The change on the previous week. The glyph is U+25B2 or U+25BC, geometric
    # characters every client draws as text; an emoji here would be a coloured
    # picture in half of them and a box in the other half. The DIRECTION IS ALSO
    # IN THE WORD beside it, so nothing is lost when the glyph does not render
    # and a screen reader still says which way it went.
    # What the paired figure COUNTS, on the cell, under the number. The scope
    # sentence below the pair says it too, at length; this is the half that
    # survives a screenshot of the block.
    # THE SIGNATURE METRIC. One line, always present, always the same shape:
    # the period's value and the cumulative one, adjacent. It is set at 20px
    # rather than the 28px of a headline figure because it is deliberately NOT
    # a headline: half the complete weeks of 2026 recorded zero, so a series
    # that is mostly zero cannot carry the top of an edition. Big enough to be
    # unmissable, small enough not to claim the week.
    ("p", "signature"): (f"margin:0 0 8px;font-family:{FONT};font-size:20px;"
                         f"line-height:1.3;font-weight:700;"
                         f"letter-spacing:-0.01em;color:{INK};"
                         f"font-variant-numeric:tabular-nums;"),
    ("p", "unit"): (f"margin:0 0 6px;font-family:{FONT};font-size:13px;"
                    f"line-height:1.4;color:{MUTED};"),
    ("p", "change"): (f"margin:0;font-family:{FONT};font-size:13px;"
                      f"line-height:1.4;font-weight:700;color:{MUTED};"),
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
    # ------------------------------------------------------------------
    # The article item. THE SECTION THIS EMAIL WAS WEAKEST AT, and the one a
    # general reader most wants: it printed a title and a severed first
    # sentence in a bullet list, which is a list of links with extra words.
    #
    # The separation is a `border-top` on the item's own `td`, not an `<hr>`
    # and not an empty spacer row. That is measured rather than preferred:
    # caniemail puts `<table>` at 100% support and `<hr>` at 72.97%, and Email
    # on Acid's spacing survey says outright that empty table cells do not
    # reliably retain their height, while `padding` is reliable ON A CELL (not
    # on a table, which desktop Outlook ignores). So every gap in this block is
    # cell padding and every rule is a cell border.
    #
    # Three sizes, so the block has a shape a skimmer can enter at any point:
    # the title is the biggest thing in the section after its heading, the
    # standfirst is body size, and the meta line is the same grey small print
    # every other qualifier in this email uses. Nothing is below 14px: iOS
    # enlarges smaller text by itself, which would break the hierarchy on the
    # device most of these are read on.
    # ------------------------------------------------------------------
    ("td", "item"): (f"padding:14px 0 0;font-family:{FONT};"
                     f"border-top:1px solid {RULE};vertical-align:top;"),
    ("td", "item-first"): (f"padding:2px 0 0;font-family:{FONT};"
                           f"vertical-align:top;"),
    ("p", "item-title"): (f"margin:0 0 5px;font-family:{FONT};font-size:17px;"
                          f"line-height:1.35;font-weight:700;"
                          f"letter-spacing:-0.01em;color:{INK};"),
    ("p", "item-blurb"): (f"margin:0 0 5px;font-family:{FONT};font-size:15px;"
                          f"line-height:1.5;color:{INK};"),
    ("p", "item-meta"): (f"margin:0 0 14px;font-family:{FONT};font-size:13px;"
                         f"line-height:1.5;color:{MUTED};"),
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


def part_metric(part):
    """The figure-and-unit fragment the SITE composed for the subject line.

    Returns (metric, minor). Empty when the plugin predates it, which is a real
    state and not an error: subject_line falls back to the edition label.

    NO FIGURE IS PRODUCED HERE, which is this module's standing rule. The site
    computes the number and wears the unit on it; this joins strings.
    """
    if len(part) > 4 and isinstance(part[4], (tuple, list)):
        metric, minor = (list(part[4]) + ["", False])[:2]
        return (str(metric or "").strip(), bool(minor))
    return (str(part[4]).strip() if len(part) > 4 and part[4] else "", False)


def week_id(day: datetime.date) -> str:
    """"2026 Week 33". The week identified without its dates, for a subject.

    THE ISO YEAR, not the calendar year: the week of 28 December 2026 is 2026
    Week 53 and the week of 31 December 2029 is 2030 Week 1. Year first, so a
    mailbox sorted by subject sorts by edition.
    """
    iso = day.isocalendar()
    return f"{iso[0]} Week {iso[1]}"


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


def _stamp(day: datetime.date) -> str:
    return f"{MONTHS[day.month - 1]} {day.day}, {day.year}"


def date_range(start: datetime.date, end: datetime.date) -> str:
    """The site's alt_digest_date_range, ported. One date shape in one email.

    MONTH FIRST. The owner read a live send and said "10 to 16 August 2026" is
    hard to read. Month first fixes the unit before the numerals arrive, which
    is why it is the US convention and why every US statistical release uses
    it. Four shapes, each the shortest form that stays unambiguous:

        one day               August 16, 2026
        inside one month      August 10-16, 2026
        across two months     August 31 - September 6, 2026
        across two years      December 28, 2026 - January 3, 2027

    The hyphen is tight between two numerals and spaced between two multi-word
    dates. It is a plain hyphen and never an em-dash, which is banned in copy
    here, and never an en-dash, which is one more character to be mangled.
    """
    if start == end:
        return _stamp(end)
    if start.year != end.year:
        return f"{_stamp(start)} - {_stamp(end)}"
    if start.month != end.month:
        return (f"{MONTHS[start.month - 1]} {start.day} - "
                f"{MONTHS[end.month - 1]} {end.day}, {end.year}")
    return f"{MONTHS[start.month - 1]} {start.day}-{end.day}, {end.year}"


def week_label(day: datetime.date) -> str:
    """"Week 33", on ISO-8601, which is the only numbering that checks out.

    THE ISO YEAR IS NOT THE CALENDAR YEAR and that is the whole trap. ISO week
    1 holds the first Thursday of January, so 1 January 2027 is week 53 of ISO
    year 2026 and 31 December 2029 is week 1 of ISO year 2030.
    `date.isocalendar()` returns (iso_year, iso_week, iso_weekday) and this
    reads member 1, never `day.year`. The site computes the same number with
    PHP's `W`, and tests/test_digest_week_numbering.py drives both over real
    boundary dates and fails on any disagreement.
    """
    return f"Week {day.isocalendar()[1]}"


def period_phrase(payload: dict) -> str:
    """A reader facing date for the window the site already chose.

    Weekly is an EDITION LABEL: the ISO week number and the dates it covers,
    together, always. A bare "Week 33" is a label a reader has to look up, and
    two readers on two conventions look it up differently; the dates make it
    self-checking. Daily is the send date, because a day is not a week.

    Returns an empty string when the payload carries a date this cannot read,
    and every caller treats that as "fall back", never as "guess".
    """
    raw_to = str((payload or {}).get("to") or "").strip()[:10]
    raw_from = str((payload or {}).get("from") or "").strip()[:10]
    try:
        end = datetime.date.fromisoformat(raw_to)
    except ValueError:
        return ""
    freq = str((payload or {}).get("freq") or "").strip().lower()
    if freq != "weekly":
        return _stamp(end)
    try:
        start = datetime.date.fromisoformat(raw_from)
    except ValueError:
        return ""
    # A MIDDLE DOT AND NOT A COMMA: an ISO week is identified, not described by
    # an endpoint, and the date already carries a comma of its own.
    return f"{week_label(start)} \u00b7 {date_range(start, end)}"


def subject_line(payload: dict, parts) -> str:
    """One pattern for all three streams, chosen by the owner.

        AskTheRecruiter.com · <period>: <figure> <unit>

        AskTheRecruiter.com · 2026 Week 33: 16,842 verified job cuts
        AskTheRecruiter.com · 2026 Week 33: 1,376 hiring signals
        AskTheRecruiter.com · 2026 Week 33: 16,842 verified job cuts · 1,376 hiring signals

    The brand up front lets a subscriber identify sender and topic in a crowded
    inbox, the middle dot gives a cleaner hierarchy than a space, and the three
    read as one weekly series.

    AND IT FIXES AN ACCURACY DEFECT STRUCTURALLY. What shipped on 2026-08-19
    was "AI Layoff Tracker: 16,842 verified cuts this week", and a reader who
    never opened it took away sixteen thousand AI-attributed cuts from a week
    whose AI figure was ZERO. Leading with the SITE rather than a tracker means
    nothing juxtaposes "AI Layoff Tracker" with a raw cut count, so the line
    cannot be read as an AI figure at all. The standing rule, enforced by
    tests/test_digest_subject_never_inflates_ai.py:

        A READER WHO SEES ONLY THE SUBJECT MUST NOT COME AWAY WITH A LARGER AI
        FIGURE THAN THE EMAIL REPORTS.

    THE TWO UNITS READ DIFFERENTLY BECAUSE THEY ARE DIFFERENT. Verified job
    cuts each have a filing or a named report behind them; hiring signals are
    deliberately weaker, a published indication that is mostly unverified. A
    consistency pass must not flatten one into the other.

    NO FIGURE IS COMPOSED HERE. Every fragment is a string the site built from
    the same query as the body.

    THIS IS A LINE FOR LINE PORT of alt_digest_subject_line in
    includes/subscribe.php, and tests/test_digest_subject_agreement.py drives
    both over the same inputs and fails on any difference.
    """
    fallback = str((payload or {}).get("subject") or "Tracker digest").strip()

    major, minor = [], []
    for part in (parts or []):
        metric, is_minor = part_metric(part)
        if not metric:
            continue
        (minor if is_minor else major).append(metric)
    metrics = major or minor

    freq = str((payload or {}).get("freq") or "").strip().lower()
    period = ""
    if freq == "weekly":
        try:
            period = week_id(datetime.date.fromisoformat(
                str((payload or {}).get("from") or "").strip()[:10]))
        except ValueError:
            period = ""
    else:
        try:
            period = _stamp(datetime.date.fromisoformat(
                str((payload or {}).get("to") or "").strip()[:10]))
        except ValueError:
            period = ""

    if metrics and period:
        # Two at most. A third runs past any client's display width and buys
        # nothing a reader can see.
        line = f"{BRAND} · {period}: " + " · ".join(metrics[:2])
        # THE CEILING IS 100 AND NOT 78. The combined line runs to about 83 and
        # the owner chose it knowing Gmail on mobile truncates near 45. It is
        # meant to be read from the left and completed by the preheader.
        if len(line) <= 100:
            return line
        # One metric rather than a truncated two: a subject cut mid-figure
        # publishes a wrong number in the line most people only ever see.
        line = f"{BRAND} · {period}: {metrics[0]}"
        if len(line) <= 100:
            return line

    names = [section_heading(part_text(part)) for part in (parts or [])]
    names = [name for name in names if name]
    phrase = period_phrase(payload)
    if not names or not phrase:
        return fallback
    subject = f"{names[0]}, {phrase}"
    if len(subject) > 100:
        subject = phrase
    return subject if len(subject) <= 100 else fallback


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

    # ------------------------------------------------------------------
    # WHAT THE TRUNCATED SUBJECT LEAVES HANGING, and never a restatement.
    #
    # The subject leads with the brand, which costs about twenty characters the
    # From name already supplies, and Gmail on mobile truncates near 45. So on
    # a phone the reader sees roughly "AskTheRecruiter.com · 2026 Week 33: 16,8"
    # and the SECOND metric is what falls off the end. The preheader is the one
    # slot left to recover it, so on a combined edition it leads with that
    # second metric and then continues into the leading section's own snippet.
    #
    # It is a JOIN of strings the site composed, never a figure produced here.
    # A line that will not fit is dropped whole rather than cut: a snippet
    # truncated mid-figure publishes a wrong number in the one line of the
    # message most people ever read.
    # ------------------------------------------------------------------
    metrics = []
    for one in (parts or []):
        metric, minor = part_metric(one)
        if metric and not minor:
            metrics.append(metric)
    if len(metrics) >= 2 and composed:
        completed = f"{metrics[1]}. {composed}"
        if len(completed) <= PREHEADER_MAX:
            return completed

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


# HOW A WEEK IS NUMBERED, SAID ONCE, IN THE EDITION THAT USES ONE.
#
# The point of putting a number on a week is that a reader can tell which week
# they are holding, and that only works if they can tell which convention it
# is. Two exist in common use and they disagree for part of every week. ISO is
# the international standard, the number is correct by definition rather than
# by convention, and this is a worldwide tracker whose readers are mostly not
# on the US calendar.
#
# It is not composed from data and carries no figure, which is why this module
# is allowed to hold it. It is passed in as a note rather than written into the
# footer unconditionally, because a DAILY edition has no week number and a
# sentence explaining one it never printed is noise.
WEEK_CONVENTION = ("Weeks are ISO-8601: Monday to Sunday, numbered from the "
                   "week holding the year's first Thursday.")


def _footer(unsub_url: str, manage_url: str, edition_note: str = "") -> str:
    """The two things a reader may need, then the small print, in that order.

    THE MEASUREMENT DISCLOSURE MOVED DOWN A LEVEL, and that is the whole change
    here. It is honest, it is required, and it was set at the same size and the
    same weight as the sentence telling a reader how to leave, which put a
    paragraph about analytics at the same rank as the content of the email. It
    is now under its own rule, at 11px, which is where small print belongs.
    NOTHING IS DELETED and nothing is softened: a reader who was told we could
    not measure them is owed the correction, and every word of
    TRACKING_SENTENCES still ships.
    """
    small = (f'margin:0 0 8px;font-family:{FONT};font-size:12px;'
             f'line-height:1.6;color:{MUTED};')
    fine = (f'margin:0 0 6px;font-family:{FONT};font-size:11px;'
            f'line-height:1.6;color:{MUTED};')
    link = f'color:{LINK};text-decoration:underline;'
    manage = ""
    if manage_url:
        manage = (f' You can also <a href="{manage_url}" style="{link}">'
                  f'Manage your subscriptions</a> to change which of these '
                  f'you get.')
    note = f'<p style="{fine}">{escape(edition_note)}</p>' if edition_note else ""
    return (f'<p style="{small}">You get this because you confirmed a digest '
            f'subscription at asktherecruiter.com.</p>'
            f'<p style="{small}"><a href="{unsub_url}" style="{link}">'
            f'Unsubscribe with one click</a>, which stops everything at once.'
            f'{manage}</p>'
            f'<table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0" style="width:100%;'
            f'border-collapse:collapse;margin:14px 0 0;">'
            f'<tr><td style="padding:12px 0 0;border-top:1px solid {RULE};'
            f'background-color:{CARD_BG};color:{MUTED};">'
            f'{note}'
            f'<p style="margin:0;font-family:{FONT};font-size:11px;'
            f'line-height:1.6;color:{MUTED};">'
            + escape(" ".join(TRACKING_SENTENCES)) +
            '</p></td></tr></table>')


def render_html(parts, *, subject: str, preheader: str, kicker: str,
                unsub_url: str, manage_url: str,
                edition_note: str = "") -> str:
    """The whole message. Inline styles only, tables only, no style block."""
    rows = []
    for index, part in enumerate(parts):
        section_html = part[1]
        padding = "22px 28px 8px" if index else "24px 28px 8px"
        rows.append(_cell(restyle(section_html), padding=padding,
                          top_rule=bool(index)))
    rows.append(_cell(_footer(unsub_url, manage_url, edition_note),
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


def render_text(parts, *, kicker: str, unsub_url: str, manage_url: str,
                edition_note: str = "") -> str:
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
    if edition_note:
        footer.append(_reflow(edition_note))
        footer.append("")
    footer.append(_reflow(" ".join(TRACKING_SENTENCES)))
    return "\n".join(head + [rule, ""] + body + [""] + footer) + "\n"
