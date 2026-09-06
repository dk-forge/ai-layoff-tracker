"""No outbound call may be able to hang forever.

A request with no timeout does not fail. It waits, and the only thing that ends
it is the workflow's `timeout-minutes` killing the whole run, which costs every
item the job had not reached yet and reports an interruption instead of a
result. The failure is silent right up to the kill, so nothing in a log looks
wrong while it is happening.

The sweep found the direct HTTP surface already clean (2026-09-06: zero
`requests.<verb>` / `urlopen` / `smtplib.SMTP` call sites without one, and both
bare `requests.Session()` users pass a per-request timeout). What it exists to
stop is the NEXT one, and in particular the paid path, which has a trap of its
own: `openai.OpenAI()` has a default timeout of TEN MINUTES. Five of the six
clients in this tree are built without an explicit `timeout=`, and are safe only
because every `chat.completions.create` on them passes one. A single new call
site that forgets is a paid job that can sit for ten minutes per item behind a
`metered_call` gate, which is also how a completion gets billed that no ledger
entry ever sees (CLAUDE.md, "a retry you did not write still counts").

So the rule enforced here is per client: EITHER the client is constructed with
`timeout=`, OR every `.create(` in that module passes `timeout=`. That is the
weakest form of the invariant that is still impossible to satisfy by accident.
"""
import ast
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]

HTTP_MODULES = {"requests", "httpx", "urllib3"}
VERBS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}


def _modules():
    for path in sorted(RAILWAY.rglob("*.py")):
        if "tests" in path.parts:
            continue
        try:
            yield path, ast.parse(path.read_text())
        except SyntaxError:  # pragma: no cover - a broken file fails elsewhere
            continue


def _kwargs(call):
    return {kw.arg for kw in call.keywords}


def _forwards_kwargs(call):
    """`f(*a, **k)` may be carrying a timeout from its caller."""
    return any(kw.arg is None for kw in call.keywords)


class NoOutboundCallCanHangForever(unittest.TestCase):
    def test_no_http_call_site_omits_a_timeout(self):
        offenders = []
        for path, tree in _modules():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn, label = node.func, None
                if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                    if fn.value.id in HTTP_MODULES and fn.attr in VERBS:
                        label = f"{fn.value.id}.{fn.attr}"
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if name in {"urlopen", "urlretrieve"}:
                    # urlopen's timeout may also be the second positional arg.
                    if len(node.args) < 2:
                        label = "urlopen"
                if name in {"SMTP", "SMTP_SSL"}:
                    label = f"smtplib.{name}"
                if label and "timeout" not in _kwargs(node) and not _forwards_kwargs(node):
                    offenders.append(f"{path.name}:{node.lineno} {label}")
        self.assertEqual(offenders, [], "\n" + "\n".join(offenders))

    def test_every_paid_client_bounds_its_own_call(self):
        offenders, seen = [], 0
        for path, tree in _modules():
            clients = [n for n in ast.walk(tree)
                       if isinstance(n, ast.Call)
                       and (n.func.attr if isinstance(n.func, ast.Attribute)
                            else getattr(n.func, "id", None)) == "OpenAI"]
            if not clients:
                continue
            seen += len(clients)
            creates = [n for n in ast.walk(tree)
                       if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "create"]
            for client in clients:
                if "timeout" in _kwargs(client):
                    continue
                bare = [c for c in creates
                        if "timeout" not in _kwargs(c) and not _forwards_kwargs(c)]
                for c in bare:
                    offenders.append(
                        f"{path.name}: OpenAI() at line {client.lineno} sets no "
                        f"timeout (the SDK default is 600s) and the .create() at "
                        f"line {c.lineno} passes none either. Give one or the other "
                        f"an explicit timeout.")
        self.assertGreaterEqual(seen, 5, "the paid-client scan found almost nothing")
        self.assertEqual(offenders, [], "\n" + "\n".join(offenders))

    def test_the_http_scan_sees_the_calls_it_is_meant_to_judge(self):
        """A clean zero from a scan that matches nothing is not a pass."""
        total = 0
        for _path, tree in _modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and isinstance(node.func.value, ast.Name) \
                        and node.func.value.id in HTTP_MODULES \
                        and node.func.attr in VERBS:
                    total += 1
        self.assertGreater(total, 30,
                           f"only {total} HTTP call sites matched; the scan has drifted")


if __name__ == "__main__":
    unittest.main()
