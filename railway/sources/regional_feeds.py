"""Regional-feed discovery: many low-volume countries at one feed's cost.

WHY THIS EXISTS (measured 2026-08-14, live, from a machine with real egress).
~90 monitored countries hold nothing, and most are places where a national
Google News edition either does not exist or returns the global English feed.
The owner's own country research surfaced the same handful of REGIONAL outlets
four to six times each: one Pacific service covers eighteen island states a
per-country sweep would never justify wiring individually. This module reads
those regional outlets' own RSS feeds directly.

EVERY CANDIDATE FEED WAS PROBED LIVE BEFORE WIRING, and half of them failed.
The verdicts, so nobody re-litigates them from memory:

  WIRED (machine-readable feed, robots.txt permits, summaries free):
    RNZ Pacific            200, 18 items, title+standfirst free, robots allows
    Pacific Island Times   200, 20 items (Wix blog-feed.xml), robots allows
    Financial Afrik        200, 15 items. The description is a members-only
                           teaser; ONLY THE HEADLINE is free text. Francophone
                           business headlines usually carry the figure
                           ("suppression de 300 postes"), but an event whose
                           headcount lives only behind the wall is lost, and
                           that is stated on the tin rather than papered over.
    Jeune Afrique          200, 30 items, title + ~200-char standfirst free.
                           robots.txt disallows "/*/feed" (per-section feeds)
                           and "/*?"; the site-level /feed/ matches neither.
    Caribbean News Global  200 but SLOW (~40s first byte; the first probe at a
                           25s timeout read as dead). Ships FULL article text
                           in content:encoded. Gets a 90s timeout, not a retry
                           loop.

  NOT WIRED, with the measured reason:
    PACNEWS/PINA           /feed/ answers 200 but the single item says "Sorry,
                           You Don't Have Feed Access" - feed access is gated.
    Loop News              TLS is broken on every probed host: www cert EXPIRED,
                           caribbean subdomain cert name-mismatch. Never bypass
                           certificate verification; dead until they fix it.
    Marianas Variety       robots.txt ends "User-agent: * Disallow: /".
                           Respected; off limits however good the feed looks.
    Balkan Insight         robots.txt FIRST group is "User-agent: * Disallow: /"
                           (named bots only are allowed). Same rule, same answer.
    ABC Pacific            No machine-readable Pacific feed exists: the topic
                           RSS path 404s, /news/feed/<id> serves other desks.

A REGIONAL FEED'S JOB IS DISCOVERY ONLY. No country is ever pre-assigned from
the feed: the extractor decides the country from the article text, exactly as
for every other news source. The `countries` tuple on each Feed is a coverage
claim for the sources page and the run report, never a stored value.

THE RELEVANCE FILTER is a free cost gate, not a truth claim: only items whose
free text carries collective-reduction vocabulary (English or French - the two
languages these five feeds publish in) are allowed to cost an extraction.
Lessons inherited from local_news: collective vocabulary only ("licenciements",
never singular court-story "licenciement"), and noisy homographs ("sack") only
paired with a workforce word.

VOLUME FLOORS: none on candidates, deliberately. A Pacific or Caribbean feed
honestly produces zero layoff stories most weeks, so a candidate floor would
manufacture alarms out of honest absence. The floor is on the FEED itself: a
non-200, an unparseable body, or a 200 whose body is not an RSS document is a
counted error and sets last_error - that is how a dead URL or a changed
scheme fails loudly while a quiet week stays quiet.

Nothing here writes a row. Every kept candidate becomes a raw dict with
raw_text set and goes through extract_layoff_data -> post_to_wordpress like
every other source, so dedup, count-verbatim, date bounds and normalization
apply once.
"""
from __future__ import annotations

import html
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

# The aggregator rule is ONE definition, shared with local_news: a layoff
# tally, a compiled exit list or a roundup republished onto an article path is
# never a source, from any collector.
from sources.local_news import is_aggregator

# requests is imported LAZILY inside the default fetcher, so tests and the
# dry-run planner can import this module without the dependency and without
# any possibility of an accidental fetch.

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
_CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}encoded"


def _env_int(name, default):
    try:
        return int(str(os.environ.get(name, default)).strip() or default)
    except (TypeError, ValueError):
        print(f"{name} invalid; using default {default}")
        return int(default)


