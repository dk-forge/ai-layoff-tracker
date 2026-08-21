"""Free layoff-news discovery via Google News RSS — no API key, no cost.

Why this exists: NewsAPI's free tier is dev-only and its paid tier is ~$449/mo,
so it is effectively dead here (see sources/newsapi.py). Google News RSS needs no
account and no key, and its item TITLE almost always carries the layoff HEADCOUNT
even when the linked article is paywalled ("Oracle fires 21,000 employees",
"Meta to cut 8,000 jobs"). That is exactly the marquee-layoff gap the paywalled
sources created: GDELT could not read the number behind the paywall, so the event
was dropped. Here the number is right there in the headline.

How it plugs in (mirrors sources/newsapi.py): each RSS item becomes a raw dict
with raw_text set (title + snippet — the extractor reads ONLY raw_text), so it
flows through the SAME extract_layoff_data -> post_to_wordpress pipeline, and all
the usual guards (verbatim count, date bounds, dedup, normalization) apply once.

We do NOT fetch the article body: the item link is a Google redirect to the
(often paywalled) page, and the headcount is already in the title/snippet. The
Google News link is stored as the source_url — it resolves to the article in a
browser and is Wayback-archivable like any other source.

No key. Optional env: GOOGLE_NEWS_MAX (items/run cap, default 150),
GOOGLE_NEWS_GAP_SECONDS (polite gap between queries, default 1).
"""
import html
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

import run_slice

RSS = "https://news.google.com/rss/search"
# Google News serves python-requests fine, but a browser-ish UA is safest and
# matches the rest of the project's outbound calls.
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}

# Lean default (was 300) to hold the monthly LLM spend near the ~$5-10 target:
# Google News returns most-relevant first, so the marquee cuts are in the top
# slice; raise GOOGLE_NEWS_MAX if you later want deeper coverage over cost.
def _env_int(name, default):
    try:
        return int(str(os.environ.get(name, default)).strip() or default)
    except (TypeError, ValueError):
        print(f"{name} invalid; using default {default}")
        return int(default)


MAX_ITEMS = max(10, _env_int("GOOGLE_NEWS_MAX", 150))
GAP = max(0.0, float(os.environ.get("GOOGLE_NEWS_GAP_SECONDS", "1")))

# Broad layoff sweeps + a dedicated AI/automation sweep, mirroring newsapi's
# intent. Google News handles OR/quotes in the q= param.
DISCOVERY_QUERIES = (
    '"layoffs" OR "job cuts" OR "lays off" OR "cutting jobs" OR "workforce reduction"',
    '("layoffs" OR "job cuts" OR "lays off") ("AI" OR "artificial intelligence" OR automation)',
    '"reduction in force" OR "restructuring" OR "redundancies" layoffs',
    # Corporate euphemisms that dodge the word "layoff" — paired with a headcount
    # signal so the results stay layoff-events, not macro/strategy noise. Budget-
    # neutral: the MAX_ITEMS cap holds total extraction flat across all queries.
    '("rightsizing" OR "workforce optimization" OR "role elimination" OR "voluntary separation" OR "organizational simplification") (jobs OR employees OR roles OR staff)',
    '"bankruptcy" OR "shuts down" OR "winding down" (layoffs OR "job cuts" OR employees)',
)


