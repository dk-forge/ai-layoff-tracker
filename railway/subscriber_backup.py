#!/usr/bin/env python3
"""The off-host copy of the subscriber list and its consent records.

Stdlib only. No paid call, no model, no new dependency: the crypto is `openssl`,
which is on the host inside PHP, on this Mac, and on a runner, so the hash-pinned
lock has nothing new to vouch for.

WHAT WAS MISSING
----------------
`backup_export.py` walks every table the plugin owns to a PUBLIC GitHub release
and EXCLUDES `wp_alt_subscribers`, which is right: addresses, consent records
and two live tokens. The consequence was that the list and its consent records
existed in exactly one place, a shared Bluehost account, with a migration
coming. A migration is when a single-copy table gets lost, and a consent record
has legal weight, so losing it is worse than losing the address it belongs to.

THE SHAPE, AND WHY IT IS THIS SHAPE
-----------------------------------
The host seals the payload with a PUBLIC key before it answers, so the plaintext
never crosses the wire and this script cannot read what it just fetched. The
private half lives only on the owner's machine. That is what makes every later
question easy: the ciphertext can sit in Time Machine, on a USB stick, in any
cloud drive, and none of those become a place personal data lives.

WHERE IT LANDS, AND WHERE IT MUST NOT
-------------------------------------
A local directory the owner names, OUTSIDE this repository, defaulting to
~/Backups/atr-subscribers. Enforced, not requested: `_refuse_public_destination`
fails on any path inside the checkout.

THERE IS DELIBERATELY NO WORKFLOW THAT HANDLES THE CIPHERTEXT, and this is the
same ruling `curated_probe.py` records. Artifacts and releases of a PUBLIC
repository are downloadable by anyone, so a scheduled job would publish the
sealed consent records of every subscriber to the open internet and rest the
whole guarantee on RSA-4096 never breaking, forever, for a file nobody could
ever unpublish. Ciphertext is a reason to relax about a USB stick. It is not a
reason to publish. The only workflow this ships is an OFFLINE drill on
synthetic rows, which is safe precisely because it never touches the host.

STDOUT IS NAMELESS BY CONSTRUCTION, not by care. `assert_nameless` is an
allowlist of numbers, ISO dates, hex digests and frozen label words, exactly as
in tracker_diff.py and curated_probe.py, so no address can be SPELLED by
anything this prints. tests/test_subscriber_backup_leak.py poisons a whole run
to prove it. The plaintext has exactly one sink: the file path the operator
names on `--open --out`, and never a default.

USAGE
  python3 subscriber_backup.py --status                 is it armed, how many rows
  python3 subscriber_backup.py --pull                   fetch and store the sealed backup
  python3 subscriber_backup.py --verify FILE            structure + fingerprint, no key needed
  python3 subscriber_backup.py --open FILE --key PRIV   prove it opens; --out writes plaintext
  python3 subscriber_backup.py --selftest               the offline round-trip drill
"""
from __future__ import annotations

import argparse
import base64
import binascii
import gzip
import hashlib
import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
FORMAT = "alt-subscriber-backup/1"
PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PUBLIC_KEY_PATH = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "data" / "subscriber-backup.pub.pem"
SEAL_PHP = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "includes" / "subscriber-backup-seal.php"
DEFAULT_DEST = Path.home() / "Backups" / "atr-subscribers"

# Mirrors alt_sbk_columns() in includes/subscriber-backup.php. The two are
# asserted equal by tests/test_subscriber_backup_crypto.py, so a column added
# on one side reddens CI instead of producing a container whose header disagrees
# with its contents.
COLUMNS = [
    "id", "email",
    "consent_layoff", "consent_talent", "consent_articles",
    "freq_layoff", "freq_talent", "freq_articles",
    "status", "confirm_token", "unsub_token", "pending_prefs",
    "created_at", "confirmed_at", "unsubscribed_at",
    "last_sent_at", "last_sent_daily", "last_sent_weekly", "last_sent_monthly",
]


# --------------------------------------------------------------------------
# The leak guard. Same construction as tracker_diff.assert_nameless and
# curated_probe.assert_nameless: an ALLOWLIST, so the public vocabulary cannot
# spell an address even for an input nobody anticipated.
# --------------------------------------------------------------------------

