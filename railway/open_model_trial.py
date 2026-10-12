#!/usr/bin/env python3
"""Could a self-hosted open model do the AI-causation classification for $0?

    python3 railway/open_model_trial.py plan            # offline: gold set + baseline, no network
    python3 railway/open_model_trial.py install         # llama.cpp + model files into ~/.cache
    python3 railway/open_model_trial.py run --model qwen2.5-7b

Owner question, 2026-10-12. DISPATCH-ONLY (open-model-trial.yml on the box2
self-hosted runner). It holds no secret, writes nothing anywhere but the runner
user's ~/.cache and the job summary, and makes NO paid call: the paid model's
answers are the ones already frozen in the gold set (`raw`), so the comparison
costs nothing. Production routing is untouched; this only measures.

SAME TASK AS PRODUCTION. The prompt is extractor.ai_causation_prompt(), the
system message extractor.MINI_SYSTEM, max_tokens 250 as classify_ai_evidence()
sends, the answer goes through extractor._parse_json_response() and
extractor.finalize_ai_causation() (the verbatim-quote guard), and the decision
is extractor.ai_explicit_from_causation(). A harness that skipped the guard
would score a model this pipeline never takes at its word.

TRUTH. The ai-causation-2026-08 gold set: 200 rows, gold by two independent
labellers agreeing (166) or by the owner's adjudication where they did not
(34). The "labellers-split" subset reported separately is the rows whose two
labellers' admitted answers disagree on ai_explicit, i.e. the hard ones whose
truth came from the owner (34 split on the 6-way label; fewer split on the
binary decision this scores).

CPU MANNERS. The box also runs CI. llama-server runs under `nice -n 19` and
`ionice -c3` with a bounded thread count; before each item the 1-minute load
average is checked and the run PAUSES while the rest of the box is busy, and
stops (reporting what it has) if the pause budget runs out. Nothing here is a
service: the server is killed when each model finishes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "docs" / "recall-reference-sets"
SAMPLE = REF / "ai-causation-2026-08.sample.json"
GOLD = REF / "ai-causation-2026-08.goldset.json"
PAID_MODEL = "google/gemini-2.5-flash-lite"   # OPENROUTER_MODEL in production

CACHE = Path(os.environ.get("TRIAL_CACHE", Path.home() / ".cache" / "open-model-trial"))
UA = "AiLayoffTracker/1.0 open-model-trial (+https://asktherecruiter.com)"

# sha256 = the Hugging Face LFS oid of the exact file (read 2026-10-12), so a
# swapped or truncated download is refused before it is ever loaded.
MODELS = {
    "qwen2.5-7b": {
        "label": "Qwen2.5-7B-Instruct Q4_K_M",
        "url": "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/"
               "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "file": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
        "sha256": "65b8fcd92af6b4fefa935c625d1ac27ea29dcb6ee14589c55a8f115ceaaa1423",
        "size": 4683074240,
    },
    "llama3.1-8b": {
        "label": "Llama-3.1-8B-Instruct Q4_K_M",
        "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/"
               "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "sha256": "7b064f5842bf9532c91456deda288a1b672397a54fa729aa665952863033557c",
        "size": 4920739232,
    },
}


def notice(title, msg):
    print(f"::notice title={title}::{msg}", flush=True)


def summary(md):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")
    print(md, flush=True)


# ---------------------------------------------------------------- gold set

def _explicit(raw, text):
    import extractor
    fin = extractor.finalize_ai_causation(raw, text)
    return (extractor.ai_explicit_from_causation(fin["ai_causation"]) if fin else None), fin


def load_items():
    """Gold rows with truth, the paid model's frozen answer, and the human flag."""
    items = json.loads(SAMPLE.read_text(encoding="utf-8"))["items"]
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    labels, raw = gold["labels"], gold["raw"]
    labellers = gold["labellers"]   # the two independent labellers, as recorded
    out = []
    for it in items:
        key = str(it["id"])
        truth = labels.get(key)
        if not isinstance(truth, bool):
            continue
        a, _ = _explicit(raw[labellers[0]].get(key), it["text"])
        b, _ = _explicit(raw[labellers[1]].get(key), it["text"])
        paid, paid_fin = _explicit(raw[PAID_MODEL].get(key), it["text"])
        out.append({"id": key, "text": it["text"], "stratum": it["stratum"],
                    "truth": truth, "human": a != b, "paid": paid,
                    "paid_cause": (paid_fin or {}).get("ai_causation")})
    return out


def ordered(items):
    """Round-robin across strata, so a run cut short by its budget is still balanced."""
    by = {}
    for it in items:
        by.setdefault(it["stratum"], []).append(it)
    pick, keys = [], sorted(by)
    while any(by.values()):
        for k in keys:
            if by[k]:
                pick.append(by[k].pop(0))
    return pick


