"""The shared subscriber-email visual spec, as tokens and two shell helpers.

Owner decision 2026-10-15: the two trackers' subscriber emails share ONE
visual spec, and this module is written so it can be copied byte for byte into
the sibling repo. It imports nothing from either tracker. Change a token here
and in the sibling together, or the two emails drift apart.

WHAT LIVES HERE: the font stack, the light and dark palettes, the card radius,
the brand header (the "AskTheRecruiter" small-caps wordmark line above the
product name) and the one optional <style> block that switches a client which
honours `prefers-color-scheme` to the dark palette.

THE STYLE BLOCK IS AN ENHANCEMENT AND NEVER A DEPENDENCY. Every light-mode
style is inline, because Gmail and a forward both delete <head> and every
<style>. The block holds a single `@media (prefers-color-scheme: dark)` rule
set and nothing else, so deleting it changes nothing a light-mode reader sees.
tests/test_email_theme.py holds that, and the contrast pairs in both palettes.
"""
from __future__ import annotations

from html import escape

FONT = "-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"

# Light palette.
INK = "#111827"
MUTED = "#4b5563"
BACKGROUND = "#ffffff"   # the card
PANEL = "#f3f4f6"        # the page behind the card, and inset panels
BORDER = "#e5e7eb"
PILL_BG = "#eef1f5"     # the tint behind an item card's pills
ACCENT = "#1d4ed8"       # links and buttons

# Dark palette.
DARK_BG = "#0b1220"
DARK_PANEL = "#111a2e"
DARK_INK = "#e5e7eb"
DARK_MUTED = "#9ca3af"
DARK_ACCENT = "#93c5fd"

# Light tints a section may set inline, and what each becomes in dark mode.
# Kept generic (any tracker's highlight green, bar track grey, panel) so the
# sibling repo can copy this list as is.
DARK_TINTS = ((PILL_BG, "#1f2a44"), ("#ecfdf3", "#0f2a1d"), ("#e4e7ec", "#26324d"),
              (PANEL, DARK_BG), (BACKGROUND, DARK_PANEL))
# Near-black rules and accents that vanish on a dark card.
DARK_RULES = (("#15181d", DARK_MUTED), (INK, DARK_MUTED), (BORDER, "#1f2a44"))

RADIUS_PX = 8
WIDTH_PX = 600
WORDMARK = "AskTheRecruiter"

# Class names the dark block targets. Inline styles carry the light values;
# a class only ever ADDS the dark override.
CLASSES = {
    "page": "et-page",
    "card": "et-card",
    "panel": "et-panel",
    "ink": "et-ink",
    "muted": "et-muted",
    "link": "et-link",
    "rule": "et-rule",
}

LIGHT_PAIRS = ((INK, BACKGROUND), (MUTED, BACKGROUND), (ACCENT, BACKGROUND),
               (INK, PANEL), (MUTED, PANEL), (ACCENT, PANEL))
DARK_PAIRS = ((DARK_INK, DARK_BG), (DARK_MUTED, DARK_BG), (DARK_ACCENT, DARK_BG),
              (DARK_INK, DARK_PANEL), (DARK_MUTED, DARK_PANEL),
              (DARK_ACCENT, DARK_PANEL))


def _lum(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a: str, b: str) -> float:
    """WCAG 2 contrast ratio of two #rrggbb colours."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def dark_style_block() -> str:
    """The single optional <style>: dark-mode overrides and nothing else."""
    c = CLASSES
    rules = (
        f".{c['page']}{{background-color:{DARK_BG}!important;}}"
        f".{c['card']}{{background-color:{DARK_PANEL}!important;"
        f"border-color:{DARK_PANEL}!important;}}"
        f".{c['panel']}{{background-color:{DARK_BG}!important;}}"
        f".{c['card']} p,.{c['card']} td,.{c['card']} li,.{c['card']} h2,"
        f".{c['card']} h3,.{c['card']} span,.{c['ink']}{{color:{DARK_INK}!important;}}"
        f".{c['muted']}{{color:{DARK_MUTED}!important;}}"
        f".{c['card']} a,.{c['link']}{{color:{DARK_ACCENT}!important;}}"
        f".{c['rule']}{{border-color:#1f2a44!important;}}"
        # Inline light tints that would otherwise stay light under dark ink.
        + "".join(f'.{c["card"]} [style*="background-color:{light}"],'
                  f'.{c["card"]} [bgcolor="{light}"]'
                  f'{{background-color:{dark}!important;}}'
                  for light, dark in DARK_TINTS)
        + "".join(f'.{c["card"]} [style*="solid {light}"]'
                  f'{{border-color:{dark}!important;}}'
                  for light, dark in DARK_RULES)
    )
    return ("<style>:root{color-scheme:light dark;supported-color-schemes:"
            "light dark;}@media (prefers-color-scheme: dark){" + rules + "}</style>")


def head_meta() -> str:
    return ('<meta name="color-scheme" content="light dark">'
            '<meta name="supported-color-schemes" content="light dark">')


def brand_header(product: str, kicker: str = "") -> str:
    """The wordmark line, then the product name, then an optional kicker."""
    out = (f'<p class="{CLASSES["muted"]}" style="margin:0;font-family:{FONT};'
           f'font-size:13px;line-height:1.4;font-weight:600;'
           f'font-variant:small-caps;letter-spacing:0.08em;color:{MUTED};">'
           f'{escape(WORDMARK)}</p>'
           f'<p class="{CLASSES["ink"]}" style="margin:2px 0 0;font-family:{FONT};'
           f'font-size:20px;line-height:1.25;font-weight:800;'
           f'letter-spacing:-0.01em;color:{INK};">{escape(product)}</p>')
    if kicker:
        out += (f'<p class="{CLASSES["muted"]}" style="margin:6px 0 0;'
                f'font-family:{FONT};font-size:13px;line-height:1.4;'
                f'letter-spacing:0.06em;text-transform:uppercase;'
                f'color:{MUTED};">{escape(kicker)}</p>')
    return out
