"""The collector registries must agree — a source can't be monitored (or report
health) without a health-page label, and a new reporter can't be added silently.

Why this exists: the public health page renders EVERY collector that POSTs to the
source-health ledger, looking each up in `meta{}` in assets/health.js and falling
back to a generic "Operational collector" label when the id is missing. So a
collector added to the pipeline without a `meta{}` entry silently shows up on a
public surface with a bare id — the exact "listed but undescribed" drift a human
is supposed to catch by hand. This test makes that drift fail CI instead.

Two ground truths, both parsed statically:
  * ops_status.py MAX_AGE  — the ingest collectors we actively monitor for
    freshness (each has a staleness ceiling). Every one MUST have a label.
  * literal report_source_health("id", ...) call sites across railway/ — the
    reporters we can see without running the code. Each MUST be either labelled
    in meta{} or explicitly classified below (internal ops telemetry, or a
    collector that reports under a family / runtime-variable id).

Adding a new collector therefore forces one deliberate choice: give it a
health-page label, or classify it here. Neither can be forgotten.
"""
import os
import re
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
OPS_STATUS = os.path.join(RAILWAY, "ops_status.py")
HEALTH_JS = os.path.abspath(os.path.join(
    RAILWAY, "..", "wordpress-plugin", "ai-layoff-tracker", "assets", "health.js"))

# Reporters that intentionally do NOT get their own meta{} label, with the reason.
# Shrinking this set (by adding a real label) is encouraged; growing it silently
# is the thing the test is here to make you think twice about.
KNOWN_UNLABELLED = {
    # Ops / QA telemetry — not public data collectors; the generic label is fine.
    "health_digest": "weekly health-digest tripwire (self-report)",
    "recall_precision": "internal recall/precision QA run",
    "tracker_diff": "internal tracker-diff discovery tripwire",
    "industry_backfill": "internal evidence-only industry backfill",
    # Collectors that report under a family / per-target / runtime-variable id
    # rather than their own module name, so the module-level literal has no
    # standalone meta entry.
    "edgar_historical": "historical EDGAR backfill; live feed is labelled 'edgar'",
    "foreign_filings": "reports per country: edinet_jp / opendart_kr / cvm_br",
    "distress_watchlist": "reports under a per-jurisdiction runtime label",
    "warn_custom_legacy": "legacy custom WARN; 'warn_custom_states' family label",
}


def _meta_keys():
    with open(HEALTH_JS, encoding="utf-8") as fh:
        text = fh.read()
    block = re.search(r"const meta = \{(.*?)\n  \};", text, re.S)
    assert block, "could not locate the meta{} block in health.js"
    keys = re.findall(r"^\s+([a-z0-9_]+):", block.group(1), re.M)
    return keys


def _ops_status_max_age_keys():
    with open(OPS_STATUS, encoding="utf-8") as fh:
        text = fh.read()
    block = re.search(r"MAX_AGE = \{(.*?)\}", text, re.S)
    assert block, "could not locate the MAX_AGE map in ops_status.py"
    return set(re.findall(r'"([a-z0-9_]+)":', block.group(1)))


def _literal_health_reporters():
    ids = set()
    for root, _dirs, files in os.walk(RAILWAY):
        if os.path.basename(root) == "tests":
            continue
        for name in files:
            if not name.endswith(".py"):
                continue
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                src = fh.read()
            ids.update(re.findall(
                r"""report_source_health\(\s*['"]([a-z0-9_]+)['"]""", src))
    return ids


class SourceRegistryParityTest(unittest.TestCase):
    def test_meta_keys_are_unique(self):
        keys = _meta_keys()
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        self.assertFalse(dupes, f"duplicate meta{{}} keys in health.js: {dupes}")

    def test_monitored_sources_have_a_health_label(self):
        meta = set(_meta_keys())
        missing = sorted(_ops_status_max_age_keys() - meta)
        self.assertFalse(missing, (
            f"These sources are monitored for freshness in ops_status.py MAX_AGE "
            f"but have no display label in meta{{}} in assets/health.js: {missing}. "
            f"The health page would show them with the generic 'Operational "
            f"collector' label. Add a meta{{}} entry (and bump ALT_VERSION)."))

    def test_every_reporter_is_labelled_or_classified(self):
        meta = set(_meta_keys())
        unaccounted = sorted(
            _literal_health_reporters() - meta - set(KNOWN_UNLABELLED))
        self.assertFalse(unaccounted, (
            f"These collectors call report_source_health(...) but have neither a "
            f"meta{{}} label nor an entry in KNOWN_UNLABELLED: {unaccounted}. Give "
            f"each a health-page label in assets/health.js, or classify it in "
            f"KNOWN_UNLABELLED with a one-line reason."))

    def test_classified_reporters_are_not_also_labelled(self):
        # If a KNOWN_UNLABELLED id gains a real meta{} label, drop it from the
        # list so the two registries can't disagree about the same id.
        meta = set(_meta_keys())
        both = sorted(meta & set(KNOWN_UNLABELLED))
        self.assertFalse(both, (
            f"These ids are both labelled in meta{{}} and listed in "
            f"KNOWN_UNLABELLED: {both}. Remove them from KNOWN_UNLABELLED."))


if __name__ == "__main__":
    unittest.main()
