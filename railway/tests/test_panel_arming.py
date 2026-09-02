"""The armed held-relabel loop routes each HELD relabel through the three-model
adjudication panel, and ONLY the held path (CLAUDE.md scope).

HERMETIC. No network, no real spend, no real correction write. The panel is
injected: every vote is a canned JSON string replayed through the REAL panel
aggregation (so the headline-mover gate and the citing-unanimity rule are the
real ones), and the apply path is the spot-check's own `request_json`, patched
to record `/edit` payloads instead of POSTing them.

What each case pins:
  * AUTO_APPLY (a small guarded-label relabel three citing models agree on) is
    RESCUED: it reaches /edit exactly once and its votes are logged.
  * a headline-mover (>= 5,000 jobs) at a citing 3-0 does NOT auto-apply; the
    owner gets a panel-vetted one-click notice.
  * a non-citing split holds and emails the one-click.
  * a REJECT neither applies nor emails (the DOGE case).
  * ALT_PANEL_ARMED unset restores today's behaviour (bare hold + email, the
    panel never runs).
  * spend.PaidReadsOff leaves every relabel HELD, applies nothing, exits 0.
"""
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import adjudication_panel as panel
import daily_classification_spotcheck as sc

# Captured BEFORE any patch so the injected fake can delegate to the real panel
# aggregation without recursing into itself.
REAL_ADJUDICATE_RELABEL = panel.adjudicate_relabel


def _vote(approve, quote="the source states it", reason="reason"):
    return json.dumps({"approve": approve, "cited_quote": quote, "reason": reason})


def all_citing_approve():
    return {m: _vote(True, quote="the evidence says so") for m in panel.PANEL_MODELS}


def one_nonciting_approve():
    # No reject, but one approve carries no quote -> not clean-unanimous -> HOLD.
    raws = {m: _vote(True, quote="the evidence says so") for m in panel.PANEL_MODELS}
    raws[panel.PANEL_MODELS[-1]] = _vote(True, quote="")
    return raws


def one_reject():
    raws = {m: _vote(True, quote="the evidence says so") for m in panel.PANEL_MODELS}
    raws[panel.PANEL_MODELS[-1]] = _vote(False, quote="", reason="not supported")
    return raws


def _fake_adjudicate(votes_by_company):
    """A drop-in for panel.adjudicate_relabel that replays canned votes through
    the REAL aggregation, keyed by the row's company."""
    def fake(row, field, old, new, evidence, models=panel.PANEL_MODELS,
             call_model=None):
        raws = votes_by_company[row.get("company")]

        def scripted(model, system, user):
            return raws[model]

        return REAL_ADJUDICATE_RELABEL(row, field, old, new, evidence,
                                       call_model=scripted)
    return fake


def _flag(row, field, suggested):
    return {"id": row["id"], "field": field,
            "current": row["country"] if field == "country" else row["industry"],
            "suggested": suggested,
            "why": "the excerpt places the cut at its Ohio plant"}


