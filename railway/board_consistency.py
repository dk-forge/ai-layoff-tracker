"""Do the numbers ON THE PAGE match the API they were counted from? Is ingest fresh?

WHY THIS EXISTS (owner report 2026-10-17, seen on a phone). The tracker showed
0 in the at-a-glance board's Today / This week columns while /query returned
rows for the same windows. Every check in data_integrity read the API; none
read the PAGE, so a page painting 0 over live rows passed all of them.

Root cause (TECHLOG 2026-10-18): layoffs.js built the board windows and the
date presets from the BROWSER's calendar day while the server counts in New
York time, so from 18:00 New York (midnight in the Netherlands) the board asked
for tomorrow: Today 0, the week a day short, the Today preset an empty table.
Fixed in 2.20.270 (siteNow()). These checks are what would have caught it.

Three checks, each three-state (PASS / FAIL / UNKNOWN; could-not-check is never
a pass):

  board_tiles_match_query  stdlib. Fetches the page as a desktop AND as a phone
      browser, reads every "Verified layoffs" tile (each cell names its own
      window in data-from/data-to), and for each window asks /query and
      /aggregate live. FAIL if a tile is 0 while /query has rows, if a tile is
      off by more than a cache lag, if /aggregate's entries plus its excluded
      superset members do not equal /query's total, or if the inlined table's
      first page is empty while it reports rows.
  board_tiles_render       the same comparison on the RENDERED page, through
      headless Chrome (cdp.py) at 390px and 1280px, which is the only way to
      see what the browser's JavaScript repaints. No Chrome here: UNKNOWN.
  freshness_main()         daily, `python3 board_consistency.py --freshness`.
      Per source class (news, WARN, SEC) was there new ingest in the window?
      Alerts through ops_notify (one door), never opens a GitHub issue.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
PAGE_URL = "https://asktherecruiter.com/blog/ai-layoff-tracker/"

DESKTOP_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
PHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
AGENTS = (("desktop", DESKTOP_UA), ("phone", PHONE_UA))
RENDER_WIDTHS = (390, 1280)
# The browser zone each render runs in. The phone render runs FAR AHEAD of New
# York (UTC+14), because the 2026-10-17 defect only showed where the reader's
# calendar day differs from the site's; at UTC+14 it differs for 18 hours of
# every New York day, including this job's slot.
RENDER_TZ = {390: "Pacific/Kiritimati", 1280: "America/New_York"}

# The board counts verified entries on the filing basis (alt_signal_board_periods).
BOARD_PARAMS = {"stage": "verified", "date_basis": "notice"}


def _di():
    """data_integrity lazily: it imports this module at its bottom."""
    import data_integrity
    return data_integrity


def lag_tolerance(expected):
    """How far a tile may trail the live count and still be a cache lag.

    DERIVATION: readers get a page cached for up to 60s at the edge
    (shortcodes.php s-maxage=60) and this check reads the API seconds later. An
    ingest burst in that gap moves a window by a handful of entries, never by a
    large share of it. One entry, or 2% of the window, whichever is larger. A
    tile of 0 over live rows is never a lag and is checked separately.
    """
    return max(1, round(0.02 * max(0, expected)))


# --------------------------------------------------------------------------
# Reading the page
# --------------------------------------------------------------------------

_ROW = re.compile(r'<div class="alt-sb-row alt-sb-r-events"[^>]*>(.*?)</div>', re.S)
_CELL = re.compile(r'<a class="alt-sb-cell[^"]*"[^>]*?data-from="(\d{4}-\d\d-\d\d)"'
                   r'[^>]*?data-to="(\d{4}-\d\d-\d\d)"[^>]*>\s*<b>([\d,]+)</b>', re.S)


def page_tiles(html):
    """[(from, to, entries)] off the server-rendered Verified layoffs row."""
    m = _ROW.search(html or "")
    if not m:
        return []
    return [(f, t, int(n.replace(",", ""))) for f, t, n in _CELL.findall(m.group(1))]


def page_table(html):
    """(total, rows on the first page) of the inlined table, or None."""
    i = (html or "").find("window.ALT_BOOTSTRAP")
    if i == -1:
        return None
    try:
        boot, _ = json.JSONDecoder().raw_decode(html[html.index("{", i):])
        q = boot.get("query") or {}
        return int(q.get("total") or 0), len(q.get("data") or [])
    except (ValueError, TypeError, AttributeError):
        return None


def _fetch_page(ctx, name, ua):
    di = _di()
    if ctx._fetch is di._default_fetch:
        # The bare URL, as a reader requests it: a query string would skip the
        # page cache and test a page nobody is served.
        req = urllib.request.Request(PAGE_URL, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=ctx.timeout) as r:
            return r.read().decode("utf-8", "replace")
    raw = ctx.fetch(PAGE_URL + "#ua=" + name, ctx.timeout)
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw


def _api(ctx, path, params):
    q = dict(params)
    q["cb"] = ctx.cachebust
    return json.loads(ctx.fetch(BASE + path + "?" + urllib.parse.urlencode(q), ctx.timeout))


def live_window(ctx, frm, to):
    """{'query': n, 'aggregate': n, 'excluded': n} for one board window."""
    p = dict(BOARD_PARAMS, **{"from": frm, "to": to})
    q = _api(ctx, "query", dict(p, per_page=1))
    a = _api(ctx, "aggregate", p)
    return {"query": int(q.get("total") or 0),
            "aggregate": int(((a.get("totals") or {}).get("entries")) or 0),
            "excluded": int(((a.get("excluded") or {}).get("entries")) or 0)}


SITE_TZ = "America/New_York"     # alt_site_timezone() in api.php


def now_utc():
    return datetime.now(timezone.utc)


def site_today_candidates(now=None, slack=timedelta(minutes=5)):
    """The site's calendar day (New York), or both days within `slack` of its
    midnight, so a page cached across midnight is not called wrong."""
    from zoneinfo import ZoneInfo
    now = now or now_utc()
    tz = ZoneInfo(SITE_TZ)
    return {(now + d).astimezone(tz).date().isoformat() for d in (-slack, timedelta(0), slack)}


def today_problem(where, tiles, now=None):
    """Pure. The board's first column must be the SITE's today.

    This is the check that catches the 2026-10-17 defect itself: the browser
    asked for its own tomorrow, which /query answers truthfully (0, or WARN
    notices filed ahead), so tile-vs-own-window agreement alone passes it."""
    if not tiles:
        return None
    frm, to, _ = tiles[0]
    days = site_today_candidates(now)
    if frm != to or frm not in days:
        return (f"{where}: the Today column counts {frm}..{to}, but the site's today "
                f"is {' or '.join(sorted(days))} ({SITE_TZ})")
    return None


def tile_problems(where, tiles, live, now=None):
    """Pure. Sentences for each tile that disagrees with its live window."""
    bad = []
    tp = today_problem(where, tiles, now)
    if tp:
        bad.append(tp)
    for frm, to, shown in tiles:
        lv = live[(frm, to)]
        expected = lv["query"] - lv["excluded"]
        span = frm if frm == to else f"{frm}..{to}"
        if lv["query"] > 0 and shown == 0:
            bad.append(f"{where}: tile {span} shows 0 but /query has {lv['query']} rows")
        elif abs(shown - expected) > lag_tolerance(expected):
            bad.append(f"{where}: tile {span} shows {shown:,}, /query counts {expected:,} "
                       f"({lv['query']:,} less {lv['excluded']:,} folded supersets)")
    return bad


def window_problems(live):
    """Pure. /aggregate and /query must describe one population."""
    bad = []
    for (frm, to), lv in sorted(live.items()):
        if lv["aggregate"] + lv["excluded"] != lv["query"]:
            bad.append(f"window {frm}..{to}: /aggregate {lv['aggregate']:,} + excluded "
                       f"{lv['excluded']:,} != /query {lv['query']:,}")
    return bad


def _transport_or_answer(inv, exc, what):
    di = _di()
    if isinstance(exc, urllib.error.HTTPError):
        why = ("site is in its deploy maintenance window (HTTP 503)" if exc.code == 503
               else f"{what} returned HTTP {exc.code}")
    else:
        why = f"could not read {what} ({exc})"
    return di.Result(inv, di.UNKNOWN, detail=why + ": not checked, NOT passing", error=exc)


class BoardTilesMatchQuery:
    key = "board_tiles_match_query"
    label = "At-a-glance tiles and the table match /query (desktop and phone)"
    reads_live_data = True

    def __init__(self, render=None):
        self.render = render     # unused; symmetric constructor for tests

    def run(self, ctx):
        di = _di()
        pages = {}
        for name, ua in AGENTS:
            try:
                pages[name] = _fetch_page(ctx, name, ua)
            except Exception as exc:                       # noqa: BLE001
                return _transport_or_answer(self, exc, "the tracker page")
        tiles = {n: page_tiles(h) for n, h in pages.items()}
        if not all(tiles.values()):
            missing = [n for n, t in tiles.items() if not t]
            return di.Result(self, di.UNKNOWN,
                             detail=f"no at-a-glance board in the {'/'.join(missing)} page: "
                                    "not checked, NOT passing")
        windows = sorted({(f, t) for ts in tiles.values() for f, t, _ in ts})
        try:
            live = {w: live_window(ctx, *w) for w in windows}
        except Exception as exc:                           # noqa: BLE001
            return _transport_or_answer(self, exc, "the live API")
        bad = window_problems(live)
        for name in pages:
            bad += tile_problems(name, tiles[name], live)
            tbl = page_table(pages[name])
            if tbl is not None and tbl[0] > 0 and tbl[1] == 0:
                bad.append(f"{name}: the table's first page is empty but reports {tbl[0]:,} rows")
        if bad:
            return di.Result(self, di.FAIL, observed=len(bad), detail="; ".join(bad[:6]))
        shown = ", ".join(f"{f}..{t}={n:,}" for f, t, n in tiles["phone"])
        return di.Result(self, di.PASS, observed=0,
                         detail=f"{len(windows)} windows agree on desktop and phone ({shown})")


# --------------------------------------------------------------------------
# The rendered page (headless Chrome)
# --------------------------------------------------------------------------

class RenderUnavailable(Exception):
    """No browser in this environment, so the rendered page was not seen."""


_RENDER_JS = """(function () {
  var tiles = Array.from(document.querySelectorAll('.alt-sb-r-events .alt-sb-cell[data-from]'))
    .map(function (a) { return [a.dataset.from, a.dataset.to, parseInt(a.innerText.replace(/[^0-9]/g, '') || '0', 10)]; });
  var cards = document.getElementById('alt-cards');
  var count = (document.getElementById('alt-table-count') || {}).innerText || '';
  var m = count.match(/of ([0-9,]+)/);
  return { tiles: tiles, cards: cards ? cards.children.length : -1,
           table_total: m ? parseInt(m[1].replace(/,/g, ''), 10) : -1 };
})()"""


def default_render(width):
    """What the browser shows at `width`, after the page's own JavaScript ran,
    with Chrome's clock in RENDER_TZ[width] (Chrome reads TZ from its env)."""
    import os
    try:
        import cdp
    except Exception as exc:                               # noqa: BLE001
        raise RenderUnavailable(f"cdp unavailable ({exc})")
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = RENDER_TZ.get(width, SITE_TZ)
    try:
        with cdp.Browser(width=width, height=900) as b:
            b.navigate(PAGE_URL, settle=6)
            out = b.eval_js(_RENDER_JS)
    except cdp.CDPUnavailable as exc:
        raise RenderUnavailable(str(exc))
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
    out["tiles"] = [tuple(t) for t in out.get("tiles") or []]
    return out


