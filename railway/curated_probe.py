"""A CURATED ITEM IS A RECALL PROBE AND A DISCOVERY WORKLIST. IT IS NEVER A SOURCE.

WHY THIS FILE EXISTS.

The owner pasted four items from a curated industry digest and asked whether we
held them. We held one. Every miss had a diagnosable cause and two of them were
the most actionable class there is: the originating outlet is not in our feed
set. Then he asked the right question — how does that stop being a thing he does
by hand?

Most of the answer already exists. `tracker_diff.learn_run()` asks exactly this
question every day against a reference universe that costs nothing and names
nobody: the GDELT layoff corpus BEFORE our trusted-domain gate. That loop is the
machine. This file does NOT rebuild it and deliberately imports its judgement
rather than copying it — the rule that decides what headcount a headline states
must have ONE definition, the same way the live invariants do.

What this file adds is the half that machine cannot have: a HUMAN-CURATED
reference universe. A domain expert's roundup is not a bigger GDELT. It is a
different distribution — trade press, regional editions, native-language
outlets and newsletters that a wire crawler never carries, which is precisely
why two of the owner's four misses were outlets rather than wording. GDELT
cannot surface an outlet GDELT does not index. A person can.

So the owner keeps doing the ten seconds he already does, and everything after
those ten seconds stops being manual.

WHAT IT COSTS: nothing. Zero model calls on every path — no OpenRouter key is
read, imported or in scope, so there is no `spend.metered_call()` here because
there is nothing to meter. The only network calls are reads of our OWN public
`/query` (one per distinct employer token, memoised) and, if keys are present,
one `/alert` POST to the owner's own inbox.

WHAT IT NEVER DOES, STRUCTURALLY:

  * IT NEVER FETCHES AN ITEM'S PAGE — not the paywalled one, not any other.
    Judgement comes from the line the owner pasted and from our own rows; when
    an item is marked inaccessible, the follow-up reads a news INDEX (the Google
    News RSS the repo already runs as its free discovery source) and takes the
    outlet's identity from that index's own `<source>` element. So no robots.txt
    is engaged, no paywall is met, no bot wall is met and no CAPTCHA exists to
    solve — not as a policy a future edit can soften, but because no content
    request to any outlet exists anywhere in this module.

  * IT NEVER TREATS "PAYWALLED" AS "UNREACHABLE". Those are different claims and
    conflating them was this file's first design. The SOURCE is inaccessible —
    recorded, permanently, in the refusal ledger. The EVENT usually is not: a
    major exclusive is picked up within hours by wires, trade press and
    foreign-language outlets, and that coverage is public. So the branch searches
    the open press for the same event and resolves to `recoverable` (an outlet
    we could wire — the valuable and probably common case), `vocabulary_gap` (we
    already read the outlets that carried it, so the miss is our terms), or
    `unreachable`, which is the only closed finding and the rare one. Filing the
    first two as closed would have written off the most learnable class of miss
    in the loop. The paywalled outlet is never proposed as a source, however the
    recovery turns out; the ACCESSIBLE one is.

  * IT NEVER STORES A ROW. A discovery signal is not evidence. Nothing here
    touches `extract_layoff_data`, `post_to_wordpress` or `/add`.

  * IT NEVER WIRES AN OUTLET. Every outlet lesson is a REVIEW instruction for a
    human, exactly like `health_digest`'s broken-scraper line. An aggregator or
    a competing tracker must never become a source, and the way to guarantee
    that is that this loop has no power to make anything a source.

  * IT NEVER PRINTS A NAME. See the next section, which is the reason this file
    is written the way it is.

THE PRIVACY PROBLEM, WHICH IS SHARPER HERE THAN ANYWHERE ELSE IN THE REPO.

Some curated digests are published BY a comparator. Under the standing rule no
comparator name, domain or figure may enter this repo, any commit, any PR, any
Actions log, any fixture or any public page. This loop reads a file that may
contain all three, on the owner's machine, and its whole job is to say
interesting things about what it read.

`benchmark_freshness.py` solved the same problem the only way it can be solved:
by shape, not by care. A reviewer noticing a name is not a mechanism; a function
that cannot spell one is. So:

  * `assert_nameless` below is an ALLOWLIST — numbers, ISO dates, and words from
    a frozen label set. It is not a filter over free text. Everything that
    reaches stdout or the committed trend file passes through it first, and the
    trend file is guarded BEFORE the write rather than after, so an unsafe value
    fails the run instead of being committed.

  * THE NAMED HALF NEVER REACHES STDOUT EITHER. This is the difference from
    `tracker_diff`, and it is deliberate. That loop runs on a runner where
    stdout is an Actions log, so its named half leaves by email and there is no
    third place for it to go. This loop runs on the owner's laptop, where stdout
    is a terminal that gets copied into chat windows and pull requests. So the
    lessons are written to a gitignored local file and mailed if keys are
    present, and the terminal gets ages and counts. The one thing a person is
    most likely to paste is the one thing that carries nothing.

  * THE DIGEST'S OWN IDENTITY CANNOT BECOME A LESSON. Any domain named in a
    `# from:` provenance comment is suppressed from every outlet lesson in that
    run, so the natural way to write down where a list came from is also the
    thing that stops it being suggested as a source. A local gitignored denylist
    is honoured on top of that.

THERE IS NO WORKFLOW FOR THIS FILE AND THERE MUST NOT BE. A workflow would need
the worklist, and the worklist in the repo IS the leak. It is local-only by
construction; `tests/test_curated_probe_leak.py` pins that no committed path
under the repo is ever read as a worklist.

WHAT THE TREND MEANS, SO IT IS NOT JUST A TO-DO LIST.

  A. CURATED RECALL — of the curated items we could judge, the share we already
     held, unaided. Nothing here stores a row, so every hit is independent by
     construction. This should trend UP as lessons are adopted.

  B. TAUGHT SHARE — the share of items that produced a lesson we do not already
     have. This should trend DOWN. It is the honest measure of DEPENDENCE on the
     curated source: when a domain expert's roundup can no longer teach us an
     outlet or a word, we have stopped needing it. Recall alone cannot say that,
     because recall rises when the digest gets easier as well as when we get
     better.

The two are recorded together under a versioned method (`c1`) so a trend line
can never silently splice two definitions of the same percentage.
"""
import json
import os
import pathlib
import re
import sys
from datetime import date, datetime, timezone