class LeakGuard(RuntimeError):
    """Raised when something that is not a declared public fact was about to be printed."""


_PUBLIC_WORDS = frozenset({
    PASS, FAIL, UNKNOWN,
    # NB: no word here may collide with a COLUMN NAME. `status` was in this
    # set as the mode label, and `status` is also a subscriber column, so the
    # vocabulary that named the mode could also have named a value. The mode is
    # `probe` for that reason alone, and a test walks every column to keep it
    # true.
    "armed", "disarmed", "pull", "verify", "open", "probe", "selftest",
    "sealed", "opened", "held", "absent", "present", "local",
})
_PUBLIC_KEYS = frozenset({
    "mode", "verdict", "armed", "rows", "bytes", "created_at", "checked_at",
    "key_fingerprint", "schema_version", "columns", "mac", "wrap", "cipher",
    "state", "files", "age_days", "compression",
})
# A fingerprint or a digest is admitted BY SHAPE, never by being today's value.
_HEX_RX = re.compile(r"^[0-9a-f]{16,128}$")
_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}(T[0-9:]{5,8}Z)?$")


def assert_nameless(obj, path="root"):
    """Prove a structure carries no free text. Raises LeakGuard.

    An address is free text and free text is refused. A reviewer noticing an
    address is not a mechanism; a function that cannot print one is.
    """
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        if obj in _PUBLIC_WORDS or _DATE_RX.match(obj) or _HEX_RX.match(obj):
            return obj
        raise LeakGuard(f"{path}: refusing to publish free text")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in _PUBLIC_KEYS:
                raise LeakGuard(f"{path}.{k}: key is not a declared public field")
            assert_nameless(v, f"{path}.{k}")
        return obj
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            assert_nameless(v, f"{path}[{i}]")
        return obj
    raise LeakGuard(f"{path}: unsupported type {type(obj).__name__}")


def public_render(facts):
    """One line of nameless facts. Raises on anything else."""
    assert_nameless(facts)
    return "; ".join(f"{k} {facts[k]}" for k in sorted(facts))


# `columns` is a list of schema identifiers, which are public (they are in this
# file, in the plugin and in docs/RECOVERY.md) but are not in _PUBLIC_WORDS,
# because admitting them as words would admit `email` as a printable string and
# the point of the guard is that nothing free-text-shaped survives it. So the
# count is what gets printed, never the names.
def _facts_from_container(header: dict) -> dict:
    return {
        "created_at": header.get("created_at", ""),
        "rows": int(header.get("rows", 0)),
        "columns": len(header.get("columns", []) or []),
        "schema_version": int(header.get("schema_version", 0)),
        "key_fingerprint": header.get("key_fingerprint", ""),
    }


# --------------------------------------------------------------------------
# Keys and the container
# --------------------------------------------------------------------------

class ContainerError(RuntimeError):
    """The container is not what it claims to be. Never a pass, never silent."""


def pem_to_der(pem: str) -> bytes:
    m = re.search(r"-----BEGIN PUBLIC KEY-----(.+?)-----END PUBLIC KEY-----", pem, re.S)
    if not m:
        raise ContainerError("the recipient key is not a PEM SubjectPublicKeyInfo block")
    try:
        return base64.b64decode(re.sub(r"\s+", "", m.group(1)), validate=True)
    except binascii.Error as exc:
        raise ContainerError(f"the recipient key body is not valid base64: {exc}") from None


def fingerprint(pem: str) -> str:
    """sha256 of the DER SubjectPublicKeyInfo, hex. Identical to alt_sbk_fingerprint()."""
    return hashlib.sha256(pem_to_der(pem)).hexdigest()


def committed_public_key() -> str:
    """The key this repository vouches for, or '' when still disarmed."""
    if not PUBLIC_KEY_PATH.is_file():
        return ""
    return PUBLIC_KEY_PATH.read_text().strip()