def scores(pairs):
    """pairs: [(pred | None, truth)]. None = no admissible JSON answer.

    Per-label precision/recall/F1 for both classes (an unparseable answer counts
    as wrong for whichever class is true), macro-F1, accuracy over ALL rows.
    """
    n = len(pairs)
    res = {"n": n, "json_ok": sum(p is not None for p, _ in pairs)}
    for cls in (True, False):
        tp = sum(p is cls and t is cls for p, t in pairs)
        fp = sum(p is cls and t is not cls for p, t in pairs)
        fn = sum(p is not cls and t is cls for p, t in pairs)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        res[cls] = {"p": prec, "r": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0}
    res["acc"] = sum(p is t for p, t in pairs) / n if n else 0.0
    res["macro_f1"] = (res[True]["f1"] + res[False]["f1"]) / 2
    return res


def fmt(res):
    return (f"acc={res['acc']:.1%} macroF1={res['macro_f1']:.3f} "
            f"AI(P/R/F1)={res[True]['p']:.2f}/{res[True]['r']:.2f}/{res[True]['f1']:.2f} "
            f"notAI(P/R/F1)={res[False]['p']:.2f}/{res[False]['r']:.2f}/{res[False]['f1']:.2f} "
            f"json_ok={res['json_ok']}/{res['n']}")


def cmd_plan(_args):
    items = load_items()
    human = [i for i in items if i["human"]]
    base = scores([(i["paid"], i["truth"]) for i in items])
    notice("Gold set", f"{len(items)} rows, {sum(i['truth'] for i in items)} AI-attributed, "
                       f"{len(human)} where the two labellers split on ai_explicit")
    notice("Paid model baseline", f"{PAID_MODEL} (frozen answers): {fmt(base)}")
    return 0


# ---------------------------------------------------------------- install