class BoardTilesRender:
    key = "board_tiles_render"
    label = "Rendered board and table at 390px and 1280px match /query"
    reads_live_data = True

    def __init__(self, render=None):
        self.render = render or default_render

    def run(self, ctx):
        di = _di()
        if self.render is default_render and ctx._fetch is not di._default_fetch:
            try:
                ctx.fetch(PAGE_URL + "#ua=render", ctx.timeout)
            except Exception as exc:                       # noqa: BLE001
                return _transport_or_answer(self, exc, "the tracker page")
            # Chrome would load the LIVE site while this run's numbers come
            # from an injected transport (a test or a replay): the two are not
            # one reading, and the offline suite must not open the network.
            return di.Result(self, di.UNKNOWN, pending=True,
                             detail="this run reads an injected transport, so the live "
                                    "page was not rendered: NOT passing")
        shots = {}
        for w in RENDER_WIDTHS:
            try:
                shots[w] = self.render(w)
            except RenderUnavailable as exc:
                return di.Result(self, di.UNKNOWN, pending=True,
                                 detail=f"no headless browser here ({exc}): the rendered "
                                        "page was not seen, NOT passing")
            except Exception as exc:                       # noqa: BLE001
                return di.Result(self, di.UNKNOWN, error=exc,
                                 detail=f"the {w}px render failed ({exc}): NOT passing")
        windows = sorted({(f, t) for s in shots.values() for f, t, _ in s["tiles"]})
        if not windows:
            return di.Result(self, di.FAIL, observed=1,
                             detail="the rendered page painted no at-a-glance tiles at "
                                    + " or ".join(f"{w}px" for w in RENDER_WIDTHS))
        try:
            live = {win: live_window(ctx, *win) for win in windows}
        except Exception as exc:                           # noqa: BLE001
            return _transport_or_answer(self, exc, "the live API")
        bad = []
        for w, s in shots.items():
            bad += tile_problems(f"{w}px", s["tiles"], live)
            if s.get("cards", 0) <= 0 and s.get("table_total", 0) != 0:
                bad.append(f"{w}px: the table rendered no rows")
        if bad:
            return di.Result(self, di.FAIL, observed=len(bad), detail="; ".join(bad[:6]))
        return di.Result(self, di.PASS, observed=0,
                         detail=f"{len(windows)} rendered windows agree at "
                                + " and ".join(f"{w}px" for w in RENDER_WIDTHS))


