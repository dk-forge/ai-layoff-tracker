"""Page-weight budget for the reader-facing pages (reach audit 2026-11-10).

Fetches each page with the browser-ish User-Agent the host requires and checks
the raw HTML size and the number of <script> tags against a ceiling. The
ceiling sits above today's measurement (tracker: 428 KB, 34 scripts) so it
catches a regression, not the status quo.

Read-only, stdlib only, no keys. Exit 0 = all within budget, 2 = a page is
over budget, 3 = a page could not be measured (UNKNOWN, never a pass).
"""
import re
import sys
import urllib.request

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_HTML_BYTES = 600_000
MAX_SCRIPTS = 45
PAGES = (
    "https://asktherecruiter.com/blog/ai-layoff-tracker/",
    "https://asktherecruiter.com/blog/company-layoffs/browse/a/",
)

_SCRIPT = re.compile(r"<script\b", re.I)


def count_scripts(html):
    return len(_SCRIPT.findall(html))


def verdict(html_bytes, scripts):
    if html_bytes is None or scripts is None:
        return "UNKNOWN"
    if html_bytes > MAX_HTML_BYTES or scripts > MAX_SCRIPTS:
        return "OVER"
    return "OK"


def exit_code(verdicts):
    if "OVER" in verdicts:
        return 2
    if "UNKNOWN" in verdicts:
        return 3
    return 0


def measure(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except Exception as e:  # noqa: BLE001 - any failure is UNKNOWN, reported
        print(f"UNKNOWN {url}: {type(e).__name__}: {e}")
        return None, None
    return len(body), count_scripts(body.decode("utf-8", "replace"))


def main():
    verdicts = []
    for url in PAGES:
        size, scripts = measure(url)
        v = verdict(size, scripts)
        verdicts.append(v)
        if size is not None:
            print(f"{v} {url}: {size} bytes (max {MAX_HTML_BYTES}), "
                  f"{scripts} scripts (max {MAX_SCRIPTS})")
    return exit_code(verdicts)


if __name__ == "__main__":
    sys.exit(main())
