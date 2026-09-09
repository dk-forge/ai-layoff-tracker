"""
Cross-source duplicate remover (the daily "deep scan").

Exact-hash and same-company-within-30-days dedup run at write time, but they
miss two cases: (1) WARN and ERM enter through /bulk, which does exact-hash
dedup only, so an ERM "Meta Platforms 8,000 (announced)" never checks against
a news "Meta 8,000"; (2) the same event reported more than 30 days apart, or
under a name variant ("Meta" vs "Meta Platforms"), slips the fuzzy window.

This pass groups entries by normalized company, forms candidate clusters of
similar job counts within a 120-day window, and asks an LLM (default
google/gemini-2.5-flash-lite, see MODEL below; DeepSeek until 2026-09-03 --
moved off it on compliance grounds, not a benchmark, see MODEL's own comment)
which entries are the SAME event reported multiple times versus genuinely
distinct layoffs (Meta cut 11,000 in 2022, 10,000 in 2023 and 8,000 in 2026 —
same company, different events). For each confirmed group it keeps ONE
canonical entry and moves every duplicate's source report onto that event
before removing the extra row. The public event-source endpoint therefore
retains every receipt.

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

import host_call
from source_health import report_source_health
import spend

JOB = "dedupe-llm"
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# THE DEDUP JUDGE. Deliberately a second copy of extractor.MODEL's default,
# not an import: this module is stdlib-only on purpose (no openai SDK), and a
# copy that quietly drifted from extractor.py used to be the point (kept an
# "unmeasured surface" from moving just because an extraction benchmark did).
# Moved off deepseek/deepseek-chat on 2026-09-03 -- COMPLIANCE, not a
# benchmark: the owner ruled DeepSeek unusable months ago on EU grounds, and
# an unmeasured surface does not get an exception from that. Set to the same
# model extractor.py's classify path now defaults to, for the same reason
# (the one model actually measured on this project's layoff text, and cheaper
# than what it replaces). tests/test_extraction_model_choice.py pins this
# default via the request this module actually builds.
MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
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
UNKNOWN_COUNTRIES = {"", "unknown", "multiple countries", "world", "worldwide"}
ERM_FACTSHEET_RX = re.compile(r"/restructuring-events/detail/(\d+)(?:[/?#]|$)", re.I)


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
    # Use the shared host-call policy so deploy maintenance becomes a counted
    # deferral while refusals, missing routes and malformed success bodies stay
    # real failures.
    return host_call.get_json(
        f"{SITE}/wp-json/layoffs/v1/{path}",
        headers={"User-Agent": UA}, timeout=90)


def norm_company(name):
    # Kept in sync with the plugin's alt_company_key (includes/api.php) so the two
    # dedup layers reach the same same-company verdict: same legal-suffix set plus
    # the trailing geographic qualifiers (America/USA/International/Global).
    n = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())   # punctuation -> space, like the PHP key ("Amazon.com" -> "amazon com")
    n = re.sub(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|sa|ag|group|holdings|holding|technologies|technology|systems|solutions|platforms|the|com)\b", "", n)
    n = re.sub(r"\b(america|americas|usa|us|international|global|worldwide|na)\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


# ---------------------------------------------------------------------------
# BUCKETING IS NOT IDENTITY, AND THIS IS THE DIFFERENCE.
#
# `norm_company` above mirrors the plugin's alt_company_key: it is an IDENTITY
# key, and two rows sharing it are treated as the same employer by both dedup
# layers. `bucket_key` below is only a CANDIDATE-GENERATION key. Sharing it
# buys a pair exactly one thing: the right to be compared. Every hard gate
# still runs afterwards -- pair_can_be_same_event (federal_rif, a country
# mismatch, two different ERM factsheet ids), the 75% job-count ratio,
# pair_window_days -- and then the model decides which ids are one event.
# Bucketing cannot merge anything on its own.
#
# WHY IT EXISTS. Bucketing ran on norm_company, which is upstream of every
# guard, so a name variant did not produce a bad merge -- it produced NO
# COMPARISON AT ALL, silently, at zero cost, with nothing to observe. Live on
# 2026-09-09: "Volkswagen" (50,000, 2026-09-03) and "Volkswagen (VW)" (50,000,
# 2026-09-04) sat in the buckets `volkswagen` and `volkswagen vw` and were
# never candidates, while a fourth report of the same event WAS caught by the
# same job. "Grupo Volkswagen" made a third bucket.
#
# EVERY TOKEN BELOW WAS READ OUT OF THE LIVE CORPUS (42,719 distinct company
# names from /companies plus a paced 2,200-row sample of the news/8K/ERM rows
# this job actually fetches), never guessed, and the ones the data REFUSED are
# recorded here because that is the load-bearing half:
#   * `spa` is NOT stripped. All 82 trailing "Spa" names in the corpus are
#     resorts ("Rancho Valencia Resort & Spa"), not Italian S.p.A. The dotted
#     form is handled separately below, which is exactly what tells them apart.
#   * `kgaa` is NOT stripped. It would put "Merck KGaA" (Darmstadt) and
#     "Merck & Co" (Rahway) in one bucket, and they are different companies.
#   * `konzern`/`koncern` are NOT stripped: zero occurrences in any leading or
#     trailing position (the corpus has "Południowy Koncern Energetyczny",
#     where the word is mid-name and stripping it would be wrong).
#   * Tokens with no trailing occurrence at all (srl, pte, pty, bhd, kk, ...)
#     are left out. A list longer than the evidence is a list nobody measured.
# ---------------------------------------------------------------------------

#: Legal forms observed as the LAST token of a real name in the corpus (counts
#: from the 42,719-name read: ab 36, gmbh 21, nv 13, as 12, sas 10, se 7, kg 6,
#: oyj 5, bv 3, oy 3, sarl 2, asa 1). Stripped repeatedly, because Nordic names
#: stack them ("Rolls-Royce Oy Ab").
#: `zoo` was tried and REJECTED by the same read: all five trailing "Zoo" names
#: are actual zoos ("Santa Barbara Zoo"), not Polish "z o.o." -- that form is
#: spelled with dots and is handled below, on the raw string.
_LEGAL_SUFFIX_TOKENS = ("gmbh", "oyj", "sarl", "asa", "sas", "nv", "bv",
                        "ab", "as", "se", "oy", "kg")
_LEGAL_SUFFIX_RX = re.compile(r"\s(?:%s)$" % "|".join(_LEGAL_SUFFIX_TOKENS))

#: Dotted legal forms, matched on the RAW name before punctuation is flattened.
#: Doing it here rather than on tokens is what keeps "S.A." from eating the
#: "U.S.A." in "Yamaha Motor Finance Corporation U.S.A.": the match must start
#: at a space, and in "U.S.A." the S does not.
#: EVERY alternative here REQUIRES a dot or a slash. That is not decoration:
#: an undotted "Spa" is a resort in this corpus 82 times out of 82, and a
#: dotless alternative would strip it off "Rancho Valencia Resort & Spa".
_LEGAL_DOTTED_RX = re.compile(
    r"[\s,]+(?:s\.p\.?a\.?|a\.s\.?|a/s|n\.v\.?|b\.v\.?|d\.d\.?"
    r"|s\.a\.r\.l\.?|sp\.?\s*z\s*o\.\s*o\.?)\s*$", re.I)

#: "Group" in the languages the corpus actually uses, as a prefix or a suffix.
#: English `group` is already stripped by norm_company; not stripping the other
#: spellings was an English-only bug, not a policy ("Grupo Volkswagen",
#: "Groupe Compass Canada", "Grupa OLX", "WAZ-Gruppe", "Telegraaf Media Groep").
_GROUP_WORDS = ("grupo", "groupe", "gruppo", "grupa", "gruppen", "gruppe", "groep")
_GROUP_LEAD_RX = re.compile(r"^(?:%s)\s" % "|".join(_GROUP_WORDS))
_GROUP_TRAIL_RX = re.compile(r"\s(?:%s)$" % "|".join(_GROUP_WORDS))

#: A parenthetical is dropped only when what remains still reads as a NAME.
#: This is the guard against the one real over-collapse the corpus contains:
#: "CTS (Coyne Textile Services)" and "CTS Corp." are different companies, and
#: so are "BD (Becton Dickinson)" and "BD (C.R. Bard Inc.)". A bare all-caps
#: initialism is not a name, it is a handle that needs its expansion to stay
#: distinguishable -- so it keeps the parenthetical and simply does not widen.
#: A short head that carries a lowercase letter is a word, not a handle, which
#: is what lets "Meta (Facebook)", "Flex (Flex Global Operations)" and "Sony
#: (Game Division)" widen while CTS/BD/ČSA do not. Measured over the full
#: corpus, that relaxation adds exactly three buckets and no wrong one.
_PAREN_MIN_HEAD_CHARS = 5
_PAREN_MIN_WORD_CHARS = 3


def _strip_parenthetical(name):
    head = re.sub(r"\s*\([^)]*\)", " ", name)
    head = re.sub(r"\s+", " ", head).strip(" ,-")
    size = len(re.sub(r"[^A-Za-z0-9]", "", head))
    if size >= _PAREN_MIN_HEAD_CHARS:
        return head
    if size >= _PAREN_MIN_WORD_CHARS and any(c.islower() for c in head):
        return head
    return name


def bucket_key(name):
    """Candidate-generation key: broader than norm_company, never an identity.

    Collapses the three name-variation classes the live corpus shows -- a
    parenthetical alias or ticker, a legal form in any of the languages we
    ingest, and "Group" in any of them -- so those pairs REACH the evidence
    gates and the model. It decides nothing on its own.

    A strip is never allowed to empty the key: "SAS" is an airline, not a
    French legal form with nothing in front of it, and a row whose key goes
    empty leaves the candidate set entirely (candidate_clusters skips a blank
    key), which would turn a widening into a silent loss of coverage.
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    stage = _strip_parenthetical(raw)
    dotted = _LEGAL_DOTTED_RX.sub("", stage)
    if dotted.strip():
        stage = dotted
    tokens = re.sub(r"[^a-z0-9]+", " ", stage.lower()).strip()
    while True:
        shorter = _LEGAL_SUFFIX_RX.sub("", tokens).strip()
        if not shorter or shorter == tokens:
            break
        tokens = shorter
    for rx in (_GROUP_LEAD_RX, _GROUP_TRAIL_RX):
        shorter = rx.sub(" ", tokens).strip()
        if shorter:
            tokens = shorter
    key = norm_company(tokens)
    # Everything above is a widening, so it must never subtract: if the extra
    # stripping leaves nothing, fall back to the identity key the bucketing
    # used before this function existed.
    return key or norm_company(raw)


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
        # Federal RIF rows are agency-month aggregates. Two rows for the same
        # agency are distinct observations even when the counts are similar,
        # so they must never enter a fuzzy cross-outlet dedup pass.
        d = api(f"query?sources=news,8K,press_release,erm&per_page=200&page={page}&sort=id&dir=asc")
        rows += d["data"]
        if page * 200 >= d["total"] or not d["data"]:
            break
        page += 1
        time.sleep(0.5)
    return rows