class Harness:
    """Drives the real sc.main() with scripted flags and an injected panel."""

    def __init__(self, rows, flags, votes_by_company, armed=True,
                 adjudicate_side_effect=None):
        self.rows = rows
        self.flags = flags
        self.votes_by_company = votes_by_company
        self.armed = armed
        self.adjudicate_side_effect = adjudicate_side_effect
        self.calls = []
        self.alerts = []
        self.summary_text = []

    def request_json(self, url, payload=None, headers=None, attempts=3, timeout=120):
        self.calls.append((url, payload))
        if "sort=layoff_date" in url:
            return {"data": self.rows}
        if "sort=job_count" in url:
            return {"data": []}
        if url.endswith("edit"):
            return {"edited": [e["id"] for e in (payload or {}).get("edits", [])]}
        raise AssertionError("unexpected request: " + url)

    def ask_model(self, prompt):
        # Flag pass, then a confirmation pass that agrees with every flag.
        if "auditing" in prompt:
            return {"flags": self.flags}
        return {"confirm": [{"id": f["id"], "agree": True} for f in self.flags]}

    def notify(self, subject, body, *, dedupe_key="", resolve_scope="",
               what="operational alert"):
        self.alerts.append({"subject": subject, "body": body,
                            "dedupe_key": dedupe_key,
                            "resolve_scope": resolve_scope})
        return True

    @property
    def edit_payloads(self):
        return [p for url, p in self.calls if url.endswith("edit")]

    @property
    def edited_ids(self):
        return {e["id"] for p in self.edit_payloads for e in p.get("edits", [])}

    @property
    def hold_alerts(self):
        return [a for a in self.alerts if not a["resolve_scope"]]

    @property
    def output(self):
        return "\n".join(self.summary_text)

    def run(self):
        door = types.SimpleNamespace(
            configured=lambda: True,
            notify=self.notify,
            resolve=lambda scope, subject, body, what="": self.notify(
                subject, body, resolve_scope=scope, what=what))
        env = {"WP_API_KEY": "test-key", "OPENROUTER_API_KEY": "test-key"}
        if self.armed:
            env["ALT_PANEL_ARMED"] = "1"
        else:
            env["ALT_PANEL_ARMED"] = "off"
        if self.adjudicate_side_effect is not None:
            adj = self.adjudicate_side_effect
        else:
            adj = _fake_adjudicate(self.votes_by_company)
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(sc, "request_json", self.request_json), \
             mock.patch.object(sc, "ops_notify", door), \
             mock.patch.object(sc, "ask_model", self.ask_model), \
             mock.patch.object(sc, "arm_deadline", lambda *_a, **_k: None), \
             mock.patch.object(sc, "summary", self.summary_text.append), \
             mock.patch.object(sc.panel, "adjudicate_relabel", adj), \
             mock.patch.object(sc.spend, "paid_reads_enabled", lambda: True):
            return sc.main()


# A small row held ONLY by the guarded worldwide-country rule (< 5,000 jobs).
GUARDED_SMALL = {"id": 501, "company_name": "Acme Retail", "industry": "Retail",
                 "country": "Multiple countries", "job_count": 200,
                 "excerpt": "Acme Retail cut 200 US jobs in Ohio.",
                 "source_name": "Local Wire", "source_url": "https://ex.invalid/a"}

# A headline-mover held by magnitude (>= 5,000 jobs).
BIG = {"id": 502, "company_name": "MegaCorp", "industry": "Automotive",
       "country": "Canada", "job_count": 8000,
       "excerpt": "MegaCorp cut 8,000 jobs across US plants.",
       "source_name": "Wire", "source_url": "https://ex.invalid/b"}


class AutoApplyRescuesASmallRelabel(unittest.TestCase):
    def test_auto_apply_reaches_edit_once_and_logs_votes(self):
        flag = _flag(GUARDED_SMALL, "country", "United States")
        h = Harness([GUARDED_SMALL], [flag],
                    {"Acme Retail": all_citing_approve()})
        code = h.run()
        self.assertEqual(code, 0)
        # Applied exactly once, through /edit (the sanctioned correction path).
        applied = [e for p in h.edit_payloads for e in p.get("edits", [])
                   if e["id"] == 501]
        self.assertEqual(len(applied), 1,
                         "a panel-approved small relabel did not reach /edit exactly once")
        self.assertEqual(applied[0]["fields"], {"country": "United States"})
        # The decision and the three votes are logged.
        self.assertIn("AUTO_APPLY", h.output)
        for m in panel.PANEL_MODELS:
            self.assertIn(m, h.output, f"vote from {m} was not logged")

    def test_auto_apply_carries_the_panel_reason_to_the_corrections_log(self):
        flag = _flag(GUARDED_SMALL, "country", "United States")
        h = Harness([GUARDED_SMALL], [flag],
                    {"Acme Retail": all_citing_approve()})
        h.run()
        panel_post = [p for p in h.edit_payloads
                      if any(e["id"] == 501 for e in p.get("edits", []))][0]
        self.assertIn("three-model", panel_post["reason"].lower())
        self.assertNotIn("—", panel_post["reason"], "no em-dash in corrections copy")


