"""The activity reader: UNKNOWN when it cannot read, and no socket in a test.

It exists because the burn could not be attributed from committed state, so
the one thing it must never do is make an unreadable account look like a quiet
one.
"""
import os
import urllib.error
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openrouter_activity as act  # noqa: E402


ROWS = [
    {"date": "2026-09-14", "usage": 1.20, "api_key_label": "layoff-tracker",
     "model": "google/gemini-2.5-flash-lite"},
    {"date": "2026-09-14", "usage": 0.40, "api_key_label": "talent-tracker",
     "model": "deepseek/deepseek-chat"},
    {"date": "2026-09-14", "usage": 0.05, "model": "openai/gpt-4o-mini"},
    {"date": "2026-09-13", "usage": 0.30, "api_key_label": "layoff-tracker",
     "model": "google/gemini-2.5-flash-lite"},
]


class AKeylessRunIsUnknownNeverEmpty(unittest.TestCase):
    def setUp(self):
        self._k = act.OR_KEY
        act.OR_KEY = ""
        self.addCleanup(lambda: setattr(act, "OR_KEY", self._k))

    def test_no_key_returns_none_and_says_it_never_asked(self):
        rows, note = act.fetch_activity()
        self.assertIsNone(rows, "no key must not read as an empty account")
        self.assertIn("UNKNOWN", note)

    def test_main_exits_3_not_0(self):
        self.assertEqual(act.main([]), act.UNKNOWN)
        self.assertNotEqual(act.UNKNOWN, act.OK)


class AFailedReadIsUnknownToo(unittest.TestCase):
    def setUp(self):
        self._k = act.OR_KEY
        act.OR_KEY = "test-key"
        self.addCleanup(lambda: setattr(act, "OR_KEY", self._k))

    def test_a_raising_get_is_unknown(self):
        def boom(url):
            raise OSError("connection reset")
        rows, note = act.fetch_activity(get=boom)
        self.assertIsNone(rows)
        self.assertIn("failed", note)

    def test_an_unexpected_shape_is_unknown(self):
        rows, note = act.fetch_activity(get=lambda url: {"data": {"not": "a list"}})
        self.assertIsNone(rows)
        self.assertIn("unexpected shape", note)

    def test_the_key_is_never_echoed_in_an_error(self):
        def boom(url):
            raise OSError(f"bad token test-key rejected")
        _rows, note = act.fetch_activity(get=boom)
        self.assertNotIn("test-key", note)
        self.assertIn("***", note)


class GroupingAttributesByKeyAndModel(unittest.TestCase):
    def test_totals_and_per_key_shares(self):
        g = act.group(ROWS, days=7)
        self.assertAlmostEqual(g["total"], 1.95, places=4)
        self.assertAlmostEqual(g["by_key"]["layoff-tracker"], 1.50, places=4)
        self.assertAlmostEqual(g["by_key"]["talent-tracker"], 0.40, places=4)

    def test_an_unlabelled_key_is_named_not_dropped(self):
        # A repo nobody labelled is exactly the consumer that went uncounted.
        g = act.group(ROWS, days=7)
        self.assertIn("unlabelled key", g["by_key"])
        self.assertAlmostEqual(g["by_key"]["unlabelled key"], 0.05, places=4)

    def test_a_renamed_spend_field_is_still_read(self):
        # Reading a renamed field as 0.0 would look exactly like a quiet account.
        g = act.group([{"date": "2026-09-14", "cost": 2.0, "api_key_label": "k"}])
        self.assertAlmostEqual(g["total"], 2.0, places=4)
        g = act.group([{"date": "2026-09-14", "total_cost": 3.0, "api_key_label": "k"}])
        self.assertAlmostEqual(g["total"], 3.0, places=4)

    def test_the_window_keeps_only_the_most_recent_days(self):
        g = act.group(ROWS, days=1)
        self.assertEqual(g["days_seen"], 1)
        self.assertAlmostEqual(g["total"], 1.65, places=4)

    def test_render_prints_no_key_and_no_prompt_text(self):
        out = act.render(act.group(ROWS, days=7))
        self.assertIn("BY API KEY", out)
        self.assertNotIn("Bearer", out)


class ItIsNotASecondBalanceWriter(unittest.TestCase):
    def test_it_does_not_write_the_balance_history_file(self):
        # openrouter_balance_history.json has ONE writer and this is not it.
        src = (Path(__file__).resolve().parents[1] / "openrouter_activity.py").read_text()
        # Checked by what WRITES, not by whether the filename is mentioned: the
        # module's docstring names openrouter_balance_history.json precisely to
        # say it is not that file's writer, and a test that forbade the mention
        # would punish the documentation. `open(` is checked with urlopen
        # stripped, because urllib's own name contains it.
        for marker in ("write_text", "json.dump", "Path(", "os.replace"):
            self.assertNotIn(marker, src,
                             "the activity reader persists nothing")
        self.assertNotIn("open(", src.replace("urlopen(", ""),
                         "the activity reader opens no file")

    def test_it_makes_no_model_call(self):
        src = (Path(__file__).resolve().parents[1] / "openrouter_activity.py").read_text()
        self.assertNotIn("/chat/completions", src)
        self.assertNotIn("metered_call", src)


if __name__ == "__main__":
    unittest.main()

class A403NamesItsOwnRemedy(unittest.TestCase):
    """The first dispatch returned 403 and the reason was not in the message.

    An operator reading "activity read failed: HTTP Error 403" learns nothing
    and will re-dispatch. /activity is restricted to a provisioning key by
    OpenRouter's design, so the message says so and names the secret to add.
    """

    def setUp(self):
        self._k, self._p = act.OR_KEY, act.USING_PROVISIONING_KEY
        act.OR_KEY, act.USING_PROVISIONING_KEY = "inference-key", False
        self.addCleanup(lambda: setattr(act, "OR_KEY", self._k))
        self.addCleanup(lambda: setattr(act, "USING_PROVISIONING_KEY", self._p))

    def _note(self):
        def forbidden(url):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        _rows, note = act.fetch_activity(get=forbidden)
        return note

    def test_a_403_on_an_inference_key_names_the_provisioning_key(self):
        note = self._note()
        self.assertIn("403", note)
        self.assertIn("PROVISIONING", note.upper())
        self.assertIn("OPENROUTER_PROVISIONING_KEY", note)

    def test_it_says_no_code_change_is_needed(self):
        # The remedy is a secret, and saying so stops the next session editing
        # the module instead of adding the key.
        self.assertIn("No code change is needed", self._note())

    def test_a_403_with_a_provisioning_key_does_not_blame_the_key_type(self):
        # Then the 403 means something else and the guidance would misdirect.
        act.USING_PROVISIONING_KEY = True
        self.assertNotIn("OPENROUTER_PROVISIONING_KEY", self._note())


class TheProvisioningKeyIsPreferred(unittest.TestCase):
    def test_no_key_at_all_names_both_variables(self):
        k, p = act.OR_KEY, act.USING_PROVISIONING_KEY
        act.OR_KEY, act.USING_PROVISIONING_KEY = "", False
        try:
            _rows, note = act.fetch_activity()
            self.assertIn("OPENROUTER_PROVISIONING_KEY", note)
            self.assertIn("OPENROUTER_API_KEY", note)
            self.assertIn("UNKNOWN", note)
        finally:
            act.OR_KEY, act.USING_PROVISIONING_KEY = k, p

