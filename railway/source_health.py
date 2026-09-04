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
import signal
import threading
import time

import requests

import host_call
import http_retry

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# A COLLECTOR THAT IS KILLED MID-RUN MUST STILL ANSWER ITS OWN `running` NOTE.
#
# Two platforms end a collector from the outside, and both do it with SIGTERM
# followed by a short grace and then SIGKILL: Railway replaces the cron
# container on every deploy (~10s grace), and GitHub cancels a step on
# `timeout-minutes` or a concurrency group (SIGTERM, then a kill ~7.5s later).
# Nothing here handled either, so the process died with its `running` note on
# the ledger and no terminal note after it. Measured: gdelt 2026-08-26 and
# 2026-09-03, gdelt_historical 2026-08-27 and 2026-09-04, archive_backfill
# 2026-08-30 - five orphans in `ops_status [2e]`, each with a FRESH
# `checked_at` that counted as OK and reset its own staleness clock.
#
# So this module keeps the set of sources whose `running` note landed and has
# not yet been answered, and installs ONE signal handler (once, on the first
# `running` note) that posts a `degraded` terminal note for each of them and
# then re-raises the signal, so the platform's own exit semantics (143) are
# preserved. `run_completion` already reads `degraded` as a finish.
#
# The posting is BOUNDED: one attempt per source, a short per-request timeout
# and a total budget well inside the shortest grace window, because a handler
# that outlives the grace is killed with the note unsent, which is exactly the
# state it exists to prevent. A failed POST prints one line and the process
# exits anyway. Second and later signals find the set already drained and do
# nothing, so a double SIGTERM cannot post twice or block the exit.
TERMINAL = ("ok", "degraded")
RUNNING = "running"
INTERRUPT_SIGNALS = (signal.SIGTERM, signal.SIGINT)
# GitHub's grace is ~7.5s and Railway's ~10s. The whole handler must finish
# inside the SHORTER one with room for the exit itself.
INTERRUPT_BUDGET_SECONDS = 5.0
INTERRUPT_POST_TIMEOUT_SECONDS = 3.0
INTERRUPTED_DETAIL = ("interrupted: {signame} before the run finished "
                      "(container replaced or job cancelled)")

_open_lock = threading.RLock()   # reentrant: the handler runs on the thread that may hold it
_open_runs = {}          # source -> the detail its `running` note carried
_handlers_installed = False
_previous_handlers = {}


def _mark_open(source, detail):
    with _open_lock:
        _open_runs[source] = detail
    _install_interrupt_handlers()


def _mark_closed(source):
    with _open_lock:
        _open_runs.pop(source, None)


def open_runs():
    """Sources whose `running` note landed and has not been answered yet."""
    with _open_lock:
        return dict(_open_runs)


def _install_interrupt_handlers():
    """Install the SIGTERM/SIGINT handler exactly once. Never raises."""
    global _handlers_installed
    if _handlers_installed:
        return
    for sig in INTERRUPT_SIGNALS:
        try:
            _previous_handlers[sig] = signal.signal(sig, _on_interrupt)
        except (ValueError, OSError) as exc:
            # Not the main thread, or a platform that refuses. Say so once;
            # the collector still runs, it just cannot answer a kill.
            print(f"source-health: could not install {sig!s} handler ({exc}); "
                  f"an interrupted run will leave its 'running' note open")
            return
    _handlers_installed = True


def _post_interrupted_note(source, signame, deadline):
    """ONE attempt, bounded by both its own timeout and the shared deadline.

    Deliberately NOT publish_source_health(): that retries three times with
    sleeps of 5 and 10 seconds, which is longer than the grace window.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        print(f"source-health: interrupt budget spent before {source} could be "
              f"closed; its 'running' note stays open")
        return False
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return False
    detail = INTERRUPTED_DETAIL.format(signame=signame)
    try:
        response = requests.post(
            f"{site}/wp-json/layoffs/v1/source-health",
            json={"source": source, "status": "degraded", "entries": 0,
                  "detail": detail[:240]},
            headers={"X-Layoff-API-Key": key, "User-Agent": UA},
            timeout=min(INTERRUPT_POST_TIMEOUT_SECONDS, remaining),
        )
        if response.status_code >= 400:
            print(f"source-health: interrupted note for {source} refused "
                  f"(HTTP {response.status_code}); exiting anyway")
            return False
        print(f"source-health: {source} closed as degraded ({detail})")
        return True
    except Exception as exc:
        print(f"source-health: interrupted note for {source} failed ({exc}); "
              f"exiting anyway")
        return False


def close_open_runs_as_interrupted(signame):
    """Post the terminal note for every open run. Idempotent BY THE DRAIN:
    the set is emptied under the lock before any request is made, so a second
    call (a second signal, or a signal that lands while the first handler is
    mid-POST) finds nothing and posts nothing. Returns the sources attempted."""
    with _open_lock:
        pending = list(_open_runs.items())
        _open_runs.clear()
    deadline = time.monotonic() + INTERRUPT_BUDGET_SECONDS
    attempted = []
    for source, _detail in pending:
        _post_interrupted_note(source, signame, deadline)
        attempted.append(source)
    return attempted


def _reraise(signum):
    """Hand the signal back to the platform's default disposition.

    SIG_DFL for SIGTERM/SIGINT terminates the process BY that signal, so a
    shell or a runner reads the conventional 128+N (143 for SIGTERM). If the
    kill somehow returns, exit with that number directly rather than resume a
    collector the platform has already decided to end.
    """
    try:
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
    except Exception:
        pass
    os._exit(128 + int(signum))


def _on_interrupt(signum, frame):
    try:
        signame = signal.Signals(signum).name
    except Exception:
        signame = f"signal {signum}"
    try:
        close_open_runs_as_interrupted(signame)
    except Exception as exc:
        # A bookkeeper that crashes while recording a kill has recorded
        # nothing; never let it also hide the kill.
        print(f"source-health: interrupt handler failed ({exc}); exiting anyway")
    _reraise(signum)


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
            # The pairing bookkeeping, AFTER the note landed: a `running` that
            # never reached the ledger has nothing to orphan, and a terminal
            # note closes its run only once the ledger holds it, so a kill
            # that lands mid-POST still gets answered.
            if status == RUNNING:
                _mark_open(source, detail)
            elif status in TERMINAL:
                _mark_closed(source)
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
