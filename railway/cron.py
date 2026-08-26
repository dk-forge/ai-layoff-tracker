"""
AI Layoff Tracker — Main Cron Script
Runs 2x daily: 9 AM ET + 5 PM ET (see railway.toml for the schedule)
"""
import os
from datetime import datetime, timedelta, timezone

import requests

from sources import cvm_br, edinet, opendart
from sources.edgar import pull_edgar_filings
from sources.gdelt import pull_gdelt_between, last_run_status as gdelt_last_run_status
from sources.newsapi import pull_news_articles
from sources.google_news import pull_google_news
from sources.local_news import pull_local_news
from sources.regional_feeds import pull_regional_feeds
from sources.national_feeds import pull_national_feeds
from sources.press_releases import pull_press_releases, reviewed_feed_count
from sources.warn_mn_letters import pull_mn_warn_letters
import extractor
import gdelt_reach
from extractor import extract_layoff_data, spend_deferral_count
from wp_poster import post_to_wordpress
from source_health import report_source_health
import spend

# Pre-extraction gate mode (cost-funnel port; see extractor.gate_verdict):
#   off    - no gate calls at all (pre-funnel behaviour)
#   shadow - the gate runs and its verdicts are RECORDED, but EVERYTHING is
#            still extracted, so a would-be false drop shows up as a stored
#            row beside a NO verdict (printed loudly + counted in the run
#            record). Costs slightly MORE than off (~+2%/run) and saves
#            nothing yet: it exists to MEASURE the gate's false-drop rate on
#            this tracker's own candidates before any coverage is at stake.
#   live   - a NO verdict skips extraction. ERROR always extracts (fail open).
#
# Default is now LIVE, and shadow is what earned it. The evidence, all from
# this tracker's own candidates and all in railway/spend_jobs.json:
#
#   103 shadow NO verdicts, 0 gate_false_drops.
#
# cron.py only writes `gate_false_drops` when the gate said NO and the
# extractor nonetheless produced a record, so the absence of that key on every
# shadow run IS the measurement, not a gap in it. For contrast, the free
# vocabulary alternative was re-measured on 2026-08-06 against 1,829 stored
# events (the sibling's 23-language reduction vocabulary, the best one either
# repo has): 29.6% false-drop, and 10.5% even after augmenting it with the
# phrasings it missed. A vocabulary cannot reach this gate's accuracy, which is
# why the gate is a model and why it is worth paying ~$0.00003 to run.
#
# Live is also a COVERAGE change, not only a cost one, and that is the point.
# Every cron run bumps the $0.20 per-run ceiling (spend.RUN_CEILING_USD) and
# then defers what is left unread, so cost-per-candidate is what decides how
# many candidates get read at all. Dropping ~22% of extractions buys ~22% more
# candidates inside the same ceiling.
#
# The safety property that makes this reversible: gate rejects are never marked
# seen (see filter_already_seen), so a wrong NO is re-pulled and re-judged on
# the next run rather than buried. Flipping back is one Railway env var, no
# deploy: ALT_GATE_MODE=shadow.
GATE_MODE = (os.environ.get("ALT_GATE_MODE", "live") or "").strip().lower()
if GATE_MODE not in ("off", "shadow", "live"):
    GATE_MODE = "live"


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


