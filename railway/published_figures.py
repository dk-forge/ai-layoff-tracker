"""DOUBLE VERIFICATION for every number a reader or a journalist can quote.

WHY THIS EXISTS
---------------
Four wrong numbers were published on one day, and every existing check passed on
all four. That is the finding. The checks were not weak, they were asking the
wrong question. They asked "did the code that renders this number run without
throwing?" — and it did. A doughnut slice that returns fourteen times what it
displays runs perfectly. A hero figure with the wrong label renders perfectly. A
retired collector published as live serialises perfectly.

So the rule here is different, and it is the whole module in one sentence:

    A NUMBER IS PUBLISHED ONLY IF IT CAN BE INDEPENDENTLY RECOMPUTED AND THE TWO
    AGREE.

Not "it rendered". A second, separately-derived value must match it. The two
derivations must come from different code paths, or the check is measuring one
path against itself and will agree with itself while being wrong — which is
exactly what the site did.

The stakes are why this is worth the round trips. Journalists quote these
figures. A wrong number is not a bug that gets fixed in the next deploy; it is a
citation in someone else's article that never gets corrected, and it costs the
thing the tracker is actually built on, which is being believed.

THE STAMPED QUERY
-----------------
Every figure in FIGURES carries the query that produces it. That is not
bookkeeping, it is the point. The failure mode of a naive checker is that it
RE-DERIVES the query from an assumption about what the figure means, and then
agrees with itself: it computes what it thinks the hero should be, gets what it
computed, and reports green while the page shows something else. Storing the
query WITH the number means the check reads the same parameters the page reads,
and any disagreement is a real disagreement.

THE FOUR ASSERTIONS
-------------------
Each one is here because it catches a specific defect that shipped.

  AGREEMENT        the figure rendered into the page equals what the API returns
                   for that figure's own stamped query. Two paths: the PHP
                   bootstrap that server-renders the page, and the REST endpoint
                   the browser calls. They are different code. They must agree.

  RECONCILIATION   the parts sum to the whole, or the card itself states why not.
                   A reader must be able to add up what they can see and land on
                   the published number. Catches a chart summing far above its own
                   headline, and a scoped chart reconciled against a wider total.

  DRILL_DOWN       tapping a slice, a bar or a tab returns the count it displays.
                   Catches a slice that displays one number and filters to
                   another, which is the defect a reader finds FOR you, in public.

  BASIS            two figures sharing a label share a basis, and a label names
                   its unit and its period and its geography. A correct number
                   with an unstated basis is still read as a contradiction of
                   whatever the reader is comparing it against, and costs the
                   same credibility as a wrong one.

Two more were added after the first pass, both from real defects:

  CROSS_SURFACE    a figure that appears on more than one page is the same figure
                   on both. A journalist reading the home page and the press page
                   and finding two different headline totals is the specific
                   failure that ends the tracker's usefulness as a source.

  COMPARISON       where a surface states a relationship between our figure and
                   an external estimate, the two sides of the comparison share a
                   basis, and the explanation of the difference is actually
                   VISIBLE rather than sealed inside a collapsed disclosure.

PASS / FAIL / UNKNOWN ARE THREE STATES
--------------------------------------
This is the single most important rule in the project and it is why several
mechanisms reported health while doing nothing. A check that cannot reach a
surface reports UNKNOWN. UNKNOWN is never folded into PASS, never counted as a
pass, and never lets a run exit zero. If this module cannot answer a question it
says so in those words: "not checked, NOT passing".

Nothing here is truncated silently either. When a check bounds how many figures
it examines, it names what it skipped in its own detail string.

HOW IT RUNS
-----------
It does not run itself. It is imported by railway/data_integrity.py, which is
the single definition of live invariants for this repo, and therefore it reaches
ops_status.py, the test suite and the weekly digest through that one door. There
is deliberately no second entry point, no second registry and no second notion
of what "failing" means.
"""
import json
import re
import urllib.error
import urllib.parse

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
SITE = "https://asktherecruiter.com/blog/"

HOME_URL = SITE + "ai-layoff-tracker/"
PRESS_URL = SITE + "ai-layoff-tracker/press/"


def _di():
    """data_integrity lazily, because it imports this module at the bottom.

    The primitives (Result, the three states, _out, _roll_up) live there and stay
    there. Duplicating them here would be a second definition of what "failing"
    means, which is the thing the brief for this module explicitly forbids."""
    import data_integrity
    return data_integrity


# ---------------------------------------------------------------------------
# UNITS: what a number counts. Mixing these is a defect, not a nuance.
# ---------------------------------------------------------------------------
JOBS = "jobs"
RECORDS = "records"          # one layoff EVENT, not one job
COMPANIES = "companies"
PLACES = "places"            # countries / states / industries: distinct counts
PERCENT = "percent"


class Figure:
    """One number a reader can see, and everything needed to re-derive it.

    `params` is the STAMPED query — the parameters the page itself sends for this
    figure. `field` turns an /aggregate `totals` object into the number. The two
    together are the second derivation; the first is whatever the page rendered.
    """

    __slots__ = ("key", "surface", "dom_id", "label", "unit", "period",
                 "geography", "params", "field", "note")

    def __init__(self, key, surface, dom_id, label, unit, period, geography,
                 params, field, note=""):
        self.key = key
        self.surface = surface
        self.dom_id = dom_id
        self.label = label
        self.unit = unit
        self.period = period
        self.geography = geography
        self.params = params
        self.field = field
        self.note = note

    def recompute(self, totals):
        return self.field(totals)


def _verified(t):
    """Jobs on the VERIFIED basis: the published total minus the announced tier.

    This is the site's headline basis and it is the one a reader is told they are
    reading. It is written out here once so that no check re-derives it from an
    assumption about which field means what."""
    return _i(t.get("jobs")) - _i(t.get("announced_jobs"))


