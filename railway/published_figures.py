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


def _home_params(ctx):
    """Exactly what the unfiltered home page sends. Nothing more, nothing less.

    The page's own currentParams() defaults to the current year and no other
    filter. A check that added `sourced=1` or `exclude_supersets=1` here would be
    checking a query no reader ever issues, and would agree with itself."""
    return {"years": _year(ctx)}


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


class _Slice:
    """_roll_up() wants something with .label and .name. This is that."""

    def __init__(self, key, label):
        self.name = key
        self.label = label


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

    WHY IT IS NOT SELF-AGREEING. Each figure's params come from FIGURES, stamped
    from the page's own defaults, not re-derived here from what the figure "ought"
    to mean. A checker that recomputed the query from an assumption would agree
    with its own assumption and pass while the page was wrong.
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

        payload, err = _get_json(ctx, "aggregate", _home_params(ctx))
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
    OVERLAP_DISCLOSURES = (
        "can carry more than one",
        "more than one reason",
        "slices overlap",
        "overlap, so they do not sum",
        "do not sum to",
        "adds up to more than",
        "counted under each",
    )

    def run(self, ctx):
        di = _di()
        params = _home_params(ctx)
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

        # --- reasons doughnut: overlap allowed, unbounded overlap is not
        reasons = payload.get("reasons") or []
        sl = _Slice("reasons", "reasons doughnut vs its own basis")
        if not reasons:
            per.append((sl, di._out(di.UNKNOWN,
                        "the live response carried no reasons block — the doughnut "
                        "is NOT being reconciled")))
        else:
            s = sum(_i(r[1]) for r in reasons if len(r) > 1)
            # RECONCILE AGAINST THE BASIS THE PAGE STATES, NOT THE ONE THE CHART
            # HAPPENS TO USE. This distinction is the whole check. The doughnut is
            # computed over ALL jobs while every tile around it, and the headline
            # above it, publish the verified basis. Measuring the slices against
            # the all-jobs figure would "reconcile" them against a number the page
            # never shows, and the check would agree with the defect instead of
            # catching it — the exact self-agreeing failure this module exists to
            # prevent. The reader's arithmetic starts at the headline, so the
            # check starts there too.
            ratio = (s / float(verified)) if verified else 0.0
            disclosed = bool(html) and any(d in html.lower()
                                           for d in self.OVERLAP_DISCLOSURES)
            if s == verified:
                per.append((sl, di._out(di.PASS,
                            f"{len(reasons)} slices sum exactly to the {verified:,} "
                            f"headline")))
            elif not disclosed:
                per.append((sl, di._out(di.FAIL,
                            f"the doughnut slices sum to {s:,} but the headline they "
                            f"sit beside publishes {verified:,} ({ratio:.2f}x), and the "
                            f"card does not say why. A reader adding up the slices "
                            f"lands {s - verified:+,} away from the published number. "
                            f"Either reconcile the slices to the headline basis or "
                            f"state on the card that a cut can carry more than one "
                            f"reason",
                            observed=s)))
            elif s < verified:
                per.append((sl, di._out(di.FAIL,
                            f"the doughnut slices sum to {s:,}, BELOW the verified "
                            f"headline of {verified:,} — overlap can only push a sum "
                            f"UP, so slices are dropping rows",
                            observed=s)))
            else:
                per.append((sl, di._out(di.PASS,
                            f"{len(reasons)} slices sum to {s:,} ({ratio:.2f}x of the "
                            f"{verified:,} headline) and the card discloses the "
                            f"overlap")))

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
        params = _home_params(ctx)
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

        per = []
        skipped = []
        for row in reasons:
            if len(row) < 2:
                continue
            tag, shown = row[0], _i(row[1])
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
        if skipped:
            res.detail += f" [not checked, below floor: {'; '.join(skipped)}]"
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

    PERIOD_WORDS = ("ytd", "year to date", "this year", "all time", "trailing",
                    "last 12", "so far")
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
        m = re.search(r'class=["\']alt-hero-figure-label["\'][^>]*>(.*?)</span>\s*<span',
                      html, re.S)
        if not m:
            m = re.search(r'class=["\']alt-hero-figure-label["\'][^>]*>(.*?)</span>',
                          html, re.S)
        if not m:
            per.append((sl, di._out(di.UNKNOWN,
                        "the hero label was not found in the served page — its basis "
                        "is NOT being checked")))
        else:
            text = re.sub(r"<[^>]+>", " ", m.group(1))
            text = re.sub(r"\s+", " ", text).strip().lower()
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

    Both pages describe their figure as verified job cuts, worldwide, for the
    year to date. That is one claim. It has one right answer.

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
            ctx.errors[self.key] = e
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
                if gap > max(1, hero * self.TOLERANCE):
                    per.append((sl, di._out(di.FAIL,
                                f"the home page publishes {hero:,} verified job cuts "
                                f"for the year and the press page publishes "
                                f"{press:,} for the same claim — a gap of {gap:,}. "
                                f"A journalist reading both gets two answers",
                                observed=hero)))
                else:
                    per.append((sl, di._out(di.PASS,
                                f"home {hero:,} and press {press:,} agree")))

        # --- retired collectors: two endpoints, one truth
        sl = _Slice("retired_collectors", "retired collectors are not published as live")
        health, herr2 = _get_json(ctx, "source-health", {})
        quality, qerr = _get_json(ctx, "quality-status", {})
        if health is None or quality is None:
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
    that computed to display:none at 0x0 and no reader ever saw it. A measurement
    of THIS page, taken with a real browser on 2026-08-04, found the same shape:
    the differences explainer sits inside <details> elements that are closed by
    default and measure 0 and 4 pixels wide.

    WHAT THIS CHECK CAN AND CANNOT DO UNATTENDED. It is stdlib-only in a runner
    with no browser, so it cannot compute a style. What it CAN decide from the
    served HTML, and what is sufficient to catch this defect, is whether the
    explainer is sealed inside a <details> that has no `open` attribute. That is
    a collapsed disclosure by definition. The stronger claim — that the visible
    box has non-zero area — is reported UNKNOWN by this module rather than
    quietly assumed, and is named as such in the report.
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

    def run(self, ctx):
        di = _di()
        html, err = _get_html(ctx, HOME_URL)
        if html is None:
            ctx.errors[self.key] = err
            return di.Result(self, di.UNKNOWN, error=err,
                             detail=_why_unreachable(err) + " — the explainer was NOT checked")

        per = []
        low = html.lower()

        sl = _Slice("explainer_exists", "the explainer exists on the home page")
        found = [m for m in self.MARKERS if m in low]
        if not found:
            per.append((sl, di._out(di.FAIL,
                        "the home page carries no explanation of why our figure "
                        "differs from a national estimate. A reader comparing two "
                        "numbers is left to assume ours is wrong")))
            return di._roll_up(self, ctx, per)
        per.append((sl, di._out(di.PASS,
                    f"found: {', '.join(found)}")))

        sl = _Slice("explainer_visible", "the explainer is not sealed in a collapsed panel")
        sealed = []
        for m in re.finditer(r"<details\b([^>]*)>(.*?)</details>", html, re.S | re.I):
            attrs, body = m.group(1), m.group(2).lower()
            if any(k in body for k in self.MARKERS):
                if not re.search(r"\bopen\b", attrs, re.I):
                    label = re.search(r"<summary[^>]*>(.*?)</summary>", m.group(2),
                                      re.S | re.I)
                    name = (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", label.group(1))).strip()
                            if label else "(unnamed panel)")
                    sealed.append(name)
        if sealed:
            per.append((sl, di._out(di.FAIL,
                        "the explanation of why our figure differs from a national "
                        "estimate is sealed inside a collapsed disclosure the reader "
                        "must click to open: "
                        + "; ".join(f'"{s}"' for s in sealed)
                        + ". A rendered measurement on 2026-08-04 confirmed these "
                          "panels compute to 0 and 4 pixels wide")))
        else:
            per.append((sl, di._out(di.PASS,
                        "the explainer is not inside a closed disclosure")))

        # The area measurement itself is honestly out of reach from here.
        per.append((_Slice("explainer_area", "the explainer has non-zero rendered area"),
                    di._out(di.UNKNOWN,
                            "computing rendered width and height needs a browser; this "
                            "runner has none, so NON-ZERO AREA IS NOT VERIFIED HERE "
                            "(the closed-disclosure check above is what runs unattended)",
                            pending=False)))

        return di._roll_up(self, ctx, per)


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
