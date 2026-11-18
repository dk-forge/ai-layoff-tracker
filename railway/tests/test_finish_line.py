"""finish_line.py / finish_line_issue.py: the checker logic, offline (no network, no browser)."""
import datetime as dt
import contextlib
import io
import os
import tempfile
import unittest
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import finish_line as fl  # noqa: E402
import finish_line_issue as fi  # noqa: E402

BASE = "https://asktherecruiter.com/blog/ai-layoff-tracker/"
TODAY = dt.date(2026, 11, 18)


def _result(**over):
    r = {"name": "T", "bad_pages": [], "bad_links": [], "truncated": False, "max_pages": 1, "max_links": 1,
         "unsourced": {}, "cta_missing": [], "data_date": "2026-11-17", "data_age_days": 1}
    r.update(over)
    return r


def test_all_green_is_pass():
    assert fl.verdict(_result()) == []


def test_each_failure_is_named():
    r = _result(bad_pages=[(BASE + "x/", 404)], bad_links=[("https://asktherecruiter.com/y", 500, BASE)],
                unsourced={BASE: ["880,000 jobs cut"]}, cta_missing=[(BASE, 390)],
                data_date="2026-11-01", data_age_days=17)
    why = " | ".join(fl.verdict(r))
    for part in ("not 200", "broken internal link", "without a source link", "CTA not visible", "17 days ago"):
        assert part in why


def test_could_not_check_is_never_a_pass():
    assert fl.verdict(_result(data_date=None, data_age_days=None))
    assert fl.verdict(_result(browser_error="CDPUnavailable: no chrome"))
    assert fl.verdict(_result(truncated=True))


def test_newest_date_prefers_the_latest_past_date():
    html = '<time datetime="2026-11-15">x</time> as of 2026-11-17 next run 2026-12-01'
    assert fl.newest_date(html, TODAY) == dt.date(2026, 11, 17)
    assert fl.newest_date("<p>nothing</p>", TODAY) is None


def test_scope_and_normalise():
    assert fl.normalise("/blog/ai-layoff-tracker/places/#x", BASE) == BASE + "places/"
    assert fl.normalise("mailto:a@b.c", BASE) is None
    assert fl.in_scope(BASE + "company/box/", BASE)
    assert not fl.in_scope(BASE + "feed/", BASE)
    assert not fl.in_scope("https://asktherecruiter.com/resume-score?utm_source=x", BASE)
    assert fl.is_internal("https://asktherecruiter.com/x") and not fl.is_internal("https://sec.gov/x")


def test_crawl_finds_bad_pages_and_bad_links():
    site = {
        BASE: (200, f'<a href="{BASE}a/">a</a><a href="{BASE}gone/">g</a><a href="/pricing">p</a><a href="https://sec.gov/f">s</a>'),
        BASE + "a/": (200, "<p>ok</p>"),
        BASE + "gone/": (404, ""),
        "https://asktherecruiter.com/pricing": (500, ""),
    }
    pages, bad_pages, bad_links, truncated = fl.crawl(BASE, 10, 10, 0, get=lambda u: site[u])
    assert set(pages) == {BASE, BASE + "a/", BASE + "gone/"}
    assert bad_pages == [(BASE + "gone/", 404)]
    assert ("https://asktherecruiter.com/pricing", 500, BASE) in bad_links
    assert not truncated


def test_crawl_cap_is_reported_as_truncated():
    site = {BASE: (200, f'<a href="{BASE}a/">a</a>'), BASE + "a/": (200, "")}
    assert fl.crawl(BASE, 1, 10, 0, get=lambda u: site[u])[3] is True


def test_markdown_says_fail_and_why():
    r = _result(cta_missing=[(BASE, 390)])
    r.update(reasons=fl.verdict(r), checked_at="now", pages_checked=1, browser_pages=1, numbers_total=0)
    md = fl.markdown(r)
    assert "**FAIL**" in md and "CTA" in md


def test_issue_plan_dedupes_by_exact_title():
    issues = [{"title": "Finish line FAIL: x", "number": 7, "state": "open"},
              {"title": "Finish line FAIL: x", "number": 8, "state": "open", "pull_request": {}}]
    assert fi.plan(fi.find_open(issues, "Finish line FAIL: x"), "t", "ATR") == ("repeat", 7)
    assert fi.plan(fi.find_open(issues, "other"), "t", "ATR") == ("create", ["Claude", "ATR"])


def test_issue_filer_without_token_does_not_fail():
    env = {k: v for k, v in os.environ.items() if k not in ("TODO_ISSUES_TOKEN", "GH_TOKEN")}
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("x")
    out = io.StringIO()
    old = os.environ.copy()
    try:
        os.environ.clear(); os.environ.update(env)
        with contextlib.redirect_stdout(out):
            rc = fi.main(["--title", "t", "--product", "ATR", "--body-file", f.name],
                         call=lambda *a: (_ for _ in ()).throw(AssertionError("no call")))
    finally:
        os.environ.clear(); os.environ.update(old); os.unlink(f.name)
    assert rc == 0 and "NOT FILED" in out.getvalue()


class FinishLine(unittest.TestCase):
    pass


for _n, _f in list(globals().items()):
    if _n.startswith("test_") and callable(_f):
        setattr(FinishLine, _n, staticmethod(_f))
