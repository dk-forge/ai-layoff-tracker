"""Every link the digest builds names its date basis, or it publishes a lie.

THE DEFECT, WHICH HAS NOW BEEN FIXED THREE TIMES IN THIS REPO.

The tracker page defaults to the FILING basis: `notice`, COALESCE(
announcement_date, layoff_date), the day a cut was filed or announced. Every
figure in the digest's layoff section counts on the EFFECTIVE basis, the day
the jobs end, because that is the date the leaders payload actually carries.
The two produce different numbers over the same window, roughly double on some
months.

So a link built from an effective-basis figure and carrying no basis lands on a
page showing a different number under a label promising the same one. It was
fixed on the press page twice and in this composer once, and each time it came
back somewhere new, because the rule lived in a comment. On 2026-08-19 the
digest went from one link per send to one per ranked row, which is twenty-odd
new chances to reintroduce it.

This is the rule as an assertion. It drives the real composer, takes every
anchor out of the rendered HTML and every URL out of the text part, and fails
on any tracker link that does not name `date_basis` explicitly.

WHAT IS DELIBERATELY NOT REQUIRED. An entry-page permalink carries no basis and
must not: it is one row's own page, not a filtered view, and there is nothing
for a basis to reinterpret. The test tells the two apart by the path.
"""
import html as html_mod
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
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

TRACKER = "https://asktherecruiter.com/blog/ai-layoff-tracker/"


def _tuple(label, all_jobs, verified_jobs):
    return [label, all_jobs, 0, None, verified_jobs, 0]


def compose(fixture):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump(fixture, handle)
        handle.close()
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, handle.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr[:1200]}")
    out = json.loads(run.stdout)
    if out.get("null"):
        raise AssertionError("the composer returned nothing for this fixture")
    return out


def fixture():
    """A window with something on every dimension that gets a link."""
    return {
        "from": "2026-08-10", "to": "2026-08-16", "compose": "layoff",
        "layoff": {
            "totals": {"jobs": 9100, "entries": 20,
                       "announced_jobs": 100, "announced_entries": 1,
                       "ai_verified_jobs": 0, "ai_verified_entries": 0,
                       "companies": 18},
            "leaders": [
                {"company_name": "Has A Page", "job_count": 4000,
                 "layoff_date": "2026-08-12", "ai_explicit": False,
                 "location": "", "state": "", "country": "United States",
                 "permalink": TRACKER.replace("ai-layoff-tracker/",
                                              "layoff/has-a-page/"),
                 "announced": False},
                # NO PERMALINK. A bulk-imported notice never acquires one, and
                # before 2026-08-19 it shipped as plain text. It now links to
                # the tracker filtered to that company, which is a filtered
                # view and therefore has to name the basis like any other.
                {"company_name": "Bulk Filed Co", "job_count": 3000,
                 "layoff_date": "2026-08-13", "ai_explicit": False,
                 "location": "", "state": "", "country": "United States",
                 "permalink": "", "announced": False},
            ],
            "top_countries": [
                _tuple("United States", 5000, 5000),
                _tuple("Germany", 2000, 2000),
                _tuple("Japan", 1000, 1000),
                _tuple("Brazil", 500, 500),
                _tuple("Multiple countries", 400, 400),
            ],
            "top_industries": [
                _tuple("Technology", 4000, 4000),
                _tuple("Retail & E-commerce", 3000, 3000),
                _tuple("Healthcare & Pharma", 1000, 1000),
                _tuple("Logistics & Transport", 500, 500),
            ],
            "source_types": [["warn", 9000, 0, None, 9000, 0]],
        },
        "ytd": {"totals": {"jobs": 100, "announced_jobs": 0,
                           "ai_verified_jobs": 0},
                "top_countries": [_tuple("United States", 100, 100)]},
    }


