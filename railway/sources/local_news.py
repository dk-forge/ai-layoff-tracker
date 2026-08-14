"""DORMANT local-language layoff discovery for markets the English sweep misses.

WHY THIS EXISTS (measured 2026-08-13 against the live /facets and Google News RSS,
not assumed). Switzerland held exactly one entry ever; Russia, Kenya and Chile
held none; Nigeria held one. Probing each market's Google News edition showed
three DIFFERENT causes, which is why one fix would not have worked:

  Switzerland  The edition exists and is already rotated by sources/google_news,
               but every DISCOVERY_QUERIES string is English. The English query
               on hl=de&gl=CH returns the global English feed (Zillow, Der
               Standard, a Minnesota paper). The same edition asked in German
               returns Chopard cutting 25 posts and DuMont; asked in French it
               returns Swisscom offshoring to Portugal and 900 posts at SSR.
               The edition was never the gap. The LANGUAGE was.

  Russia       No RU edition existed in GOOGLE_NEWS_LOCALES at all, so nothing
               Russian was ever requested. The English query against a manually
               constructed RU edition returns only ~48 items (thin), the Russian
               one returns a full 100 -- but dominated by individual-dismissal
               and employment-law noise (a supreme-court ruling on dismissal
               procedure, a reprimand case). Bare "увольнения" is individual
               firing vocabulary and must NOT be a discovery term; the
               collective-reduction phrases are "сокращение штата" and
               "сокращение персонала".

  Kenya        Edition exists, is English, and the existing English query
               ALREADY runs against it. It is not a language gap at all: the
               generic layoff query returns the same global feed (The
               Conversation, Oracle, Business Insider) inside the local edition.
               Kenyan events need LOCALITY anchoring, not translation.

  Nigeria      Same as Kenya. Additionally the Nigerian-English synonyms are a
               precision trap: a bare "sack" query returned two child-kidnapping
               stories in its top three. "sack" is only usable paired with a
               workforce word.

  Chile        Edition exists and the English query already runs against it and
               returns the global feed. Asked in Spanish the SAME edition
               returns genuinely Chilean events (HIF executing dismissals at
               Punta Arenas, Canal 13). Pure language gap, and the cleanest of
               the five.

A fourth failure mode was CHECKED AND RULED OUT: nothing is being discovered and
then lost to country normalization. alt_normalize_country() passes an unknown
single country through unchanged, so a German article yielding "Schweiz" would
mint a visible "Schweiz" bucket. The live /facets carries no Schweiz, Suisse,
Rusia or Россия bucket, so no such rows exist. The rows are not arriving at all.

THE TWO-TIER RELEVANCE FILTER, and why it is the whole cost story.
An edition does NOT imply a country: hl=de&gl=CH returns plenty of Germany. If
every item a Swiss query returned were sent to the LLM we would pay to extract
German stories under a Swiss budget. So each candidate must pass a FREE keyword
check before it is allowed to cost anything:

    text carries a country anchor  OR  the outlet is a known national publisher

The second half is what preserves recall. "Chopard: Warum 25 Stellen gestrichen
werden mussten - Bilanz" carries no Swiss token anywhere in its title, so a text
anchor alone would drop a real Swiss event; Bilanz being a Swiss publication
rescues it. The anchor is a COST filter, never a truth claim -- the extractor
still decides the country, as it does for every other source.

RAW-TEXT OUTLET ENRICHMENT. Google News titles are short and the extractor reads
ONLY raw_text. "... - Bilanz" does not tell a model that Bilanz is Swiss, which
is the most likely reason the handful of local stories that did get discovered
never landed with a country. Where the outlet is in the curated national
publisher map we append a neutral factual note about the OUTLET ("via Bilanz, a
Swiss publication"). That is a fact about the source, not about the event, and
the extractor remains free to conclude a different country -- a Swiss paper
covering a German plant closure should still be Germany.

DORMANT BY DEFAULT. This collector needs no API key, so its dormancy gate is an
explicit arming variable: LOCAL_NEWS_COUNTRIES. Unset or empty, pull_local_news
returns [] and prints why, and costs nothing. See the module docstring of
railway/local_news_ingest.py for the dry-run and the arming command.

Nothing here writes a row. Every candidate becomes a raw dict with raw_text set
and goes through extract_layoff_data -> post_to_wordpress like every other
source, so dedup, count-verbatim, date bounds and normalization apply once.
"""
from __future__ import annotations