# Per-feed cap on candidates that survive the relevance filter per run. This
# binds the worst case by construction: 5 feeds x 10 candidates x 2 runs/day x
# 30 days x $0.000315 = $0.95/month even if every item on every feed were a
# layoff story and none had ever been seen before. seen_urls dedup makes the
# realistic figure far lower (each URL costs at most once, ever).
MAX_PER_FEED = max(1, _env_int("REGIONAL_FEEDS_MAX_PER_FEED", 10))
GAP = max(0.0, float(os.environ.get("REGIONAL_FEEDS_GAP_SECONDS", "1")))

# One item's contribution to raw_text is bounded so a full-text feed item
# (Caribbean News Global ships whole articles) cannot blow the extractor's
# text budget.
MAX_RAW_TEXT = 1600


@dataclass(frozen=True)
class Feed:
    key: str           # health/diagnostics id, stable
    url: str           # the ONE URL this collector requests for the feed
    outlet: str        # human name, goes into the raw_text outlet note
    note: str          # publication-region phrase appended to raw_text
    countries: tuple   # coverage claim for the sources page; NEVER stored
    timeout: int = 30  # measured: caribbean_news_global needs ~40s first byte


FEEDS = (
    Feed("rnz_pacific",
         "https://www.rnz.co.nz/rss/pacific.xml",
         "RNZ Pacific",
         "a New Zealand public broadcaster's Pacific regional news service",
         ("Fiji", "Papua New Guinea", "Samoa", "Tonga", "Vanuatu",
          "Solomon Islands", "Kiribati", "Tuvalu", "Nauru", "Palau",
          "Marshall Islands", "Micronesia", "Cook Islands", "Niue",
          "New Caledonia", "French Polynesia", "American Samoa")),
    Feed("pacific_island_times",
         "https://www.pacificislandtimes.com/blog-feed.xml",
         "Pacific Island Times",
         "a Guam-based publication covering Micronesia",
         ("Guam", "Northern Mariana Islands", "Palau", "Micronesia",
          "Marshall Islands", "American Samoa")),
    Feed("financial_afrik",
         "https://www.financialafrik.com/feed/",
         "Financial Afrik",
         "a pan-African financial publication reporting in French",
         ("Senegal", "Ivory Coast", "Cameroon", "Morocco", "Tunisia",
          "Gabon", "Benin", "Togo", "Mali", "Burkina Faso", "Guinea",
          "Mauritania", "Niger", "Madagascar", "Chad", "Djibouti")),
    Feed("jeune_afrique",
         "https://www.jeuneafrique.com/feed/",
         "Jeune Afrique",
         "a pan-African news magazine reporting in French",
         ("Algeria", "Morocco", "Tunisia", "Senegal", "Ivory Coast",
          "Cameroon", "Mali", "Burkina Faso", "Guinea", "Gabon", "Togo",
          "Benin", "Niger", "Chad", "Madagascar")),
    Feed("caribbean_news_global",
         "https://caribbeannewsglobal.com/feed/",
         "Caribbean News Global",
         "a Caribbean regional news publication",
         ("Saint Lucia", "Jamaica", "Barbados", "Guyana", "Grenada",
          "Dominica", "Belize", "Bahamas", "Suriname", "Haiti"),
         timeout=90),
)
BY_KEY = {f.key: f for f in FEEDS}


def by_key(key):
    """The Feed record for a key, or None."""
    return BY_KEY.get(key)


#: The committed arming decision, priced from the live feeds on 2026-08-14.
#: The five feeds carry ~55 items/day combined; even if EVERY item passed the
#: relevance filter and none were URL-deduped, that is 55 x 30 x $0.000315 =
#: $0.52/month, and MAX_PER_FEED independently caps the worst case at
#: $0.95/month. The realistic figure (filter pass rate measured at 0/97 items
#: on wiring day) is under $0.05/month. That is inside the owner's authorized
#: ~$10 layoff budget alongside the $4.92 committed path and the $5.14
#: local-news markets, so this ships ARMED, same pattern as local_news.
#: REGIONAL_FEEDS still overrides for a subset dry run; "off" disarms without
#: a deploy.
ARMED_BY_DEFAULT = "all"


def armed_feeds():
    """The Feed records this run is armed for. Empty tuple means DORMANT."""
    raw = (os.environ.get("REGIONAL_FEEDS") or "").strip()
    if raw.lower() == "off":
        return ()
    if not raw:
        raw = ARMED_BY_DEFAULT
    if not raw:
        return ()
    if raw.lower() in {"all", "*"}:
        return FEEDS
    picked, unknown = [], []
    for part in re.split(r"[,;|]", raw):
        key = part.strip().lower()
        if not key:
            continue
        if key in BY_KEY:
            picked.append(BY_KEY[key])
        else:
            unknown.append(key)
    if unknown:
        print(f"REGIONAL_FEEDS: ignoring unknown {unknown}; "
              f"known feeds are {sorted(BY_KEY)}")
    return tuple(dict.fromkeys(picked))


