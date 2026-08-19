"""Mazowieckie (Poland) collective-dismissal register — WUP Warszawa.

A 2026-07 survey of all 16 Polish voivodeship labour offices found exactly ONE
that publishes employer-NAMED collective-redundancy notifications (zwolnienia
grupowe): the Mazowieckie office (WUP Warszawa), via monthly press posts on its
"dla mediów" page. That makes Mazovia the third jurisdiction with a WARN-grade
public register we can read directly, after US states and Quebec. Mazowieckie
is Poland's largest regional labour market (~16-17% of national employment,
Warsaw-HQ heavy); the other 15 offices publish aggregates or nothing, so the
rest of Poland stays news-covered.

Format (verified on the live February, March and June 2026 posts): a prose intro
with aggregate counts, then a per-company list whose items are regular:

    <Company Sp. z o.o./S.A.> – <industry>; <powiat>; ... zwolnienia objąć mają
    <N> osób ... do końca <month-genitive> <YYYY> r.

Items are anchored on the Polish legal-form suffix, or on the list item's own
"<Name> - <lowercase industry>;" shape when an employer carries no legal form,
so the parse is DETERMINISTIC (no LLM) and routes through the same /bulk path as
WARN and Quebec, keeping the "structured registers are imported with no AI
processing" claim true. An item missing its count or deadline is SKIPPED and
counted, never guessed (documented-floor rule).

REGULAR IS NOT UNIFORM, and assuming it was cost this register two thirds of
itself. Read on 2026-08-18, the collector was returning three of the eleven
notices its own listing page was serving: the office writes the legal form in
both cases, dates a completion three different ways, and does not always give an
employer a legal form at all. Every one of those returned a green health line.
So the run now audits itself against the total each post states for ITSELF (see
`_declared_total`), which is the only number in the document that can say a
parse was thin. Do not answer a shortfall there by relaxing an anchor.

The intro's OTHER number is not ours. "W czerwcu 2026 r. pracę na Mazowszu
straciło 280 osób" counts dismissals actually carried out that month, from
notices filed earlier; the register rows are the newly notified INTENTIONS, and
the two are different quantities in the same paragraph.
"""
import calendar
import hashlib
import html as _html
import re

import requests

LISTING_URL = "https://wupwarszawa.praca.gov.pl/urzad/dla-mediow"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 40

# Genitive month names as used in "do końca kwietnia 2026 r." and in the dated
# form "do 31 lipca 2026 r.".
_MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
    "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9,
    "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}
# NOMINATIVE month names, used only by the month-RANGE form ("proces
# zaplanowano na czerwiec-lipiec 2026 r."). A separate map on purpose: the two
# cases are different words in Polish, and folding them into one dictionary
# would let a genitive pattern match a nominative phrase it was never meant to.
_MONTHS_NOM = {
    "styczeń": 1, "styczen": 1, "luty": 2, "marzec": 3, "kwiecień": 4,
    "kwiecien": 4, "maj": 5, "czerwiec": 6, "lipiec": 7, "sierpień": 8,
    "sierpien": 8, "wrzesień": 9, "wrzesien": 9, "październik": 10,
    "pazdziernik": 10, "listopad": 11, "grudzień": 12, "grudzien": 12,
}

# Company anchor: name ending in a Polish legal form, then an en/em dash.
#
# THE LEGAL FORM IS MATCHED CASE-INSENSITIVELY, and that one letter cost a whole
# month. The office writes the same form both ways -- "Sp. z o.o." in the March
# post, "sp. z o.o." in the February one -- and a capital-S-only pattern found
# ZERO anchors in February, so four named employers and 164 jobs were absent
# from the register with nothing on any surface to say so. A parse that returns
# nothing for a post that lists four companies is not a quiet month.
_LEGAL = r"(?i:Sp\.? ?z ?o\. ?o\.|S\.A\.|S\.K\.A\.|sp\. ?k\.|sp\. ?j\.|P\.S\.A\.)"
# Anchor = company name ending in a legal form, followed by a dash. Items are
# parsed by SLICING between consecutive anchors (bounded window after the last
# one), because a lazy-body lookahead silently dropped the FINAL item: the
# post's closing paragraphs sit between it and end-of-text, so neither "next
# anchor" nor "$" was reachable inside the window (caught by the ground-truth
# test: Bank Nowy S.A. missing).
_ANCHOR_RX = re.compile(
    r"(?P<name>[A-ZŻŹĆŁŚÓĘĄŃ][\w&.,'\-\" ]{1,70}?" + _LEGAL + r")\s*[–—]\s*")

# SECOND anchor, for an employer with NO legal-form suffix. The June 2026 post
# leads with "Firma Budowlana ANNA-BUD" -- 76 people, the largest notice in that
# month -- and the legal-form rule cannot see it at all. Worse than a skip: with
# no anchor there is nothing to count, so the item was missing from the rows AND
# from the skipped tally, which is the one number that was supposed to reveal it.
#
# The list item's real shape is "<Name> - <lowercase industry>; ...", so this
# matches a capitalised, DOT-FREE name of at most six tokens followed by a
# spaced en/em dash and a lowercase word. Dot-free is what keeps the two anchors
# from fighting: every legal form contains dots, so a name with one belongs to
# _ANCHOR_RX and its boundary rules, not to this.
_GENERAL_ANCHOR_RX = re.compile(
    r"(?:^|(?<=[:;,.]\s))(?P<name>[A-ZŻŹĆŁŚÓĘĄŃ][^\s.;:,–—]*"
    r"(?:\s+[^\s.;:,–—]+){0,5})\s+[–—]\s+(?=[a-ząćęłńóśźż])")