# ---------------------------------------------------------------------------
# NATIONAL EDITIONS. Google News runs per-country editions: the SAME query
# against a different edition returns that country's outlets, in that country's
# language. Until 2026-07-27 this collector only ever read the US edition
# (hl=en-US&gl=US&ceid=US:en), so a worldwide layoff tracker was reading
# US headlines only -- free coverage left on the table.
#
# BUDGET-NEUTRAL: MAX_ITEMS still caps the whole run, so rotating editions
# changes WHICH articles we see, not HOW MANY we extract. Cost is unchanged.
#
# Curated for layoff coverage: the largest economies plus the markets where our
# WARN/ERM feeds do not reach. Rotated a few per run (deterministic by day) so
# the whole list is swept in ~6 days.
GOOGLE_NEWS_LOCALES = (
    ("US", "en-US", "US", "US:en"),
    ("GB", "en-GB", "GB", "GB:en"),
    ("CA", "en-CA", "CA", "CA:en"),
    ("AU", "en-AU", "AU", "AU:en"),
    ("IE", "en-IE", "IE", "IE:en"),
    ("IN", "en-IN", "IN", "IN:en"),
    ("SG", "en-SG", "SG", "SG:en"),
    ("ZA", "en-ZA", "ZA", "ZA:en"),
    ("PH", "en-PH", "PH", "PH:en"),
    ("MY", "en-MY", "MY", "MY:en"),
    ("DE", "de", "DE", "DE:de"),
    ("AT", "de", "AT", "AT:de"),
    ("CH", "de", "CH", "CH:de"),
    ("FR", "fr", "FR", "FR:fr"),
    ("BE", "nl", "BE", "BE:nl"),
    ("NL", "nl", "NL", "NL:nl"),
    ("IT", "it", "IT", "IT:it"),
    ("ES", "es", "ES", "ES:es"),
    ("PT", "pt-PT", "PT", "PT:pt-150"),
    ("SE", "sv", "SE", "SE:sv"),
    ("NO", "no", "NO", "NO:no"),
    ("DK", "da", "DK", "DK:da"),
    ("FI", "fi-FI", "FI", "FI:fi"),
    ("PL", "pl", "PL", "PL:pl"),
    ("CZ", "cs", "CZ", "CZ:cs"),
    ("RO", "ro", "RO", "RO:ro"),
    ("HU", "hu", "HU", "HU:hu"),
    ("TR", "tr", "TR", "TR:tr"),
    ("BR", "pt-BR", "BR", "BR:pt-419"),
    ("MX", "es-419", "MX", "MX:es-419"),
    ("AR", "es-419", "AR", "AR:es-419"),
    ("CL", "es-419", "CL", "CL:es-419"),
    ("CO", "es-419", "CO", "CO:es-419"),
    ("JP", "ja", "JP", "JP:ja"),
    ("KR", "ko", "KR", "KR:ko"),
    ("TW", "zh-TW", "TW", "TW:zh-Hant"),
    ("HK", "zh-HK", "HK", "HK:zh-Hant"),
    ("TH", "th", "TH", "TH:th"),
    ("VN", "vi", "VN", "VN:vi"),
    ("ID", "en-ID", "ID", "ID:en"),
    ("IL", "en-IL", "IL", "IL:en"),
    ("AE", "ar", "AE", "AE:ar"),
    ("NG", "en-NG", "NG", "NG:en"),
    ("KE", "en-KE", "KE", "KE:en"),
    ("NZ", "en-NZ", "NZ", "NZ:en"),
)
# Editions per run beyond the always-on US edition. 0 disables rotation.
LOCALES_PER_RUN = max(0, min(8, _env_int("GOOGLE_NEWS_LOCALES_PER_RUN", 4)))


def _locales_for_now():
    """US always, plus a deterministic rotating slice of the rest.

    The `hour // 12` this used to carry removed the coupling to railway.toml's
    exact HOURS but kept the `* 2`, which is a hardcoded two-runs-a-day. Once
    the cron went daily on 2026-08-14 the index advanced twice per run and this
    ring's full sweep went from 6 days to 11. It survived only because 44 rest
    locales and a stride of 8 share a factor of 4; the euphemism ring in
    sources/gdelt.py, on the same arithmetic, lost half its terms outright.
    `run_slice.rotate` steps by exactly one run, so no cadence can stride it.
    """
    us = GOOGLE_NEWS_LOCALES[0]
    rest = GOOGLE_NEWS_LOCALES[1:]
    if not LOCALES_PER_RUN or not rest:
        return [us]
    return [us] + run_slice.rotate(rest, LOCALES_PER_RUN)


def _clean(text):
    """Strip tags/entities, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _rss_url(query, hl="en-US", gl="US", ceid="US:en"):
    return f"{RSS}?" + urllib.parse.urlencode(
        {"q": query, "hl": hl, "gl": gl, "ceid": ceid})


def _iso_date(pubdate):
    """RFC-822 pubDate -> YYYY-MM-DD, or '' (the extractor also reads the date
    from the text; this is only a hint)."""
    if not pubdate:
        return ""
    try:
        return parsedate_to_datetime(pubdate).date().isoformat()
    except Exception:
        return ""


def _parse_items(xml_text):
    """Parse an RSS 2.0 body into a list of {title, link, description, source,
    published}. Never raises."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out
    for item in root.iter("item"):
        def _t(tag):
            el = item.find(tag)
            return el.text if el is not None and el.text else ""
        src_el = item.find("source")
        out.append({
            "title": _t("title"),
            "link": _t("link"),
            "description": _t("description"),
            "published": _t("pubDate"),
            "source": (src_el.text if src_el is not None and src_el.text else ""),
        })
    return out