def links_in(section):
    """Every destination the section offers, from BOTH body parts."""
    html = [html_mod.unescape(m) for m in
            re.findall(r'href="([^"]+)"', section["html"])]
    text = re.findall(r"https?://\S+", section["text"])
    return html, text


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class EveryFilteredLinkNamesItsDateBasis(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.section = compose(fixture())
        cls.html_links, cls.text_links = links_in(cls.section)

    def test_the_section_links_more_than_once(self):
        """The whole complaint was that nothing was linked. A test that passes
        vacuously on a section with one link would not have caught it."""
        tracker = [u for u in self.html_links if u.startswith(TRACKER + "?")]
        self.assertGreaterEqual(
            len(tracker), 8,
            f"the ranked rows are not linked: {self.html_links!r}")

    def test_every_tracker_link_names_the_basis(self):
        for url in self.html_links + self.text_links:
            if not url.startswith(TRACKER + "?"):
                continue
            self.assertIn("date_basis=effective", url,
                          f"this link lands on the page's default FILING "
                          f"basis while promising an effective-basis "
                          f"figure: {url}")

    def test_every_tracker_link_carries_the_window(self):
        for url in self.html_links + self.text_links:
            if not url.startswith(TRACKER + "?"):
                continue
            self.assertIn("from=2026-08-10", url, url)
            self.assertIn("to=2026-08-16", url, url)

    def test_every_filter_key_is_written_even_when_empty(self):
        """"Present and empty" clears a returning reader's saved filter.
        "Absent" leaves it ANDed into the number we just published."""
        for url in self.html_links:
            if not url.startswith(TRACKER + "?"):
                continue
            for key in ("years", "quarters", "months", "country", "industry",
                        "state", "sources", "reasons", "roles", "company",
                        "keyword", "min_jobs", "q"):
                self.assertRegex(url, rf"[?&]{key}=",
                                 f"{key} is absent from {url}, so a saved "
                                 f"filter survives into our figure")

    def test_an_entry_page_is_not_required_to_carry_a_basis(self):
        """It is one row's own page, not a filtered view, so there is nothing
        for a basis to reinterpret. Requiring one would be cargo cult."""
        entries = [u for u in self.html_links if "/blog/layoff/" in u]
        self.assertTrue(entries, "the fixture's linked leader lost its page")
        for url in entries:
            self.assertNotIn("date_basis", url)

    def test_a_row_with_no_entry_page_still_gets_a_destination(self):
        joined = " ".join(self.html_links)
        self.assertIn("company=Bulk%20Filed%20Co", joined,
                      "a bulk-imported row shipped as plain text again")

    def test_the_region_link_carries_the_countries_that_made_the_line(self):
        """A region line is the sum of its countries, so its link has to
        select exactly those countries and no others: adding a country with no
        rows would still be correct and would stop reproducing THIS line."""
        joined = " ".join(self.html_links)
        self.assertIn("country=Germany", joined)
        self.assertIn("country=Japan", joined)
        self.assertIn("country=Multiple%20countries", joined,
                      "the bucket is a line of its own and it is linkable")

    def test_the_unplaced_residual_is_never_linked(self):
        """There is no filter for an empty country, and a link that quietly
        showed something else would be worse than none.

        THE SHAPE CHANGED AND THE PROPERTY DID NOT. The geography block was a
        table of rows and is now one inline series, so the residual is an item
        between two middle dots rather than a `<tr>`. It still has to be there
        and it still has to be unlinked, so the assertion moved from the row to
        the item and asserts the same two things.
        """
        text = self.section["text"]
        block = text.split("Where the jobs were")[1].split("Which industries")[0]
        residual = [l for l in block.splitlines()
                    if "No country recorded" in l]
        self.assertTrue(residual, "the residual went missing")
        html = self.section["html"]
        geo = html.split("Where the jobs were")[1].split("Which industries")[0]
        items = [i for i in geo.split("\u00b7") if "No country recorded" in i]
        self.assertTrue(items, "the residual went missing from the HTML part")
        self.assertNotIn("<a ", items[0],
                         "the unplaced residual acquired a link, which cannot "
                         "reproduce it")


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheLinkAndTheFiguresCannotDriftApart(unittest.TestCase):
    """The CTA lands on the basis the figures beside it were counted on.

    THE GAP THIS CLOSES, WHICH THE CLASS ABOVE DOES NOT.

    Every test above asserts that a link NAMES a basis, and one of them asserts
    the literal string `date_basis=effective`. Both would stay green through
    the next form of this defect: the composer moving its /aggregate calls to
    the filing basis while the links keep saying `effective`. The link would
    still name a basis, the assertion would still match its remembered string,
    and every figure in the email would be counted one way while every link
    landed on the other.

    So this reads BOTH halves out of one render. The `requests` the harness
    records are the parameters the real composer really sent; the anchors are
    the URLs it really built. They are required to be the two spellings of ONE
    basis, and that pair has exactly one definition in the plugin,
    alt_digest_layoff_basis(). A change to either spelling is a change to that
    function, and a change to only one of them fails here.
    """

    @classmethod
    def setUpClass(cls):
        cls.section = compose(fixture())
        cls.html_links, cls.text_links = links_in(cls.section)
        src = open(SUBSCRIBE, encoding="utf-8").read()
        body = re.search(r"function alt_digest_layoff_basis\(.*?\n\}", src, re.S)
        assert body, "alt_digest_layoff_basis went missing from the composer"
        pairs = dict(re.findall(r"'(query|link)'\s*=>\s*'([a-z_]+)'", body.group(0)))
        cls.pairs = pairs

    def test_the_plugin_states_the_basis_in_exactly_one_place(self):
        self.assertEqual(set(self.pairs), {"query", "link"},
                         "the basis pair is no longer a pair")
        src = open(SUBSCRIBE, encoding="utf-8").read()
        composer = src[src.index("function alt_digest_compose_layoff"):]
        self.assertNotIn("'date_basis', '", composer,
                         "a composer request spells the basis as a literal "
                         "again, so it can move without the links moving")

    def test_every_aggregate_call_counts_on_the_query_spelling(self):
        asked = [r["params"].get("date_basis")
                 for r in self.section["requests"]
                 if "/layoffs/" in r["route"]]
        self.assertTrue(asked, "the composer made no layoff aggregate call")
        for basis in asked:
            self.assertEqual(basis, self.pairs["query"],
                             "a figure in this email is counted on a basis "
                             "the links do not land on")

    def test_every_tracker_link_lands_on_the_same_basis(self):
        seen = 0
        for url in self.html_links + self.text_links:
            if not url.startswith(TRACKER + "?"):
                continue
            seen += 1
            self.assertIn("date_basis=" + self.pairs["link"], url,
                          f"this link does not land on the basis the "
                          f"figures were computed with: {url}")
        self.assertGreater(seen, 0, "nothing was linked at all")

    def test_the_headline_cta_is_one_of_them(self):
        """The link the section signs off with is the one a reader follows to
        check the number in the subject line, so it is named rather than left
        to the sweep above."""
        # The CTA is the one tracker link on which EVERY filter is cleared:
        # it reproduces the headline, so it may not narrow it.
        keys = ("years", "quarters", "months", "country", "industry", "state",
                "sources", "reasons", "roles", "company", "keyword",
                "min_jobs", "q")
        cta = [u for u in self.text_links
               if u.startswith(TRACKER + "?")
               and all(re.search(rf"[?&]{k}=(&|$)", u) for k in keys)]
        self.assertTrue(cta, f"the unfiltered CTA is gone: {self.text_links!r}")
        self.assertIn("date_basis=" + self.pairs["link"], cta[0])
        self.assertIn("from=2026-08-10", cta[0])
        self.assertIn("to=2026-08-16", cta[0])
