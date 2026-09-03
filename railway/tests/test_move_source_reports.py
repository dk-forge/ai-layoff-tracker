"""A row can hold another event's evidence, and the correction path must be able
to put that right without touching the row.

THE CASE, 2026-09-02/03. Row 178973 ("Uber, 500, Chile, 2026-08-31") absorbed
thirteen reports of Uber's global ~3,300 cut because the same-company fuzzy
merge never read the count (fixed in 2.20.161). The row's own facts were
right; only the attached source reports were wrong. No route could fix that:
/edit has no source field, /trash drops the row, /merge-events only folds
reports IN. `/move-source-reports` moves named links to the row whose event
they describe, and `apply_correction.py --action move-sources` drives it with
the same discipline as every other correction: dry run by default, reason
required and recorded in the public corrections log, before/after shown, and
a loud failure on any link that was not moved.

`add` is the other half: the lost event's URLs are already held as reports,
so the seen-URL pre-check skips them forever and the pipeline cannot re-read
its way to the row. The row therefore goes through /add like any collector's,
with the dedup hash derived exactly as extractor.py derives it.

The PHP handler needs $wpdb, so its rules are pinned by reading the source;
the Python driver is executed with requests stubbed, and a dry run that
POSTs anything fails the test.
"""
import hashlib
import io
import json
import os
import re
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
DB = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes", "db.php")
EXTRACTOR = os.path.join(RAILWAY, "extractor.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "apply-correction.yml")

if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)
import apply_correction as ac  # noqa: E402


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _handler():
    m = re.search(r"\nfunction alt_api_move_source_reports\(.*?\n\}", _read(DB), re.S)
    assert m, "alt_api_move_source_reports is not in db.php"
    return m.group(0)


class HandlerRules(unittest.TestCase):
    def test_route_is_key_protected(self):
        src = _read(DB)
        m = re.search(r"register_rest_route\('layoffs/v1', '/move-source-reports', array\((.*?)\)\);", src, re.S)
        self.assertIsNotNone(m, "route not registered")
        self.assertIn("alt_api_permission", m.group(1))
        self.assertIn("alt_api_move_source_reports", m.group(1))

    def test_reason_is_required_and_logged(self):
        h = _handler()
        self.assertRegex(h, r"(?s)reason === ''.*?WP_Error", "an empty reason must be refused")
        self.assertIn("alt_log_correction('corrected'", h, "a move must reach the public corrections log")
        self.assertIn("sources reattributed", h)

    def test_primary_citation_is_never_moved(self):
        h = _handler()
        self.assertIn("$out['refused'][]", h)
        self.assertRegex(h, r"\$url === \(string\) \$from\['source_url'\]")

    def test_missing_link_is_reported_not_skipped(self):
        self.assertIn("$out['not_found'][]", _handler())

    def test_insert_before_delete(self):
        h = _handler()
        self.assertLess(h.index("alt_event_add_report($to_event"), h.index("$wpdb->delete($reports"),
                        "the target must hold the report before the source loses it")

    def test_two_rows_two_events(self):
        h = _handler()
        self.assertIn("$from_id === $to_id", h)
        self.assertIn("$from_event === $to_event", h)


class DedupHashParity(unittest.TestCase):
    def test_add_derives_the_extractors_hash(self):
        src = _read(EXTRACTOR)
        m = re.search(r"hash_input = \((.*?)\)\n", src, re.S)
        self.assertIsNotNone(m, "extractor's hash_input not found")
        extracted = {"company_name": "  Uber ", "layoff_date": "2026-09-02", "job_count": 3300}
        theirs = hashlib.md5(eval("(" + m.group(1) + ")").encode("utf-8")).hexdigest()  # noqa: S307
        self.assertEqual(ac.dedup_hash("  Uber ", "2026-09-02", 3300), theirs)
        self.assertEqual(ac.dedup_hash("Uber", None, 3300),
                         hashlib.md5(b"uber3300").hexdigest())


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(body)

    def json(self):
        return self._body


FROM_ROW = 178973
TO_ROW = 999001
CHILE = "https://www.df.cl/empresas/telecom-tecnologia/uber-elimina-mas-de-500-puestos-en-chile"
GLOBAL = ["https://www.bbc.com/news/articles/cp3ky2w4y9no",
          "https://www.moneycontrol.com/news/business/companies/uber-3-300-jobs.html"]


def _sources(row_id):
    if row_id == FROM_ROW:
        return [{"source_name": "df.cl", "source_url": CHILE, "excerpt": "Uber elimina mas de 500 puestos en Chile"},
                {"source_name": "bbc.com", "source_url": GLOBAL[0], "excerpt": "Uber announces 3,000 job cuts"},
                {"source_name": "moneycontrol.com", "source_url": GLOBAL[1], "excerpt": "Uber to cut 3,300 jobs"}]
    if row_id == TO_ROW:
        return [{"source_name": "livemint.com", "source_url": "https://www.livemint.com/x", "excerpt": "3,300"}]
    return []


def _fake_get(url, params=None, headers=None, timeout=None):
    m = re.search(r"/event/(\d+)/sources", url)
    if m:
        return _Resp(200, {"layoff_id": int(m.group(1)), "sources": _sources(int(m.group(1)))})
    if url.endswith("/aggregate"):
        return _Resp(200, {"totals": {"jobs": 20616745, "entries": 65413}})
    if url.endswith("/query"):
        return _Resp(200, {"data": [{"id": FROM_ROW, "company_name": "Uber", "job_count": 500,
                                     "layoff_date": "2026-08-31", "country": "Chile"}]})
    return _Resp(404, {})