def _erm_factsheet_id(row):
    if str(row.get("source_type") or "").lower() != "erm":
        return ""
    match = ERM_FACTSHEET_RX.search(str(row.get("source_url") or ""))
    return match.group(1) if match else ""


def pair_can_be_same_event(a, b):
    """Hard evidence gates applied before any probabilistic merge judgment."""
    source_types = {str(a.get("source_type") or "").lower(),
                    str(b.get("source_type") or "").lower()}
    if "federal_rif" in source_types:
        return False

    country_a = str(a.get("country") or "").strip().lower()
    country_b = str(b.get("country") or "").strip().lower()
    if (country_a not in UNKNOWN_COUNTRIES and country_b not in UNKNOWN_COUNTRIES
            and country_a != country_b):
        return False

    factsheet_a = _erm_factsheet_id(a)
    factsheet_b = _erm_factsheet_id(b)
    if factsheet_a and factsheet_b and factsheet_a != factsheet_b:
        return False
    return True


def candidate_clusters(rows):
    """Same company BUCKET + job counts within 25% + dates within window.

    The bucket is bucket_key, deliberately broader than the identity key: it
    only decides which pairs get compared. pair_can_be_same_event, the count
    ratio, the window and then the model still stand between a candidate and
    a merge.
    """
    by_co = defaultdict(list)
    for r in rows:
        if str(r.get("source_type") or "").lower() == "federal_rif":
            continue
        by_co[bucket_key(r["company_name"])].append(r)
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
                # Compare with every row already in the cluster: an unknown-
                # geography report may pair with France OR Germany, but must
                # never bridge those two known-different events into one LLM
                # prompt where the model could merge all three.
                compatible = all(pair_can_be_same_event(existing, b) for existing in group)
                if (compatible and lo / hi >= 0.75
                        and days_between(a["layoff_date"] or "", b["layoff_date"] or "") <= pair_window_days(lo, hi)):
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
                "source_type": r.get("source_type") or "",
                "country": r.get("country") or "",
                "source_url": r.get("source_url") or "",
                "excerpt": (r["excerpt"] or "")[:180]} for r in group]
    prompt = ("These layoff-tracker entries are all the same company. Some are the SAME layoff "
              "event reported by different outlets or sources; others are DISTINCT layoffs at "
              "different times. Group the ids: each group is one real event. A big round number "
              "repeated within a few weeks across outlets is usually one event; the same number "
              "years apart is usually distinct events. Reply STRICT JSON "
              '{"events":[[id,id,...],[id,...]]} covering every id exactly once.\n\n'
              + json.dumps(payload, ensure_ascii=False))
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps({"model": MODEL,
                         "messages": [{"role": "user", "content": prompt}],
                         "response_format": {"type": "json_object"}}).encode(),
        headers={"Authorization": "Bearer " + OR_KEY, "Content-Type": "application/json", "User-Agent": UA})
    for attempt in range(3):
        try:
            # Through metered_call, so the ceiling is re-read before EVERY
            # attempt. A retry is a second charge, and the loop below used to
            # sit behind one gate check per cluster: three attempts on a
            # cluster that trips the ceiling on the first is three charges past
            # the line, for one budget check.
            out = spend.metered_call(
                MODEL,
                lambda: json.load(urllib.request.urlopen(req, timeout=150)),
                what="an LLM dedup review")
            c = out["choices"][0]["message"]["content"]
            c = c[c.find("{"): c.rfind("}") + 1]
            return json.loads(c).get("events", [])
        except spend.PaidReadsOff as e:
            # Not a failed cluster: an unasked one. The rotation re-selects it.
            print(f"  {e}")
            return []
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


