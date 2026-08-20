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
import json
import os
import re
import sys
import time

import requests

import source_alert
import source_freshness
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


BASELINE_LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "warn_state_baselines.json")

# States whose WARN portal publishes a ROLLING WINDOW, not an archive. A
# high-water floor is meaningless for them: measured over the 14 warn-import
# runs 2026-08-02..2026-08-14 (TECHLOG 2026-08-14 §A), AZ swung 16-755, DE
# 8-105, ME 5-90, VT 8-100 — one high day would ratchet a floor that flags
# every ordinary day after it as drift, forever. These states are excluded
# from the ratchet AND dropped on ledger load (so a stale committed floor
# cannot resurrect the alarm); they are judged by hard-zero detection behind
# the peer-health gate instead. A hand-set WARN_GENERIC_BASELINE floor still
# applies to them — that is a reviewed human judgment, not the ratchet.
ROLLING_WINDOW_STATES = frozenset({"AZ", "DE", "ME", "VT"})


def load_state_baselines(path=BASELINE_LEDGER):
    """Committed per-tier, per-state high-water marks: {tier: {STATE: count}}.

    An ARCHIVE-publishing state's WARN scraper re-reads the state's whole
    history each run, so a healthy count is near-monotonic and the high-water
    mark is a sound floor. ROLLING_WINDOW_STATES publish a rolling window and
    are dropped here — for them the mark floats with recent volume and a floor
    built from it is a manufactured false alarm.
    Without a floor, drift detection can only see a hard 0 — and the failure that
    actually happens is a PARTIAL collapse: when Ohio's JFS pages went
    unreachable, fetch_oh fell back to a single CSV and returned 61 of 787
    notices. Non-zero, so every tripwire stayed green while 92% of the state
    silently vanished.

    Missing/malformed -> {}. That is UNKNOWN, not a pass: the caller says so in
    the run log rather than reporting a clean bill of health it cannot support.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("baseline ledger is not an object")
        return {str(t): {str(k).upper(): float(v) for k, v in (m or {}).items()
                         if float(v) > 0
                         and str(k).upper() not in ROLLING_WINDOW_STATES}
                for t, m in data.items() if isinstance(m, dict)}
    except FileNotFoundError:
        return {}
    except Exception as exc:
        print(f"WARN baseline ledger ignored ({exc}) — per-state floors UNKNOWN "
              f"this run, so only hard-zero collapse is detectable")
        return {}


def ratchet_state_baselines(ledger, tier, counts, expected, skip=()):
    """Raise this tier's high-water marks to match a healthy run. NEVER lowers.

    A floor that follows the data down is not a floor — it is the same
    self-widening clock that let the headline guards erase an open incident by
    waiting. If a state's archive legitimately shrinks, a human lowers the
    number in a reviewed commit; the ledger is committed for exactly that.

    `skip` is the set of states that DID drift this run. They are excluded, for
    the same reason: a collapsed count must never be recorded as normal.

    The exclusion is PER STATE, and that is the whole point. Every caller used
    to gate the entire tier on `if not drift:`, so one broken state withheld the
    floor from all forty of its healthy siblings — and a tier containing a
    permanently broken state could never record a single floor, which is a
    ledger that stays empty forever while reporting nothing wrong. A state whose
    own count is healthy has earned its floor regardless of its neighbours.

    ROLLING_WINDOW_STATES are never recorded: their portals publish a rolling
    window, so a count is recent volume, not archive size, and one high day
    would pin a floor their ordinary days can never clear.

    Returns True when anything changed (so the caller only rewrites on change).
    """
    tier_map = ledger.setdefault(tier, {})
    skip = {s.upper() for s in (skip or ())}
    changed = False
    for st in [s.upper() for s in expected]:
        if st in skip or st in ROLLING_WINDOW_STATES:
            continue
        n = float(counts.get(st, 0))
        if n > tier_map.get(st, 0):
            tier_map[st] = n
            changed = True
    return changed


def save_state_baselines(ledger, path=BASELINE_LEDGER):
    """Write the ledger back, sorted and stable so the git diff is readable."""
    payload = {t: {k: int(v) for k, v in sorted(m.items())}
               for t, m in sorted(ledger.items())}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _parse_generic_baselines(raw):
    """Optional per-state numeric floors from WARN_GENERIC_BASELINE.

    Format: JSON object of typical volumes, e.g. {"CA": 3000, "IL": 900}. A state
    whose count falls far below its floor counts as collapsed even if it isn't a
    hard 0 (a state that lost half its history to a parser change, say). Empty or
    malformed -> {} (pure 0-collapse detection, the conservative default).
    """
    if not raw:
        return {}
    try:
        import json
        data = json.loads(raw)
        return {str(k).upper(): float(v) for k, v in data.items() if float(v) > 0}
    except Exception as exc:
        print(f"WARN_GENERIC_BASELINE ignored (not valid JSON floors): {exc}")
        return {}


def detect_generic_state_drift(counts, expected, baselines=None, *,
                               drop_frac=0.7, peer_min_frac=0.5, peer_min_total=50,
                               zero_needs_baseline=False):
    """Which generic-tier states collapsed THIS run while their peers are healthy.

    The generic (open warn-scraper) tier reports one AGGREGATE health status
    (warn_us), so a single state silently returning 0 — its site changed and the
    open scraper broke for that ONE state — is otherwise invisible. This checks
    EVERY expected generic state against its own baseline, not just CA.

    Per-state baseline: a state is expected to be non-zero (implicit floor of 1);
    if ``baselines`` carries a numeric floor for it, a count below
    ``floor*(1-drop_frac)`` also counts as a collapse.

    Peer-health gate (avoids crying wolf): a system-wide zero — a scraper/network
    outage, or a genuinely quiet nationwide week — is warn_us's job to flag, not
    a reason to fire 40 per-state alerts. So NOTHING is flagged unless the sweep
    clearly ran: at least ``peer_min_frac`` of expected states produced > 0 AND
    the total across expected states is >= ``peer_min_total``. Only then is a
    state at 0 trustworthy evidence of a STATE-SPECIFIC break.

    Returns a sorted list of drifted state codes (empty when nothing is wrong or
    the peer gate says the run itself is untrustworthy).
    """
    expected = [s.upper() for s in expected]
    if not expected:
        return []
    baselines = {k.upper(): v for k, v in (baselines or {}).items()}
    producing = [s for s in expected if counts.get(s, 0) > 0]
    total = sum(counts.get(s, 0) for s in expected)
    # Peer gate: a nationwide zero is not per-state drift — suppress to avoid a
    # flood of false alarms (warn_us already surfaces a whole-sweep failure).
    if len(producing) < peer_min_frac * len(expected) or total < peer_min_total:
        return []
    drift = []
    for s in expected:
        n = counts.get(s, 0)
        floor = baselines.get(s)
        if n == 0:
            # zero_needs_baseline: a state that has NEVER produced has no floor,
            # so its 0 is unproven rather than anomalous. The legacy custom tier
            # sets this because some of its states legitimately file nothing on a
            # given run, and naming them every run is how a real breakage gets
            # ignored. Once a healthy run gives the state a floor, its 0 counts.
            if floor or not zero_needs_baseline:
                drift.append(s)
        elif floor and n < floor * (1 - drop_frac):
            drift.append(s)
    return sorted(drift)


def assess_state_freshness(entries, attempted, *, errored=(), collapsed=(),
                           today=None, ledger_path=None):
    """Did each attempted state return anything NEWER, judged on its own cadence.

    The count floors above answer "did the scraper return notices?". This
    answers the other question, the one no tripwire in this file could ask: a
    collector re-reading a FROZEN archive returns its whole history every run,
    clears every floor, and reports healthy forever. Kansas had looked green for
    110 days when this was written.

    The statistics live in `source_freshness`, ONE definition, so a session
    reading the committed ledger reaches the same verdict as the run that wrote
    it. This function is only the plumbing: it turns the run's own output into a
    per-state date series, judges it, folds the result into the committed
    three-state ledger, and hands back what to say.

    Never raises. A freshness check that sinks a successful import has cost more
    than the gap it found.
    """
    today = today or source_freshness.today_utc()
    dates_by_state, produced = {}, {}
    for e in entries:
        st = (e.get("state") or "").upper()
        if not st:
            continue
        dates_by_state.setdefault(st, []).append(e.get("layoff_date"))
        produced[st] = produced.get(st, 0) + 1
    errored, collapsed = {s.upper() for s in errored}, {s.upper() for s in collapsed}

    ledger = source_freshness.load_ledger(ledger_path or
                                          source_freshness.SOURCE_STATE_LEDGER)
    dark, unknown = [], []
    for st in sorted({s.upper() for s in attempted}):
        key = f"warn:{st}"
        # A state a HUMAN has classified UNAVAILABLE (no public register, or a
        # register with no headcount) is not in this queue and never re-enters
        # it on a machine's say-so.
        if (ledger.get("sources", {}).get(key, {}).get("state")
                == source_freshness.UNAVAILABLE):
            continue
        profile = source_freshness.cadence_profile(dates_by_state.get(st, []),
                                                   today=today)
        verdict = source_freshness.judge(profile, today=today)
        kind = None
        if verdict["verdict"] == source_freshness.FAIL:
            kind = source_freshness.classify(
                verdict["verdict"], errored=st in errored,
                produced=produced.get(st, 0), count_collapsed=st in collapsed)
        source_freshness.record(ledger, key, profile=profile,
                                verdict=verdict["verdict"],
                                reason=verdict["reason"], classification=kind,
                                today=today, label=f"{st} WARN",
                                p0=verdict.get("p0"))
        if verdict["verdict"] == source_freshness.FAIL:
            dark.append(st)
        elif verdict["verdict"] == source_freshness.UNKNOWN:
            unknown.append(st)
    return ledger, sorted(dark), sorted(unknown)


def describe_state_drift(drifted, counts, floors, unreachable=None):
    """The human-readable body of a collapse message, one entry per state.

    A state whose fetcher reported it could not REACH its source documents is
    annotated with that reason, because the two failures need opposite
    responses and the message used to give them the same one. "LA=33 (floor
    324) — likely site drift" was true about the number and wrong about the
    cause: laworks.net hosts only the current two years, the other nine come
    from web.archive.org, the archive was unreachable from the runner that
    morning, and 33 is exactly the two live years. A session reading that
    message goes and audits a parser that returns 324 from any other network.

    Passing no `unreachable` map reproduces the original wording exactly, so a
    genuine collapse still reads as a genuine collapse.
    """
    unreachable = unreachable or {}
    parts = []
    for st in drifted:
        line = f"{st}={counts.get(st, 0)}"
        if st in floors:
            line += f" (floor {int(floors[st])})"
        if st in unreachable:
            line += f" [NOT site drift — {unreachable[st]}]"
        parts.append(line)
    return ", ".join(parts)


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
    # Per-state drift for the GENERIC (open warn-scraper) tier. Unlike the custom
    # tiers below, warn_us reports a single AGGREGATE health status, so a single
    # generic state silently returning 0 (its site changed / the open scraper
    # broke for just that state) was previously invisible on every surface — only
    # CA was watched, and only in the run log. Now EVERY generic state is checked
    # against its own baseline (see detect_generic_state_drift), the check is
    # peer-gated so a nationwide-zero week never floods false alarms, and any real
    # collapse is FOLDED INTO the terminal warn_us health status further down
    # (degraded -> public health page + weekly digest). It is reported under
    # warn_us (this tier's own family key) rather than a new id or the
    # warn_custom_* family: warn_custom_states / warn_custom_legacy are re-reported
    # by the custom-scraper blocks BELOW this point, which would clobber a value
    # written here, and a brand-new literal id would need a health.js label.
    # Names the freshness check reads further down. Initialised here so a
    # skipped optional tier (WARN_SKIP_NEW_STATES=1) cannot turn the check into
    # a NameError, which would read as "could not run" on a healthy run.
    _new_errors, _wanted_new, _new_drift = set(), [], []
    _generic_by_state = {}
    for _e in entries:
        _gs = (_e.get("state") or "").upper()
        if _gs:
            _generic_by_state[_gs] = _generic_by_state.get(_gs, 0) + 1
    _generic_drift = []
    # Committed high-water floors, shared by BOTH scraper tiers. WARN_GENERIC_BASELINE
    # still overrides per state (it is how you tune one state without a commit),
    # but it is set by no workflow, so until now every tier ran with an empty
    # floor map and could only ever see a hard zero.
    _baselines = load_state_baselines()
    if len(states) == 1 and str(states[0]).lower() == "all":  # only meaningful on a full sweep
        _counts = ", ".join(f"{st}={_generic_by_state[st]}" for st in sorted(_generic_by_state))
        print("generic WARN per-state counts: " + (_counts or "(none)"))
        # WARN_GENERIC_MONITOR narrows the watched set for tuning; default is the
        # WHOLE generic tier (every state warn-scraper covers), not just CA.
        _mon_env = os.environ.get("WARN_GENERIC_MONITOR", "").strip()
        if _mon_env:
            _expected_g = [s.strip().upper() for s in _mon_env.split(",") if s.strip()]
        else:
            try:
                from sources.warn import ALL_STATES as _ALL_GENERIC
                _expected_g = list(_ALL_GENERIC)
            except Exception:
                _expected_g = sorted(_generic_by_state)  # fall back to what we saw
        # A state with a CUSTOM scraper is served by that scraper; the generic
        # open-scraper tier is redundant backup for it, and its own structural
        # tripwire (below) already watches it. Flagging the generic tier going
        # dark for TX/FL/GA/OH/MI... therefore cries wolf about states whose
        # data is arriving fine, which buries the states that are genuinely
        # uncovered. Watch the generic tier only where it is the ONLY source.
        try:
            from sources.warn_custom import CUSTOM_STATES as _CUSTOM
            _expected_g = [s for s in _expected_g if s.upper() not in _CUSTOM]
        except Exception:
            pass
        try:
            # NM (and now KS) are served by warn_new_states scrapers; the
            # generic tier is redundant backup for them, so a generic zero is
            # not drift (F22, audit 2026-07-28 — NM was still crying wolf).
            from sources.warn_new_states import NEW_CUSTOM_STATES as _NEWC
            _expected_g = [s for s in _expected_g if s.upper() not in _NEWC]
        except Exception:
            pass
        # Also drop states the generic tier is NOT responsible for:
        #   * HI has its own OCR collector (warn_hi_ocr) and no ordinary register.
        #   * AR / WY / NH publish no public register at all.
        #   * OK publishes notices with NO affected-employee counts, so they can
        #     never become countable rows -- 0 is the correct result, not drift.
        #     Re-verified 2026-08-13 at the source, because the old wording read
        #     like "nothing to collect" and that is not what is true. OESC's
        #     portal is a Salesforce Aura app whose guest-accessible Apex call
        #     returns all 218 notices in ONE request, so the notices are very
        #     much reachable -- but the projection has eight fields and a
        #     headcount is not among them (employer, city, zip, workforce board,
        #     notice date, closure type, Id, RecordTypeId). Reading the object
        #     directly is refused for the guest user (INSUFFICIENT_ACCESS), so
        #     there is no unauthenticated path to a count at all. 2026 is 9
        #     notices and a structurally absent job figure -- absent, not
        #     unmeasured. Ingesting count-less rows would be a policy change
        #     (they cannot enter wp_alt_layoffs, which requires job_count > 0),
        #     not a scraper fix.
        # Without this the alert named HI/OK every run alongside genuinely
        # uncovered states, which is how a real breakage gets ignored.
        _NOT_GENERIC_TIER = {"HI", "AR", "WY", "NH", "OK"}
        _expected_g = [s for s in _expected_g if s.upper() not in _NOT_GENERIC_TIER]
        _floors_g = dict(_baselines.get("generic", {}))
        _floors_g.update(_parse_generic_baselines(os.environ.get("WARN_GENERIC_BASELINE")))
        if not _floors_g:
            print("::notice:: generic tier has no per-state floors yet — this run can "
                  "only detect a hard zero, not a partial collapse (UNKNOWN, not a pass). "
                  "The ledger seeds itself from this run.")
        _generic_drift = detect_generic_state_drift(
            _generic_by_state, _expected_g, _floors_g)
        # Record floors for every state that did NOT drift, drifted siblings
        # excluded. Gating this on an entirely clean sweep meant one broken
        # state kept forty healthy ones floor-less indefinitely.
        if ratchet_state_baselines(_baselines, "generic", _generic_by_state,
                                   _expected_g, skip=_generic_drift):
            save_state_baselines(_baselines)
        if _generic_drift:
            print(f"::warning:: generic WARN state(s) went dark vs healthy peers — likely "
                  f"open-scraper drift for: {', '.join(_generic_drift)}. Check each state's "
                  f"site/parser (WARN_GENERIC_MONITOR narrows the set, WARN_GENERIC_BASELINE "
                  f"tunes per-state floors).")

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
    # A hard 0 is the LOUD failure; the quiet one is a scraper that keeps
    # answering with a fraction of the state. Ohio's JFS pages went unreachable
    # and fetch_oh fell through to one CSV: 61 notices instead of 787. Not zero,
    # not high-volume-exempt, so nothing above this line fires and the health
    # page stays green while 92% of the state is gone. Per-state floors catch
    # that. zero_needs_baseline keeps the low-volume states quiet until they
    # have earned a floor, so this adds no new noise on a fresh ledger.
    _floors_c = dict(_baselines.get("legacy_custom", {}))
    _collapse_c = detect_generic_state_drift(
        _got_by_state, _expected_c, _floors_c,
        drop_frac=0.5, zero_needs_baseline=True)
    _real_drift = sorted(set(_real_drift) | set(_collapse_c))
    if not _floors_c:
        print("::notice:: legacy custom tier has no per-state floors yet — partial "
              "collapse is UNDETECTABLE this run (UNKNOWN, not a pass). Seeding from "
              "this run's counts.")
    if _real_drift:
        from sources.warn_custom import SOURCE_UNREACHABLE as _UNREACHABLE
        _detail = describe_state_drift(_real_drift, _got_by_state, _floors_c,
                                       unreachable=_UNREACHABLE)
        # "likely site drift" is a hypothesis, and it is the WRONG one whenever
        # the fetcher already told us it could not reach the documents. Only
        # claim drift for the states that have not said otherwise.
        _blamed = [st for st in _real_drift if st not in _UNREACHABLE]
        _lead = ("Custom WARN state(s) collapsed vs their own history"
                 + (" — likely site drift" if _blamed else
                    " because their source documents were UNREACHABLE, not "
                    "because the scrapers drifted")
                 + ": ")
        print(f"::warning:: legacy WARN scraper(s) collapsed vs their own "
              f"history: {_detail}")
        report_source_health("warn_custom_legacy", "degraded", 0,
                             _lead + _detail)
    elif _expected_c:
        # Report OK explicitly. Without this the reporter only ever writes on
        # failure, so a RESOLVED drift stayed red forever (NV sat degraded for
        # 35h after the Bluehost mirror fixed it).
        report_source_health("warn_custom_legacy", "ok", len(customs),
                             f"{len(_expected_c)} legacy custom scraper(s) checked, "
                             f"no state collapsed against its own history")
    # Only a healthy STATE may raise its own floor, and only upward. Ratcheting a
    # drifted state would teach the collapse as the new normal; withholding the
    # floor from its healthy siblings (the old whole-tier gate) taught nothing
    # at all. This is outside the elif on purpose: a tier with one drifted state
    # still has to record the rest, which is exactly the run where it matters.
    if _scrape_all_c and ratchet_state_baselines(
            _baselines, "legacy_custom", _got_by_state, _expected_c,
            skip=_real_drift):
        save_state_baselines(_baselines)
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
        _wanted_new = list(wanted)
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
                _new_errors.add(st)
                print(f"WARN {st} (new importer) failed: {exc}")
        # PARTIAL collapse, the failure this tier could not see. Until now the
        # only tripwire here was `len(got) == 0`, so a state could lose most of
        # its archive and still read green: New Mexico went from 603 jobs in
        # 2025 to 51 in 2026 while the health page said "warn_us: ok — all
        # supported states". A hard zero is the loud failure; the quiet one is a
        # scraper that keeps answering with a fraction of the state, and that is
        # the one that survives for months. Same floors, same ledger, same
        # semantics as the legacy tier — a state's own history, never a peer's.
        _new_by_state = {}
        for _e in new_entries:
            _ns = (_e.get("state") or "").upper()
            if _ns:
                _new_by_state[_ns] = _new_by_state.get(_ns, 0) + 1
        _floors_n = dict(_baselines.get("new_custom", {}))
        _collapse_n = detect_generic_state_drift(
            _new_by_state, wanted, _floors_n,
            drop_frac=0.5, zero_needs_baseline=True,
            # This tier is SIX states, not forty. The peer gate is written for a
            # nationwide sweep where half the states going quiet means the run
            # itself failed; applied unchanged here it would need 3 producing
            # states and 50 notices before it would speak at all, which on a
            # tier this small means the check is off more often than it is on.
            peer_min_frac=0.0, peer_min_total=1)
        if not _floors_n:
            print("::notice:: new-states tier has no per-state floors yet — partial "
                  "collapse is UNDETECTABLE this run (UNKNOWN, not a pass). Seeding "
                  "from this run's counts.")
        _new_drift = sorted(set(drift_states) | set(_collapse_n))
        if _new_drift:
            _detail = ", ".join(
                f"{st}={_new_by_state.get(st, 0)}"
                + (f" (floor {int(_floors_n[st])})" if st in _floors_n else "")
                for st in _new_drift)
            report_source_health("warn_custom_states", "degraded", 0,
                                  "Custom WARN scraper(s) returned 0 / errored / collapsed "
                                  "against their own history — likely site drift: " + _detail)
            print(f"::warning:: new-states WARN scraper(s) collapsed vs their own "
                  f"history — likely site drift: {_detail}")
        elif wanted:
            # Explicit OK so a resolved drift clears (HI stayed red for 8h after
            # it moved to its own OCR importer and left this list entirely).
            report_source_health("warn_custom_states", "ok", len(new_entries),
                                 f"{len(wanted)} custom scraper(s) checked, "
                                 f"no state collapsed against its own history")
        if scrape_all and ratchet_state_baselines(
                _baselines, "new_custom", _new_by_state, wanted, skip=_new_drift):
            save_state_baselines(_baselines)
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
            from sources.quebec import pull_quebec, health_detail
            qc = pull_quebec(months_back=int(os.environ.get("QUEBEC_MONTHS", "4")))
            print(f"Quebec (custom): {len(qc)} notices kept")
            if start:
                qc = [e for e in qc if e["layoff_date"] >= start]
            if min_emp:
                qc = [e for e in qc if e["job_count"] >= min_emp]
            entries.extend(qc)
            # The detail now says what the run SAW -- which discovery route
            # answered, how many PDFs were readable, and how the parsed count
            # compares with the total each document states for itself. The old
            # text guessed "parser returned 0, check PDF layout" at a parser
            # that was working perfectly; the landing page was the thing that
            # had gone quiet, and that guess cost days.
            report_source_health("warn_quebec", "ok" if qc else "degraded", len(qc),
                                 health_detail(qc))
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
            from sources.wup_mazowieckie import pull_wup_mazowieckie, health_detail as _pl_detail
            pl = pull_wup_mazowieckie(max_posts=int(os.environ.get("WUP_MAZ_POSTS", "4")))
            print(f"Mazowieckie PL (custom): {len(pl)} notices kept")
            if start:
                pl = [e for e in pl if e["layoff_date"] >= start]
            if min_emp:
                pl = [e for e in pl if e["job_count"] >= min_emp]
            entries.extend(pl)
            # The detail now carries the run's OWN completeness audit — our jobs
            # against the total each post declares for itself. "ok, ran fine"
            # was true and useless for as long as the parser was reading three
            # of eleven notices.
            report_source_health("warn_mazowieckie", "ok", len(pl), _pl_detail())
        except Exception as exc:
            print(f"Mazowieckie importer failed: {exc}")
            report_source_health("warn_mazowieckie", "degraded", 0,
                                 f"Mazowieckie importer failed: {exc}")

    entries = _sanitize_warn_entries(entries)
    entries.sort(key=lambda e: e["layoff_date"], reverse=True)

    # ---- FRESHNESS: did each state return anything NEWER than last time? ----
    # Everything above this line is a COUNT check, and a count cannot see a
    # collector re-reading a frozen archive: it returns its whole history every
    # run, clears every floor, and reports healthy forever. Kansas had looked
    # green for 110 days. Deliberately placed after the sanitiser (so a
    # rescinded or unnamed row cannot pass for freshness) and before the
    # WARN_LIMIT truncation (which would drop history and forge a collapse).
    _dark, _unknown_fresh = [], []
    try:
        _attempted = set()
        if _scrape_all_c:
            _attempted |= set(_expected_g) | set(_expected_c) | set(_wanted_new)
        else:
            _attempted |= {s.upper() for s in states if s.lower() != "all"}
        # A state that produced rows is attempted whether or not a registry
        # claimed it, so a tier added later is watched by construction.
        _attempted |= {(e.get("state") or "").upper() for e in entries if e.get("state")}
        _attempted.discard("")
        _errored = set(_new_errors) | {s for s in _legacy_drift
                                       if _got_by_state.get(s, 0) == 0}
        _collapsed = set(_generic_drift) | set(_real_drift) | set(_new_drift)
        _fresh_ledger, _dark, _unknown_fresh = assess_state_freshness(
            entries, _attempted, errored=_errored, collapsed=_collapsed)
        source_freshness.save_ledger(_fresh_ledger)
        _rows = source_freshness.broken(_fresh_ledger)
        if _dark:
            # ONE finding listing the states, never one alarm per state.
            print(f"::warning:: {len(_dark)} WARN state(s) are publishing "
                  f"NOTHING NEW while their counts look healthy: "
                  f"{source_freshness.describe(_rows, limit=8)}")
        _quiet = source_freshness.quiet(_fresh_ledger)
        if _quiet:
            # Advisory, deliberately separate from the dark list and never
            # emailed as a breakage. Kansas sat here at p=0.023 with an audit
            # showing every notice already collected: the register was quiet,
            # the collector was fine, and calling that "dark" is the false
            # positive that teaches an owner to ignore the channel.
            print("::notice:: publishing less than their own recent rate "
                  "predicts, but NOT evidence of a break: "
                  + ", ".join(f"{r['key'].split(':')[-1]} {r.get('days_dark')}d "
                              f"(p={r.get('p0')})" for r in _quiet))
        if _unknown_fresh:
            print(f"::notice:: freshness UNKNOWN (too little history to fit a "
                  f"rate, which is not a pass): {', '.join(_unknown_fresh)}")
        if _rows and source_alert.enabled():
            _sent, _claimed, _note = source_alert.announce(
                _rows, run_url=source_alert.run_url())
            print(f"dark-source alert: sent={_sent} new={len(_claimed)} ({_note})")
    except Exception as exc:                                   # noqa: BLE001
        # Telemetry must never sink an import that worked. A freshness check
        # that could not run is UNKNOWN and says so; it is not a clean bill.
        print(f"::warning:: freshness check could not run ({exc}) — state "
              f"freshness is UNKNOWN this run, not verified")

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
    # Fold per-state generic-tier drift into the terminal status: a state that
    # went dark while its peers stayed healthy is a coverage gap the health page
    # and weekly digest must show, even though the bulk upsert itself succeeded.
    #
    # A state that is publishing NOTHING NEW goes through the same door. It is
    # not a second channel and must not become one: the health ledger is what
    # the public health page renders and what health_digest.py mails with a
    # paste-ready fix, and that is the owner's established loop. One line
    # naming every dark state, because six at once is one finding.
    _problems = []
    if _generic_drift:
        _problems.append("generic-tier state(s) went dark vs healthy peers "
                         "(likely open-scraper drift): " + ", ".join(_generic_drift))
    if _dark:
        _problems.append(f"{len(_dark)} state(s) publishing nothing new "
                         f"(freshness, own-cadence): " + ", ".join(_dark))
    if _problems:
        report_source_health("warn_us", "degraded", len(entries),
                             f"{scope}: {upserted} upserted, but " + "; ".join(_problems))
    else:
        _fresh_note = (f", {len(_unknown_fresh)} state(s) UNKNOWN (too little "
                       f"history to judge)" if _unknown_fresh else "")
        report_source_health("warn_us", "ok", len(entries),
                             f"{scope}: {upserted} upserted from {len(entries)} "
                             f"notices, every state also publishing NEW "
                             f"notices on its own cadence{_fresh_note}")


if __name__ == "__main__":
    main()
