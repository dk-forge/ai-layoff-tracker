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
import html as _html
import os
import re
import sys
import time

import requests

from sources.warn import pull_warn
from sources.warn_custom import pull_warn_custom
from source_health import report_source_health

# --- last-mile clean-up, applied to EVERY state scraper's output -------------
# Deliberately here and not in an individual scraper: these two defects are
# structural to scraping government HTML tables, so one guard at the import
# boundary covers all 48 states (and every state added later) instead of
# 48 copies that drift apart.
_TAG_RX = re.compile(r"<[^>]*>")
# A notice the state later RESCINDED or CANCELLED is a layoff that did not
# happen. Counting it inflates the total with jobs nobody lost; a public audit
# found 23 such rows carrying 5,050 phantom jobs (Wisconsin/Louisiana/California
# and others append the status to the employer name rather than removing the row).
_RESCINDED_RX = re.compile(r"\b(rescind\w*|cancell?ed)\b", re.I)


# Several states paste the notice's SITE ADDRESS into the employer cell
# ("SafeSource Direct L.L.C. 200 St. Nazaire Rd. Broussard, LA, 70518",
# "Walmart (1345 Crossman Ave.)"). Left in place it silently fragments company
# identity: that Walmart row never groups with plain "Walmart", so company
# totals, the directory and repeat-layoff detection all split. Louisiana is the
# worst offender (436 rows), California next.
_ADDR_RX = re.compile(
    # The number may be a RANGE ("(1500-1552 Encinitas Blvd.)"), which a plain
    # \d+ stops matching at the dash.
    r"[\s(,]+\d{1,6}(?:\s*-\s*\d{1,6})?\s+[\w.'-]+(?:\s+[\w.'-]+){0,3}\s+"
    r"(?:st|street|rd|road|ave|avenue|hwy|highway|blvd|boulevard|dr|drive|ln|lane|"
    r"pkwy|parkway|way|ct|court|cir|circle|pl|place|ter|terrace|route|rte)\b\.?",
    re.I)
# "City, ST 70518" / "City, ST, 70518" tails.
_CITYSTZIP_RX = re.compile(r"[\s,(]+[A-Za-z .'-]+,\s*[A-Z]{2},?\s*\d{5}(?:-\d{4})?\b")
# Repeated "Update:" markers some states prepend on every revision.
_UPDATE_RX = re.compile(r"^(?:\s*update\s*:\s*)+", re.I)


def _strip_site_address(name):
    """Cut a pasted-in site address off an employer name, conservatively.

    Only applied when a real name survives, so an entry that is ONLY an address
    is left exactly as scraped rather than reduced to nothing.
    """
    for rx in (_ADDR_RX, _CITYSTZIP_RX):
        m = rx.search(name)
        if m and m.start() > 0:
            head = name[:m.start()].strip(" ,;-([")
            if len(head) >= 3 and re.search(r"[A-Za-z]{3}", head):
                name = head
    return name


def _clean_company(name):
    """Strip markup a state table smuggled into the employer name.

    Wisconsin's WARN table wraps a footnote INSIDE the company cell, so a naive
    cell read stored `Wisconsin Green, LLC<br/></a><a><em ...>* Notice outlines
    multiple scenarios...` as the employer, which then rendered as raw HTML in
    the public table and in the row's excerpt.
    """
    name = _TAG_RX.sub(" ", str(name or ""))
    name = _html.unescape(name)          # "Bingham &amp; Taylor" -> "Bingham & Taylor"
    name = _UPDATE_RX.sub("", name)
    # Drop a trailing footnote marker and anything after it ("* Notice outlines
    # multiple scenarios ..."), which is commentary about the notice, not a name.
    name = re.split(r"\s*\*", name)[0]
    name = re.sub(r"\s+", " ", name).strip(" ,;-")
    name = _strip_site_address(name).strip(" ,;-")
    # Cutting the address can leave a dangling site marker ("Winn Dixie Store
    # No." once "1411 5901 Airline Drive" goes). The store number is a SITE id,
    # not company identity, so dropping it is what we want for grouping; the
    # orphaned label just should not trail the name.
    return re.sub(r"[\s,]*\b(?:no\.?|#|unit|suite|ste\.?)\s*$", "", name, flags=re.I).strip(" ,;-")


def _sanitize_warn_entries(entries):
    """Clean employer names and drop rescinded notices. Never raises."""
    out, dropped, unnamed, cleaned = [], 0, 0, 0
    for e in entries:
        try:
            raw = str(e.get("company_name") or "")
            if _RESCINDED_RX.search(_TAG_RX.sub(" ", raw)):
                dropped += 1
                continue
            name = _clean_company(raw)
            if not re.search(r"[A-Za-z0-9]", name):
                # Cleaning left nothing nameable (Tennessee's list yields rows
                # whose employer cell is just "." or ","). A row with no
                # identifiable employer cannot be checked by a reader, so it is
                # skipped rather than published as punctuation. NB the test is
                # alphanumeric, not alphabetic: "118 118" is a real company.
                unnamed += 1
                continue
            if name and name != raw:
                # Keep the excerpt consistent with the corrected name. The raw
                # name must be flattened the SAME way before substituting, or
                # the footnote survives in the excerpt after the company field
                # is already clean.
                raw_flat = re.sub(r"\s+", " ", _TAG_RX.sub(" ", raw)).strip()
                ex = re.sub(r"\s+", " ", _TAG_RX.sub(" ", str(e.get("excerpt") or ""))).strip()
                e["excerpt"] = ex.replace(raw_flat, name) if raw_flat else ex
                e["company_name"] = name
                cleaned += 1
            # dedup_hash is intentionally left as the scraper computed it: it
            # stays keyed to the same source row, so this correction flows into
            # the EXISTING stored row on the next upsert instead of forking a
            # second copy under the cleaned name.
            out.append(e)
        except Exception:
            out.append(e)
    if dropped or cleaned or unnamed:
        print(f"WARN sanitize: dropped {dropped} rescinded/cancelled notice(s), "
              f"{unnamed} with no identifiable employer, cleaned {cleaned} name(s)")
    return out


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

    entries = _sanitize_warn_entries(entries)
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