def _post_spend_record(entry):
    """Persist this run's spend record to the keyed /tracker-meta endpoint.

    Railway can neither commit nor be log-harvested, so without this POST the
    run's exact metered cost exists only in a log nobody collects and the
    account-level 'UNATTRIBUTED REMAINDER' stays permanently fat. Best-effort
    and loud: a failed POST costs one run of attribution (it stays inside the
    remainder, which is itself reported), never the ingest.
    """
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        print("spend: run record NOT persisted (WP_SITE_URL/WP_API_KEY unset) - "
              "this run stays in the unattributed remainder")
        return
    try:
        resp = requests.post(
            f"{site}/wp-json/layoffs/v1/tracker-meta",
            json={"add_spend_run": entry},
            headers={"X-Layoff-API-Key": key,
                     "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"},
            timeout=30)
        if resp.status_code == 200:
            print(f"spend: run record persisted to /tracker-meta ({entry.get('run_id')})")
        else:
            print(f"spend: run record POST got HTTP {resp.status_code} - this run "
                  f"stays in the unattributed remainder")
    except Exception as e:
        print(f"spend: run record POST failed ({e}) - this run stays in the "
              f"unattributed remainder")


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
    """Delegates to the shared seen_urls module (extracted 2026-07-28 so the
    satellite ingest scripts can use the same pre-check)."""
    from seen_urls import filter_already_seen as _shared
    return _shared(entries)


def _pull_local_news_rows():
    """Adapter: pull_local_news returns (rows, stats); this loop wants rows.

    The stats are printed per country rather than discarded, because a country
    returning 0 kept is exactly the signal this collector exists to surface -
    a thin country hidden inside a healthy total is the Quebec failure shape.
    """
    rows, stats = pull_local_news()
    for country in sorted(stats):
        st = stats[country]
        print(f"local_news[{country}]: kept={st['kept']} "
              f"fetched={st['fetched']} aggregator={st['aggregator']} "
              f"dropped={st['dropped']} errors={st['errors']}")
    return rows


def _pull_regional_feeds_rows():
    """Adapter: pull_regional_feeds returns (rows, stats); this loop wants rows.

    Per-feed tallies are printed for the same reason as local_news: a dead
    regional feed hidden inside a healthy total is the Quebec failure shape,
    and most runs will honestly keep 0 candidates (layoff events are rare in
    these regions), so the fetched counts are the liveness signal.
    """
    rows, stats = pull_regional_feeds()
    for key in sorted(stats):
        st = stats[key]
        print(f"regional_feeds[{key}]: kept={st['kept']} "
              f"fetched={st['fetched']} aggregator={st['aggregator']} "
              f"dropped={st['dropped']} errors={st['errors']}")
    return rows


def _pull_national_feeds_rows():
    """Adapter: pull_national_feeds returns (rows, stats); this loop wants rows.

    Per-feed tallies are printed for the same reason as regional_feeds: a dead
    national feed hidden inside a healthy total is the Quebec failure shape,
    and most runs will honestly keep 0 candidates, so the fetched counts are
    the liveness signal.
    """
    rows, stats = pull_national_feeds()
    for key in sorted(stats):
        st = stats[key]
        print(f"national_feeds[{key}]: kept={st['kept']} "
              f"fetched={st['fetched']} aggregator={st['aggregator']} "
              f"dropped={st['dropped']} errors={st['errors']}")
    return rows


def _spend_preflight():
    """Decide, before any paid call, whether this run may spend.

    This is the ONLY scheduled process on Railway, it carries its own OpenRouter
    key, and until 2026-08-02 it was invisible to every cost check in the repo:
    `openrouter_balance_check.py` runs in GitHub Actions and reads the Actions
    key, so the largest consumer had no measurement and no brake.

    Best-effort by construction. Ingest must not depend on a budget lookup
    succeeding: if the check cannot run, the per-run ceiling inside
    `spend.paid_reads_enabled()` still bounds this run, and the free collectors
    are unaffected either way.
    """
    try:
        key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
        if not key:
            print("spend: OPENROUTER_API_KEY not set in this runtime — paid "
                  "extraction will fail anyway; free collectors continue")
            return
        state = spend.fetch_key_state(key)
        used = float(state.get("usage") or 0)
        month_spend, month, persisted = spend.month_delta(
            used, spend.key_fingerprint(key))
        ceiling = spend.MONTHLY_ALLOWANCE_USD * spend.STOP_AT_FRACTION
        if persisted:
            print(f"spend: ${month_spend:.4f} spent in {month} of a "
                  f"${spend.MONTHLY_ALLOWANCE_USD:.2f} allowance "
                  f"(per-run ceiling ${spend.RUN_CEILING_USD:.2f})")
            if month_spend >= ceiling:
                spend.degrade(True)
        else:
            # Railway has no persistent volume, so the month-start snapshot
            # cannot be refreshed here. That makes month-to-date UNKNOWN, and
            # UNKNOWN is not a pass — say so, and lean on the per-run ceiling,
            # which needs no stored state.
            print(f"spend: month-to-date is UNKNOWN in this runtime (the "
                  f"month-start snapshot is not writable here). Not treating "
                  f"that as within budget. The ${spend.RUN_CEILING_USD:.2f} "
                  f"per-run ceiling is what is enforcing on this run.")
    except Exception as e:
        print(f"spend: preflight could not run ({e}) — per-run ceiling still "
              f"applies; free collectors unaffected")


