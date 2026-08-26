"""A SOURCE LINK IS LABELLED BY WHAT IT ACTUALLY IS, NOT "PRIMARY SOURCE".

The citation button said "View primary source" for every row, including a news
report and even a Google News redirect URL, which is an index record and not
the article. A news report is not a primary source; calling it one on a
citation-grade page is the exact overclaim the external review flagged
(docs/EXTERNAL_REVIEW_2026-08-20.md).

The label is now DERIVED from the row's source_type (and, for news, from whether
the URL is a Google News redirect). There are two implementations because the
single-entry page renders in PHP (alt_source_link_label in includes/api.php) and
the tracker cards render in JS (sourceLinkLabel in assets/layoffs.js). BOTH are
RUN here, on the same matrix, and pinned to agree character for character: a
label that drifts between the two surfaces is the same defect wearing two faces.

The load-bearing assertion is negative and blunt: NOTHING in this matrix, on
either implementation, may call a Google News redirect a primary source.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
API_PHP = (PLUGIN / "includes/api.php").read_text()
JS = (PLUGIN / "assets/layoffs.js").read_text()
SINGLE_TPL = (PLUGIN / "templates/single-layoff.php").read_text()

PHP = shutil.which("php")


def strip_js_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def _php_fn(name):
    """Brace-matched source of one top-level `function <name>(` in api.php."""
    start = API_PHP.index("function %s(" % name)
    i = API_PHP.index("{", start)
    depth, j = 0, i
    while j < len(API_PHP):
        if API_PHP[j] == "{":
            depth += 1
        elif API_PHP[j] == "}":
            depth -= 1
            if depth == 0:
                return API_PHP[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


# The matrix every implementation is measured against. (source_type, url) ->
# expected label. A Google News redirect (last row) is the case the button used
# to mislabel.
CASES = [
    ("8K", "https://www.sec.gov/Archives/edgar/data/x.htm", "View official filing"),
    ("warn", "https://dol.example.gov/warn.pdf", "View official filing"),
    ("erm", "https://www.eurofound.europa.eu/erm/x", "View official filing"),
    ("federal_rif", "https://opm.gov/x", "View official filing"),
    ("press_release", "https://ir.company.com/news/x", "View employer statement"),
    ("news", "https://www.reuters.com/business/x", "View source report"),
    ("news", "https://www.bbc.co.uk/news/x", "View source report"),
    ("seed", "", "View source"),
    ("", "https://example.com/x", "View source"),
    ("news", "https://news.google.com/rss/articles/CBMiK2h0dHBz?oc=5", "View Google News index record"),
    ("news", "https://news.google.co.uk/articles/CBMi?hl=en-GB", "View Google News index record"),
]


class ThePhpAndJsLabellersAgree(unittest.TestCase):

    def _js_labels(self):
        preamble = "var CASES = %s;\n" % json.dumps([[c[0], c[1]] for c in CASES])
        return jsrun.run(
            ["sourceLinkLabel", "isGoogleNewsUrl"],
            preamble,
            "CASES.map(function (c) { return sourceLinkLabel(c[0], c[1]); })")

    @unittest.skipUnless(PHP, "php binary not available")
    def _php_labels(self):
        harness = "<?php\n%s\n%s\n$cases = %s;\n" % (
            _php_fn("alt_is_google_news_url"),
            _php_fn("alt_source_link_label"),
            json.dumps([[c[0], c[1]] for c in CASES]))
        harness += ("$out = array();\n"
                    "foreach ($cases as $c) { $out[] = alt_source_link_label($c[0], $c[1]); }\n"
                    "echo json_encode($out);\n")
        proc = subprocess.run([PHP, "-r", harness[6:]], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_the_js_labeller_matches_the_matrix(self):
        got = self._js_labels()
        want = [c[2] for c in CASES]
        self.assertEqual(got, want)

    @unittest.skipUnless(PHP, "php binary not available")
    def test_the_php_labeller_matches_the_matrix(self):
        got = self._php_labels()
        want = [c[2] for c in CASES]
        self.assertEqual(got, want)

    @unittest.skipUnless(PHP, "php binary not available")
    def test_php_and_js_never_disagree(self):
        self.assertEqual(
            self._php_labels(), self._js_labels(),
            "the PHP citation page and the JS cards would render different "
            "labels for the same row")

    def test_a_google_news_redirect_is_never_called_a_primary_source(self):
        """The load-bearing negative. Run on both implementations."""
        js = self._js_labels()
        for (stype, url, _), label in zip(CASES, js):
            if "news.google." in url:
                self.assertNotIn("primary source", label.lower(),
                                 "JS labels a Google News redirect %r" % label)
                self.assertIn("index record", label.lower())
        if PHP:
            php = self._php_labels()
            for (stype, url, _), label in zip(CASES, php):
                if "news.google." in url:
                    self.assertNotIn("primary source", label.lower(),
                                     "PHP labels a Google News redirect %r" % label)

    def test_no_news_row_is_ever_labelled_a_primary_source(self):
        js = self._js_labels()
        for (stype, _u, _e), label in zip(CASES, js):
            if stype == "news":
                self.assertNotIn("primary source", label.lower(),
                                 "a news report is not a primary source: %r" % label)


class TheOverclaimIsGoneFromTheRenderedSurfaces(unittest.TestCase):
    """Source checks with comments stripped: the two places that hard-coded
    "View primary source" for a news row must now derive the label."""

    def test_the_single_entry_page_derives_its_button_label(self):
        vis = re.sub(r"<\?php.*?\?>", " ", SINGLE_TPL, flags=re.S)
        self.assertNotIn(
            "View primary source", vis,
            "single-layoff.php still hard-codes 'View primary source' in visible "
            "markup instead of deriving it from source_type")
        self.assertIn("alt_source_link_label", SINGLE_TPL,
                      "single-layoff.php no longer calls the honest labeller")

    def test_the_card_detail_block_derives_its_label(self):
        js = strip_js_comments(JS)
        self.assertNotIn(
            "'View primary source (", js,
            "layoffs.js still emits a literal 'View primary source (name)' label")
        self.assertIn("sourceLinkLabel(", js,
                      "layoffs.js no longer derives the source label")


if __name__ == "__main__":
    unittest.main()
