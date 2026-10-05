"""Evaluate the PyPI package `laya` (local CPU classifier) against the
AI-causation gold set already in the repo.

Gold: docs/recall-reference-sets/ai-causation-2026-08.goldset.json `labels`
({row id: bool} -- does the source attribute the layoff to AI), joined to the
item text in ai-causation-2026-08.sample.json. news-corroborated-2026-08 is a
recall reference set (events that should exist), not a yes/no label set, so
it is not scored here.

Run by .github/workflows/laya-eval.yml only: no keys, no network beyond pip
and the Hugging Face checkpoint download, writes nothing but the job summary.
"""
import json
import os
import resource
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "docs" / "recall-reference-sets"
QUESTION = {
    "ai_cause": {
        "type": "noul",
        "instructions": (
            "Does this layoff report say the job cuts were caused by, or partly "
            "attributed to, artificial intelligence or automation?"
        ),
    }
}


def load_items(limit):
    gold = json.loads((REF / "ai-causation-2026-08.goldset.json").read_text())["labels"]
    sample = json.loads((REF / "ai-causation-2026-08.sample.json").read_text())["items"]
    out = []
    for it in sample:
        key = str(it["id"])
        if key in gold and gold[key] is not None:
            title = f'{it.get("company_name", "")}: {it.get("source_url", "")}'
            out.append((title, it.get("text") or "", bool(gold[key])))
    return out[:limit]


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # Linux: KiB


def main():
    limit = int(os.environ.get("LAYA_LIMIT", "200") or 200)
    items = load_items(min(limit, 200))
    from laya import Router  # imported late: load time is not per-item time

    router = Router()
    times, agree, disagree, errors = [], 0, [], 0
    for title, text, gold in items:
        t0 = time.perf_counter()
        try:
            res = router.predict(text, QUESTION)
            p = float(res["answers"]["ai_cause"]["noul"])
        except Exception as exc:  # report, never hide
            errors += 1
            print(f"laya error on {title}: {exc!r}", file=sys.stderr)
            continue
        times.append(time.perf_counter() - t0)
        pred = p >= 0.5
        if pred == gold:
            agree += 1
        else:
            disagree.append((title, gold, p))
    scored = len(times)
    lines = [
        "## laya vs AI-causation gold set",
        "",
        "| metric | value |",
        "|---|---|",
        f"| items scored | {scored} (errors {errors}) |",
        f"| agreement vs gold | {100.0 * agree / scored:.1f}% |" if scored else "| agreement | n/a |",
        f"| gold positives | {sum(1 for _, _, g in items if g)} of {len(items)} |",
        f"| median s/item | {statistics.median(times):.3f} |" if times else "| median s/item | n/a |",
        f"| peak RSS | {peak_rss_mb():.0f} MB |",
        "",
        "### First 5 disagreements",
        "",
    ]
    for title, gold, p in disagree[:5]:
        lines.append(f"- {title} - gold={gold}, laya p(yes)={p:.2f}")
    report = "\n".join(lines) + "\n"
    print(report)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as fh:
            fh.write(report)
    return 0 if scored else 1


if __name__ == "__main__":
    sys.exit(main())
