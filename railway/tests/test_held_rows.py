"""The held-rows store (2026-11-18): a row a guard cannot decide is stored as
an unpublished WordPress post, reviewed by two referees, then released or
trashed. It must never reach a public surface and never count as seen."""
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import review_held  # noqa: E402
import wp_poster  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
API = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/api.php").read_text(encoding="utf-8")
DB = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text(encoding="utf-8")


def _fn(src, name):
    start = src.index(f"function {name}(")
    nxt = src.find("\nfunction ", start + 10)
    return src[start:nxt if nxt > 0 else len(src)]


class HeldRowLandsInTheQueue(unittest.TestCase):
    def test_add_stores_a_held_row_as_a_pending_post(self):
        add = _fn(API, "alt_api_add")
        self.assertIn("'post_status' => $held_reason !== '' ? 'pending' : 'publish'", add)
        self.assertIn("update_post_meta($post_id, 'held_reason', $held_reason);", add)

    def test_held_row_returns_before_the_table_mirror_and_report_attach(self):
        add = _fn(API, "alt_api_add")
        ret = add.index("'held' => true")
        self.assertLess(ret, add.index("alt_db_sync_post($post_id)"))
        self.assertLess(ret, add.rindex("alt_event_register_report_for_layoff($layoff_id"))

    def test_held_row_never_attaches_to_a_published_event(self):
        add = _fn(API, "alt_api_add")
        self.assertIn("if ($held_reason === '' && alt_hash_exists($dedup_hash))", add)
        self.assertIn("if ($held_reason === '' && $incoming_source !== 'warn' && ($match_id = alt_fuzzy_dupe_exists(", add)

    def test_the_queue_lists_pending_posts_with_a_reason(self):
        lst = _fn(API, "alt_api_held_list")
        self.assertIn("'post_status' => 'pending'", lst)
        self.assertIn("'key' => 'held_reason'", lst)
        self.assertIn("'/held'", API)

    def test_release_publishes_and_mirrors_trash_suppresses(self):
        dec = _fn(API, "alt_api_held_decide")
        self.assertIn("'post_status' => 'publish'", dec)
        self.assertIn("alt_db_sync_post($pid)", dec)
        self.assertIn("alt_suppress_hash(", dec)
        self.assertIn("alt_fuzzy_dupe_exists(", dec)


class HeldRowIsNotSeenOrPublic(unittest.TestCase):
    def test_only_published_posts_reach_the_table(self):
        sync = _fn(DB, "alt_db_sync_post")
        self.assertIn("get_post_status($post_id) !== 'publish'", sync)
        self.assertIn("alt_db_delete_by_post($post_id)", sync)

    def test_seen_urls_reads_only_the_table_and_reports(self):
        seen = _fn(DB, "alt_api_seen_urls")
        self.assertNotIn("wp_posts", seen)
        self.assertNotIn("WP_Query", seen)
        self.assertIn("alt_db_table()", seen)


class PosterSendsAndReportsTheHold(unittest.TestCase):
    def _post(self, body):
        resp = SimpleNamespace(status_code=201, json=lambda: body, text="")
        with mock.patch.dict("os.environ", {"WP_SITE_URL": "https://example.test", "WP_API_KEY": "k"}), \
             mock.patch.object(wp_poster.requests, "post", return_value=resp) as post:
            status = wp_poster.post_to_wordpress({
                "company_name": "Microsoft", "job_count": 60000, "layoff_date": "2026-11-13",
                "dedup_hash": "0" * 32, "held_reason": "negation: test"})
        return status, post.call_args.kwargs["json"]

    def test_held_reason_is_sent_and_a_held_201_is_not_posted(self):
        status, payload = self._post({"id": 1, "created": True, "held": True})
        self.assertEqual(payload["meta"]["held_reason"], "negation: test")
        self.assertEqual(status, "held")

    def test_plain_201_is_posted(self):
        status, _ = self._post({"id": 1, "created": True})
        self.assertEqual(status, "posted")


class RefereeOutcome(unittest.TestCase):
    def test_agreement_decides_anything_else_stays_held(self):
        self.assertEqual(review_held.decision_for("agree", "keep"), "release")
        self.assertEqual(review_held.decision_for("agree", "trash"), "trash")
        self.assertIsNone(review_held.decision_for("agree", "edit"))
        self.assertIsNone(review_held.decision_for("disagree", "keep"))
        self.assertIsNone(review_held.decision_for("unknown", "keep"))


class TheWorkflowExists(unittest.TestCase):
    def test_review_held_workflow_runs_the_script(self):
        wf = (ROOT / ".github/workflows/review-held.yml").read_text(encoding="utf-8")
        self.assertIn("python review_held.py", wf)
        self.assertTrue(re.search(r"timeout-minutes:\s*\d+", wf))


if __name__ == "__main__":
    unittest.main()
