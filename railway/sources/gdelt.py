"""
Pulls AI-related layoff coverage from GDELT — a free, keyless, global news index
(2017→present). GDELT returns article metadata (url/title/domain/date); we fetch
each article and extract the layoff details downstream via the same extractor.

This is the historical + global press layer: free, worldwide, back to 2024,
and it's where AI-attributed layoff language actually appears.
"""
import html
import os
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

from source_registry import discovery_terms

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT space = AND, OR must be explicit. ALL layoffs, not only AI-related —
# the extractor tags ai_explicit itself, so an AI clause here was pure
# coverage loss (Europe/world general layoffs never entered the pipeline).
# "redundancies" catches UK/Commonwealth English. GDELT Translingual machine-
# translates 65 languages into English before indexing, so these English
# keywords match Le Monde / Handelsblatt / NRC / Gazeta coverage too.
# Keep the retrieval vocabulary in the source registry rather than in an LLM
# prompt.  This makes coverage reviewable, testable, and expandable by market.
QUERY = "(" + " OR ".join(
    f'"{term}"' if " " in term else term for term in discovery_terms()
) + ")"

TRUSTED_DOMAINS = {
    # wires / national general
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "cnn.com", "nytimes.com",
    "washingtonpost.com", "latimes.com", "usatoday.com", "npr.org", "abcnews.go.com",
    "nbcnews.com", "cbsnews.com", "politico.com", "thehill.com", "axios.com",
    "theguardian.com", "independent.co.uk", "telegraph.co.uk", "foxbusiness.com",
    "foxnews.com", "aljazeera.com", "semafor.com",
    # business / finance
    "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "forbes.com", "fortune.com",
    "businessinsider.com", "businessinsider.in", "marketwatch.com", "barrons.com",
    "morningstar.com", "thestreet.com", "benzinga.com", "fastcompany.com", "inc.com",
    "hbr.org", "qz.com", "sherwood.news", "economist.com", "financialpost.com",
    # tech / trade
    "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com", "engadget.com",
    "zdnet.com", "venturebeat.com", "theregister.com", "gizmodo.com", "mashable.com",
    "digitaltrends.com", "theinformation.com", "restofworld.org", "9to5google.com",
    # regional US
    "sfgate.com", "sfchronicle.com", "mercurynews.com", "seattletimes.com",
    "chicagotribune.com", "bostonglobe.com", "dallasnews.com", "denverpost.com",
    # international (English)
    "dw.com", "france24.com", "scmp.com", "japantimes.co.jp", "straitstimes.com",
    "cbc.ca", "globalnews.ca",
    # Canada — was thin (only CBC + Global News + Financial Post), which
    # under-covered a country with no WARN/SEC/ERM equivalent. Added the
    # papers of record + national business/tech outlets.
    "theglobeandmail.com", "nationalpost.com", "thestar.com", "ctvnews.ca",
    "bnnbloomberg.ca", "montrealgazette.com", "torontosun.com", "betakit.com",
    "smh.com.au", "abc.net.au", "irishtimes.com",
    "business-standard.com", "moneycontrol.com", "ndtv.com", "ndtvprofit.com",
    "livemint.com", "hindustantimes.com", "thehindu.com",
    "timesofindia.indiatimes.com", "economictimes.indiatimes.com",
    # international (non-English majors — the extractor reads any language)
    "lemonde.fr", "lesechos.fr", "lefigaro.fr",              # France
    "handelsblatt.com", "spiegel.de", "faz.net", "zeit.de",  # Germany
    "elpais.com", "expansion.com",                            # Spain
    "corriere.it", "ilsole24ore.com",                         # Italy
    "nikkei.com", "asahi.com",                                # Japan
    "chosun.com", "hankyung.com",                             # South Korea
    "globo.com", "estadao.com.br", "folha.uol.com.br",       # Brazil
    "eleconomista.com.mx", "clarin.com",                      # Mexico / Argentina
    "nrc.nl", "volkskrant.nl",                                # Netherlands
    # --- Regional expansion: reputable national business/news outlets, added
    # to widen country coverage (a layoff only enters the tracker if a trusted
    # outlet covers it, so this list IS the reach lever). English editions
    # preferred; GDELT machine-translates the rest.
    "haaretz.com", "timesofisrael.com", "calcalistech.com",   # Israel
    "thenationalnews.com", "gulfnews.com", "khaleejtimes.com", "arabnews.com",  # Gulf
    "hurriyetdailynews.com", "dailysabah.com",                # Turkey
    "news24.com", "businesslive.co.za", "iol.co.za", "moneyweb.co.za",  # South Africa
    "premiumtimesng.com", "punchng.com",                      # Nigeria
    "nation.africa", "businessdailyafrica.com",               # Kenya
    "ahram.org.eg",                                            # Egypt
    "thejakartapost.com", "kompas.com",                       # Indonesia
    "bangkokpost.com", "nationthailand.com",                  # Thailand
    "vnexpress.net", "vietnamnews.vn",                        # Vietnam
    "thestar.com.my", "nst.com.my",                           # Malaysia
    "inquirer.net", "rappler.com", "philstar.com",            # Philippines
    "taipeitimes.com", "focustaiwan.tw",                      # Taiwan
    "koreaherald.com", "koreatimes.co.kr",                    # South Korea (English)
    "themoscowtimes.com", "kyivindependent.com",              # Russia / Ukraine
    "notesfrompoland.com",                                    # Poland (English)
    "thelocal.se", "thelocal.de", "thelocal.fr",             # Nordics / EU (English)
    "helsinkitimes.fi",                                       # Finland
    "swissinfo.ch",                                           # Switzerland
    "nzherald.co.nz", "rnz.co.nz",                            # New Zealand
    "eltiempo.com", "portafolio.co",                          # Colombia
    "df.cl",                                                   # Chile
    "elcomercio.pe",                                          # Peru
    # --- Deep coverage for the markets most likely to cite this tracker:
    # USA, Canada, UK/Europe, Australia. Papers of record + national business.
    "afr.com", "theaustralian.com.au", "news.com.au", "theage.com.au",  # Australia
    "9news.com.au", "skynews.com.au", "watoday.com.au", "brisbanetimes.com.au",
    "thetimes.co.uk", "news.sky.com", "standard.co.uk", "cityam.com",   # UK
    "euronews.com", "politico.eu", "euractiv.com",            # EU-wide
    "liberation.fr", "lexpress.fr",                           # France
    "sueddeutsche.de", "welt.de", "tagesschau.de",            # Germany
    "elmundo.es", "lavanguardia.com",                         # Spain
    "repubblica.it", "lastampa.it",                           # Italy
    "fd.nl",                                                   # Netherlands (business)
    "lesoir.be", "standaard.be",                              # Belgium
    "dn.se", "svd.se",                                        # Sweden
    "aftenposten.no", "e24.no",                              # Norway
    "politiken.dk", "borsen.dk",                             # Denmark
    "hs.fi",                                                  # Finland
    "nzz.ch", "letemps.ch",                                  # Switzerland
    "derstandard.at", "diepresse.com",                       # Austria
    "independent.ie", "rte.ie", "thejournal.ie",             # Ireland
    "expresso.pt", "publico.pt",                             # Portugal
    "startribune.com", "chron.com", "miamiherald.com",       # more US regionals
    "cnbc.com", "thehill.com",                               # (dupes are harmless; set dedups)
    # --- 2026-07 four-region research sweep (docs/COUNTRY_SOURCE_RESEARCH_2026_07.md
    # §3, "Newspapers-only fallback by country"): per-country papers of record and
    # business dailies. Allowlist-only — these mark articles as trusted when they
    # surface via GDELT/NewsAPI; we never scrape these sites directly.
    "latribune.fr",                                           # France
    "di.se",                                                  # Sweden
    "berlingske.dk",                                          # Denmark
    "dn.no",                                                  # Norway
    "kauppalehti.fi",                                         # Finland
    "pb.pl", "rp.pl",                                         # Poland
    "handelszeitung.ch",                                      # Switzerland
    "jornaldenegocios.pt", "eco.sapo.pt",                     # Portugal
    "elfinanciero.com.mx",                                    # Mexico
    "ambito.com", "cronista.com",                             # Argentina
    "latercera.com",                                          # Chile (Pulso)
    "larepublica.co",                                         # Colombia
    "hket.com",                                               # Hong Kong
    "businessdesk.co.nz",                                     # New Zealand
    "bisnis.com", "kontan.co.id",                             # Indonesia
    "theedgemalaysia.com",                                    # Malaysia
    "bworldonline.com",                                       # Philippines
    "vneconomy.vn",                                           # Vietnam
    "bangkokbiznews.com",                                     # Thailand (Krungthep Turakij)
    "globes.co.il",                                           # Israel
    "dunya.com",                                              # Turkey
    "argaam.com",                                             # Saudi Arabia
    "businessday.ng", "nairametrics.com",                     # Nigeria
    "dailynewsegypt.com",                                     # Egypt
    "kommersant.ru", "rbc.ru", "thebell.io",                  # Russia
    "epravda.com.ua",                                         # Ukraine
    # --- 2026-07-18 Challenger gap-closure R4 (docs/CHALLENGER_GAP_CLOSURE_PLAN.md):
    # reviewed US trade/regional outlets that carried missed-event coverage.
    # Healthcare trade press is the motivating sector (Challenger Jan
    # healthcare 17,107 vs ~400 in named events). xtalks.com was reviewed and
    # rejected (marketing/webinar site, not a newsroom).
    "healthcaredive.com", "fiercepharma.com",                 # healthcare trade
    "paymentsdive.com",                                       # fintech trade
    # --- 2026-07 US metro/city business press sweep: metro outlets report
    # local layoffs before national press. Allowlist-only (GDELT/NewsAPI
    # surface articles; never crawl). Paywalled entries follow the existing
    # wsj/ft posture; bot-blocked fetches drop out harmlessly.
    "bizjournals.com",            # ACBJ network — one domain, 44 metro Business Journals
    "chicagobusiness.com",        # Crain's Chicago Business
    "crainsnewyork.com",          # Crain's New York Business
    "crainsdetroit.com",          # Crain's Detroit Business (auto belt)
    "crainscleveland.com",        # Crain's Cleveland Business (healthcare/mfg)
    "crainsgrandrapids.com",      # Crain's Grand Rapids (W. Michigan mfg)
    "ajc.com",                    # Atlanta Journal-Constitution
    "inquirer.com",               # Philadelphia Inquirer
    "oregonlive.com",             # The Oregonian — Portland (Intel/Nike)
    "tampabay.com",               # Tampa Bay Times
    "post-gazette.com",           # Pittsburgh Post-Gazette
    "stltoday.com",               # St. Louis Post-Dispatch
    "azcentral.com",              # Arizona Republic — Phoenix (chips)
    "cleveland.com",              # Plain Dealer / Advance
    "freep.com", "detroitnews.com",  # Detroit dailies (auto layoffs)
    "jsonline.com",               # Milwaukee Journal Sentinel
    "dispatch.com",               # Columbus Dispatch (Intel Ohio)
    "tennessean.com",             # Nashville (healthcare HQs)
    "charlotteobserver.com",      # Charlotte (banking)
    "houstonchronicle.com",       # paywalled sibling of chron.com
    "statesman.com",              # Austin (Tesla/Oracle/Dell metro)
    "sandiegouniontribune.com",   # San Diego (biotech/defense)
    "sltrib.com",                 # Salt Lake Tribune (Silicon Slopes)
    "thebaltimorebanner.com",     # Baltimore Banner
    "reviewjournal.com",          # Las Vegas R-J (hospitality)
    "ibj.com",                    # Indianapolis Business Journal
    "geekwire.com",               # Seattle tech — breaks Amazon/Microsoft cuts early
    "marketplace.org",            # APM Marketplace
    "kuow.org",                   # Seattle NPR (Boeing/Amazon/Microsoft)
    "wbur.org",                   # Boston NPR (biotech)
    "kqed.org",                   # SF Bay NPR (tech)
    "techrepublic.com", "electrek.co", "gamedeveloper.com",   # tech/EV/games trade
    "chicago.suntimes.com",                                   # Chicago daily
    "wral.com",                                               # Raleigh NC (WRAL TechWire)
    "mprnews.org",                                            # Minnesota Public Radio
    "boston.com",                                             # Boston Globe Media
    "sanantonioreport.org",                                   # San Antonio nonprofit newsroom
    "fox5vegas.com",                                          # Las Vegas TV news
    "westfaironline.com",                                     # Westchester/Fairfield business
    "kvrr.com", "wwnytv.com",                                 # Fargo / Watertown TV news
    "recorder.com",                                           # Greenfield Recorder (MA)
}

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

