"""Automated broken-link check for the AI Layoff Tracker.

Two jobs, both read-only and fail-soft (a monitoring script must never page the
owner about its own hiccup):

  1. PUBLIC PAGES must return 200. The tracker, health, sources, methodology,
     ai-quotes, press and publisher-tools pages are the product; if any 404s or
     500s, that is a real outage and we alert.
  2. SOURCE LINKS decay over time (news URLs rot, states rotate files). We
     sample recent rows' source_url and report the broken rate as a health
     metric. This is INFORMATIONAL - link rot is expected and is exactly what
     the Wayback archiving backstops - so a high source-rot rate is reported,
     not alerted, unless a public PAGE is down.

Env: WP_SITE_URL, WP_API_KEY (for the /alert email + health ledger),
LINK_CHECK_SAMPLE (default 60 source links). No LLM, ~0 cost.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from http_retry import get_with_retry
except Exception:
    get_with_retry = None

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
SAMPLE = max(10, min(300, int(os.environ.get("LINK_CHECK_SAMPLE") or "60")))

PUBLIC_PAGES = (
    "/ai-layoff-tracker/",
    "/ai-layoff-tracker/ai-tracker-health/",
    "/ai-layoff-tracker/sources/",
    "/ai-layoff-tracker/methodology/",
    "/ai-layoff-tracker/ai-quotes/",
    "/ai-layoff-tracker/press/",
    "/ai-layoff-tracker/publisher-tools/",
    "/contact/",
)


def _status(url, headers, timeout=25):
    """Return an int HTTP status, or 0 on transport failure. Never raises."""
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        code = r.status_code
        r.close()
        return code
    except Exception:
        return 0


def _email(subject, body):
    if not (SITE and KEY):
        return
    try:
        requests.post(f"{SITE}/wp-json/layoffs/v1/alert",
                      json={"subject": subject, "body": body},
                      headers={"X-Layoff-API-Key": KEY, **UA}, timeout=25)
    except Exception as exc:
        print(f"alert send failed: {exc}")


def _report(status, entries, detail):
    if not (SITE and KEY):
        return
    try:
        requests.post(f"{SITE}/wp-json/layoffs/v1/source-health",
                      json={"source": "link_check", "status": status,
                            "entries": entries, "detail": detail},
                      headers={"X-Layoff-API-Key": KEY, **UA}, timeout=25)
    except Exception as exc:
        print(f"health report failed: {exc}")


def check_pages():
    """Every public page must be 200. Returns the list of broken ones."""
    broken = []
    for path in PUBLIC_PAGES:
        code = _status(f"{SITE}{path}?cb=linkcheck", BROWSER_UA)
        mark = "ok" if code == 200 else "BROKEN"
        print(f"  {mark:<6} {code}  {path}")
        if code != 200:
            broken.append((path, code))
    return broken


def check_sources():
    """Sample recent rows' source_url; report the broken rate (informational)."""
    try:
        r = requests.get(f"{SITE}/wp-json/layoffs/v1/query",
                         params={"per_page": SAMPLE, "sort": "layoff_date", "dir": "desc",
                                 "cb": "linkcheck"}, headers=UA, timeout=40)
        rows = r.json().get("data", []) if r.status_code == 200 else []
    except Exception as exc:
        print(f"could not sample rows: {exc}")
        return 0, 0, []
    urls = []
    seen = set()
    for row in rows:
        u = str(row.get("source_url") or "").strip()
        if u.startswith("http") and u not in seen:
            seen.add(u)
            urls.append(u)
    broken = []
    for u in urls:
        code = _status(u, BROWSER_UA, timeout=20)
        # 200/redirect/ 401-403 (bot walls, still live) count as reachable;
        # 404/410/0 (gone/dead) count as broken.
        if code in (0, 404, 410) or code >= 500:
            broken.append((u, code))
    print(f"\nsource links: {len(urls)} sampled, {len(broken)} broken/dead")
    return len(urls), len(broken), broken


def main():
    if not SITE:
        print("WP_SITE_URL required")
        return 1
    print("PUBLIC PAGES:")
    broken_pages = check_pages()
    sampled, broken_src, broken_list = check_sources()

    rot = round(100.0 * broken_src / sampled, 1) if sampled else 0.0
    detail = (f"{len(PUBLIC_PAGES) - len(broken_pages)}/{len(PUBLIC_PAGES)} public pages OK; "
              f"source-link sample {sampled - broken_src}/{sampled} reachable "
              f"({rot}% rot, backstopped by Wayback archiving)")
    print("\n" + detail)

    # A broken PUBLIC PAGE is a real outage -> alert + degraded. Source rot is
    # expected link decay -> informational only (the archive is the backstop).
    if broken_pages:
        lines = ["Broken public pages on the AI Layoff Tracker (these must be 200):", ""]
        for path, code in broken_pages:
            lines.append(f"  HTTP {code}  {SITE}{path}")
        lines.append("\nThis is a live-site problem. Check the deploy and the page's shortcode.")
        _email(f"{len(broken_pages)} tracker page(s) returning errors", "\n".join(lines))
        _report("degraded", len(broken_pages), detail)
        print("::error::broken public page(s) detected")
        return 1

    _report("ok", sampled - broken_src, detail)
    if rot >= 25 and broken_list:
        # Not an alert (expected), but surface a notice so a spike is visible.
        print(f"::warning::source-link rot at {rot}% "
              f"(e.g. {broken_list[0][0][:70]}) - Wayback archiving is the backstop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