def _i(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _year(ctx):
    return str(ctx.today.year)


# The only parameters the home page's stamped query may contain. Each one
# chooses a BASIS — which date a row is counted on, which country column a
# country matches — and a basis is the page's to choose. Anything else
# (`company`, `ai`, `sources`, `state`, a `from`/`to` window) NARROWS the
# population, and a narrowed population under a figure labelled "worldwide,
# year to date" is the defect this module exists to catch. The allowlist is
# what stops "read the query off the page" from degenerating into "believe
# whatever the page says": the page may pick its basis, it may not pick its
# scope.
_STAMP_BASIS_KEYS = ("date_basis", "country_basis")
_STAMP_ALLOWED = ("years",) + _STAMP_BASIS_KEYS

_BOOT_RE = re.compile(r"window\.ALT_BOOTSTRAP\s*=\s*(\{.*?\})\s*;\s*</script>", re.S)


def _home_stamp(ctx):
    """The query the home page ITSELF says produced its server-rendered figures.

    Returns (params, problem, is_defect, transport). `params` is None whenever it
    could not be established, and then `problem` says why in the words the check
    will print. `transport` is the fetch exception when the page could not be
    reached at all, and it is carried out of here rather than swallowed: an
    UNKNOWN without its exception is indistinguishable from an UNKNOWN that
    decided something, and the degradation contract in test_dedup_live requires
    every transport UNKNOWN to name its cause.

    WHY THIS IS READ OFF THE PAGE AND NOT WRITTEN DOWN HERE. It used to be
    written down here, as `{"years": <current year>}`, under a docstring
    promising it was "exactly what the unfiltered home page sends". On 2026-08-10
    the page's default date basis moved from the effective date to the filing
    date (2.20.4). The commit message for that change says a default "lives in
    four places and all four moved" — layoffs.js, the switch markup, the server
    bootstrap and the hero's label. There was a fifth: this constant. It did not
    move, so from that day this module asked /aggregate a question the page never
    asks, got the effective-basis answer, compared it against the filed-basis
    figure the page had rendered, and reported a 33,426-job disagreement on four
    figures that were in fact correct and internally consistent.

    A stamp copied by hand drifts the moment the page changes and the copy is not
    updated, and nothing in the repo can notice. The page already publishes the
    stamp: `window.ALT_BOOTSTRAP.aggregate_params` is written by
    alt_tracker_bootstrap_payload() alongside the totals it computed from them,
    by the same code, in the same render. That is the stamp. Read it there.

    WHAT THIS DOES NOT DO. It does not let the page define its way to green. The
    stamp must name the current year and may otherwise carry only a basis (see
    _STAMP_ALLOWED); a stamp that narrows the population is reported as the
    defect it is rather than obediently queried.
    """
    html, err = _get_html(ctx, HOME_URL)
    if html is None:
        return None, _why_unreachable(err), False, err
    m = _BOOT_RE.search(html)
    if not m:
        return None, ("the home page inlines no window.ALT_BOOTSTRAP, so it does "
                      "not state which query produced its figures"), False, None
    try:
        boot = json.loads(m.group(1))
        stamp = boot.get("aggregate_params")
    except ValueError:
        return (None, "the home page's window.ALT_BOOTSTRAP is not readable JSON",
                False, None)
    if not isinstance(stamp, dict) or not stamp:
        return None, ("window.ALT_BOOTSTRAP carries no aggregate_params, so the "
                      "query behind the rendered figures is unstated"), False, None
    params = {str(k): str(v) for k, v in stamp.items()}

    extra = sorted(k for k in params if k not in _STAMP_ALLOWED)
    if extra:
        return None, (f"the home page's figures were computed on a NARROWED query "
                      f"{params} — {', '.join(extra)} scopes the population under "
                      f"figures labelled worldwide, year to date"), True, None
    if params.get("years") != _year(ctx):
        return None, (f"the home page's figures were computed for years="
                      f"{params.get('years')!r} but the page publishes them as "
                      f"{_year(ctx)} year to date"), True, None
    return params, None, False, None


def _home_params(ctx):
    """The stamped home query, or None when the page did not state one."""
    return _home_stamp(ctx)[0]


# ---------------------------------------------------------------------------
# THE REGISTRY: every home-page figure that is independently recomputable
# ---------------------------------------------------------------------------
# These are the figures the PHP bootstrap SERVER-RENDERS into the page and the
# REST endpoint also computes. That duality is what makes them checkable: two
# code paths, one number. Figures drawn only in canvas (the charts) cannot be
# read back out of the HTML and are covered by RECONCILIATION and DRILL_DOWN
# instead, which do not need the rendered pixel.
HOME_FIGURES = (
    Figure("home.hero_total", "home", "alt-hero-total",
           "verified job cuts", JOBS, "year to date", "worldwide",
           _home_params, _verified,
           note="THE hero figure. The number a journalist lands on and compares "
                "against the US national survey's monthly estimate."),
    Figure("home.hero_ai", "home", "alt-hero-ai",
           "blamed on AI by the employer", JOBS, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("ai_verified_jobs")),
           note="Sits inside the hero sentence, so it is quoted with the hero."),
    Figure("home.stat_total", "home", "alt-stat-total",
           "Verified job cuts", JOBS, "year to date", "worldwide",
           _home_params, _verified,
           note="Deliberately the same number as the hero. That is a promise the "
                "CROSS_SURFACE check holds them to."),
    Figure("home.stat_announced", "home", "alt-stat-announced",
           "Announced job cuts (planned)", JOBS, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("announced_jobs"))),
    Figure("home.stat_companies", "home", "alt-stat-companies",
           "Companies", COMPANIES, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("companies"))),
    Figure("home.stat_industries", "home", "alt-stat-industries",
           "industries", PLACES, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("industries"))),
    Figure("home.stat_countries", "home", "alt-stat-countries",
           "countries with reported layoffs", PLACES, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("countries"))),
    Figure("home.stat_states", "home", "alt-stat-states",
           "US states", PLACES, "year to date", "United States",
           _home_params, lambda t: _i(t.get("states"))),
    Figure("home.stat_ai_verified", "home", "alt-stat-ai",
           "AI cuts, verified (specific)", JOBS, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("ai_verified_jobs")),
           note="AI basis 1 of 4. All four must carry distinguishing labels."),
    Figure("home.stat_ai_announced", "home", "alt-stat-ai-announced",
           "AI cuts, announced (planned)", JOBS, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("ai_announced_jobs")),
           note="AI basis 2 of 4."),
    Figure("home.stat_all", "home", "alt-stat-all",
           "Verified + announced job cuts", JOBS, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("jobs"))),
    Figure("home.stat_ai_broad", "home", "alt-stat-ai-broad",
           "AI-linked, broad (wider lens)", JOBS, "year to date", "worldwide",
           _home_params, lambda t: _i(t.get("ai_broad_jobs")),
           note="AI basis 4 of 4, and the widest. Never summed with the others."),
)

# Figures on the page that are NOT in the registry above, and why. Named here
# rather than omitted, because an unlisted gap reads as coverage.
HOME_NOT_RECOMPUTABLE = {
    "alt-stat-ai-total": "derived in the browser as ai_verified + ai_announced; "
                         "both addends ARE checked, so the sum has no independent "
                         "source to check it against",
    "board (4 periods x 4 rows)": "server-rendered from four separate bootstrap "
                                  "aggregates; covered by DRILL_DOWN on the "
                                  "period filters, not by AGREEMENT",
    "canvas charts": "drawn into a canvas element and never present in the DOM as "
                     "text; covered by RECONCILIATION and DRILL_DOWN instead",
    "jobless-claims overlay": "a different universe entirely (national claims "
                              "data, persons not jobs) and never summed into any "
                              "tracker total",
}


# ---------------------------------------------------------------------------
# shared fetch helpers
# ---------------------------------------------------------------------------
def _get_json(ctx, path, params):
    q = dict(params)
    q["cb"] = ctx.cachebust
    url = BASE + path + "?" + urllib.parse.urlencode(q)
    try:
        return (json.loads(ctx.fetch(url, ctx.timeout)) or {}), None
    except Exception as e:                                  # noqa: BLE001
        return None, e


def _get_html(ctx, url):
    sep = "&" if "?" in url else "?"
    try:
        raw = ctx.fetch(url + sep + "cb=" + str(ctx.cachebust), ctx.timeout)
        return raw.decode("utf-8", "replace"), None
    except Exception as e:                                  # noqa: BLE001
        return None, e


def _why_unreachable(e):
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 503:
            return "site is in its deploy maintenance window (HTTP 503)"
        return f"live site returned HTTP {e.code}"
    return f"could not reach the live site ({e})"


_NUM_IN_ID = r'id=["\']{0}["\'][^>]*>([0-9,\.\s]+)<'


def _rendered(html, dom_id):
    """The number the page actually printed into that element, or None.

    Deliberately a regex over the served HTML rather than a DOM parse: this must
    run unattended in a runner with no browser, stdlib only, same as every other
    check in this repo."""
    m = re.search(_NUM_IN_ID.format(re.escape(dom_id)), html)
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(1))
    return int(digits) if digits else None


def _span_text(html, cls):
    """The full text of a <span class="..."> INCLUDING its nested spans.

    A flat `(.*?)</span>` stops at the first inner closing tag, which is fine
    until the label being read grows a nested span — and the hero label has two,
    one for geography and one for the period. Read flatly, "verified job cuts
    worldwide, calendar year 2026" truncates to "verified job cuts worldwide" and
    the check reports a missing period that is right there on the page. So this
    counts nesting depth instead of trusting what follows the element.
    """
    m = re.search(r'<span[^>]*class=["\'][^"\']*'
                  + re.escape(cls) + r'[^"\']*["\'][^>]*>', html or "")
    if not m:
        return None
    depth, i = 1, m.end()
    for tok in re.finditer(r"<span\b|</span>", html[m.end():]):
        depth += 1 if tok.group(0) != "</span>" else -1
        if depth == 0:
            i = m.end() + tok.start()
            break
    else:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html[m.end():i])).strip()


class _Slice:
    """_roll_up() wants something with .label and .name. This is that."""

    def __init__(self, key, label):
        self.name = key
        self.label = label


