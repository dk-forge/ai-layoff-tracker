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

===========================================================================
AND THEN IT SHIPPED AGAIN, AND THIS GUARD WAS GREEN THROUGH IT. 2026-08-19.

The owner's inbox, a test send he took after the fix above was on main:

    16,842 verified job cuts · Aug 10-16   0 cuts attributed to AI, 10132 in the U...
    1,379 hiring signals · Aug 10-16       582 of 1379 verified against a primary...
                                           ... from 1327 companies

The property above was right. Its INPUT SET was wrong, and that is the defect
worth writing down, because it is the third time in two days that a correct
assertion has been pointed at the wrong strings.

THE INPUT SET HAD TWO HOLES.

  1. ONE COMPOSER OF THREE. This file composed the LAYOFF section and nothing
     else. `alt_digest_compose_talent` and `alt_digest_compose_articles` were
     never invoked by any test in this repo, so every field they build was
     unscanned - and the talent preheader is one of the two lines in the
     owner's screenshot. The harness has supported `compose: talent` since it
     was written. Nothing called it. A guard that reads a third of the surface
     it names is a guard against a third of the defect.

  2. IT STOPPED AT THE PHP BOUNDARY. The composers hand four strings to
     digest-api.php; digest_send.py reads them back and digest_layout.py joins
     them into the subject, the hidden preheader div and the two body parts
     that a client actually displays. Nothing checked what came out the far
     end. The preheader especially is a SEPARATE payload field: it does not
     appear in the html or the text the old tests scanned, it is inserted by
     render_html, and preheader_text may return a DIFFERENT string entirely
     when the site's own snippet does not fit. So the one field the defect
     shipped in was the one field whose delivered form nothing read.

WHAT THE REPRODUCTION ACTUALLY FOUND, so the next session does not re-derive
it. Both preheaders compose CORRECTLY on this tree and on the live build:

    0 cuts attributed to AI, 10,132 in the United States, across 73 companies,
    8,240 of them from state WARN filings.
    582 of 1,379 verified against a primary document, from 1,327 companies.

The screenshot was a build, not a bug: the deployed body differed from the
tree at the moment of that send. alt_digest_fit_preheader does not lose
formatting, and digest_layout's fallback never fired. That is why nothing here
changes a composer. It changes what is watched, so that the next time the two
disagree, something red says so before an inbox does.

THE ORDER MATTERS: the detector is proved against the owner's literal strings
FIRST, in test_the_guard_itself_can_fail, before any assertion trusts it. A
test that cannot fail is not a test, and this file has now been the thing that
could not fail twice.
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
import digest_send  # noqa: E402

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
    # A STANDARD'S NUMBER IS ITS NAME. The edition note reads "Weeks are
    # ISO-8601", and 8,601 would be a nonsense. Spelled with the word ISO
    # attached rather than as a bare 8601, so a real quantity that happens to
    # be 8601 is still caught. This exemption exists because the boundary scan
    # below reads the WHOLE rendered message, footer and edition note
    # included, which the section-level scans never did.
    re.compile(r"\bISO[\s‑-]?8601\b"),
)

# THE FIELDS A CLIENT CAN DISPLAY, named once so a new one cannot be added to
# the payload and quietly go unwatched. `preheader` is listed FIRST because it
# is the field the defect shipped in twice and the only one that travels as its
# own payload member rather than inside a rendered body.
DISPLAYED = ("preheader", "metric", "text", "html")


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


def talent_fixture():
    """THE SECTION NO TEST HAD EVER COMPOSED, on the owner's own figures.

    1,379 signals, 582 of them verified, from 1,327 companies is the exact week
    in the second screenshot. Every one of those is four digits or, in 582's
    case, sits directly in front of one, which is the shape of the string the
    preview printed raw: `582 of 1379`.
    """
    return {
        "from": "2026-08-10", "to": "2026-08-16", "compose": "talent",
        "talent": {"total": 1379, "companies": 1327, "verified": 582},
        "talent_q": {"rows": [
            {"company_name": "Northwind Robotics", "headline":
             "Northwind Robotics opens a 2,400-role plant in Ohio",
             "headcount": 2400, "signal_date": "2026-08-12",
             "country": "United States", "permalink": "", "verified": True},
            {"company_name": "Kestrel Foods", "headline":
             "Kestrel Foods to add 1,180 shift roles",
             "headcount": 1180, "signal_date": "2026-08-14",
             "country": "United States", "permalink": "", "verified": False},
        ]},
        "talent_ytd": {"total": 41208, "companies": 9317, "verified": 5064},
        "options": {"alt_last_write": 1787184000},
    }


