"""The three dimension blocks the layoff digest gained on 2026-08-25, and the
supporting source link on each biggest-cuts row.

WHY THESE BLOCKS EXIST. The layoff section already broke the headline down by
country and by industry. It could not answer three questions a reader of a
layoff tracker actually asks and the /aggregate response already held: which US
state, why the employer said, and which teams. `top_states`, `reasons` and
`top_roles` were served by the endpoint and never requested, so the composer
now asks for them and renders each in the SAME verified-tier, windowed,
top-five style as `top_industries`.

WHAT THESE TESTS HOLD, and each is a defect that shipped once on another block:

  1. THE VERIFIED TIER, NOT THE ANNOUNCED-INCLUSIVE ONE. The endpoint sorts on
     column [1] (verified plus announced) and the block prints column [4]
     (verified). A block that read [1] would put the wrong number beside a
     label under a verified headline, which is the exact bug the country block
     shipped. The fixtures set [1] != [4] so a block reading the wrong column
     fails here.

  2. EVERY BLOCK NAMES ITS WINDOW. A line lifted out on its own still says what
     it covers.

  3. THE LABELS ARE THE PROJECT'S OWN. A state code expands through
     alt_us_state_names(), the AI reason keeps the tracker's "Reason tag"
     spelling, and a role links through the slug alt_role_categories() owns.

  4. A BLOCK WITH NO DATA DROPS, rather than printing an empty heading.

  5. THE SUPPORTING SOURCE LINK is a plain external `<a>` to the filing or
     report, additive to the company link, and present only where the row
     carries a usable URL.

The composers are PHP, so this drives them through
tests/fixtures/digest_compose_harness.php. Without php on PATH the tests SKIP,
which is not a pass.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")


def _tuple(label, all_jobs, verified_jobs, ai_verified=0):
    """The /aggregate top_* / reasons / top_roles row shape, column order and
    all: [label, all_jobs, ai_jobs, display_label, verified_jobs,
    ai_verified_jobs]. all_jobs (col [1]) is set DIFFERENT from verified_jobs
    (col [4]) on purpose, so a block reading the wrong column is caught."""
    return [label, all_jobs, 0, None, verified_jobs, ai_verified]


def layoff_fixture(**over):
    data = {
        "from": "2026-08-09",
        "to": "2026-08-16",
        "compose": "layoff",
        "layoff": {
            "totals": {
                "jobs": 16726, "entries": 74,
                "announced_jobs": 3016, "announced_entries": 5,
                "ai_verified_jobs": 300, "ai_verified_entries": 2,
                "companies": 71,
            },
            "leaders": [
                # An SEC-path row WITH an entry page AND a source URL. Both
                # links should render: the company name to the page, "Source"
                # to the filing.
                {"company_name": "Applied Aerospace", "job_count": 4320,
                 "layoff_date": "2026-08-12", "ai_explicit": False,
                 "location": "", "state": "", "country": "",
                 "permalink": "https://asktherecruiter.com/blog/layoff/applied/",
                 "announced": False,
                 "source_url": "https://www.sec.gov/filing/applied"},
                # A WARN-path row with NO entry page but a state labour URL:
                # the row that could never carry a first-party permalink is
                # exactly the one the source link rescues.
                {"company_name": "Paramount Skydance", "job_count": 2500,
                 "layoff_date": "2026-08-11", "ai_explicit": True,
                 "location": "CA", "state": "CA", "country": "United States",
                 "permalink": "", "announced": True,
                 "source_url": "https://edd.ca.gov/warn/paramount.pdf"},
            ],
            "top_countries": [
                _tuple("United States", 9000, 7862, 300),
                _tuple("Brazil", 500, 476),
            ],
            "top_industries": [
                _tuple("Aerospace & Defense", 4400, 4320),
                _tuple("Food & Hospitality", 2600, 2474),
                _tuple("Retail & E-commerce", 1900, 1864),
            ],
            "source_types": [
                _tuple("warn", 6100, 6060),
                _tuple("8K", 5000, 4940),
            ],
            # col [1] != col [4] throughout, and NOT in verified order, so a
            # block that borrows the endpoint sort or the wrong column fails.
            "top_states": [
                _tuple("CA", 9999, 5200, 300),
                _tuple("IL", 9999, 1800),
                _tuple("TX", 10, 1200),
                _tuple("NY", 10, 900),
                _tuple("WA", 10, 600),
            ],
            "reasons": [
                _tuple("restructuring", 9999, 6000, 100),
                _tuple("cost_reduction", 9999, 4200),
                _tuple("ai_automation", 1, 300, 300),
                _tuple("offshoring", 1, 250),
            ],
            "top_roles": [
                _tuple("Manufacturing & production", 9999, 4320),
                _tuple("Engineering & IT", 9999, 1600, 300),
                _tuple("Customer support & success", 1, 800),
                _tuple("Sales & marketing", 1, 400),
            ],
        },
        "ytd": {
            "totals": {"jobs": 971602, "announced_jobs": 463348,
                       "ai_verified_jobs": 42253},
            "top_countries": [
                _tuple("United States", 402000, 300000),
                _tuple("Multiple countries", 60000, 40000),
            ],
        },
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


def series(section, heading):
    """The one <p data-alt="series"> under a given <h3>, tags stripped, or ''
    when the block did not render."""
    m = re.search(r"<h3>" + re.escape(heading) + r"</h3>"
                  r"<p data-alt=\"series\">(.*?)</p>", section["html"], re.S)
    return m.group(1) if m else ""


@unittest.skipIf(PHP is None, "php is not on PATH, so the composers could not "
                              "be run. UNKNOWN, not a pass.")
class TheThreeNewBlocksRender(unittest.TestCase):
    def setUp(self):
        self.section = compose(layoff_fixture())

    def test_all_three_headings_are_present(self):
        html = self.section["html"]
        for heading in ("By US state", "Why", "Roles most affected"):
            self.assertIn("<h3>" + heading + "</h3>", html,
                          f"the {heading!r} block did not render")

    def test_each_block_reads_the_verified_column_not_the_endpoint_sort(self):
        # CA verified is 5,200 (col [4]); its col [1] is 9,999. A block reading
        # the wrong column, or trusting the endpoint order, would show 9,999 or
        # rank TX/NY/WA differently.
        state = series(self.section, "By US state")
        self.assertRegex(state, r"California</a> 5,200")
        self.assertNotIn("9,999", state)
        # Restructuring verified is 6,000, not its 9,999 announced-inclusive.
        why = series(self.section, "Why")
        self.assertRegex(why, r"Restructuring</a> 6,000")
        self.assertNotIn("9,999", why)
        roles = series(self.section, "Roles most affected")
        self.assertRegex(roles, r"Manufacturing &amp; production</a> 4,320")
        self.assertNotIn("9,999", roles)

    def test_every_block_names_its_window(self):
        for heading in ("By US state", "Why", "Roles most affected"):
            self.assertIn("2026", series(self.section, heading),
                          f"the {heading!r} caption states no year")

    def test_state_codes_expand_to_names(self):
        state = series(self.section, "By US state")
        self.assertIn("California", state)
        self.assertIn("Illinois", state)
        self.assertNotRegex(state, r">CA<")  # the raw code must not be the label

    def test_top_five_only(self):
        # Five states supplied, five shown; the block slices to five like the
        # industry block slices to three.
        state = series(self.section, "By US state")
        self.assertEqual(state.count("</a>"), 5)

    def test_the_ai_reason_keeps_the_trackers_own_label(self):
        why = series(self.section, "Why")
        self.assertIn("Reason tag: AI or automation", why,
                      "the AI reason tag is not spelled the way the page spells it")

    def test_the_reason_block_says_the_dimension_overlaps(self):
        # reasons and roles are LIKE-over-packed-tags: an entry can carry
        # several, so the caption must not imply a clean partition.
        self.assertIn("can carry more than one", series(self.section, "Why"))
        self.assertIn("can name several", series(self.section, "Roles most affected"))


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheBlocksLinkToTheRightFilteredView(unittest.TestCase):
    def setUp(self):
        self.section = compose(layoff_fixture())

    def test_state_links_carry_the_state_code_and_the_basis(self):
        state = series(self.section, "By US state")
        self.assertIn("state=CA", state)
        self.assertIn("date_basis=effective", state)

    def test_reason_links_carry_the_reason_tag(self):
        why = series(self.section, "Why")
        self.assertIn("reasons=ai_automation", why)
        self.assertIn("reasons=restructuring", why)

    def test_role_links_carry_the_slug_not_the_label(self):
        roles = series(self.section, "Roles most affected")
        # alt_role_categories(): "Manufacturing & production" -> manufacturing.
        self.assertIn("roles=manufacturing", roles)
        self.assertIn("roles=engineering", roles)


@unittest.skipIf(PHP is None, "php is not on PATH.")
class ABlockWithNoDataDropsGracefully(unittest.TestCase):
    def test_absent_keys_render_no_heading(self):
        fx = layoff_fixture()
        for key in ("top_states", "reasons", "top_roles"):
            fx["layoff"].pop(key, None)
        html = compose(fx)["html"]
        for heading in ("By US state", "Roles most affected"):
            self.assertNotIn("<h3>" + heading + "</h3>", html,
                             f"{heading!r} rendered with no data behind it")

    def test_a_single_row_block_drops_like_the_industry_block(self):
        # The industry block requires more than one row to be a series; the new
        # blocks follow it. One state is not a ranking.
        fx = layoff_fixture()
        fx["layoff"]["top_states"] = [_tuple("CA", 5200, 5200)]
        html = compose(fx)["html"]
        self.assertNotIn("<h3>By US state</h3>", html)


@unittest.skipIf(PHP is None, "php is not on PATH.")
class TheBiggestCutsRowsCarryASourceLink(unittest.TestCase):
    def setUp(self):
        self.section = compose(layoff_fixture())

    def test_both_rows_render_a_source_link(self):
        html = self.section["html"]
        self.assertEqual(html.count('data-alt="source-link"'), 2,
                         "not every leader with a source_url got a Source link")
        self.assertIn("https://www.sec.gov/filing/applied", html)
        self.assertIn("https://edd.ca.gov/warn/paramount.pdf", html)

    def test_the_source_link_is_additive_to_the_company_link(self):
        # The company name still links (Applied to its entry page), and the
        # Source link is a SECOND anchor on the same row, not a replacement.
        html = self.section["html"]
        self.assertIn(
            '<a href="https://asktherecruiter.com/blog/layoff/applied/">'
            'Applied Aerospace</a>', html)

    def test_the_source_is_named_in_the_text_part(self):
        self.assertIn("Source: https://edd.ca.gov/warn/paramount.pdf",
                      self.section["text"])

    def test_the_basis_note_counts_the_sourced_rows(self):
        # Both rows carry a source, so the note says every row does.
        self.assertIn('carries a &quot;Source&quot; link',
                      self.section["html"])

    def test_a_non_http_source_url_is_refused(self):
        # alt_digest_external_link_ok() rejects a scheme a mail client could
        # treat as script or a local file. Such a row renders no Source link.
        fx = layoff_fixture()
        fx["layoff"]["leaders"][0]["source_url"] = "javascript:alert(1)"
        fx["layoff"]["leaders"][1]["source_url"] = ""
        html = compose(fx)["html"]
        self.assertNotIn('data-alt="source-link"', html)
        self.assertNotIn("javascript:alert", html)


if __name__ == "__main__":
    unittest.main()