# ---------------------------------------------------------------------------
# WHAT THE DOUGHNUT ACTUALLY DRAWS
# ---------------------------------------------------------------------------
# A /aggregate `reasons` row is [tag, all_jobs, all_ai_jobs, None, verified_jobs,
# verified_ai_jobs]. The page does NOT draw column 1. renderReasons() in
# layoffs.js pipes every row through verifiedBasis(), which takes column 4, drops
# any slice left at zero, and sorts descending — so the chart is on the same
# verified basis as the headline above it and as the filter a click applies.
#
# THIS IS THE MISTAKE THIS MODULE MADE, and it is worth naming precisely because
# it is the module's own stated failure mode pointed the wrong way. The checker
# read column 1, called it "what the slice displays", and reported eight slices
# as 1.2x to 14.9x wrong. Every one of those numbers was real and none of them
# was on the page. A checker that decides for itself what a page renders, instead
# of following the code that renders it, does not catch a defect — it invents
# one, and an invented defect is worse than no check, because the next real
# alert gets read as more of the same.
#
# So the basis is not assumed here either. _reasons_basis() reads the DEPLOYED
# asset and reports which column the shipped code maps. If that asset cannot be
# read, the answer is UNKNOWN and the slice checks say so rather than guessing.
_VERIFIED_BASIS_SIGNATURES = (
    # minified: `null!=t[4]?t[4]:t[1]`   source: `(e[4] != null) ? e[4] : e[1]`
    re.compile(r"null\s*!=\s*(\w+)\[4\]\s*\?\s*\1\[4\]\s*:\s*\1\[1\]"),
    re.compile(r"\(\s*(\w+)\[4\]\s*!=\s*null\s*\)\s*\?\s*\1\[4\]\s*:\s*\1\[1\]"),
)


def _script_url(html, name="layoffs.js"):
    m = re.search(r'src=["\']([^"\']*' + re.escape(name) + r'[^"\']*)["\']', html or "")
    return m.group(1) if m else None


def _reasons_basis(ctx, html):
    """Which column the SHIPPED chart code draws: "verified", "all", or None.

    Two derivations, same rule as everywhere else in this module: the numbers
    come from the API and the basis comes from the asset the browser executes.
    Neither is this module's opinion about what the chart ought to do.
    """
    url = _script_url(html)
    if not url:
        return None, "the served page names no layoffs.js asset"
    try:
        js = ctx.fetch(url, ctx.timeout).decode("utf-8", "replace")
    except Exception as e:                                  # noqa: BLE001
        return None, f"could not read the deployed chart code ({e})"
    if any(p.search(js) for p in _VERIFIED_BASIS_SIGNATURES):
        return "verified", js
    return "all", js


def _drawn_slices(rows, basis):
    """The slices the chart puts on screen, in the order it puts them there.

    Mirrors verifiedBasis() in layoffs.js exactly: column 4 when the deployed
    code maps it, zero-value slices dropped (they are never drawn, so they can
    never be tapped), largest first.
    """
    out = []
    for r in rows or []:
        if not r or len(r) < 2:
            continue
        if basis == "verified" and len(r) > 4 and r[4] is not None:
            v = _i(r[4])
        else:
            v = _i(r[1])
        out.append((str(r[0]), v))
    drawn = [(t, v) for t, v in out if v > 0]
    drawn.sort(key=lambda e: -e[1])
    return drawn, [(t, v) for t, v in out if v <= 0]


# ---------------------------------------------------------------------------
# 1. AGREEMENT
# ---------------------------------------------------------------------------
class FigureAgreementInvariant:
    """The number ON THE PAGE equals the API's answer to that number's own query.

    THE TWO DERIVATIONS. The page is server-rendered by PHP from a cached
    bootstrap payload; the value here comes from a fresh, cache-busted /aggregate
    call. Different code, different cache, same claimed fact. When they disagree,
    one of them is what a reader is looking at and the other is what the data
    says, and it does not matter which is which — the site is publishing a number
    it cannot reproduce.

    WHY IT IS NOT SELF-AGREEING. Each figure's params come from FIGURES, and
    FIGURES reads the stamp the PAGE published beside its own numbers
    (window.ALT_BOOTSTRAP.aggregate_params), not an assumption re-derived here
    about what the figure "ought" to mean. A checker that recomputed the query
    from an assumption agrees with its own assumption; one that hard-codes the
    page's default agrees with the page as of the day someone last typed it out,
    which is how this check spent 2026-08-10 to 2026-08-11 failing four correct
    figures. And the page cannot define its way to green either: a stamp that
    narrows the population instead of choosing a basis is a FAIL (see
    _home_stamp).

    WHAT THE TWO DERIVATIONS ACTUALLY ARE, stated exactly, because overclaiming
    it is worse than the narrower truth. The bootstrap calls the same /aggregate
    callback through the same transient, so this is NOT two independent SQL
    computes of the same figure. It is (1) the number a reader is served — the
    page's own arithmetic over the totals it inlined, rendered, minified, and
    replayed by whatever caches sit in front of /blog — against (2) what
    /aggregate answers, live and cache-busted, right now. That catches wrong
    arithmetic in the template, a mislabelled tile, a figure that vanished, and a
    served page whose numbers are older than the data. It does not catch a wrong
    number that both paths compute identically; RECONCILIATION and DRILL_DOWN
    are what stand behind that.
    """

    key = "figures_agree_with_api"
    label = "Home figures agree with the API"
    reads_live_data = True

    def run(self, ctx):
        di = _di()
        html, err = _get_html(ctx, HOME_URL)
        if html is None:
            ctx.errors[self.key] = err
            return di.Result(self, di.UNKNOWN, error=err,
                             detail=_why_unreachable(err) + " — home figures NOT checked")

        stamp, problem, is_defect, terr = _home_stamp(ctx)
        if stamp is None:
            # A stamp that NARROWS is a defect in what was published, not a gap
            # in what could be measured, so it is a FAIL and not an UNKNOWN.
            if terr is not None:
                ctx.errors[self.key] = terr
            return di.Result(self, di.FAIL if is_defect else di.UNKNOWN, error=terr,
                             detail=problem + ("" if is_defect
                                               else " — home figures NOT checked"))

        payload, err = _get_json(ctx, "aggregate", stamp)
        if payload is None:
            ctx.errors[self.key] = err
            return di.Result(self, di.UNKNOWN, error=err,
                             detail=_why_unreachable(err) + " — home figures NOT checked")
        totals = payload.get("totals") or {}
        if "jobs" not in totals:
            return di.Result(self, di.UNKNOWN,
                             detail="live API returned no totals for the home query")

        per = []
        for f in HOME_FIGURES:
            shown = _rendered(html, f.dom_id)
            expect = f.recompute(totals)
            sl = _Slice(f.key, f.key)
            if shown is None:
                # Not a pass. The figure is either gone from the page or renamed,
                # and either way this check no longer covers it.
                per.append((sl, di._out(di.UNKNOWN,
                            f"#{f.dom_id} not found in the served page — this "
                            f"figure is NOT being checked")))
            elif shown != expect:
                per.append((sl, di._out(di.FAIL,
                            f"page shows {shown:,} but the API answers {expect:,} "
                            f"for its own query {f.params(ctx)} "
                            f"({f.label}, {f.unit}, {f.period})",
                            observed=shown)))
            else:
                per.append((sl, di._out(di.PASS, f"{shown:,} {f.unit}")))

        skipped = ", ".join(sorted(HOME_NOT_RECOMPUTABLE))
        res = di._roll_up(self, ctx, per)
        if res.state == di.PASS:
            res.detail = (f"{len(HOME_FIGURES)} home figures match the API; "
                          f"not independently recomputable and therefore NOT "
                          f"covered here: {skipped}")
        return res


