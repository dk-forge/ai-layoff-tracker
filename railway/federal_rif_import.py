"""Monthly import of US federal RIF separations (OPM EHRI).

Structured government data (like WARN), so it skips the LLM and posts via the
bulk table endpoint. Reuses warn_import.post_bulk (batching, transient-5xx
retry, loud-fail). Idempotent: the dedup hash excludes the count, so OPM's
monthly revisions upsert in place. Required secret: WP_API_KEY.
"""
import sys

from source_health import report_source_health
from sources.federal_layoffs import pull_federal_rif
import warn_import  # reuse post_bulk + the FAILED_BATCHES loud-fail counter


def main():
    report_source_health("federal_rif", "running", 0, "OPM EHRI RIF import in progress")
    try:
        entries = pull_federal_rif()
    except Exception as exc:
        report_source_health("federal_rif", "degraded", 0, f"pull failed: {exc}")
        raise
    if not entries:
        # 0 is either a genuinely quiet month or an OPM schema change; the
        # collector logs which. Report degraded so a schema break is visible.
        report_source_health("federal_rif", "degraded", 0,
                             "0 RIF events parsed (quiet month or OPM schema change)")
        print("federal_rif: nothing to upsert")
        return
    upserted = warn_import.post_bulk(entries)
    print(f"federal RIF import done: {upserted} upserted from {len(entries)} agency-month events")
    if warn_import.FAILED_BATCHES:
        report_source_health("federal_rif", "degraded", upserted,
                             f"{warn_import.FAILED_BATCHES} batch(es) rejected by the API")
        sys.exit(1)
    report_source_health("federal_rif", "ok", upserted,
                         "OPM EHRI executed federal RIF separations")


if __name__ == "__main__":
    main()
