"""Two senders, one subject line, and it carries the date.

WHAT WENT OUT ON 2026-08-18.

    [AskTheRecruiter] Daily tracker digest

No date in it at all, over a body that said August 17-18, 2026. A digest
whose entire doctrine is that every figure names its own window shipped the
one line a reader sees first with no window on it, and a mailbox holding a
month of them cannot tell one from another. It is also the line that decides
whether the message is opened.

THERE ARE TWO SENDERS AND THEY DID NOT AGREE.

railway/digest_send.py relays through Brevo and composes its subject in
digest_layout.subject_line(), which names the trackers and dates the window.
alt_digest_send() in includes/subscribe.php is the in-WordPress wp_mail
sender, which takes over whenever the relay has not claimed the tier (see
alt_digest_external_active), and it composed "[AskTheRecruiter] Daily tracker
digest" itself. Which subject a subscriber got depended on which process
happened to be sending. That is not something a reader should be able to
notice, and the dateless one is the one that reached the owner.

So the PHP side is now a port of the Python function, and this file drives
BOTH implementations over the same inputs and fails on any difference. It is
the whole point: two implementations of one string stay equal only if
something checks.

Without php on PATH the cross-language cases SKIP, which is not a pass. The
Python-only assertions still run.
"""
import json
import os
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

import digest_layout as layout            # noqa: E402

PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes")
SUBSCRIBE = os.path.join(PLUGIN, "subscribe.php")
DIGEST_API = os.path.join(PLUGIN, "digest-api.php")
PHP = shutil.which("php")

# The functions under test touch no WordPress API except number formatting and
# esc_html, so they are lifted out of the file and evaluated rather than the
# whole plugin being booted. Extracting by name keeps this honest: if somebody
# renames one, this fails loudly rather than testing a stale copy.
_WANTED = ("alt_digest_date_range", "alt_digest_period_phrase",
           "alt_digest_iso_week", "alt_digest_week_label",
           "alt_digest_week_id", "alt_digest_edition_label",
           "alt_digest_valid_freq",
           "alt_digest_chars", "alt_digest_subject_line",
           "alt_digest_section_heading", "alt_digest_fallback_subject")

_RUNNER = r"""
$src = file_get_contents($argv[1]);
foreach (explode(',', $argv[2]) as $name) {
    if (!preg_match('/\nfunction ' . preg_quote($name, '/') . '\s*\(.*?\n\}/s',
                    $src, $m)) {
        fwrite(STDERR, "could not extract $name from subscribe.php\n");
        exit(2);
    }
    eval($m[0]);
}
$in = json_decode($argv[3], true);
echo json_encode(array(
    'subject'  => alt_digest_subject_line($in['freq'], $in['from'], $in['to'],
                                          $in['headings'], $in['fallback'],
                                          $in['parts']),
    'fallback' => alt_digest_fallback_subject($in['freq'], $in['to']),
    'heading'  => alt_digest_section_heading($in['section_text']),
));
"""


def php_subject(freq, to, headings, fallback, section_text="", frm="",
                parts=None):
    handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                         encoding="utf-8")
    try:
        handle.write("<?php\n" + _RUNNER)
        handle.close()
        payload = json.dumps({"freq": freq, "from": frm or to, "to": to,
                              "headings": headings, "fallback": fallback,
                              "parts": parts or [],
                              "section_text": section_text})
        run = subprocess.run([PHP, handle.name, SUBSCRIBE, ",".join(_WANTED),
                              payload],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"php runner failed: {run.stderr[:1200]}")
    return json.loads(run.stdout)


def python_subject(freq, to, headings, fallback, frm="", parts=None):
    """digest_layout.subject_line, driven through the shape it really takes."""
    payload = {"from": frm or to, "to": to, "freq": freq, "subject": fallback}
    # A section that cannot name itself has an EMPTY text part, which is the
    # real shape: the composers return nothing rather than a nameless section.
    metrics = list(parts or [])
    built = []
    for index, name in enumerate(headings):
        one = metrics[index] if index < len(metrics) else {}
        built.append((name, "<p>x</p>",
                      (name + "\nsomething\n") if name else "", "",
                      (str(one.get("metric", "")), bool(one.get("minor")))))
    return layout.subject_line(payload, built)


