"""THE ONE JOB THAT READS EVERY SUBSCRIBER ADDRESS MUST NOT BE THE THING THAT PRINTS ONE.

WHY THIS TEST IS NOT ROUTINE.

`subscriber_backup.py` exists to move the subscriber list and its consent
records off a host that is about to be migrated. Everything it touches is
personal data: addresses, consent flags, and two live tokens. It runs on a
machine where that data is present and a reviewer's is not, and it is expected
to say useful things about what it just read.

Care does not survive that arrangement. Shape does. `assert_nameless` is an
allowlist of numbers, ISO dates, hex digests and frozen label words, so the
public vocabulary cannot SPELL an address, and that property holds for inputs
nobody anticipated, which is the only kind that matters here.

`test_a_poisoned_run_leaks_nothing` runs the WHOLE loop - seal, pull, verify,
open - over rows stuffed with invented addresses, invented tokens and invented
consent stamps, and asserts not one of those strings reaches stdout or the
stored container.

THE ADDRESSES IN THE FIXTURE ARE FICTIONAL ON PURPOSE, on `.invalid`, which is
reserved and can never resolve. A test that had to contain a real address to
prove real addresses do not escape would be the leak it was written to prevent.

AND IT IS PROVEN NON-VACUOUS. `test_the_poison_reaches_the_named_sink` asserts
the markers DID arrive in the plaintext file the operator explicitly named.
Without it, a script that decrypted nothing at all would pass every leak
assertion above and look like the strongest guard in the repo.
"""
import importlib.util
import io
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout


def _repo_root():
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("test_subscriber_backup_leak: no repo root above %s" % here)


ROOT = _repo_root()
sys.path.insert(0, str(ROOT / "railway"))
_spec = importlib.util.spec_from_file_location(
    "subscriber_backup", ROOT / "railway" / "subscriber_backup.py")
sb = importlib.util.module_from_spec(_spec)
sys.modules["subscriber_backup"] = sb
_spec.loader.exec_module(sb)

HAVE_TOOLS = bool(shutil.which("openssl") and shutil.which("php"))

# Every one of these is invented. If any appeared in stdout, the corresponding
# real value would have too.
POISON = [
    "quillfeather@example-not-a-real-domain.invalid",
    "vantablack@example-not-a-real-domain.invalid",
    "marrowgate@example-not-a-real-domain.invalid",
    "ab" * 32,          # a token-shaped value
    "cd" * 32,
    "quillfeather-digest.example",
]


def _poisoned_rows():
    rows = []
    for i, addr in enumerate(POISON[:3], 1):
        rows.append({
            "id": i, "email": addr,
            "consent_layoff": 1, "consent_talent": 1, "consent_articles": 0,
            "freq_layoff": "daily", "freq_talent": "weekly", "freq_articles": "weekly",
            "status": "confirmed",
            "confirm_token": POISON[3], "unsub_token": POISON[4],
            "pending_prefs": POISON[5],
            "created_at": "2026-01-01 00:00:00", "confirmed_at": "2026-01-01 00:01:00",
            "unsubscribed_at": None, "last_sent_at": None,
            "last_sent_daily": None, "last_sent_weekly": None, "last_sent_monthly": None,
        })
    return rows


@unittest.skipUnless(HAVE_TOOLS, "openssl and php are required to run the real sealer")
class PoisonedRun(unittest.TestCase):
    """One poisoned end-to-end run, then every assertion about it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="sbk-leak-"))
        priv, pub = cls.tmp / "priv.pem", cls.tmp / "pub.pem"
        sb._openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072",
                     "-out", str(priv)])
        sb._openssl(["pkey", "-in", str(priv), "-pubout", "-out", str(pub)])
        cls.priv, cls.pub = priv, pub

        rows = _poisoned_rows()
        plaintext = ("\n".join(json.dumps(r) for r in rows) + "\n").encode()
        cls.container = sb.php_seal(plaintext, pub, len(rows))
        cls.rows = rows

        # The whole loop, exactly as an operator runs it, with the host and the
        # committed key stood in for. Nothing else is patched.
        real_get, real_key, real_host = sb._get_json, sb.committed_public_key, sb._host
        sb._get_json = lambda url, headers, timeout=120: dict(cls.container)
        sb.committed_public_key = lambda: pub.read_text()
        sb._host = lambda: ("https://example.invalid/wp-json/layoffs/v1", {})
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                cls.pull_rc = sb.cmd_pull(cls.tmp / "dest")
                stored = sorted((cls.tmp / "dest").glob("*.sealed.json"))[0]
                cls.verify_rc = sb.cmd_verify(stored)
                cls.open_rc = sb.cmd_open(stored, priv, None)
                # ...and once more with an explicitly named plaintext sink.
                cls.sink = cls.tmp / "restored.jsonl"
                cls.sink_rc = sb.cmd_open(stored, priv, cls.sink)
            cls.stdout = out.getvalue()
            cls.stored_bytes = stored.read_bytes()
        finally:
            sb._get_json, sb.committed_public_key, sb._host = real_get, real_key, real_host

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_run_actually_succeeded(self):
        """A run that failed early would leak nothing and prove nothing."""
        self.assertEqual((self.pull_rc, self.verify_rc, self.open_rc, self.sink_rc),
                         (0, 0, 0, 0), self.stdout)

    def test_a_poisoned_run_leaks_nothing_to_stdout(self):
        for marker in POISON:
            self.assertNotIn(marker, self.stdout,
                             f"a poisoned value reached stdout: this is the leak")

    def test_the_stored_container_carries_no_plaintext(self):
        for marker in POISON:
            self.assertNotIn(marker.encode(), self.stored_bytes,
                             "a poisoned value survived into the sealed container")

    def test_the_poison_reaches_the_named_sink(self):
        """NON-VACUITY. Without this, a script that decrypted nothing would pass
        every assertion above."""
        body = self.sink.read_text()
        for marker in POISON:
            self.assertIn(marker, body,
                          "the plaintext sink did not receive the data, so the "
                          "leak assertions above are vacuous")

    def test_stdout_says_something(self):
        """A guard that passes because the run printed nothing is not a guard."""
        self.assertIn("PASS", self.stdout)
        self.assertIn("rows 3", self.stdout)


class TheGuardItself(unittest.TestCase):
    def test_an_address_cannot_be_spelled(self):
        with self.assertRaises(sb.LeakGuard):
            sb.assert_nameless({"rows": "quillfeather@example-not-a-real-domain.invalid"})

    def test_an_undeclared_key_is_refused(self):
        with self.assertRaises(sb.LeakGuard):
            sb.assert_nameless({"email": 1})

    def test_numbers_dates_and_digests_pass(self):
        sb.assert_nameless({"rows": 7, "created_at": "2026-09-06T11:00:00Z",
                            "key_fingerprint": "ab" * 32, "verdict": "PASS"})

    def test_the_column_names_are_not_printable_words(self):
        """`email` is a public schema identifier and still must not be a
        printable string, or the vocabulary that names the schema becomes the
        vocabulary that can name a value."""
        for column in sb.COLUMNS:
            with self.assertRaises(sb.LeakGuard):
                sb.assert_nameless({"rows": column})


class Destinations(unittest.TestCase):
    def test_a_destination_inside_the_repo_is_refused(self):
        with self.assertRaises(SystemExit):
            sb._refuse_public_destination(ROOT / "railway" / "leak.jsonl")

    def test_a_destination_outside_the_repo_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sb._refuse_public_destination(pathlib.Path(tmp) / "ok.jsonl")


if __name__ == "__main__":
    unittest.main()
