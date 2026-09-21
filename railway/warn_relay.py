"""Scrape the US WARN registers from one address, post them from another.

WHY THIS EXISTS. Two walls face opposite ways. ChemiCloud's bot protection
challenges every datacenter address except the ONE whitelisted VPS, so every
job that touches asktherecruiter.com moved to that VPS on 2026-09-16 (#344).
The VPS is in Europe, and a number of US state sites refuse or silently drop
non-US addresses: from 2026-09-16 every daily import lost AZ, CT, DE, ME, MO,
NE, OR, RI, TN, UT, VT (generic tier), FL, GA, ID, KY, LA (legacy custom tier)
and KS, NM (new-states tier), with connect timeouts, HTTP 403s and block pages
in the log, while the runs of 2026-09-09 to 2026-09-15 on a US-hosted runner
lost none of them. Nothing in any parser was wrong.

So the import is split at its only clean seam. A job on a US-hosted runner
calls the three US scrape seams and writes what they returned to a file (it
holds no WP_API_KEY and no OpenRouter key: it can read public registers and
nothing else). The VPS job downloads that file and uses it IN PLACE of scraping
those three seams itself; everything after the seam (sanitiser, floors, drift,
freshness, /bulk, health notes) runs exactly as before, on the VPS, once.

FAIL TOWARDS TODAY'S BEHAVIOUR. `load()` returns None for a missing, unreadable,
stale, wrong-version or wrong-parameter file, and the caller then scrapes for
itself, which is precisely what it did before this module existed. A relay can
therefore never make a run worse than the run it replaces, and an absent relay
is printed, not hidden.

The three seams and their side channels, all carried:
  generic  sources.warn.pull_warn(states, min_employees, start_date)
  custom   sources.warn_custom.pull_warn_custom(states) + SOURCE_UNREACHABLE
  new      sources.warn_new_states.NEW_CUSTOM_STATES[st]() per state, with the
           per-state exception text, because warn_import treats "raised" and
           "returned 0" differently (errored states feed the freshness check).
"""
import json
import os
import sys
import time

VERSION = 1
#: A relay older than this is not this run's scrape. The scrape job finishes
#: minutes before the import job starts; six hours covers a queue on the VPS
#: label and nothing longer.
MAX_AGE_SECONDS = 6 * 3600


def _params(states, min_employees, start_date):
    return {"states": [str(s).upper() if str(s).lower() != "all" else "all" for s in states],
            "min_employees": int(min_employees or 0),
            "start_date": start_date or ""}


def scrape(states, min_employees=0, start_date="", *, now=time.time):
    """Run the three US seams and return the relay document (a plain dict)."""
    from sources.warn import pull_warn
    from sources import warn_custom
    doc = {"v": VERSION, "params": _params(states, min_employees, start_date)}
    doc["generic"] = pull_warn(states, min_employees=min_employees, start_date=start_date)
    doc["custom"] = warn_custom.pull_warn_custom(states)
    doc["custom_unreachable"] = dict(warn_custom.SOURCE_UNREACHABLE)
    new = {}
    if os.environ.get("WARN_SKIP_NEW_STATES") != "1":
        from sources.warn_new_states import NEW_CUSTOM_STATES
        scrape_all = len(states) == 1 and str(states[0]).lower() == "all"
        wanted = (list(NEW_CUSTOM_STATES) if scrape_all
                  else [s.upper() for s in states if s.upper() in NEW_CUSTOM_STATES])
        for st in wanted:
            try:
                got = NEW_CUSTOM_STATES[st]()
                print(f"WARN {st} (new importer, relay): {len(got)} notices kept")
                new[st] = {"entries": got, "error": None}
            except Exception as exc:  # carried, never swallowed: see module docstring
                print(f"WARN {st} (new importer, relay) failed: {exc}")
                new[st] = {"entries": [], "error": str(exc) or type(exc).__name__}
    doc["new"] = new
    doc["scraped_at"] = int(now())
    return doc


def dump(path, states, min_employees=0, start_date=""):
    doc = scrape(states, min_employees, start_date)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
    print(f"warn relay written: generic={len(doc['generic'])} custom={len(doc['custom'])} "
          f"new={sum(len(v['entries']) for v in doc['new'].values())} -> {path}")
    return doc


def load(path, states, min_employees=0, start_date="", *, now=time.time):
    """The relay document, or None with the reason printed. Never raises."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"::warning:: warn relay unreadable ({exc}); scraping from this runner instead")
        return None
    why = None
    if not isinstance(doc, dict) or doc.get("v") != VERSION:
        why = "wrong version"
    elif doc.get("params") != _params(states, min_employees, start_date):
        why = "scraped with different parameters than this import was asked for"
    elif not isinstance(doc.get("scraped_at"), int) or now() - doc["scraped_at"] > MAX_AGE_SECONDS:
        why = "stale"
    elif now() - doc["scraped_at"] < -300:
        why = "dated in the future"
    elif not (isinstance(doc.get("generic"), list) and isinstance(doc.get("custom"), list)
              and isinstance(doc.get("custom_unreachable"), dict)
              and isinstance(doc.get("new"), dict)):
        why = "malformed"
    if why:
        print(f"::warning:: warn relay ignored ({why}); scraping from this runner instead")
        return None
    print(f"warn relay accepted: generic={len(doc['generic'])} custom={len(doc['custom'])} "
          f"new-states={sorted(doc['new'])}")
    return doc


def main():
    raw = (os.environ.get("WARN_STATES") or "all").strip()
    states = ["all"] if raw.lower() == "all" else [s.strip().upper() for s in raw.split(",") if s.strip()]
    path = os.environ.get("WARN_RELAY_FILE") or "warn_relay.json"
    dump(path, states, int(os.environ.get("WARN_MIN_EMPLOYEES") or 0),
         os.environ.get("WARN_START") or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
