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


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    learn = "--learn" in argv
    if not (os.environ.get("WP_SITE_URL") and (DRY or os.environ.get("WP_API_KEY"))):
        print("WP_SITE_URL (and WP_API_KEY unless dry) required")
        return 1
    try:
        # Two halves of one machine, deliberately separate entry points. The
        # chase (`run`) needs a reference list that only ever arrived in a
        # secret and stays dormant without it; the learning half (`learn_run`)
        # needs no secret at all and is the one that is armed.
        learn_run() if learn else run()
        return 0
    except Exception as exc:
        if not DRY:
            label = "tracker-learn" if learn else "tracker-diff"
            # `exc` is ours or the stdlib's; no name from the corpus is ever
            # carried in an exception raised by this module (the leak test
            # pins that the poisoned run's marker never reaches stdout).
            report_source_health("tracker_diff", "degraded", 0, f"{label} failed: {exc}")
        raise



# ===========================================================================
# LEARNING MODE — the competitor-free half of this machine
# ===========================================================================
# The chase above needs a reference LIST, which only ever arrived in a secret
# the owner decided against on 2026-07-28. That half stays dormant. This half
# answers the same question — "what exists to be found that we did not find?" —
# from a reference universe that needs NO secret and names NO competitor: the
# GDELT article corpus BEFORE our own trusted-domain gate is applied.
#
# The daily ingest queries GDELT with the same vocabulary and then throws away
# every article whose domain is not in TRUSTED_DOMAINS. Those discarded
# articles are, by construction, layoff coverage that our net could see and
# chose not to read. Diffing them against our own rows produces exactly the
# four things the owner asked to learn: a wording we do not search for, an
# outlet we do not trust, a country we do not cover, a language we have no
# native term for.
#
# WHAT THIS COSTS: nothing. One extra GDELT ArtList query (keyless, the same
# endpoint the ingest already calls) plus one read per candidate against our
# OWN public /query. No model is called on any path and none may ever be added
# here — see the cost note in tracker-learn.yml.
#
# WHAT IT NEVER DOES: it never stores a row (a discovery signal is not
# evidence), never fetches an article page (so no robots.txt, paywall or bot
# wall is ever touched — titles come from the GDELT API response), and never
# writes a name anywhere but the owner's inbox. That last property is
# structural, not careful: every public sink goes through `public_render`,
# which only accepts numbers, ISO dates and words from a frozen label set, and
# raises `LeakGuard` on anything else. tests/test_tracker_learning_leak.py
# poisons a run and proves the marker reaches the email and nothing else.
# ---------------------------------------------------------------------------

LEARN_WINDOW_HOURS = max(6, min(168, int(os.environ.get("TRACKER_LEARN_WINDOW_HOURS", "36"))))
LEARN_MAX_RECORDS = max(10, min(250, int(os.environ.get("TRACKER_LEARN_MAX_RECORDS", "250"))))
LEARN_QUERY_ATTEMPTS = max(1, min(3, int(os.environ.get("TRACKER_LEARN_QUERY_ATTEMPTS", "2"))))
# GDELT's ArtList endpoint REFUSES a long query, and does it with HTTP 200 and
# the plain-text body "Your query was too short or too long." — which is not
# JSON, so it surfaces as a parse error and looks like a transient blip. The
# ingest's own 927-character `gdelt.QUERY` (all 48 discovery terms) is over that
# limit on this endpoint; measured 2026-08-18, 465 chars was refused and 152
# answered. So the learning corpus is retrieved with a ROTATING SLICE of the
# vocabulary, bounded by characters rather than by term count so a longer term
# added later cannot silently push it back over.
LEARN_QUERY_CHARS = max(80, min(300, int(os.environ.get("TRACKER_LEARN_QUERY_CHARS", "200"))))
LEARN_MAX_CANDIDATES = max(5, min(400, int(os.environ.get("TRACKER_LEARN_MAX_CANDIDATES", "120"))))
# A headline headcount below this is usually a single-site or single-role note
# that our net is not trying to catch; counting it as a miss would manufacture
# rules out of noise.
LEARN_MIN_JOBS = max(10, int(os.environ.get("TRACKER_LEARN_MIN_JOBS", "25")))
# How far our stored layoff_date may sit from the article's date and still be
# the same event. Announcement and effective dates legitimately differ by weeks.
LEARN_MATCH_DAYS = max(7, int(os.environ.get("TRACKER_LEARN_MATCH_DAYS", "45")))
LEARN_STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "tracker_learning_state.json")
LEARN_HISTORY_MAX = 180
# Three empty runs in a row is not a broken loop, it is a loop with nothing to
# say; it steps down to Mondays and steps straight back up on the first rule.
LEARN_QUIET_RUNS = max(2, int(os.environ.get("TRACKER_LEARN_QUIET_RUNS", "3")))
# The measurement method is versioned so a trend line can never silently splice
# two different definitions of the same percentage.
LEARN_METHOD = "m4"
# Every method tag this file has ever emitted. A version bump does not rewrite
# history — that's the whole point, so a splice can never hide as more data on
# one definition — so old rows sit in the committed state forever with their
# original tag. The nameless allowlist has to recognize all of them, not just
# the current one, or the very first run after a bump fails to write its own
# state because a row from BEFORE the bump no longer validates.
_LEARN_METHOD_VERSIONS = frozenset({"m2", "m4", LEARN_METHOD})

