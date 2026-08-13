"""Publish collector health after each autonomous source attempt.

Health is deliberately separate from row publication: an empty successful
response is visible as ``ok`` with zero entries, while exceptions are recorded
as ``degraded``. The public endpoint lets researchers see a coverage gap
instead of mistaking silence for zero layoffs.

WHY THERE ARE TWO ENTRY POINTS
------------------------------
`report_source_health` is the telemetry one, and it is a bool because almost
every caller uses it AFTER the work is done, where the only sane answer to a
failed note is a warning.

`publish_source_health` returns WHICH of the three outcomes happened, and it
exists for the handful of jobs that publish a `running` note as a PRECONDITION
and hard-raised when it failed. That made the health ledger's own availability
a precondition for the job, so a maintenance window on the host turned into a
red run before any work was attempted. Those callers need to tell "the host
never answered" (defer, nothing was attempted) from "the host refused us"
(a wrong or missing key — settled, and it fails identically tomorrow).
"""
import os
import requests

import host_call
import http_retry

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"


def publish_source_health(source, status, entries=0, detail=""):
    """Write one health note. Returns host_call.OK / DEFERRED / FAILURE.

    Never raises: this is called from failure paths, and a bookkeeper that
    crashes while recording a failure has recorded nothing.
    """
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        # Settled, not transient: it would fail identically tomorrow.
        print("source-health skipped: WP_SITE_URL or WP_API_KEY missing")
        return http_retry.FAILURE
    # The health ledger is TELEMETRY, and the shared host answers a transient 5xx
    # now and then. A one-off 500 here used to sink a whole data job (the run had
    # already done its work); retry the write so a blip self-heals, and never let
    # it raise - the caller decides, and a telemetry write is never worth failing
    # a completed job over.
    #
    # This file HELD ITS OWN COPY of the transient set until 2026-08-12. That is
    # the drift `http_retry` exists to prevent, so it now imports the one
    # definition. The loop stays here because this write must never raise.
    import time as _time
    outcome = http_retry.DEFERRED
    for attempt in range(3):
        try:
            response = requests.post(
                f"{site}/wp-json/layoffs/v1/source-health",
                json={"source": source, "status": status, "entries": entries, "detail": detail[:240]},
                headers={"X-Layoff-API-Key": key, "User-Agent": UA},
                timeout=20,
            )
            if response.status_code in http_retry.TRANSIENT:
                outcome = http_retry.DEFERRED
                if attempt < 2:
                    _time.sleep(5 * (attempt + 1))
                    continue
                print(f"source-health for {source}: HTTP {response.status_code} "
                      f"after {attempt + 1} attempts (non-fatal)")
                return outcome
            if response.status_code >= 400:
                # A real answer we do not accept. Retrying a settled "no" only
                # makes the run longer and the answer is the same.
                print(f"source-health REFUSED for {source}: HTTP "
                      f"{response.status_code} (non-fatal here; the caller decides)")
                return http_retry.FAILURE
            return http_retry.OK
        except Exception as exc:
            outcome = http_retry.DEFERRED
            if attempt < 2:
                _time.sleep(5 * (attempt + 1))
                continue
            print(f"source-health report failed for {source} (non-fatal): {exc}")
    return outcome


def report_source_health(source, status, entries=0, detail=""):
    """Bool wrapper: did the note land? The shape every existing caller uses."""
    return publish_source_health(source, status, entries, detail) == http_retry.OK


def require_running_note(job, source, detail):
    """Publish a `running` precondition note, or say what to do about it.

    Returns None when the note landed. Otherwise returns the exit code the job
    should use: a deferral (exit 0, counted) when the host never answered, and
    a raise when it refused us, because a wrong key is not an outage.
    """
    outcome = publish_source_health(source, "running", 0, detail)
    if outcome == http_retry.OK:
        return None
    if outcome == http_retry.DEFERRED:
        return host_call.defer(
            job, f"the source-health ledger would not accept the 'running' note "
                 f"for {source}; nothing was attempted")
    raise RuntimeError(
        f"Could not publish {source} running health status: the host refused "
        f"the write (check WP_API_KEY)")