import html
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from sources import local_news_markets as _markets

# requests is imported LAZILY, inside the one function that performs a network
# call. The dormant path, the market table, the aggregator rule and the
# relevance filter are all pure, so tests and the dry-run planner can import
# this module and exercise the real production logic without the dependency
# and without any possibility of an accidental fetch.

RSS = "https://news.google.com/rss/search"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}


def _env_int(name, default):
    try:
        return int(str(os.environ.get(name, default)).strip() or default)
    except (TypeError, ValueError):
        print(f"{name} invalid; using default {default}")
        return int(default)


# Per-country cap on candidates that survive the relevance filter. This is the
# knob that binds cost: everything past it is never fetched into the LLM.
MAX_PER_COUNTRY = max(1, _env_int("LOCAL_NEWS_MAX_PER_COUNTRY", 12))
GAP = max(0.0, float(os.environ.get("LOCAL_NEWS_GAP_SECONDS", "1")))


# ---------------------------------------------------------------------------
# AGGREGATOR EXCLUSION.
#
# A layoff TRACKER is never a source here. Storing one would republish another
# party's compiled dataset as though we had verified it, and it would also
# destroy any later recall measurement: we would be measuring our agreement
# with a list rather than our coverage of the world.
#
# This is expressed STRUCTURALLY (URL shapes that mean "a running tally") plus a
# small set of named non-news tally products, rather than as a roster of rival
# trackers -- naming those in this repo is separately forbidden, and a
# structural rule catches the ones we must not write down anyway.
#
# INDIVIDUAL ARTICLES from these publishers remain perfectly fine. Only their
# tally products are excluded, which is why the path patterns matter.
AGGREGATOR_URL_PATTERNS = (
    r"layoff[-_/]?track",          # .../layoff-tracker, layoff_tracking
    r"track(er|ing)[-_/]?layoff",
    r"layoffs?[-_/]?(list|tally|database|dataset|count)",
    r"job[-_/]?cuts?[-_/]?track",
    r"who[-_/]?s[-_/]?(hiring|firing)",
    r"companies[-_/]?(leaving|exiting|withdraw)",   # exit lists, e.g. the Yale
                                                    # SOM companies-exiting-
                                                    # Russia list: a compiled
                                                    # tally, not reporting
    r"running[-_/]?(list|tally)",
)
_AGG_RX = re.compile("|".join(AGGREGATOR_URL_PATTERNS), re.I)

# Hosts (and host prefixes) whose PRIMARY product is a compiled tally rather
# than reporting. Kept deliberately tiny and non-competitive.
AGGREGATOR_HOSTS = frozenset({
    "som.yale.edu",          # companies-exiting-Russia exit list
    "insights.techcabal.com",  # TC Insights research arm, not the newsroom
})

# A URL RULE IS NOT ENOUGH, and this is the sharpest lesson from the feed audit.
# The outlets that run a layoff tally also REPUBLISH that tally onto their
# ordinary article path -- e.g. an "inside Africa's tech layoffs" aggregate
# report and a year-end "12 startups that cut workforce" listicle both live
# under the normal /YYYY/MM/DD/slug/ pattern and arrive in the ordinary feed.
# A path-prefix exclusion cannot see them. These match the SHAPE of a roundup
# headline instead, and they are deliberately narrow: every one requires an
# enumeration cue, so a single-employer story ("GTBank lays off 300 staff")
# never matches.
AGGREGATOR_TITLE_PATTERNS = (
    r"\b\d+\s+\w*\s*(startups?|companies|firms|employers)\b[^.]*\b"
    r"(cut|laid off|layoffs?|shut|closed|downsized)\b",
    r"\binside\b[^.]*\blayoffs?\b",
    r"\blayoffs?\b[^.]*\b(tracker|roundup|round-up|tally|so far this year)\b",
    r"\b(tracking|tracker)\b[^.]*\blayoffs?\b",
    r"\blayoffs?\b[^.]*\bin\s+(h[12]|q[1-4])\s*20\d\d\b",
    r"\b(every|all the)\b[^.]*\blayoffs?\b",
    r"\blist of\b[^.]*\b(layoffs?|job cuts)\b",
)
_AGG_TITLE_RX = re.compile("|".join(AGGREGATOR_TITLE_PATTERNS), re.I)


