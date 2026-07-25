"""
Cross-source duplicate remover (the daily "deep scan").

Exact-hash and same-company-within-30-days dedup run at write time, but they
miss two cases: (1) WARN and ERM enter through /bulk, which does exact-hash
dedup only, so an ERM "Meta Platforms 8,000 (announced)" never checks against
a news "Meta 8,000"; (2) the same event reported more than 30 days apart, or
under a name variant ("Meta" vs "Meta Platforms"), slips the fuzzy window.

This pass groups entries by normalized company, forms candidate clusters of
similar job counts within a 120-day window, and asks DeepSeek which entries
are the SAME event reported multiple times versus genuinely distinct layoffs
(Meta cut 11,000 in 2022, 10,000 in 2023 and 8,000 in 2026 — same company,
different events). For each confirmed group it keeps ONE canonical entry and
moves every duplicate's source report onto that event before removing the
extra row. The public event-source endpoint therefore retains every receipt.

Canonical preference: a verified entry over an announced one; then the
earliest date; then the most authoritative source (SEC/WARN/ERM over news).
Never merges across different companies, and never changes a job count.

Env: WP_SITE_URL, WP_API_KEY, OPENROUTER_API_KEY.
DEDUPE_MAX_CLUSTERS caps LLM calls per run (default 60) so cost stays bounded.
"""
import json
import os
import re
import sys
import time
from datetime import date
import urllib.request
from collections import defaultdict

from source_health import report_source_health

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_CLUSTERS = int(os.environ.get("DEDUPE_MAX_CLUSTERS") or 60)
WINDOW_DAYS = 120
# Two NEAR-IDENTICAL counts for a material layoff are almost always the same
# plan re-reported — a strategic round-number figure ("50,000 job cuts") recurs
# in coverage for many months, well past the 120-day window. Those pairs get a
# wider window so the model at least gets to adjudicate them; merely-similar
# counts (5–25% apart) keep the tight window, where a same-quarter re-report is
# likely but a half-year-apart pair is more often a genuinely distinct round.
# (Incident 2026-07-19: VW "50,000" appeared twice, 125 days apart — 5 days past
# the flat window — so the deep scan never even compared them.)
WIDE_WINDOW_DAYS = int(os.environ.get("DEDUPE_WIDE_WINDOW_DAYS") or 365)
EXACT_WINDOW_DAYS = int(os.environ.get("DEDUPE_EXACT_WINDOW_DAYS") or 1095)  # ~3y for exact-count re-reports
# Near-identical counts (95%+) at a MODERATE size get the wide window too. Was
# 1,000, which let a same-event re-report of a mid-size cut ("Company X 420" vs
# "X 430" 200 days apart — one plan, rounded differently) fall back to the tight
# 120-day window and never reach the model. 250 catches those while staying above
# the small-number noise floor. The model still adjudicates every pair it sees,
# and the daily cluster cap keeps LLM cost flat regardless of how many it sees.
WIDE_WINDOW_MIN_COUNT = int(os.environ.get("DEDUPE_WIDE_WINDOW_MIN_COUNT") or 250)
WIDE_WINDOW_SIMILARITY = 0.95
SRC_RANK = {"8K": 3, "warn": 3, "press_release": 2, "erm": 2, "news": 1}


def pair_window_days(lo, hi):
    """Max day-gap at which two same-company counts may still be one event.

    Two cases get the WIDE window (the model still makes the final call — this
    only decides which pairs it gets to see):
      * EXACT identical counts (same company, same number) at any material size
        — a small figure re-reported months apart is almost always one event
        (Commonwealth Bank 300 in Jan and again in July, 196 days apart, was
        missed because 300 < the material-size floor for near-matches).
      * NEAR-identical counts (≥95%) at a material size (≥1,000).
    Everything else keeps the tight WINDOW_DAYS."""
    if not hi:
        return WINDOW_DAYS
    ratio = lo / hi
    if ratio >= 0.995 and hi >= 100:           # exact match, any size ≥100
        # Exact identical counts re-reported even years apart (e.g. a cumulative
        # figure restated) escaped the 365-day ceiling. Let the model see pairs
        # up to EXACT_WINDOW_DAYS (default ~3y); it still makes the final call.
        return EXACT_WINDOW_DAYS
    if ratio >= WIDE_WINDOW_SIMILARITY and hi >= WIDE_WINDOW_MIN_COUNT:
        return WIDE_WINDOW_DAYS
    return WINDOW_DAYS


def api(path):
    # shared hosting throws transient 5xx under sustained paging; retry
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"{SITE}/wp-json/layoffs/v1/{path}",
                                         headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception as e:
            if attempt == 3:
                raise
            print(f"  api retry {attempt+1}: {e}")
            time.sleep(15 * (attempt + 1))


