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
HEALTH_DIGEST = os.path.join(RAILWAY, "health_digest.py")
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
    "ingest_post": "posting-pipeline tripwire; only emits 'degraded' on a broad post outage",
    # Collectors that report under a family / per-target / runtime-variable id
    # rather than their own module name, so the module-level literal has no
    # standalone meta entry.
    "foreign_filings": "reports per country: edinet_jp / opendart_kr / cvm_br",
    "distress_watchlist": "reports under a per-jurisdiction runtime label",
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


def _health_digest_max_age():
    """{id: ceiling} from health_digest.py MAX_AGE_DAYS, plus its default."""
    with open(HEALTH_DIGEST, encoding="utf-8") as fh:
        text = fh.read()
    block = re.search(r"MAX_AGE_DAYS = \{(.*?)\}", text, re.S)
    assert block, "could not locate MAX_AGE_DAYS in health_digest.py"
    default = re.search(r"^DEFAULT_MAX_AGE\s*=\s*(\d+)", text, re.M)
    assert default, "could not locate DEFAULT_MAX_AGE in health_digest.py"
    return ({k: int(v) for k, v in re.findall(r'"([a-z0-9_]+)":\s*(\d+)', block.group(1))},
            int(default.group(1)))


def _ops_status_max_age():
    """{id: ceiling} from ops_status.py MAX_AGE."""
    with open(OPS_STATUS, encoding="utf-8") as fh:
        block = re.search(r"MAX_AGE = \{(.*?)\}", fh.read(), re.S)
    assert block, "could not locate the MAX_AGE map in ops_status.py"
    return {k: int(v) for k, v in re.findall(r'"([a-z0-9_]+)":\s*(\d+)', block.group(1))}


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


WORKFLOWS = os.path.abspath(os.path.join(RAILWAY, "..", ".github", "workflows"))


