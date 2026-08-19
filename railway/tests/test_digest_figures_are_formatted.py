"""Every figure the digest composes wears its thousands separators.

WHAT WENT OUT, AND IT TOOK TWO SCREENSHOTS TO BELIEVE. The owner's Gmail inbox
showed, in the SAME message:

    subject   16,842 verified job cuts · 1,376 hiring signals · Aug 10-16
    preview   582 of 1376 verified against a primary document, from 1324 companies.

1376 formatted in the subject and unformatted in the preview, on Gmail iOS and
Gmail desktop both. The first session report called it UNKNOWN and probably the
client's snippet extraction. That was wrong, and the reasoning that would have
caught it is one line long: a client that stripped separators would have
stripped them from the SUBJECT of the same message, and it did not.

WHY THE FIRST GUARD DID NOT FIRE, AND THIS IS THE LESSON.

The guard written for this was:

    a figure appearing in more than one composed string is spelled identically
    in all of them

which is true, and useless. The unformatted figures - 10132, 1376 in the
preview, 1324, 582 - appear ONCE. There was nothing to compare them against, so
the assertion passed vacuously on exactly the case it existed for. Most numbers
appear once; a property that only fires on duplicates is blind to the common
case.

This is the second guard tonight that was technically correct and practically
blind. The other hard-coded a fixture row that happened to still satisfy it.
Both share a shape: the assertion was written against the example in front of
the author rather than against the property.

SO THE PROPERTY IS ABSOLUTE. Every integer of four digits or more, in every
string the site composes for an email, carries separators. Not "if it also
appears elsewhere". Not "in the subject". Everywhere, once, unconditionally.

WHAT IS DELIBERATELY EXEMPT. A four-digit YEAR is a year and never takes a
separator, and years are everywhere in this email. An ISO date, a version
string and a URL are not figures either. Each exemption is narrow and named
below rather than being a general "looks like it might be fine".
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
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import digest_layout as layout  # noqa: E402

SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

# A bare run of four or more digits. The exemptions are stripped from the text
# BEFORE this runs, so anything it finds is a figure nobody formatted.
UNSEPARATED = re.compile(r"(?<![\d,.])\d{4,}(?![\d,.])")

# Years, ISO dates and anything inside a URL or an HTML attribute. Narrow and
# named: a year takes no separator, an ISO stamp is not a quantity, and a query
# string is machine text a reader never parses as a number.
EXEMPT = (
    re.compile(r"https?://\S+"),
    re.compile(r"""\s(?:href|src|style|data-alt)\s*=\s*(?:"[^"]*"|'[^']*')"""),
    re.compile(r"\b(?:19|20)\d{2}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
)


def strip_exempt(text: str) -> str:
    for pattern in EXEMPT:
        text = pattern.sub(" ", text)
    return text


def offenders(text: str):
    return UNSEPARATED.findall(strip_exempt(text or ""))


def _tuple(label, all_jobs, verified_jobs, ai_verified=0):
    return [label, all_jobs, 0, None, verified_jobs, ai_verified]


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