# The cases, chosen to cover every branch on both sides rather than to be
# realistic: one section, three sections, a weekly window, a window this cannot
# read at all, a section that cannot name itself, and a set of names long
# enough to blow the 78-character ceiling twice over.
# The cases, chosen to cover every branch on both sides rather than to be
# realistic: one section, three sections, a real ISO week, a window this cannot
# read at all, a section that cannot name itself, and a set of names long
# enough to blow the 78-character ceiling twice over. Each is (freq, from, to,
# headings): the window needs BOTH ends now, because a weekly subject carries
# the ISO week number of its first day and the dates it covers.
#
# THE LAST TWO ARE ISO YEAR BOUNDARIES and they are the reason this file has to
# carry them. December 28, 2026 - January 3, 2027 is week 53 of ISO year 2026,
# and December 31, 2029 falls in week 1 of ISO year 2030. A implementation that
# reads the calendar year beside the ISO week is wrong for a few days a year,
# ships silently, and is found the following January.
CASES = (
    ("daily",  "2026-08-17", "2026-08-18", ["AI Layoff Tracker"]),
    ("daily",  "2026-08-17", "2026-08-18", ["AI Layoff Tracker", "Talent Intelligence Tracker"]),
    ("daily",  "2026-08-17", "2026-08-18", ["AI Layoff Tracker", "Talent Intelligence Tracker",
                                            "From the blog"]),
    ("weekly", "2026-08-10", "2026-08-16", ["AI Layoff Tracker", "From the blog"]),
    ("weekly", "2026-08-10", "2026-08-16", ["AI Layoff Tracker"]),
    ("daily",  "2026-08-17", "2026-08-18", []),
    ("daily",  "2026-08-17", "2026-08-18", ["", "From the blog"]),
    ("daily",  "not-a-date", "not-a-date", ["AI Layoff Tracker"]),
    ("weekly", "2026-08-10", "not-a-date", ["AI Layoff Tracker"]),
    ("daily",  "2026-01-01", "2026-01-01", ["A tracker with a very long name indeed",
                                            "Another tracker with an equally long name",
                                            "And a third one for good measure"]),
    ("weekly", "2026-12-28", "2027-01-03", ["From the blog"]),
    ("weekly", "2029-12-31", "2030-01-06", ["AI Layoff Tracker"]),
)

FALLBACK = "[AskTheRecruiter] Daily tracker digest, August 18, 2026"


@unittest.skipUnless(PHP, "php is not on PATH")
class TheTwoSendersComposeTheSameSubject(unittest.TestCase):

    def test_every_case_agrees(self):
        for freq, frm, to, headings in CASES:
            with self.subTest(freq=freq, frm=frm, to=to, headings=headings):
                # A metric fragment per heading, so the combined form, the
                # single-metric form and the no-metric fallback are all driven
                # on both sides rather than only the last of the three.
                parts = [{"metric": m, "minor": mi}
                         for m, mi in (("16,842 verified job cuts", False),
                                       ("1,376 hiring signals", False),
                                       ("2 new posts", True))][:len(headings)]
                php = php_subject(freq, to, headings, FALLBACK, frm=frm,
                                  parts=parts)["subject"]
                py = python_subject(freq, to, headings, FALLBACK, frm=frm,
                                    parts=parts)
                self.assertEqual(php, py,
                                 "the wp_mail sender and the relay would put "
                                 "different subjects on the same digest")

    def test_the_section_heading_is_read_the_same_way(self):
        text = "\n\n  indented first\nFrom the blog\nsomething else\n"
        php = php_subject("daily", "2026-08-18", [], FALLBACK,
                          section_text=text)["heading"]
        self.assertEqual(php, layout.section_heading(text))


