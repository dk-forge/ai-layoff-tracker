"""
AI Layoff Tracker — Main Cron Script
Runs 2x daily: 9 AM ET + 5 PM ET (see railway.toml for the schedule)
"""
import os
from datetime import datetime, timedelta, timezone

import requests

from sources import cvm_br, edinet, opendart
from sources.edgar import pull_edgar_filings
from sources.gdelt import pull_gdelt_between
from sources.newsapi import pull_news_articles
from sources.press_releases import pull_press_releases, reviewed_feed_count
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health


def _mark_phase(phase):
    """Tell the live badge the pipeline is working (best-effort)."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return
    try:
        requests.post(f"{site}/wp-json/layoffs/v1/status",
                      json={"phase": phase},
                      headers={"X-Layoff-API-Key": key,
                               "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"},
                      timeout=20)
    except Exception as e:
        print(f"phase ping failed: {e}")


def _cvm_probe_newest(year):
    """Probe the newest published CVM IPE yearly index (current, else prior)."""
    try:
        return len(cvm_br.list_filings_for_year(year).filings)
    except cvm_br.CvmApiError as exc:
        if getattr(exc, "kind", "") != "not_found":
            raise
        return len(cvm_br.list_filings_for_year(year - 1).filings)


def run_discovery_probes():
    """Health-visible discovery probes for Japan EDINET, South Korea OpenDART,
    and Brazil CVM.

    Each probe lists one official filing window and reports the count to
    source health so the public page shows the probe ran. Nothing is ingested,
    classified, or added to the extraction pipeline — this is deliberately NOT
    a coverage claim (see docs/OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md before
    promoting any client to a real connector).
    """
    # Each source computes the newest *complete* local filing day itself:
    # EDINET submissions close 17:15 JST and DART reception closes 19:00 KST,
    # so the evening-UTC run (22:00 local) probes the just-closed local day and
    # the late-UTC run (07:00 local next morning) re-checks it.
    edinet_day = edinet.latest_complete_list_date()
    opendart_day = opendart.latest_complete_list_date()
    current_year = datetime.now(timezone.utc).year
    # Each probe: (source id, gating env key or None, window label, list call).
    probes = (
        ("edinet_jp", "EDINET_API_KEY_JP", edinet_day.isoformat(),
         lambda: len(edinet.list_documents_for_date(edinet_day).documents)),
        ("opendart_kr", "OPENDART_API_KEY_KR", opendart_day.isoformat(),
         lambda: len(opendart.list_disclosures(opendart_day, opendart_day).disclosures)),
        # CVM's open-data portal requires no API key, so this probe is keyless:
        # env gate is None and the "not configured" branch never applies. The
        # window is the current calendar year's Fato Relevante index.
        # CVM publishes its yearly IPE file with a lag; an unpublished
        # current-year file is the publisher's schedule, not a probe failure,
        # so fall back to the newest published year (2026-07-19: 2026 was 404
        # while 2025 served fine, which showed as a false 'degraded').
        ("cvm_br", None, str(current_year),
         lambda: _cvm_probe_newest(current_year)),
    )
    for source, env_key, window, probe in probes:
        if env_key and not os.environ.get(env_key, ""):
            report_source_health(source, "degraded", 0,
                                 f"{env_key} is not configured in this runtime")
            continue
        try:
            report_source_health(source, "running", 0, "discovery list in progress")
            count = probe()
            report_source_health(
                source, "ok", count,
                f"discovery only: {count} official filing(s) listed for "
                f"{window}; nothing ingested or classified",
            )
        except Exception as e:
            report_source_health(source, "degraded", 0, f"discovery probe failed: {e}")
            print(f"{source} discovery probe failed: {e}")


def filter_already_seen(entries):
    """Drop entries whose EXACT source_url is already in the record.

    Batched POSTs to the keyed /seen-urls endpoint (main rows + retained
    source reports). Only same-URL re-reads are dropped - a fresh outlet on
    the same event has a different URL and always goes to the extractor.
    Fails OPEN on any error: the worst outcome of a broken pre-check must be
    a slightly higher LLM bill, never a missed layoff.
    """
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    urls = [e.get("source_url") for e in entries if e.get("source_url")]
    if not (site and key and urls):
        return entries
    seen = set()
    try:
        for i in range(0, len(urls), 400):
            resp = requests.post(
                f"{site}/wp-json/layoffs/v1/seen-urls",
                json={"urls": urls[i:i + 400]},
                headers={"X-Layoff-API-Key": key,
                         "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"},
                timeout=30)
            if resp.status_code != 200:
                print(f"seen-urls pre-check HTTP {resp.status_code} - extracting everything (fail open)")
                return entries
            seen.update(resp.json().get("seen", []))
    except Exception as exc:
        print(f"seen-urls pre-check failed ({exc}) - extracting everything (fail open)")
        return entries
    kept = [e for e in entries if not (e.get("source_url") and e.get("source_url") in seen)]
    print(f"seen-urls pre-check: {len(entries) - len(kept)} same-URL re-read(s) skipped "
          f"before the extractor, {len(kept)} to process")
    return kept


def run():
    _mark_phase("refreshing")
    entries = []

    # Pull from sources — one source failing must not kill the run
    for source, collector in (
        ("edgar", pull_edgar_filings),
        ("newsapi", pull_news_articles),
        ("press_releases", pull_press_releases),
    ):
        try:
            report_source_health(source, "running", 0, "collection in progress")
            pulled = collector()
            entries += pulled
            if source == "press_releases":
                configured = reviewed_feed_count()
                if configured:
                    report_source_health(
                        source, "ok", len(pulled),
                        f"{configured} reviewed company-owned/exchange feed(s) configured",
                    )
                else:
                    # This is a visible coverage limitation, not an empty
                    # official-feed result.  Do not imply an IR collector is
                    # live until an admission-reviewed feed is configured.
                    report_source_health(
                        source, "degraded", 0,
                        "No reviewed company-owned or exchange RSS/Atom feeds configured",
                    )
            else:
                report_source_health(source, "ok", len(pulled))
        except Exception as e:
            report_source_health(source, "degraded", 0, str(e))
            print(f"{source} source failed: {e}")
    try:
        # Worldwide press coverage (Europe/Asia/everywhere) via GDELT. 36h
        # window overlaps the twice-daily runs; dedup drops the repeats.
        now = datetime.now(timezone.utc)
        report_source_health("gdelt", "running", 0, "collection in progress")
        pulled = pull_gdelt_between(now - timedelta(hours=36), now)
        entries += pulled
        report_source_health("gdelt", "ok", len(pulled))
    except Exception as e:
        report_source_health("gdelt", "degraded", 0, str(e))
        print(f"GDELT source failed: {e}")

    # Discovery probes are diagnostics only; an error here must never abort the
    # cron cycle after entries were already collected (it logs per-probe itself).
    try:
        run_discovery_probes()
    except Exception as e:
        print(f"discovery probes failed (non-fatal): {e}")

    print(f"Pulled {len(entries)} raw entries")

    # URL-level pre-check: the pull windows overlap on purpose (36h GDELT on a
    # twice-daily cadence), so the SAME article URL arrives ~3 runs in a row.
    # Re-extracting an identical URL adds zero evidence (the server INSERT
    # IGNOREs the duplicate source report) but costs an LLM call every time.
    # Skip exactly those. A new outlet covering the same event is a new URL,
    # never skipped, and still lands as a corroborating source report. FAIL
    # OPEN: if the check errors, extract everything (server dedup backstops) -
    # a cost optimization must never be able to cost coverage.
    entries = filter_already_seen(entries)

    results = []
    posted = skipped_dupes = skipped_not_layoff = failed = 0

    for raw in entries:
        try:
            # DeepSeek extracts structured data
            extracted = extract_layoff_data(raw)
            if not extracted:
                skipped_not_layoff += 1
                continue

            # Always let WordPress perform authoritative deduplication. A 409
            # now retains this article as a corroborating source report on the
            # canonical event; pre-skipping here would throw that evidence away.
            status = post_to_wordpress(extracted)
            if status == "posted":
                posted += 1
            elif status == "duplicate":
                skipped_dupes += 1
            else:
                failed += 1
            results.append({"entry": extracted["company_name"], "success": status == "posted"})
        except Exception as e:
            failed += 1
            print(f"Unexpected error processing entry {raw.get('source_url')}: {e}")

    print(
        f"Run complete: {len(entries)} pulled, {posted} posted, "
        f"{skipped_dupes} duplicates skipped, {skipped_not_layoff} non-events skipped, "
        f"{failed} failed"
    )
    return results


if __name__ == "__main__":
    run()
