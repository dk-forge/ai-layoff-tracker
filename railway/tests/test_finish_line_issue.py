"""The dk-forge/todo issue filer, copied with finish_line_issue.py from
dk-forge/asktherecruiter-sandbox PR #4352 (2026-11-18): it lists open issues
instead of searching (search answers 422 for a repo the token cannot see),
moves to the next token on a 422, pages through every issue and fails rather
than file a duplicate on an incomplete scan, and logs GitHub's own error.
unittest form: this repo runs railway/tests with unittest.
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import finish_line_issue as fi  # noqa: E402


def _http(code, msg):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(('{"message": "%s"}' % msg).encode()))


class Filer(unittest.TestCase):

    def _run(self, call):
        env = {"TODO_ISSUES_TOKEN": "first", "TODO_ISSUES_TOKEN_FALLBACK": "second"}
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("x")
        out = io.StringIO()
        try:
            with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
                os.environ.pop("GH_TOKEN", None)
                rc = fi.main(["--title", "t", "--product", "ATR", "--body-file", f.name], call=call)
        finally:
            os.unlink(f.name)
        return rc, out.getvalue()

    def test_moves_on_after_a_422(self):
        used = []

        def call(method, path, token, body=None):
            used.append(token)
            if token == "first":
                raise _http(422, "Validation Failed")
            return [] if method == "GET" else {"html_url": "https://github.com/dk-forge/todo/issues/1"}
        rc, out = self._run(call)
        self.assertEqual(rc, 0)
        self.assertIn("second", used)
        self.assertIn("FILED: https://github.com", out)

    def test_falls_back_on_403(self):
        def call(method, path, token, body=None):
            if token == "first":
                raise _http(403, "Resource not accessible")
            return [] if method == "GET" else {"html_url": "https://github.com/dk-forge/todo/issues/1"}
        self.assertIn("FILED:", self._run(call)[1])

    def test_reports_what_github_said(self):
        def call(method, path, token, body=None):
            raise _http(422, "Validation Failed: label does not exist")
        rc, out = self._run(call)
        self.assertEqual(rc, 0)
        self.assertIn("NOT FILED", out)
        self.assertIn("label does not exist", out)

    def test_dedupes_without_the_search_api(self):
        paths = []

        def call(method, path, token, body=None):
            paths.append(path)
            return [{"number": 7, "title": "t", "state": "open"}] if method == "GET" else {}
        rc, out = self._run(call)
        self.assertFalse(any("/search/" in p for p in paths))
        self.assertIn("REPEAT", out)

    def test_pages_past_500_and_finds_issue_501(self):
        issues = [{"number": n, "title": f"other {n}", "state": "open"} for n in range(500)]
        issues.append({"number": 501, "title": "t", "state": "open"})
        posts = []

        def call(method, path, token, body=None):
            if method == "GET":
                page = int(path.rsplit("page=", 1)[1])
                return issues[(page - 1) * 100:page * 100]
            posts.append(path)
            return {}
        rc, out = self._run(call)
        self.assertFalse(any(p.endswith("/issues") for p in posts))
        self.assertIn("REPEAT: https://github.com/dk-forge/todo/issues/501", out)

    def test_never_creates_on_an_incomplete_scan(self):
        posts = []

        def call(method, path, token, body=None):
            if method == "GET":
                return [{"number": 1, "title": "other", "state": "open"}] * 100
            posts.append(path)
            return {}
        rc, out = self._run(call)
        self.assertEqual(rc, 1)
        self.assertEqual(posts, [])
        self.assertIn("NOT FILED", out)

    def test_plan_labels(self):
        self.assertEqual(fi.plan(None, "t", "ATR"), ("create", ["Claude", "ATR"]))


if __name__ == "__main__":
    unittest.main()
