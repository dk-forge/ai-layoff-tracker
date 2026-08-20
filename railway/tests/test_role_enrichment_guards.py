"""Role-category extraction: fixed vocabulary, evidence gates, bounded queue."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Pure guardrail tests: no API client, no network.
sys.modules.setdefault("openai", SimpleNamespace())
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from extractor import ROLE_CATEGORIES, _sanitize_role_categories
from enrich_roles import build_passage

ROOT = Path(__file__).resolve().parents[2]
WORKER = (ROOT / "railway/enrich_roles.py").read_text()
WORKFLOW = (ROOT / ".github/workflows/enrich-roles.yml").read_text()
DB_PHP = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()
API_PHP = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/api.php").read_text()
CORRECTIONS = (ROOT / ".github/workflows/data-corrections.yml").read_text()


class RoleVocabularyTests(unittest.TestCase):
    def test_model_output_is_filtered_onto_the_fixed_vocabulary(self):
        self.assertEqual(
            _sanitize_role_categories(["Engineering", "engineering", "ceo_whims", 7, "retail_staff"]),
            ["engineering", "retail_staff"],
        )
        self.assertEqual(_sanitize_role_categories("engineering"), [])
        self.assertEqual(_sanitize_role_categories(None), [])

    def test_python_vocabulary_matches_the_php_vocabulary(self):
        for slug in ROLE_CATEGORIES:
            self.assertIn(f"'{slug}'", API_PHP, f"slug {slug} missing from alt_role_categories()")
        # 'unknown' is a stored checked-marker, never a chartable category.
        self.assertNotIn("unknown", ROLE_CATEGORIES)

    def test_worker_reads_only_stored_row_text(self):
        row = {
            "roles": "customer support",
            "excerpt": "The company said support teams were affected.",
            "ai_language": None,
            "announcement_evidence": "",
            "source_url": "https://example.com/article",
        }
        passage = build_passage(row)
        self.assertIn("customer support", passage)
        self.assertIn("support teams were affected", passage)
        # No fetch path exists in the worker at all.
        self.assertNotIn("requests.get(row", WORKER)
        self.assertNotIn("fetch_text", WORKER)


class RoleWorkerGuards(unittest.TestCase):
    def test_scheduled_work_has_a_safe_batch_and_deadline(self):
        self.assertIn("ROLES_BATCH: ${{ github.event.inputs.batch || '40' }}", WORKFLOW)
        self.assertIn("ROLES_DEADLINE_SECONDS: '900'", WORKFLOW)
        self.assertIn("OPENROUTER_TIMEOUT_SECONDS: '35'", WORKFLOW)
        self.assertIn("timeout-minutes: 20", WORKFLOW)

    def test_worker_stops_between_rows_and_fails_loudly(self):
        self.assertIn("ROLES_DEADLINE_SECONDS", WORKER)
        self.assertIn("time.monotonic() - started_at >= DEADLINE_SECONDS", WORKER)
        self.assertIn("stopping safely after", WORKER)
        self.assertIn("return 1 if checked and model_failures == checked", WORKER)

    def test_model_failure_leaves_the_row_queued_not_marked_unknown(self):
        self.assertIn("model_failures += 1\n                continue", WORKER)


class ServerSideGuards(unittest.TestCase):
    def test_endpoint_only_fills_blank_categories_and_requires_evidence(self):
        self.assertIn("if ((string) $row->role_categories !== '') { $out['rejected'][] = $id; continue; }", DB_PHP)
        self.assertIn("if ($real && strlen($evidence) < 12)", DB_PHP)

    def test_endpoint_never_pins_rows_or_touches_facts(self):
        handler = DB_PHP.split("function alt_api_enrich_roles", 1)[1].split("\nfunction ", 1)[0]
        for forbidden in ("alt_suppress_hash", "'edited'", "job_count", "layoff_date", "ai_causation", "dedup_hash"):
            self.assertNotIn(forbidden, handler)

    def test_unknown_marker_is_excluded_from_public_surfaces(self):
        self.assertIn("role_categories NOT IN ('', ',unknown,')", DB_PHP)
        self.assertIn("array_diff(alt_db_unpack_tags($row->role_categories ?? ''), array('unknown'))", DB_PHP)

    def test_enrich_roles_is_on_the_corrections_allowlist(self):
        self.assertIn('"enrich-roles"', CORRECTIONS)


if __name__ == "__main__":
    unittest.main()
