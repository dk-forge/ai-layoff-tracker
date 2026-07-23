"""Mazowieckie (Poland) collective-dismissal register — WUP Warszawa.

A 2026-07 survey of all 16 Polish voivodeship labour offices found exactly ONE
that publishes employer-NAMED collective-redundancy notifications (zwolnienia
grupowe): the Mazowieckie office (WUP Warszawa), via monthly press posts on its
"dla mediów" page. That makes Mazovia the third jurisdiction with a WARN-grade
public register we can read directly, after US states and Quebec. Mazowieckie
is Poland's largest regional labour market (~16-17% of national employment,
Warsaw-HQ heavy); the other 15 offices publish aggregates or nothing, so the
rest of Poland stays news-covered.

Format (verified on the live March-2026 post): a prose intro with aggregate
counts we IGNORE, then a per-company list whose items are regular:

    <Company Sp. z o.o./S.A.> – <industry>; <powiat>; ... zwolnienia objąć mają
    <N> osób ... do końca <month-genitive> <YYYY> r.

Items are anchored on the Polish legal-form suffix, so the parse is
DETERMINISTIC (no LLM) and routes through the same /bulk path as WARN and
Quebec, keeping the "structured registers are imported with no AI processing"
claim true. An item missing its legal form, count, or deadline is SKIPPED and
counted, never guessed (documented-floor rule).
"""
import hashlib
import html as _html
import re

import requests

LISTING_URL = "https://wupwarszawa.praca.gov.pl/urzad/dla-mediow"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 40

# Genitive month names as used in "do końca kwietnia 2026 r."
_MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
    "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9,
    "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}
_MONTH_DAYS = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
               7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}

# Company anchor: name ending in a Polish legal form, then an en/em dash.
_LEGAL = r"(?:Sp\.? ?z ?o\. ?o\.|S\.A\.|S\.K\.A\.|sp\. ?k\.|sp\. ?j\.|P\.S\.A\.)"
# Anchor = company name ending in a legal form, followed by a dash. Items are
# parsed by SLICING between consecutive anchors (bounded window after the last
# one), because a lazy-body lookahead silently dropped the FINAL item: the
# post's closing paragraphs sit between it and end-of-text, so neither "next
# anchor" nor "$" was reachable inside the window (caught by the ground-truth
# test: Bank Nowy S.A. missing).
_ANCHOR_RX = re.compile(
    r"(?P<name>[A-ZŻŹĆŁŚÓĘĄŃ][\w&.,'\-\" ]{1,70}?" + _LEGAL + r")\s*[–\-]\s*")
_COUNT_RX = re.compile(r"(\d[\d\s.]{0,6})\s*os[óo]b")
_DEADLINE_RX = re.compile(r"do końca (\w+) (\d{4})", re.I)


def _flat(html_text):
    txt = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html_text)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", _html.unescape(txt)).strip()


def _entry(company, jobs, date, industry_hint, post_url):
    company = re.sub(r"\s+", " ", (company or "")).strip(" ,;-")
    if not company or jobs <= 0 or jobs > 100000 or not date:
        return None
    if date < "2015-01-01" or date > "2028-12-31":
        return None
    is_closure = "likwidacj" in (industry_hint or "").lower()
    excerpt = (f"{'Closure' if is_closure else 'Collective dismissal'} notice at "
               f"{company}, Mazowieckie, Poland. {jobs:,} employees affected, to be "
               f"completed by {date}. Filed with the regional labour office (WUP "
               f"Warszawa) under Poland's collective-redundancy notification rules.")
    hash_input = f"warnplmz{company.lower().strip()}{date}{jobs}"
    return {
        "source_type": "warn",
        "source_name": "Mazowieckie collective-dismissal register (WUP Warszawa)",
        "verification_level": "warn",
        "company_name": company[:70],
        "ticker": None,
        "job_count": jobs,
        "layoff_date": date,
        "industry": None,
        "country": "Poland",
        "state": "",
        "roles": None,
        "excerpt": excerpt,
        "reason_tags": (["closure"] if is_closure else []),
        "ai_explicit": False,
        "ai_language": None,
        "source_url": post_url,
        "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
        "is_layoff_event": True,
    }


def _parse_post(flat_text, post_url):
    """Deterministic per-company parse; returns (entries, skipped)."""
    out, skipped = [], 0
    anchors = list(_ANCHOR_RX.finditer(flat_text))
    for i, m in enumerate(anchors):
        nxt = anchors[i + 1].start() if i + 1 < len(anchors) else len(flat_text)
        body = flat_text[m.end():min(nxt, m.end() + 500)]
        cm = _COUNT_RX.search(body)
        dm = _DEADLINE_RX.search(body)
        if not cm or not dm:
            skipped += 1
            continue
        try:
            jobs = int(re.sub(r"[\s.]", "", cm.group(1)))
        except ValueError:
            skipped += 1
            continue
        month = _MONTHS.get(dm.group(1).lower())
        if not month:
            skipped += 1
            continue
        year = int(dm.group(2))
        date = f"{year:04d}-{month:02d}-{_MONTH_DAYS[month]:02d}"
        e = _entry(m.group("name"), jobs, date, body[:120], post_url)
        if e:
            out.append(e)
        else:
            skipped += 1
    return out, skipped


def pull_wup_mazowieckie(max_posts=4):
    """Fetch recent register posts from the press listing and parse notices."""
    page = requests.get(LISTING_URL, headers=UA, timeout=TIMEOUT)
    page.raise_for_status()
    links = []
    for u, t in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page.text, re.S):
        title = re.sub(r"<[^>]+>", " ", t)
        if "zwolnienia grupowe" in title.lower() and u.startswith("http"):
            if u not in links:
                links.append(u)
    out, seen, total_skipped = [], set(), 0
    for url in links[:max_posts]:
        try:
            post = requests.get(url, headers=UA, timeout=TIMEOUT)
            if post.status_code != 200:
                continue
            entries, skipped = _parse_post(_flat(post.text), url)
            total_skipped += skipped
            for e in entries:
                if e["dedup_hash"] not in seen:
                    seen.add(e["dedup_hash"])
                    out.append(e)
        except requests.RequestException as exc:
            print(f"    WUP Mazowieckie: post fetch failed ({exc})")
    if total_skipped:
        print(f"    WUP Mazowieckie: {total_skipped} item(s) skipped (no legal-form "
              f"anchor / count / deadline) — never guessed")
    return out
