#!/usr/bin/env python3
"""A three-model adjudication panel for a CONTESTED data judgment.

DORMANT (2026-08-26). Nothing in the live cron or pipeline calls this yet, it
writes no row, it touches no correction log, and it auto-applies nothing. This
is the reviewable core: the owner runs the DOGE dry-run below, and arming plus
wiring the apply path is a later, gated step.

WHAT IT IS
----------
A reusable primitive. A CALLER that has ALREADY decided one item is contested
(a held relabel, an ai_explicit call it is unsure of) hands the panel the row's
EVIDENCE and the PROPOSED change; the panel routes it to three INDEPENDENT
models, each of which must decide APPROVE / REJECT and QUOTE the evidence it
relied on, and returns a `PanelVerdict`. The panel does NOT scan rows and does
NOT decide what is contested: it fires only on conflict or impact, never on
volume, so its cost is bounded by the caller, not by the size of the table.

WHY THREE, AND WHY DIFFERENT FAMILIES
-------------------------------------
The failure this fights is CORRELATED error: two models that share a training
lineage can read the same ambiguous source the same wrong way and agree with
confidence. Three DIVERSE families lower the chance that a wrong reading is
unanimous. If two of `PANEL_MODELS` are the same provider, the word
"independent" in this file is a lie and the guarantee is gone -- keep them on
three different providers.

WHY THE AGGREGATION IS NOT MAJORITY RULES
-----------------------------------------
The two errors are not symmetric. A false APPLY on a public headline is a wrong
number readers and crawlers see; a false HOLD is one extra click for the owner.
So the expensive side is gated:

    verdict          when
    ---------------  ------------------------------------------------------
    AUTO_APPLY       unanimous approve (3-0), EVERY vote cited the evidence,
                     AND the change is UNDER the headline-mover bound.
    REJECT           at least one model rejected. The panel actively says no;
                     the bad suggestion would have been killed.
    HOLD_FOR_REVIEW  everything else -- a non-citing approve (not a clean
                     approve, so not unanimous), OR a headline-mover even at
                     3-0. Surfaced for the owner's ONE click, with the
                     dissent's reasoning and the 3-0 / 2-1 tally as confidence.

A HEADLINE-MOVER (job_count >= HEADLINE_MOVER_JOBS, the existing held-relabel
bound) NEVER auto-applies, even at a citing 3-0. The vote still rides along so
the owner sees whether the panel was unanimous.

The panel adjudicates JUDGMENTS, never MEASUREMENTS. A headline NUMBER stays an
invariant in data_integrity.py; nothing here votes on a count.

SPEND (CLAUDE.md, non-negotiable)
---------------------------------
Every model call goes through `spend.metered_call(make_call, ...)`, and the
`make_call` performs EXACTLY ONE request. The OpenAI/OpenRouter client is built
with `max_retries=0`, because the SDK's default of 2 re-POSTs from inside the
callable on a timeout -- and a timed-out completion may already have been
generated and billed, a charge no ledger, ceiling or $/row figure ever sees.
Retry, if ever wanted, belongs on `metered_call(attempts=N)`, which re-reads
the brake and meters every try. A budget stop raises `spend.PaidReadsOff`,
which this module lets PROPAGATE: a panel that could not afford to ask has
reached NO verdict, and callers must not read the exception as a REJECT.

Usage:
    python3 railway/adjudication_panel.py --demo            # DOGE fixture
    python3 railway/adjudication_panel.py --relabel-fixture # same fixture

    With no OPENROUTER_API_KEY the demo PREVIEWS: it prints the models it would
    call and the exact prompts, and spends nothing. With a key it makes the
    real three calls (each metered) and prints the verdict + per-model votes.
"""
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spend  # noqa: E402

try:                                # optional at import time; the dry-run
    from openai import OpenAI       # preview and the tests never need it
