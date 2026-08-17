"""Monthly import of US federal RIF separations (OPM EHRI).

Structured government data (like WARN), so it skips the LLM and posts via the
bulk table endpoint. Reuses warn_import.post_bulk (batching, transient-5xx
retry, loud-fail). Idempotent: the dedup hash excludes the count, so OPM's
monthly revisions AND its late-reported rows upsert in place. Required secret:
WP_API_KEY. Makes no paid model call.

Note on the failure mode this file exists to prevent: a total is the SUM of an
effective month's slices across every reporting file, and /bulk field-updates on
hash match. So a run that read only SOME of its window would compute short
totals and overwrite correct ones. `pull_federal_rif` raises
FederalRifIncomplete rather than returning a partial set, and that is reported
degraded and exits non-zero — never posted.
"""
import sys

from source_health import report_source_health
from sources.federal_layoffs import FederalRifIncomplete, pull_federal_rif
import warn_import  # reuse post_bulk + the FAILED_BATCHES loud-fail counter


def main():
    report_source_health("federal_rif", "running", 0, "OPM EHRI RIF import in progress")
    try:
        entries = pull_federal_rif()
    except FederalRifIncomplete as exc:
        # Incomplete window: posting would shrink correct rows. Post nothing.
        report_source_health("federal_rif", "degraded", 0,
                             f"incomplete OPM window, nothing posted: {exc}")
        print(f"federal_rif: INCOMPLETE, posting nothing — {exc}")
        raise
    except Exception as exc:
        report_source_health("federal_rif", "degraded", 0, f"pull failed: {exc}")
        raise
    if not entries:
        # With the full window read, zero means OPM published no RIF at or above
        # the floor anywhere in the window — possible, but far more likely a
        # schema change. Degraded so it is visible either way.
        report_source_health("federal_rif", "degraded", 0,
                             "0 RIF events parsed across the whole window "
                             "(quiet window or OPM schema change)")
        print("federal_rif: nothing to upsert")
        return
    jobs = sum(e["job_count"] for e in entries)
    upserted = warn_import.post_bulk(entries)
    print(f"federal RIF import done: {upserted} upserted from {len(entries)} "
          f"agency-month events, {jobs:,} separations")
    if warn_import.FAILED_BATCHES:
        report_source_health("federal_rif", "degraded", upserted,
                             f"{warn_import.FAILED_BATCHES} batch(es) rejected by the API")
        sys.exit(1)
    report_source_health("federal_rif", "ok", upserted,
                         f"OPM EHRI executed federal RIF separations "
                         f"({len(entries)} agency-months, {jobs:,} separations)")


if __name__ == "__main__":
    main()