# ---------------------------------------------------------------------------
# 2. RECONCILIATION
# ---------------------------------------------------------------------------
class FigureReconciliationInvariant:
    """The parts a reader can see add up to the whole, or the card says why not.

    THE DEFECT THIS IS BUILT FROM. A chart summed to roughly 757,000 beside a
    published headline of 444,871, and a chart scoped to one country was
    reconciled against a worldwide denominator, overstating by about 104,000.
    Both are the same mistake: a set of parts and a whole that describe different
    populations, presented as if they described the same one.

    So this check never compares a bare sum to a bare total. It asks, for each
    breakdown, whether the parts and the whole are on the SAME basis, and whether
    the sum lands where the basis says it should:

      series       one bucket per month, disjoint, so it MUST equal the headline
                   exactly. Any drift is a partial period being drawn as complete
                   or a chart on a different basis from the number above it.
      reasons      a row may carry several reason tags, so the slices legitimately
                   overlap and CANNOT sum to the whole. That is allowed only if
                   the card says so and only against the basis it is drawn on. A
                   sum below the whole would mean the opposite problem: slices
                   silently dropping rows.
      geography    countries and states are disjoint per row, so their sums must
                   not EXCEED the whole they are drawn against. A US-scoped list
                   measured against a worldwide total is the 104,000 defect.
    """

    key = "figure_parts_reconcile"
    label = "Published breakdowns reconcile with their own headline"
    reads_live_data = True

    # Phrases that would constitute the card STATING why its parts do not sum to
    # the whole. A card carrying one of these has told the reader what they are
    # looking at; a card carrying none has not.
    #
    # A sum can miss the headline in two OPPOSITE directions and they need
    # different sentences, so they are two lists. Overlap pushes a sum UP: one
    # event carrying three tags is counted in three slices. Untagged rows pull it
    # DOWN: an event whose source states no reason is on no slice at all. On the
    # 2026 view both are true at once, and a card that discloses only overlap
    # while sitting 196,072 BELOW its headline has not explained what the reader
    # is looking at.
    OVERLAP_DISCLOSURES = (
        "can carry more than one",
        "more than one reason",
        "carry several tags",
        "reason tags overlap",
        "slices overlap",
        "overlap, so they do not sum",
        "do not sum to",
        "not meant to sum",
        "adds up to more than",
        "counted under each",
    )
    UNTAGGED_DISCLOSURES = (
        "states no reason carries none",
        "no reason carries none",
        "carries no tag",
        "not a breakdown of the total",
        "records with no reason",
    )

    def run(self, ctx):
        di = _di()
        params, problem, _defect, terr = _home_stamp(ctx)
        if params is None:
            if terr is not None:
                ctx.errors[self.key] = terr
            return di.Result(self, di.UNKNOWN, error=terr,
                             detail=problem + " — reconciliation NOT checked")
        html, _herr = _get_html(ctx, HOME_URL)
        payload, err = _get_json(ctx, "aggregate", params)
        if payload is None:
            ctx.errors[self.key] = err
            return di.Result(self, di.UNKNOWN, error=err,
                             detail=_why_unreachable(err) + " — reconciliation NOT checked")
        totals = payload.get("totals") or {}
        if "jobs" not in totals:
            return di.Result(self, di.UNKNOWN,
                             detail="live API returned no totals for the home query")

        verified = _verified(totals)
        alljobs = _i(totals.get("jobs"))  # noqa: F841 - kept for basis reporting
        per = []

        # --- monthly series: disjoint buckets, must equal the headline exactly
        series = payload.get("series")
        sl = _Slice("series", "monthly chart vs the headline")
        if not series:
            per.append((sl, di._out(di.UNKNOWN,
                        "the live response carried no series block — the monthly "
                        "chart is NOT being reconciled")))
        else:
            s = sum(_i(p.get("verified_jobs")) for p in series)
            if s != verified:
                per.append((sl, di._out(di.FAIL,
                            f"the monthly chart sums to {s:,} verified jobs but the "
                            f"headline above it publishes {verified:,} "
                            f"(delta {s - verified:+,}). A reader adding up the bars "
                            f"cannot reach the published number",
                            observed=s)))
            else:
                per.append((sl, di._out(di.PASS,
                            f"{len(series)} months sum to {s:,}, equal to the headline")))

        # --- monthly series: every bucket must sit inside the window it is drawn in
        #
        # THE OTHER HALF OF THE SAME DEFECT, and the half a sum cannot catch. A
        # chart that selects rows by one date and stacks them by another is
        # wrong in two independent ways: the total drifts (above) AND buckets
        # appear that the filter excluded. On 2026-08-11 the page's own default
        # query, years=2026, returned 2027-02 and 2027-03 buckets, because the
        # WHERE ran on COALESCE(announcement_date, layoff_date) and the GROUP BY
        # ran on layoff_date. Those two symptoms can also occur ALONE: a
        # compensating pair of stray buckets can sum to the right number, and a
        # dropped row can shorten the sum without adding a bucket. So they are
        # two slices, not one.
        #
        # Only years= is checked, and deliberately: it is the one filter whose
        # correct bucket set is knowable from the request alone, without
        # re-deriving the server's own window arithmetic here and thereby
        # grading this checker's copy of it instead of the page.
        sl = _Slice("series_window", "monthly chart buckets vs the window they are drawn in")
        want_years = {y.strip() for y in str(params.get("years", "")).split(",") if y.strip()}
        if not series:
            per.append((sl, di._out(di.UNKNOWN,
                        "the live response carried no series block — the chart's "
                        "buckets are NOT being checked")))
        elif not want_years:
            per.append((sl, di._out(di.UNKNOWN,
                        f"the home query carries no years= filter ({params!r}), so "
                        "there is no window to hold the buckets against")))
        else:
            labelled = [str(p.get("month") or "") for p in series if p.get("month")]
            stray = sorted({m for m in labelled if m[:4] not in want_years})
            if not labelled:
                # Absence of a signal is not a pass. A bucket with no label
                # cannot be held against the window it is drawn in, and a slice
                # that quietly skipped those would report "no stray buckets"
                # about a chart whose buckets it never read.
                per.append((sl, di._out(di.UNKNOWN,
                            f"none of the {len(series)} series rows carry a month "
                            f"key, so the chart's buckets cannot be held against "
                            f"the {'/'.join(sorted(want_years))} window")))
            elif stray:
                per.append((sl, di._out(di.FAIL,
                            f"the monthly chart is drawn for "
                            f"{'/'.join(sorted(want_years))} but the response carries "
                            f"{len(stray)} bucket(s) outside it: {', '.join(stray)}. A "
                            f"bucket has to contain what its label says it contains, so "
                            f"the rows were selected on one date and stacked on another",
                            observed=len(stray))))
            else:
                per.append((sl, di._out(di.PASS,
                            f"all {len(labelled)} labelled buckets fall inside "
                            f"{'/'.join(sorted(want_years))}")))

        # --- reasons doughnut: overlap allowed, unbounded overlap is not
        reasons = payload.get("reasons") or []
        sl = _Slice("reasons", "reasons doughnut vs its own basis")
        basis, js = _reasons_basis(ctx, html)
        if not reasons:
            per.append((sl, di._out(di.UNKNOWN,
                        "the live response carried no reasons block — the doughnut "
                        "is NOT being reconciled")))
        elif basis is None:
            per.append((sl, di._out(di.UNKNOWN,
                        f"{js} — which column the chart draws is therefore unknown, "
                        f"and the doughnut is NOT being reconciled")))
        else:
            drawn, zeroed = _drawn_slices(reasons, basis)
            s = sum(v for _t, v in drawn)
            # RECONCILE THE SLICES THAT ARE ON SCREEN, AGAINST THE HEADLINE BESIDE
            # THEM. Both halves of that sentence are load-bearing. The headline is
            # the verified basis, so a sum measured against the all-jobs figure
            # would reconcile the card against a number the page never prints. And
            # the slices are the ones _drawn_slices() says the deployed chart code
            # draws, not a column this check picked — reading column 1 while the
            # shipped chart drew column 4 is exactly how this check came to report
            # eight defects that were not on the page.
            ratio = (s / float(verified)) if verified else 0.0
            hay = ((html or "") + (js if isinstance(js, str) else "")).lower()
            # The card's sentence is written by renderReasons() at run time, so it
            # is in the shipped SCRIPT, not in the server-rendered body. Looking
            # only at the HTML would report "the card does not say why" about a
            # card that says exactly why, every time it draws.
            overlap_said = any(d in hay for d in self.OVERLAP_DISCLOSURES)
            untagged_said = any(d in hay for d in self.UNTAGGED_DISCLOSURES)
            biggest = max(drawn, key=lambda e: e[1]) if drawn else None

            if biggest and biggest[1] > verified:
                # A slice is a SUBSET of the population. One larger than the whole
                # is a basis error no disclosure can excuse.
                per.append((sl, di._out(di.FAIL,
                            f"the '{biggest[0]}' slice alone displays {biggest[1]:,} "
                            f"against a headline of {verified:,} — a slice cannot be "
                            f"larger than the population it is drawn from, so the "
                            f"chart and the headline are on different bases",
                            observed=biggest[1])))
            elif s == verified:
                per.append((sl, di._out(di.PASS,
                            f"{len(drawn)} slices sum exactly to the {verified:,} "
                            f"headline")))
            elif s > verified and not overlap_said:
                per.append((sl, di._out(di.FAIL,
                            f"the doughnut slices sum to {s:,} but the headline they "
                            f"sit beside publishes {verified:,} ({ratio:.2f}x), and the "
                            f"card does not say why. A reader adding up the slices "
                            f"lands {s - verified:+,} away from the published number. "
                            f"Either reconcile the slices to the headline basis or "
                            f"state on the card that a cut can carry more than one "
                            f"reason",
                            observed=s)))
            elif s < verified and not untagged_said:
                per.append((sl, di._out(di.FAIL,
                            f"the doughnut slices sum to {s:,}, {verified - s:,} BELOW "
                            f"the verified headline of {verified:,}, and the card does "
                            f"not say why. Overlap can only push a sum UP, so either "
                            f"slices are dropping rows or the card must state that an "
                            f"event whose source gives no reason carries no tag",
                            observed=s)))
            else:
                said = "overlap" if s > verified else "untagged events"
                detail = (f"{len(drawn)} drawn slices sum to {s:,} ({ratio:.2f}x of the "
                          f"{verified:,} headline), no slice exceeds it, and the card "
                          f"discloses {said} [basis: the deployed chart draws the "
                          f"{basis} column]")
                if zeroed:
                    detail += (" [drawn as no slice at all, so untappable: "
                               + ", ".join(t for t, _v in zeroed) + "]")
                per.append((sl, di._out(di.PASS, detail)))

        # --- geography: disjoint per row, must not exceed the whole
        for block, human in (("top_countries", "countries"), ("top_states", "US states")):
            rows = payload.get(block) or []
            sl = _Slice(block, f"{human} bars vs the headline")
            if not rows:
                per.append((sl, di._out(di.UNKNOWN,
                            f"no {block} block in the live response — the {human} "
                            f"bars are NOT being reconciled")))
                continue
            # index 4 is the verified-jobs column the bars are drawn from
            s = sum(_i(r[4]) if len(r) > 4 else 0 for r in rows)
            whole = verified
            if block == "top_states":
                # A US-scoped list must be reconciled against the US total, never
                # against the worldwide one. Recomputing the correct denominator
                # rather than assuming it is the whole point of this branch.
                us, uerr = _get_json(ctx, "aggregate",
                                     dict(params, country="United States",
                                          country_basis="any"))
                if us is None:
                    per.append((sl, di._out(di.UNKNOWN,
                                "could not fetch the US denominator — the US bars "
                                "are NOT being reconciled")))
                    continue
                whole = _verified(us.get("totals") or {})
            if s > whole:
                per.append((sl, di._out(di.FAIL,
                            f"the {human} bars sum to {s:,} against a published "
                            f"{whole:,} — the parts exceed the whole by "
                            f"{s - whole:,}, so they are on different bases",
                            observed=s)))
            else:
                per.append((sl, di._out(di.PASS,
                            f"top {len(rows)} {human} sum to {s:,}, within {whole:,}")))

        return di._roll_up(self, ctx, per)


