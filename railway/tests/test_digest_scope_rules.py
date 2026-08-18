"""Every figure in the digest names the window it covers, and where it counts.

WHAT WENT WRONG, AND WHY A REVIEW WOULD NOT HAVE CAUGHT IT.

The first live digest, 16 August 2026, printed a period total, then a
year-to-date total, then a country breakdown scoped to the PERIOD directly
underneath the YEAR figure. The arithmetic was right in every line. The email
was still wrong, because the country block stated no window of its own and
adjacency supplied one, and the block adjacent to it was the year. The owner
read it as a breakdown of 508,254 and asked whether the maths was broken.

Adjacency is the wrong mechanism, and not only in that one arrangement. It
fails when somebody quotes a line, forwards a fragment, or reads on a phone
narrow enough that the visual grouping stops being visible. So the property
these tests hold is:

    A LINE OF THIS EMAIL, LIFTED OUT ON ITS OWN, IS STILL TRUE AND STILL
    SAYS WHAT IT COVERS.

The second fault in the same section was fixed prose around variable data. The
country block always ended "so the list does not add up to the total above",
including on the send where it added up exactly. A caveat that is false
whenever the data is clean is worse than no caveat: it is only ever read by
the person who checked, and it tells them we did not.

WHAT IS ENFORCED HERE, AND WHAT IS NOT.

Enforced: every UNINDENTED line of the plain-text part that states a data
figure carries a four-digit year. Indented lines are table rows, and a row is
exempt only because the caption immediately above it is checked to carry one.

NOT enforced: the same rule per SENTENCE. Two sentences in the section state a
figure and take their window from the sentence beside them inside the same
short note, and forcing a date into every clause produced copy nobody would
read. That is a real gap, it is named here rather than papered over, and the
line is the unit a reader actually quotes or screenshots.

THE FOURTH DIMENSION, ADDED 2026-08-17 BECAUSE IT WAS MISSING FROM THE FIRST
THREE.

The redesign named four things a figure has to state: the timeframe, the tier
(verified or announced), the date basis, and the geography. Three of them
reached the headline. The delivered email of 2026-08-16 read:

    Verified job cuts
    13,658
    10 to 17 August 2026, counted by the date the cuts take effect.

The owner's question was one word long: where. Nothing in that block answers
it. The country table further down said "counted where the jobs were rather
than where the employer is based", but that qualifier belonged to the table,
and a reader who lifts the 13,658 carries none of it.

Measured before the fix, on the live week: 13,658 verified job cuts, of which
8,989 sit on entries carrying a country and 4,669 do not. The composer sends
no `country` parameter, so alt_db_where applies no country clause at all. The
figure is worldwide, and it is worldwide in a way that includes entries whose
country we do not hold. Both halves of that go in the sentence, and the second
half is MEASURED per send rather than written down once: a window where every
verified cut carries a country must not claim otherwise.

The composers are PHP, so this drives them through
tests/fixtures/digest_compose_harness.php against fixture payloads whose tuple
shapes were copied from a live /aggregate response. Without php on PATH the
tests SKIP, which is not a pass.
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

# A four-digit year is the scope token. Every window this email can describe
# is rendered with one, whether it is a range, a single day, or "YTD 2026".
YEAR = re.compile(r"\b(19|20)\d{2}\b")

# A data figure: a number wearing the unit it counts. This is deliberately
# narrower than "any digit". "3 of the 5 companies listed" is a fact about the
# list on screen, not a measurement, and demanding a date inside it would buy
# nothing a reader wants.
FIGURE = re.compile(
    r"\b\d[\d,]*\s+(job cuts|jobs|entries|companies|signals)\b", re.I)


def _tuple(label, all_jobs, verified_jobs):
    """The shape /aggregate returns for top_* rows, column order and all.

    [label, all_jobs, ai_jobs, display_label, verified_jobs, ai_verified_jobs]

    Copied rather than invented, because column [4] being the verified tier
    while the endpoint SORTS on column [1] is the bug this shape exists to
    keep catching.
    """
    return [label, all_jobs, 0, None, verified_jobs, 0]


def layoff_fixture(**over):
    data = {
        "from": "2026-08-09",
        "to": "2026-08-16",
        "compose": "layoff",
        "layoff": {
            "totals": {
                "jobs": 16726, "entries": 74,
                "announced_jobs": 3016, "announced_entries": 5,
                "ai_verified_jobs": 0, "ai_verified_entries": 0,
                "companies": 71,
            },
            "leaders": [
                {"company_name": "Applied Aerospace", "job_count": 4320,
                 "layoff_date": "2026-08-12", "ai_explicit": False,
                 "location": "",
                 "permalink": "https://asktherecruiter.com/blog/layoff/applied-2026-08-12/",
                 "announced": False},
                # ANNOUNCED, and the second biggest cut of the week. This is
                # the live shape of 2026-08-17 and the reason the tier had to
                # reach the row: 2,500 of these is not inside the verified
                # headline the table sits under.
                {"company_name": "Paramount Skydance", "job_count": 2500,
                 "layoff_date": "2026-08-11", "ai_explicit": True,
                 "location": "CA", "permalink": "", "announced": True},
            ],
            # United States is NOT first by the verified column, on purpose.
            "top_countries": [
                _tuple("Multiple countries", 2501, 1),
                _tuple("United States", 7862, 7862),
                _tuple("Brazil", 476, 476),
            ],
            # The live composition of 2026-08-17, which is the point: an AI
            # layoff tracker whose week is aerospace, food and retail, with
            # Technology ninth. Deliberately NOT in verified order, because
            # the endpoint sorts on the announced-inclusive column.
            "top_industries": [
                _tuple("Media & Entertainment", 2746, 75),
                _tuple("Aerospace & Defense", 4320, 4320),
                _tuple("Food & Hospitality", 2600, 2474),
                _tuple("Retail & E-commerce", 1900, 1864),
                _tuple("Logistics & Transport", 1000, 995),
                _tuple("Healthcare & Pharma", 900, 866),
                _tuple("Manufacturing", 900, 843),
                _tuple("Energy", 500, 476),
                _tuple("Finance & Insurance", 400, 310),
                _tuple("Technology", 300, 247),
                _tuple("Education", 200, 173),
            ],
            "source_types": [
                _tuple("warn", 6060, 6060),
                _tuple("8K", 4940, 4940),
                _tuple("news", 5726, 2710),
            ],
        },
        "ytd": {
            "totals": {"jobs": 971602, "announced_jobs": 463348,
                       "ai_verified_jobs": 42253},
            # The year window has its own country split, so its own headline
            # gets its own measured geography clause. Sharing the period's
            # would be the adjacency fault again, one dimension over.
            "top_countries": [
                _tuple("United States", 402000, 300000),
                _tuple("Multiple countries", 60000, 40000),
            ],
        },
    }
    data.update(over)
    return data


def talent_fixture(**over):
    """The talent section's shape. The harness routes /talent/ requests by
    `since`, so ONE fixture answers both the aggregate and the query call:
    they read different keys off it."""
    data = {
        "from": "2026-08-09",
        "to": "2026-08-16",
        "compose": "talent",
        "talent": {
            "total": 1332, "companies": 1281, "verified": 568,
            "countries": 84,
            # Deliberately in the order the endpoint returns, which is
            # materiality then RECENCY, and deliberately the wrong order for a
            # reader: the 2,200-job signal is third and an unreadable headline
            # is second. That is the live shape of the week to 2026-08-16.
            "rows": [
                {"company": "Concentrix", "headline": "rolls out matched PERA",
                 "published_date": "2026-08-16", "headcount": None},
                # Latin letters are a quarter of this, and "True Customer Day"
                # is why a "contains any Latin" test was not enough.
                {"company": "\u0e17\u0e23\u0e39",
                 "headline": "\u0e17\u0e23\u0e39\u0e2a\u0e48\u0e07\u0e1e\u0e25\u0e31\u0e07"
                             "\u0e1e\u0e19\u0e31\u0e01\u0e07\u0e32\u0e19 "
                             "\u0e04\u0e34\u0e01\u0e2d\u0e2d\u0e1f True Customer Day 2026",
                 "published_date": "2026-08-15", "headcount": 2000},
                {"company": "Sanad Service Centres",
                 "headline": "create more than 2,200 jobs",
                 "published_date": "2026-08-14", "headcount": 2200},
                {"company": "Sudamericana de L\u00e1cteos",
                 "headline": "vuelve a abrir sus puertas tras seis meses",
                 "published_date": "2026-08-13", "headcount": 80},
                {"company": "Northwind", "headline": "opens a Dublin hub",
                 "published_date": ""},
            ],
        },
        "talent_ytd": {"total": 41880, "companies": 20114, "verified": 9902,
                       "countries": 141},
    }
    data.update(over)
    return data


def compose(fixture):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(fixture, handle)
        path = handle.name
    try:
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, path],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    if run.returncode != 0:
        raise AssertionError(f"the harness failed: {run.stderr[:2000]}")
    return json.loads(run.stdout)


# A headline figure: the three-line stat block the sections open and close
# with, in either body part. In HTML it is marked; in text it is the lede
# shape, a count wearing its noun at the start of the line.
SCOPE_P = re.compile(r"<p data-alt=\"scope\">(.*?)</p>", re.S)
LEDE = re.compile(r"^[\d,]+ (?:verified job cuts|new hiring signals"
                  r"|hiring signals), (.*)$")

# The word that answers "where". One token, checked in both parts, so a
# rewrite that drops it from one of them fails rather than half-ships.
GEO = "worldwide"


@unittest.skipIf(PHP is None, "php is not on PATH, so the composers could not "
                              "be run. UNKNOWN, not a pass.")
class NoHeadlineFigureLeavesItsGeographyToBeInferred(unittest.TestCase):
    """The defect the owner found by reading the delivered email: the headline
    stated its window, its tier and its date basis, and not where on earth it
    counted. "Where? USA or world or what" is the whole bug report."""

    def _headlines(self, section):
        """Every headline figure's own scope sentence, from BOTH parts."""
        html = [re.sub(r"<[^>]+>", "", m) for m in SCOPE_P.findall(section["html"])]
        text = [m.group(1) for m in
                (LEDE.match(l) for l in section["text"].splitlines()) if m]
        self.assertTrue(html, "the section emitted no scope line at all")
        self.assertEqual(len(html), len(text),
                         "the two body parts carry different numbers of "
                         "headline figures, so one of them is unscoped")
        return html + text

    def test_the_layoff_headlines_say_where_they_count(self):
        for scope in self._headlines(compose(layoff_fixture())):
            self.assertIn(GEO, scope,
                          f"this headline figure states its window and its "
                          f"date basis and never says where on earth it "
                          f"counts: {scope!r}")

    def test_the_talent_headlines_say_where_they_count(self):
        for scope in self._headlines(compose(talent_fixture())):
            self.assertIn(GEO, scope,
                          f"this headline figure states its window and its "
                          f"date basis and never says where on earth it "
                          f"counts: {scope!r}")

    def test_the_ai_figure_says_where_it_counts(self):
        """It is the one figure this tracker is named after, and it is a line
        somebody quotes on its own more often than any other."""
        text = compose(layoff_fixture())["text"]
        ai = [l for l in text.splitlines() if "AI attribution" in l]
        self.assertTrue(ai, "the measured-zero AI sentence went missing")
        self.assertIn(GEO, ai[0], f"the AI figure names no geography: {ai[0]!r}")

        fixture = layoff_fixture()
        fixture["layoff"]["totals"]["ai_verified_jobs"] = 900
        fixture["layoff"]["totals"]["ai_verified_entries"] = 3
        text = compose(fixture)["text"]
        ai = [l for l in text.splitlines() if "Attributed to AI" in l]
        self.assertTrue(ai, "the real AI sentence went missing")
        self.assertIn(GEO, ai[0], f"the AI figure names no geography: {ai[0]!r}")

    def test_worldwide_is_not_allowed_to_do_quiet_work(self):
        """The figure is worldwide only because no country filter is sent, and
        on the live week 4,669 of 13,658 verified cuts sat on entries carrying
        no country at all. A bare "worldwide" would imply a placed total."""
        scopes = self._headlines(compose(layoff_fixture()))
        self.assertTrue(
            all("no country recorded" in s for s in scopes),
            "the fixture's countries fall short of the headline, so every "
            "headline has to say the total includes entries we cannot "
            f"place: {scopes!r}")

    def test_a_window_where_every_cut_is_placed_claims_nothing_more(self):
        """Fixed prose around variable data, one dimension over. If the
        countries account for the whole headline, the caveat is false."""
        fixture = layoff_fixture()
        verified = (fixture["layoff"]["totals"]["jobs"]
                    - fixture["layoff"]["totals"]["announced_jobs"])
        fixture["layoff"]["top_countries"] = [
            _tuple("United States", verified, verified)]
        section = compose(fixture)
        period = section["text"].split("\nYTD 2026")[0]
        self.assertIn(GEO, period.splitlines()[1])
        self.assertNotIn("no country recorded", period,
                         "every verified cut in this window carries a "
                         "country and the email still told the reader some "
                         "of them do not")


