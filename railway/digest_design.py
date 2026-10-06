"""The subscriber email design: a colour per tracker, highlights, small charts.

Owner request TRACKER-EMAIL-QUALITY. The design was shown to the owner on
2026-09-29 and approved; the content order shipped 2026-10-01, and this module
is the visual half that had not: a red accent on the layoff section, a blue
accent on the talent section, green for a highlighted finding, bold section
headings, a bigger lead number and small bar charts.

WHY THE CHARTS ARE TABLE CELLS AND NEVER AN IMAGE.

`digest_transport.assert_message_is_clean` refuses any message that fetches
from a server, and that check must not be weakened. An inline (cid) PNG would
also be a picture with no text in it. A bar here is one table cell with a
percentage `width` attribute and a `bgcolor` attribute, which Outlook's Word
engine draws, every webmail draws, and a forward cannot strip (the style is
inline). It is `aria-hidden`: the figure each bar stands for is printed in the
same row, so a screen reader or a client that drops the bar loses nothing.

WHAT A BAR IS NOT. It is not a figure. Its length is the row's own printed
figure relative to the largest printed figure in the same block, read from the
strings the site composed. Nothing is summed, nothing is published, and a block
whose figures cannot all be read draws no chart rather than a wrong one.

The colours clear 4.5:1 on the white card and again on the inverted card that a
dark-mode client produces; tests/test_digest_email_design.py checks both.
"""
from __future__ import annotations

import re

RED = "#b42a18"      # AI Layoff Tracker (no 4-digit run: a hex is not a figure)
BLUE = "#1d4ed8"     # Talent Intelligence Tracker
GREEN = "#067647"    # highlights
GREEN_BG = "#ecfdf3"
TRACK = "#e4e7ec"    # the unfilled part of a bar
NEUTRAL = "#15181d"  # sections that belong to neither tracker (the blog)

_ACCENTS = {"layoff": RED, "follows": RED, "talent": BLUE}

BAR_HEIGHT_PX = 8
MAX_BARS = 8

# FIXED REGION COLOURS (redesign stage 2, 2026-10-06). A region wears the same
# colour in every edition, so a reader learns it once. Okabe-Ito hues, which
# stay distinguishable under the common colour-vision deficiencies; the three
# residual lines share one neutral grey because they are not places. The bars
# are decoration (aria-hidden): the label and figure are always text.
REGION_COLOURS = {
    "United States": "#0b72b2",
    "Canada": "#d55e00",
    "United Kingdom": "#cc79a7",
    "Europe": "#009e73",
    "Asia Pacific": "#e69f00",
    "Latin America": "#56b4e9",
    "Middle East and Africa": "#7a51a5",
    "Elsewhere": "#6b7a8f",
    "Multiple countries, no split given": "#6b7a8f",
    "No country recorded": "#6b7a8f",
}


def accent_for(section: str) -> str:
    """The accent colour of a composed section, by its list key."""
    return _ACCENTS.get((section or "").strip().lower(), NEUTRAL)


def accent_styles(accent: str, font: str, ink: str, muted: str) -> dict:
    """Per-section overrides for digest_layout's tag and variant styles."""
    return {
        ("h2", ""): (f"margin:0 0 14px;padding:2px 0 2px 12px;font-family:{font};"
                     f"font-size:22px;line-height:1.25;font-weight:800;"
                     f"letter-spacing:-0.01em;color:{accent};"
                     f"border-left:4px solid {accent};"),
        ("h3", ""): (f"margin:24px 0 6px;font-family:{font};font-size:15px;"
                     f"line-height:1.3;font-weight:700;letter-spacing:0.01em;"
                     f"color:{accent};"),
        ("p", "stat"): (f"margin:0 0 5px;font-family:{font};font-size:40px;"
                        f"line-height:1.05;font-weight:800;letter-spacing:-0.02em;"
                        f"color:{accent};font-variant-numeric:tabular-nums;"),
        ("p", "stat-pair"): (f"margin:0 0 4px;font-family:{font};font-size:30px;"
                             f"line-height:1.1;font-weight:800;"
                             f"letter-spacing:-0.02em;color:{accent};"
                             f"font-variant-numeric:tabular-nums;"),
        ("p", "kicker"): (f"margin:0 0 4px;font-family:{font};font-size:11px;"
                          f"line-height:1.3;font-weight:700;letter-spacing:0.09em;"
                          f"text-transform:uppercase;color:{accent};"),
        ("p", "finding"): (f"margin:0 0 14px;padding:10px 12px;font-family:{font};"
                           f"font-size:15px;line-height:1.5;font-weight:700;"
                           f"color:{ink};background-color:{GREEN_BG};"
                           f"border-left:3px solid {GREEN};"),
        ("p", "why"): (f"margin:0 0 20px;padding:10px 0 0;font-family:{font};"
                       f"font-size:14px;line-height:1.55;color:{ink};"
                       f"border-top:2px solid {GREEN};"),
        ("table", "chart"): ("width:100%;border-collapse:collapse;margin:6px 0 0;"
                             "mso-table-lspace:0;mso-table-rspace:0;"),
        ("table", "series-chart"): ("width:100%;border-collapse:collapse;"
                                    "margin:0 0 16px;mso-table-lspace:0;"
                                    "mso-table-rspace:0;"),
        ("td", "bar"): (f"padding:0;height:{BAR_HEIGHT_PX}px;font-size:0;"
                        f"line-height:0;font-family:{font};color:{accent};"
                        f"background-color:{accent};border-radius:2px;"),
        ("td", "track"): (f"padding:0;height:{BAR_HEIGHT_PX}px;font-size:0;"
                          f"line-height:0;font-family:{font};color:{muted};"
                          f"background-color:{TRACK};"),
        ("td", "chart-label"): (f"padding:4px 10px 4px 0;font-family:{font};"
                                f"font-size:13px;line-height:1.3;color:{ink};"
                                f"white-space:nowrap;vertical-align:middle;"
                                f"width:30%;"),
        ("td", "chart-cell"): (f"padding:4px 0;font-family:{font};font-size:13px;"
                               f"line-height:1.3;color:{ink};"
                               f"vertical-align:middle;"),
        ("td", "chart-figure"): (f"padding:4px 0 4px 10px;font-family:{font};"
                                 f"font-size:13px;line-height:1.3;font-weight:700;"
                                 f"color:{ink};white-space:nowrap;"
                                 f"vertical-align:middle;width:1%;"
                                 f"font-variant-numeric:tabular-nums;"),
    }


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_TAGS = re.compile(r"<[^>]+>")
_RANK_ROW = re.compile(
    r'(<td data-alt="label(?:-last)?">)(.*?)(</td>\s*<td data-alt="figure'
    r'(?:-last)?"[^>]*>)(.*?)(</td>)', re.S)
