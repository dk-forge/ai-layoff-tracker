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
# is rendered with one, whether it is a range, a single day, or "2026 so far".
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
                 "permalink": "https://asktherecruiter.com/blog/layoff/applied-2026-08-12/"},
                {"company_name": "Paramount Skydance", "job_count": 2500,
                 "layoff_date": "2026-08-11", "ai_explicit": True,
                 "location": "CA", "permalink": ""},
            ],
            # United States is NOT first by the verified column, on purpose.
            "top_countries": [
                _tuple("Multiple countries", 2501, 1),
                _tuple("United States", 7862, 7862),
                _tuple("Brazil", 476, 476),
            ],
            "top_industries": [
                _tuple("Media & Entertainment", 2746, 75),
                _tuple("Aerospace & Defense", 4320, 4320),
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
            "rows": [
                {"company": "Concentrix", "headline": "rolls out matched PERA",
                 "published_date": "2026-08-16"},
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
        period = section["text"].split("\n2026 so far")[0]
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
                        self.text.index("2026 so far"))
        self.assertLess(self.text.index("Which industries"),
                        self.text.index("2026 so far"))

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
        self.assertIn("1 of the 2 companies listed for 9 to 16 August 2026 "
                      "link to an entry page", text)

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


if __name__ == "__main__":
    unittest.main()
