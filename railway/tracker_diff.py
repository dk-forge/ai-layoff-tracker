"""Tracker-diff discovery tripwire — automated 'work backwards from other trackers'.

Takes a competitor company list, diffs it against our own data, and for anything
they list that we lack, fires a company-TARGETED primary-source query → the same
DeepSeek extractor + dedup + poster. We never cite the competitor: their list is a
discovery SIGNAL that points us at a primary source, which is what actually gets
stored. Company names arrive ONLY via a secret (never committed, per the
standalone-brand rule), and only counts/slice indices are logged — never the list.

Two ways to supply the list (use either or both):
  * BENCHMARK_FEED_URLS  — comma-separated URLs, each returning a JSON array of
    {company, date?, jobs?} objects (or {"data":[...]}/{"events":[...]}) OR a CSV
    with a `company`/`company_name`/`name` column.
  * BENCHMARK_COMPANIES  — the list pasted inline (comma- or newline-separated
    company names). Use this when the competitor has no machine feed but you can
    see their list: paste the names into this secret and the cron chases them.

Ships DORMANT: with neither set it logs and exits clean, so the repo carries zero
competitor data. The owner adds a secret to activate.

Each daily run chases a rotating slice (TRACKER_DIFF_MAX companies), so over a few
days the WHOLE list is walked — not just the first slice each time.

Env: BENCHMARK_FEED_URLS, BENCHMARK_COMPANIES (secrets), TRACKER_DIFF_MAX
(default 40 companies per run), TRACKER_DIFF_DRY=1 (log, don't post).
"""
import csv
import io
import json
import os
import re
import sys
import time
from datetime import date

import requests

from company_watchlist import already_have, query_for, DAYS_BACK
from sources.newsapi import pull_news_articles
from sources.google_news import pull_google_news
from sources.edgar import search_company_filings
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
FEEDS = [u.strip() for u in (os.environ.get("BENCHMARK_FEED_URLS") or "").split(",") if u.strip()]
INLINE = [n.strip() for n in re.split(r"[,\n]", os.environ.get("BENCHMARK_COMPANIES") or "") if n.strip()]
MAX_CHASE = max(1, int(os.environ.get("TRACKER_DIFF_MAX", "40")))
# Recall alarm: email the owner when our coverage of the reference list drops
# below this percent. Names go ONLY to the owner's inbox (never the repo, health
# ledger, or Actions log), so the standalone-brand rule holds.
RECALL_ALERT_PCT = float(os.environ.get("TRACKER_DIFF_RECALL_ALERT_PCT", "90"))
RECALL_ALERT_MAX_NAMES = max(5, int(os.environ.get("TRACKER_DIFF_RECALL_MAX_NAMES", "60")))
# Weaning thresholds (see the WEANING block below _norm). Defined HERE with the
# other env config: test_tracker_diff_sitemap exec's the _norm..run source slice
# in a bare namespace, so that region must stay free of module-level os reads.
IND_WEAN_PCT = float(os.environ.get("TRACKER_DIFF_WEAN_PCT", "90"))
IND_WEAN_DAYS = max(7, int(os.environ.get("TRACKER_DIFF_WEAN_DAYS", "21")))
FORCE_CHASE = os.environ.get("TRACKER_DIFF_FORCE_CHASE", "").lower() in {"1", "true", "yes"}
# Tag namespaces mix companies with topics/cities; drop the obvious non-company
# slugs so we never chase "layoffs" or "san-francisco" as if it were an employer.
_SITEMAP_STOP = {
    "ai", "layoffs", "layoff", "tech", "startup", "startups", "crypto", "fintech",
    "aerospace", "hardware", "software", "healthcare", "media", "retail", "finance",
    "food", "energy", "education", "logistics", "manufacturing", "marketing",
    "san-francisco", "new-york", "london", "bangalore", "remote", "usa", "uk",
    "india", "europe", "layoffs-2024", "layoffs-2025", "layoffs-2026", "news", "press",
    # cities appear as tags in these lists; they are locations, not employers
    "atlanta", "austin", "berlin", "boston", "chicago", "seattle", "denver",
    "los-angeles", "miami", "toronto", "dublin", "singapore", "tel-aviv",
    "amsterdam", "paris", "sydney", "melbourne", "dallas", "houston", "phoenix",
    "portland", "pittsburgh", "detroit", "nashville", "washington-dc",
    "new-york-city", "san-francisco-bay-area", "silicon-valley", "bengaluru",
    "mumbai", "delhi", "hyderabad", "pune", "chennai", "gurugram", "noida",
    "tokyo", "hong-kong", "shanghai", "beijing", "dubai", "abu-dhabi",
    "vancouver", "montreal", "atlanta-ga", "raleigh", "denver-co", "boulder",
    # topic / non-employer tags common on layoff sitemaps
    "hiring", "funding", "ipo", "acquisition", "merger", "recession",
    "remote-work", "return-to-office", "salaries", "severance", "wfh",
    "big-tech", "faang", "unicorn", "series-a", "series-b", "vc", "yc",
    "job-cuts", "restructuring", "downsizing", "furlough", "buyout",
    "healthcare", "biotech", "pharma", "edtech", "adtech", "insurtech",
    "proptech", "cleantech", "climate-tech", "cybersecurity", "saas",
    "e-commerce", "logistics", "automotive", "manufacturing", "banking",
    "north-america", "south-america", "middle-east", "africa", "asia-pacific",
    "germany", "france", "spain", "italy", "netherlands", "sweden", "canada",
    "australia", "japan", "china", "united-kingdom", "united-states",
}
# A tag is dropped when it is a single generic word OR clearly a place/topic. A
# real company slug almost always has 2+ tokens or a legal suffix; a bare
# lowercase single word is far more likely to be a topic/city than an employer.
DRY = os.environ.get("TRACKER_DIFF_DRY", "").lower() in {"1", "true", "yes"}