RULE_KINDS = ("vocabulary", "outlet", "country_edition", "language")
# Minimum unmatched articles before a rule is worth the owner's attention. An
# outlet that closed one gap once is a coincidence; two is a pattern.
#
# THE VOCABULARY FLOOR IS THE ONE THAT MATTERS, and it is why the vocabulary
# subject is a normalised PHRASE rather than the headline. Grouping by headline
# gives every unmatched article a rule of its own — a daily email of ~40
# one-off "rules" that nobody reads and, worse, a loop whose rule count can
# never reach zero, so the earned cadence below could never earn anything. A
# wording that shows up twice in one window is a wording we should be
# searching for; a wording that shows up once is a headline.
RULE_FLOOR = {"vocabulary": 2, "outlet": 2, "country_edition": 3, "language": 3}
# Per-kind ceiling on one run's email. A loop that asks for forty changes gets
# none of them made.
RULE_CAP = {"vocabulary": 5, "outlet": 8, "country_edition": 5, "language": 5}


class LeakGuard(RuntimeError):
    """Raised when a value that could carry a name reaches a public sink."""


# Every string any public sink is allowed to contain. Not a filter over free
# text — an allowlist of the whole vocabulary. A name cannot be spelled with it.
_PUBLIC_WORDS = frozenset(RULE_KINDS) | _LEARN_METHOD_VERSIONS | frozenset({
    "learn", "ok", "degraded", "unknown", "pass", "fail",
    "daily", "weekly", "quiet", "skipped", "ran",
})
_PUBLIC_KEYS = frozenset(RULE_KINDS) | frozenset({
    "date", "method", "mode", "cadence", "window_hours", "corpus", "candidates",
    "matched", "unmatched", "unknown", "independent_recall_pct", "rules",
    "rules_by_kind", "history", "quiet_runs", "emailed", "state", "explored",
    "rule_misses",
})
_PUBLIC_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}(T[0-9:]{5,8}Z)?$")


def assert_nameless(obj, path="root"):
    """Prove a structure carries no free text, recursively. Raises LeakGuard.

    This is the whole leak-safety property and it is deliberately a WHITELIST:
    numbers, booleans, None, ISO dates and words from `_PUBLIC_WORDS`. A
    reviewer noticing a name is not a mechanism; a function that cannot spell
    one is. Everything printed, health-reported or committed by learning mode
    passes through here first.
    """
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        if obj in _PUBLIC_WORDS or _PUBLIC_DATE_RX.match(obj):
            return obj
        raise LeakGuard(f"{path}: refusing to publish free text")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in _PUBLIC_KEYS:
                raise LeakGuard(f"{path}.{k}: key is not a declared public field")
            assert_nameless(v, f"{path}.{k}")
        return obj
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            assert_nameless(v, f"{path}[{i}]")
        return obj
    raise LeakGuard(f"{path}: unsupported type {type(obj).__name__}")