# ---------------------------------------------------------------------------
# 3. DRILL-DOWN
# ---------------------------------------------------------------------------
class DrillDownInvariant:
    """Tapping a slice returns the count the slice displays.

    This is the defect a READER finds for you. They see a slice labelled 10,415,
    they tap it because that is what a chart is for, and the page fills with 700.
    Nothing errored. The slice was computed over one population and the filter it
    applies selects another.

    WHAT IT DOES. For each slice the doughnut draws, it issues the SAME filter the
    click handler issues and compares the answer to the displayed value on the
    basis the reader lands on. Not the basis the slice was computed on — the one
    they end up looking at. That difference IS the bug.

    "THE SLICE DISPLAYS" MEANS WHAT THE DEPLOYED CHART CODE PUTS ON SCREEN, and
    getting that wrong is how this check spent a day reporting eight defects that
    did not exist. It read the all-jobs column out of the API and called it the
    displayed value, while renderReasons() had been drawing the verified column
    for weeks. Every ratio it printed was arithmetic on a number no reader could
    see. _drawn_slices() now takes the column the shipped asset maps, so the
    comparison is page-against-API rather than assumption-against-API.

    A SLICE THAT IS NOT DRAWN CANNOT BE TAPPED. A tag with zero verified jobs is
    filtered out of the chart entirely, so there is no wedge and no click. It is
    named in the detail as undrawn rather than reported as a slice that returns
    nothing, which is a different and much louder claim.

    Bounded, and it says what it bounded. Ten reason tags is the whole doughnut,
    so nothing is skipped there; the geography bars are capped and the cap is
    named in the detail rather than left implicit.
    """

    key = "figure_drilldown_matches"
    label = "Chart drill-downs return what they display"
    reads_live_data = True

    # Below this many jobs a slice is too small for the ratio to mean anything.
    FLOOR = 200
    # A displayed value more than this multiple of what the click returns is the
    # defect, not rounding.
    MAX_RATIO = 1.10

    def run(self, ctx):
        di = _di()
        params, problem, _defect, terr = _home_stamp(ctx)
        if params is None:
            if terr is not None:
                ctx.errors[self.key] = terr
            return di.Result(self, di.UNKNOWN, error=terr,
                             detail=problem + " — drill-downs NOT checked")
        payload, err = _get_json(ctx, "aggregate", params)
        if payload is None:
            ctx.errors[self.key] = err
            return di.Result(self, di.UNKNOWN, error=err,
                             detail=_why_unreachable(err) + " — drill-downs NOT checked")
        reasons = payload.get("reasons") or []
        if not reasons:
            return di.Result(self, di.UNKNOWN,
                             detail="no reasons block in the live response — chart "
                                    "drill-downs are NOT being checked")

        html, _herr = _get_html(ctx, HOME_URL)
        basis, why = _reasons_basis(ctx, html)
        if basis is None:
            return di.Result(self, di.UNKNOWN,
                             detail=f"{why} — the displayed value cannot be read from "
                                    f"the shipped chart code, so drill-downs are NOT "
                                    f"being checked")
        drawn, zeroed = _drawn_slices(reasons, basis)

        per = []
        skipped = []
        if zeroed:
            skipped.append("drawn as no slice at all and therefore untappable: "
                           + ", ".join(t for t, _v in zeroed))
        for tag, shown in drawn:
            sl = _Slice("reason:" + str(tag), f"doughnut slice {tag}")
            if shown < self.FLOOR:
                skipped.append(f"{tag} ({shown:,} < floor {self.FLOOR})")
                continue
            got, gerr = _get_json(ctx, "aggregate", dict(params, reasons=tag))
            if got is None:
                per.append((sl, di._out(di.UNKNOWN,
                            f"could not fetch the drill-down for {tag} — this slice "
                            f"is NOT being checked")))
                continue
            t = got.get("totals") or {}
            landed = _verified(t)      # what the reader sees after the click
            if landed <= 0:
                per.append((sl, di._out(di.FAIL,
                            f"the slice displays {shown:,} jobs but tapping it returns "
                            f"nothing at all",
                            observed=shown)))
            elif shown > landed * self.MAX_RATIO:
                per.append((sl, di._out(di.FAIL,
                            f"the slice displays {shown:,} jobs but tapping it returns "
                            f"{landed:,} ({shown / float(landed):.1f}x). The slice is "
                            f"computed over a different population from the one the "
                            f"click selects",
                            observed=shown)))
            else:
                per.append((sl, di._out(di.PASS,
                            f"displays {shown:,}, click returns {landed:,}")))

        if not per:
            return di.Result(self, di.UNKNOWN,
                             detail="every slice fell below the floor — nothing was "
                                    "actually checked")
        res = di._roll_up(self, ctx, per)
        if res.state == di.PASS:
            res.detail += (f" [displayed value read from the deployed chart code, "
                           f"which draws the {basis} column]")
        if skipped:
            res.detail += f" [not checked: {'; '.join(skipped)}]"
        return res