def _get(url, dest, sha256=None, size=None):
    """Download to dest with a .part file; verify size and sha256 when given."""
    if dest.exists() and (sha256 is None or _sha(dest) == sha256):
        print(f"cached: {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as resp, open(part, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
            fh.write(chunk)
    if size is not None and part.stat().st_size != size:
        part.unlink()
        raise SystemExit(f"{dest.name}: size mismatch, refused")
    if sha256 is not None and h.hexdigest() != sha256:
        part.unlink()
        raise SystemExit(f"{dest.name}: sha256 mismatch, refused")
    part.rename(dest)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _release_asset(tag):
    """The llama.cpp ubuntu-x64 CPU build for `tag`, with GitHub's own digest."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{tag}",
        headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        rel = json.load(resp)
    for a in rel.get("assets", []):
        name = a["name"]
        if "bin-ubuntu-x64" in name and name.endswith((".zip", ".tar.gz")):
            digest = (a.get("digest") or "")
            return name, a["browser_download_url"], \
                digest.split(":", 1)[1] if digest.startswith("sha256:") else None
    raise SystemExit(f"llama.cpp {tag}: no bin-ubuntu-x64 asset")


def server_binary(tag):
    root = CACHE / "llama.cpp" / tag
    found = list(root.rglob("llama-server")) if root.exists() else []
    return found[0] if found else None


def cmd_install(args):
    free = shutil.disk_usage(Path.home()).free / 1e9
    need = sum(m["size"] for k, m in MODELS.items() if k in args.models
               and not (CACHE / "models" / m["file"]).exists()) / 1e9 + 1
    if free < need + 5:
        raise SystemExit(f"Not enough disk in $HOME: {free:.1f} GB free, need ~{need + 5:.0f} GB")
    if server_binary(args.tag) is None:
        name, url, digest = _release_asset(args.tag)
        if digest is None:
            notice("llama.cpp", f"{name} has no published digest; size-checked only")
        arc = CACHE / "dl" / name
        _get(url, arc, sha256=digest)
        root = CACHE / "llama.cpp" / args.tag
        root.mkdir(parents=True, exist_ok=True)
        if name.endswith(".zip"):
            with zipfile.ZipFile(arc) as zf:
                zf.extractall(root)
        else:
            with tarfile.open(arc) as tf:
                tf.extractall(root, filter="data")
        for p in root.rglob("*"):
            if p.is_file() and (p.name.startswith("llama-") or p.suffix == ".so"):
                p.chmod(0o755)
        arc.unlink()
    exe = server_binary(args.tag)
    if exe is None:
        raise SystemExit("llama-server not found in the release archive")
    ver = subprocess.run([str(exe), "--version"], capture_output=True, text=True,
                         env=_lib_env(exe), timeout=60)
    print((ver.stdout + ver.stderr).strip()[-300:])
    for key in args.models:
        m = MODELS[key]
        _get(m["url"], CACHE / "models" / m["file"], sha256=m["sha256"], size=m["size"])
    notice("Install", f"llama.cpp {args.tag} + {', '.join(args.models)} in {CACHE}")
    return 0


def _lib_env(exe):
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = f"{exe.parent}:{env.get('LD_LIBRARY_PATH', '')}"
    return env


# ---------------------------------------------------------------- run

def _post(port, body, timeout=600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _wait_health(port, proc, seconds=600):
    end = time.time() + seconds
    while time.time() < end:
        if proc.poll() is not None:
            raise SystemExit(f"llama-server exited with {proc.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                if r.status == 200:
                    return
        except Exception:  # noqa: BLE001 - not up yet
            pass
        time.sleep(3)
    raise SystemExit("llama-server never became healthy")


def _wait_for_quiet(args, own_threads, budget):
    """Pause while the REST of the box is busy. Returns seconds paused, or None if out of budget."""
    paused = 0.0
    while True:
        others = os.getloadavg()[0] - own_threads
        if others <= args.max_other_load:
            return paused
        if budget - paused <= 0:
            return None
        time.sleep(30)
        paused += 30


def cmd_run(args):
    import extractor
    m = MODELS[args.model]
    exe = server_binary(args.tag)
    gguf = CACHE / "models" / m["file"]
    if exe is None or not gguf.exists():
        raise SystemExit("run `install` first")
    items = ordered(load_items())[: args.limit]

    cmd = [str(exe), "-m", str(gguf), "-t", str(args.threads), "-tb", str(args.threads),
           "-c", "4096", "-np", "1", "--host", "127.0.0.1", "--port", str(args.port),
           "--no-webui"]
    prefix = ["nice", "-n", "19"]
    if shutil.which("ionice"):
        prefix += ["ionice", "-c3"]
    log = open(CACHE / f"server-{args.model}.log", "w", encoding="utf-8")
    proc = subprocess.Popen(prefix + cmd, stdout=log, stderr=subprocess.STDOUT,
                            env=_lib_env(exe), start_new_session=True)
    t_load = time.time()
    try:
        _wait_health(args.port, proc)
        load_s = time.time() - t_load
        rows, walls, pps, tps, ptoks, gtoks = [], [], [], [], [], []
        paused_total, stopped = 0.0, None
        deadline = time.time() + args.budget_min * 60
        for i, it in enumerate(items):
            if time.time() > deadline:
                stopped = f"time budget ({args.budget_min} min) reached"
                break
            p = _wait_for_quiet(args, args.threads if i else 0, args.pause_budget_min * 60 - paused_total)
            if p is None:
                stopped = "box stayed busy past the pause budget (CI); stopped politely"
                break
            paused_total += p
            text = (it["text"] or "")[: extractor.AI_CAUSATION_TEXT_LIMIT]
            body = {"model": args.model, "temperature": 0, "max_tokens": 250,
                    "messages": [{"role": "system", "content": extractor.MINI_SYSTEM},
                                 {"role": "user", "content": extractor.ai_causation_prompt(text)}]}
            t0 = time.time()
            try:
                resp = _post(args.port, body)
                content = resp["choices"][0]["message"]["content"] or ""
                tim = resp.get("timings") or {}
            except Exception as exc:  # noqa: BLE001 - an errored call is reported, not dropped
                print(f"item {it['id']}: {type(exc).__name__}")
                content, tim = "", {}
            walls.append(time.time() - t0)
            if tim:
                pps.append(tim.get("prompt_per_second") or 0)
                tps.append(tim.get("predicted_per_second") or 0)
                ptoks.append(tim.get("prompt_n") or 0)
                gtoks.append(tim.get("predicted_n") or 0)
            parsed = extractor._parse_json_response(content)
            fin = extractor.finalize_ai_causation(parsed, text)
            pred = extractor.ai_explicit_from_causation(fin["ai_causation"]) if fin else None
            rows.append({**it, "pred": pred, "cause": (fin or {}).get("ai_causation")})
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(items)} scored, {sum(walls) / len(walls):.1f}s/item", flush=True)
    finally:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
        log.close()

    report(args, m, rows, walls, pps, tps, ptoks, gtoks, load_s, paused_total, stopped)
    return 0


def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def report(args, m, rows, walls, pps, tps, ptoks, gtoks, load_s, paused, stopped):
    if not rows:
        notice(m["label"], f"no rows scored ({stopped})")
        return
    model = scores([(r["pred"], r["truth"]) for r in rows])
    paid = scores([(r["paid"], r["truth"]) for r in rows])
    hum = [r for r in rows if r["human"]]
    model_h = scores([(r["pred"], r["truth"]) for r in hum]) if hum else None
    paid_h = scores([(r["paid"], r["truth"]) for r in hum]) if hum else None
    agree = sum(r["pred"] is r["paid"] for r in rows) / len(rows)
    agree6 = sum(r["cause"] == r["paid_cause"] for r in rows) / len(rows)
    per_item = _mean(walls)
    per_hour = 3600 / per_item if per_item else 0
    cpu_h_day = args.daily_volume * per_item * args.threads / 3600
    wall_h_day = args.daily_volume * per_item / 3600
    stop = f" STOPPED EARLY: {stopped}." if stopped else ""

    notice(f"{m['label']} accuracy",
           f"{fmt(model)} | paid {PAID_MODEL} on same rows: {fmt(paid)}{stop}")
    if model_h:
        notice(f"{m['label']} hard rows",
               f"labellers-split n={len(hum)}: model acc={model_h['acc']:.1%} vs paid acc={paid_h['acc']:.1%}")
    notice(f"{m['label']} agreement",
           f"ai_explicit agreement with paid model {agree:.1%}; 6-way ai_causation agreement {agree6:.1%}")
    notice(f"{m['label']} speed",
           f"{per_item:.1f}s/item wall, {per_hour:.0f} items/hour, prompt {_mean(pps):.1f} tok/s, "
           f"gen {_mean(tps):.1f} tok/s ({args.threads} threads, nice 19); "
           f"{args.daily_volume} items/day = {wall_h_day:.2f} h wall = {cpu_h_day:.2f} CPU-core-hours/day; "
           f"model load {load_s:.0f}s; paused for CI {paused:.0f}s")

    def row(name, r):
        return (f"| {name} | {r['n']} | {r['acc']:.1%} | {r['macro_f1']:.3f} | "
                f"{r[True]['p']:.2f}/{r[True]['r']:.2f}/{r[True]['f1']:.2f} | "
                f"{r[False]['p']:.2f}/{r[False]['r']:.2f}/{r[False]['f1']:.2f} | "
                f"{r['json_ok']}/{r['n']} |")
    lines = [f"### {m['label']} (llama.cpp {args.tag}, {args.threads} threads)", "",
             "| Model | n | Accuracy | Macro-F1 | AI P/R/F1 | not-AI P/R/F1 | JSON valid |",
             "|---|---|---|---|---|---|---|",
             row(m["label"], model), row(f"{PAID_MODEL} (paid, frozen)", paid)]
    if model_h:
        lines += [row(f"{m['label']}; labellers-split rows", model_h),
                  row("paid; labellers-split rows", paid_h)]
    lines += ["",
              f"- Agreement with paid model: ai_explicit {agree:.1%}, 6-way label {agree6:.1%}",
              f"- Speed: {per_item:.1f} s/item, {per_hour:.0f} items/hour, prompt "
              f"{_mean(pps):.1f} tok/s, generation {_mean(tps):.1f} tok/s, "
              f"avg {_mean(ptoks):.0f} prompt + {_mean(gtoks):.0f} output tokens",
              f"- A {args.daily_volume}-item day: {wall_h_day:.2f} h wall, "
              f"{cpu_h_day:.2f} CPU-core-hours",
              f"- Model load {load_s:.0f}s; paused for other load {paused:.0f}s{stop}", ""]
    summary("\n".join(lines))
    out = CACHE / f"result-{args.model}.json"
    out.write_text(json.dumps({"model": args.model, "model_acc": model["acc"],
                               "paid_acc": paid["acc"], "agree": agree, "per_item_s": per_item,
                               "rows": [{k: r[k] for k in ("id", "truth", "paid", "pred", "cause")}
                                        for r in rows]}, indent=1), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    ins = sub.add_parser("install")
    ins.add_argument("--tag", default=os.environ.get("LLAMA_CPP_TAG", "b11000"))
    ins.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    run = sub.add_parser("run")
    run.add_argument("--model", required=True, choices=list(MODELS))
    run.add_argument("--tag", default=os.environ.get("LLAMA_CPP_TAG", "b11000"))
    run.add_argument("--threads", type=int, default=int(os.environ.get("TRIAL_THREADS", "6")))
    run.add_argument("--limit", type=int, default=int(os.environ.get("TRIAL_LIMIT", "200")))
    run.add_argument("--budget-min", type=float, default=float(os.environ.get("TRIAL_BUDGET_MIN", "55")))
    run.add_argument("--pause-budget-min", type=float, default=20)
    run.add_argument("--max-other-load", type=float, default=float(os.environ.get("TRIAL_MAX_OTHER_LOAD", "6")))
    run.add_argument("--daily-volume", type=int, default=int(os.environ.get("TRIAL_DAILY_VOLUME", "300")))
    run.add_argument("--port", type=int, default=18080)
    args = ap.parse_args(argv)
    return {"plan": cmd_plan, "install": cmd_install, "run": cmd_run}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