import requests

# ONE DEFINITION, IMPORTED RATHER THAN COPIED. These are the pure, tested
# judgement functions the daily learning loop already uses: what headcount a
# headline states, which employer it names, whether our rows answer it, whether
# our discovery vocabulary can see it, and whether the feed set already admits
# an outlet. Copying them here would let this loop and the ingest drift into two
# different answers to "did we hold this?", which is the defect this repo has
# paid for elsewhere. A rename upstream breaks this import loudly in CI, which is
# the correct failure — silent divergence is not.
from tracker_diff import (        # noqa: E402  (import order is deliberate)
    _covered_by_allowlist,
    headline_employer_token,
    headline_jobs,
    rows_verdict,
    vocab_hit,
    vocab_phrase,
)

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}

REPO = pathlib.Path(__file__).resolve().parent.parent
# LOCAL ONLY. `scratchpad/` is gitignored in its entirety, for exactly this
# reason and by the same decision that put the private benchmark there.
DEFAULT_WORKLIST = REPO / "scratchpad" / "recall-worklist.txt"
DEFAULT_DENYLIST = REPO / "scratchpad" / "recall-aggregators.txt"
DEFAULT_REPORT = REPO / "scratchpad" / "recall-lessons.md"
# The "have we suggested this before" ledger. Subjects are names, so it lives
# beside the worklist and only its counts ever cross into the repo.
DEFAULT_KNOWN = REPO / "scratchpad" / "recall-known.json"
# The refusal ledger: outlets we declined to read, and why. A paywall, a bot
# wall or a CAPTCHA is a permanent fact about a SOURCE and is worth keeping —
# but it is a name, so it stays local like everything else here.
DEFAULT_REFUSALS = REPO / "scratchpad" / "recall-refusals.json"

STATE_PATH = pathlib.Path(__file__).resolve().parent / "curated_probe_state.json"
HISTORY_MAX = 180
METHOD = "c1"

# Match window and floor are the learning loop's, for the same reasons stated
# there: announcement and effective dates legitimately differ by weeks, and a
# sub-floor headcount is a single-site note our net is not trying to catch.
MATCH_DAYS = max(7, int(os.environ.get("CURATED_MATCH_DAYS", "45")))

# The tier that should have caught a miss. Frozen vocabulary — these are OUR
# words, not anybody's name, which is why they are safe to print.
#
# THE INACCESSIBLE BRANCH IS THREE OUTCOMES, NOT ONE, and getting that wrong
# would have written off the most learnable class of miss in the loop. "The
# outlet I happened to read it in is paywalled" and "no accessible outlet
# reported this at all" are completely different findings, and the first is far
# more common: a major exclusive is picked up within hours by wires, trade press
# and foreign-language outlets covering the same deal. That follow-on coverage
# is public, and reading a news INDEX for it is ordinary discovery.
#
#   recoverable      — accessible coverage exists from an outlet we could wire.
#                      The valuable case. The lesson is that outlet.
#   vocabulary_gap   — accessible coverage exists from an outlet we ALREADY
#                      read, so the miss is our query terms, not the paywall.
#   should_have_held — accessible coverage exists, from a wired outlet, in
#                      wording we already search. Neither lesson applies and
#                      saying "unreachable" would be a lie.
#   unreachable      — no accessible outlet reported it. THIS is the closed
#                      finding, and it is the rare one.
#   recovery_unknown — the search could not be made. Absence of a signal is not
#                      a pass; it is certainly not "unreachable".
TIERS = ("not_in_feed_set", "vocabulary_gap", "no_origin", "recoverable",
         "should_have_held", "unreachable", "recovery_unknown", "unparsed")
