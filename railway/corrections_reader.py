"""What the corrections log says left the corpus, in a window.

WHY THIS EXISTS. On 2026-09-08 `headline_containment` reported ~42,000 jobs
gone from the worldwide headline and could not say why. Its own text offered
two mechanisms and admitted it could not tell them apart. It was neither: the
rows had been DELETED, and the endpoint built for headline forensics says in
its own metadata that deletions are invisible to it, because a merge
hard-deletes its duplicate and leaves no ``updated_at``.

The cause was public the entire time. The corrections log had:

    2026-09-08: 8 entries merged. Daily cross-source dedup ...
    2026-09-07: 1 entry removed. Source-verification audit: SEC exhibit
                reports $4.320 million ... it states no absolute worker count.

An hour of forensics to read two lines the site was already publishing. The
guard could not read them because the log rendered only as HTML on the tracker
page; ``/corrections`` now serves the same entries as JSON.

WHAT THIS DOES NOT DO, AND MUST NOT. It does not clear a failing check, and it
must never be made to. A disclosed removal is a CANDIDATE EXPLANATION, not a
verdict: the log records that eight rows were merged, not how many jobs they
carried, so it can narrow an investigation and can never close one. Wiring
"corrections exist, therefore pass" would convert a true alarm into a rubber
stamp, which is the failure this repo keeps digging out of.

UNKNOWN stays UNKNOWN. If the endpoint cannot be read, the guard says the log
could not be consulted, never that there was nothing in it.

Pure stdlib. Read-only. No keys: this endpoint is public because the log it
serves is already published on the page.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

_TIMEOUT = 15

#: Browser-ish, because ModSecurity blocks library user agents on this host.
_UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

#: Actions that REMOVE jobs from the corpus. A merge hard-deletes its
#: duplicate and a removal trashes the row; both leave no updated_at, which is
#: precisely why /changed-rows cannot see them and this module exists.
REMOVING_ACTIONS: frozenset[str] = frozenset({"merged", "removed"})


def entry_jobs(entry):
    """The jobs a log entry discloses, or None for "we did not measure it".

    None and 0 are DIFFERENT ANSWERS and the difference is the whole point: 0
    is a removal of rows that carried no headcount, None is a removal whose
    headcount nobody recorded. A negative or unparsable figure is not a
    measurement either, so it reads None rather than being clamped to 0 --
    clamping would turn a garbled write into a confident zero.
    """
    if not isinstance(entry, dict) or "jobs" not in entry:
        return None
    raw = entry["jobs"]
    if raw is None or isinstance(raw, bool) or isinstance(raw, (list, dict)):
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return None if value < 0 else value


@dataclass(frozen=True)
class DisclosedRemovals:
    """Removals the site disclosed in a window, as candidate explanations."""

    consulted: bool
    rows: int = 0
    entries: list[dict] = field(default_factory=list)
    error: str = ""

    @property
    def measured_jobs(self) -> int:
        """Jobs disclosed by the entries that carry a figure. NOT a window total:
        read it with `unmeasured`, never on its own."""
        return sum(j for j in (entry_jobs(e) for e in self.entries) if j is not None)

    @property
    def unmeasured(self) -> list:
        """The removing entries in this window that record no jobs figure."""
        return [e for e in self.entries if entry_jobs(e) is None]

    @property
    def jobs_accounted(self) -> bool:
        """True only if the window was read AND every removal in it is measured."""
        return self.consulted and not self.unmeasured

    def summary(self) -> str:
        """One line for a guard message. Never asserts that it explains the move."""
        if not self.consulted:
            return (
                f"the corrections log could not be consulted ({self.error}), so "
                f"whether a disclosed removal explains this is UNKNOWN"
            )
        if not self.entries:
            return (
                "the corrections log discloses NO removal or merge in this "
                "window, so a deleted row is not the explanation"
            )
        if self.jobs_accounted:
            carried = f"carrying {self.measured_jobs:,} disclosed job(s)"
        else:
            n = len(self.unmeasured)
            carried = (f"of which {n} "
                       f"{'entry records' if n == 1 else 'entries record'} no job "
                       f"total, so what those carried is UNKNOWN")
        parts = []
        for e in self.entries[:4]:
            reason = (e.get("reason") or "").strip()
            if len(reason) > 110:
                reason = reason[:107] + "..."
            parts.append(
                f"{e.get('date')}: {e.get('count')} {e.get('action')} — {reason}"
            )
        more = "" if len(self.entries) <= 4 else f" (+{len(self.entries) - 4} more)"
        return (
            f"the corrections log discloses {self.rows} row(s) removed or merged "
            f"in this window, {carried}, which is a CANDIDATE explanation and not a "
            f"verdict: "
            + "; ".join(parts)
            + more
        )


def fetch_removals(site_url: str, since: str, opener=None) -> DisclosedRemovals:
    """Disclosed removals on or after ``since`` (YYYY-MM-DD). Never raises."""
    url = f"{site_url.rstrip('/')}/wp-json/layoffs/v1/corrections?since={since}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return DisclosedRemovals(consulted=False, error=f"unreachable: {exc}")
    except (ValueError, json.JSONDecodeError) as exc:
        return DisclosedRemovals(consulted=False, error=f"unreadable: {exc}")
    if not isinstance(body, dict):
        return DisclosedRemovals(consulted=False, error="unexpected response shape")
    entries = [
        e
        for e in (body.get("entries") or [])
        if isinstance(e, dict) and str(e.get("action", "")).lower() in REMOVING_ACTIONS
    ]
    return DisclosedRemovals(
        consulted=True,
        rows=sum(max(0, int(e.get("count") or 0)) for e in entries),
        entries=entries,
    )