_RANK_TABLE = re.compile(r"<table\b[^>]*>(?:(?!</table>).)*?data-alt=\"label"
                         r"(?:(?!</table>).)*</table>", re.S)
_SERIES = re.compile(r'(<p data-alt="series">)(.*?)(</p>)', re.S)
_SERIES_ITEM = re.compile(r"^(?P<label>.+?)\s+(?P<fig>\d[\d,]*(?:\.\d+)?%?)$")


def _value(text: str):
    found = _NUM.search(_TAGS.sub("", text or ""))
    if not found:
        return None
    try:
        return float(found.group(0).replace(",", ""))
    except ValueError:
        return None


def _widths(values):
    top = max(values) if values else 0
    if not top or top <= 0:
        return None
    return [max(1, round(v / top * 100)) if v > 0 else 0 for v in values]


def _bar(width: int, accent: str) -> str:
    """One bar: a filled cell and, unless it is full, the unfilled track."""
    if width <= 0:
        cells = '<td data-alt="track" width="100%">&nbsp;</td>'
    else:
        cells = (f'<td data-alt="bar" width="{width}%" bgcolor="{accent}">'
                 f'&nbsp;</td>')
        if width < 100:
            cells += (f'<td data-alt="track" width="{100 - width}%" '
                      f'bgcolor="{TRACK}">&nbsp;</td>')
    return ('<table data-alt="chart" role="presentation" aria-hidden="true" '
            'width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>{cells}</tr></table>')


def _chart_rank_table(table: str, accent: str) -> str:
    rows = _RANK_ROW.findall(table)
    values = [_value(r[3]) for r in rows]
    if len(rows) < 2 or any(v is None for v in values):
        return table
    widths = _widths(values)
    if widths is None:
        return table
    it = iter(widths)

    def put(match):
        return (match.group(1) + match.group(2) + _bar(next(it), accent)
                + match.group(3) + match.group(4) + match.group(5))
    return _RANK_ROW.sub(put, table)


def _series_items(inner: str):
    text = _TAGS.sub("", inner).replace("&amp;", "&")
    items = [i.strip() for i in text.split("·")]
    if len(items) < 2:
        return None
    if ": " in items[0]:
        items[0] = items[0].rsplit(": ", 1)[1]
    if ". " in items[-1]:
        items[-1] = items[-1].split(". ", 1)[0]
    items[-1] = items[-1].rstrip(".")
    out = []
    for item in items[:MAX_BARS]:
        found = _SERIES_ITEM.match(item)
        if not found:
            return None
        out.append((found.group("label"), found.group("fig")))
    return out


def _chart_series(match, accent: str) -> str:
    whole = match.group(0)
    items = _series_items(match.group(2))
    if not items:
        return whole
    widths = _widths([_value(fig) or 0 for _, fig in items])
    if widths is None:
        return whole
    from html import escape
    rows = "".join(
        f'<tr><td data-alt="chart-label">{escape(label)}</td>'
        f'<td data-alt="chart-cell">{_bar(width, REGION_COLOURS.get(label, accent))}</td>'
        f'<td data-alt="chart-figure" align="right">{escape(fig)}</td></tr>'
        for (label, fig), width in zip(items, widths))
    return (whole + '<table data-alt="series-chart" role="presentation" '
            'aria-hidden="true" width="100%" cellpadding="0" cellspacing="0" '
            f'border="0">{rows}</table>')


def add_charts(fragment: str, accent: str = RED) -> str:
    """Add a small bar chart to every ranked table and every series line.

    Runs on the site's markup BEFORE digest_layout.restyle, so the injected
    cells are styled by the same mechanism as everything else (their
    `data-alt` names a variant and is consumed).
    """
    fragment = fragment or ""
    fragment = _RANK_TABLE.sub(lambda m: _chart_rank_table(m.group(0), accent),
                               fragment)
    return _SERIES.sub(lambda m: _chart_series(m, accent), fragment)