def _parse_feed(url, label):
    """Return a list of company names from a competitor feed (JSON or CSV).

    NEVER print the URL (it's a private competitor source in a secret; a URL
    substring can slip past GitHub's secret masking into a public Actions log).
    Reference the feed only by its index `label`.
    """
    try:
        r = requests.get(url, headers=UA, timeout=40)
        if r.status_code != 200:
            print(f"feed {label}: HTTP {r.status_code}")
            return []
        body = r.text
    except Exception as exc:
        print(f"feed {label}: fetch failed ({type(exc).__name__})")
        return []
    names = []
    body_strip = body.lstrip()
    # A sitemap (or sitemap index) is the cleanest competitor feed: one URL that
    # auto-expands to the full, self-refreshing company list, so the secret
    # holds a single link instead of thousands of pasted names going stale. A
    # tag/company sitemap encodes each company as a URL slug (/tag/acme-corp/,
    # /company/acme-corp/); de-slugify it back to a name for the diff.
    if body_strip[:5].lower() == "<?xml" or "<urlset" in body_strip[:400] or "<sitemapindex" in body_strip[:400]:
        locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", body, re.I)
        # A sitemap INDEX points at child sitemaps; follow the ones that look
        # like per-company tag/company maps (bounded, so a hostile index can't
        # fan out forever).
        child_maps = [u for u in locs if re.search(r"(tag|compan|organi[sz]ation)", u, re.I)][:6]
        if child_maps and not re.search(r"/(tag|company)/[^/]+/?$", locs[0] if locs else ""):
            for cu in child_maps:
                try:
                    cr = requests.get(cu, headers=UA, timeout=40)
                    if cr.status_code == 200:
                        locs += re.findall(r"<loc>\s*([^<]+?)\s*</loc>", cr.text, re.I)
                except Exception:
                    pass
        for u in locs:
            m = re.search(r"/(?:tag|company|organi[sz]ation)/([^/?#]+)/?", u, re.I)
            if not m:
                continue
            slug = m.group(1)
            # Skip non-company tags that share the namespace (cities, topics).
            # Pure-numeric tags (/tag/200/ = a headcount, not an employer) and
            # stop-listed cities/topics/countries never become "companies".
            if slug.lower() in _SITEMAP_STOP or len(slug) < 2 or slug.isdigit():
                continue
            name = re.sub(r"[-_]+", " ", slug).strip()
            # Title-case only all-lowercase slugs; leave AllBirds/23andMe alone.
            if name and name == name.lower():
                name = name.title()
            names.append(name)
        # de-dupe, keep order
        seen = set(); out = []
        for n in names:
            k = n.lower()
            if k not in seen:
                seen.add(k); out.append(n)
        print(f"feed {label}: sitemap parsed -> {len(out)} company name(s)")
        return out
    if body_strip[:1] in ("[", "{"):
        try:
            data = json.loads(body)
            rows = data if isinstance(data, list) else (data.get("data") or data.get("events") or [])
            for r in rows:
                if isinstance(r, dict):
                    n = r.get("company") or r.get("company_name") or r.get("name")
                    if n:
                        names.append(str(n).strip())
        except Exception as exc:
            print(f"feed {label}: JSON parse failed ({type(exc).__name__})")
    else:
        try:
            for row in csv.DictReader(io.StringIO(body)):
                n = (row.get("company") or row.get("company_name") or row.get("name") or "").strip()
                if n:
                    names.append(n)
        except Exception as exc:
            print(f"feed {label}: CSV parse failed ({type(exc).__name__})")
    return names


