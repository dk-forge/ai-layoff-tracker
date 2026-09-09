"""Make pytest-style test functions run under this suite's unittest runner.

WHY THIS EXISTS. This repository has no pytest (see #288). The runner is
`railway/run_tests.py`, which is `unittest`, and unittest collects TestCase
METHODS. A module-level `def test_x(monkeypatch)` is collected as nothing at
all: it does not fail, it does not error, it does not appear. It is silently
absent.

On 2026-09-09 `test_mailbox_janitor.py` and `test_dmarc_fetch.py` were both
found to collect ZERO tests. They had been on main since 2026-09-08 and had
never run once. In the same window every mailbox-janitor run on record was
failing, on a defect those tests would not have caught anyway because none of
them was executing. A guard that does not run is not a weaker guard, it is a
false one, because its presence is what stops anyone looking.

`bind(namespace, name)` builds a real TestCase out of the module's `test_*`
functions, passing each one a minimal `monkeypatch` with the two methods those
tests use, undone after every test. It keeps the test bodies exactly as they
are, so nothing is re-litigated by the port.

`railway/tests/test_test_groups.py` fails on any module that collects zero
tests, so this cannot go quiet again.
"""
from __future__ import annotations

import inspect
import unittest


class MonkeyPatch:
    """The sliver of pytest's fixture these tests use, with an undo."""

    def __init__(self) -> None:
        self._undo: list = []

    def setattr(self, target, name, value) -> None:
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def setenv(self, name: str, value: str) -> None:
        import os
        self._undo.append((os.environ, name, os.environ.get(name)))
        os.environ[name] = value

    def delenv(self, name: str, raising: bool = True) -> None:
        import os
        if name in os.environ:
            self._undo.append((os.environ, name, os.environ[name]))
            del os.environ[name]
        elif raising:
            raise KeyError(name)

    def undo(self) -> None:
        import os
        for target, name, old in reversed(self._undo):
            if target is os.environ:
                if old is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old
            else:
                setattr(target, name, old)
        self._undo.clear()


def _method(fn):
    takes_patch = "monkeypatch" in inspect.signature(fn).parameters

    def run(self):
        mp = MonkeyPatch()
        try:
            fn(mp) if takes_patch else fn()
        finally:
            mp.undo()

    run.__name__ = fn.__name__
    run.__doc__ = fn.__doc__
    return run


def bind(namespace: dict, class_name: str) -> type:
    """Turn every `test_*` function in `namespace` into a TestCase method."""
    attrs = {
        name: _method(obj)
        for name, obj in sorted(namespace.items())
        if name.startswith("test_") and inspect.isfunction(obj)
    }
    if not attrs:
        raise AssertionError(
            f"{class_name}: bridged a module with no test functions in it")
    return type(class_name, (unittest.TestCase,), attrs)