# ---------------------------------------------------------------------------
# 4. BASIS
# ---------------------------------------------------------------------------
class BasisDisclosureInvariant:
    """A label names its unit, its period and its geography — and equal labels
    mean equal bases.

    WHY A CORRECT NUMBER CAN STILL FAIL HERE. A journalist landing on the home
    page compares our headline against the US national survey's monthly estimate
    within seconds. If our figure does not say, in the label itself, that it
    counts verified job cuts, over a stated period, over a stated geography, then
    a correct number reads as a contradiction of theirs. The credibility cost is
    identical to publishing a wrong number, and it is invisible to every check
    that only looks at arithmetic.

    So this reads the SERVED PAGE, not the source, and asserts the hero's label
    carries all three. It also asserts that the several AI figures — which sit on
    four genuinely different bases — carry labels that distinguish them, because
    four numbers all called "AI" on one page is not a labelling nit, it is four
    numbers a reader will assume are comparable.
    """

    key = "figure_basis_is_stated"
    label = "Published figures state their basis"
    reads_live_data = True

    # "calendar year 2026" is a period; a bare "2026" is deliberately NOT, and
    # that omission stays. Rows are dated by EFFECTIVE date, so the 2026 window
    # holds notices filed for dates still ahead — a reader told only "2026"
    # cannot tell whether they are looking at what has happened or at what is on
    # file, and those are two different numbers 33,939 apart.
    PERIOD_WORDS = ("ytd", "year to date", "this year", "all time", "trailing",
                    "last 12", "so far", "calendar year")
    GEO_WORDS = ("worldwide", "global", "united states", "us ", "u.s.",
                 "world", "across")
    UNIT_WORDS = ("job cut", "jobs", "companies", "employers", "events",
                  "records", "states", "countries", "industries")

    def run(self, ctx):
        di = _di()
        html, err = _get_html(ctx, HOME_URL)
        if html is None:
            ctx.errors[self.key] = err
            return di.Result(self, di.UNKNOWN, error=err,
                             detail=_why_unreachable(err) + " — basis labels NOT checked")

        per = []

        # --- the hero label must name unit, period AND geography
        sl = _Slice("hero_label", "hero label states its basis")
        text = _span_text(html, "alt-hero-figure-label")
        if text is None:
            per.append((sl, di._out(di.UNKNOWN,
                        "the hero label was not found in the served page — its basis "
                        "is NOT being checked")))
        else:
            text = text.lower()
            missing = []
            if not any(w in text for w in self.UNIT_WORDS):
                missing.append("unit")
            if not any(w in text for w in self.PERIOD_WORDS):
                missing.append("period")
            if not any(w in text for w in self.GEO_WORDS):
                missing.append("geography")
            if missing:
                per.append((sl, di._out(di.FAIL,
                            f'the hero reads "{text}" and does not state its '
                            f'{" or ".join(missing)}. A reader comparing it against a '
                            f'national estimate cannot tell what it counts')))
            else:
                per.append((sl, di._out(di.PASS, f'hero label states unit, period '
                                                 f'and geography: "{text}"')))

        # --- the four AI figures must be distinguishable from one another
        sl = _Slice("ai_labels", "the AI figures are distinguishable")
        ai_ids = [f for f in HOME_FIGURES if ".stat_ai" in f.key or f.key.endswith("hero_ai")]
        labels = {}
        for f in ai_ids:
            lm = re.search(
                r'id=["\']' + re.escape(f.dom_id) + r'["\'][^>]*>[^<]*</span>\s*'
                r'<span class=["\']alt-stat-label["\']>(.*?)</span>', html, re.S)
            if lm:
                labels[f.key] = re.sub(r"\s+", " ",
                                       re.sub(r"<[^>]+>", "", lm.group(1))).strip()
        dupes = {}
        for k, v in labels.items():
            dupes.setdefault(v.lower(), []).append(k)
        clashing = {v: ks for v, ks in dupes.items() if len(ks) > 1}
        if not labels:
            per.append((sl, di._out(di.UNKNOWN,
                        "no AI stat labels were found in the served page — they are "
                        "NOT being checked")))
        elif clashing:
            per.append((sl, di._out(di.FAIL,
                        "two AI figures on different bases share one label: "
                        + "; ".join(f'"{v}" used by {", ".join(ks)}'
                                    for v, ks in clashing.items()))))
        else:
            per.append((sl, di._out(di.PASS,
                        f"{len(labels)} AI figures carry distinct labels")))

        return di._roll_up(self, ctx, per)