def canonical(header: dict) -> bytes:
    """The bytes the MAC covers. Field ORDER is part of the format; it is
    hard-coded here and in alt_sbk_canonical(), never derived from the JSON's
    key order, because a MAC over whatever keys happened to be present is a MAC
    that changes meaning when somebody adds a field."""
    return "\n".join([
        str(header["format"]),
        str(header["created_at"]),
        str(int(header["schema_version"])),
        str(int(header["rows"])),
        ",".join(header["columns"]),
        str(header["key_fingerprint"]),
        str(header["wrapped_key"]),
        str(header["iv"]),
        str(header["ciphertext"]),
    ]).encode("utf-8")


REQUIRED_FIELDS = (
    "format", "created_at", "schema_version", "rows", "columns",
    "key_fingerprint", "wrapped_key", "iv", "ciphertext", "mac",
)


def verify_structure(header: dict, *, expect_fingerprint: str = "") -> list:
    """Everything checkable WITHOUT the private key. Returns a list of faults.

    An empty list is not "the backup is good", it is "nothing here is wrong
    that can be seen from outside the envelope". Only --open answers the other
    half, which is why the drill exists.
    """
    faults = []
    missing = [f for f in REQUIRED_FIELDS if f not in header]
    if missing:
        return [f"container is missing {len(missing)} required field(s)"]
    if header["format"] != FORMAT:
        faults.append("container declares a format this build does not know")
    for field in ("wrapped_key", "iv", "ciphertext", "mac"):
        try:
            raw = base64.b64decode(header[field], validate=True)
        except binascii.Error:
            faults.append(f"{field} is not valid base64")
            continue
        if not raw:
            faults.append(f"{field} is empty")
    try:
        ct = base64.b64decode(header["ciphertext"], validate=True)
        if len(ct) % 16:
            faults.append("ciphertext is not a whole number of AES blocks")
        if int(header["rows"]) > 0 and len(ct) == 0:
            faults.append("the header claims rows but the ciphertext is empty")
    except binascii.Error:
        pass
    if list(header["columns"]) != COLUMNS:
        faults.append("the container's column list is not the one this build pins")
    if expect_fingerprint and header["key_fingerprint"] != expect_fingerprint:
        # The important one. A host persuaded to seal to a different recipient
        # produces a backup nobody can open, and the only moment that is
        # discoverable is now, rather than the day the host is gone.
        faults.append("sealed to a key this repository does not vouch for")
    return faults


# --------------------------------------------------------------------------
# Opening. The only path that ever produces plaintext.
# --------------------------------------------------------------------------