# Precedence when an item earns more than one. `not_in_feed_set` outranks
# `vocabulary_gap` because wiring an outlet permanently raises recall for every
# future story it runs, whereas a term only helps where the crawler already
# reaches.
TIER_ORDER = ("recoverable", "not_in_feed_set", "vocabulary_gap",
              "should_have_held", "unreachable", "recovery_unknown",
              "no_origin", "unparsed")

# How many inaccessible items one run will chase in the open press. THE TRIGGER
# IS "AN EVENT WE KNOW OCCURRED AND DO NOT HOLD", NEVER "ENUMERATE EVERYTHING A
# CURATED LIST NAMES". Searching for a known event in the open press is
# discovery; walking a comparator's database is reconstructing it, which this
# cap exists to make structurally impossible as well as forbidden.
RECOVER_MAX = max(1, min(40, int(os.environ.get("CURATED_RECOVER_MAX", "12"))))

# `source_type` values we are willing to name in public output. Anything else is
# counted as "other" rather than printed, so a source type added later cannot
# widen what this file can spell.
HELD_TIERS = frozenset({"warn", "news", "sec", "edgar", "erm", "filing", "gov", "other"})

# An item the owner has already established is unreachable. Written by hand in
# the worklist; the point is that recording it CLOSES it.
_CLOSED_RX = re.compile(r"\[(paywall|paywalled|unreachable|bot ?wall|captcha)\]", re.I)
_URL_RX = re.compile(r"https?://\S+")


class LeakGuard(RuntimeError):
    """Raised when a value that could carry a name reaches a public sink."""


_PUBLIC_WORDS = frozenset(TIERS) | frozenset(HELD_TIERS) | frozenset({
    "curated", "ok", "unknown", "pass", "fail", "ran", "skipped", "idle",
    "none", METHOD,
})
_PUBLIC_KEYS = frozenset(TIERS) | frozenset(HELD_TIERS) | frozenset({
    "date", "method", "mode", "state", "worklist_date", "items", "judged",
    "matched", "unmatched", "unknown", "unparsed", "closed",
    "curated_recall_pct", "taught_pct", "lessons", "lessons_by_tier",
    "held_by_tier", "history", "reported", "emailed", "new_outlets",
    "new_terms",
})
_DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def assert_nameless(obj, path="root"):
    """Prove a structure carries no free text, recursively. Raises LeakGuard.

    A WHITELIST, not a filter: numbers, booleans, None, ISO dates and words from
    `_PUBLIC_WORDS`. The property is that a name cannot be SPELLED with the
    permitted vocabulary, so this holds against inputs nobody anticipated —
    which is the only kind that matters, since the whole risk is a file this
    repo has never seen.
    """
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        if obj in _PUBLIC_WORDS or _DATE_RX.match(obj):
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
    """One stdout line from a nameless fact dict. Raises on anything else."""
    assert_nameless(facts)
    parts = []
    for key in sorted(facts):
        val = facts[key]
        if isinstance(val, dict):
            inner = ", ".join(f"{k} {val[k]}" for k in sorted(val))
            if inner:
                parts.append(f"{key}: {inner}")
        elif val is not None:
            parts.append(f"{key} {val}")
    return "; ".join(parts)


# --- reading the worklist --------------------------------------------------