# ---------------------------------------------------------------------------
# 5. CROSS-SURFACE AGREEMENT
# ---------------------------------------------------------------------------
class CrossSurfaceAgreementInvariant:
    """One figure, published on two pages, is the same number on both.

    THE FAILURE THIS PREVENTS is specific and it is the worst one available: a
    journalist opens the home page, opens the press page — which exists to be
    quoted — and finds two different headline totals for the same thing. There is
    no recovery from that in the reader's mind. It does not read as a rounding
    difference, it reads as a tracker that does not know its own numbers.

    ONE CLAIM HAS ONE ANSWER. TWO CLAIMS MAY HAVE TWO, AND MUST SHOW THE WORKING.
    This check first demanded the two figures be equal, and that was too strict in
    a way worth writing down, because "too strict" is how a guard gets switched
    off. Rows are dated by EFFECTIVE date, and WARN notices are filed by law weeks
    before the cut lands. So a calendar year legitimately has two correct totals:
    what has taken effect (449,768 on 2026-08-04) and the whole window as filed
    (483,707). The press page leads with the first because it is being quoted into
    a "so far" sentence; the home page headlines the second.

    Prose alone must not buy an exemption — "these measure different things" is
    what a genuinely broken pair of numbers would also say. So the escape hatch
    here is ARITHMETIC, and all four conditions have to hold:

      1. the home figure equals the API's calendar-year verified total,
      2. the press figure equals the API's to-date verified total,
      3. both pages print the SAME reconciling sentence, and
      4. the residual that sentence names equals home minus press, exactly.

    Any drift in any of those four and this fails, which is the point: the pair is
    allowed to differ only while it can still be added up. Two unexplained totals,
    or an explanation whose subtraction does not check out, is the original defect
    and still reads FAIL.

    It also holds the two ops surfaces to the same standard: /source-health and
    /quality-status answer the same question about the same collector, and a
    collector that one of them calls retired cannot be 'ok' on the other. A
    retired collector published as live is a claim about how fresh the data is,
    which is exactly the kind of number a reader trusts without checking.
    """

    key = "figures_agree_across_surfaces"
    label = "The same figure agrees on every page that prints it"
    reads_live_data = True

    # Two pages computing the same claim through different SQL will not differ.
    # This is not a tolerance for drift, it is a tolerance for the seconds between
    # two fetches while a collector writes.
    TOLERANCE = 0.005

    def run(self, ctx):
        di = _di()
        per = []

        # --- home hero vs the press page headline
        sl = _Slice("home_vs_press", "home hero vs press headline")
        home_html, herr = _get_html(ctx, HOME_URL)
        press_html, perr = _get_html(ctx, PRESS_URL)
        if home_html is None or press_html is None:
            e = herr or perr
            # Filed under the SLICE name as well as the invariant key, because
            # _roll_up looks the error up by slice. Without this the exception is
            # dropped, Result.transport comes back False, and a dead network is
            # reported as "the site answered wrongly" — the one distinction
            # ops_status uses to tell an environment block (exit 3) from a real
            # defect (exit 2). This is the only check here that reaches a verdict
            # through _roll_up after a transport failure; the other five return
            # their Result directly with error= set, which is why they were fine.
            ctx.errors[self.key] = e
            ctx.errors[sl.name] = e
            per.append((sl, di._out(di.UNKNOWN,
                        _why_unreachable(e) + " — cross-surface agreement NOT checked")))
        else:
            hero = _rendered(home_html, "alt-hero-total")
            press = self._press_headline(press_html, ctx)
            if hero is None:
                per.append((sl, di._out(di.UNKNOWN,
                            "the home hero was not found — NOT checked")))
            elif press is None:
                per.append((sl, di._out(di.UNKNOWN,
                            "the press page headline sentence was not found — NOT "
                            "checked")))
            else:
                gap = abs(hero - press)
                if gap <= max(1, hero * self.TOLERANCE):
                    per.append((sl, di._out(di.PASS,
                                f"home {hero:,} and press {press:,} agree")))
                else:
                    per.append((sl, self._reconciled(ctx, di, hero, press,
                                                     home_html, press_html)))

        # --- retired collectors: two endpoints, one truth
        sl = _Slice("retired_collectors", "retired collectors are not published as live")
        health, herr2 = _get_json(ctx, "source-health", {})
        quality, qerr = _get_json(ctx, "quality-status", {})
        if health is None or quality is None:
            ctx.errors[sl.name] = herr2 or qerr
            per.append((sl, di._out(di.UNKNOWN,
                        _why_unreachable(herr2 or qerr)
                        + " — retired-collector agreement NOT checked")))
        else:
            hmap = self._status_map(health)
            qmap = self._status_map(quality.get("source_health") or quality)
            retired = {k for k, v in hmap.items() if v == "retired"}
            leaking = sorted(k for k in retired
                             if qmap.get(k) and qmap[k] != "retired")
            if not retired:
                per.append((sl, di._out(di.UNKNOWN,
                            "no endpoint reported any retired collector, so this "
                            "check could not confirm the masking works at all")))
            elif leaking:
                per.append((sl, di._out(di.FAIL,
                            "retired collectors are published as live on "
                            "/quality-status (and therefore on the health page): "
                            + "; ".join(f"{k} reads '{qmap[k]}' there but 'retired' "
                                        f"on /source-health" for k in leaking))))
            else:
                per.append((sl, di._out(di.PASS,
                            f"{len(retired)} retired collectors are masked "
                            f"consistently on both endpoints")))

        return di._roll_up(self, ctx, per)

    # The reconciling sentence both pages print, from alt_period_split_sentence()
    # in db.php and periodSplitSentence() in layoffs.js. Captured as three numbers
    # because this check does the subtraction itself; matching the prose without
    # checking the arithmetic would let any sentence excuse any pair of figures.
    SPLIT = re.compile(
        r"([\d,]+) have taken effect as of [^.]+\. The other ([\d,]+) are on notices "
        r"already filed for effective dates later in (\d{4})\. Together they make the "
        r"([\d,]+) total for \3\.", re.I)

    def _reconciled(self, ctx, di, hero, press, home_html, press_html):
        """FAIL, unless the two figures are two correct periods that ADD UP.

        Every branch below that is not the last one is a FAIL, and they are
        written out separately so the alert says which condition broke rather
        than "the pages disagree".
        """
        gap = hero - press
        unexplained = (
            f"the home page publishes {hero:,} verified job cuts for the year and "
            f"the press page publishes {press:,} for the same claim — a gap of "
            f"{abs(gap):,}. A journalist reading both gets two answers")

        # (1)+(2) both figures must be periods the API actually produces.
        stamp, problem, _defect, terr = _home_stamp(ctx)
        if stamp is None:
            if terr is not None:
                ctx.errors["home_vs_press"] = terr
            return di._out(di.UNKNOWN, problem
                           + " — whether the gap reconciles is NOT checked")
        payload, err = _get_json(ctx, "aggregate", stamp)
        if payload is None:
            ctx.errors["home_vs_press"] = err
            return di._out(di.UNKNOWN, _why_unreachable(err)
                           + " — whether the gap reconciles is NOT checked")
        t = payload.get("totals") or {}
        if "jobs" not in t or t.get("to_date_jobs") is None:
            return di._out(di.UNKNOWN,
                           "the API returned no to-date totals, so whether the gap "
                           "reconciles is NOT checked")
        calendar = _verified(t)
        to_date = _i(t.get("to_date_jobs")) - _i(t.get("to_date_announced_jobs"))

        if hero != calendar or press != to_date:
            return di._out(di.FAIL, unexplained + (
                f". Neither is a stated period of the other: the API's calendar-year "
                f"verified total is {calendar:,} and its to-date verified total is "
                f"{to_date:,}"), observed=hero)

        # (3) the same sentence on both surfaces, or one page has an explanation
        # the other reader never sees.
        hm = self.SPLIT.search(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", home_html)))
        pm = self.SPLIT.search(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", press_html)))
        if not hm or not pm:
            missing = "home page" if not hm else "press page"
            return di._out(di.FAIL, unexplained + (
                f". The {missing} does not print the sentence reconciling the two, so "
                f"a reader on it has no way to reach the other figure"), observed=hero)
        if hm.group(0) != pm.group(0):
            return di._out(di.FAIL, unexplained + (
                ". The two pages print DIFFERENT reconciling sentences, so at least "
                "one of them is stating a relationship that does not hold"),
                observed=hero)

        # (4) and the subtraction on the page has to be the real one.
        said_to_date = int(hm.group(1).replace(",", ""))
        said_later = int(hm.group(2).replace(",", ""))
        said_total = int(hm.group(4).replace(",", ""))
        if (said_to_date != press or said_total != hero
                or said_later != gap or said_to_date + said_later != said_total):
            return di._out(di.FAIL, unexplained + (
                f". The reconciling sentence does not add up: it says {said_to_date:,} "
                f"+ {said_later:,} = {said_total:,}, against a press figure of "
                f"{press:,}, a home figure of {hero:,} and a real gap of {gap:,}"),
                observed=hero)

        return di._out(di.PASS,
                       f"home {hero:,} and press {press:,} are two correct periods and "
                       f"both pages print the same reconciliation, verified against the "
                       f"API: {press:,} taken effect + {said_later:,} filed for later "
                       f"effective dates = {hero:,} for the calendar year")

    @staticmethod
    def _status_map(blob):
        out = {}
        if isinstance(blob, dict):
            src = blob.get("sources") if isinstance(blob.get("sources"), dict) else blob
            for k, v in (src or {}).items():
                if isinstance(v, dict) and "status" in v:
                    out[k] = str(v.get("status") or "").lower()
        elif isinstance(blob, list):
            for v in blob:
                if isinstance(v, dict) and v.get("source"):
                    out[v["source"]] = str(v.get("status") or "").lower()
        return out

    @staticmethod
    def _press_headline(html, ctx):
        """The press page's own YTD verified total, from its quotable sentence."""
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
        year = str(ctx.today.year)
        pats = (
            r"verified ([\d,]+) job cuts worldwide in " + year,
            r"For " + year + r" so far, ([\d,]+) job cuts are documented worldwide",
        )
        for p in pats:
            m = re.search(p, text, re.I)
            if m:
                return int(m.group(1).replace(",", ""))
        return None


# ---------------------------------------------------------------------------
# 6. COMPARISON BASIS
# ---------------------------------------------------------------------------
class ComparisonBasisInvariant:
    """Where we compare our figure to an outside estimate, the reader can see why.

    Two things have to hold and they fail independently.

    FIRST, the explanation has to EXIST and be accurate. It does exist, it is
    deliberately written without naming anyone, and that framing is a standing
    rule: the public wording is "the US national survey" or "an independent
    national estimate", never a publisher.

    SECOND, and this is what actually broke, it has to be SEEN. An explanation
    sealed inside a collapsed disclosure is not an explanation, it is a defence
    the reader never encounters before they have already decided our number
    contradicts the one they arrived with. This codebase shipped a chart caveat
    that computed to display:none at 0x0 and no reader ever saw it.

    WHAT THIS CHECK MEASURES, AND WHY NOT PIXELS. An earlier version of this
    docstring cited a browser measurement finding the explainer panels "0 and 4
    pixels wide". That measurement was wrong and the citation is removed rather
    than softened. Re-run in a real browser at 1280px, a CLOSED <details> keeps a
    full 1127x309 layout box — the summary row and the panel's own padding are
    laid out whether or not the panel is open — and the 0/4 readings came from a
    viewport whose own clientWidth was 0, so the probe was measuring nothing at
    all. A width probe cannot distinguish an open panel from a sealed one, which
    means the geometry was never the signal.

    The two signals that DO discriminate, and that this check asserts:

      OPEN      a <details> without the `open` attribute is a collapsed
                disclosure by definition, in every browser, with no styling
                involved. This is decidable from the served HTML.
      TEXT      how much explanation is actually reachable, in characters of
                rendered text with the summary excluded. The pre-fix page put 0
                chars in front of the reader; the fixed one puts thousands. A
                panel that is open but empty is the same defect wearing the right
                attribute, and the character count is what catches it.

    A FALSE POSITIVE IS A DEFECT IN THE CHECK. This check also spent a day
    failing a page whose explainer was open and 5,094 characters long, because a
    loose marker ("documented floor") also occurs inside a routine FAQ accordion,
    and ANY closed panel containing ANY marker was reported as the explainer being
    sealed. A collapsed FAQ item is a working FAQ item. So existence is tested
    with the broad markers and VISIBILITY is tested only against the panel that
    carries the explainer itself.
    """

    key = "comparison_basis_is_visible"
    label = "The 'why our number differs' explanation is visible"
    reads_live_data = True

    # Phrases that mark the name-free explainer. No publisher is named here
    # and none may be: the public framing is "the US national survey".
    MARKERS = (
        "why our number is lower",
        "why our numbers differ",
        "documented floor",
    )
    # The subset that identifies the EXPLAINER ITSELF rather than any passage
    # that happens to use the same vocabulary. "documented floor" is a phrase the
    # FAQ uses in passing; the two below are the explainer's own title.
    EXPLAINER_MARKERS = (
        "why our number is lower",
        "why our numbers differ",
    )
    # Characters of rendered text, summary excluded, below which an "open" panel
    # is not actually explaining anything. The real explainer runs to about five
    # thousand; the defect this replaces put zero in front of the reader.
    MIN_TEXT = 500

    def run(self, ctx):
        di = _di()
        html, err = _get_html(ctx, HOME_URL)
        if html is None:
            ctx.errors[self.key] = err
            return di.Result(self, di.UNKNOWN, error=err,
                             detail=_why_unreachable(err) + " — the explainer was NOT checked")

        per = []
        low = html.lower()

        # DID WE ACTUALLY GET THE PAGE? Every other check in this module answers
        # UNKNOWN when the served body is not readable as the tracker page — a
        # figure "not found in the served page" is explicitly NOT a pass and
        # explicitly not a FAIL either. This one alone had no such anchor, so any
        # 200 that was not the page (a proxy interstitial, a cached error body, a
        # bare `{}`) read as "the explainer is missing" and reported a defect in
        # the page rather than a failure to read it. That is a FALSE FAIL, and a
        # guard that cries wolf on a captive-portal response is a guard that gets
        # muted. The anchor is the hero element the page cannot render without.
        sl = _Slice("page_was_served", "the served body is the tracker home page")
        if "alt-hero-total" not in low:
            per.append((sl, di._out(di.UNKNOWN,
                        "the body served for the home page does not contain the "
                        "hero element, so this is not the tracker page and the "
                        "explainer was NOT checked")))
            return di._roll_up(self, ctx, per)

        sl = _Slice("explainer_exists", "the explainer exists on the home page")
        found = [m for m in self.MARKERS if m in low]
        # Existence turns on the explainer's OWN title, not on the vocabulary it
        # shares with the FAQ. A page whose only match is "documented floor" in a
        # FAQ answer has not explained why our figure differs; it has used a
        # phrase. The broader list is still reported, because what was found is
        # useful in the detail line.
        if not any(m in low for m in self.EXPLAINER_MARKERS):
            per.append((sl, di._out(di.FAIL,
                        "the home page carries no explanation of why our figure "
                        "differs from a national estimate. A reader comparing two "
                        "numbers is left to assume ours is wrong")))
            return di._roll_up(self, ctx, per)
        per.append((sl, di._out(di.PASS,
                    f"found: {', '.join(found)}")))

        sl = _Slice("explainer_visible", "the explainer is not sealed in a collapsed panel")
        panels = self._explainer_panels(html)
        open_panels = [p for p in panels if p["open"]]
        readable = [p for p in open_panels if p["chars"] >= self.MIN_TEXT]

        if not panels:
            # Outside a <details> entirely: nothing to open, nothing to seal.
            per.append((sl, di._out(di.PASS,
                        "the explainer is not inside a disclosure panel at all, so "
                        "there is nothing for a reader to open")))
            per.append((_Slice("explainer_text", "the explainer has text to read"),
                        di._out(di.UNKNOWN,
                                "the explainer is not in a panel this check can bound, "
                                "so its rendered length is NOT measured here")))
            return di._roll_up(self, ctx, per)

        if not open_panels:
            names = "; ".join(f'"{p["summary"]}"' for p in panels)
            per.append((sl, di._out(di.FAIL,
                        f"the explanation of why our figure differs from a national "
                        f"estimate is sealed inside a collapsed disclosure the reader "
                        f"must click to open: {names}. A <details> with no `open` "
                        f"attribute starts closed, so its {panels[0]['chars']:,} "
                        f"characters of explanation reach nobody who does not click")))
        else:
            per.append((sl, di._out(di.PASS,
                        f'"{open_panels[0]["summary"]}" carries the `open` attribute, '
                        f"so the explanation is on screen without a click")))

        # RENDERED TEXT LENGTH, which is the signal a width probe cannot give.
        sl = _Slice("explainer_text", "the explainer has text to read without clicking")
        if not open_panels:
            per.append((sl, di._out(di.FAIL,
                        "0 characters of the explanation are readable without opening "
                        "a panel")))
        elif not readable:
            per.append((sl, di._out(di.FAIL,
                        f"the open explainer holds only "
                        f"{max(p['chars'] for p in open_panels):,} characters of text, "
                        f"below the {self.MIN_TEXT:,} an actual explanation needs — an "
                        f"open but empty panel is the same defect with the right "
                        f"attribute")))
        else:
            per.append((sl, di._out(di.PASS,
                        f"{max(p['chars'] for p in readable):,} characters of "
                        f"explanation are readable without a click")))

        return di._roll_up(self, ctx, per)

    def _explainer_panels(self, html):
        """Every <details> carrying the explainer itself, with open state and size.

        Matched on EXPLAINER_MARKERS, not MARKERS: a collapsed FAQ item that uses
        the phrase "documented floor" in passing is a working FAQ item, and
        failing the page for it is the false positive this method exists to end.
        """
        out = []
        for m in re.finditer(r"<details\b([^>]*)>(.*?)</details>", html, re.S | re.I):
            attrs, body = m.group(1), m.group(2)
            if not any(k in body.lower() for k in self.EXPLAINER_MARKERS):
                continue
            label = re.search(r"<summary[^>]*>(.*?)</summary>", body, re.S | re.I)
            inner = re.sub(r"<summary[^>]*>.*?</summary>", "", body,
                           flags=re.S | re.I)
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()
            out.append({
                "open": bool(re.search(r"\bopen\b", attrs, re.I)),
                "chars": len(text),
                "summary": (re.sub(r"\s+", " ",
                                   re.sub(r"<[^>]+>", "", label.group(1))).strip()
                            if label else "(unnamed panel)"),
            })
        return out


# ---------------------------------------------------------------------------
# What data_integrity.py adds to its own registry.
# ---------------------------------------------------------------------------
FIGURE_INVARIANTS = (
    FigureAgreementInvariant(),
    FigureReconciliationInvariant(),
    DrillDownInvariant(),
    BasisDisclosureInvariant(),
    CrossSurfaceAgreementInvariant(),
    ComparisonBasisInvariant(),
)