except Exception:                   # pragma: no cover - import guard
    OpenAI = None


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
#
# THREE DIFFERENT PROVIDERS. If two of these share a provider, they share a
# training lineage and correlated blind spots, and "independent panel" is a
# false claim -- the whole design is to make a wrong reading UNLIKELY to be
# unanimous. Override with ALT_PANEL_MODELS (comma-separated), keeping them on
# three distinct families.
# Three families the tracker's OpenRouter key can actually reach today. The key
# has no Anthropic access (a live DOGE dry-run on 2026-08-26 404'd on
# anthropic/claude-3.5-haiku: "No endpoints found"), so Claude is left out until
# Anthropic is enabled on the account; swap it in via ALT_PANEL_MODELS then.
# Google + DeepSeek + OpenAI are still three distinct lineages.
_DEFAULT_PANEL_MODELS = (
    "google/gemini-2.5-flash-lite",   # Google
    "deepseek/deepseek-chat",         # DeepSeek
    "openai/gpt-4o-mini",             # OpenAI
)


def _panel_models() -> tuple[str, ...]:
    raw = (os.environ.get("ALT_PANEL_MODELS") or "").strip()
    if raw:
        models = tuple(m.strip() for m in raw.split(",") if m.strip())
        if models:
            return models
    return _DEFAULT_PANEL_MODELS


PANEL_MODELS = _panel_models()

#: The meter books every panel call under this source tag, so the run breakdown
#: can say what the panel cost independently of the collectors.
PANEL_SOURCE = "panel"

#: A change at or above this job count NEVER auto-applies, even at a citing 3-0
#: (the existing held-relabel / headline-mover bound). It is always the owner's
#: one click; the panel vote rides along as confidence.
HEADLINE_MOVER_JOBS = 5000

# The three terminal verdicts.
AUTO_APPLY = "AUTO_APPLY"
HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
REJECT = "REJECT"


# --------------------------------------------------------------------------
# Value types
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Evidence:
    """What the models are shown. `excerpt` is the text they must quote from."""
    source_name: str
    url: str
    excerpt: str

    @classmethod
    def coerce(cls, value) -> "Evidence":
        if isinstance(value, Evidence):
            return value
        v = dict(value or {})
        return cls(source_name=str(v.get("source_name") or v.get("source") or ""),
                   url=str(v.get("url") or ""),
                   excerpt=str(v.get("excerpt") or v.get("text") or ""))


@dataclass(frozen=True)
class ProposedChange:
    """One field moving old -> new. `question` is what the panel must decide."""
    field: str
    old: str
    new: str

    def describe(self) -> str:
        return f"{self.field}: {self.old!r} -> {self.new!r}"


@dataclass
class Vote:
    """One model's decision.

    `approve` is Optional: True (approve), False (reject), or None when the
    response could not be parsed or the call errored -- an unparseable vote is
    neither a clean approve nor an explicit reject, so it can only hold the
    panel, never auto-apply it and never on its own reject.
    """
    model: str
    approve: Optional[bool]
    cited: bool
    reason: str
    cited_quote: str = ""
    error: str = ""

    @property
    def is_clean_approve(self) -> bool:
        return self.approve is True and self.cited and not self.error

    @property
    def is_reject(self) -> bool:
        return self.approve is False and not self.error


@dataclass
class PanelVerdict:
    verdict: str
    votes: list                     # list[Vote]
    unanimous: bool                 # every model voted approve (3-0), cited or not
    is_headline_mover: bool
    question: str = ""
    proposed_change: str = ""

    @property
    def approve_tally(self) -> str:
        approves = sum(1 for v in self.votes if v.approve is True)
        total = len(self.votes)
        return f"{approves}-{total - approves}"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "unanimous": self.unanimous,
            "is_headline_mover": self.is_headline_mover,
            "tally": self.approve_tally,
            "question": self.question,
            "proposed_change": self.proposed_change,
            "votes": [
                {"model": v.model, "approve": v.approve, "cited": v.cited,
                 "reason": v.reason, "cited_quote": v.cited_quote,
                 "error": v.error}
                for v in self.votes
            ],
        }


