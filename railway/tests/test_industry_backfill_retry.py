"""Guards for the industry-backfill scan's transient-error handling.

The backfill scans ~140 pages of blank-industry rows before doing any work. A
single deep page answering 500 (which the shared host does while a large WARN
import is loading it) used to abort the whole run, so the job failed daily and
the backlog never drained. These tests pin the recovery semantics.
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_SRC = open(os.path.join(os.path.dirname(__file__), "..", "industry_backfill.py")).read()
_BODY = _SRC[_SRC.index("_TRANSIENT = {"):_SRC.index("def fetch_candidates")]


class _Resp:
    def __init__(self, code):
        self.status_code = code


class _FakeRequests:
    RequestException = Exception

    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.calls = 0

    def get(self, *a, **k):
        self.calls += 1
        value = self.sequence.pop(0)
        if isinstance(value, Exception):
            raise value
        return _Resp(value)


def _load(sequence):
    fake = _FakeRequests(sequence)
    ns = {"requests": fake, "time": types.SimpleNamespace(sleep=lambda *_: None), "UA": {}}
    exec(compile(_BODY, "industry_backfill_slice", "exec"), ns)
    return ns["_get_with_retry"], fake


def test_recovers_from_a_transient_500():
    get, fake = _load([500, 200])
    assert get("u", {}).status_code == 200
    assert fake.calls == 2


def test_returns_none_when_transient_persists():
    # None (not a 5xx response) is what lets the caller continue with the pages
    # it already has instead of raising and discarding the run.
    get, fake = _load([500, 503, 504])
    assert get("u", {}) is None
    assert fake.calls == 3


def test_a_real_error_is_passed_through_not_retried():
    # 403/404 are not transient: retrying wastes time and the caller must still
    # raise on them.
    get, fake = _load([403])
    assert get("u", {}).status_code == 403
    assert fake.calls == 1


def test_network_exception_is_retried_then_reported_as_none():
    get, fake = _load([Exception("boom"), Exception("boom"), Exception("boom")])
    assert get("u", {}) is None
    assert fake.calls == 3
