"""One verified national publisher per Tier-2 economy, read from its own feed.

WHY THIS EXISTS (probed live and first-party on 2026-08-14 from a machine with
real egress). The local-language sweep asks Google News editions; the regional
feeds read one outlet for a whole region. Between them sits a band of
mid-sized economies where neither works: the national edition returns the
global English feed, and no regional service covers the country at all.
Ethiopia, Jordan, Iraq, Nepal, Paraguay and Papua New Guinea held nothing and
had no route to hold anything. This module reads ONE national business or
general publisher per such country, directly from its own RSS.

EVERY CANDIDATE WAS PROBED BEFORE WIRING AND TEN OF TWENTY-FIVE FAILED. The
refusals are recorded with their measured evidence in
`railway/data/source_catalogue.json` and rendered on the public sources page,
because a country we deliberately hold nothing on should be a visible row that
says why, not an omission. The short version, so nobody re-probes from memory:

  WIRED (200, parses as RSS, items present, robots.txt permits the path):
    Daily News Egypt      10 items, ~700-char descriptions
    La Republica (CO)     60 items, Colombia's business daily
    Addis Fortune (ET)    12 items, ~390-char descriptions
    Kursiv (KZ)          100 items, in Russian. This is the measured fix for
                         "Kazakhstan: 201 items, 0 local" - the ru-KZ Google
                         News edition serves Russian press, not Kazakh press.
    MyJoyOnline (GH)      50 items, carries the Joy Business desk
    Dawn Business (PK)    30 items, ~3,800-char descriptions (near-full text)
    Jordan News (JO)      15 items. Published by the state-owned Jordan Press
                         Foundation; that provenance is noted on the catalogue
                         row rather than left for a reader to discover.
    Iraq Business News    40 items, ~630-char descriptions
    Jamaica Gleaner       10 items, the paper's own business desk feed
    The Kathmandu Post    40 items. The /money/rss desk path serves HTML; the
                         site-level /rss is the one that parses. Re-probed
                         2026-09-03: still 200, still RSS, still 40 items, but
                         one item title carries a bare "&" ("Q&A: ..."), which
                         a conforming parser must reject. Read through the
                         bare-ampersand escape in regional_feeds; the URL was
                         never wrong.
    Post-Courier (PG)     10 items shipping FULL article text (~6.6k chars)
    ABC Color Economia    33 items, via the publisher's arc outbound feed
    Biznis.rs (RS)        50 items, ~1,260-char descriptions
    Gestion Economia (PE) 69 items, via the publisher's arc outbound feed

  REFUSED, each measured twice from a clean vantage before being called a
  refusal (full evidence in the catalogue JSON):
    Georgia    bm.ge answers 403 to robots.txt AND to the feed; bme.ge and
               georgiatoday.ge serve HTML at /feed/; agenda.ge presents a
               self-signed certificate chain. Certificate verification is
               never bypassed, so that one is closed until they fix it.
    Ivory Coast  Abidjan.net's economie.xml answers 200 with a 4.1MB body that
               is NOT well-formed (invalid token at line 2512). We do not
               hand-repair a third party's XML.
    Morocco    Medias24 and L'Economiste both 403, robots.txt included.
    Lebanon    Every L'Orient Today feed path 404s, and lorientlejour.com's
               robots.txt opens "User-agent: * Disallow: /". Respected.
    Oman       Times of Oman's feed IS RSS but carries an unbound namespace
               prefix at line 4; three paths, same defect.
    Kuwait     kuwaittimes.com/feed/ 404s and /rss serves HTML; Arab Times the
               same. (Kuwait is already swept in Arabic and English by
               local_news, so this is a duplicate route, not a hole.)
    Bahrain    GDN Online 404s at both feed paths; News of Bahrain's rss.xml
               serves HTML.
    Panama     Capital Financiero's TLS handshake fails outright; both La
               Prensa and La Estrella arc feeds 404.
    Mongolia   theubposts.com fails TLS, ubpost.mn and Montsame 404, news.mn
               times out.
    Moldova    Mold-Street answered 503 on three separate probes.

  DROPPED AS REDUNDANT, not retired and not lost:
    Sri Lanka  EconomyNext was wired here on 2026-08-14 and answered HTTP 202
               to the collector's own network from 2026-08-18 - a bot wall
               keyed on the datacentre's address range, since the same feed
               answers 200 from a laptop. The answer was neither to disguise
               the client nor to drop the country: MEASURED on 2026-08-18, the
               live Sri Lanka market sweep in local_news returns
               economynext.com items under its own committed queries (4 of 241
               items across the en/si/ta editions, alongside dailymirror.lk 9,
               sundaytimes.lk 6, island.lk 4, themorning.lk 4, ft.lk 3), and
               economynext.com is already a listed GDELT domain. The direct
               feed was therefore a SECOND route to a publisher we already
               read: over the 14 days to 2026-08-18 it stored zero rows, and
               the one item that passed the relevance filter on a laptop probe
               was a false positive (an SLT-Mobitel 5G/AI investment story).
               So the publisher moved to catalogue status "researched" -
               watched through its market sweep - and Sri Lanka keeps its
               coverage through the route that actually reaches it. The other
               paths on that host were probed too and none is an alternative:
               /feed/atom/ and the wp-json posts endpoint both answer 200 with
               a body that is not RSS, and /category/economy/feed/ 404s.

ONE PUBLISHER PER COUNTRY, and no aggregators, ever - the rule is imported
from local_news so there is a single definition of what a compiled tally is.

NO COUNTRY IS EVER PRE-ASSIGNED. The `country` on each Feed is a coverage
claim for the sources page and the run report. The extractor decides the
country from the article text, exactly as for every other news source: a
Nairobi-datelined story in a Ghanaian paper is Kenya's.

THE RELEVANCE FILTER is a free cost gate, not a truth claim. Only items whose
free text carries COLLECTIVE reduction vocabulary in one of the four languages
these feeds publish in (English, Spanish, Russian, Serbian) may cost an
extraction. Two lessons are inherited and re-applied per language: collective
vocabulary only (Spanish bare "despido" and Serbian bare "otkaz" are
individual-dismissal words, the same trap French "licenciement" and Russian
"увольнения" set), and noisy homographs only when paired with a workforce word.

VOLUME FLOORS: none on candidates. A national feed honestly produces no layoff
story most weeks. The floor is on the FEED: a non-200, an unparseable body, or
a 200 that is not an RSS document is a counted error that sets last_error, so
a dead URL fails loudly while a quiet week stays quiet. Those last two are
reported SEPARATELY as of 2026-09-03 - "not an RSS document" means our URL is
now wrong, "an RSS document that is not well-formed" means the publisher's is
- because for six weeks this collector said the first about the second and
Nepal went dark over an unescaped ampersand.

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
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

# The aggregator rule is ONE definition, shared with local_news and
# regional_feeds: a layoff tally, a compiled exit list or a roundup
# republished onto an article path is never a source, from any collector.
from sources.local_news import is_aggregator
# English collective-layoff vocabulary is also ONE definition, shared with the
# regional feeds. A correction to the English terms must land in both places
# at the same time or the two collectors disagree about what a layoff story is.
# `parse_feed` is the ONE definition of "is this body a feed, and if not,
# which kind of not": a scheme change is ours to fix, a malformed document is
# the publisher's, and reporting the second as the first is what cost Nepal
# six weeks (see FEED_SHAPES in regional_feeds).
from sources.regional_feeds import (EN_PATTERNS, EN_TERMS, PAIRED_TERMS,
                                    parse_feed, trim_trailing_junk)

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
# binds the worst case by construction; see ARMED_BY_DEFAULT for the arithmetic.
MAX_PER_FEED = max(1, _env_int("NATIONAL_FEEDS_MAX_PER_FEED", 8))
GAP = max(0.0, float(os.environ.get("NATIONAL_FEEDS_GAP_SECONDS", "1")))

# One item's contribution to raw_text is bounded so a full-text feed item
# (Post-Courier ships whole articles) cannot blow the extractor's text budget.
MAX_RAW_TEXT = 1600


@dataclass(frozen=True)
class Feed:
    key: str           # health/diagnostics id, stable
    url: str           # the ONE URL this collector requests for the feed
    outlet: str        # human name, goes into the raw_text outlet note
    country: str       # coverage claim for the sources page; NEVER stored
    lang: str          # which vocabulary set its items are read with
    note: str          # publication-country phrase appended to raw_text
    timeout: int = 30


FEEDS = (
    Feed("dailynews_egypt", "https://www.dailynewsegypt.com/feed/",
         "Daily News Egypt", "Egypt", "en",
         "an Egyptian English-language daily"),
    Feed("larepublica_co", "https://www.larepublica.co/rss",
         "La Republica", "Colombia", "es",
         "a Colombian business daily reporting in Spanish"),
    Feed("addis_fortune", "https://addisfortune.news/feed/",
         "Addis Fortune", "Ethiopia", "en",
         "an Ethiopian business weekly"),
    Feed("kursiv_kz", "https://kz.kursiv.media/feed/",
         "Kursiv", "Kazakhstan", "ru",
         "a Kazakh business publication reporting in Russian"),
    Feed("myjoyonline_gh", "https://www.myjoyonline.com/feed/",
         "MyJoyOnline", "Ghana", "en",
         "a Ghanaian news publication carrying the Joy Business desk"),
    Feed("dawn_business_pk", "https://www.dawn.com/feeds/business",
         "Dawn Business", "Pakistan", "en",
         "the business desk of Pakistan's largest English daily"),
    Feed("jordan_news", "https://www.jordannews.jo/rss",
         "Jordan News", "Jordan", "en",
         "a Jordanian English-language daily published by the state-owned "
         "Jordan Press Foundation"),
    Feed("iraq_business_news", "https://www.iraq-businessnews.com/feed/",
         "Iraq Business News", "Iraq", "en",
         "an Iraqi business news publication"),
    Feed("jamaica_gleaner_business", "https://jamaica-gleaner.com/feed/business.xml",
         "Jamaica Gleaner", "Jamaica", "en",
         "the business desk of a Jamaican national daily"),
    Feed("kathmandu_post", "https://kathmandupost.com/rss",
         "The Kathmandu Post", "Nepal", "en",
         "a Nepali English-language national daily"),
    Feed("post_courier_pg", "https://www.postcourier.com.pg/feed/",
         "Post-Courier", "Papua New Guinea", "en",
         "a Papua New Guinean national daily"),
    Feed("abc_color_economia", "https://www.abc.com.py/arc/outboundfeeds/rss/"
                               "category/economia/?outputType=xml",
         "ABC Color", "Paraguay", "es",
         "the economy desk of a Paraguayan national daily, in Spanish"),
    Feed("biznis_rs", "https://biznis.rs/feed/",
         "Biznis.rs", "Serbia", "sr",
         "a Serbian business publication reporting in Serbian"),
    Feed("gestion_pe", "https://gestion.pe/arc/outboundfeeds/rss/"
                       "category/economia/?outputType=xml",
         "Gestion", "Peru", "es",
         "the economy desk of Peru's business daily, in Spanish"),
)
BY_KEY = {f.key: f for f in FEEDS}
COUNTRIES = tuple(dict.fromkeys(f.country for f in FEEDS))


def by_key(key):
    """The Feed record for a key, or None."""
    return BY_KEY.get(key)


#: The committed arming decision, priced from the live feeds on 2026-08-14 at
#: the measured news-path rate of $0.000315 per candidate.
#:
#:   14 feeds x MAX_PER_FEED 8 x 2 runs/day x 30 days x $0.000315 = $2.12/month
#:
#: That is the WORST case: it assumes every feed hits its cap on every run,
#: which requires eight fresh, never-before-seen collective-layoff stories per
#: feed per run. The realistic figure is far lower - seen_urls dedup makes a
#: repeated URL free forever, and the relevance filter passed 0 of the ~600
#: items on the wiring-day probe. $2.12 fits the discretionary room left after
#: the committed path ($4.92) and the local-news markets ($5.14) inside the
#: $14.00 allowance in railway/spend.py, and it is under the $4/month bar the
#: owner set for arming by default. So this ships ARMED.
#:
#: A policy lives in a diff, not in a dashboard env var nobody can review.
#: NATIONAL_FEEDS still overrides for a subset dry run; "off" disarms without
#: a deploy.
ARMED_BY_DEFAULT = "all"


def armed_feeds():
    """The Feed records this run is armed for. Empty tuple means DORMANT."""
    raw = (os.environ.get("NATIONAL_FEEDS") or "").strip()
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
        print(f"NATIONAL_FEEDS: ignoring unknown {unknown}; "
              f"known feeds are {sorted(BY_KEY)}")
    return tuple(dict.fromkeys(picked))


# ---------------------------------------------------------------------------
# RELEVANCE: the free cost gate, per language.
#
# English rides EN_TERMS / EN_PATTERNS / PAIRED_TERMS imported from
# regional_feeds, so the two collectors can never drift apart on what an
# English layoff headline looks like. The other three languages are defined
# here because these are the first feeds in the repo that publish in them.

# Spanish. Bare "despido" is the singular of an INDIVIDUAL dismissal and it is
# the vocabulary of employment-court stories, so it is excluded exactly as
# French "licenciement" is in regional_feeds. Plural and explicitly collective
# forms only.
ES_TERMS = (
    "despidos", "despido colectivo", "despidos colectivos", "despido masivo",
    "despidos masivos", "desvinculaciones", "recorte de personal",
    "recortes de personal", "reduccion de personal", "reducción de personal",
    "reduccion de plantilla", "reducción de plantilla", "cese colectivo",
    "ceses colectivos", "cierre de planta", "cierre de fabrica",
    "cierre de fábrica", "puestos de trabajo eliminados",
    "recorte de empleos", "expediente de regulacion de empleo",
    "expediente de regulación de empleo",
)
# Headlines interleave the figure with the noun ("despide a 250 trabajadores",
# "despidos de 300 empleados"), which plain substrings cannot see.
ES_PATTERNS = re.compile(
    r"(despid(?:e|en|ira|irá|iran|irán|io|ió)\s+a\s+(?:[\d][\d.,\s]*\s*)?"
    r"(?:trabajador|emplead|person)"
    r"|despidos?\s+de\s+(?:[\d][\d.,\s]*\s*)"
    r"(?:trabajador|emplead|person)"
    r"|recort(?:e|a|ara|ará|an)\s+(?:[\d][\d.,\s]*\s*)?(?:puestos|empleos))",
    re.I)

# Russian (Kursiv publishes in Russian). Bare "увольнения" is individual-firing
# vocabulary - the trap local_news measured on the RU edition - so the terms
# are the collective-reduction phrases only.
RU_TERMS = (
    "сокращение штата", "сокращения штата", "сокращение персонала",
    "сокращение сотрудников", "сокращает штат", "сокращает персонал",
    "сократит штат", "сократил штат", "сократит персонал",
    "массовое сокращение", "массовые сокращения", "сокращение рабочих мест",
    "оптимизация численности", "закрытие завода", "закрытие предприятия",
)
RU_PATTERNS = re.compile(
    r"сократ\w*\s+(?:[\d][\d\s.,]*\s*)?(?:сотрудник|работник|штат|персонал)",
    re.I)

# Serbian, in both scripts, because Serbian media publish in both and a feed
# mixes them freely. Bare "otkaz" is an individual dismissal, so it is only
# ever read paired with a workforce word (below).
SR_TERMS = (
    "отпуштање радника", "otpustanje radnika", "otpuštanje radnika",
    "вишак запослених", "visak zaposlenih", "višak zaposlenih",
    "смањење броја запослених", "smanjenje broja zaposlenih",
    "затварање фабрике", "zatvaranje fabrike", "остаје без посла",
    "ostaje bez posla", "колективно отпуштање", "kolektivno otpustanje",
    "kolektivno otpuštanje",
)
SR_PATTERNS = re.compile(
    r"(otpu(?:sta|šta|stila|štila|stili|štili)\s+(?:[\d][\d.\s]*\s*)?radnik"
    r"|отпу(?:шта|штила|штили)\s+(?:[\d][\d.\s]*\s*)?радник"
    r"|bez\s+posla\s+(?:ostaje|ostalo|ostace|ostaće)\s+(?:[\d][\d.\s]*\s*)?"
    r"(?:radnik|zaposlen))",
    re.I)

# Noisy homographs, kept only when paired with a workforce word, per language.
LANG_PAIRED = {
    "sr": (("otkaz", ("radnik", "radnicima", "zaposlen")),
           ("отказ", ("радник", "радницима", "запослен"))),
}

LANG_TERMS = {"en": EN_TERMS, "es": ES_TERMS, "ru": RU_TERMS, "sr": SR_TERMS}
LANG_PATTERNS = {"en": EN_PATTERNS, "es": ES_PATTERNS, "ru": RU_PATTERNS,
                 "sr": SR_PATTERNS}


def relevance(lang, title, snippet):
    """Free pre-LLM layoff filter for one language. Returns (keep, why).

    This decides what is ALLOWED to cost money; it never decides what is
    stored - the extractor still rules on every kept candidate.

    English is always ALSO checked, whatever the feed's language: these
    publishers quote wire copy and run English headlines inside non-English
    feeds, and reading a real layoff story is worth one extraction either way.
    """
    t = f"{title} {snippet}".lower()
    langs = ("en",) if lang == "en" else (lang, "en")
    for lg in langs:
        for term in LANG_TERMS.get(lg, ()):
            if term in t:
                return True, f"term:{lg}:{term}"
        pat = LANG_PATTERNS.get(lg)
        if pat is not None and pat.search(t):
            return True, f"pattern:{lg}"
        pairs = LANG_PAIRED.get(lg, ()) if lg != "en" else PAIRED_TERMS
        for term, partners in pairs:
            if term in t and any(p in t for p in partners):
                return True, f"paired:{lg}:{term}"
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
    """(items, is_feed) - the two-state view of the shared `parse_feed`, kept
    for callers that only need "could we read it?". The collector itself uses
    parse_feed, because a health note has to name WHICH failure this was."""
    items, shape, _detail = parse_feed(xml_text)
    return items, shape in ("ok", "repaired")


def build_raw(feed, item):
    """One feed item -> the standard raw dict, or None when filtered out.

    Mirrors sources/newsapi.py, local_news.py and regional_feeds.py exactly:
    raw_text is always set (the extractor reads ONLY that), no country is ever
    asserted, and the outlet note is a fact about the SOURCE, never about the
    event - a Ghanaian paper covering a Nigerian plant closure is Nigeria's.
    """
    link = _clean(item.get("link"))
    if not link:
        return None
    title = _clean(item.get("title"))
    desc = _clean(item.get("description"))
    content = _clean(item.get("content"))
    if is_aggregator(link, feed.outlet, title):
        return None
    keep, _why = relevance(feed.lang, title, f"{desc} {content}")
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


# ---------------------------------------------------------------------------
# A FEED WE CANNOT READ IS NOT A FEED THAT BROKE
#
# On 2026-08-18 the health page said "feed broke: economynext_lk: HTTP 202".
# Probed the same day from a laptop, all fifteen feeds answered HTTP 200 with a
# well-formed RSS document, economynext.com included, and its robots.txt
# permits us. A 202 carrying a non-feed body is the signature of a bot wall
# keyed on the datacentre's address range — the collector runs from Railway,
# not from a laptop — so nothing in this file was broken and nothing in it
# could be fixed to make that host answer.
#
# CORRECTLY LABELLED IS NOT COLLECTING, so the label was not the end of it.
# That feed is gone from FEEDS as of the same day, because the measurement
# above it shows the publisher already reaches us through the Sri Lanka market
# sweep; see "DROPPED AS REDUNDANT" in the module docstring. What is kept here
# is the CLASSIFIER, which is general: the next feed to hit an address-range
# wall must still be told apart from a feed whose URL we broke, and answering
# a wall by spoofing the client is not on the list of options.
#
# Three statuses in this set for the same reason: 403 (refused), 429 (throttled)
# and 503 (unavailable) are all "this host is not serving this network right
# now". 451 is legal geoblocking, which is the same fact with a different cause.
#
# What stays a BREAK, deliberately: 404 and 410 mean the document moved or was
# withdrawn and the URL in this file is now wrong, and a 200 whose body is not
# RSS means the publisher changed scheme. Both of those are ours to fix, and
# blurring them into "unreachable" would be exactly the silencing this is not.
UNREACHABLE_STATUSES = frozenset({202, 403, 429, 451, 503})


def classify_failure(status):
    """'unreachable' (nothing here to fix) or 'broke' (something here to fix)."""
    return "unreachable" if status in UNREACHABLE_STATUSES else "broke"


def health_verdict(failures):
    """(status, detail) for the source-health ledger, from the failure list.

    Never resolves a feed we could not read to `ok`: an unreadable feed is
    degraded, same as a broken one, because the health page must not claim a
    source is working when the collector cannot read it. Only the WORDING
    differs, and it has to, because "feed broke" sent a session to a parser
    that was working.
    """
    if not failures:
        return "ok", ""
    def _say(group):
        return ", ".join(f"{f['feed']}: {f['detail']}" for f in group)
    blocked = [f for f in failures if f["kind"] == "unreachable"]
    broken = [f for f in failures if f["kind"] == "broke"]
    parts = []
    if broken:
        parts.append("feed broke: " + _say(broken))
    if blocked:
        parts.append(
            f"{len(blocked)} feed(s) could not be READ from this network "
            f"(bot wall / throttle / geoblock — the publisher serves these "
            f"fine elsewhere, so there is no parser fault to fix): "
            + _say(blocked))
    return "degraded", "; ".join(parts)


def pull_national_feeds(feeds=None, fetch=None):
    """Return (rows, stats). Armed by default; NATIONAL_FEEDS=off disarms.

    `fetch` is injectable for tests: fetch(url, timeout) -> (status, text).
    Fail-loud: every failing feed is appended to pull_national_feeds.failures
    (with its kind, see `classify_failure`) so the caller degrades the source
    instead of masking a dead feed.

    `.failures` is a LIST because `.last_error` was one slot, overwritten per
    feed, so a sweep in which three feeds were blocked reported exactly one —
    and "is this an instance or a class?" is the first question anyone asks
    about a blocked host. `.last_error` is kept for compatibility and now
    summarises ALL of them rather than whichever happened to fail last.
    """
    pull_national_feeds.last_error = None
    pull_national_feeds.failures = []
    picked = tuple(feeds) if feeds else armed_feeds()
    stats = {f.key: {"fetched": 0, "aggregator": 0, "dropped": 0,
                     "kept": 0, "errors": 0, "repaired": 0} for f in picked}
    if not picked:
        print("national_feeds: DORMANT (NATIONAL_FEEDS=off, or the armed set "
              "is empty), so no request was made and nothing was spent. "
              "Known feeds: " + ", ".join(sorted(BY_KEY)))
        return [], stats

    def _default_fetch(url, timeout):
        import requests
        r = requests.get(url, headers=UA, timeout=timeout)
        return r.status_code, r.text
    do_fetch = fetch or _default_fetch

    def _fail(feed, kind, detail):
        stats[feed.key]["errors"] += 1
        pull_national_feeds.failures.append(
            {"feed": feed.key, "kind": kind, "detail": detail})
        pull_national_feeds.last_error = "; ".join(
            f"{f['feed']}: {f['detail']}" for f in pull_national_feeds.failures)

    rows, seen_links = [], set()
    for feed in picked:
        st = stats[feed.key]
        try:
            status, body = do_fetch(feed.url, feed.timeout)
        except Exception as e:
            # A transport error never reached the publisher at all, so it is
            # the purest case of unreachable.
            _fail(feed, "unreachable", f"{type(e).__name__}: {e}")
            time.sleep(GAP)
            continue
        if status != 200:
            _fail(feed, classify_failure(status), f"HTTP {status}")
            time.sleep(GAP)
            continue
        items, shape, detail = parse_feed(body)
        if shape == "not_feed":
            _fail(feed, "broke",
                  "200 but the body is not an RSS feed - scheme changed?")
            time.sleep(GAP)
            continue
        if shape == "malformed":
            # An RSS document we cannot read is the PUBLISHER's defect, and
            # saying "scheme changed" about it sends a session to rewrite a
            # URL that is correct. Named separately, and still an error.
            _fail(feed, "broke",
                  f"200 and the body IS an RSS document, but its XML is not "
                  f"well-formed and no bare-ampersand escape recovers it "
                  f"({detail})")
            time.sleep(GAP)
            continue
        if shape == "repaired":
            # Read, not silently: a feed whose only defect is an unescaped "&"
            # is collected (the alternative is losing a country over one
            # character) and counted, so the run report says so. It is NOT a
            # degrade - a permanently amber source is noise that hides the
            # real breakage this collector exists to report.
            st["repaired"] = st.get("repaired", 0) + 1
            print(f"national_feeds: {feed.key}: {detail}")
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
    #   NATIONAL_FEEDS=all python3 -m sources.national_feeds
    COST_PER_CANDIDATE_USD = 0.000315   # measured on the news path, 2026-08
    rows, stats = pull_national_feeds()
    for key in sorted(stats):
        st = stats[key]
        print(f"{key}: fetched={st['fetched']} kept={st['kept']} "
              f"dropped={st['dropped']} aggregator={st['aggregator']} "
              f"errors={st['errors']} repaired={st.get('repaired', 0)}")
    n = len(rows)
    print(f"candidates this run: {n} -> ${n * COST_PER_CANDIDATE_USD:.4f} "
          f"if every one were new (seen_urls dedup makes repeats free)")
    for r in rows:
        print(f"  [{r['_feed_key']}] {r['raw_text'][:120]}")
    if pull_national_feeds.last_error:
        print(f"last_error: {pull_national_feeds.last_error}")
        raise SystemExit(2)
