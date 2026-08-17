#!/usr/bin/env python3
"""MEASURE THE SIGNUP'S PHONE FOLD, AND RECORD WHAT THE COPY WAS WHEN YOU DID.

WHY THIS EXISTS. The signup block in wordpress-plugin/ai-layoff-tracker/
includes/subscribe.php has to fit one 812px phone screen from its heading to
its Subscribe button, because both trackers carry a hero button that jumps to
#alt-digest and a jump that lands on a form the reader still has to hunt for is
the defect wearing the fix's clothes. Two rendered tests hold that bar:

    tests/test_digest_route_is_findable.py    the tracker page, after the jump
    tests/test_signup_reaches_landing_pages.py   a blog post, scrolled to the top

Both need headless Chrome. Both are slow. Neither is the test anyone runs after
changing a sentence, and that is the whole problem: the phone fold has broken
FOUR times in one week and every single time the sequence was identical. Someone
edited copy in subscribe.php, did not re-measure, pushed, and CI reported a
pixel arithmetic failure twenty minutes later on a build that had already
deployed. The 2026-08-16 one was a rewrite of the intro that added a paragraph
and put the email field 862.4px down an 812px screen.

WHAT SHORTENS THE LOOP. Not another pixel bar - the pixel bars work, they caught
it every time. What was missing is a cheap thing that notices the copy MOVED and
says so before the expensive thing has to. So:

  * this script measures the fold in Chrome and prints the per-element
    breakdown, which is the number you actually want when you are deciding what
    to cut;
  * `--record` writes railway/signup_fold_stamp.json: the measurement, plus a
    hash of every reader-facing string the signup renders ABOVE the Subscribe
    button;
  * tests/test_signup_fold_stamp.py is stdlib-only, needs no browser, runs in
    milliseconds, and fails the moment that copy hash stops matching the stamp.
    Its failure message is one command: this one.

So the loop becomes: edit copy -> the cheapest test in the suite goes red
locally -> run this -> read the pixels -> record. The Chrome tests stay exactly
as they are and stay the authority; this only makes it impossible to reach them
by surprise.

HEADROOM, NOT FIT. The recorded figures have to clear the fold by
REQUIRED_HEADROOM_PX, not merely fit it. A local Mac render is not a CI render:
measured on 2026-08-16 the same fixtures came out 34px (tracker) and 49px (blog)
SHORTER here than on the Linux runner, purely on font metrics. "It fits by
2.3px" is a sentence already in subscribe.php's own comments, about a build that
then broke. The margin is what stops this script certifying that again.

Usage:
    python3 railway/signup_fold.py              # measure and print
    python3 railway/signup_fold.py --record     # ... and update the stamp
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date, timezone, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBSCRIBE = ROOT / "wordpress-plugin/ai-layoff-tracker/includes/subscribe.php"
STAMP = ROOT / "railway/signup_fold_stamp.json"

# The gap between a render here and a render on the Linux CI runner, plus room
# for a word. Measured 2026-08-16, same commit, same fixtures: tracker 828.3
# local against 862.4 on the runner, blog 806.8 against 855.7. The larger of
# those is 49px; 80 is that plus a line of 14px copy and a little air.
REQUIRED_HEADROOM_PX = 80.0


# --------------------------------------------------------------------------
# The copy, extracted once, here, so the stamp and the test cannot disagree
# about what "the copy above the button" means.
# --------------------------------------------------------------------------

def fold_copy():
    """Every reader-facing string the signup renders above the Subscribe button.

    TEXT ONLY, tags and PHP stripped. A class rename or a re-indent must not
    invalidate a measurement that is still true; a changed sentence must.

    The slice runs from the <section> open tag to the close of the <form>,
    which is exactly the region the fold budget covers, plus the per-surface
    lead sentences from alt_digest_context_lead(): those render INSIDE the
    intro paragraph, and the longest of them is what the blog fixture measures.
    The tracking disclosure and the privacy note are deliberately outside it -
    they sit below the button and cost the budget nothing, which is why they
    were moved there.
    """
    src = SUBSCRIBE.read_text(encoding="utf-8")
    start = src.find('<section class="alt-digest"')
    end = src.find("</form>", start)
    if start < 0 or end < 0:
        raise SystemExit(
            "cannot find the signup's <section> ... </form> in %s, so the fold "
            "copy cannot be read. The markup changed shape: fix this extractor "
            "rather than deleting the guard." % SUBSCRIBE.name)
    region = src[start:end]

    m = re.search(r"function alt_digest_context_lead\(.*?\n\}", src, re.S)
    leads = re.findall(r"=>\s*'([^']*)'", m.group(0)) if m else []

    region = re.sub(r"<\?php.*?\?>", " ", region, flags=re.S)   # PHP out
    region = re.sub(r"<[^>]+>", " ", region)                    # tags out
    region = region.replace("&nbsp;", " ")
    text = " ".join(region.split())
    return text + " || " + " | ".join(sorted(x for x in leads if x))


def copy_digest():
    text = fold_copy()
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), len(text)


# --------------------------------------------------------------------------
# The measurement
# --------------------------------------------------------------------------

BREAKDOWN = r"""
(function () {
  var sec = document.querySelector('#alt-digest');
  if (!sec) return JSON.stringify({missing: true});
  var sr = sec.getBoundingClientRect();
  function row(label, sel) {
    var el = sel === null ? sec : sec.querySelector(sel);
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return {label: label, top: +(r.top - sr.top).toFixed(1),
            h: +r.height.toFixed(1), bottom: +(r.bottom - sr.top).toFixed(1)};
  }
  var parts = [['section', null], ['heading', 'h2'],
               ['intro', '.alt-digest-intro'],
               ['lists', '.alt-digest-lists'], ['frequency', '.alt-digest-freq'],
               ['email row', '.alt-digest-row'],
               ['field', 'input[type="email"]'],
               ['submit', 'button[type="submit"]'],
               ['tracking note', '.alt-digest-tracking'],
               ['privacy', '.alt-digest-privacy']];
  var out = [];
  for (var i = 0; i < parts.length; i++) {
    var r = row(parts[i][0], parts[i][1]);
    if (r) out.push(r);
  }
  return JSON.stringify({rows: out, secTop: +(sr.top + scrollY).toFixed(1)});
})()
"""


def _harness():
    sys.path.insert(0, str(ROOT / "railway"))
    sys.path.insert(0, str(ROOT / "railway/tests"))
    from cdp import Browser, find_chrome            # noqa: E402
    if not find_chrome():
        raise SystemExit(
            "no Chrome/Chromium on this machine, so the fold could not be "
            "measured. That is UNKNOWN, not a pass: do not record a stamp "
            "from a run that measured nothing.")
    return Browser


def measure_tracker(Browser, width, height):
    """The tracker page, after a reader follows the hero button's #alt-digest."""
    import test_digest_route_is_findable as R
    fx = R.FollowingTheDigestRouteLandsSomewhereUsable(
        "test_the_jump_lands_the_whole_signup_on_screen_on_a_phone")
    fx._cache = {}
    fx._markup = R.markup_with_the_digest()
    with Browser(width=width, height=height) as page:
        fx._page(page, fx._html())
        page.eval_js("(function(){location.hash='';"
                     "location.hash='alt-digest';return true;})()")
        land = json.loads(page.eval_js(R.LANDING_PROBE))
        data = json.loads(page.eval_js(BREAKDOWN))
    # After the jump the block is measured against the viewport, anchor offset
    # already paid, which is what a reader who took the route actually gets.
    reach = max(land[p]["bottom"] for p in ("heading", "field", "submit"))
    return reach, data


