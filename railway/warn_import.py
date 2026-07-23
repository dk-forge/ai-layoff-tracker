"""
Imports US state WARN Act notices straight into the fast-query table.

WARN forms are already structured (company, headcount, date, location), so they
skip the LLM extractor. They're written via the bulk table endpoint (not the CPT
/add path) so 100K+ notices don't create 100K WordPress posts. Idempotent via the
exact dedup hash, so it's safe to re-run.

Env:
  WARN_STATES         comma list of state codes, or "all" (default "CA")
  WARN_MIN_EMPLOYEES  drop notices below this headcount (default 0 = keep all)
  WARN_START          YYYY-MM-DD lower bound on effective date (default "" = all)
  WARN_LIMIT          max notices (blank = no cap)
  WP_SITE_URL, WP_API_KEY
"""
import os
import sys
import time

import requests

from sources.warn import pull_warn
from sources.warn_custom import pull_warn_custom
from source_health import report_source_health

BATCH = 1000
FAILED_BATCHES = 0


def post_bulk(entries):
    global FAILED_BATCHES
    wp = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
    key = os.environ.get("WP_API_KEY")
    if not wp or not key:
        print("post_bulk error: WP_SITE_URL or WP_API_KEY not set")
        FAILED_BATCHES += 1
        return 0
    headers = {
        "X-Layoff-API-Key": key,
        "Content-Type": "application/json",
        "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
    }
    upserted = 0
    total_batches = (len(entries) + BATCH - 1) // BATCH
    # The shared host intermittently answers 5xx/timeouts under load (a
    # 2026-07-18 nationwide reload lost 5 batches to 504s). The upsert is
    # hash-idempotent, so retrying a batch is always safe; only a batch that
    # stays failed after the retries counts against the run.
    transient = {500, 502, 503, 504, 520, 521, 522, 524}
    for i in range(0, len(entries), BATCH):
        chunk = entries[i:i + BATCH]
        n = i // BATCH + 1
        for attempt in range(3):
            try:
                resp = requests.post(f"{wp}/wp-json/layoffs/v1/bulk",
                                     json={"entries": chunk}, headers=headers, timeout=180)
                if resp.status_code == 200:
                    got = resp.json().get("upserted", 0)
                    upserted += got
                    print(f"  batch {n}/{total_batches}: upserted {got}")
                    break
                if resp.status_code in transient and attempt < 2:
                    print(f"  batch {n}/{total_batches}: transient {resp.status_code}, retrying in 60s")
                    time.sleep(60)
                    continue
                FAILED_BATCHES += 1
                print(f"  batch {n}/{total_batches} FAILED: {resp.status_code} {resp.text[:200]}")
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  batch {n}/{total_batches}: {e}; retrying in 60s")
                    time.sleep(60)
                    continue
                FAILED_BATCHES += 1
                print(f"  batch {n}/{total_batches} error: {e}")
                break
    return upserted


