"""One operational sender, one subject prefix, and a reader digest that keeps
its own identity.

WHAT WENT WRONG, AND WHY A TEST IS THE RIGHT ANSWER
---------------------------------------------------
Operational mail moved to Resend on 2026-08-19 with an explicit promise in
CLAUDE.md: sender identity is deliberately operational, never the digest's
From name. Three callers were converted. Nine were not, and nobody noticed,
because a wrong From line produces no error anywhere. The mail arrives. It
just arrives wearing the wrong face.

The nine went on POSTing to `/wp-json/layoffs/v1/alert`, which calls bare
`wp_mail()`. On this install the Brevo plugin intercepts `wp_mail` and
replaces the whole From line with the SUBSCRIBER newsletter identity
(subscribe.php documents that at length, measured 2026-08-17). So on
2026-08-19 the owner received his OpenRouter low-balance alarm and his
held-relabel notice from `newsletter@asktherecruiter.com` under the reader
newsletter's display name.

That is not cosmetic. It is the eight-emails-in-an-afternoon failure with a
longer fuse: mail that looks like a newsletter gets filed with the newsletter,
and after that the alarm is decoration. The owner asked for exactly one thing
- "can we do system so it's easy for me to sort" - and one From plus one
prefix is that system.

So the invariant is asserted rather than remembered. A tenth caller cannot be
added with its own sender without this file going red.

THE OTHER DIRECTION MATTERS JUST AS MUCH. The reader digest must NOT gain the
ops prefix or the ops From. Somebody subscribed to it; a subject stamped
`[AI Layoff Tracker]` in front of an edition they asked for reads as machine
noise, and moving it to Resend would put a bad afternoon of red CI in front of
the allowance readers depend on. Two identities, cleanly separated, and both
halves of that are tested here.
"""
import ast
import contextlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ops_notify
import opsmail

RAILWAY = Path(__file__).resolve().parents[1]
REPO = RAILWAY.parent
WORKFLOWS = REPO / ".github" / "workflows"

#: The route that hands a message to `wp_mail`, and through it to the reader
#: newsletter's From line. Nothing under railway/ may build a request to it.
ALERT_ROUTE = "wp-json/layoffs/v1/alert"

#: Modules that legitimately talk to Resend directly. `opsmail` IS the
#: transport; `ci_alert` is the ledger that rules on a message before handing
#: it over; `ops_notify` is the door every other caller uses. Everything else
#: goes through `ops_notify`. Keep this list SHORT: each entry is a place the
#: From line could drift without anything noticing.
DIRECT_SENDERS = {"opsmail.py", "ci_alert.py", "ops_notify.py",
                  "alert_drain.py", "health_digest.py", "ci_noise_report.py"}

#: The reader path. Different provider, different budget, different identity,
#: and none of this file's rules apply to it except "stay separate".
READER_MODULES = {"digest_transport.py", "digest_send.py", "digest_layout.py",
                  "digest_slot.py"}


def _evaluated_strings(path):
    """Every string literal a module actually EVALUATES, docstrings excluded.

    Prose is not behaviour, and several modules must go on describing the
    `/alert` route because that history is why the current design exists. What
    none of them may do is build a request to it.
    """
    tree = ast.parse(Path(path).read_text())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docs.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docs]


def _railway_modules():
    return sorted(p for p in RAILWAY.glob("*.py"))


@contextlib.contextmanager
def _scratch_ledger():
    """Send for real, but never into the COMMITTED ledger.

    `ops_notify.notify` calls `ci_alert.post_alert`, which claims
    railway/alert_state.json before sending. That is the correct production
    ordering and it means an unguarded test rewrites a tracked file: the first
    run of this suite dirtied the real ledger, which would have been committed
    by anyone staging with `git add -u`. A test that mutates repository state
    is a test that has to be remembered, and this one no longer has to be.
    """
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.dict(
                os.environ,
                {"ALERT_STATE_PATH": str(Path(tmp) / "alert_state.json")}):
            yield


