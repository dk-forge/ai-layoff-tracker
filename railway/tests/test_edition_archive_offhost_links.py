"""The archive publishes every section, with off-host links unlinked.

On 2026-08-20 the talent section gained a link per hiring signal and on
2026-08-25 the layoff section gained a source link per biggest cut. The
archive's publication gate admits no host but our own, so from those dates
every daily edition archived the blog section alone, and the only trace was a
WordPress error_log line nobody reads. Found 2026-09-05 when the 09-05 daily
page showed one section for a send that composed three.

These pin the repair: a section carrying an off-host link becomes a copy whose
anchors are plain text naming the outlet, that copy passes the gate, our own
links are untouched, and the other rules still refuse what they refused.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PLUGIN = os.path.join(HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker")
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
ARCHIVE = os.path.join(PLUGIN, "includes", "digest-archive.php")
HARNESS = os.path.join(HERE, "fixtures", "edition_archive_harness.php")
PHP = shutil.which("php")
SITE = "https://asktherecruiter.com/blog"


def rewrite(pairs):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump({"rewrite": pairs}, handle)
        handle.close()
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, ARCHIVE, handle.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr[:1500]}")
    return json.loads(run.stdout)["rewrite"]


def composed_section():
    import test_digest_link_basis as basis
    return basis.compose(basis.fixture())


OFF = "https://www.example-outlet.test/news/story-one"


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class OffHostLinksBecomePlainOutletText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sec = composed_section()
        cls.html = sec["html"] + f'<p data-alt="source"><a href="{OFF}">Source</a></p>'
        cls.text = sec["text"] + f"\nSource: {OFF}\n"

    def test_the_real_section_with_a_source_link_is_now_publishable(self):
        out = rewrite({"s": {"html": self.html, "text": self.text}})["s"]
        self.assertTrue(out["gate"]["ok"], out["gate"]["rule"])

    def test_the_anchor_is_unlinked_and_names_the_outlet(self):
        out = rewrite({"s": {"html": self.html, "text": self.text}})["s"]
        self.assertNotIn(OFF, out["html"])
        self.assertIn("Source (example-outlet.test)", out["html"])
        self.assertNotIn(OFF, out["text"])
        self.assertIn("Source: example-outlet.test", out["text"])

    def test_our_own_links_are_untouched(self):
        own = f'<a href="{SITE}/layoff/has-a-page/">Has A Page</a>'
        out = rewrite({"s": {"html": own, "text": f"{SITE}/layoff/has-a-page/"}})["s"]
        self.assertEqual(out["html"], own)
        self.assertEqual(out["text"], f"{SITE}/layoff/has-a-page/")

    def test_a_label_that_already_names_the_host_is_not_doubled(self):
        out = rewrite({"s": {"html": f'<a href="{OFF}">example-outlet.test</a>', "text": ""}})["s"]
        self.assertEqual(out["html"], "example-outlet.test")

    def test_the_other_rules_still_refuse(self):
        addr = {"html": self.html + "<p>reader@example.test</p>", "text": self.text}
        token = {"html": self.html + f'<p><a href="{SITE}/ai-layoff-tracker/unsubscribe/{"a" * 64}/">x</a></p>',
                 "text": self.text}
        out = rewrite({"addr": addr, "token": token})
        self.assertFalse(out["addr"]["gate"]["ok"])
        self.assertIn("address", out["addr"]["gate"]["rule"])
        self.assertFalse(out["token"]["gate"]["ok"])

    def test_a_section_with_no_links_is_byte_identical(self):
        out = rewrite({"s": {"html": "<p data-alt=\"unit\">3 signals</p>", "text": "3 signals"}})["s"]
        self.assertEqual(out["html"], "<p data-alt=\"unit\">3 signals</p>")
        self.assertEqual(out["text"], "3 signals")


if __name__ == "__main__":
    unittest.main()


class TheCaptureUsesTheCopy(unittest.TestCase):
    """The function above is only a repair if capture calls it BEFORE the gate
    and stores what it returns. Read from the source, since capture needs a
    database this suite does not stand up."""

    def test_capture_rewrites_before_it_judges(self):
        with open(ARCHIVE, encoding="utf-8") as fh:
            src = fh.read()
        start = src.index("function alt_edition_capture(")
        body = src[start:src.index("\n}\n", start)]
        copy_at = body.find("alt_edition_publishable_copy(")
        gate_at = body.find("alt_edition_public_safe(")
        self.assertGreater(copy_at, 0, "capture never makes the publishable copy")
        self.assertLess(copy_at, gate_at, "the gate must judge the copy, not the original")
