"""Two builds must never share one plugin version, and git cannot see it.

WHAT HAPPENED, TWICE, ON 2026-08-19. Two PRs read main at 2.20.114, both were
correct when they read it, both bumped to 2.20.115, and both merged eight
minutes apart. Nothing conflicted. Two branches writing the SAME string to the
same line is a clean auto-merge, so every check passed on both sides and the
collision was visible only by reading main afterwards. An hour later 2.20.116
was claimed by two more PRs the same way. TECHLOG 2026-08-19 has the full
record.

WHY IT IS NOT BOOKKEEPING. The bump is three mechanisms at once:

  * `?ver=` cache-busts layoffs.css and the JS. The first build to deploy under
    a version puts its stylesheet in every cache under that key, and the second
    build ships new CSS behind an answer that is already in front of it.
  * `alt_flush_caches_on_deploy()` fires on a version CHANGE, so the second
    deploy at the same version flushes nothing.
  * `includes/build-stamp.php` hashes the plugin's own bytes at render time, so
    one version now answers with two build stamps. `reader_freshness.py` reads
    that as a FAULT and it is right to. It is the 2.20.21 raced-render
    signature, manufactured deliberately.

THE PROPERTY, AND WHY IT IS CHECKED HERE RATHER THAN ON THE PR. A PR-only check
passes for both branches independently, because each is correct against the
main it was written from. The collision does not exist until the second merge,
so this compares the NEW MAIN TIP against the PREVIOUS MAIN TIP:

  On main, a push that changes any plugin file must raise ALT_VERSION strictly
  above the version the previous main tip carried.

Three findings, three separate causes:

  COLLIDED      plugin bytes changed and the version did not move. This is the
                second merge of a version race, failing at the moment it
                becomes true.
  REUSED        the version is one an earlier commit already published. A
                rollback that retypes an old number is the same defect with a
                different shape, and it is cheap to check.
  LANDED_NOOP   a merged branch changed plugin files against its merge base,
                and the merge changed none. The branch lost the race: its
                number was taken while it sat in checks and its edits are
                already on main, so nothing new shipped under that version.
                This is the shape PR #155 landed in.

WHAT IT DELIBERATELY DOES NOT DO. A workflow-only or Python-only change touches
no plugin file, so it is SKIPPED and no bump is ever demanded of it. Getting
that condition wrong would redden every CI edit, which is the failure mode this
repo has been burned by more than once. `Version:` and `ALT_VERSION` agreement
is NOT re-checked here: `tests/test_theme_light_dark.py` already pins it, and
two definitions of one rule drift.

THREE STATES. A shallow checkout cannot answer the history question, and a tree
with no readable ALT_VERSION cannot answer any of them. Both resolve to
UNKNOWN, exit 3, never to a pass. Run the workflow with `fetch-depth: 0`.

CLI:
    python3 railway/version_collision.py --mode main --base <sha> --head <sha>
    python3 railway/version_collision.py --mode pr   --base <sha> --head <sha>

Exit 0 PASS or SKIP, 1 FAIL, 3 UNKNOWN.
"""

import argparse
import re
import subprocess
import sys

PLUGIN_PREFIX = "wordpress-plugin/ai-layoff-tracker/"
MAIN_PHP = PLUGIN_PREFIX + "ai-layoff-tracker.php"

# The constant, not the header comment. One of the two is enough here and the
# pair is pinned elsewhere.
VERSION_RE = re.compile(r"define\(\s*'ALT_VERSION'\s*,\s*'([0-9][0-9.]*)'\s*\)")
ADDED_VERSION_RE = re.compile(
    r"^\+define\(\s*'ALT_VERSION'\s*,\s*'([0-9][0-9.]*)'\s*\)", re.M)

PASS, FAIL, SKIP, UNKNOWN = "PASS", "FAIL", "SKIP", "UNKNOWN"

# The deploy mirrors the plugin folder minus these globs, so a change to one of
# them ships no bytes and earns no version. Same rule as build-stamp.php.
def _excluded(rel):
    for part in rel.split("/"):
        if part.startswith(".git") or part.endswith(".zip"):
            return True
    return False


