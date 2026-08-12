"""The daily spot-check must not relabel a big row unattended.

THE DEFECT THESE GUARD
----------------------
`daily_classification_spotcheck.py` samples the fifteen LARGEST rows in the
corpus (`query?sort=job_count&dir=desc&per_page=15`), asks a model whether their
labels look right, and used to apply every confirmed answer through `/edit` with
no magnitude bound, no cap and no human.

On 2026-08-08 (run 31264210709, "Auto-applied 14 double-confirmed label fix(es)")
it re-scored three ERM rows - 114335 Citigroup 52,000, 113529 General Motors
47,000, 64351 Cinemaworld 45,000 - from "Multiple countries" to "United States".
That put 92,000 jobs into the published US headline on the `country_basis=any`
basis and 144,000 on the strict job-location basis while leaving the worldwide
total untouched, and it stood on the live site for four days
(docs/US_HEADLINE_MOVEMENT_FORENSICS_2026_08.md, section 8).

It was systematic, not unlucky, for two reasons and both are tested here:

* Asked whether "Citigroup" belongs under "Multiple countries", a model reasons
  from the company's nationality rather than from where the jobs were cut. The
  same sample today holds Philips, VW Group, Lufthansa, UBS and HSBC, all
  legitimately "Multiple countries" for famous national companies. The bait is
  permanent.
* The "two independent passes" were the same `ask_model` called twice, so the
  shared bias survives both. Confirmation is not independence and buys nothing
  against exactly this error.

WHAT IS ACTUALLY BEING ASSERTED
-------------------------------
Not that the screening function returns the right verdict - that a run of
`main()` over the 2026-08-08 sample never reaches `/edit` with those rows.
A bound that is computed and then not consulted by the writer is the defect
with extra steps, so the end-to-end tests drive the real `main()` and watch the
HTTP calls it makes.

Offline: every response is a literal dict of the shape the endpoint returns.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_classification_spotcheck as sc


# The three rows of the 2026-08-08 incident, as `/query` returns them.
INCIDENT_ROWS = [
    {"id": 114335, "company_name": "Citigroup", "industry": "Finance",
     "country": "Multiple countries", "job_count": 52000,
     "excerpt": "Internal restructuring at Citigroup (Multiple countries): 52,000 announced job losses."},
    {"id": 113529, "company_name": "General Motors", "industry": "Automotive",
     "country": "Multiple countries", "job_count": 47000,
     "excerpt": "Internal restructuring at General Motors (Multiple countries): 47,000 announced job losses."},
    {"id": 64351, "company_name": "Cinemaworld", "industry": "Retail",
     "country": "Multiple countries", "job_count": 45000,
     "excerpt": "Bankruptcy at Cinemaworld (Multiple countries): 45,000 announced job losses."},
]

SMALL_ROW = {"id": 900001, "company_name": "Acme Widgets", "industry": "Retail",
             "country": "United States", "job_count": 120,
             "excerpt": "Acme Widgets cut 120 jobs at its Ohio plant."}


def _flag(row, field, suggested):
    return {"id": row["id"], "field": field,
            "current": row["country"] if field == "country" else row["industry"],
            "suggested": suggested, "why": "the company is American"}


class Harness:
    """Drives the real main() with scripted model answers and records HTTP."""

    def __init__(self, newest, biggest, flags, agreed_ids=None):
        self.newest, self.biggest = newest, biggest
        self.flags = flags
        self.agreed = [{"id": f["id"], "agree": True}
                       for f in (flags if agreed_ids is None
                                 else [f for f in flags if f["id"] in agreed_ids])]
        self.calls = []          # (url, payload)
        self.summary_text = []

    def request_json(self, url, payload=None, headers=None, attempts=3, timeout=120):
        self.calls.append((url, payload))
        if "sort=layoff_date" in url:
            return {"data": self.newest}
        if "sort=job_count" in url:
            return {"data": self.biggest}
        if url.endswith("edit"):
            return {"edited": [e["id"] for e in (payload or {}).get("edits", [])]}
        if url.endswith("alert"):
            return {"ok": True, "sent": True}
        raise AssertionError("unexpected request: " + url)

    def ask_model(self, prompt):
        # First call is the flagging pass, second is the confirmation pass.
        return {"flags": self.flags} if "auditing" in prompt else {"confirm": self.agreed}

    @property
    def edit_payloads(self):
        return [p for url, p in self.calls if url.endswith("edit")]

    @property
    def edited_ids(self):
        return {e["id"] for p in self.edit_payloads for e in p.get("edits", [])}

    @property
    def alert_payloads(self):
        return [p for url, p in self.calls if url.endswith("alert")]

    @property
    def output(self):
        return "\n".join(self.summary_text)

    def run(self):
        with mock.patch.dict(os.environ, {"WP_API_KEY": "test-key",
                                          "OPENROUTER_API_KEY": "test-key"}), \
             mock.patch.object(sc, "request_json", self.request_json), \
             mock.patch.object(sc, "ask_model", self.ask_model), \
             mock.patch.object(sc, "arm_deadline", lambda *_a, **_k: None), \
             mock.patch.object(sc, "summary", self.summary_text.append), \
             mock.patch.object(sc.spend, "paid_reads_enabled", lambda: True):
            return sc.main()


class BigCountryRelabelIsHeld(unittest.TestCase):
    """The bound is enforced where the writing happens, not in a report."""

    def _incident_harness(self):
        flags = [_flag(r, "country", "United States") for r in INCIDENT_ROWS]
        return Harness(newest=[SMALL_ROW], biggest=INCIDENT_ROWS, flags=flags)

    def test_the_52000_job_row_is_not_written(self):
        h = self._incident_harness()
        code = h.run()
        self.assertEqual(code, 0, "holding a relabel is not a failed run")
        self.assertNotIn(114335, h.edited_ids,
                         "a confirmed country relabel on a 52,000-job row reached "
                         "/edit; this is the 2026-08-08 defect, unchanged")

    def test_none_of_the_three_incident_rows_is_written(self):
        h = self._incident_harness()
        h.run()
        self.assertEqual(h.edited_ids & {114335, 113529, 64351}, set(),
                         "the rows that moved the published US headline by 92,000 "
                         "were relabeled again with no human in the loop")

    def test_the_run_says_it_held_them_and_why(self):
        h = self._incident_harness()
        h.run()
        out = h.output
        self.assertIn("HELD", out, "a held relabel that says nothing is a silent drop")
        for rid in (114335, 113529, 64351):
            self.assertIn(str(rid), out, f"row {rid} was held without being named")
        self.assertIn("5,000", out, "the run does not state the bound it applied")

    def test_the_owner_is_told_through_the_existing_alert_route(self):
        h = self._incident_harness()
        h.run()
        self.assertTrue(h.alert_payloads,
                        "nothing was posted to /alert, so a held relabel waits in a "
                        "queue nobody drains")
        p = h.alert_payloads[0]
        self.assertIn("dedupe_key", p, "an alert with no cause key mails daily forever")
        self.assertRegex(p["dedupe_key"], r"^[a-z0-9][a-z0-9:._-]{0,159}$",
                         "the endpoint rejects a dedupe_key outside this shape")
        self.assertIn("114335", p["body"])

    def test_an_unbounded_edit_cannot_slip_past_the_writer(self):
        """The last line of defence: even if screening were bypassed, the
        function that POSTs refuses a payload it cannot vouch for."""
        with self.assertRaises(Exception):
            sc.guard_edits([{"id": 114335, "fields": {"country": "United States"}}],
                           {114335: 52000})

    def test_a_row_whose_size_is_unknown_is_held_not_guessed(self):
        # The model can return an id that was never in the sample. Absence of a
        # job count is UNKNOWN, and UNKNOWN is not "small enough to edit".
        ghost = {"id": 777777, "field": "country", "current": "Multiple countries",
                 "suggested": "United States", "why": "hallucinated row"}
        h = Harness(newest=[SMALL_ROW], biggest=[], flags=[ghost])
        h.run()
        self.assertNotIn(777777, h.edited_ids)


class GuardedCountryLabels(unittest.TestCase):
    def test_multiple_countries_is_never_auto_relabeled_even_when_small(self):
        # The nationality bias does not switch off below the size bound; it is
        # simply cheaper when it is wrong. A worldwide restructuring label is
        # the one a model reliably reads as the company's home country.
        row = dict(SMALL_ROW, id=900002, country="Multiple countries", job_count=90)
        h = Harness(newest=[row], biggest=[],
                    flags=[_flag(row, "country", "United States")])
        h.run()
        self.assertNotIn(900002, h.edited_ids,
                         "a 'Multiple countries' row was auto-relabeled to a single "
                         "country; that is the exact reasoning error of 2026-08-08")


class SmallFixesStillLand(unittest.TestCase):
    """A guard that blocks everything is a broken feature, not a safe one."""

    def test_a_small_country_correction_is_still_applied(self):
        row = dict(SMALL_ROW, id=900003, country="Canada", job_count=120)
        h = Harness(newest=[row], biggest=[],
                    flags=[_flag(row, "country", "United States")])
        h.run()
        self.assertIn(900003, h.edited_ids)

    def test_a_small_industry_correction_is_still_applied(self):
        h = Harness(newest=[SMALL_ROW], biggest=[],
                    flags=[_flag(SMALL_ROW, "industry", "Manufacturing")])
        h.run()
        self.assertIn(SMALL_ROW["id"], h.edited_ids)

    def test_a_big_industry_relabel_is_held_too(self):
        # Industry cannot move a country headline, but it does move the
        # published by-industry aggregate by the row's full job count, and the
        # leverage argument is identical. Same bound, stated separately.
        h = Harness(newest=[], biggest=[INCIDENT_ROWS[0]],
                    flags=[_flag(INCIDENT_ROWS[0], "industry", "Technology")])
        h.run()
        self.assertNotIn(114335, h.edited_ids)


class NothingHeldClearsTheAlarm(unittest.TestCase):
    def test_a_clean_run_resolves_the_open_alert(self):
        h = Harness(newest=[SMALL_ROW], biggest=[], flags=[])
        h.run()
        self.assertTrue(any("resolve_scope" in (p or {}) for p in h.alert_payloads),
                        "nothing cleared the open hold, so a fixed backlog keeps "
                        "mailing STILL FAILING every fortnight")


class TheDocsDoNotClaimIndependence(unittest.TestCase):
    def test_the_public_correction_reason_does_not_say_independent(self):
        src = (Path(__file__).resolve().parents[1] /
               "daily_classification_spotcheck.py").read_text()
        # assertFalse, not assertNotIn: assertNotIn's failure message prints the
        # whole haystack, and a 200-line source dump buries the one sentence
        # that says what is wrong.
        self.assertFalse("independently confirmed by two LLM passes" in src,
                         "the reason written to the PUBLIC corrections log still "
                         "claims two independent passes; they are one model called "
                         "twice and share every bias")
        self.assertFalse("double-confirmed label fix" in src,
                         "the run summary still calls one model's repeat answer a "
                         "double confirmation")


if __name__ == "__main__":
    unittest.main()
