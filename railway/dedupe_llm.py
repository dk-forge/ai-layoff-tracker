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
different events). For each same-event group it keeps ONE canonical entry and
trashes the rest through /trash, which suppresses their hashes so the next
import cannot resurrect them and logs the removal in the public corrections
log.

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
import urllib.request
from collections import defaultdict

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_CLUSTERS = int(os.environ.get("DEDUPE_MAX_CLUSTERS") or 60)
WINDOW_DAYS = 120
SRC_RANK = {"8K": 3, "warn": 3, "press_release": 2, "erm": 2, "news": 1}


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
    n = re.sub(r"[^a-z0-9 ]", "", (name or "").lower())
    n = re.sub(r"\b(inc|corp|corporation|co|ltd|llc|plc|sa|ag|group|holdings|platforms|the)\b", "", n)
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
        d = api(f"query?sources=news,8K,press_release,erm&per_page=200&page={page}&sort=id&dir=asc")
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
                if lo / hi >= 0.75 and days_between(a["layoff_date"] or "", b["layoff_date"] or "") <= WINDOW_DAYS:
                    group.append(b)
                    used.add(b["id"])
            if len(group) > 1:
                used.add(a["id"])
                clusters.append(group)
    # biggest clusters first (most impact); bound the count
    clusters.sort(key=len, reverse=True)
    return clusters[:MAX_CLUSTERS]


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
        data=json.dumps({"model": "deepseek/deepseek-chat",
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
    rows = fetch_all()
    by_id = {r["id"]: r for r in rows}
    clusters = candidate_clusters(rows)
    print(f"{len(rows)} entries, {len(clusters)} candidate clusters to review")

    trash_ids = []
    for group in clusters:
        events = ask_llm(group)
        for ev in events:
            ev = [i for i in ev if i in by_id]
            if len(ev) < 2:
                continue
            keep = canonical([by_id[i] for i in ev])
            for i in ev:
                if i != keep["id"]:
                    trash_ids.append(i)
                    print(f"  dup: id {i} ({by_id[i]['source_name'][:18]}) -> keep {keep['id']} "
                          f"({keep['company_name']} {keep['job_count']} {keep['layoff_date']})")

    trash_ids = sorted(set(trash_ids))
    print(f"\n{len(trash_ids)} duplicate(s) to remove")
    if not trash_ids:
        return
    # trash in batches; /trash suppresses hashes + logs the correction
    for i in range(0, len(trash_ids), 100):
        batch = trash_ids[i:i + 100]
        req = urllib.request.Request(f"{SITE}/wp-json/layoffs/v1/trash",
            data=json.dumps({"ids": batch,
                "reason": "Daily cross-source dedup: same layoff event reported by multiple sources, confirmed by DeepSeek"}).encode(),
            headers={"X-Layoff-API-Key": KEY, "Content-Type": "application/json", "User-Agent": UA})
        print(json.load(urllib.request.urlopen(req, timeout=90)))


if __name__ == "__main__":
    main()