def is_aggregator(url: str, outlet: str = "", title: str = "") -> bool:
    """True when a candidate is a compiled layoff tally rather than reporting.

    Three independent checks, because one alone leaks: the HOST (a research
    subdomain), the URL SHAPE (a tracker path), and the TITLE SHAPE (a roundup
    republished onto an ordinary article path).
    """
    u = str(url or "")
    if title and _AGG_TITLE_RX.search(str(title)):
        return True
    if not u:
        return False
    try:
        host = (urllib.parse.urlsplit(u).hostname or "").lower().lstrip(".")
    except ValueError:
        return True   # unparseable -> refuse rather than admit
    if host:
        for bad in AGGREGATOR_HOSTS:
            if host == bad or host.endswith("." + bad):
                return True
    return bool(_AGG_RX.search(u) or _AGG_RX.search(str(outlet or "")))


# ---------------------------------------------------------------------------
# THE MARKET TABLE lives in sources/local_news_markets.py: publishers, country
# anchors, editions and the per-language phrase sets, one reviewable record per
# country. Keeping it out of here means a market correction never risks the
# fetching/filtering logic, and the logic is testable without the table.
COUNTRIES = _markets.COUNTRIES


def market(country):
    """The Market record for a country name, or None."""
    return _markets.BY_COUNTRY.get(country)


def armed_countries():
    """Countries this run is armed for. Empty tuple means DORMANT."""
    raw = (os.environ.get("LOCAL_NEWS_COUNTRIES") or "").strip()
    if not raw:
        return ()
    if raw.lower() in {"all", "*"}:
        return COUNTRIES
    if raw.lower().startswith("tier"):
        try:
            want = int(raw.split("tier", 1)[1].strip() or 0)
        except ValueError:
            want = 0
        if want:
            return tuple(m.country for m in _markets.MARKETS if m.tier == want)
    picked, unknown = [], []
    for part in re.split(r"[,;|]", raw):
        name = part.strip()
        if not name:
            continue
        match = next((c for c in COUNTRIES if c.lower() == name.lower()), None)
        if match:
            picked.append(match)
        else:
            unknown.append(name)
    if unknown:
        print(f"LOCAL_NEWS_COUNTRIES: ignoring unknown {unknown}; "
              f"known countries are {list(COUNTRIES)}")
    return tuple(dict.fromkeys(picked))


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _rss_url(query, hl, gl, ceid):
    return f"{RSS}?" + urllib.parse.urlencode(
        {"q": query, "hl": hl, "gl": gl, "ceid": ceid})


def _iso_date(pubdate):
    if not pubdate:
        return ""
    try:
        return parsedate_to_datetime(pubdate).date().isoformat()
    except Exception:
        return ""


def _parse_items(xml_text):
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


def publisher_of(country, outlet):
    """The matched national-publisher token, or '' when the outlet is unknown."""
    o = str(outlet or "").lower()
    m = market(country)
    if not o or m is None:
        return ""
    for token in m.publishers:
        if token in o:
            return token
    return ""


def anchor_hit(country, text):
    """The matched country anchor token in the text, or ''."""
    t = str(text or "").lower()
    m = market(country)
    if not t or m is None:
        return ""
    for token in m.anchors:
        if token in t:
            return token
    return ""


def relevance(country, title, snippet, outlet):
    """Free pre-LLM country filter.

    Returns (keep: bool, why: str). A candidate is kept when the text carries a
    country anchor OR the outlet is a curated national publisher. This decides
    what is ALLOWED to cost money; it never decides what country is stored.
    """
    pub = publisher_of(country, outlet)
    if pub:
        return True, f"publisher:{pub}"
    tok = anchor_hit(country, f"{title} {snippet}")
    if tok:
        return True, f"anchor:{tok}"
    return False, "no-country-evidence"


