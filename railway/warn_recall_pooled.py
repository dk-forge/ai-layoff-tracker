#!/usr/bin/env python3
"""Every published US WARN recall figure, DERIVED from the committed measurements.

WHY THIS EXISTS
---------------
`tests/test_cadence_is_derived.py` is the precedent and it was written from a
real incident: the ingest cadence halved, the two surfaces that COMPUTED their
copy followed, and every surface that had the number TYPED into it went on
saying the old one -- the Sources page seven times, the FAQ twice, 182 rows of a
generated country table, and a methodology page that contradicted itself four
lines apart, live. The rule that came out of it is the one this module
implements for recall: **never type a figure a surface can compute.**

Wave 1's results document types 99/100, four per-state cells, three size bands
and a census figure by hand. They were right on the day they were written. This
module recomputes all of them, plus wave 2's, plus the SEVEN-STATE POOLED figure
that neither document can compute on its own, and renders them into a block the
documents carry between markers. `tests/test_warn_recall_pooled.py` fails when a
committed block disagrees with what the measurement files say -- so a re-measure
that moves a number cannot leave a stale one published.

WHAT IT REFUSES TO DO
---------------------
- It does not compute anything the measurements do not contain, and it never
  writes a manifest, a measurement, or the SEC set's files.
- **It reports the editor-confirmed figure and the machine upper bound as two
  different things and never lets the second stand in for the first.** Wave 2
  has not been adjudicated: its editor-confirmed numerator is 0 by construction,
  and the block says so in words rather than showing a blank.
- **It does not pool an unadjudicated set's machine bound with an adjudicated
  set's confirmed figure.** That would be one number made of two different
  questions. The pooled row is computed once per BASIS and each is labelled.
- An UNKNOWN (an event whose query could not be completed) is excluded from
  both numerator and denominator and is reported by count, never rounded in.

USAGE
    python3 railway/warn_recall_pooled.py            # print the derived figures
    python3 railway/warn_recall_pooled.py --render   # write the blocks into the docs
    python3 railway/warn_recall_pooled.py --check    # non-zero if a doc is stale
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recall_goldset import format_interval, wilson                 # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
REF_DIR = REPO_ROOT / "docs" / "recall-reference-sets"

# (label, manifest, measurement). Adding a wave means adding one line here and
# nothing else: every figure below is computed from whatever this list holds.
WAVES = (
    ("wave 1", REF_DIR / "us-warn-ca-tx-fl-tn-2025-07_2026-06.goldset.json",
     HERE / "warn_recall_measurement.json"),
    ("wave 2", REF_DIR / "us-warn-il-oh-pa-2025-07_2026-06.goldset.json",
     HERE / "warn_recall_measurement_wave2.json"),
)
MISS_CAUSES = HERE / "warn_recall_miss_causes.json"

BEGIN = "<!-- BEGIN DERIVED: warn_recall_pooled.py -->"
END = "<!-- END DERIVED: warn_recall_pooled.py -->"
RENDER_TARGETS = (
    REF_DIR / "US-WARN-WAVE2-RESULTS-2026-09.md",
)


def _load():
    out = []
    for label, manifest_path, measurement_path in WAVES:
        if not (manifest_path.exists() and measurement_path.exists()):
            continue
        out.append((label,
                    json.loads(manifest_path.read_text(encoding="utf-8")),
                    json.loads(measurement_path.read_text(encoding="utf-8"))))
    return out


def _rate(rows, pred):
    n = len(rows)
    k = sum(1 for r in rows if pred(r))
    point, low, high = wilson(k, n) if n else (None, None, None)
    return {"n": n, "k": k, "point": point, "low": low, "high": high,
            "interval": format_interval(k, n) if n else "no sample"}


def _confirmed(r):
    return r["match_decision"] == "matched"


def _machine(r):
    return bool(r["candidates"])


def derive():
    """Every figure, from the committed files only."""
    waves = _load()
    per_state, per_band, census, unknown = {}, {}, {}, {}
    frame_detail, excluded = {}, {}
    pooled_rows, frames = [], {}
    adjudicated = {}
    for label, manifest, measurement in waves:
        prim = measurement["results"]["primary"]
        pooled_rows += [dict(r, _wave=label) for r in prim]
        unknown[label] = measurement.get("unreachable", 0)
        adjudicated[label] = any(_confirmed(r) for r in prim)
        for st in manifest["states"]:
            rows = [r for r in prim if r["state"] == st]
            per_state[st] = {
                "wave": label,
                "frame": manifest["frame_sizes"].get(st),
                "frame_jobs": manifest["frame_jobs"].get(st),
                "editor_confirmed": _rate(rows, _confirmed),
                "machine_upper_bound": _rate(rows, _machine),
            }
            frames[st] = manifest["frame_sizes"].get(st, 0)
            rng = (manifest.get("frame_notice_date_range") or {}).get(st) or {}
            frame_detail[st] = {
                "wave": label,
                "published_rows": sum(
                    1 for e in manifest["reference_events"]
                    + manifest["large_event_census"] if e["state"] == st),
                "in_window_events": manifest["frame_sizes"].get(st),
                "frame_jobs": manifest["frame_jobs"].get(st),
                "months_covered": rng.get("months_covered"),
                "notice_date_range": [rng.get("min"), rng.get("max")],
                "multi_row_events": (manifest.get("frame_multi_row_events")
                                     or {}).get(st),
            }
        for row in manifest.get("excluded_rows") or []:
            if row.get("state") not in manifest["states"]:
                continue
            reason = str(row.get("excluded_because") or "")
            key = ("notice date outside the window"
                   if reason.startswith("notice_date ")
                   else reason.split(" -- ")[0].split(" \u2014 ")[0].strip())
            excluded.setdefault(label, {})
            excluded[label][key] = excluded[label].get(key, 0) + 1
        census[label] = {
            "editor_confirmed": _rate(measurement["results"]["large_census"], _confirmed),
            "machine_upper_bound": _rate(measurement["results"]["large_census"], _machine),
        }
    for band in ("S", "M", "L"):
        rows = [r for r in pooled_rows if r["size_band"] == band]
        per_band[band] = {"editor_confirmed": _rate(rows, _confirmed),
                          "machine_upper_bound": _rate(rows, _machine)}

    total_w = sum(frames.get(st, 0) for st in per_state)
    weighted = (round(sum((frames.get(st, 0) / total_w)
                          * (per_state[st]["machine_upper_bound"]["point"] or 0.0)
                          for st in per_state), 4) if total_w else None)

    causes = {}
    if MISS_CAUSES.exists():
        causes = json.loads(MISS_CAUSES.read_text(encoding="utf-8"))

    return {
        "states_measured": sorted(per_state),
        "per_state": per_state,
        "per_size_band": per_band,
        "pooled_equal_allocation": {
            "editor_confirmed": _rate(pooled_rows, _confirmed),
            "machine_upper_bound": _rate(pooled_rows, _machine),
        },
        # The confirmed figure over ONLY the sets a reviewer has actually been
        # through. Without this row the pooled confirmed cell reads as a
        # collapse in coverage when it is an absence of review, and a reader
        # who takes one number from this block should be able to take a true
        # one. It is a DIFFERENT DENOMINATOR and is labelled as one.
        "pooled_adjudicated_sets_only": _rate(
            [r for r in pooled_rows if adjudicated.get(r["_wave"])], _confirmed),
        "pooled_notice_volume_weighted_machine_upper_bound": weighted,
        "large_event_census_by_wave": census,
        "unknown_by_wave": unknown,
        "adjudicated_by_wave": adjudicated,
        "frame_detail": frame_detail,
        "excluded_rows_by_reason": excluded,
        "miss_causes": causes.get("cause_counts", {}),
        "measured_at": {label: m["measured_at"] for label, _, m in waves},
    }


def _pct(rate):
    if not rate["n"]:
        return "no sample"
    return rate["interval"]


def render_block(figures=None):
    f = figures or derive()
    lines = [BEGIN,
             "",
             "<!-- Generated by railway/warn_recall_pooled.py from the committed",
             "     measurement files. Do not edit by hand: every number in this",
             "     block is recomputed, and tests/test_warn_recall_pooled.py",
             "     fails if what is committed here disagrees with them. -->",
             ""]
    unadjudicated = [w for w, done in f["adjudicated_by_wave"].items() if not done]
    lines += [
        "### Per state",
        "",
        "| State | Wave | Frame (events) | Editor-confirmed | Machine upper bound |",
        "|---|---|---|---|---|",
    ]
    for st in f["states_measured"]:
        cell = f["per_state"][st]
        lines.append(f"| {st} | {cell['wave']} | {cell['frame']} | "
                     f"{_pct(cell['editor_confirmed'])} | "
                     f"{_pct(cell['machine_upper_bound'])} |")
    lines += [
        "",
        "**These cells are not ranked and must not be.** Each is 25 events and "
        "carries a Wilson interval roughly 14 points wide even at the ceiling; "
        "both definitions committed in advance to not ranking on cells this size.",
        "",
        "### Pooled",
        "",
        "| Basis | Figure |",
        "|---|---|",
        f"| Editor-confirmed, equal allocation, ALL measured states | "
        f"{_pct(f['pooled_equal_allocation']['editor_confirmed'])} |",
        f"| Editor-confirmed, ADJUDICATED sets only ("
        + ", ".join(w for w, done in f["adjudicated_by_wave"].items() if done)
        + f") | {_pct(f['pooled_adjudicated_sets_only'])} |",
        f"| Machine upper bound, equal allocation | "
        f"{_pct(f['pooled_equal_allocation']['machine_upper_bound'])} |",
        f"| Machine upper bound, notice-volume weighted | "
        f"{f['pooled_notice_volume_weighted_machine_upper_bound']} |",
        "",
        "Allocation is **equal, not proportional**: every state contributes 25 "
        "events regardless of how many notices it publishes, so the pooled figure "
        "is the mean of the state samples and **not** a population-weighted "
        "national estimate. The volume-weighted row is beside it for exactly that "
        "reason.",
        "",
    ]
    if unadjudicated:
        lines += [
            "> **The editor-confirmed pooled figure is held down by "
            + ", ".join(unadjudicated) + ", which has not been adjudicated.** Its "
            "numerator is zero BY CONSTRUCTION, not by measurement: every "
            "candidate in that set ships `not_matched` and only a reviewer may "
            "promote one. Until that review happens, the honest reading of the "
            "pooled editor-confirmed row is *a floor over a denominator that "
            "includes an unreviewed set*, and the machine bound beside it is the "
            "ceiling. **Neither is 'our WARN recall'.**",
            "",
        ]
    lines += ["### By event size, pooled", "",
              "| Band | Affected workers | Editor-confirmed | Machine upper bound |",
              "|---|---|---|---|"]
    for band, span in (("S", "1-99"), ("M", "100-499"), ("L", "500+")):
        cell = f["per_size_band"][band]
        lines.append(f"| {band} | {span} | {_pct(cell['editor_confirmed'])} | "
                     f"{_pct(cell['machine_upper_bound'])} |")
    lines += ["", "### The frames, before any matching", "",
              "| State | Wave | In-window events | Frame jobs | Months covered | "
              "Notice dates | Multi-row events |", "|---|---|---|---|---|---|---|"]
    for st in f["states_measured"]:
        d = f["frame_detail"][st]
        lines.append(
            f"| {st} | {d['wave']} | {d['in_window_events']} | "
            f"{(d['frame_jobs'] or 0):,} | {d['months_covered']} | "
            f"{d['notice_date_range'][0]} to {d['notice_date_range'][1]} | "
            f"{d['multi_row_events']} |")
    lines += ["", "A frame that stops early is a smaller denominator and not a "
              "recall result, which is why the month coverage and the notice-date "
              "range are printed beside every cell.", ""]
    for label, reasons in f["excluded_rows_by_reason"].items():
        if not reasons:
            continue
        total = sum(reasons.values())
        lines.append(f"**{label}: {total} published rows excluded**, each recorded "
                     "in the manifest with its reason: "
                     + "; ".join(f"{v} {k}" for k, v in sorted(reasons.items()))
                     + ".")
        lines.append("")
    lines += ["", "This is **event size, not employer size**. WARN publishes how "
              "many workers a notice affects and not how large the employer is.",
              "", "### Large-event census, reported apart and never pooled", "",
              "| Set | Editor-confirmed | Machine upper bound |", "|---|---|---|"]
    for label, cell in f["large_event_census_by_wave"].items():
        lines.append(f"| {label} | {_pct(cell['editor_confirmed'])} | "
                     f"{_pct(cell['machine_upper_bound'])} |")
    lines += ["", "Pooling a census with a systematic sample double-counts the "
              "events in both and silently reweights the result, so it is not done.",
              ""]
    if f["miss_causes"]:
        lines += ["### Why the wave-2 misses are misses", "",
                  "| Cause | Events |", "|---|---|"]
        for cause, count in f["miss_causes"].items():
            if count:
                lines.append(f"| `{cause}` | {count} |")
        lines += ["", "`UNKNOWN` is a verdict. `walked_not_read`, "
                  "`fetched_rejected` and `extracted_dropped` are statements "
                  "about a collector's own output, which a public read cannot "
                  "see, so a miss that cannot be placed stays UNKNOWN rather "
                  "than being guessed into one of them.", ""]
    unknown_total = sum(f["unknown_by_wave"].values())
    lines += [f"**Unreachable / UNKNOWN events excluded from every numerator and "
              f"denominator above: {unknown_total}.**", "",
              "Measured at: "
              + "; ".join(f"{k} {v}" for k, v in f["measured_at"].items()) + ".",
              "", END]
    return "\n".join(lines) + "\n"


def _apply(path, block):
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise RuntimeError(f"{path.name} carries no derived-block markers; add "
                           f"{BEGIN} / {END} where the figures belong")
    head = text[:text.index(BEGIN)]
    tail = text[text.index(END) + len(END):]
    return head + block.rstrip("\n") + tail


def render():
    block = render_block()
    for path in RENDER_TARGETS:
        path.write_text(_apply(path, block), encoding="utf-8")
        print(f"derived block written: {path}")
    return block


def check():
    """Non-zero if any target's committed block is not what the files compute."""
    block = render_block()
    stale = []
    for path in RENDER_TARGETS:
        if path.read_text(encoding="utf-8") != _apply(path, block):
            stale.append(path.name)
    if stale:
        print("STALE derived block in: " + ", ".join(stale))
        print("run: python3 railway/warn_recall_pooled.py --render")
        return 1
    print(f"derived blocks agree with the measurements ({len(RENDER_TARGETS)} file(s))")
    return 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if "--render" in argv:
        render()
        return 0
    if "--check" in argv:
        return check()
    print(json.dumps(derive(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