def run():
    _mark_phase("refreshing")
    _spend_preflight()
    entries = []

    # Pull from sources — one source failing must not kill the run
    for source, collector in (
        ("edgar", pull_edgar_filings),
        # Free, keyless discovery. Its headlines carry the headcount even for
        # paywalled marquee layoffs (the exact gap NewsAPI's death + paywalls
        # created), so it leads the news sweep.
        ("google_news", pull_google_news),
        # Local-language discovery for the 25 wired markets. 45 editions carried
        # local UI languages while every DISCOVERY_QUERIES phrase was English,
        # which is why 142 countries held nothing (TECHLOG 2026-08-14). Armed by
        # ARMED_BY_DEFAULT in sources/local_news.py; a run with it dormant
        # reports itself dormant rather than vanishing from this table.
        # pull_local_news returns (rows, stats) - the adapter keeps this loop's
        # list contract and prints the per-country tallies so a thin country is
        # visible in the run log rather than only a total.
        ("local_news", _pull_local_news_rows),
        # Regional feeds: five verified regional outlets (Pacific, Francophone
        # Africa, Caribbean) covering the low-volume countries no per-country
        # sweep would justify. Direct RSS, robots-checked, armed by committed
        # default (measured under $1/month worst case; see ARMED_BY_DEFAULT in
        # sources/regional_feeds.py). Most runs honestly keep 0 candidates.
        ("regional_feeds", _pull_regional_feeds_rows),
        # National publisher feeds: the top VERIFIED business or national
        # publisher in each of fifteen mid-sized economies where the national
        # news edition returns the worldwide English feed and no regional
        # service reaches. Direct RSS, robots-checked, one publisher per
        # country, armed by committed default (measured $2.27/month worst
        # case; see ARMED_BY_DEFAULT in sources/national_feeds.py). Most runs
        # honestly keep 0 candidates.
        ("national_feeds", _pull_national_feeds_rows),
        # newsapi RETIRED 2026-07-25: the free tier is dev-only and the paid tier
        # is ~$449/mo, so it perpetually reported degraded (dead/exhausted key)
        # while contributing nothing. Google News RSS (keyless) replaced it and
        # carries the headcount even for paywalled marquee layoffs. Code kept in
        # sources/newsapi.py + the branch below, re-enablable by restoring this row.
        ("press_releases", pull_press_releases),
        # Minnesota DEED per-company WARN LETTER PDFs. DEED shifted recent
        # notices from the monthly report tables (fetch_mn -> /bulk) to
        # individual free-text letters, which _mn_parse_table cannot read; they
        # went unread for 53 days (MN freshness stall, 2026-08-24) while every
        # count-based check stayed green. Free text, so they ride the standard
        # gate -> extract -> post path here. The collector emits only letters
        # dated after the newest monthly report, so a letter and its monthly-
        # report twin cannot both be counted (see sources/warn_mn_letters.py).
        ("mn_warn_letters", pull_mn_warn_letters),
    ):
        try:
            report_source_health(source, "running", 0, "collection in progress")
            pulled = collector()
            for e in pulled:
                # Attribution tag for the spend meter: which collector this
                # candidate came from, so the run record can price each source.
                e.setdefault("_collector", source)
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
            elif source in ("newsapi", "google_news"):
                # These news channels must fail loud: a masked "ok" at 0 rows (a
                # dead/exhausted key, a plan rejection, or Google News blocking
                # the feed) silently starves discovery. Degrade on any API error,
                # and on a 0-item pull (abnormal for these channels) so it hits
                # the health page + weekly digest instead of hiding.
                fn = pull_news_articles if source == "newsapi" else pull_google_news
                err = getattr(fn, "last_error", None)
                if err:
                    report_source_health(source, "degraded", 0, f"{source} error: {err}")
                    print(f"::warning::{source} degraded: {err}")
                elif not pulled:
                    hint = ("verify the key/tier (free tier is dev-only, ~100 req/day)"
                            if source == "newsapi" else
                            "Google News RSS returned nothing — the feed may be blocked/changed")
                    report_source_health(source, "degraded", 0,
                        f"{source} returned 0 items — {hint}")
                    print(f"::warning::{source} returned 0 items")
                elif source == "google_news":
                    # Citation quality rides along with the OK row. A run can be
                    # perfectly healthy and still be storing links that rot:
                    # robots.txt forbids following a Google News redirector, so
                    # the unresolved share is a standing ceiling, not a breakage,
                    # and it belongs where someone reads it rather than only in a
                    # run log nobody opens.
                    from sources.google_news import citation_summary
                    report_source_health(
                        source, "ok", len(pulled),
                        citation_summary(getattr(pull_google_news,
                                                 "citation_states", None)))
                else:
                    report_source_health(source, "ok", len(pulled))
            elif source in ("regional_feeds", "national_feeds"):
                # 0 rows is NORMAL here (layoff events are rare in these
                # regions), so unlike google_news an empty pull is not
                # degradation. A feed-level failure IS: pull_regional_feeds
                # sets last_error on a non-200, a timeout, or a 200 whose body
                # is no longer an RSS document (the changed-scheme shape).
                fn = (pull_regional_feeds if source == "regional_feeds"
                      else pull_national_feeds)
                # national_feeds classifies each failure: a feed that answers a
                # laptop and refuses this datacentre (202/403/429/451/503) is
                # UNREACHABLE, and saying "feed broke" about it sent a session
                # hunting a parser that was working. Still degraded either way —
                # the health page must never claim a source is working when the
                # collector cannot read it. regional_feeds has no classifier
                # yet, so it keeps the original single-slot wording.
                failures = getattr(fn, "failures", None)
                err = getattr(fn, "last_error", None)
                if failures is not None:
                    from sources.national_feeds import health_verdict
                    status, detail = health_verdict(failures)
                    report_source_health(source, status, len(pulled), detail)
                    if status != "ok":
                        print(f"::warning::{source} degraded: {detail}")
                elif err:
                    report_source_health(source, "degraded", len(pulled),
                                         f"feed broke: {err}")
                    print(f"::warning::{source} degraded: {err}")
                else:
                    report_source_health(source, "ok", len(pulled))
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
        # Measurement only (railway/gdelt_reach.py). The reach ledger is
        # reset here rather than inside the collector because a backfill
        # sweep calls pull_gdelt_between many times and one run is one ledger.
        gdelt_reach.reset()
        pulled = pull_gdelt_between(now - timedelta(hours=36), now)
        for e in pulled:
            e.setdefault("_collector", "gdelt")
        entries += pulled
        # `detail` was EMPTY on every gdelt run ever recorded, which is why
        # nobody could say whether a window was truncated at maxrecords or a
        # country was dropped at the allowlist. It is a 240-char budget in the
        # store, so health_detail() spends the headline facts first. Every
        # health write is also appended to the public /source-runs table, so
        # this is durable history from the first run.
        # `ok` ONLY when every planned window/sweep slot completed. A run that
        # returned rows but left a capped, abandoned or mirror-ceiling slot is
        # `degraded` (the collector tracks this per-slot), so a truncated or
        # lost window is visible on the health page instead of silently green.
        report_source_health("gdelt", gdelt_last_run_status(), len(pulled),
                             gdelt_reach.current().health_detail())
    except Exception as e:
        # An abandoned window already lands here. Carry the reach facts with
        # it so a degraded run says WHICH slots died, not only that one did.
        _reach = gdelt_reach.current().health_detail(budget=140)
        report_source_health("gdelt", "degraded", 0, f"{e} | {_reach}"[:240])
        print(f"GDELT source failed: {e}")

    # RETIRED: the EDINET(JP)/OpenDART(KR)/CVM(BR) discovery probes ingested zero
    # layoff rows after months live — those regulatory filings essentially never
    # announce layoffs, and that coverage comes from news + ERM instead. They only
    # cluttered the health page with "listed N, nothing ingested". Off by default;
    # set RUN_DISCOVERY_PROBES=1 to re-enable the diagnostics.
    if os.environ.get("RUN_DISCOVERY_PROBES", "").lower() in {"1", "true", "yes"}:
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
    _before_seen = {id(e): e for e in entries}
    entries = filter_already_seen(entries)
    # Which countries the overlapping 36h window is re-reading. Measurement
    # only: these rows were dropped by the pre-check that already existed.
    _kept_ids = {id(e) for e in entries}
    for _e in _before_seen.values():
        if id(_e) not in _kept_ids and _e.get("_reach_cc"):
            gdelt_reach.current().note_cc(_e["_reach_cc"], "already_ingested")

    results = []
    posted = skipped_dupes = skipped_not_layoff = failed = 0
    gate_dropped = gate_false_drops = 0
    per_source = {}

    for raw in entries:
        tag = raw.get("_collector") or raw.get("source_type") or "unknown"
        stats = per_source.setdefault(tag, {"items": 0, "stored": 0})
        stats["items"] += 1
        spend.set_meter_context(tag)
        try:
            # Cheap pre-extraction gate (see GATE_MODE above). ERROR is a
            # non-judgement and always falls through to extraction.
            verdict = None
            if GATE_MODE in ("shadow", "live"):
                verdict = extractor.gate_verdict(raw)
                if verdict != extractor.GATE_ERROR:
                    spend.record_gate_outcome(verdict != extractor.GATE_NO)
                if verdict == extractor.GATE_NO and GATE_MODE == "live":
                    gate_dropped += 1
                    if raw.get("_reach_cc"):
                        gdelt_reach.current().note_cc(raw["_reach_cc"], "gate_no")
                    continue

            # DeepSeek extracts structured data
            extracted = extract_layoff_data(raw)
            if not extracted:
                skipped_not_layoff += 1
                if raw.get("_reach_cc"):
                    gdelt_reach.current().note_cc(raw["_reach_cc"], "not_an_event")
                continue
            if verdict == extractor.GATE_NO:
                # Shadow mode's whole purpose: the gate would have dropped a
                # candidate the extractor turned into a real record. Loud,
                # counted, and in the committed run record - this is the
                # false-drop evidence the live/shadow decision rests on.
                gate_false_drops += 1
                print(f"::warning::GATE FALSE DROP (shadow, not enforced): gate said NO "
                      f"but extraction produced {extracted['company_name']} "
                      f"({extracted['job_count']}) - {raw.get('source_url')}")

            # Always let WordPress perform authoritative deduplication. A 409
            # now retains this article as a corroborating source report on the
            # canonical event; pre-skipping here would throw that evidence away.
            status = post_to_wordpress(extracted)
            if status == "posted":
                posted += 1
                stats["stored"] += 1
            elif status == "duplicate":
                skipped_dupes += 1
            else:
                failed += 1
            results.append({"entry": extracted["company_name"], "success": status == "posted"})
        except Exception as e:
            failed += 1
            print(f"Unexpected error processing entry {raw.get('source_url')}: {e}")
    spend.set_meter_context(None)
    for tag, s in per_source.items():
        spend.annotate_tag(tag, items=s["items"], stored=s["stored"])

    print(
        f"Run complete: {len(entries)} pulled, {posted} posted, "
        f"{skipped_dupes} duplicates skipped, {skipped_not_layoff} non-events skipped, "
        f"{failed} failed"
        + (f", {gate_dropped} gate-dropped" if GATE_MODE == "live" else "")
        + (f", gate would drop {gate_false_drops} stored row(s) - DO NOT go live"
           if gate_false_drops else "")
    )
    # What did that cost, and did it buy anything? Before this line the question
    # was unanswerable from a run's own output — the only cost signal in the repo
    # was a daily account balance that could not attribute a cent to a run.
    print(spend.run_summary(rows_stored=posted))
    # The reach ledger again, now with the downstream stages folded in. The
    # health `detail` above is the COLLECTOR-stage view only (240 chars, and
    # it is written before extraction runs); this end-of-run table is the one
    # that says whether a country's candidates died at the allowlist, at the
    # already-seen pre-check, at the headline gate or at extraction.
    for _line in gdelt_reach.current().report_lines():
        print(_line)
    # The run's spend record, WITH a per-collector breakdown (spend books each
    # call under the _collector tag set above). Railway has no
    # GITHUB_WORKFLOW_REF and cannot commit, so the printed ledger line is
    # unreadable from anywhere - which is why the record is ALSO posted to the
    # keyed /tracker-meta endpoint below, where the daily balance job's
    # `spend.py --harvest` collects it into the committed railway/spend_jobs.json
    # and ops_status [2a] prices this cron per source per run. The run_id makes
    # the twice-daily runs distinct and the POST idempotent.
    run_id = "railway-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    ledger_entry = spend.record_job_run(items=len(entries), stored=posted,
                                        job="railway-cron", run_id=run_id)
    ledger_entry["gate_mode"] = GATE_MODE
    if gate_false_drops:
        ledger_entry["gate_false_drops"] = gate_false_drops
    _post_spend_record(ledger_entry)
    deferred = spend_deferral_count()
    if deferred:
        # Loud in the log, deliberately NOT a row on the health ledger: the
        # health page labels any unrecognised id "Operational collector"
        # (assets/health.js), and the Sources page must list exactly the live
        # collectors. A spend decision is not a collector, and inventing one to
        # carry it would put a wrong claim on two public surfaces to buy a
        # signal that belongs in ops_status. See ops_status.py [2a].
        print(f"::warning::spend ceiling: {deferred} candidate(s) went unread "
              f"this run. They are UNMARKED and will be re-pulled on a later "
              f"run. WARN/SEC/ERM and every free collector ran normally.")
    # FAIL LOUD (CLAUDE.md iron rule): the per-source health above covers
    # COLLECTION. This covers POSTING. A cycle that pulled real work but posted
    # nothing while failures piled up is an outage (rotated WP_API_KEY / WP host
    # 5xx), not a quiet no-op, and Railway won't flag a bare exit-0. Surface it
    # on the health ledger AND exit non-zero so the cycle is visibly red.
    if len(entries) > 0 and posted == 0 and failed >= 3:
        report_source_health(
            "ingest_post", "degraded", 0,
            f"news/SEC ingest posted 0 of {len(entries)} entries with {failed} post "
            f"failures this cycle (likely WP host down or WP_API_KEY rotated)")
        raise SystemExit(
            f"ingest posted 0/{len(entries)} with {failed} post failures; failing loud")
    return results


if __name__ == "__main__":
    run()