def build_raw(country, item):
    """One RSS item -> the standard raw dict, or None when it is filtered out.

    Mirrors sources/newsapi.py and sources/google_news.py exactly: raw_text is
    always set (the extractor reads ONLY that), and nothing else is asserted
    about the event.
    """
    link = (item.get("link") or "").strip()
    if not link:
        return None
    title = _clean(item.get("title"))
    desc = _clean(item.get("description"))
    outlet = (item.get("source") or "").strip()
    if is_aggregator(link, outlet, title):
        return None
    keep, _why = relevance(country, title, desc, outlet)
    if not keep:
        return None
    raw_text = (title + (". " + desc if desc and desc != title else "")).strip()
    if not raw_text:
        return None
    pub = publisher_of(country, outlet)
    if outlet:
        m = market(country)
        note = (m.note if (pub and m is not None) else "")
        # A fact about the OUTLET, never about the event. The extractor is still
        # free to conclude a different country for the jobs themselves.
        raw_text = f"{raw_text} (via {outlet}{', ' + note if note else ''})"
    return {
        "source_type": "news",
        "source_name": outlet or "Google News",
        "verification_level": "bronze",
        "raw_text": raw_text,
        "source_url": link,
        "company_name": None,
        "ticker": None,
        "filing_date": _iso_date(item.get("published")),
    }


def pull_local_news(countries=None, fetch=None):
    """Return (rows, stats). DORMANT unless LOCAL_NEWS_COUNTRIES is set.

    `fetch` is injectable for tests: fetch(url) -> (status_code, text).
    Fail-loud: pull_local_news.last_error is set on any HTTP/parse failure so a
    caller degrades the source instead of masking a dead feed as 'ok'.
    """
    pull_local_news.last_error = None
    picked = tuple(countries) if countries else armed_countries()
    stats = {c: {"fetched": 0, "aggregator": 0, "dropped": 0,
                 "kept": 0, "errors": 0, "why": {}} for c in picked}
    if not picked:
        print("local_news: DORMANT — LOCAL_NEWS_COUNTRIES is unset, so no "
              "request was made and nothing was spent. Known countries: "
              + ", ".join(COUNTRIES))
        return [], stats

    def _default_fetch(url):
        import requests
        r = requests.get(url, headers=UA, timeout=30)
        return r.status_code, r.text
    do_fetch = fetch or _default_fetch

    rows, seen_links, seen_titles = [], set(), set()
    for country in picked:
        st = stats[country]
        for ed in (market(country).editions if market(country) else ()):
            for q in ed.queries:
                if st["kept"] >= MAX_PER_COUNTRY:
                    break
                try:
                    status, body = do_fetch(_rss_url(q, ed.hl, ed.gl, ed.ceid))
                    if status != 200:
                        st["errors"] += 1
                        pull_local_news.last_error = f"HTTP {status} ({ed.lang})"
                        time.sleep(GAP)
                        continue
                    items = _parse_items(body)
                except Exception as e:
                    st["errors"] += 1
                    pull_local_news.last_error = f"{type(e).__name__}: {e} ({ed.lang})"
                    time.sleep(GAP)
                    continue
                for it in items:
                    st["fetched"] += 1
                    link = (it.get("link") or "").strip()
                    if not link or link in seen_links:
                        continue
                    title = _clean(it.get("title"))
                    tkey = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()[:120]
                    if tkey and tkey in seen_titles:
                        continue
                    outlet = (it.get("source") or "").strip()
                    if is_aggregator(link, outlet, title):
                        st["aggregator"] += 1
                        continue
                    keep, why = relevance(country, title, _clean(it.get("description")), outlet)
                    st["why"][why.split(":")[0]] = st["why"].get(why.split(":")[0], 0) + 1
                    if not keep:
                        st["dropped"] += 1
                        continue
                    raw = build_raw(country, it)
                    if not raw:
                        st["dropped"] += 1
                        continue
                    seen_links.add(link)
                    if tkey:
                        seen_titles.add(tkey)
                    raw["_country_plan"] = country     # diagnostics only; the
                    raw["_why"] = why                  # poster ignores unknown keys
                    rows.append(raw)
                    st["kept"] += 1
                    if st["kept"] >= MAX_PER_COUNTRY:
                        break
                time.sleep(GAP)
    total_err = sum(s["errors"] for s in stats.values())
    if total_err and not rows:
        pull_local_news.last_error = pull_local_news.last_error or "all queries failed"
    return rows, stats