REQUEST_DELAY = 5.0       # GDELT asks for gentle use; 429s under load, so pace well below the shared limit
RAW_TEXT_LIMIT = 3000
MAX_DOC_BYTES = 400_000
FETCH_WORKERS = max(1, min(6, int(os.environ.get("GDELT_FETCH_WORKERS", "4"))))
# Five patient attempts with a longer base backoff: a rate-limited shared API
# rewards waiting, and the cursor design means an abandoned window is retried
# next run anyway — so patience here converts "degraded" runs into "ok" runs
# without any extra request volume.
QUERY_ATTEMPTS = max(1, min(6, int(os.environ.get("GDELT_QUERY_ATTEMPTS", "5"))))
QUERY_BACKOFF_SECONDS = max(1, min(120, int(os.environ.get("GDELT_QUERY_BACKOFF_SECONDS", "40"))))


def _retry_delay(response, attempt):
    """Honor a bounded Retry-After hint, with jitter for shared API fairness."""
    hinted = 0
    try:
        hinted = int((response.headers.get("Retry-After") or "").strip()) if response else 0
    except (AttributeError, TypeError, ValueError):
        hinted = 0
    return min(180, max(QUERY_BACKOFF_SECONDS * (attempt + 1), hinted)) + random.uniform(0, 3)