class Result:
    """A verdict that can say it does not know.

    `ok` is true only for PASS and SKIP, so a check that could not run can
    never satisfy `if result.ok`.
    """

    def __init__(self, verdict, detail, findings=None, suggested=None):
        self.verdict = verdict
        self.detail = detail
        self.findings = list(findings or [])
        self.suggested = suggested

    @property
    def ok(self):
        return self.verdict in (PASS, SKIP)

    @property
    def exit_code(self):
        return {PASS: 0, SKIP: 0, FAIL: 1, UNKNOWN: 3}[self.verdict]

    def __repr__(self):
        return "<Result %s: %s>" % (self.verdict, self.detail)


def git(args, repo=None, check=True):
    out = subprocess.run(["git"] + list(args), cwd=repo,
                         capture_output=True, text=True)
    if check and out.returncode != 0:
        raise GitError((out.stderr or out.stdout).strip())
    return out.stdout


class GitError(RuntimeError):
    pass


def parse_version(text):
    """'2.20.116' -> (2, 20, 116). None when it is not a version."""
    if not text:
        return None
    parts = text.strip().split(".")
    if not all(p.isdigit() for p in parts) or not parts:
        return None
    return tuple(int(p) for p in parts)


def next_version(used):
    """The lowest patch release above every version in `used`."""
    highest = max(v for v in used if v)
    return ".".join(str(n) for n in highest[:-1] + (highest[-1] + 1,))


def version_at(ref, repo=None):
    """The ALT_VERSION the plugin carried at `ref`, or None."""
    try:
        php = git(["show", "%s:%s" % (ref, MAIN_PHP)], repo=repo)
    except GitError:
        return None
    found = VERSION_RE.search(php)
    return found.group(1) if found else None


def plugin_files_changed(base, head, repo=None):
    """Plugin files that differ between two trees, deploy exclusions removed."""
    names = git(["diff", "--name-only", base, head, "--", PLUGIN_PREFIX],
                repo=repo).split("\n")
    out = []
    for name in names:
        name = name.strip()
        if not name.startswith(PLUGIN_PREFIX):
            continue
        if _excluded(name[len(PLUGIN_PREFIX):]):
            continue
        out.append(name)
    return sorted(out)


def versions_ever_used(ref, repo=None):
    """Every ALT_VERSION any commit reachable from `ref` ever introduced.

    One `git log -p` over the ~600 commits that touch the one file, parsed for
    added constant lines. Merges show no diff of their own, so a version is
    attributed to the commit that actually typed it.
    """
    log = git(["log", "-p", "-U0", "--format=%x00%H", ref, "--", MAIN_PHP],
              repo=repo)
    used = {}
    for chunk in log.split("\0"):
        if not chunk.strip():
            continue
        sha = chunk.split("\n", 1)[0].strip()
        for raw in ADDED_VERSION_RE.findall(chunk):
            used.setdefault(raw, []).append(sha)
    return used


def is_shallow(repo=None):
    return git(["rev-parse", "--is-shallow-repository"],
               repo=repo).strip() == "true"


def _merge_parents(ref, repo=None):
    line = git(["rev-list", "--parents", "-n", "1", ref], repo=repo).split()
    return line[1:] if len(line) > 1 else []


def check(base, head, mode="main", repo=None):
    """Judge one main advance, or one PR head, against the tip it must clear.

    `mode="main"`: base is the PREVIOUS main tip and head is the new one.
    `mode="pr"`:   base is the CURRENT main tip and head is the PR head. What
                   counts as "this PR changed a plugin file" is measured from
                   the merge base, never from the tip, or main's own plugin
                   edits would demand a bump from a Python-only PR.
    """
    try:
        if is_shallow(repo):
            return Result(UNKNOWN, "shallow checkout: history cannot be read, "
                                   "use fetch-depth: 0")
    except GitError as exc:
        return Result(UNKNOWN, "not a git checkout: %s" % exc)
    try:
        base = git(["rev-parse", "--verify", "%s^{commit}" % base], repo=repo).strip()
        head = git(["rev-parse", "--verify", "%s^{commit}" % head], repo=repo).strip()
    except GitError as exc:
        return Result(UNKNOWN, "cannot resolve a revision: %s" % exc)

    try:
        return _judge(base, head, mode, repo)
    except GitError as exc:
        return Result(UNKNOWN, "git failed: %s" % exc)