def registrable_domain(url):
    """The outlet host from a pasted URL, lowercased and stripped of `www.`.

    Deliberately NOT a public-suffix resolution: the value is compared against
    `TRUSTED_DOMAINS` by `_covered_by_allowlist`, which already judges a host
    against its parents, and a wrong guess at a suffix would only ever make an
    outlet look un-wired when it is wired — a false lesson, which the human
    review step catches. Returns '' when there is no host.
    """
    m = re.match(r"^https?://([^/\s:?#]+)", str(url or "").strip(), re.I)
    if not m:
        return ""
    host = m.group(1).lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def parse_worklist(text):
    """Parse the owner's pasted lines into items plus the suppressed domains.

    Returns (items, suppressed). An item is
    {headline, url, domain, closed} — the PRIVATE object, which never leaves
    this module except through the local report or the owner's inbox.

    THE FORMAT IS DELIBERATELY ALMOST NOTHING, because the ingest path only
    beats hand-pasting if it is faster than hand-pasting. One item per line, in
    any order: a URL anywhere on the line is the origin, whatever else is on the
    line is the headline. Blank lines are skipped. A `#` line is a comment and is
    NEVER parsed as an item — and a `# from:` comment additionally SUPPRESSES
    every domain it names, so writing down where a list came from is the same
    keystroke as guaranteeing that list can never be proposed as a source.
    """
    items, suppressed = [], set()
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            # Provenance comments feed the suppression set and nothing else.
            for url in _URL_RX.findall(line):
                dom = registrable_domain(url)
                if dom:
                    suppressed.add(dom)
            for tok in re.findall(r"\b([a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+)\b", line.lower()):
                suppressed.add(tok[4:] if tok.startswith("www.") else tok)
            continue
        marker = _CLOSED_RX.search(line)
        closed = bool(marker)
        reason = (marker.group(1).lower().replace(" ", "") if marker else "")
        line = _CLOSED_RX.sub(" ", line)
        urls = _URL_RX.findall(line)
        url = urls[0].rstrip(").,;") if urls else ""
        headline = _URL_RX.sub(" ", line)
        headline = re.sub(r"\s{2,}", " ", headline).strip(" -–—|\t")
        items.append({"headline": headline, "url": url,
                      "domain": registrable_domain(url), "closed": closed,
                      "reason": reason})
    return items, suppressed


def read_denylist(path):
    """Domains the owner has marked as aggregators. Local, gitignored, optional.

    Absence is not a failure and not a pass: with no denylist the loop still
    cannot wire anything, because it has no power to wire anything. This only
    stops a known aggregator from consuming a slot in the owner's review list.
    """
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return set()
    out = set()
    for raw in text.splitlines():
        line = raw.split("#")[0].strip().lower()
        if not line:
            continue
        dom = registrable_domain(line) or line.strip("/")
        if dom:
            out.add(dom[4:] if dom.startswith("www.") else dom)
    return out


# --- our own corpus --------------------------------------------------------