@unittest.skipUnless(PHP, "php is not on PATH")
class TheSubjectCarriesTheDateOnEveryPath(unittest.TestCase):
    """Including the fallback, which is still a subject somebody receives."""

    def test_the_composed_subject_dates_the_window(self):
        out = php_subject("daily", "2026-08-18", ["AI Layoff Tracker"], FALLBACK,
                          frm="2026-08-17")
        self.assertEqual(out["subject"], "AI Layoff Tracker, August 18, 2026")

    def test_weekly_says_which_week_by_number_and_by_date(self):
        """"the week to August 17, 2026" was a rolling seven days ending on the
        send day, which is a window that belongs to no week anybody
        recognises. It is an ISO week now, and the number never travels
        without the dates that let a reader check it."""
        out = php_subject("weekly", "2026-08-16", ["AI Layoff Tracker"], FALLBACK,
                          frm="2026-08-10")
        self.assertEqual(out["subject"],
                         "AI Layoff Tracker, Week 33 · August 10-16, 2026")

    def test_the_iso_year_is_not_the_calendar_year(self):
        """January 1, 2027 sits in week 53 of ISO year 2026, and this is the
        defect that ships silently and is found the following January."""
        out = php_subject("weekly", "2027-01-03", ["AI Layoff Tracker"], FALLBACK,
                          frm="2026-12-28")
        self.assertEqual(out["subject"],
                         "AI Layoff Tracker, Week 53 · December 28, 2026 - January 3, 2027")
        out = php_subject("weekly", "2030-01-06", ["AI Layoff Tracker"], FALLBACK,
                          frm="2029-12-31")
        self.assertIn("Week 1 \u00b7", out["subject"])

    def test_the_fallback_is_dated_too(self):
        out = php_subject("daily", "2026-08-18", [], FALLBACK)
        self.assertEqual(out["fallback"],
                         "[AskTheRecruiter] Daily tracker digest, August 18, 2026")
        self.assertEqual(out["subject"], out["fallback"],
                         "no section could name itself, so the dated fallback "
                         "is what goes out")

    def test_only_one_place_in_the_plugin_spells_a_subject_at_all(self):
        """The literal lives in alt_digest_fallback_subject and nowhere else.

        A composed subject is checked above. This catches the other way the
        dateless line could come back: somebody writing the string again at a
        send site, which is exactly how the two senders drifted apart in the
        first place.
        """
        src = open(SUBSCRIBE, encoding="utf-8").read()
        self.assertEqual(src.count("' tracker digest'"), 1,
                         "subscribe.php spells a digest subject somewhere "
                         "other than alt_digest_fallback_subject")
        body = src.split("function alt_digest_fallback_subject")[1].split("\n}")[0]
        self.assertIn("' tracker digest'", body)
        self.assertIn("wp_mail($row['email'], $subject,", src,
                      "the wp_mail sender must send the composed subject")

        api = open(DIGEST_API, encoding="utf-8").read()
        self.assertNotIn("tracker digest", api,
                         "digest-api.php must ask alt_digest_fallback_subject "
                         "rather than spelling its own")
        self.assertIn("alt_digest_fallback_subject($freq, $to_date)", api)


class TheRelayStillFallsBackToWhatTheSiteSent(unittest.TestCase):
    """Python-only, so it runs with or without php."""

    def test_an_unreadable_window_keeps_the_sites_subject(self):
        self.assertEqual(
            python_subject("daily", "nonsense", ["AI Layoff Tracker"], FALLBACK),
            FALLBACK)

    def test_a_section_that_cannot_name_itself_is_skipped(self):
        self.assertEqual(
            python_subject("daily", "2026-08-18", ["", "From the blog"], FALLBACK),
            "From the blog, August 18, 2026")


if __name__ == "__main__":
    unittest.main()