def norm_company(name):
    # Kept in sync with the plugin's alt_company_key (includes/api.php) so the two
    # dedup layers reach the same same-company verdict: same legal-suffix set plus
    # the trailing geographic qualifiers (America/USA/International/Global).
    n = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())   # punctuation -> space, like the PHP key ("Amazon.com" -> "amazon com")
    n = re.sub(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|sa|ag|group|holdings|holding|technologies|technology|systems|solutions|platforms|the|com)\b", "", n)
    n = re.sub(r"\b(america|americas|usa|us|international|global|worldwide|na)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def days_between(a, b):
    from datetime import date
    try:
        pa = date(*map(int, a[:10].split("-")))
        pb = date(*map(int, b[:10].split("-")))
        return abs((pa - pb).days)
    except Exception:
        return 9999


def fetch_all():
    # Only non-WARN sources are eligible: WARN notices are deliberately exempt
    # from fuzzy dedup (a company legally files several notices close together),
    # and every cross-source duplicate we've seen is news/ERM/SEC. This also
    # keeps the fetch to ~10K rows (per_page=200 is the server cap) instead of
    # 40K+, which the shared host can't paginate without throwing 500s.
    rows, page = [], 1
    while True:
        d = api(f"query?sources=news,8K,press_release,erm,federal_rif&per_page=200&page={page}&sort=id&dir=asc")
        rows += d["data"]
        if page * 200 >= d["total"] or not d["data"]:
            break
        page += 1
        time.sleep(0.5)
    return rows


def candidate_clusters(rows):
    """Same normalized company + job counts within 25% + dates within window."""
    by_co = defaultdict(list)
    for r in rows:
        by_co[norm_company(r["company_name"])].append(r)
    clusters = []
    for co, items in by_co.items():
        if not co or len(items) < 2:
            continue
        items.sort(key=lambda r: (r["job_count"], r["layoff_date"] or ""))
        used = set()
        for i, a in enumerate(items):
            if a["id"] in used:
                continue
            group = [a]
            for b in items[i + 1:]:
                if b["id"] in used:
                    continue
                hi = max(a["job_count"], b["job_count"]) or 1
                lo = min(a["job_count"], b["job_count"])
                if lo / hi >= 0.75 and days_between(a["layoff_date"] or "", b["layoff_date"] or "") <= pair_window_days(lo, hi):
                    group.append(b)
                    used.add(b["id"])
            if len(group) > 1:
                used.add(a["id"])
                clusters.append(group)
    # Do not slice here. A stable "largest first" cap starves every small
    # two-report cluster forever when the backlog is large (exactly the class
    # of duplicate a newsroom needs us to catch).
    return clusters


def _cluster_identity(group):
    """Deterministic key, used to rotate the bounded daily work queue."""
    return tuple(sorted(int(r["id"]) for r in group))


def _cluster_priority(group):
    """High-confidence repeats are reviewed every day; all others rotate."""
    counts = defaultdict(int)
    for row in group:
        counts[int(row["job_count"])] += 1
    # Exact matching counts are a strong duplicate signal, but never a merge
    # decision: the LLM still reviews source excerpts before any action.
    exact_repeat = max(counts.values())
    newest = max((row.get("layoff_date") or "") for row in group)
    return exact_repeat, newest, len(group)


def select_candidate_clusters(clusters, limit=MAX_CLUSTERS, today=None):
    """Return a bounded, rotating queue so no candidate is permanently missed.

    One quarter of the budget is reserved for the highest-confidence repeats;
    the rest walks deterministically through all remaining clusters each day.
    With a stable backlog, every candidate receives an LLM decision over time.
    """
    if limit <= 0 or not clusters:
        return []
    if len(clusters) <= limit:
        return clusters
    always_n = min(len(clusters), max(1, limit // 4))
    ranked = sorted(clusters, key=_cluster_priority, reverse=True)
    always = ranked[:always_n]
    always_keys = {_cluster_identity(group) for group in always}
    remaining = sorted(
        (group for group in clusters if _cluster_identity(group) not in always_keys),
        key=_cluster_identity,
    )
    slots = limit - len(always)
    if not remaining or slots <= 0:
        return always
    day = today or date.today()
    start = (day.toordinal() * slots) % len(remaining)
    rotated = (remaining[start:] + remaining[:start])[:slots]
    return always + rotated


def ask_llm(group):
    payload = [{"id": r["id"], "company": r["company_name"], "jobs": r["job_count"],
                "date": r["layoff_date"], "source": r["source_name"],
                "excerpt": (r["excerpt"] or "")[:180]} for r in group]
    prompt = ("These layoff-tracker entries are all the same company. Some are the SAME layoff "
              "event reported by different outlets or sources; others are DISTINCT layoffs at "
              "different times. Group the ids: each group is one real event. A big round number "
              "repeated within a few weeks across outlets is usually one event; the same number "
              "years apart is usually distinct events. Reply STRICT JSON "
              '{"events":[[id,id,...],[id,...]]} covering every id exactly once.\n\n'
              + json.dumps(payload, ensure_ascii=False))
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps({"model": os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat"),
                         "messages": [{"role": "user", "content": prompt}],
                         "response_format": {"type": "json_object"}}).encode(),
        headers={"Authorization": "Bearer " + OR_KEY, "Content-Type": "application/json", "User-Agent": UA})
    for attempt in range(3):
        try:
            out = json.load(urllib.request.urlopen(req, timeout=150))
            c = out["choices"][0]["message"]["content"]
            c = c[c.find("{"): c.rfind("}") + 1]
            return json.loads(c).get("events", [])
        except Exception as e:
            print(f"  llm retry {attempt+1}: {e}")
            time.sleep(8 * (attempt + 1))
    return []


def canonical(group):
    """Keep verified over announced, then earliest, then strongest source."""
    return sorted(group, key=lambda r: (
        1 if r.get("announced") else 0,
        r["layoff_date"] or "9999",
        -SRC_RANK.get(r["source_type"], 0),
    ))[0]


def main():
    if not (SITE and KEY and OR_KEY):
        print("WP_SITE_URL / WP_API_KEY / OPENROUTER_API_KEY required"); sys.exit(1)

    # A total fetch failure is a real problem (exit non-zero). Everything after
    # is resilient: each company cluster is handled on its own, and one bad
    # cluster or trash batch is skipped, not fatal. Dedup is best-effort
    # cleanup, so a run that clears 58 of 60 clusters is a success, not a
    # failure email. (Chunking by letter would still fail per-chunk; per-
    # cluster isolation is strictly better and just as free.)
    rows = fetch_all()
    by_id = {r["id"]: r for r in rows}
    all_clusters = candidate_clusters(rows)
    clusters = select_candidate_clusters(all_clusters)
    print(f"{len(rows)} entries, {len(all_clusters)} candidate clusters; "
          f"{len(clusters)} selected for this rotating review")

    merges, skipped = [], 0
    for group in clusters:
        try:
            events = ask_llm(group)
            for ev in events:
                ev = [i for i in ev if i in by_id]
                if len(ev) < 2:
                    continue
                keep = canonical([by_id[i] for i in ev])
                duplicate_ids = [i for i in ev if i != keep["id"]]
                if duplicate_ids:
                    merges.append({"keeper_id": keep["id"], "duplicate_ids": duplicate_ids})
                    for i in duplicate_ids:
                        print(f"  dup: id {i} ({by_id[i]['source_name'][:18]}) -> keep {keep['id']} "
                              f"({keep['company_name']} {keep['job_count']} {keep['layoff_date']})")
        except Exception as e:  # one company's cluster failing must not abort the run
            skipped += 1
            print(f"  skipped cluster {group[0]['company_name'][:24]}: {e}")

    # A source link is evidence, not disposable duplicate clutter. The server
    # merges each confirmed report into the keeper's canonical event before it
    # removes the duplicate row, so /event/{id}/sources remains complete.
    deduped = {}
    for merge in merges:
        keeper = merge["keeper_id"]
        deduped.setdefault(keeper, set()).update(merge["duplicate_ids"])
    merges = [{"keeper_id": keeper, "duplicate_ids": sorted(ids)} for keeper, ids in deduped.items()]
    print(f"\n{sum(len(m['duplicate_ids']) for m in merges)} duplicate(s) to merge, {skipped} cluster(s) skipped")
    merged = fails = 0
    for i in range(0, len(merges), 100):
        batch = merges[i:i + 100]
        try:
            req = urllib.request.Request(f"{SITE}/wp-json/layoffs/v1/merge-events",
                data=json.dumps({"merges": batch,
                    "reason": "Daily cross-source dedup: same layoff event reported by multiple sources, confirmed by DeepSeek"}).encode(),
                headers={"X-Layoff-API-Key": KEY, "Content-Type": "application/json", "User-Agent": UA})
            res = json.load(urllib.request.urlopen(req, timeout=90))
            merged += len(res.get("merged_rows", []))
            print(res)
        except Exception as e:  # a failed batch is retried tomorrow, not fatal today
            fails += 1
            print(f"  merge batch failed (will retry next run): {e}")
    print(f"\nDone: {merged} merged, {fails} batch(es) deferred, {skipped} cluster(s) skipped")

    # Observability: publish what the dedup pass did to the same public health
    # ledger every other collector reports to, so "is dedup working?" is answered
    # by a live number instead of a guess. `remaining` = candidate clusters still
    # awaiting review across the whole backlog (the rotation works through them
    # over successive days); a persistently large `remaining` is the signal that
    # the cap or window needs attention.
    remaining = max(0, len(all_clusters) - len(clusters))
    detail = (f"{merged} duplicate row(s) merged this run from {len(clusters)} reviewed "
              f"cluster(s); {len(all_clusters)} candidate clusters total, ~{remaining} "
              f"awaiting a later rotation; {skipped} skipped, {fails} batch(es) deferred")
    status = "degraded" if (fails or (clusters and skipped == len(clusters))) else "ok"
    try:
        report_source_health("dedupe_llm", status, merged, detail)
    except Exception as e:  # health is observability, never the reason a cleanup run "fails"
        print(f"  dedup health write failed (non-fatal): {e}")

    # Only fail the run if literally nothing could be processed.
    if clusters and not merges and skipped == len(clusters):
        sys.exit(1)


if __name__ == "__main__":
    main()
