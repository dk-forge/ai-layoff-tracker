"""No file may name Bluehost as the current host.

DK 2026-11-19: the web host is ChemiCloud (since about Aug 2026). Bluehost is
not used. Sessions kept repeating Bluehost because stale text said it.

Only dated history may still mention it: incident narratives in TECHLOG,
HANDOFF and code comments that explain a guard by the outage that caused it.
Those files are allow-listed below. Do not add a path to make this pass:
write ChemiCloud (or "the WordPress host") instead. Shrinking the list is fine.
"""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

HISTORY_ALLOWLIST = frozenset({
    ".github/workflows/alert-drain.yml",
    ".github/workflows/ci-alert.yml",
    ".github/workflows/deploy-plugin.yml",
    "CLAUDE.md",
    "docs/ARCHITECTURE.md",
    "docs/HANDOFF.md",
    "docs/LEGACY-hello-dolly-css.md",
    "docs/RUNBOOK.md",
    "docs/TECHLOG.md",
    "docs/recall-reference-sets/US-WARN-RESULTS-2026-08.md",
    "railway/alert_outbox.py",
    "railway/ci_alert.py",
    "railway/deferral_ledger.py",
    "railway/endpoint_check.py",
    "railway/gh_fallback.py",
    "railway/historical_news_sweep.py",
    "railway/host_call.py",
    "railway/http_retry.py",
    "railway/mail_auth_check.py",
    "railway/ops_status.py",
    "railway/opsmail.py",
    "railway/reader_freshness.py",
    "railway/recall_goldset.py",
    "railway/rolling_recall.py",
    "railway/subscriber_backup.py",
    "railway/tests/test_alert_outbox.py",
    "railway/tests/test_ci_alert.py",
    "railway/tests/test_current_host_documentation.py",
    "railway/tests/test_deploy_reaches_readers.py",
    "railway/tests/test_digest_brevo_feedback.py",
    "railway/tests/test_historical_sweep_cursor.py",
    "railway/tests/test_host_call_deferral.py",
    "railway/tests/test_no_bluehost_outside_history.py",
    "railway/tests/test_ops_mail_split.py",
    "railway/tests/test_rolling_recall.py",
    "railway/warn_import.py",
    "railway/warn_reference_set.py",
    "wordpress-plugin/ai-layoff-tracker/includes/db.php",
    "wordpress-plugin/ai-layoff-tracker/includes/digest-api.php",
    "wordpress-plugin/ai-layoff-tracker/includes/htaccess.php",
    "wordpress-plugin/ai-layoff-tracker/includes/subscriber-backup.php",
})


def files_mentioning_bluehost():
    out = subprocess.run(
        ["git", "grep", "-l", "-i", "-I", "bluehost"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if out.returncode not in (0, 1):
        raise AssertionError(out.stderr)
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


class NoBluehostOutsideHistory(unittest.TestCase):
    def test_bluehost_only_in_dated_history(self):
        offenders = sorted(files_mentioning_bluehost() - HISTORY_ALLOWLIST)
        self.assertEqual(offenders, [], "web host is ChemiCloud (DK 2026-11-19)")

    def test_allowlist_paths_exist(self):
        missing = sorted(p for p in HISTORY_ALLOWLIST if not (ROOT / p).exists())
        self.assertEqual(missing, [], "remove stale allow-list entries")


if __name__ == "__main__":
    unittest.main()
