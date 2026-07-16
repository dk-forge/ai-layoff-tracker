"""
Pulls AI-related layoff coverage from GDELT — a free, keyless, global news index
(2017→present). GDELT returns article metadata (url/title/domain/date); we fetch
each article and extract the layoff details downstream via the same extractor.

This is the historical + global press layer: free, worldwide, back to 2024,
and it's where AI-attributed layoff language actually appears.
"""
import html
import re
import time
from datetime import timezone

import requests

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT space = AND, OR must be explicit. ALL layoffs, not only AI-related —
# the extractor tags ai_explicit itself, so an AI clause here was pure
# coverage loss (Europe/world general layoffs never entered the pipeline).
# "redundancies" catches UK/Commonwealth English. GDELT Translingual machine-
# translates 65 languages into English before indexing, so these English
# keywords match Le Monde / Handelsblatt / NRC / Gazeta coverage too.
QUERY = '(layoffs OR "job cuts" OR "cutting jobs" OR "lays off" OR redundancies OR "job losses" OR "workforce reduction")'

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
    "cbc.ca", "globalnews.ca", "smh.com.au", "abc.net.au", "irishtimes.com",
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
}

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

REQUEST_DELAY = 1.2       # GDELT asks for gentle use
RAW_TEXT_LIMIT = 3000
MAX_DOC_BYTES = 400_000


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
    for kw in ("laid off", "layoff", "job cuts", "cutting jobs", "reduction in force"):
        idx = lowered.find(kw)
        if idx != -1:
            start = max(0, idx - 400)
            return text[start:start + RAW_TEXT_LIMIT]
    return text[:RAW_TEXT_LIMIT]


def pull_gdelt_between(start, end, max_records=250):
    """Return raw layoff-news entries (trusted domains) filed in [start, end]."""
    params = {
        "query": QUERY,
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
    # GDELT throttles aggressively on historical sweeps — back off and retry
    # instead of surrendering the whole month window (a 72-window backfill
    # once lost 63 windows to 429s without this).
    articles = None
    for attempt in range(5):
        time.sleep(REQUEST_DELAY if attempt == 0 else 45 * attempt)
        try:
            resp = requests.get(GDELT_URL, params=params,
                                headers={"User-Agent": BROWSER_UA}, timeout=30)
            if resp.status_code == 429:
                print(f"GDELT 429 (attempt {attempt + 1}/5), backing off")
                continue
            resp.raise_for_status()
            articles = resp.json().get("articles", []) or []
            break
        except Exception as e:
            print(f"GDELT query error (attempt {attempt + 1}/5): {e}")
    if articles is None:
        print("GDELT window abandoned after 5 attempts")
        return []

    results, seen = [], set()
    for a in articles:
        url = a.get("url")
        dom = _domain(a)
        if not url or url in seen or not _is_trusted(dom):
            continue
        seen.add(url)
        try:
            time.sleep(0.2)
            text = _fetch_article(url)
        except Exception as e:
            print(f"GDELT fetch error {url}: {e}")
            continue
        if not text.strip():
            continue
        results.append({
            "source_type": "news",
            "source_name": dom,
            "verification_level": "bronze",
            "raw_text": f"{a.get('title', '')} {text}",
            "source_url": url,
            "company_name": None,
            "ticker": None,
            "filing_date": _seen_to_iso(a.get("seendate")),
        })

    print(f"GDELT: {len(articles)} matched, {len(results)} from trusted domains")
    return results