# --------------------------------------------------------------------------
# Prompting
# --------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are one of three independent reviewers on a data-quality panel for a "
    "layoff tracker. You judge whether ONE proposed change to a stored record "
    "is CORRECT given ONLY the evidence shown. You must ground your decision in "
    "the evidence: quote the exact span of the evidence you relied on. If the "
    "evidence does not support the change, reject it. Do not use outside "
    "knowledge and do not guess.\n\n"
    "Answer with ONE line of strict JSON and nothing else:\n"
    '{"approve": true or false, "cited_quote": "verbatim span from the '
    'evidence", "reason": "one sentence"}\n'
    "If you cannot find a span of the evidence that supports approving, set "
    "cited_quote to an empty string."
)


def build_prompt(question: str, evidence: Evidence,
                 proposed_change: ProposedChange) -> tuple[str, str]:
    """Return (system, user) for one reviewer. Pure; no I/O, no key needed."""
    user = (
        f"QUESTION: {question}\n\n"
        f"PROPOSED CHANGE\n  {proposed_change.describe()}\n\n"
        f"EVIDENCE\n"
        f"  source: {evidence.source_name}\n"
        f"  url: {evidence.url}\n"
        f"  excerpt:\n{evidence.excerpt.strip()}\n\n"
        "Decide whether the proposed change is CORRECT given the evidence. "
        "Quote the exact part of the evidence you relied on. Reply with the "
        "strict JSON line described in your instructions."
    )
    return _SYSTEM_PROMPT, user


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_vote(model: str, raw: str) -> Vote:
    """Parse one model's raw content into a Vote. A response we cannot read is
    approve=None (it holds the panel; it neither approves nor rejects)."""
    text = (raw or "").strip()
    match = _JSON_RE.search(text)
    if not match:
        return Vote(model=model, approve=None, cited=False,
                    reason="unparseable response", error="no JSON found")
    try:
        obj = json.loads(match.group(0))
    except Exception as exc:
        return Vote(model=model, approve=None, cited=False,
                    reason="unparseable response", error=f"bad JSON: {exc}")
    approve = obj.get("approve")
    if not isinstance(approve, bool):
        return Vote(model=model, approve=None, cited=False,
                    reason=str(obj.get("reason") or ""),
                    error="approve was not a boolean")
    quote = str(obj.get("cited_quote") or "").strip()
    return Vote(model=model, approve=approve, cited=bool(quote),
                reason=str(obj.get("reason") or ""), cited_quote=quote)