# The "learn" step: a company we cannot verify from any source we scan is a
# signal about a MISSING SOURCE, not just a missing row. Cluster the unresolved
# names by cheap deterministic hints so each run answers "what should we add
# next", ranked by how many misses it would fix. Heuristic and labelled as a
# hint, never a fact.
_GAP_HINTS = (
    ("crypto / web3 trade press (The Block, CoinDesk, Decrypt)",
     ("crypto", "web3", "blockchain", "token", "chain", "dao", "nft", "defi",
      "protocol", "labs", "network", "polygon", "guild")),
    ("India / SEA startup press (Inc42, YourStory, Entrackr)",
     ("india", "bangalore", "mumbai", "singapore", "jakarta", "gojek", "paytm")),
    ("Israel tech press (Globes, Calcalist, CTech)",
     ("israel", "tel aviv", "cyber", "wiz", "monday")),
    ("gaming / iGaming trade press",
     ("games", "gaming", "studio", "poker", "casino", "esports", "playtika")),
    ("LATAM business press (Exame, InfoMoney, NeoFeed)",
     ("brazil", "sao paulo", "mexico", "latam", "hotmart", "nubank")),
    ("EU startup press (Sifted, EU-Startups, Tech.eu)",
     ("berlin", "paris", "amsterdam", "stockholm", "gmbh", "sp z o o")),
)


def _cluster_gaps(unresolved):
    """Return ranked (category, count, examples) for the unresolved names."""
    buckets = {}
    for name in unresolved:
        low = " " + re.sub(r"[^a-z0-9 ]+", " ", name.lower()) + " "
        for label, toks in _GAP_HINTS:
            if any(f" {t} " in low or low.strip().endswith(t) or t in low for t in toks):
                buckets.setdefault(label, []).append(name)
                break
    ranked = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
    return [(lab, len(names), names[:4]) for lab, names in ranked]


def _norm(name):
    """Loose company key for the SEC cross-reference guard."""
    n = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower())
    n = re.sub(r"\b(inc|corp|corporation|co|ltd|llc|plc|sa|ag|nv|group|holdings|the)\b", " ", n)
    return re.sub(r"\s+", " ", n).strip()


# ---------------------------------------------------------------------------
# WEANING: the reference lists are a teacher, not a crutch. Three mechanisms
# make the dependence measurable and shrink it over time:
#   1. INDEPENDENT RECALL — of the companies they list, how many did our OWN
#      pipeline already have (i.e., have MINUS ever-chase-resolved)? This is
#      the "we don't need them" number, recorded daily server-side.
#   2. LEARN FROM WINS — when a chase resolves a company, remember WHICH outlet
#      carried it. An outlet that repeatedly closes gaps but is not in our
#      allowlist is a ranked candidate to join the permanent net.
#   3. GRADUATED CADENCE — once independent recall holds >=90% for 21 straight
#      recorded days, the chase steps down to Mondays only (the recall gauge
#      still runs daily). If they ever block robots, coverage barely moves.
# State lives in the keyed /tracker-meta endpoint (WP DB) — names never touch
# the repo or the Actions log, so the standalone-brand rule holds.
# (IND_WEAN_PCT / IND_WEAN_DAYS / FORCE_CHASE are defined with the env config
# at the top of the file — this region must stay free of module-level os reads
# because test_tracker_diff_sitemap exec's the _norm..run slice bare.)
# ---------------------------------------------------------------------------