# --------------------------------------------------------------------------
# Daily ingest freshness, per source class
# --------------------------------------------------------------------------

# DERIVATION: the daily ingest runs at 22:00 UTC and takes up to ~2h, so a 24h
# window read at an arbitrary hour can fall just before a run finishes. 26h
# still catches one missed day; two days would be the ingest_silence alarm.
FRESH_WINDOW = timedelta(hours=26)

NEWS_SOURCES = frozenset({"gdelt", "google_news", "national_feeds", "regional_feeds",
                          "local_news", "press_releases", "supplemental_news"})
SEC_SOURCES = frozenset({"edgar"})


def source_class(source):
    s = str(source or "")
    if s.endswith("_historical"):
        return None             # back-sweeps re-read the past; they are not new ingest
    if s in NEWS_SOURCES:
        return "news"
    if s.startswith("warn_"):
        return "WARN"
    if s in SEC_SOURCES:
        return "SEC"
    return None


def _when(r):
    try:
        at = datetime.fromisoformat(str(r.get("attempted_at")).replace("Z", "+00:00"))
    except Exception:                                      # noqa: BLE001
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def freshness_verdict(runs, now=None, window=FRESH_WINDOW):
    """[(class, state, sentence)] for news, WARN and SEC.

    news and WARN must have WRITTEN rows (a completed run with entries > 0):
    both publish every day. SEC needs a completed run only: 8-K item 2.05
    filings average under one a day, so a run that found none is a quiet day,
    not a stale pipeline. A `running` note is never a completed run.
    """
    di = _di()
    now = now or datetime.now(timezone.utc)
    since = now - window
    seen = {"news": [0, 0], "WARN": [0, 0], "SEC": [0, 0]}   # runs, entries
    for r in runs or ():
        if not isinstance(r, dict):
            continue
        k = source_class(r.get("source"))
        at = _when(r)
        status = str(r.get("status") or "").lower()
        if not k or at is None or at < since or status == "running" \
                or status.startswith(("err", "fail")):
            continue
        seen[k][0] += 1
        try:
            seen[k][1] += int(r.get("entries") or 0)
        except (TypeError, ValueError):
            pass
    hours = int(window.total_seconds() // 3600)
    out = []
    for k in ("news", "WARN", "SEC"):
        n_runs, n_rows = seen[k]
        need_rows = k != "SEC"
        if n_runs == 0:
            out.append((k, di.FAIL, f"{k}: no completed collector run in {hours}h"))
        elif need_rows and n_rows == 0:
            out.append((k, di.FAIL, f"{k}: {n_runs} run(s) in {hours}h wrote 0 rows"))
        else:
            out.append((k, di.PASS, f"{k}: {n_runs} run(s), {n_rows} rows in {hours}h"))
    return out


def _fetch_runs():
    url = f"{BASE}source-runs?days=2&per_page=200&cb={uuid.uuid4().hex[:12]}"
    req = urllib.request.Request(url, headers={"User-Agent": DESKTOP_UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


class IngestFreshness:
    key = "ingest_fresh_per_class"
    label = "News, WARN and SEC each ingested in the last day"
    reads_live_data = True

    def run(self, ctx):
        di = _di()
        try:
            payload = _api(ctx, "source-runs", {"days": 2, "per_page": 200})
        except Exception as exc:                           # noqa: BLE001
            return _transport_or_answer(self, exc, "/source-runs")
        runs = payload.get("runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list):
            return di.Result(self, di.UNKNOWN,
                             detail="/source-runs answered without a runs list: "
                                    "not checked, NOT passing")
        v = freshness_verdict(runs)
        bad = [s for _, st, s in v if st == di.FAIL]
        if bad:
            return di.Result(self, di.FAIL, observed=len(bad), detail="; ".join(bad))
        return di.Result(self, di.PASS, observed=0, detail="; ".join(s for _, _, s in v))


def freshness_main(fetch=_fetch_runs, now=None, notify=None):
    """0 fresh, 1 stale (alert sent), 3 unreadable. Never opens an issue."""
    di = _di()
    try:
        payload = fetch() or {}
    except Exception as exc:                               # noqa: BLE001
        print(f"INGEST FRESHNESS UNKNOWN: could not read /source-runs ({exc})")
        return 3
    runs = payload.get("runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        print("INGEST FRESHNESS UNKNOWN: /source-runs answered without a runs list")
        return 3
    v = freshness_verdict(runs, now=now)
    for _, _, line in v:
        print(line)
    stale = [k for k, st, _ in v if st == di.FAIL]
    if not stale:
        return 0
    if notify is None:
        import ops_notify
        notify = ops_notify.notify
    body = "\n".join(line for _, _, line in v) + (
        "\n\nRead from the public /source-runs log. Runbook: docs/RUNBOOK.md, "
        "\"a data source broke\". Raised by .github/workflows/tracker-zeros-watch.yml.")
    notify(f"Ingest stale: no new {', '.join(stale)} rows in the last day", body,
           dedupe_key="ingest-freshness:" + ",".join(stale),
           what="ingest freshness alert")
    return 1


def render_main():
    """Run the two page checks once, print them, alert on FAIL. 0/1/3."""
    di = _di()
    report = di.check_all(invariants=(BoardTilesMatchQuery(), BoardTilesRender()))
    states = [r.state for r in report.results]
    for r in report.results:
        print(f"{r.state.upper():8} {r.inv.key}: {r.detail}")
    if di.FAIL in states:
        import ops_notify
        ops_notify.notify(
            "Tracker page shows numbers /query does not",
            "\n".join(f"{r.inv.key}: {r.detail}" for r in report.results
                      if r.state == di.FAIL)
            + "\n\nRaised by .github/workflows/tracker-zeros-watch.yml.",
            dedupe_key="board-tiles-vs-query", what="tracker page consistency alert")
        return 1
    return 3 if di.UNKNOWN in states else 0


if __name__ == "__main__":
    if "--freshness" in sys.argv:
        sys.exit(freshness_main())
    sys.exit(render_main())