class MoveSourcesDriver(unittest.TestCase):
    def _run(self, apply, urls=None, posts=None):
        posts = [] if posts is None else posts

        def fake_post(url, json=None, headers=None, timeout=None):
            posts.append((url, json))
            return _Resp(200, {"from_id": FROM_ROW, "to_id": TO_ROW, "moved": list(json["urls"]),
                               "not_found": [], "refused": []})
        out = io.StringIO()
        with mock.patch.object(ac.requests, "get", _fake_get), \
             mock.patch.object(ac.requests, "post", fake_post), \
             mock.patch.object(ac.time, "sleep", lambda *_: None), \
             redirect_stdout(out):
            rc = ac.run_move_sources("https://x", "key", [FROM_ROW],
                                     {"to_id": TO_ROW, "urls": urls or GLOBAL}, "why", apply)
        return rc, out.getvalue(), posts

    def test_dry_run_classifies_and_writes_nothing(self):
        rc, text, posts = self._run(apply=False)
        self.assertEqual(rc, 0)
        self.assertEqual(posts, [], "a dry run must not POST")
        self.assertIn("DRY RUN", text)
        self.assertRegex(text, r"MOVE\s+bbc\.com")
        self.assertRegex(text, r"MOVE\s+moneycontrol\.com")
        self.assertRegex(text, r"stay\s+df\.cl")

    def test_apply_posts_once_with_reason(self):
        rc, text, posts = self._run(apply=True)
        self.assertEqual(rc, 0)
        self.assertEqual(len(posts), 1)
        url, body = posts[0]
        self.assertTrue(url.endswith("/move-source-reports"))
        self.assertEqual(body["reason"], "why")
        self.assertEqual(body["urls"], GLOBAL)
        self.assertIn("after   row", text)

    def test_link_not_held_by_from_row_refuses_before_any_write(self):
        rc, text, posts = self._run(apply=True, urls=[GLOBAL[0], "https://example.com/not-attached"])
        self.assertNotEqual(rc, 0)
        self.assertEqual(posts, [], "a bad link list must never reach the host")
        self.assertIn("NOT attached", text)

    def test_server_shortfall_is_a_red_run(self):
        posts = []

        def short_post(url, json=None, headers=None, timeout=None):
            posts.append(url)
            return _Resp(200, {"moved": [GLOBAL[0]], "not_found": [GLOBAL[1]], "refused": []})
        out = io.StringIO()
        with mock.patch.object(ac.requests, "get", _fake_get), \
             mock.patch.object(ac.requests, "post", short_post), \
             mock.patch.object(ac.time, "sleep", lambda *_: None), \
             redirect_stdout(out):
            rc = ac.run_move_sources("https://x", "key", [FROM_ROW], {"to_id": TO_ROW, "urls": GLOBAL}, "why", True)
        self.assertNotEqual(rc, 0)
        self.assertIn("::error::", out.getvalue())

    def test_needs_exactly_one_from_row(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = ac.run_move_sources("https://x", "key", [1, 2], {"to_id": 3, "urls": GLOBAL}, "why", False)
        self.assertNotEqual(rc, 0)


class AddDriver(unittest.TestCase):
    ENTRY = {"company_name": "Uber", "job_count": 3300, "layoff_date": "2026-09-02",
             "source_url": "https://www.livemint.com/x", "source_name": "livemint.com",
             "country": "Multiple countries", "industry": "Technology"}

    def test_dry_run_shows_row_and_headline_and_posts_nothing(self):
        out = io.StringIO()
        with mock.patch.object(ac.requests, "get", _fake_get), \
             mock.patch.object(ac.requests, "post", side_effect=AssertionError("dry run POSTed")), \
             redirect_stdout(out):
            rc = ac.run_add("https://x", "key", dict(self.ENTRY), "why", False)
        text = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("DRY RUN", text)
        self.assertIn("20,616,745", text)
        self.assertIn("20,620,045", text, "the headline after must be stated before anything is written")
        self.assertIn(ac.dedup_hash("Uber", "2026-09-02", 3300), text)

    def test_apply_goes_through_the_one_poster_and_fails_on_409(self):
        seen = []

        def fake_poster(entry):
            seen.append(entry)
            return "duplicate"
        out = io.StringIO()
        with mock.patch.object(ac.requests, "get", _fake_get), \
             mock.patch.dict(sys.modules, {"wp_poster": mock.Mock(post_to_wordpress=fake_poster)}), \
             mock.patch.object(ac.time, "sleep", lambda *_: None), \
             redirect_stdout(out):
            rc = ac.run_add("https://x", "key", dict(self.ENTRY), "why", True)
        self.assertNotEqual(rc, 0, "a 409 is nothing stored and must be a red run")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["dedup_hash"], ac.dedup_hash("Uber", "2026-09-02", 3300))

    def test_missing_required_field_refuses(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = ac.run_add("https://x", "key", {"company_name": "Uber"}, "why", False)
        self.assertNotEqual(rc, 0)


class WorkflowOffersBoth(unittest.TestCase):
    def test_choices(self):
        wf = _read(WORKFLOW)
        self.assertIn("options: [trash, edit, move-sources, add]", wf)
        self.assertIn("default: false", wf, "apply must default to a dry run")


if __name__ == "__main__":
    unittest.main()