def public_render(facts):
    """One log/health line from a nameless fact dict. Raises on anything else."""
    assert_nameless(facts)
    parts = []
    for key in sorted(facts):
        val = facts[key]
        if isinstance(val, dict):
            inner = ", ".join(f"{k} {val[k]}" for k in sorted(val))
            if inner:
                parts.append(f"{key}: {inner}")
        else:
            parts.append(f"{key} {val}")
    return "; ".join(parts)


# --- reading the reference universe ---------------------------------------

def _learn_corpus(window_hours=None):
    """The layoff-news corpus BEFORE our trusted-domain gate, from the GDELT
    API we already call. Returns (anchor, rotating, error). Never fetches a page.

    TWO SLICES, AND THE SPLIT IS THE POINT. Independent recall is only a trend
    if its denominator is comparable between runs, so it is measured on the
    ANCHOR slice: a fixed head of the vocabulary, the same query every day.
    The ROTATING slice walks the rest of the vocabulary and feeds rule
    discovery only — measured 2026-08-18, one day's rotation ("collective
    dismissal", "retrenchment", "plant closure") yielded 4 candidates from 250
    articles while the everyday words yield several times that, so letting the
    rotation into the measurement would make the number swing on which words
    came up rather than on our coverage.

    THE ATTEMPT BUDGET IS DELIBERATELY SMALLER THAN THE INGEST'S. GDELT's public
    endpoint is shared and throttles hard: measured from here on 2026-08-18 the
    default five attempts spent 426 seconds in backoff and still came back
    empty. The ingest is right to be that patient — it is collecting data and a
    lost window is data nobody re-reads. This query collects nothing. It is the
    same rule gdelt.py already applies to its rotating segment sweeps: a
    rate-limited query is skipped with a log line and comes back around, and it
    must never sit on a shared endpoint that the ingest needs next."""
    from datetime import datetime, timedelta, timezone, date as _date
    from sources import gdelt
    try:
        from source_registry import discovery_terms
        terms = discovery_terms()
    except Exception:
        terms = ()
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=window_hours or LEARN_WINDOW_HOURS)
    patience = gdelt.QUERY_ATTEMPTS
    gdelt.QUERY_ATTEMPTS = min(patience, LEARN_QUERY_ATTEMPTS)
    try:
        anchor, _rl, err = gdelt._query_window(
            learn_query(terms, None), start, end, LEARN_MAX_RECORDS)
        # The exploring half is best-effort: it widens what the rules can see
        # and must never decide whether the run happened.
        rotating, _rl2, _err2 = gdelt._query_window(
            learn_query(terms, _date.today()), start, end, LEARN_MAX_RECORDS)
    finally:
        gdelt.QUERY_ATTEMPTS = patience
    if anchor is None:
        return [], [], (err or "window abandoned")
    return anchor, (rotating or []), None


def learn_query(terms, today):
    """A GDELT query from a rotating slice of the discovery vocabulary.

    Bounded by `LEARN_QUERY_CHARS` because the endpoint refuses a long query
    (see the constant). The slice rotates on the calendar date, so the whole
    vocabulary is walked over a few days rather than the first N terms being
    the only ones this loop ever looks through — the same deterministic
    rotation `gdelt._segment_queries_for_now` uses, for the same reason."""
    terms = [t for t in (terms or []) if t]
    if not terms:
        return ""
    # `today=None` is the ANCHOR: always the head of the vocabulary, so the
    # recall denominator is built the same way every run.
    start = 0 if today is None else today.toordinal() % len(terms)
    picked, size = [], 2
    for i in range(len(terms)):
        term = terms[(start + i) % len(terms)]
        quoted = f'"{term}"' if " " in term else term
        cost = len(quoted) + (4 if picked else 0)
        if picked and size + cost > LEARN_QUERY_CHARS:
            break
        picked.append(quoted)
        size += cost
    return "(" + " OR ".join(picked) + ")"


