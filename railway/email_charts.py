"""Small server-side chart PNGs for the subscriber email, in pure Python.

Owner decision 2026-10-15: the email carries one to three small charts as
real images, generated here with no imaging dependency (the lock holds no
Pillow, and a PNG is a zlib stream of rows, which the standard library writes).

WHAT A CHART IS, AND IS NOT.
  - It is drawn from figures the email already prints as text, so the picture
    adds shape and never a number. Its alt text repeats every figure.
  - Its background is TRANSPARENT and its marks are mid-tone colours that
    clear 3:1 (the WCAG non-text contrast floor) against both the light card
    and the dark card, so a client that inverts or darkens the page never
    leaves a white slab or an invisible bar. tests/test_email_charts.py checks
    both.
  - It carries no text: a glyph rasterised into a picture is unreadable to a
    screen reader and blurry on every density but one.
  - It travels INLINE (Content-ID), never as a remote URL in the email, so
    opening the message fetches nothing from any server. The public archive
    serves the same bytes from our own site.
"""
from __future__ import annotations

import re
import struct
import zlib

# Chart marks: mid tones, >= 3:1 on white AND on the dark card (#111a2e).
CHART_COLOURS = {
    "layoff": "#e5484d",
    "talent": "#3b82f6",
    "default": "#3b82f6",
}
BASELINE = "#9ca3af"

WIDTH = 1088          # drawn at 2x, displayed at 544px
HEIGHT = 240
MAX_CHARTS = 3


def _rgb(hex_colour: str):
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return (struct.pack(">I", len(data)) + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))


def encode_png(width: int, height: int, pixels) -> bytes:
    """RGBA rows (list of bytearrays, width*4 each) -> PNG bytes. Deterministic."""
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 9))
            + _chunk(b"IEND", b""))


def column_chart(values, colour: str, width: int = WIDTH,
                 height: int = HEIGHT) -> bytes:
    """Vertical columns, oldest left, newest right and at full strength."""
    values = [max(0.0, float(v)) for v in values]
    top = max(values) if values else 0.0
    rows = [bytearray(width * 4) for _ in range(height)]
    if not values or top <= 0:
        return encode_png(width, height, rows)
    r, g, b = _rgb(colour)
    br, bg_, bb = _rgb(BASELINE)
    n = len(values)
    pad_top, base_h = 8, 4
    usable = height - pad_top - base_h
    slot = width / n
    gap = max(4, int(slot * 0.22))
    for i, v in enumerate(values):
        x0 = int(i * slot + gap / 2)
        x1 = int((i + 1) * slot - gap / 2)
        h = int(round(usable * v / top)) if v > 0 else 0
        if v > 0:
            h = max(h, 3)
        alpha = 255 if i == n - 1 else 190
        segment = bytes((r, g, b, alpha)) * (x1 - x0)
        for y in range(height - base_h - h, height - base_h):
            rows[y][x0 * 4:x1 * 4] = segment
    for y in range(height - base_h, height):
        rows[y][:] = bytes((br, bg_, bb, 255)) * width
    return encode_png(width, height, rows)


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def figure_value(text: str):
    found = _NUM.search(text or "")
    if not found:
        return None
    try:
        return float(found.group(0).replace(",", ""))
    except ValueError:
        return None


def alt_text(title: str, items) -> str:
    """Every figure, in order, so the picture adds nothing a reader can miss."""
    listed = "; ".join(f"{label} {fig}" for label, fig in items)
    return f"{title}: {listed}." if listed else title


def colour_for(section: str) -> str:
    return CHART_COLOURS.get((section or "").strip().lower(),
                             CHART_COLOURS["default"])