# --------------------------------------------------------------------------
# The one paid request
# --------------------------------------------------------------------------
def _default_call_model(model: str, system: str, user: str,
                        client_factory: Optional[Callable] = None) -> str:
    """Make EXACTLY ONE metered request to `model` and return the raw content.

    This is the only function here that spends. It is factored out so the tests
    can inject a fake `call_model` and never touch the network. Raises
    spend.PaidReadsOff when the brake is down -- adjudicate() lets that
    propagate, because a call that was not made is not a verdict.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; the panel cannot call")
    if client_factory is None:
        if OpenAI is None:
            raise RuntimeError("the openai client is not importable")
        # max_retries=0: the SDK defaults to 2 and re-POSTs on a timeout from
        # INSIDE the callable handed to metered_call -- a charge with no gate
        # read and no meter entry, and a timed-out completion may already be
        # billed. Retry only via spend.metered_call(attempts=N).
        client_factory = lambda: OpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=api_key,
            max_retries=0)
    client = client_factory()
    timeout = int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35"))
    spend.set_meter_context(PANEL_SOURCE)
    try:
        resp = spend.metered_call(
            model,
            lambda: client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=0, max_tokens=300, timeout=timeout,
            ),
            what=f"panel vote from {model}",
        )
    finally:
        spend.set_meter_context(None)
    return resp.choices[0].message.content or ""


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------
def _aggregate(question: str, proposed_change: ProposedChange,
               job_count: int, votes: list) -> PanelVerdict:
    is_headline_mover = int(job_count or 0) >= HEADLINE_MOVER_JOBS
    n = len(votes)
    rejects = [v for v in votes if v.is_reject]
    clean_approves = [v for v in votes if v.is_clean_approve]
    unanimous = n > 0 and all(v.approve is True for v in votes)

    if rejects:
        # Any explicit reject kills it. The panel actively says no.
        verdict = REJECT
    elif n > 0 and len(clean_approves) == n:
        # Unanimous AND every vote cited the evidence. The only path to
        # auto-apply -- and only under the headline-mover bound.
        verdict = HOLD_FOR_REVIEW if is_headline_mover else AUTO_APPLY
    else:
        # Everything else: a non-citing approve, an unparseable vote, an empty
        # panel. Not clean-unanimous, no explicit reject -> the owner decides.
        verdict = HOLD_FOR_REVIEW

    return PanelVerdict(
        verdict=verdict, votes=votes, unanimous=unanimous,
        is_headline_mover=is_headline_mover, question=question,
        proposed_change=proposed_change.describe(),
    )


def adjudicate(question: str, evidence, proposed_change, job_count: int,
               models=PANEL_MODELS, call_model: Optional[Callable] = None
               ) -> PanelVerdict:
    """Route one CONTESTED judgment to the panel and return a PanelVerdict.

    `evidence` is an Evidence (or a dict coerced to one); `proposed_change` is
    a ProposedChange (or a dict). `call_model(model, system, user) -> str` does
    the single metered request; the default spends, the tests inject a fake.

    spend.PaidReadsOff propagates: a panel that could not afford every vote has
    reached no verdict, and the caller must leave the item queued.
    """
    evidence = Evidence.coerce(evidence)
    if isinstance(proposed_change, dict):
        proposed_change = ProposedChange(
            field=str(proposed_change.get("field") or ""),
            old=str(proposed_change.get("old") or ""),
            new=str(proposed_change.get("new") or ""))
    caller = call_model or _default_call_model
    votes: list = []
    for model in models:
        system, user = build_prompt(question, evidence, proposed_change)
        # PaidReadsOff is NOT caught: a budget stop is undecided, not a reject.
        raw = caller(model, system, user)
        votes.append(parse_vote(model, raw))
    return _aggregate(question, proposed_change, job_count, votes)


# --------------------------------------------------------------------------
# Adapters (pure functions; no pipeline wiring, no writes)
# --------------------------------------------------------------------------
def adjudicate_relabel(row: dict, field: str, old, new, evidence,
                       models=PANEL_MODELS, call_model=None) -> PanelVerdict:
    """A held relabel (the DOGE class: an industry or country correction).

    Asks the panel whether moving `field` from `old` to `new` is CORRECT given
    the evidence. Reads job_count off the row for the headline-mover gate.
    """
    company = row.get("company") or row.get("employer") or "this employer"
    question = (
        f"Should the {field} of the {company} layoff record be changed from "
        f"'{old}' to '{new}'? Approve only if the evidence supports '{new}'."
    )
    change = ProposedChange(field=field, old=str(old), new=str(new))
    return adjudicate(question, evidence, change,
                      job_count=int(row.get("job_count") or 0),
                      models=models, call_model=call_model)


def adjudicate_ai_causation(row: dict, evidence,
                            models=PANEL_MODELS, call_model=None) -> PanelVerdict:
    """An ai_explicit call. The ruled speaker question (CLAUDE.md): ai_explicit
    requires THE EMPLOYER to have attributed the cuts to AI. A report counts
    when it quotes or reports the employer saying it; a journalist's own
    characterisation is the broad ai_linked tier, NOT this.
    """
    company = row.get("company") or row.get("employer") or "this employer"
    question = (
        f"Did the EMPLOYER ({company}) attribute these job cuts to AI or "
        "automation? Approve ai_explicit ONLY if the evidence quotes or reports "
        "the employer itself naming AI/automation as a cause. A journalist's "
        "own framing, an analyst's opinion, or a future projection does NOT "
        "count."
    )
    change = ProposedChange(field="ai_explicit",
                            old=str(row.get("ai_explicit", "false")),
                            new="true")
    return adjudicate(question, evidence, change,
                      job_count=int(row.get("job_count") or 0),
                      models=models, call_model=call_model)


# --------------------------------------------------------------------------
# Committed dry-run fixture (the real held DOGE case)
# --------------------------------------------------------------------------
DOGE_FIXTURE = {
    "row": {
        "company": "Department of Government Efficiency Service (DOGE)",
        "job_count": 60000,
        "industry": "Government & Nonprofit",
        "country": "United States",
    },
    "relabels": [
        {"field": "industry", "old": "Government & Nonprofit",
         "new": "Aerospace & Defense"},
        {"field": "country", "old": "United States",
         "new": "Multiple countries"},
    ],
    "evidence": {
        "source_name": "wire report (fixture)",
        "url": "https://example.invalid/doge-fixture",
        "excerpt": (
            "The Department of Government Efficiency Service (DOGE), the "
            "cost-cutting effort led by Elon Musk, drove roughly 60,000 U.S. "
            "federal job reductions across civilian agencies. The Pentagon was "
            "among the departments affected, but the reductions were carried "
            "out by federal agencies of the United States government, not by a "
            "defense contractor, and the affected employees were based in the "
            "United States."
        ),
    },
}


# --------------------------------------------------------------------------
# Dry-run CLI
# --------------------------------------------------------------------------
def _preview(models, question, evidence: Evidence,
             change: ProposedChange) -> None:
    system, user = build_prompt(question, evidence, change)
    print("  would call: " + ", ".join(models))
    print("  --- system prompt ---")
    print("  " + system.replace("\n", "\n  "))
    print("  --- user prompt ---")
    print("  " + user.replace("\n", "\n  "))


def _print_verdict(v: PanelVerdict) -> None:
    print(f"VERDICT: {v.verdict}   tally={v.approve_tally}   "
          f"unanimous={v.unanimous}   headline_mover={v.is_headline_mover}")
    print(f"  question: {v.question}")
    print(f"  change:   {v.proposed_change}")
    for vote in v.votes:
        mark = {True: "APPROVE", False: "REJECT", None: "NO-VOTE"}[vote.approve]
        cite = "cited" if vote.cited else "NOT cited"
        print(f"    [{mark:7}] {vote.model}  ({cite})")
        if vote.reason:
            print(f"             reason: {vote.reason}")
        if vote.cited_quote:
            print(f"             quote:  {vote.cited_quote}")
        if vote.error:
            print(f"             error:  {vote.error}")


def _run_demo() -> int:
    fx = DOGE_FIXTURE
    row = fx["row"]
    evidence = Evidence.coerce(fx["evidence"])
    have_key = bool(os.environ.get("OPENROUTER_API_KEY"))
    models = PANEL_MODELS

    print("=" * 72)
    print("ADJUDICATION PANEL - DRY RUN (DOGE held-relabel fixture)")
    print(f"company:   {row['company']}")
    print(f"job_count: {row['job_count']}  "
          f"(headline-mover bound is {HEADLINE_MOVER_JOBS}: "
          f"{'YES, never auto-applies' if row['job_count'] >= HEADLINE_MOVER_JOBS else 'no'})")
    print(f"models:    {', '.join(models)}")
    print(f"api key:   {'present -- will make real metered calls' if have_key else 'ABSENT -- preview only, spends nothing'}")
    print("=" * 72)

    for rel in fx["relabels"]:
        change = ProposedChange(field=rel["field"], old=rel["old"], new=rel["new"])
        question = (
            f"Should the {change.field} of the {row['company']} layoff record "
            f"be changed from '{change.old}' to '{change.new}'? Approve only if "
            f"the evidence supports '{change.new}'."
        )
        print(f"\n### PROPOSED RELABEL: {change.describe()}")
        if not have_key:
            _preview(models, question, evidence, change)
            continue
        try:
            verdict = adjudicate_relabel(row, change.field, change.old,
                                         change.new, evidence, models=models)
        except spend.PaidReadsOff as exc:
            print(f"  UNDECIDED (budget stop, no verdict): {exc}")
            continue
        _print_verdict(verdict)

    if not have_key:
        print("\n(no OPENROUTER_API_KEY -- this was a preview. Set the key to "
              "make the three real metered calls.)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true",
                    help="run the panel on the committed DOGE fixture")
    ap.add_argument("--relabel-fixture", action="store_true",
                    help="alias for --demo")
    args = ap.parse_args(argv)
    if args.demo or args.relabel_fixture:
        return _run_demo()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