def _strip_html(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _domain(a):
    d = (a.get("domain") or "").lower()
    return d[4:] if d.startswith("www.") else d


def _is_trusted(dom):
    return any(dom == d or dom.endswith("." + d) for d in TRUSTED_DOMAINS)


def _seen_to_iso(seendate):
    s = re.sub(r"[^0-9]", "", seendate or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else ""


def _fetch_article(url):
    """Fetch an article and return a text window centered on the layoff mention."""
    resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=25)
    resp.raise_for_status()
    text = _strip_html(resp.text[:MAX_DOC_BYTES])
    lowered = text.lower()
    for kw in discovery_terms():
        idx = lowered.find(kw)
        if idx != -1:
            start = max(0, idx - 400)
            return text[start:start + RAW_TEXT_LIMIT]
    return text[:RAW_TEXT_LIMIT]


# Segmented recall sweeps: a broad "layoffs" query ranks global mega-stories
# first, so smaller country/state/industry announcements can fall below the
# maxrecords cutoff and never enter the pipeline. Each run therefore ALSO
# runs a few narrow queries chosen by deterministic daily rotation, so the
# whole matrix is covered every ~6 days at twice-daily cadence without
# increasing per-run volume beyond a handful of extra requests. Expand the
# matrix freely — rotation, not volume, absorbs growth.
SEGMENT_TERMS = (
    # US states with the highest layoff volume
    '"California"', '"New York"', '"Texas"', '"Washington"', '"Florida"',
    '"Illinois"', '"Massachusetts"', '"Georgia"', '"Michigan"', '"Ohio"',
    '"Pennsylvania"', '"New Jersey"',
    # countries (Translingual matches non-English coverage too)
    '"Germany"', '"France"', '"United Kingdom"', '"Canada"', '"India"',
    '"Japan"', '"Brazil"', '"Spain"', '"Italy"', '"Netherlands"',
    '"Sweden"', '"South Korea"', '"Singapore"', '"Israel"', '"Mexico"',
    '"Poland"', '"Switzerland"', '"Ireland"', '"Australia"',
    # industries
    '"manufacturing"', '"software"', '"banking"', '"retail"',
    '"healthcare"', '"automotive"', '"media"', '"logistics"',
    '"pharmaceutical"', '"insurance"', '"telecom"', '"aerospace"',
    # AI-attribution phrasings the broad vocabulary can rank too low
    '"AI layoffs"', '"replaced by AI"', '"because of AI"',
    '"artificial intelligence" "job cuts"', '"automation" "restructuring"',
)
SEGMENT_QUERIES_PER_RUN = max(0, min(8, int(os.environ.get("GDELT_SEGMENT_QUERIES", "4"))))


def _segment_queries_for_now():
    """Deterministic daily rotation over the segment matrix (0 disables)."""
    if not SEGMENT_QUERIES_PER_RUN:
        return []
    now = datetime.now(timezone.utc)
    run_of_day = 0 if now.hour < 17 else 1  # the two Railway cron slots
    start_idx = ((now.timetuple().tm_yday * 2 + run_of_day) * SEGMENT_QUERIES_PER_RUN) % len(SEGMENT_TERMS)
    picked = [SEGMENT_TERMS[(start_idx + i) % len(SEGMENT_TERMS)] for i in range(SEGMENT_QUERIES_PER_RUN)]
    return [f"{QUERY} {term}" for term in picked]


def _query_window(query, start, end, max_records):
    """One GDELT ArtList query with patient 429 backoff.

    Returns (articles, saw_rate_limit, last_error); articles is None when the
    window was abandoned after all attempts.
    """
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sortby": "datedesc",
        # No sourcelang restriction: the trusted-domain list is the quality
        # gate, and it now includes major non-English outlets (Le Monde,
        # Handelsblatt, Nikkei, Globo...). The extractor reads any language.
        "startdatetime": start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
    }
    articles = None
    last_error = None
    saw_rate_limit = False
    delay = REQUEST_DELAY
    for attempt in range(QUERY_ATTEMPTS):
        time.sleep(delay)
        try:
            resp = requests.get(GDELT_URL, params=params,
                                headers={"User-Agent": BROWSER_UA}, timeout=30)
            if resp.status_code == 429:
                saw_rate_limit = True
                last_error = "HTTP 429"
                delay = _retry_delay(resp, attempt)
                print(f"GDELT 429 (attempt {attempt + 1}/{QUERY_ATTEMPTS}), retrying after {delay:.0f}s")
                continue
            resp.raise_for_status()
            articles = resp.json().get("articles", []) or []
            break
        except Exception as e:
            last_error = str(e)
            print(f"GDELT query error (attempt {attempt + 1}/{QUERY_ATTEMPTS}): {e}")
    return articles, saw_rate_limit, last_error