def main():
    raw_states = (os.environ.get("WARN_STATES") or "CA").strip()
    states = ["all"] if raw_states.lower() == "all" else [s.strip().upper() for s in raw_states.split(",") if s.strip()]
    min_emp = int(os.environ.get("WARN_MIN_EMPLOYEES") or 0)
    start = os.environ.get("WARN_START") or ""
    limit = int(os.environ.get("WARN_LIMIT") or 0) or None

    scope = "all supported states" if states == ["all"] else f"{len(states)} states"
    purge = (os.environ.get("WARN_PURGE") or "").lower() in ("1", "true", "yes")
    print(f"WARN import: {scope}, min_employees={min_emp}, start={start or 'all'}, limit={limit}, purge={purge}")

    # Purge deletes EVERY state's table-only WARN rows, so it may only pair
    # with a full nationwide reload — purging then importing one state would
    # silently drop the rest.
    if purge and states != ["all"]:
        print("ERROR: WARN_PURGE requires WARN_STATES=all (purge is global; a "
              "state-scoped reload would wipe the other states)")
        sys.exit(1)
    report_source_health("warn_us", "running", 0, f"WARN import in progress: {scope}")
    try:
        entries = pull_warn(states, min_employees=min_emp, start_date=start)
    except Exception as exc:
        report_source_health("warn_us", "degraded", 0, f"WARN scrape failed: {exc}")
        raise
    # Custom collectors cover the states whose sites broke the open scraper
    # (TX, FL, GA, OH, MI, CO, ID, LA, NC, NV, MN, MA) plus the retired NY
    # history database (dedup hashes absorb the warn-scraper overlap).
    # Per-state visibility for the GENERIC (open warn-scraper) tier. Unlike the
    # custom tiers below, warn_us reports a single AGGREGATE health status, so a
    # single generic state silently returning 0 (its site changed / the open
    # scraper broke for just that state) is otherwise invisible. Log every
    # generic state's count, and warn LOUDLY in the run log for the high-volume
    # generic states where a 0 is almost certainly drift, not a quiet filing
    # week. No separate health-ledger reporter here — that needs live per-state
    # volume calibration to avoid crying wolf on the public page (see RUNBOOK);
    # the run-log ::warning:: surfaces it for an auditing human for now.
    _generic_by_state = {}
    for _e in entries:
        _gs = (_e.get("state") or "").upper()
        if _gs:
            _generic_by_state[_gs] = _generic_by_state.get(_gs, 0) + 1
    if len(states) == 1 and str(states[0]).lower() == "all":  # only meaningful on a full sweep
        _counts = ", ".join(f"{st}={_generic_by_state[st]}" for st in sorted(_generic_by_state))
        print("generic WARN per-state counts: " + (_counts or "(none)"))
        _generic_monitor = {s.strip().upper() for s in
                            os.environ.get("WARN_GENERIC_MONITOR", "CA").split(",") if s.strip()}
        _generic_drift = sorted(st for st in _generic_monitor if _generic_by_state.get(st, 0) == 0)
        if _generic_drift:
            print(f"::warning:: HIGH-VOLUME generic WARN state(s) returned 0 — likely "
                  f"open-scraper drift for: {', '.join(_generic_drift)}. Check that state's "
                  f"site/parser (set WARN_GENERIC_MONITOR to tune the watched set).")

    customs = pull_warn_custom(states)
    # Structural-drift tripwire for the LEGACY custom scrapers (parity with the
    # new-states check below): these are high-volume states (TX, FL, GA, ...), so
    # a requested state returning 0 almost always means its page changed and the
    # parser silently broke. Surface it on the health page instead of a silent gap.
    try:
        from sources.warn_custom import CUSTOM_STATES as _LEGACY_CUSTOM
    except Exception:
        _LEGACY_CUSTOM = {}
    _scrape_all_c = len(states) == 1 and str(states[0]).lower() == "all"
    _expected_c = list(_LEGACY_CUSTOM) if _scrape_all_c else [s.upper() for s in states if s.upper() in _LEGACY_CUSTOM]
    _got_by_state = {}
    for e in customs:
        _st = (e.get("state") or "").upper()
        _got_by_state[_st] = _got_by_state.get(_st, 0) + 1
    # A 0 only means DRIFT for high-volume states (a 0 there is anomalous). Low-
    # volume states (NV, ID, LA...) legitimately file nothing on a given run, so
    # flagging them cries wolf and erodes trust in the alert. Log those quietly;
    # only degrade/email on the big states where 0 = the scraper broke.
    _HIGH_VOLUME = {"TX", "FL", "GA", "CA", "OH", "MI", "NY", "NC"}
    _legacy_drift = [st for st in _expected_c if _got_by_state.get(st, 0) == 0]
    _real_drift = [st for st in _legacy_drift if st in _HIGH_VOLUME]
    if _legacy_drift:
        print(f"::notice:: legacy custom WARN returned 0 for {', '.join(_legacy_drift)} "
              f"(quiet run or drift; only high-volume states alert)")
    if _real_drift:
        print(f"::warning:: HIGH-VOLUME legacy WARN scraper(s) returned 0 — likely site drift: {', '.join(_real_drift)}")
        report_source_health("warn_custom_legacy", "degraded", 0,
                             "High-volume custom WARN returned 0 — likely site drift: " + ", ".join(_real_drift))
    elif _expected_c:
        # Report OK explicitly. Without this the reporter only ever writes on
        # failure, so a RESOLVED drift stayed red forever (NV sat degraded for
        # 35h after the Bluehost mirror fixed it).
        report_source_health("warn_custom_legacy", "ok", len(customs),
                             f"{len(_expected_c)} legacy custom scraper(s) checked, no high-volume drift")
    if min_emp:
        customs = [e for e in customs if e["job_count"] >= min_emp]
    if start:
        customs = [e for e in customs if e["layoff_date"] >= start]
    entries.extend(customs)

    # Newly-added importers (MS, WV, HI, NM) — validated live on 2026-07-20
    # (MS 129 / WV 24 / NM 11 notices; HI 0 by design). Now part of the daily
    # sweep; set WARN_SKIP_NEW_STATES=1 to disable if a source ever breaks.
    if os.environ.get("WARN_SKIP_NEW_STATES") != "1":
        try:
            from sources.warn_new_states import NEW_CUSTOM_STATES
        except Exception as exc:
            NEW_CUSTOM_STATES = {}
            print(f"WARN new-states module unavailable: {exc}")
        scrape_all = len(states) == 1 and str(states[0]).lower() == "all"
        wanted = list(NEW_CUSTOM_STATES) if scrape_all else [s.upper() for s in states if s.upper() in NEW_CUSTOM_STATES]
        new_entries = []
        drift_states = []
        for st in wanted:
            try:
                got = NEW_CUSTOM_STATES[st]()
                print(f"WARN {st} (new importer): {len(got)} notices kept")
                new_entries.extend(got)
                # Structural-drift tripwire: a custom scraper normally returns
                # notices; a sudden 0 almost always means the state redesigned
                # its page and our parser silently broke. Surface it LOUDLY on
                # the health page instead of publishing a silent gap.
                if len(got) == 0:
                    drift_states.append(st)
                    print(f"::warning:: WARN {st} custom scraper returned 0 notices — likely structural drift (page changed). Check the scraper.")
            except Exception as exc:
                drift_states.append(st)
                print(f"WARN {st} (new importer) failed: {exc}")
        if drift_states:
            report_source_health("warn_custom_states", "degraded", 0,
                                  "Custom WARN scraper(s) returned 0 / errored — likely site drift: "
                                  + ", ".join(drift_states))
        elif wanted:
            # Explicit OK so a resolved drift clears (HI stayed red for 8h after
            # it moved to its own OCR importer and left this list entirely).
            report_source_health("warn_custom_states", "ok", len(new_entries),
                                 f"{len(wanted)} custom scraper(s) checked, no drift")
        if min_emp:
            new_entries = [e for e in new_entries if e["job_count"] >= min_emp]
        if start:
            new_entries = [e for e in new_entries if e["layoff_date"] >= start]
        entries.extend(new_entries)

    # Quebec (Canada) collective-dismissal notices (avis de licenciements
    # collectifs) from the MESS monthly PDFs — WARN-class (a legal advance
    # notice of a mass layoff). Live by default; set WARN_SKIP_QUEBEC=1 to
    # disable if the PDF layout ever breaks the parser. Isolated in try/except
    # so a Quebec hiccup never sinks the US WARN import.
    if os.environ.get("WARN_SKIP_QUEBEC") != "1":
        try:
            from sources.quebec import pull_quebec
            qc = pull_quebec(months_back=int(os.environ.get("QUEBEC_MONTHS", "4")))
            print(f"Quebec (custom): {len(qc)} notices kept")
            if start:
                qc = [e for e in qc if e["layoff_date"] >= start]
            if min_emp:
                qc = [e for e in qc if e["job_count"] >= min_emp]
            entries.extend(qc)
            report_source_health("warn_quebec", "ok" if qc else "degraded", len(qc),
                                 "Quebec collective-dismissal notices (MESS)"
                                 + ("" if qc else " — parser returned 0, check PDF layout"))
        except Exception as exc:
            print(f"Quebec importer failed: {exc}")
            report_source_health("warn_quebec", "degraded", 0, f"Quebec importer failed: {exc}")

    # Mazowieckie (Poland) collective-dismissal register — WUP Warszawa's
    # monthly named press posts, the only one of Poland's 16 voivodeship labour
    # offices that publishes employers by name (2026-07 survey). Deterministic
    # parse (no LLM), WARN-class provenance, same /bulk path. The register is
    # monthly, so a run finding 0 NEW notices is normal — health only degrades
    # on an exception, not an empty month. Set WARN_SKIP_WUP_MAZOWIECKIE=1 to
    # disable if the post format ever drifts. Fail-isolated like Quebec.
    if os.environ.get("WARN_SKIP_WUP_MAZOWIECKIE") != "1":
        try:
            from sources.wup_mazowieckie import pull_wup_mazowieckie
            pl = pull_wup_mazowieckie(max_posts=int(os.environ.get("WUP_MAZ_POSTS", "4")))
            print(f"Mazowieckie PL (custom): {len(pl)} notices kept")
            if start:
                pl = [e for e in pl if e["layoff_date"] >= start]
            if min_emp:
                pl = [e for e in pl if e["job_count"] >= min_emp]
            entries.extend(pl)
            report_source_health("warn_mazowieckie", "ok", len(pl),
                                 "Mazowieckie collective-dismissal register (WUP Warszawa)"
                                 + ("" if pl else " — no notices in the recent monthly posts"))
        except Exception as exc:
            print(f"Mazowieckie importer failed: {exc}")
            report_source_health("warn_mazowieckie", "degraded", 0,
                                 f"Mazowieckie importer failed: {exc}")

    entries.sort(key=lambda e: e["layoff_date"], reverse=True)
    if limit:
        entries = entries[:limit]
    print(f"WARN import: {len(entries)} notices to upsert (bulk)")

    # Purge only AFTER a successful scrape, and only when the scrape looks like
    # a real nationwide sweep — never leave the public table empty because the
    # state sites happened to be down today.
    if purge:
        if len(entries) < 5000:
            print(f"ERROR: refusing to purge — scrape returned only "
                  f"{len(entries)} notices (expected 20K+ nationwide); the "
                  f"replacement data is too small to swap in safely")
            sys.exit(1)
        wp = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
        key = os.environ.get("WP_API_KEY")
        try:
            resp = requests.post(f"{wp}/wp-json/layoffs/v1/bulk-purge", headers={
                "X-Layoff-API-Key": key,
                "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
            }, timeout=120)
            print(f"purge: HTTP {resp.status_code} {resp.text[:120]}")
            if resp.status_code != 200:
                print("ERROR: purge failed, aborting so stale rows aren't duplicated")
                sys.exit(1)
        except Exception as e:
            print(f"ERROR: purge failed ({e}), aborting")
            sys.exit(1)

    upserted = post_bulk(entries)
    print(f"WARN import done: {upserted} upserted from {len(entries)} notices")

    # A green run must mean the data actually landed — fail loudly if any
    # batch was rejected so the scheduled workflow shows red.
    if FAILED_BATCHES:
        print(f"ERROR: {FAILED_BATCHES} batch(es) failed to post")
        report_source_health("warn_us", "degraded", 0,
                             f"{FAILED_BATCHES} bulk batch(es) rejected by the API")
        sys.exit(1)
    report_source_health("warn_us", "ok", len(entries),
                         f"{scope}: {upserted} upserted from {len(entries)} notices")


if __name__ == "__main__":
    main()