def _run():
    if not (SITE and KEY and OR_KEY):
        print("WP_SITE_URL / WP_API_KEY / OPENROUTER_API_KEY required")
        return 1

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

    # Spend guard: this script builds its own OpenRouter client, so
    # extractor.py's gate does not cover it. Until 2026-08-02 that meant this
    # job IGNORED the guard entirely — the workflow's --degrade step set
    # ALT_PAID_READS=off and nothing here ever read it. Skip cleanly instead:
    # the rotation re-selects the same clusters on the next run, so a
    # deferred review costs a day, never coverage.
    if not spend.paid_reads_enabled():
        print("paid reads are OFF (spend ceiling) — skipping the LLM dedup "
              "review this run; the rotation resumes on the next schedule")
        spend.record_job_run(items=0, changed=0)
        return 0

    merges, skipped = [], 0
    for group in clusters:
        if not spend.paid_reads_enabled():
            # The per-run ceiling tripped mid-review. Merge what was already
            # adjudicated; the untouched clusters rotate back tomorrow.
            print("  per-run spend ceiling reached — deferring the remaining "
                  "clusters to the next run")
            break
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
                        duplicate = by_id[i]
                        print(
                            "  dup: "
                            f"id {i} ({duplicate['company_name']} {duplicate['job_count']} "
                            f"{duplicate['layoff_date']} {duplicate.get('country') or '(country blank)'} "
                            f"{duplicate.get('source_type') or '(type blank)'} "
                            f"{duplicate.get('source_url') or '(URL blank)'}) -> "
                            f"keep {keep['id']} ({keep['company_name']} {keep['job_count']} "
                            f"{keep['layoff_date']} {keep.get('country') or '(country blank)'} "
                            f"{keep.get('source_type') or '(type blank)'} "
                            f"{keep.get('source_url') or '(URL blank)'})")
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
                    "reason": "Daily cross-source dedup: same layoff event reported by multiple sources, confirmed by the configured adjudication model"}).encode(),
                headers={"X-Layoff-API-Key": KEY, "Content-Type": "application/json", "User-Agent": UA})
            res = json.load(urllib.request.urlopen(req, timeout=90))
            merged += len(res.get("merged_rows", []))
            print(res)
        except Exception as e:  # a failed batch is retried tomorrow, not fatal today
            fails += 1
            print(f"  merge batch failed (will retry next run): {e}")
    print(f"\nDone: {merged} merged, {fails} batch(es) deferred, {skipped} cluster(s) skipped")
    spend.record_job_run(items=len(clusters), changed=merged)

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
        return 1
    return 0


def main():
    """Defer transient WordPress downtime without concealing real failures."""
    try:
        code = _run()
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc), source="dedupe_llm")
    host_call.clear(JOB)
    return code


if __name__ == "__main__":
    sys.exit(main())