def layoff_fixture():
    """Every figure four digits or longer, so nothing passes by being small.

    The live week that produced the defect had 16,842 worldwide, 10,132 in the
    United States and 73 companies, and the preview printed the middle one
    unformatted. These are the same shapes with nothing under a thousand that
    could hide a missing separator.
    """
    return {
        "from": "2026-08-10", "to": "2026-08-16", "compose": "layoff",
        "layoff": {
            "totals": {"jobs": 20358, "entries": 1076,
                       "announced_jobs": 3516, "announced_entries": 6,
                       "ai_verified_jobs": 0, "ai_verified_entries": 0,
                       "ai_broad_jobs": 4820, "companies": 1073},
            "leaders": [
                {"company_name": "Applied Aerospace", "job_count": 4320,
                 "layoff_date": "2026-08-12", "ai_explicit": False,
                 "location": "", "state": "", "country": "United States",
                 "permalink": "", "announced": False},
            ],
            "top_countries": [
                _tuple("United States", 10132, 10132),
                _tuple("Germany", 2960, 2960),
                _tuple("Multiple countries", 2501, 1234),
            ],
            "top_industries": [
                _tuple("Aerospace & Defense", 4320, 4320),
                _tuple("Food & Hospitality", 2553, 2553),
                _tuple("Retail & E-commerce", 1690, 1690),
                _tuple("Technology", 1055, 1055),
            ],
            "source_types": [["warn", 8240, 0, None, 8240, 0],
                             ["8K", 4940, 0, None, 4940, 0]],
        },
        "ytd": {"totals": {"jobs": 520549, "announced_jobs": 0,
                           "ai_verified_jobs": 42953},
                "top_countries": [_tuple("United States", 400000, 400000)]},
        "options": {"alt_last_write": 1787184000},
    }


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class NoComposedFigureIsMissingItsSeparators(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.section = compose(layoff_fixture())

    def _check(self, name, text):
        found = offenders(text)
        self.assertEqual(
            found, [],
            f"{name} carries {found!r} with no thousands separator. Every "
            f"figure the digest composes goes through alt_digest_number(); "
            f"something here used a raw integer.")

    def test_the_preview_line(self):
        """The line the defect actually shipped in."""
        self._check("the preheader", self.section.get("preheader", ""))

    def test_the_subject_fragment(self):
        self._check("the metric fragment", self.section.get("metric", ""))

    def test_the_plain_text_part(self):
        self._check("the text part", self.section["text"])

    def test_the_html_part(self):
        self._check("the html part", self.section["html"])

    def test_a_figure_appearing_once_is_still_checked(self):
        """THE ASSERTION THE OLD GUARD COULD NOT MAKE.

        Its property was "a figure in two composed strings is spelled the same
        way", so a figure appearing once had nothing to be compared against and
        passed. The company count appears in the preview and nowhere else, and
        it is four digits in this fixture on purpose.
        """
        preview = self.section.get("preheader", "")
        self.assertIn("1,073", preview,
                      "the company count is in the preview and appears "
                      "nowhere else, which is exactly the shape the old guard "
                      "was blind to")

    def test_the_guard_itself_can_fail(self):
        """A test that cannot fail is not a test. This proves the detector
        fires on the real defect string before trusting it on our output."""
        self.assertEqual(offenders("582 of 1376 verified, from 1324 companies."),
                         ["1376", "1324"])
        self.assertEqual(offenders("0 cuts attributed to AI, 10132 in the US"),
                         ["10132"])

    def test_a_year_is_not_a_figure(self):
        self.assertEqual(offenders("August 10-16, 2026 and 1 January 2026"), [])
        self.assertEqual(offenders("2026-08-16"), [])

    def test_a_url_is_not_a_figure(self):
        self.assertEqual(
            offenders("https://asktherecruiter.com/blog/?from=2026-08-10&x=12345"),
            [])

    def test_a_formatted_figure_passes(self):
        self.assertEqual(offenders("16,842 verified job cuts"), [])
        self.assertEqual(offenders("73 companies"), [])


class ThePhpAndThePythonAgreeOnHowAFigureLooks(unittest.TestCase):
    """The site formats every figure and the relay formats none, which is the
    rule that makes one spelling possible. This pins both halves."""

    def test_the_layout_module_formats_nothing(self):
        source = open(os.path.join(RAILWAY, "digest_layout.py"),
                      encoding="utf-8").read()
        self.assertNotIn("{:,}", source,
                         "digest_layout composed a figure, which is the site's "
                         "job and the reason the two surfaces cannot disagree")

    @unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
    def test_the_site_uses_one_formatter_and_not_the_locale(self):
        """number_format_i18n() depends on a $wp_locale this file does not own
        and a filter any plugin may hook, so a figure a reporter may quote does
        not go through it."""
        source = open(SUBSCRIBE, encoding="utf-8").read()
        code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        code = re.sub(r"//[^\n]*", "", code)
        self.assertNotIn("number_format_i18n(", code,
                         "a digest figure went through the locale formatter "
                         "again; use alt_digest_number()")
        self.assertIn("function alt_digest_number(", source)


if __name__ == "__main__":
    unittest.main()
