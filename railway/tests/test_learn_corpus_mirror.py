"""tracker_diff --learn reads its reference corpus from the BigQuery mirror.

Since 2026-09-02 the public GDELT DOC API answers HTTP 429 within seconds to
every caller, and the learning loop's one keyless read of it returned UNKNOWN
three days running: honest, and blind. The daily collector was unaffected
because it reads the same universe from the BigQuery mirror. This file pins
that the learning loop now reads it the same way, through the collector's OWN
function (`sources.gdelt.mirror_corpus`), and that nothing else moved:

  * the collector's mirror walk is unchanged (`_collect_mirror` still reports
    the walk's own verdict, `pull_gdelt_between` still reads the same flag);
  * the mirror read is a NEW METHOD (`m5`), because the mirror cannot express
    the DOC query -- title-or-theme over the whole vocabulary, walked to
    completion, against text-match over an anchor slice capped at 250 -- and a
    trend must not splice two denominators under one tag;
  * nameless output survives: the marker reaches the owner's email and no other
    sink, and a mirror failure prints the exception's CLASS, never its text;
  * the workflow passes exactly the two env lines the collector workflows pass,
    and still carries no OpenRouter key on the learn step ($0.00 in model spend
    is structural, not a promise).

Offline. `requests` is stubbed through the shared installer; the mirror is
patched at `sources.gdelt.mirror_corpus`, the seam the loop actually calls.
"""
import io
import json
import os
import re
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()
if "openai" not in sys.modules:
    sys.modules["openai"] = types.ModuleType("openai")

import tracker_diff as td  # noqa: E402
from sources import gdelt, gdelt_bq  # noqa: E402

MARK = "Zzqqmarker"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "tracker-diff.yml"


def _poisoned(n=6):
    return [{
        "title": f"{MARK}{i} to cut {300 + i} jobs in restructuring",
        "domain": f"{MARK.lower()}-news{i % 2}.example",
        "sourcecountry": f"{MARK}land",
        "language": f"{MARK}ish",
        "seendate": f"20260903T{10 + i:02d}0000Z",
        "url": f"https://{MARK.lower()}.example/{i}",
    } for i in range(n)]


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


