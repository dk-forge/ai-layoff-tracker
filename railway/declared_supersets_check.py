"""Every reviewer-declared superset membership is reflected on the live rows.

WHY. `alt_reconcile_supersets()` erases every `superset_of` mark and re-derives
them on each run. A membership two reviewers DECLARED (staged announcements of
one programme, counted once at the latest announced size) lives in a separate
store, `alt_declared_supersets`, and the reconciler re-applies it after its
clean slate (includes/declared-supersets.php). This asks the one question that
store cannot answer about itself: did that re-application actually land? A
declaration that is stored and not reflected is an over-count already published
(Estee Lauder, 2026-09-21: 15,200 jobs), and nothing else would say so.

ONE REQUEST to the read-only `/declared-supersets`, which returns each
declaration beside the member's live `superset_of`. Never a page walk.

Three states, never two. No read, a non-JSON body or a build that predates the
route is UNKNOWN. An empty store is a PASS that says it checked nothing, in
words, because "0 declarations" and "could not read" must not look alike.

The definition lives here ONCE and is appended to data_integrity.INVARIANTS, so
the test suite, ops_status and the weekly digest read the same thing.
"""
import json
import urllib.error
import urllib.parse

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"


def _di():
    """data_integrity lazily: it imports this module at its bottom."""
    import data_integrity
    return data_integrity


def declared_superset_findings(declarations):
    """Pure. The declarations that the live rows do NOT reflect, with why."""
    bad = []
    for d in declarations:
        if not isinstance(d, dict):
            bad.append({"member_id": None, "why": "malformed declaration"})
            continue
        member, primary = d.get("member_id"), d.get("primary_id")
        if not d.get("member_exists"):
            why = "member row no longer exists; withdraw the declaration"
        elif not d.get("primary_exists"):
            why = (f"primary {primary} no longer exists, so the member counts again; "
                   "re-declare against the surviving total or withdraw")
        elif d.get("member_superset_of") != primary:
            why = (f"live superset_of is {d.get('member_superset_of')}, declared {primary}: "
                   "the reconciler did not re-apply it")
        elif d.get("primary_superset_of"):
            why = (f"primary {primary} is itself marked a member of "
                   f"{d.get('primary_superset_of')} (chain)")
        else:
            continue
        bad.append({"member_id": member, "primary_id": primary, "why": why})
    return bad


class DeclaredSupersetsInvariant:
    key = "declared_supersets_reflected"
    label = "Reviewer-declared programme totals are counted once"
    reads_live_data = True

    def run(self, ctx):
        di = _di()
        url = BASE + "declared-supersets?" + urllib.parse.urlencode({"cb": ctx.cachebust})
        try:
            payload = json.loads(ctx.fetch(url, ctx.timeout))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return di.Result(self, di.UNKNOWN, pending=True, error=exc,
                                 detail="/declared-supersets is not on the deployed build yet "
                                        "(HTTP 404): not checked, NOT passing")
            why = ("site is in its deploy maintenance window (HTTP 503)"
                   if exc.code == 503 else f"/declared-supersets returned HTTP {exc.code}")
            return di.Result(self, di.UNKNOWN, detail=why, error=exc)
        except Exception as exc:
            return di.Result(self, di.UNKNOWN,
                             detail=f"could not read /declared-supersets ({exc})", error=exc)

        decls = payload.get("declarations") if isinstance(payload, dict) else None
        if not isinstance(decls, list) or payload.get("count") != len(decls):
            return di.Result(self, di.UNKNOWN,
                             detail="/declared-supersets answered without a coherent "
                                    "declarations list: not checked, NOT passing")
        if not decls:
            return di.Result(self, di.PASS, observed=0,
                             detail="the store was read and holds 0 declarations, so there "
                                    "was nothing to reflect")
        bad = declared_superset_findings(decls)
        if bad:
            return di.Result(self, di.FAIL, observed=len(bad),
                             detail="; ".join(f"member {b['member_id']}: {b['why']}" for b in bad[:6])
                                    + (" ..." if len(bad) > 6 else ""))
        jobs = sum(int(d.get("member_job_count") or 0) for d in decls)
        return di.Result(self, di.PASS, observed=0,
                         detail=f"{len(decls)} declared member(s) carrying {jobs:,} jobs are all "
                                f"marked on the live rows")