# Prose the general anchor must never read as a company. The March post says
# "Zwolnienia bedą realizowane etapowo - do konca kwietnia, lipca lub wrzesnia
# 2026 r., w zaleznosci od firmy:", which is capitalised, dot-free, four tokens
# and sits in front of a real count and a real deadline. Without this list it
# posts as an employer named after a sentence fragment. A name containing any of
# these is prose; it is SKIPPED and counted, never guessed at.
_PROSE_TOKENS = frozenset("""
    będą bedą będzie bedzie mają maja ma są sa jest zostaną zostana zostały
    zostaly realizowane przeprowadzone złożyły zlozyly zgłosiły zglosily
    oraz lub przez dla tych ich się sie nie może moze do na w z i o od po przy
    że ze który ktory które ktore łącznie lacznie wszystkie
""".split())
_COUNT_RX = re.compile(r"(\d[\d\s.]{0,6})\s*os[óo]b")
# THREE deadline forms, because the office uses all three and the register lost
# a month to that. Until 2026-08-18 only the first was read, so the June 2026
# post parsed zero of its four notices -- every one of them phrased its date as
# an explicit day or a month range.
#   1. "przeprowadzone zostaną do końca lipca 2026 r."   -> end of that month
#   2. "planowany termin do 31 lipca 2026 r."            -> that exact day
#   3. "proces zaplanowano na czerwiec-lipiec 2026 r."   -> end of the LAST month
# Form 2 requires the literal "do" so that a FILING date cannot be mistaken for
# a completion date: the June post's Bank Nowy item reads "zgłoszenie z 5 marca
# 2026 r. obejmuje zwolnienie 3 osób, proces rozłożony do 30 września 2026 r.",
# and the deadline is the September one.
_DEADLINE_END_OF_MONTH_RX = re.compile(r"do końca (\w+) (\d{4})", re.I)
_DEADLINE_DATED_RX = re.compile(r"do (\d{1,2}) (\w+) (\d{4})", re.I)
_DEADLINE_RANGE_RX = re.compile(r"na (\w+)\s*[–—-]\s*(\w+) (\d{4})", re.I)


def _end_of_month(year, month):
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def _deadline(body):
    """The date the notified dismissals are to be completed by, or None.

    Never guesses: a body whose phrasing matches none of the three documented
    forms returns None and the item is skipped and counted.
    """
    m = _DEADLINE_END_OF_MONTH_RX.search(body)
    if m:
        month = _MONTHS.get(m.group(1).lower())
        if month:
            return _end_of_month(int(m.group(2)), month)
    m = _DEADLINE_DATED_RX.search(body)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month:
            day = int(m.group(1))
            year = int(m.group(3))
            if 1 <= day <= calendar.monthrange(year, month)[1]:
                return f"{year:04d}-{month:02d}-{day:02d}"
    m = _DEADLINE_RANGE_RX.search(body)
    if m:
        # A range runs to the END of its second month: "czerwiec-lipiec 2026"
        # is a process that finishes in July, so the completion date is July's
        # last day. Taking the first month would date the row before the cut.
        month = _MONTHS_NOM.get(m.group(2).lower())
        if month:
            return _end_of_month(int(m.group(3)), month)
    return None


def _looks_like_prose(name):
    """True when a general-anchor candidate is a sentence, not an employer."""
    tokens = [t.strip("„”\"'()").lower() for t in name.split()]
    return any(t in _PROSE_TOKENS for t in tokens)


def _anchors(flat_text):
    """Company anchors from both rules, in document order, without overlaps.

    The legal-form rule wins wherever the two overlap: it is the stricter of
    the two and its name boundary is the one that survives a dotted suffix.
    """
    found = [(m.start(), m.end(), m.group("name"), "legal")
             for m in _ANCHOR_RX.finditer(flat_text)]
    for m in _GENERAL_ANCHOR_RX.finditer(flat_text):
        name = m.group("name")
        if _looks_like_prose(name):
            continue
        found.append((m.start(), m.end(), name, "general"))
    found.sort(key=lambda a: (a[0], 0 if a[3] == "legal" else 1))
    out = []
    for start, end, name, kind in found:
        if out and start < out[-1][1]:
            continue
        out.append((start, end, name, kind))
    return out