def measure_blog(Browser, width, height):
    """A blog post, the signup scrolled to its own top: the best case a reader
    can reach, which is how test_signup_reaches_landing_pages measures it."""
    import test_signup_reaches_landing_pages as S
    html = S.blog_page_with_signup(True)
    with Browser(width=width, height=height) as page:
        page.call("Page.navigate", {"url": "about:blank"})
        page.eval_js("(function(){document.open();document.write(%s);"
                     "document.close();return true;})()" % json.dumps(html))
        probe = json.loads(page.eval_js(S.PROBE))
        data = json.loads(page.eval_js(BREAKDOWN))
    top = probe["section"]["top"]
    reach = max(probe[p]["top"] - top + probe[p]["h"]
                for p in ("heading", "field", "submit"))
    return reach, data


SURFACES = (
    ("tracker", 375, 812, measure_tracker),
    ("tracker", 414, 896, measure_tracker),
    ("blog", 375, 812, measure_blog),
    ("blog", 414, 896, measure_blog),
)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", action="store_true",
                    help="write railway/signup_fold_stamp.json from this run")
    args = ap.parse_args(argv)

    Browser = _harness()
    figures = {}
    ok = True
    for surface, width, height, fn in SURFACES:
        reach, data = fn(Browser, width, height)
        key = "%s@%dx%d" % (surface, width, height)
        headroom = height - reach
        figures[key] = {"reach_px": round(reach, 1), "screen_px": height,
                        "headroom_px": round(headroom, 1),
                        "parts": {r["label"]: r["h"] for r in data["rows"]}}
        verdict = "OK"
        if reach > height:
            verdict, ok = "OVER THE FOLD by %.1fpx" % (reach - height), False
        elif headroom < REQUIRED_HEADROOM_PX:
            verdict, ok = ("only %.1fpx of headroom, under the %.0fpx this "
                           "needs to survive a CI render"
                           % (headroom, REQUIRED_HEADROOM_PX)), False
        print("%-18s reaches %7.1f of %d  (%.1fpx spare)  %s"
              % (key, reach, height, headroom, verdict))
        for r in data["rows"]:
            print("      %-14s %7.1f tall, ends %7.1f from the block's top"
                  % (r["label"], r["h"], r["bottom"]))
        print()

    sha, chars = copy_digest()
    print("fold copy: %d chars, sha256 %s" % (chars, sha))

    if not args.record:
        print("\n(not recorded. Re-run with --record once the figures above "
              "are the ones you mean to publish.)")
        return 0 if ok else 2

    if not ok:
        print("\nREFUSING TO RECORD: a surface above is over the fold or "
              "inside the %.0fpx CI margin. Fix the block, then record."
              % REQUIRED_HEADROOM_PX)
        return 2

    STAMP.write_text(json.dumps({
        "_comment": ("What the signup's copy was when the phone fold was last "
                     "measured, and what it measured. Written by "
                     "railway/signup_fold.py --record; read by "
                     "railway/tests/test_signup_fold_stamp.py. Never edit by "
                     "hand: a stamp nobody measured is worse than no stamp."),
        "copy_sha256": sha,
        "copy_chars": chars,
        "measured_on": date.today().isoformat(),
        "measured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "measured_on_platform": sys.platform,
        "required_headroom_px": REQUIRED_HEADROOM_PX,
        "figures": figures,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("\nrecorded -> %s" % STAMP.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