class _LearnHarness(unittest.TestCase):
    """The poisoned-run harness from test_tracker_learning_leak, plus the
    mirror preference and a fake credential so `gdelt_bq.available()` is true
    without a client ever being built."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._saved = (td.LEARN_STATE_PATH, td._learn_fetch, td.requests,
                       td.report_source_health, td.ops_notify)
        self._env = {k: os.environ.get(k) for k in
                     ("GDELT_PREFER_BQ", "GCP_BIGQUERY_CREDENTIALS_JSON",
                      "WP_SITE_URL", "WP_API_KEY")}
        td.LEARN_STATE_PATH = os.path.join(self.tmp, "state.json")
        self.fetch_calls = []
        td._learn_fetch = lambda query, *a, **k: (
            self.fetch_calls.append(query) or (_poisoned(), 0, None))
        self.emails, self.health = [], []
        td.ops_notify = types.SimpleNamespace(
            configured=lambda: True,
            notify=lambda subject, body, **kw: (
                self.emails.append({"subject": subject, "body": body, **kw}) or True),
            resolve=lambda *a, **k: True)
        td.requests = types.SimpleNamespace(
            get=lambda *a, **k: _FakeResponse({"data": []}),
            post=lambda *a, **k: _FakeResponse({}))
        td.report_source_health = lambda *a: self.health.append(a)
        os.environ["WP_SITE_URL"] = "https://example.test/blog"
        os.environ["WP_API_KEY"] = "test-key"
        os.environ["GDELT_PREFER_BQ"] = "1"
        os.environ["GCP_BIGQUERY_CREDENTIALS_JSON"] = '{"fake": true}'

    def tearDown(self):
        (td.LEARN_STATE_PATH, td._learn_fetch, td.requests,
         td.report_source_health, td.ops_notify) = self._saved
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _run(self, mirror):
        buf = io.StringIO()
        with patch.object(gdelt, "mirror_corpus", mirror), redirect_stdout(buf):
            facts = td.learn_run(today=date(2026, 9, 4))
        return facts, buf.getvalue()


class TheMirrorIsTheCorpus(_LearnHarness):
    def test_a_poisoned_mirror_run_reaches_the_email_and_nothing_else(self):
        """The leak property, on the new path. MUTATION: add a `print(title)`
        anywhere on the mirror read and this fails."""
        facts, out = self._run(lambda s, e: (_poisoned(), True))
        self.assertGreater(facts["rules"], 0, "an empty run proves nothing")
        self.assertEqual(len(self.emails), 1)
        self.assertIn(MARK.lower(), json.dumps(self.emails[0]).lower())
        self.assertNotIn(MARK.lower(), out.lower())
        self.assertNotIn(MARK.lower(), json.dumps(self.health).lower())
        with open(td.LEARN_STATE_PATH) as fh:
            self.assertNotIn(MARK.lower(), fh.read().lower())
        td.assert_nameless(facts)

    def test_the_public_api_is_not_touched_when_the_mirror_answers(self):
        """The whole point: no request to the endpoint that answers 429."""
        facts, _ = self._run(lambda s, e: (_poisoned(), True))
        self.assertEqual(self.fetch_calls, [])
        self.assertEqual(facts["state"], "ran")
        self.assertEqual(facts["corpus"], 6)
        # The mirror already used the whole vocabulary; nothing to rotate.
        self.assertEqual(facts["explored"], 0)

    def test_a_mirror_read_is_method_m5_and_the_trend_point_says_so(self):
        """MUTATION: return LEARN_METHOD from the mirror branch of
        `_learn_corpus` and this fails. The two reads are different
        denominators; a trend that spliced them would move on the switch."""
        facts, _ = self._run(lambda s, e: (_poisoned(), True))
        self.assertEqual(facts["method"], td.LEARN_METHOD_MIRROR)
        self.assertNotEqual(td.LEARN_METHOD_MIRROR, td.LEARN_METHOD)
        with open(td.LEARN_STATE_PATH) as fh:
            point = json.load(fh)["history"][-1]
        self.assertEqual(point["method"], td.LEARN_METHOD_MIRROR)
        # ...and the tag is admitted by the nameless guard by shape.
        td.assert_nameless({"method": td.LEARN_METHOD_MIRROR})

    def test_the_window_passed_to_the_mirror_is_the_learn_window(self):
        seen = {}

        def mirror(start, end):
            seen["start"], seen["end"] = start, end
            return _poisoned(), True

        self._run(mirror)
        span = seen["end"] - seen["start"]
        self.assertEqual(round(span.total_seconds() / 3600), td.LEARN_WINDOW_HOURS)
        self.assertIsNotNone(seen["end"].tzinfo, "the mirror wants aware UTC stamps")


class TheMirrorFailingIsNotTheEnd(_LearnHarness):
    def test_a_mirror_failure_falls_back_to_the_public_api_under_m4(self):
        def boom(s, e):
            raise RuntimeError("quota")

        facts, out = self._run(boom)
        self.assertEqual(len(self.fetch_calls), 2, "anchor and rotating DOC reads")
        self.assertEqual(facts["method"], td.LEARN_METHOD)
        self.assertEqual(facts["state"], "ran")
        self.assertIn("mirror read failed (RuntimeError)", out)

    def test_a_failure_message_carrying_a_name_never_reaches_stdout(self):
        """MUTATION: print `e` instead of `type(e).__name__` and this fails. A
        BigQuery error can quote the SQL and its parameters; the stdout of this
        loop is a public sink and admits a class name only."""
        def boom(s, e):
            raise RuntimeError(f"{MARK} appeared in a message")

        _facts, out = self._run(boom)
        self.assertNotIn(MARK.lower(), out.lower())
        self.assertIn("RuntimeError", out)

    def test_a_partial_walk_is_still_read(self):
        """`complete=False` means the page ceiling, not a failure: the walked
        part is a corpus, and the fact is said on stdout."""
        facts, out = self._run(lambda s, e: (_poisoned(), False))
        self.assertEqual(facts["state"], "ran")
        self.assertEqual(facts["method"], td.LEARN_METHOD_MIRROR)
        self.assertIn("page ceiling", out)

    def test_no_credentials_means_the_public_api_not_a_client(self):
        os.environ["GCP_BIGQUERY_CREDENTIALS_JSON"] = ""
        calls = []
        facts, out = self._run(lambda s, e: calls.append(1) or (_poisoned(), True))
        self.assertEqual(calls, [], "mirror_corpus must not be called without credentials")
        self.assertEqual(len(self.fetch_calls), 2)
        self.assertEqual(facts["method"], td.LEARN_METHOD)
        self.assertIn("no BigQuery credentials", out)

    def test_the_flag_unset_is_the_old_path_exactly(self):
        os.environ.pop("GDELT_PREFER_BQ")
        calls = []
        facts, _ = self._run(lambda s, e: calls.append(1) or (_poisoned(), True))
        self.assertEqual(calls, [])
        self.assertEqual(len(self.fetch_calls), 2)
        self.assertEqual(facts["method"], td.LEARN_METHOD)


class TheMirrorReadItself(unittest.TestCase):
    def setUp(self):
        self._creds = os.environ.get("GCP_BIGQUERY_CREDENTIALS_JSON")
        os.environ["GCP_BIGQUERY_CREDENTIALS_JSON"] = "x"

    def tearDown(self):
        if self._creds is None:
            os.environ.pop("GCP_BIGQUERY_CREDENTIALS_JSON", None)
        else:
            os.environ["GCP_BIGQUERY_CREDENTIALS_JSON"] = self._creds

    def test_articles_come_back_newest_first(self):
        """The DOC read sampled the newest 250 (`sortby=datedesc`) and the
        candidate cap walks the list in order; the mirror walks (DATE, url)
        ASCENDING. Newest first keeps the cap sampling the same end of the
        window."""
        arts = _poisoned(4)                       # seendates ascending by i
        start = datetime(2026, 9, 3, tzinfo=timezone.utc)
        end = datetime(2026, 9, 4, tzinfo=timezone.utc)
        with patch.object(gdelt, "mirror_corpus", lambda s, e: (list(arts), True)):
            out, state = td._learn_mirror(start, end)
        self.assertIsNone(state)
        stamps = [a["seendate"] for a in out]
        self.assertEqual(stamps, sorted(stamps, reverse=True))

    def test_the_read_is_the_collectors_own_function(self):
        """Not a copy of its query. MUTATION: inline a `gdelt_bq.query_window_walk`
        call in `_learn_mirror` and this fails -- the two universes could then
        drift on vocabulary without either side noticing."""
        src = Path(td.__file__).read_text(encoding="utf-8")
        body = src[src.index("def _learn_mirror"):]
        body = body[:body.index("\n\ndef ")]
        self.assertIn("gdelt.mirror_corpus(", body)
        self.assertNotIn("query_window_walk", body)
        self.assertNotIn("query_window_page", body)


class TheCollectorDidNotMove(unittest.TestCase):
    """The extraction must be a pure refactor for the collector."""

    def test_collect_mirror_still_reports_the_walks_own_verdict(self):
        start = datetime(2026, 9, 3, tzinfo=timezone.utc)
        end = datetime(2026, 9, 4, tzinfo=timezone.utc)
        for complete, status in ((True, "complete"), (False, "partial")):
            with patch.object(gdelt_bq, "query_window_walk",
                              lambda s, e, terms, **k: ([{"url": "u", "domain": "d"}], complete)):
                arts, got = gdelt._collect_mirror(start, end)
            self.assertEqual(got, status)
            self.assertEqual(len(arts), 1)

    def test_mirror_corpus_hands_the_walk_the_full_vocabulary(self):
        seen = {}

        def fake_walk(s, e, terms, **k):
            seen["terms"] = list(terms)
            return [], True

        with patch.object(gdelt_bq, "query_window_walk", fake_walk):
            gdelt.mirror_corpus(datetime(2026, 9, 3, tzinfo=timezone.utc),
                                datetime(2026, 9, 4, tzinfo=timezone.utc))
        self.assertIn("layoffs", seen["terms"])
        self.assertIn("Stellenabbau", seen["terms"])

    def test_mirror_corpus_prints_nothing(self):
        """It is called from a loop whose stdout is nameless by construction;
        a print here would be a second sink."""
        src = Path(gdelt.__file__).read_text(encoding="utf-8")
        body = src[src.index("def mirror_corpus"):]
        body = body[:body.index("\n\ndef ")]
        self.assertNotIn("print(", body)

    def test_one_definition_of_the_preference_flag(self):
        src = Path(gdelt.__file__).read_text(encoding="utf-8")
        self.assertEqual(src.count('os.environ.get("GDELT_PREFER_BQ"'), 1,
                         "the flag is read in prefer_mirror() and nowhere else")
        self.assertIn("prefer_bq = prefer_mirror()", src)
        saved = os.environ.get("GDELT_PREFER_BQ")
        try:
            for val, want in (("1", True), ("true", True), ("yes", True),
                              ("0", False), ("", False)):
                os.environ["GDELT_PREFER_BQ"] = val
                self.assertIs(gdelt.prefer_mirror(), want, val)
            os.environ.pop("GDELT_PREFER_BQ")
            self.assertIs(gdelt.prefer_mirror(), False)
        finally:
            if saved is None:
                os.environ.pop("GDELT_PREFER_BQ", None)
            else:
                os.environ["GDELT_PREFER_BQ"] = saved


class TheWorkflowPassesWhatTheCollectorsPass(unittest.TestCase):
    def _learn_step(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        start = text.index("name: Run tracker-learn")
        end = text.index("\n      - name:", start + 1)
        return text[start:end]

    def test_the_learn_step_carries_the_two_mirror_lines(self):
        step = self._learn_step()
        self.assertIn("GCP_BIGQUERY_CREDENTIALS_JSON: ${{ secrets.GCP_BIGQUERY_CREDENTIALS_JSON }}",
                      step)
        self.assertRegex(step, r"GDELT_PREFER_BQ: ['\"]1['\"]")

    def test_it_is_spelled_exactly_as_the_collector_workflows_spell_it(self):
        for name in ("gdelt-backfill.yml", "historical-news-sweep.yml"):
            other = (WORKFLOW.parent / name).read_text(encoding="utf-8")
            self.assertIn("GCP_BIGQUERY_CREDENTIALS_JSON: ${{ secrets.GCP_BIGQUERY_CREDENTIALS_JSON }}",
                          other, name)
            self.assertIn("GDELT_PREFER_BQ: '1'", other, name)

    def test_no_model_key_reaches_the_learn_step(self):
        """$0.00 in model spend, structurally."""
        step = self._learn_step()
        self.assertNotIn("OPENROUTER_API_KEY", step)
        self.assertRegex(step, r"ALT_PAID_READS: ['\"]off['\"]")


if __name__ == "__main__":
    unittest.main()