def _declared_total(flat_text):
    """The post's own tally of the notified jobs, for a completeness audit.

    Every post states it, in one of two wordings, and it is the same number our
    rows must sum to: "cztery firmy z Mazowsza - łącznie 140 osób" (June) or
    "Łącznie w wyniku tych zapowiedzi pracę ma stracić 80 osób" (March). It is
    NOT the other figure in the same paragraph -- "pracę na Mazowszu straciło
    280 osób" counts dismissals actually CARRIED OUT that month, from notices
    filed earlier, and summing our rows against that would compare intentions
    with completions and call a correct parse broken.
    """
    for rx in (r"łącznie\s+(\d[\d\s.]{0,6})\s*os[óo]b",
               r"pracę\s+ma(?:ją)?\s+stracić\s+(\d[\d\s.]{0,6})\s*os[óo]b"):
        m = re.search(rx, flat_text, re.I)
        if m:
            try:
                return int(re.sub(r"[\s.]", "", m.group(1)))
            except ValueError:
                pass
    return None


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
    anchors = _anchors(flat_text)
    for i, (_start, end, name, _kind) in enumerate(anchors):
        nxt = anchors[i + 1][0] if i + 1 < len(anchors) else len(flat_text)
        body = flat_text[end:min(nxt, end + 500)]
        cm = _COUNT_RX.search(body)
        date = _deadline(body)
        if not cm or not date:
            skipped += 1
            continue
        try:
            jobs = int(re.sub(r"[\s.]", "", cm.group(1)))
        except ValueError:
            skipped += 1
            continue
        e = _entry(name, jobs, date, body[:120], post_url)
        if e:
            out.append(e)
        else:
            skipped += 1
    return out, skipped


# Filled by pull_wup_mazowieckie so warn_import can report what the run SAW.
_LAST_REPORT = {}


def last_run_report():
    """What the most recent pull actually saw, for the health detail."""
    return dict(_LAST_REPORT)


def health_detail():
    """One line for the health ledger that can disagree with a thin parse.

    It reports our jobs against the total the posts state for THEMSELVES, so
    "the collector ran" and "the collector read the register" stop being the
    same sentence. Three of eleven notices read as "ok" for as long as it did
    because nothing on any surface compared the two.
    """
    r = _LAST_REPORT
    base = "Mazowieckie collective-dismissal register (WUP Warszawa)"
    if not r:
        return base
    if not r.get("posts_read"):
        return (f"{base} — NO register post was readable this run "
                f"({r.get('posts_found', 0)} link(s) on the listing page). The "
                f"register may be fine; this is a fetch failure, not a parse one.")
    declared = r.get("declared_jobs")
    audit = ""
    if declared:
        # Compared BEFORE dedup, because the declared totals are per post and a
        # notice repeated across two months is counted in both of them. After
        # dedup the two sides measure different things and the audit would show
        # a permanent shortfall that means nothing.
        audit = (f", {r.get('parsed_jobs', 0):,} of the {declared:,} jobs those "
                 f"posts declare for themselves")
    elif r.get("posts_without_a_total"):
        audit = (f", and {r['posts_without_a_total']} post(s) stated no total of "
                 f"their own, so completeness is UNKNOWN this run, not verified")
    skipped = (f"; {r['skipped']} item(s) skipped for a missing count or deadline"
               if r.get("skipped") else "")
    return (f"{base} — {r.get('notices', 0)} notices from "
            f"{r['posts_read']} monthly post(s){audit}{skipped}")


def pull_wup_mazowieckie(max_posts=4):
    """Fetch recent register posts from the press listing and parse notices."""
    global _LAST_REPORT
    page = requests.get(LISTING_URL, headers=UA, timeout=TIMEOUT)
    page.raise_for_status()
    links = []
    for u, t in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page.text, re.S):
        title = re.sub(r"<[^>]+>", " ", t)
        if "zwolnienia grupowe" in title.lower() and u.startswith("http"):
            if u not in links:
                links.append(u)
    _LAST_REPORT = {"posts_found": len(links), "posts_read": 0, "notices": 0,
                    "jobs": 0, "parsed_jobs": 0, "declared_jobs": 0,
                    "posts_without_a_total": 0, "skipped": 0}
    out, seen, total_skipped = [], set(), 0
    for url in links[:max_posts]:
        try:
            post = requests.get(url, headers=UA, timeout=TIMEOUT)
            if post.status_code != 200:
                continue
            flat = _flat(post.text)
            entries, skipped = _parse_post(flat, url)
            total_skipped += skipped
            _LAST_REPORT["posts_read"] += 1
            _LAST_REPORT["parsed_jobs"] += sum(e["job_count"] for e in entries)
            declared = _declared_total(flat)
            if declared:
                _LAST_REPORT["declared_jobs"] += declared
            else:
                _LAST_REPORT["posts_without_a_total"] += 1
            for e in entries:
                if e["dedup_hash"] not in seen:
                    seen.add(e["dedup_hash"])
                    out.append(e)
        except requests.RequestException as exc:
            print(f"    WUP Mazowieckie: post fetch failed ({exc})")
    _LAST_REPORT["notices"] = len(out)
    _LAST_REPORT["jobs"] = sum(e["job_count"] for e in out)
    _LAST_REPORT["skipped"] = total_skipped
    if total_skipped:
        print(f"    WUP Mazowieckie: {total_skipped} item(s) skipped (no legal-form "
              f"anchor / count / deadline) — never guessed")
    return out