def _worst_gap_days(cron):
    """Longest legitimate gap, in days, between two runs of one cron line.

    Deliberately coarse and deliberately an OVER-estimate of the cadence, never
    an under-estimate: this feeds a test that fails when a ceiling is TIGHTER
    than the cadence, so guessing a job runs more often than it does is the
    direction that manufactures a false failure.
    """
    fields = cron.split()
    if len(fields) != 5:
        return None
    _minute, _hour, dom, month, dow = fields
    if month != "*":                      # quarterly and friends: not swept here
        return None
    if dom != "*":                        # "the 1st", "the 6th": monthly
        return 31 if dom.isdigit() else None
    if dow != "*":                        # weekly, or n days a week
        days = [d for d in dow.split(",") if d.strip()]
        return 7 if len(days) == 1 else (7 // max(len(days), 1)) + 1
    return 1                              # daily or more often


def _workflow_cadences():
    """{health id: (worst gap in days, workflow file)} for what we can derive.

    A workflow's cron gives the cadence; the modules it runs give the health ids
    it posts under. Anything this cannot resolve statically (a runtime id, a
    PHP-side reporter, a manual-dispatch-only job) is simply absent, which is
    the honest answer for a static sweep — absence here is "not swept", not
    "fine".
    """
    out = {}
    for name in sorted(os.listdir(WORKFLOWS)):
        if not name.endswith((".yml", ".yaml")):
            continue
        with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as fh:
            text = fh.read()
        crons = re.findall(r"^\s*-\s*cron:\s*'([^']+)'", text, re.M)
        gaps = [g for g in (_worst_gap_days(c) for c in crons) if g]
        if not gaps:
            continue
        gap = min(gaps)                   # several schedules: the job runs on the tightest
        for mod in set(re.findall(r"python3?\s+(?:railway/)?([a-z0-9_]+)\.py", text)):
            path = os.path.join(RAILWAY, f"{mod}.py")
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            ids = set(re.findall(
                r"""report_source_health\(\s*['"]([a-z0-9_]+)['"]""", src))
            ids.update(re.findall(r"""^HEALTH_ID\s*=\s*['"]([a-z0-9_]+)['"]""",
                                  src, re.M))
            for src_id in ids:
                prev = out.get(src_id)
                # A source posted by two jobs is as fresh as the FASTER one.
                if prev is None or gap < prev[0]:
                    out[src_id] = (gap, name)
    return out


class StalenessCeilingsMatchTheRealCadence(unittest.TestCase):
    """A ceiling a job cannot meet is not a monitor, it is permanent noise.

    Three instances of this one defect have now been fixed by hand: `newsapi`
    at 2 days against a weekly job, `federal_rif` missing from health_digest so
    a monthly job fell through DEFAULT_MAX_AGE = 10, and `source_audit` (fixed
    2026-08-15) with no entry in EITHER map against a monthly workflow — STALE
    for roughly two weeks in every three, every month, since it shipped.

    Three is a class, not three instances, so this closes it: the cadence is
    read from the workflow's own cron and the ceiling must cover it. A source
    this cannot resolve statically is left out rather than guessed at.
    """

    def test_no_monitored_source_has_a_ceiling_tighter_than_its_cadence(self):
        cadences = _workflow_cadences()
        self.assertIn("source_audit", cadences,
                      "the sweep stopped seeing the source it was written for")
        ops = _ops_status_max_age()
        digest, default = _health_digest_max_age()
        problems = []
        for src, (gap, workflow) in sorted(cadences.items()):
            # ops_status only judges what it lists; the digest applies
            # DEFAULT_MAX_AGE to every id in the ledger, so its effective
            # ceiling is never absent — that is the federal_rif defect.
            for where, ceiling in (("ops_status.MAX_AGE", ops.get(src)),
                                   ("health_digest.MAX_AGE_DAYS",
                                    digest.get(src, default))):
                if ceiling is None:
                    continue
                if ceiling < gap:
                    problems.append(
                        f"{src}: {where} allows {ceiling}d but {workflow} can leave "
                        f"{gap}d between runs")
        self.assertFalse(problems, (
            f"These ceilings are tighter than the job's own cron cadence, so they "
            f"report STALE on a healthy job: {problems}. Raise the ceiling to the "
            f"real cadence (longest gap + a few days of slack) and put the "
            f"derivation in the comment."))

    def test_the_monthly_audit_ceiling_is_derived_not_guessed(self):
        """31 (longest month) + 4 days of slack, the federal_rif arithmetic."""
        ops = _ops_status_max_age()
        digest, _default = _health_digest_max_age()
        self.assertEqual(ops.get("source_audit"), 35)
        self.assertEqual(digest.get("source_audit"), 35)
        self.assertEqual(_worst_gap_days("0 13 1 * *"), 31)


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

    def test_staleness_ceilings_agree_across_the_two_monitors(self):
        """ops_status.py and health_digest.py must not disagree about a ceiling.

        Both files carry a comment saying they match the other, and on
        2026-08-02 they did not: federal_rif was 35 in ops_status (correct — the
        importer is a MONTHLY workflow) and absent here, so the digest applied
        DEFAULT_MAX_AGE and called it STALE from day 11 of every month onward.
        A ceiling a job cannot meet is not a monitor, it is permanent noise —
        the same defect the retired `newsapi` id caused, and the reason a real
        breakage can sit unnoticed among the amber.
        """
        ops = _ops_status_max_age()
        digest, default = _health_digest_max_age()
        conflicts = sorted(
            f"{k}: ops_status={ops[k]}d vs health_digest={digest[k]}d"
            for k in set(ops) & set(digest) if ops[k] != digest[k])
        self.assertFalse(conflicts, (
            f"The two staleness monitors disagree: {conflicts}. They are meant "
            f"to be one definition — reconcile them to the job's REAL cadence."))
        # A ceiling present in ops_status but missing here silently becomes
        # DEFAULT_MAX_AGE in the digest, which is the federal_rif defect. Only
        # flag it when the default is actually TIGHTER than the declared
        # ceiling, i.e. when the omission can manufacture a false STALE.
        implicit = sorted(
            f"{k}: declared {ops[k]}d, digest would use {default}d"
            for k in set(ops) - set(digest) if ops[k] > default)
        self.assertFalse(implicit, (
            f"These sources are monitored in ops_status.py with a ceiling LOOSER "
            f"than health_digest's DEFAULT_MAX_AGE ({default}d), but are missing "
            f"from MAX_AGE_DAYS: {implicit}. The digest will report them STALE "
            f"on a normal cadence. Add them to health_digest.MAX_AGE_DAYS."))

    def test_classified_reporters_are_not_also_labelled(self):
        # If a KNOWN_UNLABELLED id gains a real meta{} label, drop it from the
        # list so the two registries can't disagree about the same id.
        meta = set(_meta_keys())
        both = sorted(meta & set(KNOWN_UNLABELLED))
        self.assertFalse(both, (
            f"These ids are both labelled in meta{{}} and listed in "
            f"KNOWN_UNLABELLED: {both}. Remove them from KNOWN_UNLABELLED."))


class EveryDeclaredCollectorHasCodeBehindIt(unittest.TestCase):
    """The other direction, which was open for thirteen months.

    Everything above guards reporter -> label: a collector that POSTs health
    must be described. Nothing guarded label -> reporter, so a label could be
    written for a collector that was never built, and that is what happened.

    `earnings_ingest` was added to `meta{}` in 2.19.84 (2026-07-21, "surface the
    4 new collectors on both public pages") describing daily earnings-call
    transcripts. In the SAME batch the transcript ingest was dropped, because
    the transcript endpoint answered HTTP 402 — paid-only. The module was never
    written, no workflow ever ran it, `cron.py` never referenced it. The label
    outlived the intent, and `source_inventory.never_reported` correctly
    reported a collector with no health row at every session start for thirteen
    months. That signal was TRUE and unresolvable: no amount of investigating a
    broken collector can fix a collector that does not exist.

    The bar here is the weakest one that still closes the class: the id must be
    named by at least one file that runs. Passing it is nearly free for a real
    collector and impossible for a label with nothing behind it.
    """

    def test_no_meta_label_names_a_collector_that_does_not_exist(self):
        import sys
        sys.path.insert(0, RAILWAY)
        import source_inventory

        orphans = source_inventory.unimplemented_collectors()
        self.assertFalse(sorted(orphans), (
            f"These ids are declared in meta{{}} in assets/health.js but are "
            f"named by NO python module, workflow or data file in this repo: "
            f"{sorted(orphans)}. A meta{{}} entry is a public promise that a "
            f"collector exists, and the inventory will report it NEVER REPORTED "
            f"forever because there is nothing to report. Either build the "
            f"collector, or delete the label and record the decision in "
            f"docs/TECHLOG.md."))

    def test_the_scan_can_actually_fail(self):
        """A guard that cannot fail has not been tested.

        Feeds the real function a registry containing one id that certainly
        appears nowhere, and requires it to be named. Without this, deleting
        the corpus walk would leave a permanently-green test.
        """
        import sys
        import tempfile
        sys.path.insert(0, RAILWAY)
        import source_inventory

        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as fh:
            fh.write("  const meta = {\n"
                     "    edgar: ['a real one'],\n"
                     "    zzz_never_built_collector: ['a label with no code'],\n"
                     "  };\n")
            path = fh.name
        try:
            orphans = source_inventory.unimplemented_collectors(path)
            self.assertEqual(orphans, ("zzz_never_built_collector",))
        finally:
            os.unlink(path)

    def test_an_unreadable_registry_is_unknown_not_a_pass(self):
        import sys
        sys.path.insert(0, RAILWAY)
        import source_inventory

        with self.assertRaises(ValueError):
            source_inventory.unimplemented_collectors(
                os.path.join(RAILWAY, "no-such-health.js"))


if __name__ == "__main__":
    unittest.main()