def articles_fixture():
    """The third composer, also never invoked here before.

    Its preheader is the newest post's own title, so the figure risk lives in
    the caption and the read-time line rather than in the snippet. It is
    scanned on the same terms as the other two rather than being trusted for
    being small: `alt_digest_count` reaches it too.
    """
    body = "word " * 4200
    return {
        "from": "2026-08-10", "to": "2026-08-16", "compose": "articles",
        "posts": [
            {"title": "What 10,132 US job cuts in one week actually look like",
             "excerpt": "A week read through its filings.",
             "date": "2026-08-14 09:00:00", "content": body,
             "link": "https://asktherecruiter.com/blog/one/"},
            {"title": "The WARN notice is the document, not the headline",
             "excerpt": "Where the numbers come from.",
             "date": "2026-08-11 09:00:00", "content": body,
             "link": "https://asktherecruiter.com/blog/two/"},
        ],
        "options": {"alt_last_write": 1787184000},
    }


FIXTURES = (("layoff", layoff_fixture), ("talent", talent_fixture),
            ("articles", articles_fixture))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class NoComposedFigureIsMissingItsSeparators(unittest.TestCase):
    """EVERY composer, EVERY field a client can display. Both were narrower."""

    @classmethod
    def setUpClass(cls):
        cls.sections = {name: compose(build()) for name, build in FIXTURES}
        cls.section = cls.sections["layoff"]

    def _check(self, name, text):
        found = offenders(text)
        self.assertEqual(
            found, [],
            f"{name} carries {found!r} with no thousands separator. Every "
            f"figure the digest composes goes through alt_digest_number(); "
            f"something here used a raw integer.")

    def test_every_displayed_field_of_every_composer(self):
        """THE ASSERTION THE OLD INPUT SET COULD NOT MAKE.

        It composed `layoff` alone, so two of the three composers were never
        run by any test in this repo, and the talent preheader is one of the
        two lines in the owner's second screenshot. The fields are read from
        DISPLAYED rather than named one test at a time, so a new payload
        member cannot be added without being scanned.
        """
        for name, section in sorted(self.sections.items()):
            for field in DISPLAYED:
                with self.subTest(section=name, field=field):
                    self._check(f"{name}.{field}", section.get(field, ""))

    def test_the_preview_line(self):
        """The line the defect actually shipped in, on both streams."""
        self._check("the layoff preheader",
                    self.sections["layoff"].get("preheader", ""))
        self._check("the talent preheader",
                    self.sections["talent"].get("preheader", ""))

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

    def test_the_talent_preview_spells_the_screenshot_correctly(self):
        """The owner's second screenshot, positively.

        `offenders` returning nothing proves no raw figure is present. It does
        not prove the right figures are, and a composer that dropped the
        verified split entirely would satisfy it. So the delivered spelling of
        the exact string he photographed is asserted here.
        """
        self.assertEqual(
            self.sections["talent"].get("preheader", ""),
            "582 of 1,379 verified against a primary document, "
            "from 1,327 companies.")

    def test_the_guard_itself_can_fail(self):
        """A test that cannot fail is not a test. This proves the detector
        fires on the real defect strings before trusting it on our output.

        Both screenshots, verbatim. The 2026-08-19 pair is here because a
        detector proved only against the strings of the FIRST incident is a
        detector proved against the example in front of its author, which is
        the exact shape of failure this file exists to record.
        """
        self.assertEqual(offenders("582 of 1376 verified, from 1324 companies."),
                         ["1376", "1324"])
        self.assertEqual(offenders("0 cuts attributed to AI, 10132 in the US"),
                         ["10132"])
        self.assertEqual(
            offenders("0 cuts attributed to AI, 10132 in the United States"),
            ["10132"])
        self.assertEqual(
            offenders("582 of 1379 verified against a primary document, "
                      "from 1327 companies."),
            ["1379", "1327"])
        self.assertEqual(offenders("1379 hiring signals"), ["1379"])

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


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheMessageThatLeavesTheRelayCarriesNoRawFigure(unittest.TestCase):
    """THE FAR SIDE OF THE BOUNDARY, which nothing used to read.

    The composers hand four strings to digest-api.php. digest_send.py reads
    them back off the wire and digest_layout.py decides what a client is
    actually shown: it JOINS metric fragments into one subject, and it CHOOSES
    a preheader off a three-rung ladder where the site's own snippet is only
    the first rung. Scanning the composer's output proves what the site said.
    It does not prove what the reader gets, and the preheader is the field
    where those two can differ: it travels as its own payload member, appears
    in neither the html nor the text the section-level tests scan, and is
    inserted into the message by render_html at the very end.

    So this assembles the payload the site really returns, runs the real
    usable_sections / subject_line / preheader_text / render_html /
    render_text, and scans the four fields a client displays. Same detector,
    proved on the same strings, one boundary further out.
    """

    @classmethod
    def setUpClass(cls):
        sections = {name: compose(build()) for name, build in FIXTURES}
        cls.payload = {
            "freq": "weekly", "from": "2026-08-10", "to": "2026-08-16",
            "subject": "Tracker digest",
            "manage_url": "https://asktherecruiter.com/blog/manage/",
            "sections": {
                name: {"html": part["html"], "text": part["text"],
                       "preheader": part.get("preheader", ""),
                       "metric": part.get("metric", ""),
                       "minor": bool(part.get("minor"))}
                for name, part in sections.items()},
        }
        cls.wanted = ["layoff", "talent", "articles"]

    def _rendered(self, wanted):
        parts = digest_send.usable_sections(self.payload, wanted)
        self.assertTrue(parts, f"no usable section for {wanted!r}")
        subject = layout.subject_line(self.payload, parts)
        preheader = layout.preheader_text(parts)
        unsub = "https://asktherecruiter.com/blog/u/token/"
        html = layout.render_html(
            parts, subject=subject, preheader=preheader, kicker="Weekly",
            unsub_url=unsub, manage_url=self.payload["manage_url"],
            edition_note=layout.WEEK_CONVENTION)
        text = layout.render_text(
            parts, kicker="Weekly", unsub_url=unsub,
            manage_url=self.payload["manage_url"],
            edition_note=layout.WEEK_CONVENTION)
        return {"subject": subject, "preheader": preheader,
                "html": html, "text": text}

    def test_every_field_of_every_single_list_message(self):
        """One list at a time, which is exactly how the test sends go out.

        DIGEST_TEST_LISTS=talent builds a message from the talent section
        alone, and that message's preheader is the talent preheader with no
        other section able to stand in for it. The owner's second screenshot is
        two such messages.
        """
        for name in self.wanted:
            rendered = self._rendered([name])
            for field, value in sorted(rendered.items()):
                with self.subTest(list=name, field=field):
                    found = offenders(value)
                    self.assertEqual(
                        found, [],
                        f"the {field} of a {name}-only message carries "
                        f"{found!r} with no thousands separator")

    def test_every_field_of_the_combined_message(self):
        rendered = self._rendered(self.wanted)
        for field, value in sorted(rendered.items()):
            with self.subTest(field=field):
                found = offenders(value)
                self.assertEqual(
                    found, [],
                    f"the {field} of the combined message carries {found!r} "
                    f"with no thousands separator")

    def test_the_delivered_preheader_is_the_one_the_site_composed(self):
        """POSITIVE, because "no raw figure" is also true of an empty string.

        preheader_text drops the site's snippet whole when it will not fit and
        falls back to a line with no figure in it at all. That fallback is
        correct behaviour and it is ALSO a silent way for this whole file to
        keep passing while the reader loses the figures. So the delivered
        snippet is compared to the composed one, per list.
        """
        for name in self.wanted:
            with self.subTest(list=name):
                composed = (self.payload["sections"][name]
                            .get("preheader", "")).strip()
                self.assertTrue(composed,
                                f"the {name} composer supplied no snippet, so "
                                f"the reader gets a fallback with no figure")
                self.assertEqual(self._rendered([name])["preheader"], composed)

    def test_the_delivered_talent_preheader_verbatim(self):
        """The string the owner photographed, as it leaves the relay."""
        self.assertEqual(
            self._rendered(["talent"])["preheader"],
            "582 of 1,379 verified against a primary document, "
            "from 1,327 companies.")