# ---------------------------------------------------------------------------
# RELEVANCE: the free cost gate. Collective-reduction vocabulary only, in the
# two languages these feeds publish in. Substring match on lowercased text.
EN_TERMS = (
    "layoff", "lay off", "lays off", "laid off", "redundanc", "retrench",
    "job cuts", "jobs cut", "downsiz", "workforce reduction", "staff cut",
    "jobs to go", "positions eliminated",
)
# Headlines interleave the figure with the verb ("cuts 200 jobs", "suppression
# de 300 postes"), which plain substrings cannot see. These carry an optional
# number between verb and noun; nothing here matches a figure-free generic
# sentence a substring would not already catch.
EN_PATTERNS = re.compile(
    r"\b(cut|cuts|cutting|axe|axes|axed|shed|sheds|shedding)\s+"
    r"(?:[\d][\d,.\s]*\s*)?jobs\b", re.I)
FR_PATTERNS = re.compile(
    r"suppressions?\s+d[e'’]\s*(?:[\d][\d\s.,]*\s*)?(postes|emplois)", re.I)
FR_TERMS = (
    # Plural / collective only: singular "licenciement" is the vocabulary of
    # individual-dismissal court stories, the same trap local_news documented
    # for Russian individual-firing vocabulary.
    "licenciements", "licenciement collectif", "licenciement economique",
    "licenciement économique", "plan social", "plans sociaux",
    "suppression de postes", "suppressions de postes",
    "suppression d'emplois", "suppressions d'emplois", "emplois supprimes",
    "emplois supprimés", "postes supprimes", "postes supprimés",
    "compression du personnel", "reduction des effectifs",
    "réduction des effectifs",
)
# Noisy homographs, kept only when paired with a workforce word (the Nigeria
# "sack" lesson from local_news: bare, it matches kidnapping stories).
PAIRED_TERMS = (
    ("sack", ("workers", "staff", "employees")),
)


def relevance(title, snippet):
    """Free pre-LLM layoff filter. Returns (keep, why).

    This decides what is ALLOWED to cost money; it never decides what is
    stored - the extractor still rules on every kept candidate.
    """
    t = f"{title} {snippet}".lower()
    for term in EN_TERMS + FR_TERMS:
        if term in t:
            return True, f"term:{term}"
    if EN_PATTERNS.search(t):
        return True, "pattern:en-jobs-verb"
    if FR_PATTERNS.search(t):
        return True, "pattern:fr-suppression"
    for term, partners in PAIRED_TERMS:
        if term in t and any(p in t for p in partners):
            return True, f"paired:{term}"
    return False, "no-layoff-vocabulary"


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _iso_date(pubdate):
    if not pubdate:
        return ""
    try:
        return parsedate_to_datetime(pubdate).date().isoformat()
    except Exception:
        return ""


