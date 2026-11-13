"""A full-size MONTHLY edition, shaped on the 2026-11-01..12 test send.

The owner's test of that edition (sent 2026-11-13 to the owner's test address)
arrived as 183,793 bytes of HTML and Gmail clipped it ("[Message clipped]"
past ~102 KB), hiding the footer and the unsubscribe link. A digest whose
unsubscribe link is hidden is a compliance defect, not a style one.

This module builds that edition's SHAPE through the real composers (both PHP
briefings via the compose harness) and the real `digest_send.build_message`,
so a size test measures what a reader would be sent rather than a sample.
The names and numbers are fictional; the counts that drive size are not:
40 verified rows over 22 countries with a single-report majority, 8 trend
weeks, 40 hiring signals, and the blog section.

`received_size()` adds what the relay does after us. Click tracking is ON by
the owner's decision (2026-08-16), and the relay rewrites every link into its
own redirect URL, measured at ~780 characters each in the received copy. A
budget that ignores that rewrite passes a message Gmail clips anyway.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

FROM, TO = "2026-11-01", "2026-11-12"

# Measured in the received 2026-11-13 test copy: the relay's redirect URLs
# ran 772 to 786 characters. The rounded-up figure is the allowance.
TRACKED_URL_CHARS = 790

# Gmail clips a message whose HTML passes ~102 KB. The owner's target is
# ~90 KB; the test ceiling is 95 KB so a small edition-to-edition swing does
# not land in the clip.
CLIP_BYTES = 102 * 1024
CEILING_BYTES = 95 * 1000

COUNTRIES = ["United States", "United Kingdom", "Netherlands", "Germany",
             "France", "India", "Canada", "Australia", "Japan", "Brazil",
             "Mexico", "Paraguay", "Spain", "Italy", "Poland", "Sweden",
             "Singapore", "South Korea", "Ireland", "Belgium", "Chile",
             "Multiple countries"]
INDUSTRIES = ["Technology", "Finance & Insurance", "Manufacturing",
              "Automotive", "Telecommunications", "Retail & E-commerce",
              "Healthcare & Pharma", "Transportation & Logistics",
              "Aerospace & Defense", "Energy & Utilities"]


def tup(label, verified, all_jobs=None, ai=0):
    return [label, verified if all_jobs is None else all_jobs, 0, None, verified, ai]


def _row(i, company, jobs, country, *, single=False, state="", industry="Technology"):
    news = single or i % 3 == 0
    return {
        "id": 180000 + i, "event_id": 150000 + i, "company_name": company,
        "job_count": jobs, "layoff_date": "2026-11-%02d" % (1 + i % 12),
        "country": country, "state": state,
        "source_type": "news" if news else "warn",
        "source_name": "Example Daily News" if news else "%s WARN notice" % (state or "CA"),
        "verification_level": "bronze" if single else ("silver" if news else "gold"),
        "additional_sources": [] if single else [{"url": "https://example.test/second/%d" % i}],
        "tier": "verified", "announced": False,
        "source_url": "https://example-news.test/2026/11/%d/a-long-article-slug-about-job-cuts-at-%d" % (i, i),
        "industry": industry,
    }


def layoff_fixture():
    rows = []
    big = [("Telecom Group", 8000, "United Kingdom", True),
           ("Bank Holding", 7000, "Multiple countries", True),
           ("Flag Carrier Airline", 5000, "Netherlands", False),
           ("Bearing Maker", 3460, "Germany", False),
           ("Ride App", 3000, "Paraguay", True),
           ("Payments Co", 3000, "United States", True),
           ("Planemaker", 2500, "United States", True),
           ("Big Bank", 2500, "Australia", False),
           ("Carmaker", 2200, "Italy", True),
           ("Luxury Cars", 1800, "Germany", False)]
    for i, (c, j, country, single) in enumerate(big):
        rows.append(_row(i + 1, c, j, country, single=single,
                         state="WA" if country == "United States" else "",
                         industry=INDUSTRIES[i % len(INDUSTRIES)]))
    for i in range(30):
        country = COUNTRIES[i % len(COUNTRIES)]
        rows.append(_row(20 + i, "Employer %02d Holdings" % i, 1500 - i * 40, country,
                         single=(i % 2 == 0),
                         state="TX" if country == "United States" else "",
                         industry=INDUSTRIES[i % len(INDUSTRIES)]))
    ver = sum(r["job_count"] for r in rows)
    by_country, by_ind = {}, {}
    for r in rows:
        by_country[r["country"]] = by_country.get(r["country"], 0) + r["job_count"]
        by_ind[r["industry"]] = by_ind.get(r["industry"], 0) + r["job_count"]
    layoff = {
        "totals": {"jobs": ver + 5000, "entries": len(rows) + 3,
                   "announced_jobs": 5000, "announced_entries": 3,
                   "ai_verified_jobs": 3420, "ai_verified_entries": 4,
                   "companies": len(rows) + 3},
        "map_countries": [tup(c, v) for c, v in sorted(by_country.items(), key=lambda x: -x[1])],
        "top_countries": [],
        "top_industries": [tup(k, v) for k, v in sorted(by_ind.items(), key=lambda x: -x[1])],
        "leaders": [],
        "concentration": {"largest_row_company": "Telecom Group", "largest_row_jobs": 8000},
    }
    weeks = {}
    for k, f in enumerate(["2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05",
                           "2026-10-12", "2026-10-19", "2026-10-26"]):
        weeks[f] = {"totals": {"jobs": 15000 + 1700 * k, "announced_jobs": 0},
                    "concentration": {"largest_row_company": "X", "largest_row_jobs": 10}}
    return {
        "from": FROM, "to": TO, "freq": "monthly", "compose": "layoff",
        "options": {"alt_last_write": 1794500000,
                    "alt_digest_briefing_tiers": "daily,weekly,monthly"},
        "layoff": layoff, "layoff_rows": rows, "weeks": weeks,
        "ytd": {"totals": {"jobs": 990000, "announced_jobs": 460000, "ai_verified_jobs": 43000},
                "map_countries": [tup("United States", 400000)]},
    }


def _sig(i, company, country, headcount, city=""):
    return {"signal_id": "s%d" % i, "company": company, "country": country,
            "hq_country": "", "signal_direction": "hiring",
            "headcount": None if headcount is None else str(headcount),
            "industry": "technology", "city": city, "state": "",
            "source_name": "Example Business Wire",
            "source_url": "https://example-wire.test/2026/11/%d/company-announces-expansion-%d" % (i, i),
            "materiality": "high"}


def talent_fixture():
    codes = ["US", "IN", "GB", "DE", "FR", "CA", "AU", "JP", "BR", "MX", "NL", "SG"]
    rows = [_sig(i, "Hiring Company %02d" % i, codes[i % len(codes)],
                 12000 - i * 250, city="City %d" % i) for i in range(40)]
    by_country = {}
    for r in rows:
        by_country[r["country"]] = by_country.get(r["country"], 0) + 1
    # Consistent with the rows, or the composer's own check holds the lists.
    agg = {"total": len(rows), "companies": len(rows), "stated_headcount": len(rows),
           "by_direction": [{"k": "hiring", "n": str(len(rows))}],
           "by_country": [{"k": k, "n": str(v)} for k, v in by_country.items()]}
    return {"from": FROM, "to": TO, "freq": "monthly", "compose": "talent",
            "options": {"alt_digest_talent_briefing_tiers": "daily,weekly,monthly"},
            "talent": agg, "talent_q": {"total": len(rows), "rows": rows},
            "talent_ytd": {"total": 30000, "by_country": []}, "talent_geo": agg}


ARTICLES_HTML = (
    "<h2>Career resources</h2>"
    "<p>Three reads from the blog this month.</p>"
    + "".join('<p><a href="https://asktherecruiter.com/blog/article-%d/">'
              "A practical guide for job seekers, part %d</a></p>"
              "<p>A short summary of the article that a reader sees.</p>" % (i, i)
              for i in range(6)))
ARTICLES_TEXT = ("Career resources\nThree reads from the blog this month.\n"
                 + "".join("  - A practical guide, part %d: https://asktherecruiter.com/blog/article-%d/\n" % (i, i)
                           for i in range(6)))


def compose(fx):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as h:
        json.dump(fx, h)
    try:
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, h.name],
                             capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(h.name)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:1500])
    return json.loads(run.stdout)


UNSUB = ("https://asktherecruiter.com/blog/wp-admin/admin-post.php"
         "?action=alt_digest_unsub&t=" + "a" * 64)
MANAGE = ("https://asktherecruiter.com/blog/ai-layoff-tracker/preferences/1-"
          + "b" * 64 + "/")


def build():
    """(message, layoff_out, talent_out) for the full monthly edition."""
    import digest_send
    lay = compose(layoff_fixture())
    tal = compose(talent_fixture())
    payload = {
        "freq": "monthly", "from": FROM, "to": TO,
        "sections": {
            "layoff": {k: lay.get(k, "") for k in ("html", "text", "preheader", "metric")},
            "talent": {k: tal.get(k, "") for k in ("html", "text", "preheader", "metric")},
            "articles": {"html": ARTICLES_HTML, "text": ARTICLES_TEXT},
        },
    }
    msg = digest_send.build_message(
        payload, {"email": "reader@example.test", "unsub_url": UNSUB,
                  "manage_url": MANAGE, "lists": ["layoff", "talent", "articles"]},
        "AskTheRecruiter.com <newsletter@example.test>", "reply@example.test")
    return msg, lay, tal


_HREF = re.compile(r'href="(https?://[^"]*)"')


def received_size(html: str) -> int:
    """Bytes of HTML as the reader's mailbox holds it: every http(s) link
    rewritten by the relay's click tracking to a ~790-character redirect."""
    return len(_HREF.sub(lambda m: 'href="' + "x" * TRACKED_URL_CHARS + '"',
                         html).encode("utf-8"))


if __name__ == "__main__":
    m, _, _ = build()
    print("sent bytes", len(m.html.encode()), "received bytes", received_size(m.html),
          "links", len(_HREF.findall(m.html)))