class HeadlineMoverNeverAutoApplies(unittest.TestCase):
    def test_a_citing_3_0_on_a_big_row_holds_and_emails_the_one_click(self):
        flag = _flag(BIG, "country", "United States")
        h = Harness([BIG], [flag], {"MegaCorp": all_citing_approve()})
        code = h.run()
        self.assertEqual(code, 0)
        self.assertNotIn(502, h.edited_ids,
                         "a >= 5,000-job relabel auto-applied even at a citing 3-0")
        self.assertTrue(h.hold_alerts, "the owner was not emailed a held notice")
        body = h.hold_alerts[0]["body"]
        self.assertIn("502", body)
        self.assertIn("apply_correction.py", body, "no one-click command in the notice")
        self.assertIn("3-0", body, "the tally is not shown in the notice")


class ASplitHolds(unittest.TestCase):
    def test_a_non_citing_split_holds_and_emails(self):
        flag = _flag(GUARDED_SMALL, "country", "United States")
        h = Harness([GUARDED_SMALL], [flag],
                    {"Acme Retail": one_nonciting_approve()})
        h.run()
        self.assertNotIn(501, h.edited_ids, "a non-citing split was auto-applied")
        self.assertTrue(h.hold_alerts, "a split did not email the owner")
        self.assertIn("apply_correction.py", h.hold_alerts[0]["body"])


class ARejectIsSilent(unittest.TestCase):
    def test_reject_neither_applies_nor_emails(self):
        flag = _flag(GUARDED_SMALL, "country", "United States")
        h = Harness([GUARDED_SMALL], [flag],
                    {"Acme Retail": one_reject()})
        code = h.run()
        self.assertEqual(code, 0)
        self.assertNotIn(501, h.edited_ids, "a rejected suggestion was applied")
        self.assertFalse(h.hold_alerts,
                         "a rejected suggestion emailed the owner; a killed bad "
                         "suggestion is noise, not an action item")
        # But it is auditable in the run log.
        self.assertIn("REJECT", h.output)
        self.assertIn("501", h.output)


class DormantRestoresTodaysBehaviour(unittest.TestCase):
    def test_off_holds_and_emails_bare_and_never_calls_the_panel(self):
        flag = _flag(GUARDED_SMALL, "country", "United States")
        boom = mock.Mock(side_effect=AssertionError(
            "the panel was called while ALT_PANEL_ARMED was off"))
        h = Harness([GUARDED_SMALL], [flag], {}, armed=False,
                    adjudicate_side_effect=boom)
        code = h.run()
        self.assertEqual(code, 0)
        boom.assert_not_called()
        self.assertNotIn(501, h.edited_ids)
        self.assertTrue(h.hold_alerts, "today's bare hold email did not go out")
        # Bare notice, not the panel-vetted one.
        self.assertNotIn("apply_correction.py", h.hold_alerts[0]["body"])
        self.assertIn("HELD", h.output)


class PaidReadsOffLeavesItHeld(unittest.TestCase):
    def test_a_budget_stop_holds_everything_and_applies_nothing(self):
        flag = _flag(GUARDED_SMALL, "country", "United States")
        stop = mock.Mock(side_effect=sc.spend.PaidReadsOff("ceiling reached"))
        h = Harness([GUARDED_SMALL], [flag], {}, armed=True,
                    adjudicate_side_effect=stop)
        code = h.run()
        self.assertEqual(code, 0, "a budget stop must not redden CI")
        self.assertEqual(h.edited_ids, set(), "a budget stop applied a relabel")
        self.assertTrue(h.hold_alerts,
                        "an undecided relabel was not held for the owner")


class TheAiCausationPathIsNotWired(unittest.TestCase):
    def test_spotcheck_leaves_a_todo_and_does_not_call_ai_causation(self):
        src = (Path(__file__).resolve().parents[1] /
               "daily_classification_spotcheck.py").read_text()
        # The follow-up must be recorded, and the ai-causation panel must not be
        # CALLED. A mention inside the explanatory TODO comment is expected; an
        # actual invocation `panel.adjudicate_ai_causation(` is not.
        self.assertIn("TODO (ai-causation)", src,
                      "the ai-causation follow-up is not recorded")
        self.assertNotIn("adjudicate_ai_causation(", src.replace(
            "adjudication_panel.adjudicate_ai_causation()", ""),
            "the ai-causation panel is invoked; it must stay dormant until it "
            "has conflict/impact gating")


if __name__ == "__main__":
    unittest.main()