class ThePhpAndThePythonAgreeOnHowAFigureLooks(unittest.TestCase):
    """The site formats every figure and the relay formats none, which is the
    rule that makes one spelling possible. This pins both halves."""

    def test_the_layout_module_formats_nothing(self):
        with open(os.path.join(RAILWAY, "digest_layout.py"),
                  encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("{:,}", source,
                         "digest_layout composed a figure, which is the site's "
                         "job and the reason the two surfaces cannot disagree")

    @unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
    def test_the_site_uses_one_formatter_and_not_the_locale(self):
        """number_format_i18n() depends on a $wp_locale this file does not own
        and a filter any plugin may hook, so a figure a reporter may quote does
        not go through it."""
        with open(SUBSCRIBE, encoding="utf-8") as handle:
            source = handle.read()
        code = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        code = re.sub(r"//[^\n]*", "", code)
        self.assertNotIn("number_format_i18n(", code,
                         "a digest figure went through the locale formatter "
                         "again; use alt_digest_number()")
        self.assertIn("function alt_digest_number(", source)

    def test_every_composer_this_file_knows_about_is_scanned(self):
        """THE HOLE THAT LET THE SECOND SCREENSHOT HAPPEN, closed structurally.

        The old input set composed `layoff` and nothing else, and nothing said
        so: two composers existed and no test named them. A fourth composer
        added tomorrow would repeat that exactly, so this reads the composer
        names out of digest-api.php - the one place that decides which sections
        the payload carries - and fails when this file does not build a fixture
        for one of them.
        """
        api = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                           "includes", "digest-api.php")
        with open(api, encoding="utf-8") as handle:
            source = handle.read()
        shipped = set(re.findall(r"'(\w+)'\s*=>\s*'alt_digest_compose_\w+'",
                                 source))
        self.assertTrue(shipped, "no composer map found in digest-api.php")
        self.assertEqual(
            shipped - {name for name, _ in FIXTURES}, set(),
            "digest-api.php ships a composed section this file never renders, "
            "which is the exact shape of the 2026-08-19 blind spot: the "
            "property was right and it was pointed at one composer of three")


if __name__ == "__main__":
    unittest.main()