class NobodyMailsTheOwnerBehindTheHelpersBack(unittest.TestCase):

    def test_no_module_can_still_build_a_request_to_the_alert_route(self):
        """The root cause, closed for every module rather than for three.

        `test_ops_mail_split.py` already asserts this for `ci_alert`,
        `alert_drain` and `opsmail`. Those were the three that were converted.
        The nine that were not are exactly the ones that check did not look at,
        which is how the defect survived a change that was specifically about
        it. So the scope is now every module in railway/.
        """
        offenders = []
        for path in _railway_modules():
            for literal in _evaluated_strings(path):
                if ALERT_ROUTE in literal:
                    offenders.append(path.name)
                    break
        self.assertEqual(offenders, [], f"{offenders} can still POST to the "
                         "site's /alert route, which wp_mail hands to the "
                         "reader newsletter's From line. Use ops_notify.")

    def test_only_the_helpers_talk_to_resend_directly(self):
        """A new sender has to come through the door, not around it.

        Anything that imports `opsmail` is choosing its own send call, and a
        send call is where a From line gets invented. Modules that need to are
        named above and reviewed; everything else uses `ops_notify`, which owns
        no From line of its own either.
        """
        offenders = []
        for path in _railway_modules():
            if path.name in DIRECT_SENDERS:
                continue
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                if any(n.split(".")[0] == "opsmail" for n in names):
                    offenders.append(path.name)
                    break
        self.assertEqual(sorted(set(offenders)), [],
                         "these import the transport directly instead of "
                         "ops_notify; add them to DIRECT_SENDERS only with a "
                         "reason, because each one is a From line that can "
                         "drift without anything noticing")

    def test_the_from_line_has_exactly_one_definition(self):
        """`OPS_MAIL_FROM` is READ in one place and nowhere else.

        A second reader is a second default, and a second default is how two
        alarms end up in two folders.

        Naming the variable in a diagnostic string is not reading it, and three
        modules rightly do that: when a send fails on a bad sender, the message
        that says "check OPS_MAIL_FROM" is the useful one. So this looks for an
        actual environment access, via the AST, rather than for the words.
        """
        readers = []
        for path in _railway_modules():
            for node in ast.walk(ast.parse(path.read_text())):
                key = None
                # os.environ.get("OPS_MAIL_FROM", ...)
                if isinstance(node, ast.Call) and node.args and \
                        isinstance(node.args[0], ast.Constant):
                    fn = node.func
                    if isinstance(fn, ast.Attribute) and fn.attr == "get" and \
                            isinstance(fn.value, ast.Attribute) and \
                            fn.value.attr == "environ":
                        key = node.args[0].value
                # os.environ["OPS_MAIL_FROM"]
                elif isinstance(node, ast.Subscript) and \
                        isinstance(node.value, ast.Attribute) and \
                        node.value.attr == "environ" and \
                        isinstance(node.slice, ast.Constant):
                    key = node.slice.value
                if key == "OPS_MAIL_FROM":
                    readers.append(path.name)
                    break
        self.assertEqual(sorted(set(readers)), ["opsmail.py"], readers)

    def test_the_operational_sender_is_not_the_newsletter(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPS_MAIL_FROM", None)
            sender = opsmail.sender()
        self.assertIn("Ops", sender)
        self.assertNotIn("newsletter@", sender)
        # The address the reader relay sends as, and the display name beside
        # it. Neither may appear in the operational From line.
        subscribe = (REPO / "wordpress-plugin" / "ai-layoff-tracker" /
                     "includes" / "subscribe.php").read_text()
        reader_address = re.search(
            r"ALT_DIGEST_FROM_EMAIL',\s*'([^']+)'", subscribe).group(1)
        self.assertNotIn(reader_address, sender)


class OneSubjectPrefixSoOneMailRuleCatchesEverything(unittest.TestCase):

    def test_every_operational_subject_is_stamped(self):
        """Applied by the transport, so no caller can forget it."""
        seen = {}

        def spy(method, path, body=None, extra_headers=None):
            seen.update(body or {})
            return 200, {"id": "re_1"}

        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(opsmail, "_request", spy):
            opsmail.send_once("a source broke", "b")
        self.assertTrue(seen["subject"].startswith(opsmail.SUBJECT_PREFIX),
                        seen["subject"])

    def test_no_caller_adds_a_prefix_of_its_own(self):
        """Two prefixes is a subject the owner's one mail rule still catches
        and a subject line that looks broken. The transport stamps it; a
        caller that stamps it too gets `[AI Layoff Tracker] [AI Layoff
        Tracker] ...`."""
        marker = opsmail.SUBJECT_PREFIX.strip()
        offenders = []
        for path in _railway_modules():
            if path.name == "opsmail.py":
                continue
            for literal in _evaluated_strings(path):
                if marker in literal:
                    offenders.append(f"{path.name}: {literal[:60]}")
        self.assertEqual(offenders, [], offenders)

    def test_the_prefix_is_stamped_once_end_to_end(self):
        sent = []
        with _scratch_ledger(), \
                mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(
                    opsmail, "send_once",
                    lambda s, b, i="": (sent.append(s) or
                                        (True, "emailed the owner", False))):
            ops_notify.notify("a source broke", "body", what="test")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].count(opsmail.SUBJECT_PREFIX.strip()), 0,
                         "ops_notify must hand the transport an UNstamped "
                         "subject; the transport is what stamps it")