def _meta_sync(payload):
    """Merge payload into the server-side weaning memory; return full state.
    Fail-soft: a blip returns {} and the run continues without the gauge."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return {}
    try:
        r = requests.post(f"{site}/wp-json/layoffs/v1/tracker-meta",
                          json=payload, headers={**UA, "X-ALT-KEY": key}, timeout=30)
        return r.json() if r.status_code == 200 else {}
    except Exception as exc:
        print(f"tracker-meta sync failed (non-fatal): {exc}")
        return {}


def chase_today(ind_history, today, wean_pct=None, wean_days=None):
    """True if the full chase should run today. Pure + tested.

    Daily until independent recall has held >= wean_pct for wean_days straight
    recorded points; after that, Mondays only. Any dip below the bar snaps the
    cadence back to daily — weaning is earned continuously, never a ratchet."""
    wean_pct = IND_WEAN_PCT if wean_pct is None else wean_pct
    wean_days = IND_WEAN_DAYS if wean_days is None else wean_days
    pts = [p for p in (ind_history or []) if isinstance(p, dict) and "ind" in p]
    if len(pts) < wean_days:
        return True
    recent = pts[-wean_days:]
    if all(float(p["ind"]) >= wean_pct for p in recent):
        return today.weekday() == 0  # weaned: Monday spot-check only
    return True


def _win_key(raw):
    """Outlet identity for learn-from-wins: a real domain when the source URL
    has one, else the outlet name (Google News links are redirects, so the RSS
    <source> name is the truthful identity there)."""
    url = str(raw.get("source_url") or "")
    m = re.search(r"https?://(?:www\.)?([^/]+)/", url + "/")
    dom = (m.group(1).lower() if m else "")
    if dom and "google." not in dom:
        return dom
    name = re.sub(r"\s+", " ", str(raw.get("source_name") or "").strip().lower())
    return name


def _covered_by_allowlist(outlet, trusted):
    """Is this win's outlet already admitted by the allowlist?

    `_win_key` yields EITHER a real hostname ('inc42.com') or, for Google News
    redirects, the RSS outlet NAME ('techcrunch', 'globes english'), so both
    shapes have to be judged and they are judged differently.

    This used to be one substring test — the outlet's first label appearing
    anywhere inside any trusted domain. That silently suppressed genuine
    candidates: 'news.example.com' matched because 'news' sits inside
    'apnews.com', 'ft.co.za' because of 'ft.com', 'post.co.uk' because of
    'washingtonpost.com'. Since suppression means "already covered, do not
    suggest", the bug starved the exact learning loop this function feeds.
    """
    if "." in outlet and " " not in outlet:
        # A hostname: covered when the allowlist admits this host or its parent,
        # the same test gdelt._is_trusted applies to every collected article.
        return any(outlet == d or outlet.endswith("." + d) for d in trusted)
    # An outlet name: covered when it names the FIRST LABEL of a trusted domain
    # ('techcrunch' -> techcrunch.com). A whole-label comparison, never a
    # substring, so 'news' cannot match 'apnews.com'.
    name = re.sub(r"[^a-z0-9]+", "", outlet)
    return bool(name) and any(name == d.split(".")[0] for d in trusted)


def outlet_suggestions(wins, trusted_domains):
    """Outlets that closed >=2 gaps but are not in the allowlist — ranked,
    these are the permanent-net candidates that shrink future dependence.
    Win keys may carry a country suffix ('sifted.eu · Germany') so the owner
    learns WHERE each repeat winner reports from; matching against the
    allowlist uses only the outlet part before the suffix."""
    trusted = {d.lower() for d in (trusted_domains or [])}
    out = []
    for key, cnt in sorted((wins or {}).items(), key=lambda kv: -int(kv[1])):
        if int(cnt) < 2 or not key:
            continue
        outlet = key.split(" · ")[0].strip()
        if _covered_by_allowlist(outlet, trusted):
            continue
        out.append((key, int(cnt)))
    return out[:10]


def vocab_hit(text, terms):
    """True when any discovery term appears in the text. A resolved win whose
    headline matches NO term is the sharpest learning signal we get: that story
    was invisible to our broad sweep and only a targeted chase found it — its
    wording belongs in the vocabulary."""
    low = " " + re.sub(r"\s+", " ", str(text or "").lower()) + " "
    # WORD boundaries, not substrings: "RIF" lives inside "tariff", "sacked"
    # inside "ransacked" — plain substring matching made almost every headline
    # a false hit and silently suppressed the whole signal (audit 2026-07-25).
    return any(t and re.search(r"\b" + re.escape(t.lower()) + r"\b", low)
               for t in (terms or []))


def _email_recall_gap(missing, recall_pct, n_total):
    """Email the owner the tracked layoffs we're MISSING vs the reference list,
    so a coverage gap self-surfaces instead of being noticed by hand. PRIVATE:
    company names go only to the owner's inbox via /alert, never to the repo,
    the health ledger, or the Actions log. Fires only below the alert threshold
    so a healthy day is silent. Never raises."""
    if recall_pct >= RECALL_ALERT_PCT or not missing:
        return
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return
    shown = sorted(missing, key=str.lower)[:RECALL_ALERT_MAX_NAMES]
    more = f" (first {len(shown)} of {len(missing)})" if len(missing) > len(shown) else ""
    subject = (f"Coverage recall {recall_pct}%: missing {len(missing)} of "
               f"{n_total} tracked layoffs")
    body = "\n".join([
        "The recall audit compared our data against the reference layoff list.",
        f"We carry {n_total - len(missing)} of {n_total} ({recall_pct}%). "
        f"Missing {len(missing)}.",
        "",
        f"Companies on the list with no current-year entry of ours{more}:",
        "  " + ", ".join(shown),
        "",
        "Likely causes: NewsAPI discovery is empty (paywalled outlets are not",
        "indexed), or the announced headcount is not in a machine-readable source",
        "so the extractor skips it. To chase these now, open a Claude Code session",
        "in the ai-layoff-tracker repo and paste:",
        '  "Run tracker_diff to chase the missing companies; for any still missing,',
        '   widen discovery and store the announced figure with an announced label."',
    ])
    try:
        requests.post(f"{site}/wp-json/layoffs/v1/alert",
                      json={"subject": subject, "body": body},
                      headers={"X-Layoff-API-Key": key, "User-Agent": UA["User-Agent"]},
                      timeout=25)
        print(f"recall-gap alert emailed to owner ({recall_pct}% recall, "
              f"{len(missing)} missing)")
    except Exception as exc:
        print(f"recall alert failed: {exc}")


def _email_learning(vocab_misses, suggestions):
    """Owner-only learning digest: headlines our broad sweep could not see plus
    repeat-winner outlets, so vocabulary and allowlist growth is a one-line
    paste instead of detective work. Best-effort; never raises."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return
    lines = ["The daily chase resolved layoffs our own sweep missed. What to learn:\n"]
    if vocab_misses:
        lines.append("Headlines matching NO discovery term (add the missing wording):")
        lines += [f"  - {h}" for h in vocab_misses[:10]]
    if suggestions:
        lines.append("\nOutlets that keep closing gaps (allowlist candidates, with country):")
        lines += [f"  - {cnt}x {dom}" for dom, cnt in suggestions[:10]]
    lines.append("\nPaste into a Claude session: \"Adopt the outlet/vocabulary learnings from "
                 "today\'s tracker_diff learning email.\"")
    try:
        requests.post(f"{site}/wp-json/layoffs/v1/alert",
                      json={"subject": "Tracker learning: wording/outlets our sweep missed",
                            "message": "\n".join(lines)},
                      headers={**UA, "X-ALT-KEY": key}, timeout=30)
        print("learning email sent to owner")
    except Exception as exc:
        print(f"learning email failed (non-fatal): {exc}")