@unittest.skipIf(PHP is None, "php is not on PATH, so the composers could not "
                              "be run. UNKNOWN, not a pass.")
class EveryFigureNamesItsWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.section = compose(layoff_fixture())
        cls.text = cls.section["text"]
        cls.html = cls.section["html"]

    def test_no_unindented_figure_line_leaves_its_window_to_be_inferred(self):
        offenders = []
        for line in self.text.splitlines():
            if not line.strip() or line[:1].isspace():
                continue
            if FIGURE.search(line) and not YEAR.search(line):
                offenders.append(line)
        self.assertEqual(offenders, [],
                         "these lines state a figure and no window, so their "
                         "meaning comes from whatever happens to sit above "
                         "them:\n" + "\n".join(offenders))

    def test_every_indented_row_sits_under_a_caption_that_names_the_window(self):
        """A table row is the one exempt shape, and this is what it is exempt
        BECAUSE of. If the caption ever loses its date the rows lose theirs."""
        lines = self.text.splitlines()
        caption = None
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            if not line[:1].isspace():
                caption = line
                continue
            if not FIGURE.search(line):
                continue
            self.assertIsNotNone(caption, f"row {line!r} has nothing above it")
            self.assertRegex(caption, YEAR,
                             f"the row {line.strip()!r} is scoped only by the "
                             f"caption {caption.strip()!r}, which names no window")

    def test_the_period_and_the_year_are_never_two_bare_totals(self):
        """The exact confusion the owner hit: a period figure and a year
        figure with nothing between them saying which is which."""
        self.assertIn("9 to 16 August 2026", self.text)
        self.assertIn("1 January to 16 August 2026", self.text)

    def test_the_year_to_date_block_comes_last(self):
        """It used to sit above a period-scoped country list. Every figure
        names itself now, so this is belt and braces, but the belt is cheap."""
        self.assertLess(self.text.index("Where the jobs were"),
                        self.text.index("YTD 2026"))
        self.assertLess(self.text.index("Which industries"),
                        self.text.index("YTD 2026"))

    def test_the_basis_and_the_tier_travel_with_the_headline(self):
        lede = self.text.splitlines()[1]
        self.assertIn("verified job cuts", lede)
        self.assertIn("9 to 16 August 2026", lede)
        self.assertIn("counted by the date the cuts take effect", lede)

    def test_the_geography_basis_is_attached_to_the_geography_block(self):
        block = self.text.split("Where the jobs were")[1]
        caption = block.strip().splitlines()[0]
        self.assertIn("where the jobs were rather than", caption)
        self.assertRegex(caption, YEAR)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class NoFixedProseAroundVariableData(unittest.TestCase):
    """A caveat is printed when it is true and not when it is not, and when it
    is true it says by how much."""

    def test_a_list_that_reconciles_exactly_carries_no_caveat(self):
        """The send that started this: the countries added up, and the email
        said they did not."""
        fixture = layoff_fixture()
        # One country, holding every verified job cut in the window.
        verified = (fixture["layoff"]["totals"]["jobs"]
                    - fixture["layoff"]["totals"]["announced_jobs"])
        fixture["layoff"]["top_countries"] = [
            _tuple("United States", verified, verified)]
        text = compose(fixture)["text"]
        # This block only. The industry list in the same fixture genuinely
        # falls short, and it SHOULD still carry its shortfall.
        block = text.split("Where the jobs were")[1].split("\nWhich industries")[0]
        self.assertIn("United States", block)
        self.assertNotIn("These lines cover", block,
                         "the list reconciles exactly and the email still "
                         "told the reader it does not")
        self.assertNotIn("does not add up", text)
        self.assertIn("These lines cover", text,
                      "the industry list falls short in this fixture, so the "
                      "shortfall must still be stated somewhere")

    def test_a_list_that_falls_short_says_by_exactly_how_much(self):
        text = compose(layoff_fixture())["text"]
        self.assertIn("These lines cover 8,339 of the 13,710 verified job cuts",
                      text)
        self.assertIn("5,371 are on entries with no country recorded", text)

    def test_the_ranked_lists_are_sorted_by_the_column_they_print(self):
        """The endpoint sorts on the announced-inclusive column and this block
        prints the verified one, so the rows have to be re-sorted. Otherwise a
        list titled "the largest" is not ordered by the number beside it."""
        text = compose(layoff_fixture())["text"]
        block = text.split("Which industries")[1].split("Where these came")[0]
        rows = [l for l in block.splitlines() if l[:1].isspace() and ":" in l]
        self.assertIn("Aerospace & Defense", rows[0],
                      "the industry list is still in the endpoint's order, "
                      "which is a different tier than the one printed")
        values = [int(re.search(r"([\d,]+) jobs", r).group(1).replace(",", ""))
                  for r in rows]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_one_job_is_not_one_jobs(self):
        text = compose(layoff_fixture())["text"]
        self.assertIn("Multiple countries, no split given: 1 job\n", text)

    def test_a_measured_zero_on_the_ai_figure_is_stated_not_hidden(self):
        """On an AI tracker "none this week" is the answer a reader came for,
        and a silent omission leaves them unable to tell it from "not
        checked". This is not the zero-filling the repo bans: the query
        succeeded and the number is real."""
        text = compose(layoff_fixture())["text"]
        self.assertIn("No verified job cuts worldwide in 9 to 16 August 2026 "
                      "carry an explicit AI attribution", text)

    def test_a_real_ai_figure_replaces_that_sentence(self):
        fixture = layoff_fixture()
        fixture["layoff"]["totals"]["ai_verified_jobs"] = 900
        fixture["layoff"]["totals"]["ai_verified_entries"] = 3
        text = compose(fixture)["text"]
        self.assertIn("Attributed to AI by the employer: 900", text)
        self.assertNotIn("carry an explicit AI attribution", text)

    def test_the_entry_page_claim_counts_the_rows_that_actually_link(self):
        """One of the two fixture leaders has no permalink, because a WARN row
        bulk-imported without a post does not get one."""
        text = compose(layoff_fixture())["text"]
        # SINGULAR, since exactly one of the two links. The delivered digest
        # of 2026-08-18 read "1 of the 5 companies listed ... link to an entry
        # page" and the owner named it: a count driving a plural verb is the
        # cheapest way for a citable product to read as machine output.
        self.assertIn("1 of the 2 companies listed for 9 to 16 August 2026 "
                      "links to an entry page", text)

    def test_a_window_it_cannot_date_composes_nothing_at_all(self):
        """A section that cannot say what it covers does not go out."""
        fixture = layoff_fixture(**{"from": "not-a-date"})
        self.assertEqual(compose(fixture), {"null": True})


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheVerifiedTierIsNeverMixed(unittest.TestCase):
    """The site publishes that verified and announced are never mixed. The
    country block read the announced-inclusive column and printed it under a
    verified headline, which on the live week of 2026-08-16 was the difference
    between 2,501 and 1 on a single line."""

    def test_the_country_list_reads_the_verified_column(self):
        text = compose(layoff_fixture())["text"]
        self.assertIn("Multiple countries, no split given: 1 job", text)
        self.assertNotIn("2,501", text,
                         "the block is printing the announced-inclusive tier "
                         "under a verified headline")

    def test_the_headline_is_the_verified_tier_and_says_so(self):
        text = compose(layoff_fixture())["text"]
        self.assertIn("13,710 verified job cuts", text)
        self.assertNotIn("16,726 verified", text)

    def test_the_announced_tier_is_stated_rather_than_dropped(self):
        text = compose(layoff_fixture())["text"]
        self.assertIn("16,726 job cuts across 71 companies", text)
        self.assertIn("Announced cuts are plans companies have stated", text)

    def test_a_window_with_no_announced_rows_says_so_in_words(self):
        fixture = layoff_fixture()
        fixture["layoff"]["totals"]["announced_jobs"] = 0
        fixture["layoff"]["totals"]["announced_entries"] = 0
        text = compose(fixture)["text"]
        self.assertIn("The window holds no announced estimates.", text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheMarkupSaysWhatALineIsAndNotHowItLooks(unittest.TestCase):
    """digest_layout.py owns the design. The composer owns the meaning. A size
    or a colour chosen here is a second place the design can drift."""

    def test_the_composer_picks_no_font_size_and_no_colour(self):
        html = compose(layoff_fixture())["html"]
        for banned in ("font-size", "color:", "font-weight", "padding-left"):
            self.assertNotIn(banned, html,
                             f"the composer chose {banned}, which belongs in "
                             f"digest_layout.py and nowhere else")

    def test_the_variants_it_uses_all_exist_in_the_layout(self):
        sys.path.insert(0, RAILWAY)
        import digest_layout as layout
        html = compose(layoff_fixture())["html"]
        for tag, variant in re.findall(
                r"<(\w+)[^>]*data-alt=\"([^\"]+)\"", html):
            self.assertIn((tag, variant), layout.VARIANT_STYLES,
                          f"the composer marks a line {variant!r} and the "
                          f"layout has no style for it, so it silently falls "
                          f"back to the plain tag")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class AFigureCarriesItsOwnSourcing(unittest.TestCase):
    """A figure that cannot be traced is not a citable figure, and citability
    is what this product is for.

    The provenance sentence existed before this and was in the wrong place:
    at the FOOT of the section, three tables below the headline it explains.
    A reader who screenshots the headline, quotes it, or stops after the
    first screen took the number and left its sourcing behind. That is the
    same adjacency failure the window rules above fix, on the dimension the
    whole product is differentiated by.

    The convention is not ours. ProPublica's news-apps guide asks for sources
    beneath the display of data rather than in a credits block at the bottom;
    Datawrapper asks for the source name and its URL together.
    """

    def test_the_sourcing_sits_under_the_headline_and_not_at_the_foot(self):
        text = compose(layoff_fixture())["text"]
        source = text.index("Where these came from")
        self.assertLess(source, text.index("Biggest cuts"),
                        "the provenance of the headline figure is printed "
                        "below the tables that break it down, so anyone "
                        "quoting the headline leaves the sourcing behind")
        # Directly under it: nothing but the headline's own scope line between.
        head = text[:source].strip().splitlines()
        self.assertEqual(len(head), 2, f"unexpected lines above it: {head}")

    def test_the_sourcing_names_its_window_and_its_tier(self):
        """It is now a headline-level line, so it stands alone like one."""
        line = [l for l in compose(layoff_fixture())["text"].splitlines()
                if l.startswith("Where these came from")][0]
        self.assertIn("9 to 16 August 2026", line)
        self.assertIn("verified only", line)
        self.assertNotIn("above", line,
                         "the shortfall clause still points at a figure that "
                         "is no longer above this line")

    def test_it_reads_the_verified_column_the_headline_counts(self):
        line = [l for l in compose(layoff_fixture())["text"].splitlines()
                if l.startswith("Where these came from")][0]
        self.assertIn("2,710 from named news reports", line)
        self.assertNotIn("5,726", line,
                         "the source split is printing the announced-inclusive "
                         "tier under a verified headline")

    def test_the_layout_owns_the_look_of_the_new_line(self):
        html = compose(layoff_fixture())["html"]
        self.assertIn('data-alt="source"', html)
        sys.path.insert(0, RAILWAY)
        import digest_layout as layout
        self.assertIn(("p", "source"), layout.VARIANT_STYLES)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheEmailCanBeCited(unittest.TestCase):
    """This email is the one surface where the number and its source are
    already separated by the time anybody quotes it.

    Every page we publish is live: a reader who quotes it can re-read it.
    This is a SNAPSHOT. The figures were read once and never move again while
    the database behind them keeps moving. Chicago asks for an access date
    when a source carries no revision date and prefers a last-modified stamp
    where one exists; APA 7 asks for a retrieval date when a source "is
    designed to change over time"; FORCE11 asks for enough specificity to
    identify the exact timeslice. So the block carries all three: the window,
    the read date, and the last-modified stamp.
    """

    @classmethod
    def setUpClass(cls):
        fixture = layoff_fixture()
        fixture["last_updated_label"] = "Aug 17, 2026 · 6:04 AM EDT"
        cls.text = compose(fixture)["text"]
        cls.html = compose(fixture)["html"]

    def test_the_citation_names_the_tracker_the_window_and_a_read_date(self):
        line = [l for l in self.text.splitlines()
                if l.startswith("AI Layoff Tracker, AskTheRecruiter.com")][0]
        self.assertIn("Figures for 9 to 16 August 2026", line)
        # The read date is TODAY, not the window's end: `to` is the last day
        # the figures COVER and this is the day they were pulled. Asserted by
        # shape plus the current UTC year rather than against a computed date,
        # because a run that straddles midnight UTC should not go red for it.
        year = datetime.datetime.now(datetime.timezone.utc).year
        self.assertRegex(line, rf"accessed \d{{1,2}} [A-Z][a-z]+ {year}\.")
        self.assertNotIn("accessed 16 August", line,
                         "the read date is the window's end, so it claims the "
                         "figures were read before the period closed")

    def test_the_citation_url_is_pasteable_text_and_not_a_link(self):
        """Two rules meet here and both are load-bearing.

        It cannot be the counter URL: a citation is a string somebody PASTES,
        and /wp-json/layoffs/v1/click?s=..&l=.. in a published story puts a
        counter in the record instead of our address. It cannot be a bare
        anchor either, which is what the first attempt was:
        test_digest_subscription refuses an uncounted link to a destination
        the digest also links through the counter, because then the count
        means nothing. A reference string is not a control, so it is text.
        """
        cite = self.html.split("Cite this")[1]
        self.assertIn("https://asktherecruiter.com/blog/ai-layoff-tracker/",
                      cite)
        self.assertNotIn("layoffs/v1/click", cite)
        self.assertNotIn("<a ", cite,
                         "the citation URL is an anchor, so it is a third "
                         "uncounted route to a page the digest already links")
        self.assertIn("https://asktherecruiter.com/blog/ai-layoff-tracker/",
                      self.text.split("Cite this")[1])

    def test_the_last_changed_stamp_is_printed_when_the_site_has_one(self):
        self.assertIn("Our database last changed Aug 17, 2026", self.text)

    def test_no_stamp_prints_no_sentence_rather_than_a_guess(self):
        text = compose(layoff_fixture())["text"]
        self.assertNotIn("Our database last changed", text)
        self.assertIn("a recent window is provisional", text,
                      "the provisional warning is true whether or not we can "
                      "date the last write, so it must survive the absence")

    def test_the_provisional_warning_does_not_promise_figures_only_rise(self):
        """Late filings grow a window, and corrections shrink it. The public
        corrections log has a Rhode Island notice that went 9,891 to 2."""
        self.assertIn("a correction can lower it", self.text)

    def test_the_citation_block_is_the_last_thing_in_the_section(self):
        self.assertLess(self.text.index("YTD 2026"),
                        self.text.index("Cite this"))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheEntryLinkClaimIsExact(unittest.TestCase):
    """The composer already counted the rows that link. What it got wrong was
    one word: "no page of their own YET" promises a page that is not coming.
    alt_api_bulk() writes every row with post_id => null, by construction, so
    a notice from the bulk import path never acquires one."""

    def test_it_says_why_a_row_has_no_page_and_does_not_promise_one(self):
        text = compose(layoff_fixture())["text"]
        self.assertIn("arrived through a bulk filing import, which builds no "
                      "page", text)
        self.assertNotIn("no page of their own yet", text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheBiggestCutsTableDeclaresItsTier(unittest.TestCase):
    """The most-read block was the last one still mixing tiers.

    Every other ranked block moved to the verified column when it was found
    they printed the announced-inclusive tier under a verified headline. This
    one could not: db.php's leaders query selected no `announced` column, so
    the composer had no way to tell. Live on 2026-08-17 the SECOND row,
    Paramount Skydance at 2,500, is announced and is not inside the 13,658
    above it. "Verified and announced together" labelled that correctly and it
    was still wrong, because a reader could not see WHICH row to subtract.

    The list is deliberately NOT filtered to verified. It answers "what were
    the biggest cuts this week", and filtering would hide the largest cut of
    the week whenever that cut is an announcement.
    """

    def test_an_announced_row_is_marked_on_the_row(self):
        text = compose(layoff_fixture())["text"]
        row = [l for l in text.splitlines() if "Paramount Skydance" in l][0]
        self.assertIn("announced", row)

    def test_a_verified_row_is_not_marked(self):
        text = compose(layoff_fixture())["text"]
        row = [l for l in text.splitlines() if "Applied Aerospace" in l][0]
        self.assertNotIn("announced", row,
                         "marking both tiers puts a word on every line to "
                         "distinguish a minority")

    def test_the_caption_counts_them_and_says_they_are_outside_the_headline(self):
        text = compose(layoff_fixture())["text"]
        # Singular, for the same reason as the entry-page claim above.
        self.assertIn("1 of these 2 is an announcement, marked below, and sits "
                      "outside the verified figure above", text)

    def test_a_table_with_no_announced_row_says_verified_only(self):
        """Fixed prose again: "verified and announced together" was false on
        every week where the leaders happen to all be verified."""
        fixture = layoff_fixture()
        for leader in fixture["layoff"]["leaders"]:
            leader["announced"] = False
        block = (compose(fixture)["text"].split("Biggest cuts")[1]
                 .split("\nWhere the jobs were")[0])
        self.assertIn("verified only, ranked by job count", block)
        self.assertNotIn("announcements, marked below", block)

    def test_a_payload_without_the_field_reports_unknown_not_none(self):
        """An /aggregate served by a plugin build older than the one that
        added the column returns leaders with no tier. Absence of a signal is
        not a pass, and "verified only" over an announced row would be a worse
        lie than the mixed caption this replaced."""
        fixture = layoff_fixture()
        for leader in fixture["layoff"]["leaders"]:
            leader.pop("announced", None)
        block = (compose(fixture)["text"].split("Biggest cuts")[1]
                 .split("\nWhere the jobs were")[0])
        self.assertIn("This list can include announcements, which sit outside "
                      "the verified figure above", block)
        self.assertNotIn("verified only", block)

    def test_the_basis_caveat_about_the_tracker_page_is_gone(self):
        """It said the page counts on a different basis and would show a
        different total, which made the click meant to PROVE the figure the
        click that contradicted it. The link now carries the window and the
        basis, so the caveat is not merely unnecessary, it is false."""
        text = compose(layoff_fixture())["text"]
        self.assertNotIn("counts by filing date", text)
        self.assertIn("date_basis=effective", text,
                      "the link no longer carries the basis, so the caveat "
                      "should not have been removed")
        self.assertRegex(text, r"[?&]from=2026-08-09")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class ThePeriodIsAllowedToHaveAShape(unittest.TestCase):
    """Every figure in this email states its window, tier, basis and
    geography, and none of them says what it MEANS. This is the one derived
    line, and the discipline is that it is DERIVED: computed from the same
    rows the table above it prints, and silent when the period has no shape
    worth naming. A line that always fires is decoration."""

    def test_it_names_the_three_largest_and_their_share(self):
        text = compose(layoff_fixture())["text"]
        self.assertIn("Aerospace & Defense, Food & Hospitality and Retail & "
                      "E-commerce are the three largest", text)
        self.assertRegex(text, r"are the three largest, \d+% of the [\d,]+ "
                               r"verified job cuts we classified by industry "
                               r"in 9 to 16 August 2026\.")

    def test_it_places_technology_when_technology_is_not_in_the_top_three(self):
        """The documented editorial rule: this is the AI Layoff Tracker, so
        technology is the sector its reader is asking about. It prints the
        real rank and the real share and asserts nothing about expectations."""
        text = compose(layoff_fixture())["text"]
        self.assertIn("Technology is ninth, at 2%.", text)

    def test_it_says_nothing_about_technology_when_technology_leads(self):
        fixture = layoff_fixture()
        fixture["layoff"]["top_industries"] = [
            _tuple("Technology", 9000, 9000), _tuple("Finance & Insurance", 2000, 2000),
            _tuple("Retail & E-commerce", 1500, 1500), _tuple("Energy", 900, 900),
        ]
        text = compose(fixture)["text"]
        self.assertIn("are the three largest", text)
        self.assertNotIn("Technology is", text)

    def test_it_is_silent_when_too_little_of_the_headline_is_classified(self):
        """The composition of the classified part is not the composition of
        the period. Below the coverage floor this line must not appear."""
        fixture = layoff_fixture()
        fixture["layoff"]["top_industries"] = [
            _tuple("Aerospace & Defense", 900, 900), _tuple("Energy", 400, 400),
            _tuple("Retail & E-commerce", 300, 300), _tuple("Education", 200, 200),
        ]
        self.assertNotIn("are the three largest", compose(fixture)["text"])

    def test_it_is_silent_when_there_is_no_concentration(self):
        """A top three that is a third of a long tail is not a shape."""
        fixture = layoff_fixture()
        flat = 13710 // 12
        fixture["layoff"]["top_industries"] = [
            _tuple(f"Sector {i}", flat, flat) for i in range(12)]
        self.assertNotIn("are the three largest", compose(fixture)["text"])

    def test_it_is_silent_when_the_list_is_too_short_to_be_a_finding(self):
        """"The three largest" out of three is the list read aloud."""
        fixture = layoff_fixture()
        fixture["layoff"]["top_industries"] = [
            _tuple("Aerospace & Defense", 8000, 8000),
            _tuple("Food & Hospitality", 4000, 4000),
            _tuple("Energy", 1710, 1710)]
        self.assertNotIn("are the three largest", compose(fixture)["text"])


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheTalentSignalsAreRankedByMateriality(unittest.TestCase):
    """"Latest signals" was a feed dump, and the obvious diagnosis was wrong.

    /talent/v1/query already DEFAULTS to sort=notable, so the section was
    already getting materiality first. Measured live over the week to
    2026-08-16: 1,349 signals graded 264 high, 1,082 medium, 3 routine. A
    grade 99.8% of rows pass is not a ranking, so the tiebreak decided the
    list, and the tiebreak is recency, which is close to random when every row
    is from the same week.

    sort=largest IS honoured but only 4.7% of rows carry a headcount and
    MySQL sorts NULLs last, so it returns five headcount stories and nothing
    else can compete. So the ranking is done in the composer.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = compose(talent_fixture())["text"]
        cls.rows = [l for l in cls.text.splitlines() if l.strip().startswith("- ")]

    def test_the_signal_naming_the_most_jobs_leads(self):
        self.assertIn("Sanad Service Centres", self.rows[0])
        self.assertIn("2,200 jobs", self.rows[0])

    def test_a_signal_naming_no_jobs_sorts_below_every_signal_that_does(self):
        placed = [i for i, r in enumerate(self.rows) if "jobs)" in r or "job," in r]
        unplaced = [i for i, r in enumerate(self.rows) if "jobs" not in r]
        if placed and unplaced:
            self.assertLess(max(placed), min(unplaced))

    def test_the_number_that_did_the_ranking_is_shown(self):
        """A list claiming to lead with the biggest signals and printing no
        size is asking to be taken on trust."""
        self.assertIn("(2,200 jobs, 14 Aug 2026)", self.text)

    def test_a_row_naming_no_jobs_prints_no_count_rather_than_a_zero(self):
        """Absent, null and zero all mean "the source stated no number", and
        none of them is a measured zero."""
        row = [r for r in self.rows if "Concentrix" in r][0]
        self.assertNotIn("0 jobs", row)
        self.assertIn("16 Aug 2026", row)

    def test_a_headline_that_is_mostly_not_latin_does_not_take_a_slot(self):
        """Script, not language: the schema has no language column, so
        detecting language would be a guess and detecting script is not. This
        row names 2,000 jobs and would otherwise rank SECOND, which is what
        the live render did before the test existed."""
        self.assertNotIn("ทรู", self.text)

    def test_an_embedded_english_brand_does_not_smuggle_it_back_in(self):
        """The first version asked whether the headline held ANY Latin letter,
        and "... True Customer Day 2026" walked through it."""
        self.assertNotIn("True Customer Day", self.text)

    def test_another_language_in_latin_script_still_ships(self):
        """Dropping these would narrow this summary to the English-speaking
        world while the tracker underneath it is not narrow."""
        self.assertIn("Sudamericana de Lácteos", self.text)

    def test_the_caption_says_how_the_list_is_ordered(self):
        self.assertIn("the signals naming the most jobs first, then the "
                      "tracker's own order", self.text)
        self.assertNotIn("newest first", self.text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheSectionComposesItsOwnInboxSnippet(unittest.TestCase):
    """A preheader has one purpose and one hard ceiling, so it is composed for
    that ceiling rather than borrowed from a body sentence.

    The body lede reached 143 characters against a ceiling of 130 once the
    geography clause was added, and digest_layout walked past it to the next
    section, so a live send carried "AI Layoff Tracker" in the subject beside
    "1,332 new hiring signals" in the snippet. The lede was not too long. A
    body sentence has no length budget and should not acquire one because
    something else borrows it.
    """

    PREHEADER_MAX = 130

    def test_the_layoff_snippet_fits_the_ceiling(self):
        snippet = compose(layoff_fixture())["preheader"]
        self.assertTrue(snippet)
        self.assertLessEqual(len(snippet), self.PREHEADER_MAX)

    def test_the_body_lede_is_free_to_be_longer_than_the_snippet(self):
        """The point of the whole change: the clause stays in the body where
        there is room, and the snippet is composed separately."""
        section = compose(layoff_fixture())
        lede = section["text"].splitlines()[1]
        self.assertGreater(len(lede), self.PREHEADER_MAX,
                           "this fixture no longer reproduces the condition "
                           "that broke the preheader, so it proves nothing")
        self.assertLessEqual(len(section["preheader"]), self.PREHEADER_MAX)

    def test_the_snippet_carries_the_figure_its_tier_and_its_window(self):
        """A figure with no scope is not an acceptable snippet at any length.
        These three are the part the fitter may never drop."""
        snippet = compose(layoff_fixture())["preheader"]
        self.assertIn("13,710", snippet)
        self.assertIn("verified job cuts", snippet)
        self.assertIn("9 to 16 August 2026", snippet)

    def test_geography_outranks_the_date_basis_when_only_one_fits(self):
        """Both will not fit beside the full geography clause. "Where" was the
        owner's own question about this figure, and a snippet naming only the
        date basis is easier to misread than one naming only the geography."""
        snippet = compose(layoff_fixture())["preheader"]
        self.assertIn("worldwide", snippet)
        self.assertNotIn("take effect", snippet)

    def test_both_clauses_survive_when_the_geography_is_short(self):
        """A window where every verified cut carries a country says just
        "worldwide", and then there is room for the basis too."""
        fixture = layoff_fixture()
        verified = (fixture["layoff"]["totals"]["jobs"]
                    - fixture["layoff"]["totals"]["announced_jobs"])
        fixture["layoff"]["top_countries"] = [
            _tuple("United States", verified, verified)]
        snippet = compose(fixture)["preheader"]
        self.assertIn("worldwide", snippet)
        self.assertIn("counted by the date the cuts take effect", snippet)
        self.assertLessEqual(len(snippet), self.PREHEADER_MAX)

    def test_the_talent_section_composes_one_too(self):
        """It fits today. Composing it anyway is what stops it breaking the
        next time somebody adds a clause to that lede, which is exactly how
        the layoff one broke."""
        snippet = compose(talent_fixture())["preheader"]
        self.assertTrue(snippet)
        self.assertLessEqual(len(snippet), self.PREHEADER_MAX)
        self.assertIn("1,332 new hiring signals", snippet)
        self.assertIn("9 to 16 August 2026", snippet)


if __name__ == "__main__":
    unittest.main()