class TheReaderDigestKeepsItsOwnIdentity(unittest.TestCase):
    """The other direction, and it is not symmetric politeness.

    A person subscribed to the digest. Stamping an ops prefix on an edition
    they asked for reads as machine noise, and moving it onto Resend would let
    a bad afternoon of red CI eat the allowance readers depend on.
    """

    def test_the_reader_path_never_imports_the_operational_transport(self):
        for name in READER_MODULES:
            path = RAILWAY / name
            if not path.exists():
                continue
            source = path.read_text()
            tree = ast.parse(source)
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add((node.module or "").split(".")[0])
            self.assertNotIn("opsmail", imported, name)
            self.assertNotIn("ops_notify", imported, name)

    def test_no_reader_subject_carries_the_operational_prefix(self):
        marker = opsmail.SUBJECT_PREFIX.strip()
        for name in READER_MODULES:
            path = RAILWAY / name
            if not path.exists():
                continue
            for literal in _evaluated_strings(path):
                self.assertNotIn(marker, literal,
                                 f"{name} would stamp a reader subject with "
                                 "the operations prefix")

    def test_the_two_senders_are_different_addresses(self):
        subscribe = (REPO / "wordpress-plugin" / "ai-layoff-tracker" /
                     "includes" / "subscribe.php").read_text()
        reader = re.search(r"ALT_DIGEST_FROM_EMAIL',\s*'([^']+)'",
                           subscribe).group(1)
        self.assertNotIn(reader, opsmail.DEFAULT_FROM)