def pull_gdelt_between(start, end, max_records=250):
    """Return raw layoff-news entries (trusted domains) filed in [start, end]."""
    # GDELT throttles aggressively on historical sweeps — back off and retry
    # instead of surrendering the whole month window (a 72-window backfill
    # once lost 63 windows to 429s without this).
    articles, saw_rate_limit, last_error = _query_window(QUERY, start, end, max_records)
    if articles is None:
        # A 429 followed by a malformed/empty upstream response is still an
        # upstream availability incident. Preserve the 429 marker so the
        # caller leaves the cursor in place and reports the source as
        # deferred, rather than classifying the final parser symptom as a
        # repository failure.
        if saw_rate_limit:
            last_error = f"HTTP 429 (followed by upstream response error: {last_error or 'unknown error'})"
        raise RuntimeError(f"GDELT window abandoned after {QUERY_ATTEMPTS} attempts: {last_error or 'unknown error'}")

    # Rotating narrow sweeps ride the same window. Only the broad query is
    # health-bearing: a segment that stays rate-limited is skipped with a log
    # line and rotates back around within days, so it must not fail the run.
    for segment_query in _segment_queries_for_now():
        seg_articles, _, seg_error = _query_window(segment_query, start, end, max_records)
        if seg_articles is None:
            print(f"GDELT segment skipped ({seg_error}): {segment_query[-60:]}")
            continue
        print(f"GDELT segment {segment_query[-48:]}: {len(seg_articles)} article(s)")
        articles.extend(seg_articles)

    candidates, seen = [], set()
    for a in articles:
        url = a.get("url")
        dom = _domain(a)
        if not url or url in seen or not _is_trusted(dom):
            continue
        seen.add(url)
        candidates.append((a, url, dom))

    def fetch_candidate(candidate):
        a, url, dom = candidate
        try:
            # Gentle staggering plus a small worker pool prevents one slow or
            # dead publisher from serially blocking an entire global window.
            time.sleep(0.2)
            text = _fetch_article(url)
        except Exception as e:
            print(f"GDELT fetch error {url}: {e}")
            return None
        if not text.strip():
            return None
        return {
            "source_type": "news",
            "source_name": dom,
            "verification_level": "bronze",
            "raw_text": f"{a.get('title', '')} {text}",
            "source_url": url,
            "company_name": None,
            "ticker": None,
            "filing_date": _seen_to_iso(a.get("seendate")),
        }

    results = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = [pool.submit(fetch_candidate, candidate) for candidate in candidates]
        for future in as_completed(futures):
            entry = future.result()
            if entry:
                results.append(entry)

    print(f"GDELT: {len(articles)} matched, {len(candidates)} trusted, {len(results)} fetched")
    return results