def run():
    if not FEEDS and not INLINE:
        print("Neither BENCHMARK_FEED_URLS nor BENCHMARK_COMPANIES set — tripwire "
              "dormant, nothing to diff. Paste a competitor company list into the "
              "BENCHMARK_COMPANIES secret (or a feed URL into BENCHMARK_FEED_URLS) "
              "to activate; either stays out of the repo.")
        # A DORMANT RUN STILL REPORTS, and that is the whole point of this call.
        #
        # This branch used to `return` here, before any report_source_health().
        # The job is scheduled daily and exits green daily, so the LAST health
        # row stayed frozen at whatever the final armed run wrote: 2026-07-26,
        # two days before the owner made it dormant. Staleness is measured from
        # checked_at, so the public Tracker Health page has said this collector
        # "may have STOPPED" ever since and would have said it forever. That is
        # the CLAUDE.md three-step retirement rule missing its third step: a
        # source removed from duty whose remaining path still owns a health id.
        #
        # Reported as `ok` deliberately, not `degraded`. Nothing is broken: the
        # job ran, and doing nothing is the correct behaviour when unarmed. The
        # detail carries WHY, so nobody re-diagnoses this as a dead scraper, and
        # the checked_at it refreshes is a real run of real code. `dormant` is
        # not a status the health page, ops_status or the digest understand, and
        # inventing one here would publish a word three readers render as
        # unknown. This is also NOT `retired`: retired is one-way and masked,
        # while this is one secret away from live.
        report_source_health(
            "tracker_diff", "ok", 0,
            "Dormant by owner decision (2026-07-28): no competitor feed configured, "
            "so there is nothing to diff and the run costs nothing. Not broken and "
            "not retired. Set BENCHMARK_COMPANIES or BENCHMARK_FEED_URLS to re-arm.")
        return
    by_key = {}
    for i, url in enumerate(FEEDS, 1):
        for n in _parse_feed(url, f"#{i}"):
            by_key.setdefault(n.lower(), n)
    for n in INLINE:
        by_key.setdefault(n.lower(), n)
    competitor_names = sorted(by_key.values(), key=str.lower)  # stable order for the rotating slice
    n_total = len(competitor_names)
    if not n_total:
        print("competitor list resolved to 0 companies — nothing to diff.")
        report_source_health("tracker_diff", "ok", 0, "0 competitor companies resolved")
        return

    # FULL-LIST RECALL (the self-catching marquee alarm): check EVERY listed
    # company against our data, not just this run's slice. This is the number
    # that says, automatically, how much of the known landscape we lack — so a
    # gap surfaces in an email instead of only when someone eyeballs another
    # tracker. One /query call per company; a lookup blip counts as "have" so a
    # transient error never inflates the gap.
    all_missing = [c for c in competitor_names if not already_have(c)]
    n_missing = len(all_missing)
    recall_pct = round(100.0 * (n_total - n_missing) / n_total, 1) if n_total else 100.0
    print(f"RECALL: we carry {n_total - n_missing}/{n_total} listed companies "
          f"({recall_pct}%); missing {n_missing}")

    # INDEPENDENT RECALL: strip out every company we only ever got by chasing
    # their list. What remains is what our own net caught — the number that
    # proves the data stands on its own (and the weaning dial).
    meta = _meta_sync({}) if not DRY else {}
    resolved_ever = set((meta.get("resolved") or {}).keys())
    have = [c for c in competitor_names if c not in set(all_missing)]
    ind_have = [c for c in have if _norm(c) not in resolved_ever]
    ind_recall = round(100.0 * len(ind_have) / n_total, 1) if n_total else 100.0
    print(f"INDEPENDENT RECALL: {len(ind_have)}/{n_total} ({ind_recall}%) found by "
          f"our own pipeline without their pointer ({len(have) - len(ind_have)} "
          f"chase-resolved historically)")
    if not DRY:
        meta = _meta_sync({"record_ind": {"d": date.today().isoformat(),
                                          "ind": ind_recall, "total": recall_pct}}) or meta
        _email_recall_gap(all_missing, recall_pct, n_total)

    # GRADUATED CADENCE: earned weaning. Recall is measured every day (above);
    # the chase itself steps down to Mondays once independence has held.
    do_chase = FORCE_CHASE or chase_today(meta.get("ind_history"), date.today())
    if not do_chase:
        detail = (f"{n_total} listed; recall {recall_pct}%; independent {ind_recall}%; "
                  f"weaned cadence: chase skipped (Mondays only while independence holds)")
        print("tracker-diff:", detail)
        if not DRY:
            report_source_health("tracker_diff", "ok", 0, detail)
        return

    # Chase a rotating slice OF THE MISSING (not the whole list), so the daily
    # SEC/LLM budget is spent only on real gaps and the whole backlog is walked
    # over a few days. The calendar date is the cursor.
    chase_pool = all_missing or competitor_names
    n_slices = max(1, (len(chase_pool) + MAX_CHASE - 1) // MAX_CHASE)
    slice_idx = date.today().toordinal() % n_slices
    missing = chase_pool[slice_idx * MAX_CHASE:(slice_idx + 1) * MAX_CHASE]
    print(f"competitor list: {n_total} companies; recall {recall_pct}%; chasing "
          f"slice {slice_idx + 1}/{n_slices} of {n_missing} missing "
          f"({len(missing)} this run)")
    posted = ai = via_sec = via_press = 0
    resolved = set()
    run_wins = {}
    vocab_misses = []
    for i in range(0, len(missing), 20):
        chunk = missing[i:i + 20]
        entries = []
        # SEC FIRST: a filing is the strongest primary source, and a targeted
        # full-text search per company is cheap. Then press (NewsAPI + GDELT)
        # for the rest. Either way the OTHER tracker is only the pointer; what
        # gets stored is our own filing or named report. WARN needs no per-
        # company call here: it is bulk-imported daily, so any missing company
        # is by definition not in a WARN notice we already hold.
        for c in chunk:
            try:
                sec = search_company_filings(c, days_back=DAYS_BACK if DAYS_BACK > 60 else 120)
            except Exception:
                sec = []
            for r in sec:
                r["_alt_verify"] = "sec"
                r["_alt_target"] = c        # who we searched for, to reject cross-refs
            entries.extend(sec)
        # Google News FIRST (free, keyless, and its headlines carry the count)
        # then NewsAPI if it's alive. This is what lets the chase actually close
        # a gap again — NewsAPI alone was dead, so every run added 0.
        try:
            gnews = pull_google_news(company_names=chunk)
            for r in gnews:
                r["_alt_verify"] = "press"
            entries.extend(gnews)
        except Exception as exc:
            print(f"google-news fetch failed: {exc}")
        # (NewsAPI chase removed 2026-07-25: the source is retired — the call
        # only burned a 429 round-trip per chunk. Google News above is the
        # press path; restore from git if NewsAPI is ever paid for.)
        for raw in entries:
            try:
                ex = extract_layoff_data(raw)
            except Exception:
                continue
            if not ex:
                continue
            if raw.get("_alt_verify") == "sec":
                tgt = _norm(raw.get("_alt_target", ""))
                got = _norm(ex.get("company_name", ""))
                if not tgt or not got or (tgt not in got and got not in tgt):
                    # The filing is about a different company; it only mentioned
                    # the target. Not evidence the target laid anyone off.
                    continue
            if DRY:
                print(f"  DRY would add: {ex.get('company_name')} {ex.get('job_count')}")
                continue
            if post_to_wordpress(ex) == "posted":
                posted += 1
                ai += 1 if ex.get("ai_explicit") else 0
                if raw.get("_alt_verify") == "sec":
                    via_sec += 1
                else:
                    via_press += 1
                    # LEARN FROM WINS: remember which outlet carried the story
                    # we missed AND which country it reported for — repeat
                    # winners become allowlist candidates, tagged by country so
                    # coverage gaps are geographic facts, not guesses.
                    wk = _win_key(raw)
                    if wk:
                        country = str(ex.get("country") or "").strip()
                        key = f"{wk} · {country}" if country else wk
                        run_wins[key] = run_wins.get(key, 0) + 1
                    # VOCAB LEARNING: a win whose text matches NONE of our
                    # discovery terms was invisible to the broad sweep — keep
                    # its headline (owner-email only) so the missing wording
                    # can join the vocabulary.
                    try:
                        from source_registry import discovery_terms
                        if not vocab_hit(raw.get("raw_text"), discovery_terms()):
                            vocab_misses.append(str(raw.get("raw_text") or "")[:140])
                    except Exception:
                        pass
                got_key = _norm(ex.get("company_name", ""))
                resolved.add(got_key)
                # Also record the COMPETITOR-list spelling(s) this resolve
                # covers: the independence gauge compares against THEIR names,
                # and "_norm('Amazon.com, Inc.')" != "_norm('Amazon')" — the
                # mismatch made every chased company count as independently
                # found (audit 2026-07-25).
                for c_listed in chunk:
                    ck = _norm(c_listed)
                    if ck and got_key and (ck in got_key or got_key in ck):
                        resolved.add(ck)
                print(f"  + [{raw.get('_alt_verify','?')}] {ex.get('company_name')} "
                      f"{ex.get('job_count')} ({ex.get('layoff_date')})")
        time.sleep(1)
    unresolved = [c for c in missing if _norm(c) not in resolved]
    gaps = _cluster_gaps(unresolved)
    if gaps:
        print("SOURCE-GAP LEARNING (what to add next, ranked by misses it would fix):")
        for label, cnt, examples in gaps:
            print(f"    +{cnt}  {label}")
        # log ONLY the category + counts to health, never the competitor names
        gap_summary = "; ".join(f"{cnt} {lab.split('(')[0].strip()}" for lab, cnt, _ in gaps[:4])
    else:
        gap_summary = ""
    # Persist what this run learned: which companies only exist because we
    # chased (feeds the independence gauge) and which outlets carried the wins
    # (feeds the allowlist suggestions). Then surface any repeat-winner outlets
    # that are NOT yet in our own net — each one adopted is dependence removed.
    suggestions = []
    if not DRY and (resolved or run_wins):
        meta = _meta_sync({"add_resolved": sorted(resolved), "add_wins": run_wins}) or meta
    try:
        from sources.gdelt import TRUSTED_DOMAINS
        suggestions = outlet_suggestions(meta.get("wins") or run_wins, TRUSTED_DOMAINS)
    except Exception:
        suggestions = []
    if suggestions:
        print("LEARN-FROM-WINS (outlets that keep closing our gaps; allowlist candidates):")
        for dom, cnt in suggestions:
            print(f"    {cnt}x  {dom}")
    if vocab_misses:
        # Count only in the public log; the actual headlines go to the owner's
        # inbox via /alert (they may quote competitor-adjacent material).
        print(f"VOCAB LEARNING: {len(vocab_misses)} resolved win(s) matched no discovery term "
              f"(wording candidates emailed to owner)")
    if not DRY and (vocab_misses or suggestions):
        # Either kind of learning is worth the email: vocabulary to add OR
        # outlets to adopt (gating on vocab alone silenced the outlet email).
        _email_learning(vocab_misses, suggestions)

    detail = (f"{n_total} listed; recall {recall_pct}%; independent {ind_recall}%; "
              f"slice {slice_idx + 1}/{n_slices}; "
              f"{len(missing)} missing chased, {posted} added "
              f"({via_sec} via SEC, {via_press} via press; {ai} AI)"
              + (f" | source gaps: {gap_summary}" if gap_summary else "")
              + (f" | outlet candidates: {len(suggestions)}" if suggestions else ""))
    print("tracker-diff:", detail)
    if not DRY:
        report_source_health("tracker_diff", "ok", posted, detail)


def main():
    if not (os.environ.get("WP_SITE_URL") and (DRY or os.environ.get("WP_API_KEY"))):
        print("WP_SITE_URL (and WP_API_KEY unless dry) required")
        return 1
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY:
            report_source_health("tracker_diff", "degraded", 0, f"tracker-diff failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
