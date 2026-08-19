"""The one place a `requests` stub is stood up for the test suite.

Several modules under test (`warn_import`, `health_digest`, `seen_urls`,
`archive_sources`, the watchlist) import `requests` at module scope, so a suite
running offline needs something in `sys.modules["requests"]`. `sys.modules` is
process-global and a test module CANNOT restore it in tearDown: the module
under test binds `requests` at import time and keeps that reference for the rest
of the run. So the only isolation that works is that every installer agrees on
ONE surface, installed idempotently, regardless of who gets there first.

Six modules used to each install their own partial stub and skip when one was
already present, which made the surface a function of unittest's discovery
order. `tests/test_digest_subscription.WeeklyEmailWiring` passed when the module
ran alone (its own stub defined `get`) and ERRORed with "module 'requests' does
not have the attribute 'get'" in a full-suite run, because a warn test's stub -
`RequestException` and nothing else - had claimed the slot first. Five red tests
that had nothing to do with the code under test.

Two rules keep it that way:

* `install()` COMPLETES an existing stub rather than skipping it, so a stub left
  by an older code path still ends up with the full surface.
* The stub is a fallback, not a preference. If the real `requests` is
  importable (CI installs it from the lock) it is used untouched, so local and
  CI exercise the same objects.
"""
import sys
import types

# Every attribute any module under test touches on `requests`. Add here, never
# in a test module: a per-module addition is how the surface became
# order-dependent in the first place.
_EXCEPTIONS = ("RequestException", "ConnectionError", "Timeout", "HTTPError",
               "TooManyRedirects", "ReadTimeout", "ConnectTimeout")
_VERBS = ("get", "post", "put", "head", "delete", "patch", "request")


def _no_network(name):
    def _call(*_a, **_k):
        raise RuntimeError(
            "no network in tests: requests.%s() was called unpatched" % name)
    return _call


def install():
    """Return a usable `requests` module, standing a complete stub in if needed.

    Idempotent, and safe to call at import time or inside a test.
    """
    mod = sys.modules.get("requests")
    if mod is None:
        try:                                # the real thing wins when present
            import requests as mod
        except ImportError:
            mod = types.ModuleType("requests")
            sys.modules["requests"] = mod
    if getattr(mod, "__file__", None):      # a real install, not anyone's stub
        return mod                          # -- never decorate it

    for name in _EXCEPTIONS:                # complete, never skip
        if not hasattr(mod, name):
            setattr(mod, name, type(name, (Exception,), {}))
    for name in _VERBS:
        if not hasattr(mod, name):
            setattr(mod, name, _no_network(name))
    if not hasattr(mod, "Session"):
        class Session:
            def __getattr__(self, name):
                return _no_network("Session." + name)

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False
        mod.Session = Session
    if not hasattr(mod, "exceptions"):
        exc = types.ModuleType("requests.exceptions")
        for name in _EXCEPTIONS:
            setattr(exc, name, getattr(mod, name))
        mod.exceptions = exc
        sys.modules["requests.exceptions"] = exc
    return mod
