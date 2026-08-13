#!/usr/bin/env python3
"""Minimal stdlib PDF text extractor, with coordinates.

WHY THIS EXISTS
---------------
`docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md` enumerates
California's reference frame from the EDD's ARCHIVED fiscal-year WARN report,
which is a PDF. That is the whole point of choosing it: our own CA collector
reads `warn_report1.xlsx`, a different, rolling file, so the reference frame and
the collector's input are two separate documents published by the same agency.

Reading it needed a PDF parser, and this repo's dependencies are hash-pinned
(`railway/requirements.lock`, installed with `--require-hashes`). A reference set
is not a good enough reason to widen the install surface of a runner that holds
`WP_API_KEY` and `OPENROUTER_API_KEY`, and `pdfplumber` is in the FULL lock only
— which the recall jobs deliberately do not install. So this is stdlib: `zlib`
for FlateDecode, `re` for the content stream.

It is NOT a general PDF library. It handles what a generated tabular report
uses: FlateDecode streams, /ObjStm object streams, and the Tj/TJ/Td/TD/Tm/T*/'
text operators. It returns (x, y, text) per drawn string so a table can be
rebuilt by COLUMN POSITION rather than by reading order — a table read in
reading order silently interleaves columns when one cell wraps.

Known limit, and it is disclosed in the manifest rather than hidden: a PDF
column truncates long text at its own width, so a long employer name arrives
cut. That is harmless for this measurement because both the alias rule and the
collapse key read LEADING tokens, but it would not be harmless for anything that
needs the full string.
"""
import re
import zlib

__all__ = ["PDF", "page_items"]


class PDF:
    def __init__(self, data):
        self.data = data
        self.objs = {}
        self._scan()

    def _scan(self):
        for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b", self.data):
            body = self.data[m.end():]
            end = body.find(b"endobj")
            self.objs[int(m.group(1))] = body[:end if end >= 0 else len(body)]
        for body in list(self.objs.values()):
            if b"/ObjStm" in body[:400]:
                try:
                    self._expand_objstm(body)
                except Exception:                              # noqa: BLE001
                    pass                                       # one bad ObjStm is not fatal

    def _expand_objstm(self, body):
        raw = self._stream(body)
        n = int(re.search(rb"/N\s+(\d+)", body).group(1))
        first = int(re.search(rb"/First\s+(\d+)", body).group(1))
        header = raw[:first].split()
        for i in range(n):
            num = int(header[2 * i])
            off = int(header[2 * i + 1])
            nxt = int(header[2 * i + 3]) + first if i + 1 < n else len(raw)
            self.objs.setdefault(num, raw[first + off:nxt])

    @staticmethod
    def _inflate(raw):
        try:
            return zlib.decompress(raw)
        except zlib.error:
            try:                                               # truncated tail
                return zlib.decompressobj().decompress(raw)
            except zlib.error:
                return b""

    def _stream(self, body):
        m = re.search(rb"stream\r?\n", body)
        if not m:
            return b""
        raw = body[m.end():]
        e = raw.rfind(b"endstream")
        return self._inflate(raw[:e] if e >= 0 else raw)

    def pages(self):
        """Decoded content stream per /Type /Page, in object order."""
        out = []
        for _, body in sorted(self.objs.items()):
            if not re.search(rb"/Type\s*/Page\b", body):
                continue
            m = re.search(rb"/Contents\s+(\d+)\s+\d+\s+R", body)
            refs = [int(m.group(1))] if m else []
            if not refs:
                m = re.search(rb"/Contents\s*\[(.*?)\]", body, re.S)
                if m:
                    refs = [int(x) for x in re.findall(rb"(\d+)\s+\d+\s+R", m.group(1))]
            content = b"".join(self._stream(self.objs.get(r, b"")) for r in refs)
            if content:
                out.append(content)
        return out


_TOKEN = re.compile(rb"""
      \((?:\\.|[^\\()])*\)
    | <[0-9A-Fa-f\s]*>
    | \[|\]
    | [-+]?[0-9]*\.?[0-9]+
    | /[^\s/\[\]()<>]+
    | [A-Za-z'"*]+
""", re.X | re.S)

_ESC = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
        b"(": b"(", b")": b")", b"\\": b"\\"}


def _literal(tok):
    s, out, i = tok[1:-1], bytearray(), 0
    while i < len(s):
        c = s[i:i + 1]
        if c == b"\\" and i + 1 < len(s):
            nxt = s[i + 1:i + 2]
            if nxt in _ESC:
                out += _ESC[nxt]
                i += 2
                continue
            if nxt.isdigit():
                j, oct_ = i + 1, b""
                while j < len(s) and len(oct_) < 3 and s[j:j + 1].isdigit():
                    oct_ += s[j:j + 1]
                    j += 1
                out.append(int(oct_, 8) & 0xFF)
                i = j
                continue
            if nxt in (b"\n", b"\r"):
                i += 2
                continue
            out += nxt
            i += 2
            continue
        out += c
        i += 1
    return bytes(out).decode("latin-1")


def _hexstr(tok):
    h = re.sub(rb"[^0-9A-Fa-f]", b"", tok)
    if len(h) % 2:
        h += b"0"
    return bytes.fromhex(h.decode()).decode("latin-1")


def page_items(content):
    """[(x, y, text)] for one page's content stream, in operator order."""
    items, stack = [], []
    tm = [1, 0, 0, 1, 0, 0]
    tlm, leading, cur = list(tm), 0.0, None
    for m in _TOKEN.finditer(content):
        t = m.group(0)
        if t[:1] == b"(":
            stack.append(("s", _literal(t)))
            continue
        if t[:1] == b"<" and t[-1:] == b">":
            stack.append(("s", _hexstr(t)))
            continue
        if t in (b"[", b"]"):
            continue
        if t[:1] == b"/":
            stack.append(("n", t))
            continue
        try:
            stack.append(("f", float(t)))
            continue
        except ValueError:
            pass
        op = t
        nums = [v for k, v in stack if k == "f"]
        strs = [v for k, v in stack if k == "s"]
        if op == b"BT":
            tm, tlm, cur = [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0], None
        elif op == b"Tm" and len(nums) >= 6:
            tm = nums[-6:]
            tlm, cur = list(tm), None
        elif op in (b"Td", b"TD") and len(nums) >= 2:
            if op == b"TD":
                leading = -nums[-1]
            tlm = [tlm[0], tlm[1], tlm[2], tlm[3],
                   tlm[4] + nums[-2] * tlm[0] + nums[-1] * tlm[2],
                   tlm[5] + nums[-2] * tlm[1] + nums[-1] * tlm[3]]
            tm, cur = list(tlm), None
        elif op == b"TL" and nums:
            leading = nums[-1]
        elif op in (b"T*", b"'", b'"'):
            tlm = [tlm[0], tlm[1], tlm[2], tlm[3],
                   tlm[4] - leading * tlm[2], tlm[5] - leading * tlm[3]]
            tm, cur = list(tlm), None
        if op in (b"Tj", b"TJ", b"'", b'"') and strs:
            if cur is None:
                cur = (round(tm[4], 1), round(tm[5], 1), [])
                items.append(cur)
            cur[2].append("".join(strs))
        stack = []
    return [(x, y, "".join(p)) for x, y, p in items if "".join(p).strip()]
