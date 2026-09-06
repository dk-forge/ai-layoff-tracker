"""City recall sweep: "if you searched 'layoffs' plus every major city, would we find them?"

WHAT THIS IS. A third reference universe for the recall machinery in
`tracker_diff` and `curated_probe`, and like those two it is a PROBE, never a
source. The learning loop reads GDELT before our allowlist; the curated probe
reads what the owner pastes. This one reads the Google News RSS index for
"layoffs" plus each of the world's largest metropolitan areas, in the country's
own edition and, where `sources/native_layoff_terms` has a vocabulary for the
language, in the country's own words. A city name is the one query dimension
neither of the other two universes ever varies, and it is the one a reader
varies first ("layoffs Chicago").

WHAT IT COSTS. Nothing. One RSS index request per (city, language), spaced
`GAP_SECONDS` apart, plus reads of our OWN public `/query`, memoised per
employer token. No model is called on any path (no OpenRouter key is read or
in scope, so there is nothing for `spend.metered_call` to meter). No article
page is ever fetched: outlet identity comes from the index's own `<source>`
element, so no publisher robots.txt, paywall or bot wall is engaged. The
`tests/test_city_recall_sweep.py` pin proves no request is built from an
item's link.

JUDGEMENT IS IMPORTED, NEVER COPIED. `headline_jobs`, `headline_employer_token`,
`rows_verdict`, `vocab_hit`, `vocab_phrase` and `_covered_by_allowlist` are
`tracker_diff`'s, so "did we hold this?" keeps one definition across all three
probes. What this file adds on top is honestly labelled: a native-language
headcount pattern (the imported one reads English nouns only) and a second
employer candidate for headlines that do not open with the employer, both of
which are counted separately in the summary so a native-language verdict is
never mistaken for the English-grade one.

TWO SINKS, BY SHAPE. stdout carries COUNTS ONLY: per country (ISO2) and per
city (an index into the committed CITIES table), through `assert_nameless`, an
allowlist that cannot spell a headline, an employer or an outlet. Every name
goes to ONE gitignored file under `scratchpad/`, in the curated probe's
worklist format so the owner can paste the misses straight into
`recall-worklist.txt`. There is deliberately no workflow for this script: a
runner that can write the named file is the leak.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import requests  # noqa: E402

from curated_probe import registrable_domain  # noqa: E402
from sources.google_news import (  # noqa: E402
    GOOGLE_NEWS_LOCALES, UA as GN_UA, _clean, _iso_date, _parse_items, _rss_url,
)
from sources.google_news_url import resolve as resolve_article_url  # noqa: E402
from sources.native_layoff_terms import PHRASES_BY_LANG, language_of_hl  # noqa: E402
from tracker_diff import (  # noqa: E402
    _TITLE_STOP,
    _covered_by_allowlist,
    headline_employer_token,
    headline_jobs,
    rows_verdict,
    vocab_hit,
    vocab_phrase,
)

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
REPO = pathlib.Path(__file__).resolve().parent.parent
GAP_SECONDS = max(1.0, float(os.environ.get("CITY_SWEEP_GAP_SECONDS", "5")))
WINDOW_DAYS = max(1, min(30, int(os.environ.get("CITY_SWEEP_WINDOW_DAYS", "14"))))
METHOD = "x1"

# ---------------------------------------------------------------------------
# THE CITIES. The 120 largest metropolitan areas by population, in the order
# of the UN World Urbanization Prospects agglomeration table (2018 revision,
# the latest public one), trimmed of two that no news edition reaches in any
# language (Sana'a, Mogadishu) and topped up from the same table. Native name is given where the LOCAL press writes the city in a
# non-Latin script or under a different Latin name; it is the string put to
# the native-language edition. English-press countries carry no native name.
# (english, native or "", ISO2)
CITIES = (
    ("Tokyo", "東京", "JP"), ("Delhi", "", "IN"), ("Shanghai", "上海", "CN"),
    ("Sao Paulo", "São Paulo", "BR"), ("Mexico City", "Ciudad de México", "MX"),
    ("Cairo", "القاهرة", "EG"), ("Mumbai", "", "IN"), ("Beijing", "北京", "CN"),
    ("Dhaka", "", "BD"), ("Osaka", "大阪", "JP"), ("New York", "", "US"),
    ("Karachi", "", "PK"), ("Chongqing", "重庆", "CN"), ("Istanbul", "İstanbul", "TR"),
    ("Buenos Aires", "", "AR"), ("Kolkata", "", "IN"), ("Lagos", "", "NG"),
    ("Kinshasa", "", "CD"), ("Manila", "", "PH"), ("Tianjin", "天津", "CN"),
    ("Guangzhou", "广州", "CN"), ("Rio de Janeiro", "", "BR"), ("Lahore", "", "PK"),
    ("Bengaluru", "", "IN"), ("Shenzhen", "深圳", "CN"), ("Moscow", "Москва", "RU"),
    ("Chennai", "", "IN"), ("Bogota", "Bogotá", "CO"), ("Paris", "", "FR"),
    ("Jakarta", "", "ID"), ("Lima", "", "PE"), ("Bangkok", "กรุงเทพ", "TH"),
    ("Hyderabad", "", "IN"), ("Seoul", "서울", "KR"), ("Nagoya", "名古屋", "JP"),
    ("London", "", "GB"), ("Chengdu", "成都", "CN"), ("Tehran", "تهران", "IR"),
    ("Nanjing", "南京", "CN"), ("Ho Chi Minh City", "TP.HCM", "VN"),
    ("Luanda", "", "AO"), ("Wuhan", "武汉", "CN"), ("Xi'an", "西安", "CN"),
    ("Ahmedabad", "", "IN"), ("Kuala Lumpur", "", "MY"), ("Hangzhou", "杭州", "CN"),
    ("Surat", "", "IN"), ("Suzhou", "苏州", "CN"), ("Hong Kong", "香港", "HK"),
    ("Riyadh", "الرياض", "SA"), ("Shenyang", "沈阳", "CN"), ("Baghdad", "بغداد", "IQ"),
    ("Dar es Salaam", "", "TZ"),
    ("Pune", "", "IN"), ("Santiago", "", "CL"), ("Madrid", "", "ES"),
    ("Toronto", "", "CA"), ("Belo Horizonte", "", "BR"),
    ("Khartoum", "الخرطوم", "SD"), ("Johannesburg", "", "ZA"), ("Singapore", "", "SG"),
    ("Dalian", "大连", "CN"), ("Qingdao", "青岛", "CN"), ("Zhengzhou", "郑州", "CN"),
    ("Jinan", "济南", "CN"), ("Barcelona", "", "ES"),
    ("Saint Petersburg", "Санкт-Петербург", "RU"), ("Abidjan", "", "CI"),
    ("Yangon", "", "MM"), ("Fukuoka", "福岡", "JP"), ("Alexandria", "الإسكندرية", "EG"),
    ("Guadalajara", "", "MX"), ("Ankara", "", "TR"), ("Chittagong", "", "BD"),
    ("Addis Ababa", "", "ET"), ("Melbourne", "", "AU"), ("Nairobi", "", "KE"),
    ("Hanoi", "Hà Nội", "VN"), ("Sydney", "", "AU"), ("Monterrey", "", "MX"),
    ("Changsha", "长沙", "CN"), ("Brasilia", "Brasília", "BR"), ("Cape Town", "", "ZA"),
    ("Jeddah", "جدة", "SA"), ("Taipei", "台北", "TW"), ("Tel Aviv", "", "IL"), ("Kano", "", "NG"), ("Montreal", "Montréal", "CA"), ("Recife", "", "BR"), ("Los Angeles", "", "US"),
    ("Berlin", "", "DE"), ("Milan", "Milano", "IT"), ("Rome", "Roma", "IT"),
    ("Chicago", "", "US"), ("Busan", "부산", "KR"), ("Kabul", "", "AF"),
    ("Casablanca", "الدار البيضاء", "MA"), ("Fortaleza", "", "BR"), ("Salvador", "", "BR"),
    ("Kuwait City", "الكويت", "KW"), ("Dubai", "دبي", "AE"), ("Houston", "", "US"),
    ("Dallas", "", "US"), ("Athens", "Αθήνα", "GR"), ("Lisbon", "Lisboa", "PT"),
    ("Manchester", "", "GB"), ("Amman", "عمان", "JO"), ("Medellin", "Medellín", "CO"),
    ("Kyiv", "Київ", "UA"), ("Warsaw", "Warszawa", "PL"), ("Ruhr", "Ruhrgebiet", "DE"),
    ("Miami", "", "US"), ("Philadelphia", "", "US"), ("Washington", "", "US"),
    ("Atlanta", "", "US"), ("Boston", "", "US"), ("Phoenix", "", "US"),
    ("San Francisco", "", "US"), ("Surabaya", "", "ID"), ("Guayaquil", "", "EC"),
)

# Editions for countries the collector does not rotate. Same shape as a
# GOOGLE_NEWS_LOCALES row minus the code: (hl, gl, ceid). A country with no
# row here and no collector row is asked on the worldwide English edition, and
# the summary counts how many cities that fallback covered, because "we asked
# the world feed" is a weaker read than "we asked that country's own press".
EXTRA_EDITIONS = {
    "CN": ("zh-CN", "CN", "CN:zh-Hans"),
    "EG": ("ar", "EG", "EG:ar"),
    "SA": ("ar", "SA", "SA:ar"),
    "LB": ("ar", "LB", "LB:ar"),
    "RU": ("ru", "RU", "RU:ru"),
    "PK": ("en-PK", "PK", "PK:en"),
    "PE": ("es-419", "PE", "PE:es-419"),
    "EC": ("es-419", "PE", "PE:es-419"),
    "SN": ("fr", "SN", "SN:fr"),
    "CD": ("fr", "SN", "SN:fr"),
    "CI": ("fr", "SN", "SN:fr"),
    "MA": ("fr", "MA", "MA:fr"),
    "ET": ("en-ET", "ET", "ET:en"),
    "TZ": ("en-TZ", "TZ", "TZ:en"),
    "GH": ("en-GH", "GH", "GH:en"),
    "UA": ("uk", "UA", "UA:uk"),
    "GR": ("el", "GR", "GR:el"),
    "BD": ("bn", "BD", "BD:bn"),
    "IQ": ("ar", "AE", "AE:ar"),
    "KW": ("ar", "AE", "AE:ar"),
    "JO": ("ar", "AE", "AE:ar"),
    "SD": ("ar", "EG", "EG:ar"),
    "IR": ("en-US", "US", "US:en"),
    "AF": ("en-US", "US", "US:en"),
    "AO": ("pt-PT", "PT", "PT:pt-150"),
    "MM": ("en-US", "US", "US:en"),
}
WORLD_EDITION = ("en-US", "US", "US:en")
# Bilingual English-language business press on Arabic editions; ask both.
ENGLISH_ALSO = {"AE": ("en-AE", "AE", "AE:en"), "SA": ("en-AE", "AE", "AE:en"),
                "KW": ("en-AE", "AE", "AE:en"), "EG": ("en-US", "US", "US:en"),
                "JO": ("en-AE", "AE", "AE:en"), "IQ": ("en-AE", "AE", "AE:en"),
                "IL": None, "CN": ("en-US", "US", "US:en"),
                "HK": ("en-US", "US", "US:en"), "TW": ("en-US", "US", "US:en"),
                "JP": ("en-US", "US", "US:en"), "KR": ("en-US", "US", "US:en")}

_LOCALE_BY_CODE = {row[0]: (row[1], row[2], row[3]) for row in GOOGLE_NEWS_LOCALES}


def edition_for(iso2):
    """(hl, gl, ceid) for a country, and whether it was the world fallback."""
    if iso2 in _LOCALE_BY_CODE:
        return _LOCALE_BY_CODE[iso2], False
    if iso2 in EXTRA_EDITIONS:
        ed = EXTRA_EDITIONS[iso2]
        return ed, ed == WORLD_EDITION
    return WORLD_EDITION, True


def queries_for_city(city):
    """[(query, (hl, gl, ceid), language)] for one CITIES row.

    An English query always, on the country's English edition where it has one
    (else the world edition); a native query when the edition's language has a
    vocabulary in `native_layoff_terms`, phrased the way the collector phrases
    it: the language's phrases OR'd, plus the city in its own script."""
    english, native, iso2 = city
    ed, _fallback = edition_for(iso2)
    lang = language_of_hl(ed[0])
    when = f"when:{WINDOW_DAYS}d"
    out = []
    if lang == "en":
        out.append((f'layoffs "{english}" {when}', ed, "en"))
    else:
        eng_ed = ENGLISH_ALSO.get(iso2, WORLD_EDITION)
        if eng_ed:
            out.append((f'layoffs "{english}" {when}', eng_ed, "en"))
        phrases = PHRASES_BY_LANG.get(lang, ())
        if phrases:
            local = native or english
            terms = " OR ".join(f'"{p}"' for p in phrases[:4])
            out.append((f'({terms}) "{local}" {when}', ed, lang))
    return out


# ---------------------------------------------------------------------------
# NATIVE-LANGUAGE HEADCOUNT. `tracker_diff.headline_jobs` reads English nouns
# ("500 jobs", "cut 1,200"). A Handelsblatt headline says "1.200 Stellen", a
# Nikkei one "1万人". This pattern is the honest extension, and every verdict it
# enables is counted under `native_parsed` rather than folded into the
# English-grade number.
_NATIVE_NOUNS = (
    r"Stellen|Arbeitspl[äa]tze|Mitarbeiter(?:innen)?|Besch[äa]ftigte|Jobs|"
    r"postes|emplois|salari[ée]s|employ[ée]s|"
    r"empleos|puestos|trabajadores|empleados|despidos|"
    r"vagas|funcion[áa]rios|empregos|demiss[õo]es|trabalhadores|"
    r"posti|dipendenti|esuberi|lavoratori|"
    r"banen|medewerkers|arbeidsplaatsen|"
    r"etat[óo]w|pracownik[óo]w|miejsc pracy|"
    r"tj[äa]nster|anst[äa]llda|jobb|stillinger|ansatte|job|"
    r"ty[öo]paikkaa|ty[öo]ntekij[äa][äa]|henkil[öo][äa]|"
    r"[çc]alı[şs]an(?:ı|ın)?|ki[şs]i|i[şs][çc]i|"
    r"сотрудник(?:ов|а)?|рабочих мест|человек|работник(?:ов|а)?|"
    r"موظف(?:ا|ين)?|عامل(?:ا|ين)?|وظيفة|وظائف|"
    r"คน|ตำแหน่ง|nh[âa]n vi[êe]n|lao [đd][ộo]ng|ng[ưu][ờo]i"
)
_NATIVE_HEADCOUNT_RX = re.compile(
    r"(?<![\d.,%])(\d{1,3}(?:[.,  ]\d{3})+|\d{2,6})\s*(?:[a-zà-ÿ]{1,12}\s+)?(?:" + _NATIVE_NOUNS + r")\b",
    re.I | re.U)
_CJK_HEADCOUNT_RX = re.compile(r"(?<![\d.,%])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(万|萬)?\s*(?:人|名|명|個崗位|个岗位|个职位)")


def native_headline_jobs(title, floor=25):
    """A headcount from a non-English headline, or None. First number only."""
    t = str(title or "")
    m = _CJK_HEADCOUNT_RX.search(t)
    if m:
        try:
            n = float(m.group(1).replace(",", ""))
            if m.group(2):
                n *= 10000
            n = int(n)
            return n if n >= floor else None
        except ValueError:
            pass
    m = _NATIVE_HEADCOUNT_RX.search(t)
    if m:
        try:
            n = int(re.sub(r"[.,  ]", "", m.group(1)))
        except ValueError:
            return None
        return n if n >= floor else None
    return None


def employer_candidates(title, city_words, vocab_words):
    """Up to two employer tokens: the imported heuristic's first, then the next
    capitalised run that is neither the city, a vocabulary word nor a stop word.
    German capitalises every noun, so the second candidate is what makes
    "Stellenabbau bei Bosch" resolvable at all. Never more than two: each is a
    read of our own API and the point is a bound, not a search."""
    out = []
    first = headline_employer_token(title)
    skip = {w.lower() for w in city_words} | {w.lower() for w in vocab_words} | _TITLE_STOP
    if first and first.lower() not in skip:
        out.append(first)
    head = re.split(r"\s+[-–|]\s+", str(title or ""))[0]
    for word in re.split(r"[^\w&.'’-]+", head, flags=re.U):
        clean = word.strip(".'’-")
        if len(clean) < 3 or clean.lower() in skip or not clean[0].isupper():
            continue
        if clean not in out:
            out.append(clean)
        if len(out) >= 2:
            break
    return out


# OUR OWN HOST IS A REFUSAL WE CAN MEET, AND A SWEEP MUST STOP AT IT RATHER
# THAN WALK 120 CITIES INTO IT. On 2026-09-06 this run met a site-wide HTTP 409
# bot challenge on `/blog` (every route, not only `/query`). Without a breaker
# the sweep would have made several hundred more reads into that wall and
# reported 120 cities of UNKNOWN as if it had looked. It had not. So:
# consecutive failed reads trip `HostBreaker`, the run stops asking, and the
# summary says `host unreachable`: UNKNOWN is recorded as UNKNOWN and is
# never rounded to a miss or to a pass.
HOST_FAIL_LIMIT = max(2, int(os.environ.get("CITY_SWEEP_HOST_FAIL_LIMIT", "5")))
HOST_GAP_SECONDS = max(0.0, float(os.environ.get("CITY_SWEEP_HOST_GAP_SECONDS", "1")))


class HostBreaker:
    """Consecutive-failure breaker over reads of our OWN /query."""

    def __init__(self, limit=None):
        self.limit = limit or HOST_FAIL_LIMIT
        self.consecutive = 0
        self.tripped = False

    def record(self, ok):
        if ok:
            self.consecutive = 0
            return
        self.consecutive += 1
        if self.consecutive >= self.limit:
            self.tripped = True


def our_rows(token, site, timeout=30, cache=None, breaker=None, sleep=time.sleep):
    """Rows we hold for a token, or None when the read could not be made
    (UNKNOWN, never a miss). Memoised per token: one read per employer, paced
    by `HOST_GAP_SECONDS`, and skipped entirely once the breaker has tripped."""
    if cache is not None and token in cache:
        return cache[token]
    if breaker is not None and breaker.tripped:
        return None
    # A BREAKER MEASURES REQUESTS, NOT INTENTIONS. When no request is
    # attempted -- `--index-only` passes an empty site, and a headline with no
    # employer candidate passes an empty token -- there is nothing to record.
    # Counting those as failures tripped the breaker on the very first item of
    # an index-only run, so that run reported `host_unreachable True` and
    # printed "our own /query stopped answering mid-run" having never asked it
    # anything (2026-09-06). An UNKNOWN with no request behind it must not be
    # dressed up as an outage.
    if not site or not token:
        return None
    rows = None
    try:
        r = requests.get(f"{site}/wp-json/layoffs/v1/query",
                         params={"company": token, "per_page": 50},
                         headers=UA, timeout=timeout)
        if r.status_code == 200:
            rows = r.json().get("data") or []
    except Exception:
        rows = None
    if HOST_GAP_SECONDS:
        sleep(HOST_GAP_SECONDS)
    if breaker is not None:
        breaker.record(rows is not None)
    if cache is not None and rows is not None:
        cache[token] = rows
    return rows


# ---------------------------------------------------------------------------
# PUBLIC SINK. Same construction as tracker_diff.assert_nameless: an allowlist
# of what stdout may carry. Keys by shape (an ISO2, a city index `c001`), values
# numbers, ISO dates and frozen label words. A headline, an employer or an
# outlet cannot be spelled with it.
class LeakGuard(RuntimeError):
    """Raised when a value that could carry a name reaches a public sink."""


VERDICTS = ("held", "missed", "unknown")
TIERS = ("not_in_feed_set", "vocabulary_gap", "residual")
_PUBLIC_WORDS = frozenset(VERDICTS) | frozenset(TIERS) | frozenset({
    "city", "ok", "index_error", "world_edition", "native", METHOD,
})
_PUBLIC_KEYS = frozenset(VERDICTS) | frozenset(TIERS) | frozenset({
    "date", "method", "window_days", "cities", "queries", "index_errors",
    "world_edition_cities", "items", "with_headcount", "native_parsed",
    "host_unreachable", "index_reused", "outlet_unwired", "vocab_unmatched",
    "judged", "by_country", "by_city", "held_pct", "miss_tiers", "no_results",
})
_ISO2_RX = re.compile(r"^[A-Z]{2}$")
_CITY_KEY_RX = re.compile(r"^c\d{3}$")
_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def assert_nameless(obj, path="root"):
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        if obj in _PUBLIC_WORDS or _DATE_RX.match(obj):
            return obj
        raise LeakGuard(f"{path}: refusing to publish free text")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not (k in _PUBLIC_KEYS or _ISO2_RX.match(str(k)) or _CITY_KEY_RX.match(str(k))):
                raise LeakGuard(f"{path}.{k}: key is not a declared public field")
            assert_nameless(v, f"{path}.{k}")
        return obj
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            assert_nameless(v, f"{path}[{i}]")
        return obj
    raise LeakGuard(f"{path}: unsupported type {type(obj).__name__}")


def public_render(facts):
    assert_nameless(facts)
    lines = []
    for key in sorted(facts):
        val = facts[key]
        if isinstance(val, dict) and val and all(isinstance(v, dict) for v in val.values()):
            for sub in sorted(val):
                inner = ", ".join(f"{k} {val[sub][k]}" for k in sorted(val[sub]))
                lines.append(f"  {key}.{sub}: {inner}")
        elif isinstance(val, dict):
            lines.append(f"  {key}: " + ", ".join(f"{k} {val[k]}" for k in sorted(val)))
        else:
            lines.append(f"  {key} {val}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------

def judge_item(item, city, lang, site, trusted, discovery, native_vocab, cache,
               breaker=None, sleep=time.sleep):
    """One headline -> a PRIVATE record {verdict, tier, jobs, native, ...}.

    Pure given `cache` pre-filled (tests) or `site` (live)."""
    title = _clean(item.get("title"))
    jobs = headline_jobs(title)
    native = False
    if jobs is None and lang != "en":
        jobs = native_headline_jobs(title)
        native = jobs is not None
    if jobs is None:
        return None
    english, native_name, iso2 = city
    city_words = set(english.split()) | set((native_name or "").split())
    when = None
    stamp = _iso_date(item.get("published"))
    if stamp:
        try:
            y, m, d = (int(x) for x in stamp.split("-"))
            when = date(y, m, d)
        except ValueError:
            when = None
    verdict, tokens = "unknown", employer_candidates(title, city_words, list(discovery) + list(native_vocab))
    if not tokens:
        verdict = "unknown"
    else:
        verdicts = []
        for tok in tokens:
            rows = our_rows(tok, site, cache=cache, breaker=breaker, sleep=sleep)
            if rows is None:
                verdicts.append("unknown")
                continue
            verdicts.append(rows_verdict(rows, jobs, when))
        if "match" in verdicts:
            verdict = "held"
        elif "unknown" in verdicts:
            verdict = "unknown"
        else:
            verdict = "missed"
    # NET COVERAGE IS A FACT ABOUT US, NOT ABOUT THIS VERDICT, so it is
    # computed for every judged headline and not only for the misses. "This
    # outlet is not in our allowlist" and "no discovery term matches this
    # wording" stay true whether or not we happened to hold the row through
    # another outlet, and they are the two findings this sweep exists to
    # produce. They also survive our own host being unreachable, which is why
    # they are separated: on 2026-09-06 the first full run met a site-wide 409
    # and every verdict was UNKNOWN, while the coverage question was answerable
    # the whole time.
    domain = registrable_domain(item.get("source_home") or "")
    unwired = bool(domain) and not _covered_by_allowlist(domain, trusted)
    unmatched = not vocab_hit(title, list(discovery) + list(native_vocab))
    tier = None
    if verdict == "missed":
        if unwired:
            tier = "not_in_feed_set"
        elif unmatched:
            tier = "vocabulary_gap"
        else:
            tier = "residual"
    cite, _state = resolve_article_url(item.get("link") or "")
    origin = cite if "news.google.com" not in (cite or "") else (item.get("source_home") or "")
    return {"title": title, "jobs": jobs, "native": native, "when": stamp,
            "verdict": verdict, "tier": tier, "domain": domain,
            "unwired": unwired, "unmatched": unmatched,
            "outlet": (item.get("source") or "").strip(), "origin": origin,
            "tokens": tokens,
            "phrase": vocab_phrase(title) if unmatched else ""}


def _bucket():
    return {"items": 0, "judged": 0, "held": 0, "missed": 0, "unknown": 0,
            "not_in_feed_set": 0, "vocabulary_gap": 0, "residual": 0,
            "native_parsed": 0, "index_errors": 0,
            "outlet_unwired": 0, "vocab_unmatched": 0}


def _tally(bucket, rec):
    bucket["judged"] += 1
    bucket[rec["verdict"]] += 1
    if rec["native"]:
        bucket["native_parsed"] += 1
    if rec["unwired"]:
        bucket["outlet_unwired"] += 1
    if rec["unmatched"]:
        bucket["vocab_unmatched"] += 1
    if rec["tier"]:
        bucket[rec["tier"]] += 1


# ---------------------------------------------------------------------------
# THE INDEX HALF IS THE EXPENSIVE HALF AND IT MUST SURVIVE THE HOST HALF
# FAILING. A full sweep is ~190 index reads and ~300 reads of our own /query,
# and only the second kind can meet a bot challenge on `/blog`. On 2026-09-06
# it did: the host went to HTTP 409 mid-run, every verdict became UNKNOWN, and
# the only way to get the answer back was to walk all ~190 index reads a second
# time to reach the reads that had actually failed. That is 190 requests spent
# re-learning something we already knew, at a moment when the correct response
# to a challenged host is to make FEWER requests, not more.
#
# So the index is memoised to a file, keyed by (query, edition) and stamped
# with the window it was gathered for. A re-run reads it and spends its whole
# request budget on the half that failed. The file carries HEADLINES, so it is
# a name-bearing sink: it lives under `scratchpad/` (gitignored) with the named
# worklist, never in the repo, and it is never the default -- an unasked-for
# cache is a stale answer waiting to be believed.
def load_index_cache(path):
    """Cached index items keyed 'query\x00hl\x00gl\x00ceid', or {} when the
    file is absent, unreadable, or was gathered for a different window."""
    if not path:
        return {}
    try:
        blob = json.loads(pathlib.Path(path).read_text())
    except Exception:
        return {}
    if not isinstance(blob, dict) or blob.get("window_days") != WINDOW_DAYS:
        return {}
    entries = blob.get("entries")
    return entries if isinstance(entries, dict) else {}


def save_index_cache(path, entries):
    if not path:
        return
    try:
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text(json.dumps(
            {"window_days": WINDOW_DAYS, "method": METHOD,
             "saved": datetime.now(timezone.utc).date().isoformat(),
             "entries": entries}))
    except Exception:
        pass


def cache_key(query, ed):
    return "\x00".join([query, ed[0], ed[1], ed[2]])


def fetch_index(query, ed, timeout=30):
    """One RSS index read. Returns (items, error) where error is '' or a
    short transport label. Never raises."""
    try:
        r = requests.get(_rss_url(query, ed[0], ed[1], ed[2]), headers=GN_UA, timeout=timeout)
    except Exception as e:
        return [], type(e).__name__
    if r.status_code != 200:
        return [], f"HTTP {r.status_code}"
    return _parse_items(r.text), ""


def run(site, out_path, fetch=fetch_index, sleep=time.sleep, cities=CITIES, today=None,
        index_cache_path=None):
    today = today or date.today()
    index_cache = load_index_cache(index_cache_path)
    index_hits = 0
    from sources.gdelt import TRUSTED_DOMAINS
    from source_registry import discovery_terms
    trusted = {d.lower() for d in TRUSTED_DOMAINS}
    discovery = discovery_terms()
    native_vocab = [p for phrases in PHRASES_BY_LANG.values() for p in phrases]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).date().isoformat()

    facts = {"date": today.isoformat(), "method": METHOD, "window_days": WINDOW_DAYS,
             "cities": len(cities), "queries": 0, "index_errors": 0,
             "world_edition_cities": 0, "no_results": 0, "items": 0,
             "with_headcount": 0, "native_parsed": 0, "judged": 0,
             "held": 0, "missed": 0, "unknown": 0,
             "outlet_unwired": 0, "vocab_unmatched": 0,
             "miss_tiers": {t: 0 for t in TIERS},
             "host_unreachable": False, "index_reused": 0,
             "by_country": {}, "by_city": {}}
    breaker = HostBreaker()
    named = []          # the PRIVATE list: every judged record, with its city
    errors = []         # (city index, query language, label) for the named file
    cache = {}
    seen_titles = set()

    for idx, city in enumerate(cities):
        key = f"c{idx + 1:03d}"
        iso2 = city[2]
        _ed, fallback = edition_for(iso2)
        if fallback:
            facts["world_edition_cities"] += 1
        cb = facts["by_city"].setdefault(key, _bucket())
        kb = facts["by_country"].setdefault(iso2, _bucket())
        for q, ed, lang in queries_for_city(city):
            facts["queries"] += 1
            ck = cache_key(q, ed)
            if ck in index_cache:
                items, err = index_cache[ck], ""
                index_hits += 1
            else:
                items, err = fetch(q, ed)
                sleep(GAP_SECONDS)
                if not err:
                    index_cache[ck] = items
            if err:
                facts["index_errors"] += 1
                cb["index_errors"] += 1
                kb["index_errors"] += 1
                errors.append((key, lang, err))
                continue
            if not items:
                facts["no_results"] += 1
            for it in items:
                title = _clean(it.get("title"))
                tkey = re.sub(r"[^\w]+", " ", title.lower(), flags=re.U).strip()[:120]
                if not tkey or tkey in seen_titles:
                    continue
                seen_titles.add(tkey)
                stamp = _iso_date(it.get("published"))
                if stamp and stamp < cutoff:
                    continue
                facts["items"] += 1
                cb["items"] += 1
                kb["items"] += 1
                rec = judge_item(it, city, lang, site, trusted, discovery,
                                 native_vocab, cache, breaker=breaker, sleep=sleep)
                if rec is None:
                    continue
                facts["with_headcount"] += 1
                rec["city"] = city[0]
                rec["iso2"] = iso2
                rec["lang"] = lang
                named.append(rec)
                _tally(cb, rec)
                _tally(kb, rec)
                facts["judged"] += 1
                facts[rec["verdict"]] += 1
                if rec["native"]:
                    facts["native_parsed"] += 1
                if rec["unwired"]:
                    facts["outlet_unwired"] += 1
                if rec["unmatched"]:
                    facts["vocab_unmatched"] += 1
                if rec["tier"]:
                    facts["miss_tiers"][rec["tier"]] += 1

    save_index_cache(index_cache_path, index_cache)
    facts["index_reused"] = index_hits
    facts["host_unreachable"] = bool(breaker.tripped)
    decided = facts["held"] + facts["missed"]
    facts["held_pct"] = round(100.0 * facts["held"] / decided, 1) if decided else None
    # Drop empty per-city rows so the summary stays readable; the country
    # table keeps every country so an absent edition reads as zero, not gone.
    facts["by_city"] = {k: v for k, v in facts["by_city"].items() if v["items"]}

    write_named(out_path, named, errors, facts, cities)
    print("city-recall-sweep:")
    print(public_render(facts))
    if breaker.tripped:
        print("city-recall-sweep: our own /query stopped answering mid-run. Every "
              "verdict after that point is UNKNOWN, not a miss and not a pass, and "
              "this run's recall figure is NOT comparable with a complete one. "
              "Triage the host first (ops_status [1]), then re-run.")
    return facts, named


def write_named(out_path, named, errors, facts, cities):
    """The ONE named sink. Curated-worklist format for the misses so the owner
    can paste them straight in, then the diagnosis. Comment lines never carry a
    dotted token: `curated_probe.parse_worklist` suppresses every domain a `#`
    line names, so an outlet in a comment would silently exempt itself."""
    def undot(text):
        return re.sub(r"(?<=\w)\.(?=\w)", " ", str(text or ""))
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# city recall sweep {facts['date']} (window {facts['window_days']} days)",
             "# Section 1 is paste-ready for the curated worklist (misses only).",
             "# Sections 2 and 3 are diagnosis and are NOT worklist lines.",
             ""]
    misses = [r for r in named if r["verdict"] == "missed"]
    for r in misses:
        lines.append(f"{r['title']} {r['origin']}".strip())
    lines += ["", "# ---- 2. diagnosis per miss (city / language / tier / outlet / tokens tried) ----"]
    for r in misses:
        lines.append(f"#   {r['city']} [{r['iso2']}/{r['lang']}] {r['tier']} "
                     f"jobs={r['jobs']}{' native' if r['native'] else ''} "
                     f"outlet={undot(r['outlet']) or '?'} host={undot(r['domain']) or '?'} "
                     f"tokens={'|'.join(r['tokens'])}"
                     + (f" phrase={r['phrase']}" if r["phrase"] else ""))
    lines += ["", "# ---- 3. net coverage over EVERY judged headline "
              "(true regardless of the verdict) ----"]
    for r in named:
        if not (r["unwired"] or r["unmatched"]):
            continue
        flags = " ".join(f for f, on in (("outlet_unwired", r["unwired"]),
                                         ("vocab_unmatched", r["unmatched"])) if on)
        lines.append(f"#   {r['city']} [{r['iso2']}/{r['lang']}] {flags} "
                     f"verdict={r['verdict']} outlet={undot(r['outlet']) or '?'} "
                     f"host={undot(r['domain']) or '?'}"
                     + (f" phrase={r['phrase']}" if r["phrase"] else ""))

    lines += ["", "# ---- 4. held and unknown (for the record) ----"]
    for r in named:
        if r["verdict"] == "missed":
            continue
        lines.append(f"#   {r['verdict']:7} {r['city']} [{r['iso2']}/{r['lang']}] "
                     f"jobs={r['jobs']} tokens={'|'.join(r['tokens'])} :: {undot(r['title'])}")
    if errors:
        lines += ["", "# ---- 5. index errors ----"]
        for key, lang, label in errors:
            lines.append(f"#   {key} {cities[int(key[1:]) - 1][0]} {lang}: {label}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None,
                    help="named worklist path (default scratchpad/city-recall-<date>.txt)")
    ap.add_argument("--limit", type=int, default=0, help="first N cities only (smoke test)")
    ap.add_argument("--index-only", action="store_true",
                    help="read the news index and report NET COVERAGE only. Makes no "
                         "request to our own host, so every verdict is UNKNOWN by "
                         "construction and is reported as UNKNOWN. Use when the host "
                         "is unreachable (ops_status [1]): the outlet and vocabulary "
                         "findings do not depend on it.")
    ap.add_argument("--index-cache", default=None,
                    help="memoise the news index to this file and reuse it on a re-run. "
                         "The file carries HEADLINES, so it must live under scratchpad/ "
                         "(gitignored). Use it when a run may have to be repeated: the "
                         "index half costs ~190 requests and does not need re-reading "
                         "just because our own host stopped answering.")
    args = ap.parse_args(argv)
    site = "" if args.index_only else os.environ.get("WP_SITE_URL", "").rstrip("/")
    if args.index_only:
        print("city-recall-sweep: INDEX ONLY. No request is made to our own host, so "
              "held/missed is UNKNOWN by construction; only the outlet and "
              "vocabulary coverage figures are measured.")
    elif not site:
        print("city-recall-sweep: WP_SITE_URL is not set; every verdict would be UNKNOWN. Refusing.")
        return 2
    today = date.today()
    out = args.out or (REPO / "scratchpad" / f"city-recall-{today.isoformat()}.txt")
    cities = CITIES[:args.limit] if args.limit else CITIES
    run(site, out, cities=cities, today=today, index_cache_path=args.index_cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