def _openssl(args, *, stdin=None) -> bytes:
    exe = shutil.which("openssl")
    if not exe:
        raise ContainerError("openssl is not on PATH, so this cannot be checked: UNKNOWN, not a pass")
    proc = subprocess.run([exe] + args, input=stdin, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise ContainerError(f"openssl {args[0]} failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def unwrap_cek(header: dict, private_key_path: Path) -> bytes:
    """RSA-OAEP unwrap. The digest is NAMED on both sides rather than defaulted:
    PHP's OPENSSL_PKCS1_OAEP_PADDING is MGF1-SHA1 and the CLI defaults the same
    way today, but two defaults are not one promise, and a build that moved one
    of them would produce a container nobody could open, with no error until the
    day it was needed."""
    wrapped = base64.b64decode(header["wrapped_key"], validate=True)
    return _openssl([
        "pkeyutl", "-decrypt", "-inkey", str(private_key_path),
        "-pkeyopt", "rsa_padding_mode:oaep",
        "-pkeyopt", "rsa_oaep_md:sha1",
        "-pkeyopt", "rsa_mgf1_md:sha1",
    ], stdin=wrapped)


def open_container(header: dict, private_key_path: Path) -> bytes:
    """Return the JSON Lines plaintext. Raises on any failure; never returns partial."""
    cek = unwrap_cek(header, private_key_path)
    if len(cek) != 32:
        raise ContainerError("the unwrapped content key is not 32 bytes")

    mac_key = hmac.new(cek, b"alt-sbk/1 mac", hashlib.sha256).digest()
    expected = hmac.new(mac_key, canonical(header), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, base64.b64decode(header["mac"], validate=True)):
        # CBC is malleable. Without this, an edited container decrypts to
        # something, and something plausible is worse than nothing.
        raise ContainerError("MAC mismatch: this container has been truncated or altered")

    gz = _openssl([
        "enc", "-d", "-aes-256-cbc",
        "-K", cek.hex(),
        "-iv", base64.b64decode(header["iv"], validate=True).hex(),
    ], stdin=base64.b64decode(header["ciphertext"], validate=True))
    return gzip.decompress(gz)


def count_rows(plaintext: bytes) -> int:
    """Parse every line. A line that will not parse is a fault, not a skip."""
    n = 0
    for i, line in enumerate(plaintext.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise ContainerError(f"line {i} of the restored payload is not JSON")
        if list(row.keys()) != COLUMNS:
            raise ContainerError(f"line {i} of the restored payload has an unexpected column set")
        n += 1
    return n


# --------------------------------------------------------------------------
# Destinations
# --------------------------------------------------------------------------

def _refuse_public_destination(path: Path) -> None:
    """A sealed backup of consent records must not land anywhere this repo can
    publish it. Enforced rather than requested, because the one time it is
    requested and ignored is the one that matters."""
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return
    raise SystemExit(
        f"REFUSED: {path} is inside the repository checkout. This repository is "
        f"PUBLIC and its releases and Actions artifacts are downloadable by "
        f"anyone. Choose a destination outside it (default: {DEFAULT_DEST})."
    )


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------

def _host():
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not site:
        raise SystemExit("WP_SITE_URL is not set.")
    if not key:
        raise SystemExit("WP_API_KEY is not set. This route is keyed.")
    return f"{site}/wp-json/layoffs/v1", {"X-Layoff-API-Key": key, "User-Agent": UA}


def _get_json(url, headers, timeout=120):
    # urllib, not requests: this script must run on the owner's Mac with nothing
    # installed. A browser-ish UA is mandatory (ModSecurity blocks python-requests).
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"HTTP {exc.code} from {url.rsplit('/', 1)[-1]}: {body}")


def cmd_status() -> int:
    base, headers = _host()
    data = _get_json(f"{base}/subscriber-backup-status", headers)
    committed = committed_public_key()
    local_fp = fingerprint(committed) if committed else ""
    armed = bool(data.get("armed")) and bool(committed)
    facts = {
        "mode": "probe",
        "armed": armed,
        "rows": data.get("rows"),
        "key_fingerprint": data.get("key_fingerprint") or "",
        "schema_version": int(data.get("schema_version") or 0),
    }
    print(public_render(facts))
    if not committed:
        print("verdict DISARMED: no recipient key is committed at "
              "wordpress-plugin/ai-layoff-tracker/data/subscriber-backup.pub.pem")
        return 2
    if data.get("key_fingerprint") != local_fp:
        print("verdict FAIL: the host is sealing to a key this repository does not vouch for")
        return 1
    if data.get("rows") is None:
        print("verdict UNKNOWN: the host could not report a row count, which is not zero")
        return 3
    print("verdict PASS: armed, and the host seals to the committed key")
    return 0


def cmd_pull(dest: Path) -> int:
    _refuse_public_destination(dest)
    base, headers = _host()
    committed = committed_public_key()
    if not committed:
        raise SystemExit(
            "DISARMED: no recipient key at "
            "wordpress-plugin/ai-layoff-tracker/data/subscriber-backup.pub.pem. "
            "See docs/RUNBOOK.md 'back up the subscriber list'."
        )
    header = _get_json(f"{base}/subscriber-backup", headers)
    faults = verify_structure(header, expect_fingerprint=fingerprint(committed))
    if faults:
        for f in faults:
            print(f"FAULT: {f}")
        print("verdict FAIL: nothing was written")
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out = dest / f"subscribers-{stamp}.sealed.json"
    out.write_text(json.dumps(header, indent=1, sort_keys=True))
    os.chmod(out, 0o600)
    facts = _facts_from_container(header)
    facts.update({"mode": "pull", "verdict": PASS, "bytes": out.stat().st_size})
    print(public_render(facts))
    # The PATH is not a subscriber fact and the operator needs it, so it is
    # printed outside the nameless render, deliberately and only here.
    print(f"sealed backup written to {out}")
    print("verdict PASS: structure and recipient verified. Run --open to prove it opens.")
    return 0


def cmd_verify(path: Path) -> int:
    header = json.loads(path.read_text())
    committed = committed_public_key()
    faults = verify_structure(header, expect_fingerprint=fingerprint(committed) if committed else "")
    facts = _facts_from_container(header)
    facts["mode"] = "verify"
    facts["verdict"] = FAIL if faults else (PASS if committed else UNKNOWN)
    print(public_render(facts))
    for f in faults:
        print(f"FAULT: {f}")
    if faults:
        return 1
    if not committed:
        print("verdict UNKNOWN: no committed key to check the recipient against. "
              "Structure is intact; who can open it is unproven from here.")
        return 3
    print("verdict PASS: structure intact and sealed to the committed key. "
          "This does NOT prove it opens; only --open does.")
    return 0


def cmd_open(path: Path, private_key: Path, out: Path | None) -> int:
    header = json.loads(path.read_text())
    plaintext = open_container(header, private_key)
    rows = count_rows(plaintext)
    claimed = int(header["rows"])
    facts = _facts_from_container(header)
    facts.update({"mode": "open", "verdict": PASS if rows == claimed else FAIL, "rows": rows})
    print(public_render(facts))
    if rows != claimed:
        print("verdict FAIL: the container's header and its contents disagree on the row count")
        return 1
    if out is not None:
        _refuse_public_destination(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        # THE ONE SINK. Written 0600 and named by the operator, never defaulted:
        # a default plaintext path is a plaintext copy somebody forgets.
        with open(out, "wb") as fh:
            fh.write(plaintext)
        os.chmod(out, 0o600)
        print(f"plaintext written to {out} (mode 0600). Delete it when you are done.")
    print("verdict PASS: opened, MAC verified, every row parsed")
    return 0


# --------------------------------------------------------------------------
# The drill. Offline, synthetic, and it runs the REAL sealer.
# --------------------------------------------------------------------------

SELFTEST_ROWS = 7


def _synthetic_rows(n=SELFTEST_ROWS):
    """Obviously fake, and shaped exactly like the real thing. A drill on real
    rows would be the leak it exists to prevent."""
    out = []
    for i in range(1, n + 1):
        out.append({
            "id": i,
            "email": f"drill-{i}@example-not-a-real-domain.invalid",
            "consent_layoff": 1, "consent_talent": 0, "consent_articles": 1,
            "freq_layoff": "weekly", "freq_talent": "weekly", "freq_articles": "monthly",
            "status": "confirmed",
            "confirm_token": f"{i:064x}",
            "unsub_token": f"{i + 1000:064x}",
            "pending_prefs": None,
            "created_at": "2026-01-0%d 00:00:00" % ((i % 9) + 1),
            "confirmed_at": "2026-01-0%d 00:01:00" % ((i % 9) + 1),
            "unsubscribed_at": None,
            "last_sent_at": None, "last_sent_daily": None,
            "last_sent_weekly": None, "last_sent_monthly": None,
        })
    return out


def php_seal(plaintext: bytes, public_pem_path: Path, rows: int) -> dict:
    """Run the PRODUCTION sealer. Not a Python re-implementation of it: a second
    implementation that agrees with itself proves nothing about the one the host
    runs."""
    php = shutil.which("php")
    if not php:
        raise ContainerError("php is not on PATH, so the sealer cannot be exercised: UNKNOWN, not a pass")
    harness = (
        "<?php require %s;"
        "$pt = file_get_contents('php://stdin');"
        "$pem = file_get_contents(%s);"
        "echo json_encode(alt_sbk_seal($pt, $pem, array("
        "  'schema_version' => 1, 'rows' => %d, 'columns' => %s,"
        "  'plugin_version' => 'drill')));"
        % (json.dumps(str(SEAL_PHP)), json.dumps(str(public_pem_path)), rows,
           "array(" + ", ".join(json.dumps(c) for c in COLUMNS) + ")")
    )
    with tempfile.NamedTemporaryFile("w", suffix=".php", delete=False) as fh:
        fh.write(harness)
        harness_path = fh.name
    try:
        proc = subprocess.run([php, harness_path], input=plaintext,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise ContainerError(f"the PHP sealer failed: {proc.stderr.decode('utf-8', 'replace')[:400]}")
        return json.loads(proc.stdout.decode("utf-8"))
    finally:
        os.unlink(harness_path)


def selftest() -> int:
    """Prove the whole path: real PHP sealer -> container -> openssl -> the same
    rows. Plus the negative controls, because a check that has only ever been
    seen to pass is indistinguishable from one that does nothing."""
    if not shutil.which("openssl") or not shutil.which("php"):
        print("verdict UNKNOWN: openssl or php is not on PATH, so the round trip "
              "could not be run. That is UNKNOWN, not a pass.")
        return 3
    rows = _synthetic_rows()
    plaintext = ("\n".join(json.dumps(r) for r in rows) + "\n").encode("utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        priv, pub, other = tmp / "priv.pem", tmp / "pub.pem", tmp / "other.pem"
        _openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:4096",
                  "-out", str(priv)])
        _openssl(["pkey", "-in", str(priv), "-pubout", "-out", str(pub)])
        _openssl(["genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:4096",
                  "-out", str(other)])

        header = php_seal(plaintext, pub, len(rows))

        faults = verify_structure(header, expect_fingerprint=fingerprint(pub.read_text()))
        if faults:
            for f in faults:
                print(f"FAULT: {f}")
            print("verdict FAIL: the sealer produced a container that does not verify")
            return 1

        # 1. It opens, and it is byte-identical.
        got = open_container(header, priv)
        if got != plaintext:
            print("verdict FAIL: the round trip did not return the same bytes")
            return 1
        if count_rows(got) != len(rows):
            print("verdict FAIL: the restored payload has a different row count")
            return 1

        # 2. The plaintext is NOT in the container. Obvious, and therefore
        #    exactly the kind of thing nobody checks.
        blob = json.dumps(header)
        for row in rows:
            if row["email"] in blob or row["unsub_token"] in blob:
                print("verdict FAIL: a plaintext value survived into the container")
                return 1

        # 3. Negative control: a flipped ciphertext byte must be REFUSED.
        tampered = dict(header)
        raw = bytearray(base64.b64decode(header["ciphertext"]))
        raw[len(raw) // 2] ^= 0x01
        tampered["ciphertext"] = base64.b64encode(bytes(raw)).decode()
        try:
            open_container(tampered, priv)
            print("verdict FAIL: a tampered container opened. The MAC is not working, "
                  "so a clean verify of a real container proves nothing.")
            return 1
        except ContainerError:
            pass

        # 4. Negative control: the wrong private key must not open it.
        try:
            open_container(header, other)
            print("verdict FAIL: the wrong key opened the container")
            return 1
        except ContainerError:
            pass

        # 5. Negative control: a container sealed to a key we do not vouch for
        #    must be caught by the fingerprint check, not by luck.
        _openssl(["pkey", "-in", str(other), "-pubout", "-out", str(tmp / "other.pub")])
        if not verify_structure(header, expect_fingerprint=fingerprint((tmp / "other.pub").read_text())):
            print("verdict FAIL: the recipient check did not notice a foreign key")
            return 1

    facts = {"mode": "selftest", "verdict": PASS, "rows": len(rows), "bytes": len(plaintext)}
    print(public_render(facts))
    print("verdict PASS: sealed by the production PHP, opened by openssl, "
          "byte-identical, and all four negative controls fired")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--status", action="store_true", help="is the host armed, and to which key")
    ap.add_argument("--pull", action="store_true", help="fetch and store the sealed backup")
    ap.add_argument("--verify", metavar="FILE", help="check a stored container without the private key")
    ap.add_argument("--open", metavar="FILE", help="prove a stored container opens")
    ap.add_argument("--key", metavar="PRIVATE_PEM", help="the private key, for --open")
    ap.add_argument("--out", metavar="PATH", help="where --pull stores, or where --open writes plaintext")
    ap.add_argument("--selftest", action="store_true", help="the offline round-trip drill")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.status:
        return cmd_status()
    if args.pull:
        return cmd_pull(Path(args.out) if args.out else DEFAULT_DEST)
    if args.verify:
        return cmd_verify(Path(args.verify))
    if args.open:
        if not args.key:
            raise SystemExit("--open needs --key: the private half never leaves your machine.")
        return cmd_open(Path(args.open), Path(args.key), Path(args.out) if args.out else None)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