def _judge(base, head, mode, repo):
    """The judgement itself, once both revisions are known to exist."""
    change_base = base
    if mode == "pr":
        change_base = git(["merge-base", base, head], repo=repo).strip()

    changed = plugin_files_changed(change_base, head, repo=repo)
    branch_changed = []
    parents = _merge_parents(head, repo=repo) if mode == "main" else []
    if mode == "main" and len(parents) == 2:
        mb = git(["merge-base", parents[0], parents[1]], repo=repo).strip()
        branch_changed = plugin_files_changed(mb, parents[1], repo=repo)

    if not changed and not branch_changed:
        return Result(SKIP, "no plugin file changed, so no version is owed")

    head_raw, base_raw = version_at(head, repo=repo), version_at(base, repo=repo)
    head_v, base_v = parse_version(head_raw), parse_version(base_raw)
    if head_v is None or base_v is None:
        return Result(UNKNOWN, "ALT_VERSION unreadable at %s"
                      % ("head" if head_v is None else "base"))

    history = versions_ever_used(base, repo=repo)
    known = {parse_version(v) for v in history} | {base_v, head_v}
    suggested = next_version({v for v in known if v})

    findings = []
    if changed and head_v <= base_v:
        findings.append(Finding(
            "COLLIDED",
            "%d plugin file(s) changed and ALT_VERSION did not move above "
            "%s (%s at %s, still %s here). Another merge took that number "
            "while this branch sat in checks."
            % (len(changed), "the previous main tip" if mode == "main"
               else "the current main tip", base_raw, base[:8], head_raw),
            changed))
    elif head_raw in history:
        findings.append(Finding(
            "REUSED",
            "ALT_VERSION %s was already published by %s. A version string is "
            "spent once; readers and caches hold the older answer under it."
            % (head_raw, ", ".join(s[:8] for s in history[head_raw])),
            changed))
    if not changed and branch_changed:
        findings.append(Finding(
            "LANDED_NOOP",
            "the merged branch changed %d plugin file(s) and this merge "
            "changed none, so nothing shipped under %s. Its edits are already "
            "on main, which means the branch lost a version race rather than "
            "landing one." % (len(branch_changed), head_raw),
            branch_changed))

    if findings:
        return Result(FAIL, findings[0].detail, findings, suggested)
    return Result(PASS, "plugin bytes changed and %s > %s" % (head_raw, base_raw),
                  suggested=suggested)


class Finding:
    def __init__(self, cause, detail, files):
        self.cause = cause
        self.detail = detail
        self.files = list(files)


def report(result, mode, base, head, log=print):
    log("version-collision: %s" % result.verdict)
    log("  mode=%s base=%s head=%s" % (mode, base[:12], head[:12]))
    if not result.findings:
        log("  %s" % result.detail)
    for finding in result.findings:
        log("")
        log("  %s: %s" % (finding.cause, finding.detail))
        for name in finding.files[:12]:
            log("      %s" % name)
        if len(finding.files) > 12:
            log("      ... and %d more" % (len(finding.files) - 12))
    if result.verdict == FAIL:
        log("")
        log("  WHAT TO DO. Your branch is stale, not wrong. Rebase onto main,")
        log("  set BOTH `Version:` and ALT_VERSION in")
        log("  %s to %s," % (MAIN_PHP, result.suggested))
        log("  and push. Record the number in docs/HANDOFF.md so the next")
        log("  session does not claim it too.")
        log("")
        log("  Re-reading main before pushing is necessary and is not")
        log("  sufficient. The window between reading and merging is where")
        log("  this lands, which is why the check runs on the merge.")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=["main", "pr"], default="main")
    ap.add_argument("--base", required=True,
                    help="previous main tip (main mode) or main tip (pr mode)")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--repo", default=None)
    args = ap.parse_args(argv)

    try:
        result = check(args.base, args.head, mode=args.mode, repo=args.repo)
    except GitError as exc:
        result = Result(UNKNOWN, "git failed: %s" % exc)

    base = args.base
    head = args.head
    try:
        base = subprocess.run(["git", "rev-parse", args.base], cwd=args.repo,
                              capture_output=True, text=True).stdout.strip() or base
        head = subprocess.run(["git", "rev-parse", args.head], cwd=args.repo,
                              capture_output=True, text=True).stdout.strip() or head
    except OSError:
        pass
    report(result, args.mode, base, head)
    if result.verdict == FAIL:
        print("::error::plugin version collision: %s" % result.detail)
    elif result.verdict == UNKNOWN:
        print("::warning::version collision check could not run: %s"
              % result.detail)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
