"""A blog post is pushed to IndexNow the moment it is published (2.20.235).

The plugin already pinged IndexNow for the tracker surfaces, once a day, when
data lands. The /blog posts themselves (724 of them on 2026-10-12, all in the
sitemap) waited to be crawled. Publishing a post now submits exactly that
one permalink, once per post, non-blocking, through the same key.
"""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
SRC = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")


def _fn(name):
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", SRC, re.S)
    assert m, name + " missing"
    return m.group(0)


class PublishPing(unittest.TestCase):
    def test_hooked_on_status_transition(self):
        self.assertIn("add_action('transition_post_status', 'alt_indexnow_on_publish', 10, 3);", SRC)

    def test_only_first_publish_of_a_public_post(self):
        body = _fn("alt_indexnow_on_publish")
        self.assertIn("$new !== 'publish'", body)
        self.assertIn("$old === 'publish'", body)
        self.assertIn("'post'", body)
        self.assertIn("post_password", body)

    def test_one_url_non_blocking_same_key(self):
        body = _fn("alt_indexnow_submit_urls")
        self.assertIn("'blocking' => false", body)
        self.assertIn("alt_indexnow_key()", body)
        self.assertIn("api.indexnow.org", body)
        self.assertIn("get_permalink", _fn("alt_indexnow_on_publish"))

    def test_daily_ping_reuses_the_submitter(self):
        self.assertIn("alt_indexnow_submit_urls(", _fn("alt_indexnow_ping"))


if __name__ == "__main__":
    unittest.main()