def pull_google_news(queries=None, company_names=None):
    """Return a list of raw dicts ready for extract_layoff_data.

    Fail-loud: on an HTTP/parse error, set pull_google_news.last_error so the
    cron caller can degrade the source instead of masking a dead feed as 'ok'."""
    pull_google_news.last_error = None
    qs = list(queries or DISCOVERY_QUERIES)
    # Company-targeted queries are the surgical fix for the exact miss list
    # (Google, HP, Accenture, SAP, Uber...): the watchlist supplies the names.
    # They go FIRST: MAX_ITEMS is a GLOBAL cap, and with the broad sweeps in
    # front the first two queries alone could exhaust it, so the targeted
    # queries (the whole point of a chase call) never fired (audit 2026-07-25).
    for c in (company_names or []):
        c = str(c or "").strip()
        if c:
            qs.insert(0, f'"{c}" (layoffs OR "job cuts" OR "lays off" OR restructuring)')

    # Each query runs against the US edition plus a rotating slice of national
    # editions, so the same vocabulary surfaces LOCAL outlets in local languages.
    # Company-targeted queries (inserted at the front) stay US-only: a chase is
    # for one named employer, and fanning it across editions would spend the cap
    # on duplicates of the same story.
    locales = _locales_for_now()
    n_company = len([c for c in (company_names or []) if str(c or "").strip()])
    # LOCALE-MAJOR order (audit 2026-07-28): company chases first (US only),
    # then EVERY discovery query on the US edition, then the rotating editions.
    # The previous query-major order meant per-query slices exhausted MAX_ITEMS
    # before the last query ever ran — the bankruptcy/shutdown sweep (the feed
    # for the new bankruptcy tag) executed zero times on every run.
    jobs = [(qs[i], locales[0]) for i in range(n_company)]
    for loc in locales:
        for q in qs[n_company:]:
            jobs.append((q, loc))

    results, seen = [], set()
    seen_titles = set()   # same story surfaces in several editions under
    errors = 0            # different redirect URLs; one LLM read is enough
    # Per-job slice: every (query, edition) pair gets a fair share of the global
    # cap, so a later job (the euphemism sweep, a company chase, a non-US
    # edition) can never be starved by an earlier one returning ~100 items.
    per_q = max(8, MAX_ITEMS // max(1, len(jobs)))
    for q, loc in jobs:
        if len(results) >= MAX_ITEMS:
            break
        taken_this_q = 0
        try:
            r = requests.get(_rss_url(q, loc[1], loc[2], loc[3]), headers=UA, timeout=30)
            if r.status_code != 200:
                errors += 1
                pull_google_news.last_error = f"HTTP {r.status_code}"
                time.sleep(GAP)
                continue
            items = _parse_items(r.text)
        except Exception as e:
            errors += 1
            pull_google_news.last_error = f"{type(e).__name__}: {e}"
            time.sleep(GAP)   # the error paths skipped the politeness gap,
            continue          # hammering the endpoint exactly when it 429s
        for it in items:
            link = (it.get("link") or "").strip()
            if not link or link in seen:
                continue
            seen.add(link)
            title = _clean(it.get("title"))
            tkey = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()[:120]
            if tkey and tkey in seen_titles:
                continue
            if tkey:
                seen_titles.add(tkey)
            desc = _clean(it.get("description"))
            source = (it.get("source") or "").strip()
            # The headcount lives in the title; the description is usually just a
            # link + outlet, but include it when it adds text. Name the outlet so
            # the extractor has attribution context.
            raw_text = (title + (". " + desc if desc and desc != title else "")).strip()
            if source and source.lower() not in raw_text.lower():
                raw_text = f"{raw_text} (via {source})"
            if not raw_text:
                continue
            results.append({
                "source_type": "news",
                "source_name": source or "Google News",
                "verification_level": "bronze",
                "raw_text": raw_text,
                "source_url": link,
                "company_name": None,   # the extractor fills this in
                "ticker": None,
                "filing_date": _iso_date(it.get("published")),
            })
            taken_this_q += 1
            if taken_this_q >= per_q or len(results) >= MAX_ITEMS:
                break
        time.sleep(GAP)

    # A run where every query errored (and nothing came back) is a real outage,
    # not a quiet day — surface it.
    if errors and errors == len(jobs) and not results:
        pull_google_news.last_error = pull_google_news.last_error or "all queries failed"
    print(f"Google News: {len(results)} unique items; {len(jobs)} query-edition "
          f"jobs planned across editions [{', '.join(l[0] for l in locales)}]"
          + (f" ({errors} error(s))" if errors else ""))
    return results


if __name__ == "__main__":
    # Manual smoke test: python -m sources.google_news
    rows = pull_google_news()
    for r in rows[:10]:
        print(f"  [{r['source_name']}] {r['raw_text'][:90]}")
    print(f"total: {len(rows)}; last_error={getattr(pull_google_news,'last_error',None)}")