_HEADCOUNT_RX = (
    # "500 jobs", "1,200 workers", "12,000 employees"
    re.compile(r"(?<![\d,.%])(\d{1,3}(?:,\d{3})+|\d{2,6})\s+"
               r"(?:more\s+)?(?:jobs|workers|employees|staff|positions|roles|people)\b", re.I),
    # "cut 500", "lays off 1,200", "to axe 900"
    re.compile(r"\b(?:cut|cuts|cutting|lay\s*off|lays\s*off|laying\s*off|axe|axes|"
               r"slash|slashes|eliminate|eliminates|shed|sheds|sack|sacks)\s+"
               r"(?:about|around|up\s+to|some|its|nearly|almost|over)?\s*"
               r"(\d{1,3}(?:,\d{3})+|\d{2,6})(?![\d,.%])", re.I),
)
# Words that open a headline without being the employer.
_TITLE_STOP = {
    "exclusive", "breaking", "update", "updated", "report", "reports", "opinion",
    "analysis", "watch", "live", "video", "photos", "the", "a", "an", "more",
    "why", "how", "what", "when", "after", "amid", "as", "another", "new",
    "us", "u.s.", "uk", "eu", "tech", "ai", "big",
    # Generic leading adjectives. Measured against a real sweep on 2026-08-18,
    # "Major retail meat company closes plants, lays off over 3,200" produced
    # the employer token "Major", which of course matches nothing we hold and
    # so scored a real headline as a miss. Skipping the word drops to the next
    # token, which is lower case, which correctly yields no candidate at all.
    "major", "top", "global", "local", "state", "federal", "national",
    "leading", "giant", "embattled", "struggling", "troubled",
}