def _parse_items(xml_text):
    """Returns (items, is_feed). is_feed is False when the body is not an RSS
    document at all - the changed-scheme shape (an HTML page at a former feed
    path), which the caller must count as an error. A VALID channel with zero
    items is ([], True): a quiet feed is honest absence, not breakage."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out, False
    if root.tag.split("}")[-1] != "rss" or root.find("channel") is None:
        return out, False
    for item in root.iter("item"):
        def _t(tag):
            el = item.find(tag)
            return el.text if el is not None and el.text else ""
        enc = item.find(_CONTENT_NS)
        out.append({
            "title": _t("title"),
            "link": _t("link"),
            "description": _t("description"),
            "published": _t("pubDate"),
            "content": (enc.text if enc is not None and enc.text else ""),
        })
    return out, True


def build_raw(feed, item):
    """One feed item -> the standard raw dict, or None when filtered out.

    Mirrors sources/newsapi.py and sources/local_news.py exactly: raw_text is
    always set (the extractor reads ONLY that), no country is ever asserted,
    and the outlet note is a fact about the SOURCE, never about the event.
    """
    link = _clean(item.get("link"))
    if not link:
        return None
    title = _clean(item.get("title"))
    desc = _clean(item.get("description"))
    content = _clean(item.get("content"))
    if is_aggregator(link, feed.outlet, title):
        return None
    keep, _why = relevance(title, f"{desc} {content}")
    if not keep:
        return None
    parts = [title]
    if desc and desc != title:
        parts.append(desc)
    if content and content != desc:
        parts.append(content)
    raw_text = ". ".join(p.rstrip(".") for p in parts if p).strip()
    if not raw_text:
        return None
    raw_text = raw_text[:MAX_RAW_TEXT]
    raw_text = f"{raw_text} (via {feed.outlet}, {feed.note})"
    return {
        "source_type": "news",
        "source_name": feed.outlet,
        "verification_level": "bronze",
        "raw_text": raw_text,
        "source_url": link,
        "company_name": None,
        "ticker": None,
        "filing_date": _iso_date(item.get("published")),
    }


def pull_regional_feeds(feeds=None, fetch=None):
    """Return (rows, stats). Armed by default; REGIONAL_FEEDS=off disarms.

    `fetch` is injectable for tests: fetch(url, timeout) -> (status, text).
    Fail-loud: pull_regional_feeds.last_error is set on any HTTP/parse/empty
    failure so the caller degrades the source instead of masking a dead feed.
    """
    pull_regional_feeds.last_error = None
    picked = tuple(feeds) if feeds else armed_feeds()
    stats = {f.key: {"fetched": 0, "aggregator": 0, "dropped": 0,
                     "kept": 0, "errors": 0} for f in picked}
    if not picked:
        print("regional_feeds: DORMANT (REGIONAL_FEEDS=off, or the armed set "
              "is empty), so no request was made and nothing was spent. "
              "Known feeds: " + ", ".join(sorted(BY_KEY)))
        return [], stats

    def _default_fetch(url, timeout):
        import requests
        r = requests.get(url, headers=UA, timeout=timeout)
        return r.status_code, r.text
    do_fetch = fetch or _default_fetch

    rows, seen_links = [], set()
    for feed in picked:
        st = stats[feed.key]
        try:
            status, body = do_fetch(feed.url, feed.timeout)
        except Exception as e:
            st["errors"] += 1
            pull_regional_feeds.last_error = f"{feed.key}: {type(e).__name__}: {e}"
            time.sleep(GAP)
            continue
        if status != 200:
            st["errors"] += 1
            pull_regional_feeds.last_error = f"{feed.key}: HTTP {status}"
            time.sleep(GAP)
            continue
        items, is_feed = _parse_items(body)
        if not is_feed:
            # The changed-scheme shape: the URL still answers 200 but the body
            # is no longer an RSS document (an HTML page at a former feed
            # path). A valid channel with zero items is NOT this - a quiet
            # week in the Pacific is honest absence.
            st["errors"] += 1
            pull_regional_feeds.last_error = (
                f"{feed.key}: 200 but the body is not an RSS feed - "
                f"scheme changed?")
            time.sleep(GAP)
            continue
        for it in items:
            st["fetched"] += 1
            if st["kept"] >= MAX_PER_FEED:
                break
            link = _clean(it.get("link"))
            if not link or link in seen_links:
                continue
            title = _clean(it.get("title"))
            if is_aggregator(link, feed.outlet, title):
                st["aggregator"] += 1
                continue
            raw = build_raw(feed, it)
            if not raw:
                st["dropped"] += 1
                continue
            seen_links.add(link)
            raw["_feed_key"] = feed.key   # diagnostics only; the poster
            rows.append(raw)              # ignores unknown keys
            st["kept"] += 1
        time.sleep(GAP)
    return rows, stats


if __name__ == "__main__":
    # Free dry run: fetches the armed feeds, applies the real filters, PRINTS
    # what would have been sent to the LLM, extracts nothing and posts nothing.
    #   REGIONAL_FEEDS=all python3 -m sources.regional_feeds
    COST_PER_CANDIDATE_USD = 0.000315   # measured on the news path, 2026-08
    rows, stats = pull_regional_feeds()
    for key in sorted(stats):
        st = stats[key]
        print(f"{key}: fetched={st['fetched']} kept={st['kept']} "
              f"dropped={st['dropped']} aggregator={st['aggregator']} "
              f"errors={st['errors']}")
    n = len(rows)
    print(f"candidates this run: {n} -> ${n * COST_PER_CANDIDATE_USD:.4f} "
          f"if every one were new (seen_urls dedup makes repeats free)")
    for r in rows:
        print(f"  [{r['_feed_key']}] {r['raw_text'][:120]}")
    if pull_regional_feeds.last_error:
        print(f"last_error: {pull_regional_feeds.last_error}")
        raise SystemExit(2)