def our_rows(token, timeout=30):
    """Rows we hold for an employer token, or None when the lookup could not be
    made. None is UNKNOWN and leaves the denominator — an API blip must never be
    recorded as a miss, nor as a find. This is a read of our OWN public API and
    it is free; there is no paid call anywhere in this module."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not (site and token):
        return None
    try:
        r = requests.get(f"{site}/wp-json/layoffs/v1/query",
                         params={"company": token, "per_page": 50},
                         headers=UA, timeout=timeout)
        if r.status_code != 200:
            return None
        return r.json().get("data") or []
    except Exception:
        return None


def held_tier(rows, jobs, tolerance_pct=0.02):
    """Which tier of ours actually caught a held item, as a frozen label.

    THE POSITIVE SIGNAL IS WORTH KEEPING, and it is the reason this returns
    anything at all rather than a bare boolean. One of the owner's four was held
    only through a non-English report of an English-wire event, which says the
    multilingual sweep is carrying more than anyone assumed. A loop that records
    only its failures cannot tell you that.

    Any `source_type` outside the frozen set is reported as "other" rather than
    printed, so a source type added later cannot widen what this file can spell.
    """
    tolerance = max(1, int(round(jobs * tolerance_pct)))
    for row in rows or []:
        try:
            count = int(row.get("job_count") or 0)
        except (TypeError, ValueError):
            continue
        if count and abs(count - jobs) <= tolerance:
            tier = str(row.get("source_type") or "").strip().lower()
            return tier if tier in HELD_TIERS else "other"
    return "other"


# --- the post-mortem -------------------------------------------------------

def search_open_press(token, timeout=30):
    """Accessible coverage of the same event, from the news INDEX we already
    operate. Returns [{title, outlet}], or None when the search could not be
    made (UNKNOWN, never "nothing exists").

    THE INACCESSIBLE OUTLET'S PAGE IS NEVER FETCHED, AND NEITHER IS ANY OTHER
    OUTLET'S. The only host called is the Google News RSS index — the repo's
    existing free discovery source — and an outlet's IDENTITY arrives in that
    index's own `<source>` element. So the question this function answers ("who
    else covered this?") is answered without a single content request to any
    outlet, which is why no robots.txt, paywall or bot wall is engaged by it.
    Reading the index is not a workaround for the paywall; it is the ordinary
    discovery path, and the paywalled article stays unread.
    """
    from sources.google_news import _rss_url, _parse_items, UA as GN_UA
    from company_watchlist import query_for
    try:
        r = requests.get(_rss_url(query_for(token)), headers=GN_UA, timeout=timeout)
        if r.status_code != 200:
            return None
        items = _parse_items(r.text)
    except Exception:
        return None
    return [{"title": it.get("title") or "", "outlet": (it.get("source") or "").strip()}
            for it in items]


def recover(item, trusted, discovery, suppressed, search):
    """The inaccessible-source post-mortem. Returns (tier, lessons).

    Called when the owner marked an item paywalled, bot-walled or CAPTCHA'd. The
    SOURCE being inaccessible is recorded and stays recorded — but the EVENT
    usually is not, and stopping at "paywalled" would file the most learnable
    class of miss as closed.

    Pure given `search`, so the branch that decides "recoverable" versus
    "genuinely unreachable" is tested rather than trusted.
    """
    token = headline_employer_token(item.get("headline") or "")
    if search is None or not token:
        return "recovery_unknown", []
    hits = search(token)
    if hits is None:
        return "recovery_unknown", []

    lessons, open_outlets = [], []
    for hit in hits:
        outlet = str(hit.get("outlet") or "").strip().lower()
        if not outlet or outlet in suppressed:
            continue
        if not _covered_by_allowlist(outlet, trusted):
            open_outlets.append(outlet)
    if open_outlets:
        # RECOVERABLE — the valuable case. The lesson is the ACCESSIBLE outlet.
        # The paywalled one is NOT proposed as a source just because the event
        # turned out to be real; it stays in the refusal ledger with its reason.
        for outlet in list(dict.fromkeys(open_outlets))[:5]:
            lessons.append({
                "kind": "outlet", "subject": outlet,
                "detail": "accessible coverage of an event we missed behind an "
                          "inaccessible source",
            })
        return "recoverable", lessons

    if not hits:
        # GENUINELY UNREACHABLE. No accessible outlet reported it at all. This
        # is the closed finding, and it is the rare one.
        return "unreachable", []

    for hit in hits[:5]:
        title = hit.get("title") or ""
        if title and not vocab_hit(title, discovery):
            phrase = vocab_phrase(title) or title[:70]
            lessons.append({
                "kind": "vocabulary", "subject": phrase,
                "detail": "wording in accessible coverage that no discovery term matches",
            })
    if lessons:
        # The outlets were all wired. We could have read this and did not, so
        # the miss is our query terms, not the paywall.
        return "vocabulary_gap", lessons
    return "should_have_held", []


def diagnose(item, jobs, trusted, discovery, suppressed, search=None):
    """Why did we not hold this? Returns (tier, lessons) — lessons is a list of
    {kind, subject, detail}, the PRIVATE object.

    Pure, so the rule that assigns blame is tested rather than trusted.
    """
    if item.get("closed"):
        return recover(item, trusted, discovery, suppressed, search)

    lessons, tiers = [], []
    domain = (item.get("domain") or "").lower()
    headline = item.get("headline") or ""

    if not domain:
        tiers.append("no_origin")
    elif domain in suppressed:
        # The digest's own host, or a known aggregator. NEVER a lesson: storing
        # an aggregator as a source is the one thing that corrupts the only
        # measurement we trust. It is not even reported as a gap, because it is
        # not one.
        pass
    elif not _covered_by_allowlist(domain, trusted):
        tiers.append("not_in_feed_set")
        lessons.append({
            "kind": "outlet", "subject": domain,
            "detail": "carried a layoff story we do not hold and is not in the feed set",
        })

    if headline and not vocab_hit(headline, discovery):
        tiers.append("vocabulary_gap")
        phrase = vocab_phrase(headline) or headline[:70]
        lessons.append({
            "kind": "vocabulary", "subject": phrase,
            "detail": "wording no discovery term matches",
        })

    if not tiers:
        # Wired outlet, vocabulary we already search: the gap is neither of the
        # two things this loop can name. Saying "unparsed" would be a lie and
        # inventing a fifth tier for it would be worse; it is the residual, and
        # the honest thing is to count it without a lesson.
        return "no_origin" if not domain else "unparsed", lessons
    for tier in TIER_ORDER:
        if tier in tiers:
            return tier, lessons
    return "unparsed", lessons


# --- state -----------------------------------------------------------------

def _read_state():
    try:
        state = json.loads(STATE_PATH.read_text())
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _write_state(state):
    """Commit-bound measurement file. Guarded BEFORE the write, so an unsafe
    value fails the run instead of being committed."""
    assert_nameless(state)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def read_known(path):
    """Subjects earlier runs already surfaced. LOCAL, gitignored, never committed.

    THE DEPENDENCE TREND NEEDS "HAVE WE SEEN THIS ONE BEFORE", AND THE SUBJECTS
    ARE NAMES. So the ledger cannot live in the committed state file — but it
    does not need to. It lives beside the worklist, under the same gitignored
    directory, on the same machine, and only its COUNTS ever cross into the
    repo.

    Without this the loop can only report "distinct subjects this run", which
    would let a digest that names the same unwired outlet every week read as
    permanent teaching and make `taught_pct` a flat line that never falls. That
    is the number's entire purpose, so an approximation of it is worse than
    none.
    """
    try:
        blob = json.loads(pathlib.Path(path).read_text())
    except Exception:
        return {"outlet": set(), "vocabulary": set()}
    return {kind: set(blob.get(kind) or []) for kind in ("outlet", "vocabulary")}


def merge_refusals(path, new):
    """Append to the refusal ledger, newest reason wins per domain. LOCAL.

    Kept because a source that is paywalled today is paywalled tomorrow, and the
    loop should not re-derive that every week. It is deliberately NOT an input to
    any wiring decision: nothing here can wire anything, and a domain in this
    file must never be proposed as a source even when the event behind it turned
    out to be real and recoverable elsewhere.
    """
    try:
        blob = json.loads(pathlib.Path(path).read_text())
        ledger = blob if isinstance(blob, dict) else {}
    except Exception:
        ledger = {}
    for entry in new or []:
        dom = (entry.get("domain") or "").strip().lower()
        if not dom:
            continue
        ledger[dom] = {"reason": entry.get("reason") or "inaccessible",
                       "seen": entry.get("date") or ""}
    try:
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text(
            json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception:
        return {}
    return ledger


def write_known(path, known):
    try:
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text(json.dumps(
            {k: sorted(v) for k, v in known.items()}, indent=2) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


# --- the two sinks ---------------------------------------------------------

def render_report(items_seen, lessons, held, facts, fresh=None):
    """The NAMED half, for the owner only. Never printed, never committed."""
    fresh = fresh or {"outlet": set(), "vocabulary": set()}
    lines = [
        "# Curated recall probe — lessons",
        "",
        f"Run {facts['date']} (method {facts['method']}). "
        f"{facts['matched']} of {facts['judged']} judged items already held "
        f"({facts.get('curated_recall_pct')}% independent recall). "
        f"Still teaching us on {facts.get('taught_pct')}% of items.",
        "",
        "LOCAL FILE. Nothing below may enter the repo, a commit, a PR, an Actions",
        "log or a public page. What crosses over is the lesson, never the item and",
        "never where the list came from.",
        "",
    ]
    outlets = [l for l in lessons if l["kind"] == "outlet"]
    terms = [l for l in lessons if l["kind"] == "vocabulary"]
    if outlets:
        lines += ["## Outlets to review for the feed set", "",
                  "A wired outlet permanently raises recall. Review each one as a PRIMARY",
                  "source. Never wire an aggregator or another tracker.",
                  "NEW = not suggested by an earlier run. A repeat is the same gap still open.",
                  ""]
        seen = {}
        for l in outlets:
            seen[l["subject"]] = seen.get(l["subject"], 0) + 1
        for dom, n in sorted(seen.items(), key=lambda kv: (-kv[1], kv[0])):
            flag = "NEW " if dom in fresh.get("outlet", ()) else "again "
            lines.append(f"  - {flag}Review {dom} for sources/gdelt.py TRUSTED_DOMAINS "
                         f"({n} missed item(s)).")
        lines.append("")
    if terms:
        lines += ["## Wording to add to the discovery vocabulary", "",
                  "Vocabulary gaps are invisible until something like this surfaces them.", ""]
        seen_t = []
        for l in terms:
            if l["subject"] not in seen_t:
                seen_t.append(l["subject"])
        for subject in seen_t[:20]:
            flag = "NEW " if subject in fresh.get("vocabulary", ()) else "again "
            lines.append(f'  - {flag}Add to source_registry.GLOBAL_TERMS: "{subject}"')
        lines.append("")
    if held:
        lines += ["## Held, and by which tier", "",
                  "The positive signal: what our own pipeline caught unaided.", ""]
        for headline, tier in held[:40]:
            lines.append(f"  - [{tier}] {headline[:110]}")
        lines.append("")
    closed = [i for i in items_seen if i.get("closed")]
    if closed:
        lines += ["## Inaccessible sources (refusal ledger)", "",
                  "We never bypass a paywall, a bot wall or a CAPTCHA, so these outlets",
                  "stay unread and are NEVER proposed as sources. The EVENT behind each",
                  "one was then chased in the open press; anything recoverable appears in",
                  "the outlet section above, as the ACCESSIBLE outlet that carried it.",
                  ""]
        for i in closed[:20]:
            reason = i.get("reason") or "inaccessible"
            lines.append(f"  - [{reason}] {(i.get('domain') or '')} — "
                         f"{(i.get('headline') or '')[:90]}")
        lines += ["",
                  "A tier of `unreachable` in the run line means no accessible outlet",
                  "reported it at all. That is the only closed finding, and it is rare.",
                  ""]
    lines += [
        "## Apply",
        "",
        'Paste into a Claude Code session in the ai-layoff-tracker repo:',
        '  "Adopt the outlet and vocabulary lessons in scratchpad/recall-lessons.md,',
        '   then update the sources page and health labels in the same session."',
        "",
    ]
    return "\n".join(lines) + "\n"


def _email(report, facts):
    """Owner-only. Best-effort; never raises, and never prints a body — a failed
    send must not spill what it was carrying into the terminal."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return False
    try:
        requests.post(f"{site}/wp-json/layoffs/v1/alert",
                      json={"subject": f"Curated recall probe: {facts.get('lessons')} lesson(s)",
                            "message": report},
                      headers={**UA, "X-ALT-KEY": key}, timeout=30)
        return True
    except Exception:
        print("curated-probe: the lesson email could not be delivered (non-fatal); "
              "the local report was still written")
        return False


