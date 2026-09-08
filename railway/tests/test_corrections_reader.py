"""The corrections log narrows a headline investigation. It never closes one.

Written with the guard on 2026-09-08, after `headline_containment` reported
~42,000 jobs gone and could not say why. The cause -- a Bloomberg duplicate of
the Volkswagen 50,000 event, merged away after five days of double-counting --
was published in the corrections log the entire time. A merge hard-deletes its
duplicate, so /changed-rows is structurally blind to it.

The danger in fixing that is obvious and is what these tests exist for: it
would be very easy, and completely wrong, to let "a correction was disclosed"
stand in for "the move is explained". The log records how many ROWS were
removed and never how many JOBS they carried, so it can point at a cause and
can never do the arithmetic. A failing check must still fail.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from railway.corrections_reader import (
    REMOVING_ACTIONS,
    DisclosedRemovals,
    fetch_removals,
)

_LOG = {
    "entries": [
        {"date": "2026-09-08", "action": "merged", "count": 8,
         "reason": "Daily cross-source dedup: same layoff event reported by multiple sources"},
        {"date": "2026-09-08", "action": "enriched", "count": 51,
         "reason": "Automated industry classification"},
        {"date": "2026-09-07", "action": "removed", "count": 1,
         "reason": "Source-verification audit: SEC exhibit reports $4.320 million"},
        {"date": "2026-09-07", "action": "corrected", "count": 3,
         "reason": "Reason-tag backfill"},
    ]
}


def _opener(payload, status=200):
    def _open(req, timeout=None):
        class _R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R(json.dumps(payload).encode())
    return _open


def test_only_removing_actions_are_counted() -> None:
    """Enrichment and field corrections do not remove jobs from the corpus.

    Mutation guard: drop the REMOVING_ACTIONS filter and this fails, because
    the 51 enriched and 3 corrected rows join the total and the guard starts
    pointing at a backfill job as the cause of a headline drop.
    """
    r = fetch_removals("https://example.test/blog", "2026-09-07", opener=_opener(_LOG))
    assert r.consulted is True
    assert r.rows == 9, "expected 8 merged + 1 removed, not the enrichment rows"
    assert {e["action"] for e in r.entries} <= REMOVING_ACTIONS


def test_an_unreachable_log_is_unknown_and_never_an_all_clear() -> None:
    """The whole failure family this repo keeps digging out of.

    Mutation guard: make the except branch return consulted=True and this
    fails, because a network blip would then read as "nothing was removed".
    """
    def _boom(req, timeout=None):
        raise urllib.error.URLError("no route to host")

    r = fetch_removals("https://example.test/blog", "2026-09-07", opener=_boom)
    assert r.consulted is False
    assert r.rows == 0
    text = r.summary().lower()
    assert "unknown" in text
    assert "no removal" not in text, (
        "an unreadable log must not be worded like an empty one"
    )


def test_an_empty_window_says_so_positively() -> None:
    """Distinct from unreachable: here we DID look, and there was nothing."""
    r = fetch_removals("https://example.test/blog", "2026-09-07",
                       opener=_opener({"entries": []}))
    assert r.consulted is True
    assert "discloses NO removal" in r.summary()


def test_the_summary_never_claims_to_explain_the_move() -> None:
    """It offers a candidate. The log holds rows, not job counts, so it cannot
    do the arithmetic and must not sound as though it did."""
    text = fetch_removals("https://example.test/blog", "2026-09-07",
                          opener=_opener(_LOG)).summary()
    assert "CANDIDATE" in text
    assert "not a verdict" in text
    for overclaim in ("explains the move", "accounts for", "therefore", "resolved"):
        assert overclaim not in text.lower()


def test_the_disclosed_reason_reaches_the_reader() -> None:
    """The point is that a human reads the cause without further digging."""
    text = fetch_removals("https://example.test/blog", "2026-09-07",
                          opener=_opener(_LOG)).summary()
    assert "cross-source dedup" in text
    assert "Source-verification audit" in text


def test_a_garbled_response_is_unknown_not_empty() -> None:
    def _junk(req, timeout=None):
        class _R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R(b"<html>not json</html>")

    r = fetch_removals("https://example.test/blog", "2026-09-07", opener=_junk)
    assert r.consulted is False
    assert "unknown" in r.summary().lower()


@pytest.mark.parametrize("action", sorted(REMOVING_ACTIONS))
def test_both_removing_actions_are_recognised(action: str) -> None:
    payload = {"entries": [{"date": "2026-09-08", "action": action, "count": 2,
                            "reason": "x"}]}
    assert fetch_removals("https://e.test/blog", "2026-09-07",
                          opener=_opener(payload)).rows == 2


def test_a_negative_or_absent_count_cannot_inflate_the_total() -> None:
    payload = {"entries": [
        {"date": "2026-09-08", "action": "merged", "count": -5, "reason": "x"},
        {"date": "2026-09-08", "action": "removed", "reason": "x"},
    ]}
    assert fetch_removals("https://e.test/blog", "2026-09-07",
                          opener=_opener(payload)).rows == 0
