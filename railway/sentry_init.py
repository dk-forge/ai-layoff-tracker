"""Sentry initialisation, shared by every scheduled-job entry point.

Deliberately tiny and deliberately silent when unconfigured: `init_sentry()`
is a no-op unless `SENTRY_DSN` is set, so a checkout or a workflow with no
Sentry secret behaves exactly as it did before this module existed. It never
raises — a Sentry SDK import failure or init failure must not take a data
job down with it, the same "the alarm must not depend on what it watches"
principle as `railway/opsmail.py`.

No PII, no performance tracing by default (`traces_sample_rate=0.0`):
this repo processes company layoff data, not personal data, but request
bodies and environment can still leak into breadcrumbs, so
`send_default_pii` stays False.
"""
from __future__ import annotations

import os

_initialised = False

#: Provider hiccups the callers already retry (spend.metered_call) and degrade
#: on. The Sentry OpenAI integration reports each failed SDK call as UNHANDLED
#: before our except clause runs (AI-LAYOFF-TRACKER-2/-4/-5/-6); the callers log
#: a handled warning on final failure instead.
_HANDLED_PROVIDER_ERRORS = frozenset(
    {"APITimeoutError", "APIConnectionError", "RateLimitError"})


def before_send(event, hint):
    """Drop transient OpenAI-SDK errors auto-captured with mechanism openai."""
    try:
        for v in (event.get("exception") or {}).get("values") or []:
            if (v.get("type") in _HANDLED_PROVIDER_ERRORS
                    and (v.get("mechanism") or {}).get("type") == "openai"):
                return None
    except Exception:  # noqa: BLE001 - a filter must never break reporting
        pass
    return event


def init_sentry(component: str | None = None) -> bool:
    """Initialise Sentry once per process if SENTRY_DSN is set. Returns True
    if it initialised (or already had), False if it's a no-op (no DSN or the
    SDK could not be set up). Never raises."""
    global _initialised
    if _initialised:
        return True
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment="production",
            send_default_pii=False,
            traces_sample_rate=0.0,
            before_send=before_send,
        )
        if component:
            sentry_sdk.set_tag("component", component)
        _initialised = True
        return True
    except Exception:  # noqa: BLE001 - Sentry must never break the job it watches
        return False
