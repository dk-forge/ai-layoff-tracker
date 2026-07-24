"""Tracker-diff discovery tripwire — automated 'work backwards from other trackers'.

Takes a competitor company list, diffs it against our own data, and for anything
they list that we lack, fires a company-TARGETED primary-source query → the same
DeepSeek extractor + dedup + poster. We never cite the competitor: their list is a
discovery SIGNAL that points us at a primary source, which is what actually gets
stored. Company names arrive ONLY via a secret (never committed, per the
standalone-brand rule), and only counts/slice indices are logged — never the list.

Two ways to supply the list (use either or both):
  * COMPETITOR_FEED_URLS  — comma-separated URLs, each returning a JSON array of
    {company, date?, jobs?} objects (or {"data":[...]}/{"events":[...]}) OR a CSV
    with a `company`/`company_name`/`name` column.
  * COMPETITOR_COMPANIES  — the list pasted inline (comma- or newline-separated
    company names). Use this when the competitor has no machine feed but you can
    see their list: paste the names into this secret and the cron chases them.

Ships DORMANT: with neither set it logs and exits clean, so the repo carries zero
competitor data. The owner adds a secret to activate.

Each daily run chases a rotating slice (TRACKER_DIFF_MAX companies), so over a few
days the WHOLE list is walked — not just the first slice each time.

Env: COMPETITOR_FEED_URLS, COMPETITOR_COMPANIES (secrets), TRACKER_DIFF_MAX
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
FEEDS = [u.strip() for u in (os.environ.get("COMPETITOR_FEED_URLS") or "").split(",") if u.strip()]
INLINE = [n.strip() for n in re.split(r"[,\n]", os.environ.get("COMPETITOR_COMPANIES") or "") if n.strip()]
MAX_CHASE = max(1, int(os.environ.get("TRACKER_DIFF_MAX", "40")))
# Recall alarm: email the owner when our coverage of the reference list drops
# below this percent. Names go ONLY to the owner's inbox (never the repo, health
# ledger, or Actions log), so the standalone-brand rule holds.
RECALL_ALERT_PCT = float(os.environ.get("TRACKER_DIFF_RECALL_ALERT_PCT", "90"))
RECALL_ALERT_MAX_NAMES = max(5, int(os.environ.get("TRACKER_DIFF_RECALL_MAX_NAMES", "60")))
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


def run():
    if not FEEDS and not INLINE:
        print("Neither COMPETITOR_FEED_URLS nor COMPETITOR_COMPANIES set — tripwire "
              "dormant, nothing to diff. Paste a competitor company list into the "
              "COMPETITOR_COMPANIES secret (or a feed URL into COMPETITOR_FEED_URLS) "
              "to activate; either stays out of the repo.")
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
    if not DRY:
        _email_recall_gap(all_missing, recall_pct, n_total)

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
        try:
            press = pull_news_articles(days_back=DAYS_BACK, queries=[query_for(c) for c in chunk])
            for r in press:
                r["_alt_verify"] = "press"
            entries.extend(press)
        except Exception as exc:
            print(f"news fetch failed: {exc}")
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
                resolved.add(_norm(ex.get("company_name", "")))
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
    detail = (f"{n_total} listed; recall {recall_pct}% ({n_missing} missing); "
              f"slice {slice_idx + 1}/{n_slices}; "
              f"{len(missing)} missing chased, {posted} added "
              f"({via_sec} via SEC, {via_press} via press; {ai} AI)"
              + (f" | source gaps: {gap_summary}" if gap_summary else ""))
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