class TheDoorItselfIsWellBehaved(unittest.TestCase):

    def test_it_never_prints_the_subject_or_the_body(self):
        """`tracker_diff` and `curated_probe` send company names through this
        function, and both have a test that poisons a whole run to prove those
        names reach the owner's inbox and no other sink. A debug print of the
        payload in ops_notify would defeat both of them from outside.
        """
        import io
        from contextlib import redirect_stdout
        secret = "Zzyzxcorp"
        buf = io.StringIO()
        with _scratch_ledger(), \
                mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(opsmail, "send_once",
                                  lambda s, b, i="": (True, "emailed the owner",
                                                      False)), \
                redirect_stdout(buf):
            ops_notify.notify(f"missing {secret}", f"body about {secret}",
                              what="test report")
        self.assertNotIn(secret.lower(), buf.getvalue().lower())

    def test_an_unconfigured_relay_is_a_state_and_never_an_exception(self):
        buf_ok = None
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESEND_API_KEY", None)
            buf_ok = ops_notify.notify("s", "b", what="test report")
        self.assertFalse(buf_ok)

    def test_a_raising_transport_does_not_take_the_caller_down(self):
        """Every caller is a reporting tail on a job that already did its real
        work. A notifier that raises while handling somebody else's failure has
        told nobody anything and reddened a run for it."""
        def boom(*a, **k):
            raise RuntimeError("relay exploded")

        import ci_alert
        with mock.patch.dict(os.environ, {"RESEND_API_KEY": "k"}), \
                mock.patch.object(ci_alert, "post_alert", boom):
            self.assertFalse(ops_notify.notify("s", "b", what="test report"))


class EveryJobThatMailsCarriesTheKeyThatLetsItMail(unittest.TestCase):
    """A ported caller with no `RESEND_API_KEY` in its workflow is silent.

    This is the specific way this change could go wrong and be invisible: the
    code is right, the run is green, and the email simply never arrives,
    because the job's env still lists the WordPress credential the old route
    needed. `configured()` returns False, the job prints one line nobody reads,
    and exits 0.
    """

    #: script name -> workflow file that runs it.
    JOBS = {
        "openrouter_balance_check.py": "openrouter-balance-check.yml",
        "link_check.py": "link-check.yml",
        "source_verification_audit.py": "source-verification-audit.yml",
        "process_tips.py": "process-tips.yml",
        "daily_classification_spotcheck.py": "data-quality.yml",
        "tracker_diff.py": "tracker-diff.yml",
    }

    def test_the_sender_override_travels_with_the_key(self):
        """`OPS_MAIL_FROM` goes wherever `RESEND_API_KEY` goes, on the ops side.

        The variable is unset today, so `opsmail`'s default applies everywhere
        and nothing is visibly wrong. That is the trap. Five older ops
        workflows pass `vars.OPS_MAIL_FROM` and the six ported ones did not, so
        the day somebody sets that variable to move the sender, five jobs would
        move and six would keep the old From. Two From lines is precisely the
        defect this whole change exists to close, arriving later and by a
        different route.
        """
        missing = []
        for workflow in set(self.JOBS.values()):
            text = (WORKFLOWS / workflow).read_text()
            if "RESEND_API_KEY" in text and "OPS_MAIL_FROM" not in text:
                missing.append(workflow)
        self.assertEqual(sorted(missing), [], missing)

    def test_the_reader_send_never_receives_the_operations_sender(self):
        """digest-send.yml carries RESEND_API_KEY, because Resend is one of the
        transports the READER digest can be pointed at. It must never carry
        OPS_MAIL_FROM: that would be the alarm's identity on an edition
        somebody subscribed to. The reader path reads DIGEST_FROM."""
        path = WORKFLOWS / "digest-send.yml"
        if not path.exists():
            self.skipTest("no digest-send workflow")
        text = path.read_text()
        self.assertIn("DIGEST_FROM", text)
        self.assertNotIn("OPS_MAIL_FROM", text)

    def test_each_workflow_passes_the_resend_key(self):
        missing = []
        for script, workflow in self.JOBS.items():
            path = WORKFLOWS / workflow
            if not path.exists():
                missing.append(f"{workflow} (no such workflow)")
                continue
            text = path.read_text()
            if script not in text:
                missing.append(f"{workflow} no longer runs {script}")
            elif "RESEND_API_KEY" not in text:
                missing.append(f"{workflow} runs {script} but passes no "
                               "RESEND_API_KEY, so its mail is silent")
        self.assertEqual(missing, [], missing)


if __name__ == "__main__":
    unittest.main()