def headline_jobs(title):
    """The headcount a headline states, or None. FIRST number only, matching the
    same rule the ingest uses — a headline that says "500 of 2,000" announces
    500. A percentage is never a headcount."""
    for rx in _HEADCOUNT_RX:
        m = rx.search(title or "")
        if m:
            try:
                n = int(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if n >= LEARN_MIN_JOBS:
                return n
    return None


def headline_employer_token(title):
    """A best-effort employer token from a headline, deterministically.

    Learning mode has no LLM (that is the point: it must cost nothing), so this
    is a heuristic and is treated as one — a wrong token makes an article look
    unmatched, and the rule floors above are what stop one bad guess becoming a
    rule. Returns '' when the headline does not open with a name-shaped token."""
    t = re.sub(r"\s+", " ", str(title or "")).strip()
    t = re.sub(r"^[A-Z][A-Za-z]{2,9}:\s*", "", t)          # "Exclusive: ..."
    t = re.split(r"\s+[-–|]\s+", t)[0]                      # drop " - Outlet"
    for word in re.split(r"[^A-Za-z0-9&.'’-]+", t):
        if not word or word.lower() in _TITLE_STOP:
            continue
        if word[0].isupper() or word.isupper():
            clean = word.strip(".'’-")
            if len(clean) >= 3:
                return clean
        else:
            break   # past the leading capitalised run; no employer here
    return ""


def _our_rows(token, timeout=30):
    """Rows we already hold for an employer token, or None when the lookup
    could not be made. None is UNKNOWN and is excluded from the denominator —
    an API blip must never be recorded as a miss (or as a find)."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not (site and token):
        return None
    try:
        r = requests.get(f"{site}/wp-json/layoffs/v1/query",
                         params={"company": token, "per_page": 50},
                         headers=UA, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json().get("data") or []
    except Exception:
        return None


def rows_verdict(rows, jobs, when, match_days=None):
    """"match" / "miss" / "unknown" for one headline against our own rows.

    A match is the same headcount (within rounding) at a date the same event
    could plausibly carry. The third state is the one that had to exist: a row
    with the SAME company and the SAME headcount but a date far outside the
    window is not evidence we hold this event and is certainly not evidence we
    missed it — most often it is a retrospective piece about an event we
    already have. Scoring that as a miss would depress independent recall and
    manufacture a rule out of our own coverage. Pure, so the rule that decides
    the headline number is tested rather than trusted."""
    from datetime import date as _date
    window = match_days or LEARN_MATCH_DAYS
    tolerance = max(1, int(round(jobs * 0.02)))
    ambiguous = False
    for row in rows or []:
        try:
            count = int(row.get("job_count") or 0)
        except (TypeError, ValueError):
            continue
        if not count or abs(count - jobs) > tolerance:
            continue
        stamp = str(row.get("layoff_date") or "")[:10]
        if not when or not _PUBLIC_DATE_RX.match(stamp or "x"):
            return "match"     # count agrees and we cannot date it: not a miss
        try:
            y, m, d = (int(x) for x in stamp.split("-"))
            delta = abs((_date(y, m, d) - when).days)
        except Exception:
            return "match"
        if delta <= window:
            return "match"
        ambiguous = True
    return "unknown" if ambiguous else "miss"


def _seendate_to_date(seendate):
    from datetime import date as _date
    s = re.sub(r"[^0-9]", "", str(seendate or ""))
    if len(s) < 8:
        return None
    try:
        return _date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def vocab_phrase(title):
    """The wording around the headcount, normalised, or ''.

    This is the SUBJECT of a vocabulary rule. Grouping by it (rather than by
    headline) is what makes the rule "this phrasing keeps appearing and we do
    not search for it" instead of "here is another headline"."""
    for rx in _HEADCOUNT_RX:
        m = rx.search(title or "")
        if not m:
            continue
        low = str(title).lower()
        window = low[max(0, m.start() - 40):m.end() + 24]
        words = [w for w in re.split(r"[^a-z]+", window) if len(w) > 2]
        # Drop the fragments at both edges of the window, which are cut
        # mid-word as often as not, and the count itself (digits are gone
        # already) — what is left is the phrasing.
        return " ".join(words[1:-1] if len(words) > 3 else words)[:70]
    return ""


def rank_rules(unmatched, trusted_domains, discovery):
    """Turn unmatched articles into RULES, ranked. Returns a list of dicts
    {kind, subject, count, examples} — the PRIVATE object. Pure and tested."""
    buckets = {kind: {} for kind in RULE_KINDS}
    for art in unmatched:
        title = str(art.get("title") or "")
        domain = str(art.get("domain") or "").lower().strip()
        country = str(art.get("sourcecountry") or "").strip()
        language = str(art.get("language") or "").strip()
        if domain and not _covered_by_allowlist(domain, {d.lower() for d in trusted_domains or []}):
            buckets["outlet"].setdefault(domain, []).append(title)
        if country:
            buckets["country_edition"].setdefault(country, []).append(title)
        if language and language.lower() not in ("english", "en", ""):
            buckets["language"].setdefault(language, []).append(title)
        if title and not vocab_hit(title, discovery):
            phrase = vocab_phrase(title)
            if phrase:
                buckets["vocabulary"].setdefault(phrase, []).append(title)
    rules = []
    for kind in RULE_KINDS:
        floor, cap = RULE_FLOOR[kind], RULE_CAP[kind]
        ranked = sorted(buckets[kind].items(), key=lambda kv: (-len(kv[1]), kv[0]))
        for subject, titles in ranked[:cap]:
            if len(titles) < floor:
                continue
            rules.append({"kind": kind, "subject": subject,
                          "count": len(titles), "examples": titles[:3]})
    return rules


def learn_today(history, today, quiet_runs=None):
    """Earned cadence. Daily while the loop is teaching something; after
    `quiet_runs` consecutive recorded runs that produced ZERO rules it steps
    down to Mondays, and the first rule of any run steps it straight back up.
    Pure + tested — a backoff nobody can reason about gets overridden."""
    quiet = quiet_runs or LEARN_QUIET_RUNS
    pts = [p for p in (history or []) if isinstance(p, dict) and "rules" in p]
    if len(pts) < quiet:
        return True
    if any(int(p.get("rules") or 0) > 0 for p in pts[-quiet:]):
        return True
    return today.weekday() == 0


# --- the two sinks ---------------------------------------------------------

def _learn_state():
    try:
        with open(LEARN_STATE_PATH) as fh:
            state = json.load(fh)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _write_learn_state(state):
    """Commit-bound measurement file. Passed through assert_nameless BEFORE it
    is written, so an unsafe value fails the run instead of being committed."""
    assert_nameless(state)
    with open(LEARN_STATE_PATH, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _rule_instruction(rule):
    """The paste-ready line for one rule — the same shape health_digest uses
    for a broken scraper, because that is the loop the owner already runs."""
    kind = rule["kind"]
    subject = rule["subject"]
    if kind == "vocabulary":
        return ('Add the missing wording from this headline to '
                f'source_registry.GLOBAL_TERMS: "{subject}"')
    if kind == "outlet":
        return (f'Review {subject} for sources/gdelt.py TRUSTED_DOMAINS '
                f'({rule["count"]} layoff stories we did not read).')
    if kind == "country_edition":
        return (f'Review coverage for {subject} ({rule["count"]} unmatched '
                'layoff stories) — source_registry.MARKETS.')
    return (f'Add a native-language term for {subject} to '
            f'sources/gdelt.py NATIVE_TERMS ({rule["count"]} unmatched stories).')


def _email_rules(rules, facts):
    """Owner-only. Every NAME in this whole module leaves through this one
    function and no other. Best-effort; never raises."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key and rules):
        return False
    lines = [
        "The learning run compared the worldwide layoff-news corpus against our",
        "own rows and found coverage we do not have. Each line below is a change,",
        "not a score.",
        "",
        f"Independent recall this run: {facts.get('independent_recall_pct')}% "
        f"({facts.get('matched')} of {facts.get('candidates')} announcements we "
        "could match found by our own pipeline, unaided).",
        "",
    ]
    for kind in RULE_KINDS:
        of_kind = [r for r in rules if r["kind"] == kind]
        if not of_kind:
            continue
        lines.append(f"{kind.replace('_', ' ').upper()}:")
        for rule in of_kind[:8]:
            lines.append("  - " + _rule_instruction(rule))
            for ex in rule["examples"][:1]:
                if ex != rule["subject"]:
                    lines.append(f"      seen: {ex[:120]}")
        lines.append("")
    lines += [
        "Paste into a Claude Code session in the ai-layoff-tracker repo:",
        '  "Adopt the rules from today\'s tracker learning email: add the terms,',
        '   review the outlets, and update the sources page in the same session."',
        "",
        "These outlets are DISCOVERY signals. Never store an aggregator or another",
        "tracker as a source, and never put any name from this email in the repo.",
    ]
    try:
        requests.post(f"{site}/wp-json/layoffs/v1/alert",
                      json={"subject": f"Tracker learning: {len(rules)} rule(s) to apply",
                            "message": "\n".join(lines)},
                      headers={**UA, "X-ALT-KEY": key}, timeout=30)
        return True
    except Exception:
        # Never printed with a body: a failed send must not spill the names it
        # was carrying into the Actions log.
        print("learning email could not be delivered (non-fatal)")
        return False


def learn_run(today=None):
    """One learning run. Returns the PUBLIC fact dict (never any name)."""
    from datetime import date as _date
    today = today or _date.today()
    state = _learn_state()
    history = state.get("history") or []
    facts = {"date": today.isoformat(), "method": LEARN_METHOD, "mode": "learn",
             "window_hours": LEARN_WINDOW_HOURS}

    if not learn_today(history, today):
        facts["cadence"] = "quiet"
        facts["state"] = "skipped"
        print("tracker-learn:", public_render(facts))
        report_source_health("tracker_diff", "ok", 0,
                             "learning loop quiet (no rule found in the last "
                             f"{LEARN_QUIET_RUNS} runs): " + public_render(facts))
        return facts
    facts["cadence"] = "daily"

    anchor, rotating, err = _learn_corpus()
    if err:
        # An upstream throttle is UNKNOWN. Three things it must not become:
        #   * a PASS — the word UNKNOWN leads the health detail and a point is
        #     written to the committed trend, so a day the corpus could not be
        #     read is visible as itself and can never be read as a quiet day;
        #   * a DEGRADED collector — nothing of ours is broken, no data is
        #     lost, and a shared endpoint throttling an advisory query is not
        #     an incident anyone should be paged for;
        #   * a QUIET run — the point carries no `rules` key, so the earned
        #     cadence below skips it entirely. An outage cannot wean the loop.
        facts["state"] = "unknown"
        facts["corpus"] = 0
        line = public_render(facts)
        print("tracker-learn: UNKNOWN — the reference corpus could not be read "
              "(upstream); nothing judged, no rule inferred")
        report_source_health("tracker_diff", "ok", 0,
                             "learning run UNKNOWN: the reference corpus could not "
                             "be read this run (upstream throttle or outage). "
                             "Nothing was judged and no rule was inferred. " + line)
        history.append({k: facts[k] for k in ("date", "method", "state")})
        state["history"] = [h for h in history if isinstance(h, dict)][-LEARN_HISTORY_MAX:]
        _write_learn_state(state)
        return facts
    facts["corpus"] = len(anchor)
    facts["explored"] = len(rotating)

    def _candidates(articles, measured):
        out = []
        for art in articles:
            title = str(art.get("title") or "")
            jobs = headline_jobs(title)
            if not jobs:
                continue
            token = headline_employer_token(title)
            if not token:
                continue
            out.append((art, jobs, token, measured))
            if len(out) >= LEARN_MAX_CANDIDATES:
                break
        return out

    candidates = _candidates(anchor, True) + _candidates(rotating, False)

    matched = unknown = 0
    unmatched = []          # every miss, measured or explored, feeds the rules
    seen_tokens = {}
    for art, jobs, token, measured in candidates:
        key = token.lower()
        if key not in seen_tokens:
            seen_tokens[key] = _our_rows(token)
        rows = seen_tokens[key]
        if rows is None:
            if measured:
                unknown += 1  # our own API did not answer; judged nothing
            continue
        verdict = rows_verdict(rows, jobs, _seendate_to_date(art.get("seendate")))
        if verdict == "match":
            matched += measured
        elif verdict == "unknown":
            unknown += measured   # same company and count, implausible date
        else:
            unmatched.append((art, measured))

    measured_misses = sum(1 for _a, m in unmatched if m)
    judged = matched + measured_misses
    facts["candidates"] = judged
    facts["matched"] = matched
    facts["unmatched"] = measured_misses
    facts["unknown"] = unknown
    facts["rule_misses"] = len(unmatched)
    # INDEPENDENT RECALL: of the announcements we could judge, the share our own
    # pipeline already holds — with no pointer from anybody. Nothing in this
    # loop stores a row, so every find here is unaided by construction and this
    # number is the one that should trend up as the rules are adopted.
    facts["independent_recall_pct"] = round(100.0 * matched / judged, 1) if judged else None

    try:
        from sources.gdelt import TRUSTED_DOMAINS
    except Exception:
        TRUSTED_DOMAINS = set()
    try:
        from source_registry import discovery_terms
        discovery = discovery_terms()
    except Exception:
        discovery = ()
    rules = rank_rules([a for a, _m in unmatched], TRUSTED_DOMAINS, discovery)
    facts["rules"] = len(rules)
    facts["rules_by_kind"] = {kind: sum(1 for r in rules if r["kind"] == kind)
                              for kind in RULE_KINDS if any(r["kind"] == kind for r in rules)}
    facts["state"] = "ran"
    facts["emailed"] = bool(_email_rules(rules, facts))

    history = [h for h in history if isinstance(h, dict)]
    history.append({k: facts[k] for k in
                    ("date", "method", "rules", "matched", "unmatched", "unknown",
                     "candidates", "independent_recall_pct") if k in facts})
    state["history"] = history[-LEARN_HISTORY_MAX:]
    state["quiet_runs"] = sum(1 for h in state["history"][-LEARN_QUIET_RUNS:]
                              if not int(h.get("rules") or 0))
    _write_learn_state(state)

    line = public_render(facts)
    print("tracker-learn:", line)
    report_source_health("tracker_diff", "ok", 0, "learning run: " + line)
    return facts


# The entry point lives at the END of the module, not in the middle of it.
# It sat above the learning block for one run and `python tracker_diff.py
# --learn` died with `NameError: learn_run is not defined`: the guard executes
# during module import, so everything it can call has to be defined above it.
# Nothing local caught this because a test imports the module and never runs
# the guard.
if __name__ == "__main__":
    sys.exit(main())