# --- the run ---------------------------------------------------------------

def run(worklist_path=None, denylist_path=None, report_path=None, known_path=None,
        refusal_path=None, search=search_open_press, today=None):
    """One probe. Returns the PUBLIC fact dict (never any name)."""
    today = today or date.today()
    worklist_path = pathlib.Path(worklist_path or os.environ.get("CURATED_WORKLIST")
                                 or DEFAULT_WORKLIST)
    denylist_path = pathlib.Path(denylist_path or os.environ.get("CURATED_DENYLIST")
                                 or DEFAULT_DENYLIST)
    report_path = pathlib.Path(report_path or os.environ.get("CURATED_REPORT")
                               or DEFAULT_REPORT)
    known_path = pathlib.Path(known_path or os.environ.get("CURATED_KNOWN")
                              or DEFAULT_KNOWN)
    refusal_path = pathlib.Path(refusal_path or os.environ.get("CURATED_REFUSALS")
                                or DEFAULT_REFUSALS)

    facts = {"date": today.isoformat(), "method": METHOD, "mode": "curated"}
    state = _read_state()
    history = [h for h in (state.get("history") or []) if isinstance(h, dict)]

    try:
        text = worklist_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        # No worklist is not a failure and not a pass. It is a loop with nothing
        # to read, which is the ordinary state between the owner's pastes.
        facts["state"] = "idle"
        facts["items"] = 0
        print("curated-probe:", public_render(facts))
        print("curated-probe: no worklist at the configured path — nothing to judge. "
              "Drop pasted items into it and run again.")
        return facts

    items, suppressed = parse_worklist(text)
    suppressed |= read_denylist(denylist_path)
    facts["items"] = len(items)
    try:
        stamp = datetime.fromtimestamp(worklist_path.stat().st_mtime, timezone.utc)
        facts["worklist_date"] = stamp.date().isoformat()
    except Exception:
        pass

    if not items:
        facts["state"] = "idle"
        print("curated-probe:", public_render(facts))
        return facts

    try:
        from sources.gdelt import TRUSTED_DOMAINS
        trusted = {d.lower() for d in TRUSTED_DOMAINS}
    except Exception:
        trusted = set()
    try:
        from source_registry import discovery_terms
        discovery = discovery_terms()
    except Exception:
        discovery = ()

    # TWO TALLIES, AND KEEPING THEM SEPARATE IS THE WHOLE CORRECTNESS OF THE
    # NUMBER. `matched`/`missed` is the RECALL denominator and admits only items
    # this loop could actually judge — a headcount to compare and an employer to
    # look up. `tiers` is the LESSON histogram and admits more, because an item
    # we could not score can still name an outlet we do not read.
    #
    # Folding them together was the first version's bug, caught on the first
    # live run: a self-probe built entirely from rows we demonstrably hold
    # scored 73.3%, because every sub-floor WARN line with no parseable
    # headcount had been counted as a coverage miss. That is our parser's floor
    # being reported as our pipeline's blind spot — a number that would have
    # trended on the wrong thing forever, and quietly, since it moves in the
    # believable direction.
    matched = missed = unknown = unparsed = closed = 0
    held, lessons, tiers = [], [], {}
    # Lessons grouped BY ITEM as well as flat, because dependence is a share of
    # items ("how often did the curator still have something to teach") while
    # the report is a list of subjects. Counting subjects over items is not a
    # proportion at all: one item naming an unwired outlet in unfamiliar wording
    # yields two lessons, and the first version of `taught_pct` duly reported
    # 200%.
    per_item = []
    refusals = []
    recovered = 0
    row_cache = {}
    for item in items:
        if item.get("closed"):
            # THE SOURCE IS INACCESSIBLE AND STAYS RECORDED AS SUCH. That fact
            # is real and belongs in the refusal ledger — and the paywalled
            # outlet is never proposed as a source, however the recovery turns
            # out.
            closed += 1
            refusals.append({"domain": item.get("domain") or "",
                             "reason": item.get("reason") or "inaccessible",
                             "date": today.isoformat()})
            # THE EVENT USUALLY IS NOT INACCESSIBLE. Chase it in the open press,
            # bounded — see RECOVER_MAX for why the bound is the guard against
            # this becoming database reconstruction rather than discovery.
            if recovered < RECOVER_MAX:
                recovered += 1
                tier, item_lessons = diagnose(item, 0, trusted, discovery,
                                              suppressed, search)
            else:
                tier, item_lessons = "recovery_unknown", []
            lessons.extend(item_lessons)
            per_item.append(item_lessons)
            tiers[tier] = tiers.get(tier, 0) + 1
            continue
        headline = item.get("headline") or ""
        jobs = headline_jobs(headline)
        token = headline_employer_token(headline)
        if not jobs or not token:
            unparsed += 1
            tier, item_lessons = diagnose(item, 0, trusted, discovery, suppressed)
            lessons.extend(item_lessons)
            per_item.append(item_lessons)
            tiers[tier] = tiers.get(tier, 0) + 1
            continue
        key = token.lower()
        if key not in row_cache:
            row_cache[key] = our_rows(token)
        rows = row_cache[key]
        if rows is None:
            unknown += 1          # our own API did not answer; judged nothing
            continue
        # DATELESS ON PURPOSE, AND IT LOOSENS THE MATCH — say so rather than
        # let a reader assume otherwise. A pasted line carries no reliable date
        # (the worklist format does not ask for one, because asking would cost
        # the ten seconds this whole design is built around), so `when=None`
        # makes this a company-and-headcount match. The failure mode is a stale
        # row of the same size for the same employer reading as a hit, which
        # flatters recall slightly. The alternative — scoring an event we do
        # hold as a miss because we could not date the paste — manufactures
        # lessons out of our own coverage, which is worse for a loop whose only
        # output is lessons.
        verdict = rows_verdict(rows, jobs, None, MATCH_DAYS)
        if verdict == "match":
            matched += 1
            held.append((headline, held_tier(rows, jobs)))
        elif verdict == "unknown":
            unknown += 1
        else:
            missed += 1
            tier, item_lessons = diagnose(item, jobs, trusted, discovery, suppressed)
            lessons.extend(item_lessons)
            per_item.append(item_lessons)
            tiers[tier] = tiers.get(tier, 0) + 1

    judged = matched + missed
    facts["judged"] = judged
    facts["matched"] = matched
    facts["unmatched"] = missed
    facts["unknown"] = unknown
    facts["unparsed"] = unparsed
    facts["closed"] = closed
    facts["curated_recall_pct"] = round(100.0 * matched / judged, 1) if judged else None
    facts["lessons"] = len(lessons)
    facts["lessons_by_tier"] = {t: tiers[t] for t in TIERS if tiers.get(t)}
    tier_counts = {}
    for _h, tier in held:
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    facts["held_by_tier"] = tier_counts

    known = read_known(known_path)
    fresh = {"outlet": set(), "vocabulary": set()}
    for l in lessons:
        if l["subject"] not in known.get(l["kind"], set()):
            fresh[l["kind"]].add(l["subject"])
    facts["new_outlets"] = len(fresh["outlet"])
    facts["new_terms"] = len(fresh["vocabulary"])

    # DEPENDENCE, the number that should FALL. A share of ITEMS: of everything
    # the curator handed us and we could examine, how often did they still have
    # something to teach. Two different questions from recall, which asks "of
    # what we could SCORE, how much did we hold" — an item we cannot score can
    # still name an outlet we do not read, so this denominator is the wider one.
    #
    # Counted as items-with-a-new-lesson rather than lessons, so it is a
    # proportion and cannot exceed 100.
    taught_items = sum(1 for ls in per_item
                       if any(l["subject"] in fresh[l["kind"]] for l in ls))
    lesson_base = len(per_item)
    facts["taught_pct"] = (round(100.0 * taught_items / lesson_base, 1)
                           if lesson_base else None)
    facts["state"] = "ran"

    report = render_report(items, lessons, held, facts, fresh)
    # The ledger is only advanced once the report that carries the suggestions
    # has been written. A run that could not tell the owner about an outlet must
    # not also record it as already suggested.
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        facts["reported"] = True
    except Exception:
        facts["reported"] = False
    facts["emailed"] = bool(lessons) and bool(_email(report, facts))
    if refusals:
        merge_refusals(refusal_path, refusals)
    if facts["reported"] or facts["emailed"]:
        for kind in ("outlet", "vocabulary"):
            known.setdefault(kind, set()).update(fresh[kind])
        write_known(known_path, known)

    history.append({k: facts[k] for k in
                    ("date", "method", "judged", "matched", "unmatched",
                     "curated_recall_pct", "taught_pct", "lessons") if k in facts})
    state["history"] = history[-HISTORY_MAX:]
    _write_state(state)

    print("curated-probe:", public_render(facts))
    print("curated-probe: the lessons are in the local report only "
          "(never stdout, never the repo).")
    return facts


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
