# Incident classes

A fixed vocabulary for the **shape** of a defect, so recurrence can be counted
instead of remembered.

## Why this exists

Two learning layers already work here, and neither is the gap.

1. **Per bug.** 170 of 213 test files in `railway/tests/` name the date of the
   incident that produced them. Those exact bugs do not come back.
2. **Per pattern.** `CLAUDE.md`'s *"Iron rules learned the hard way"* — 16
   rules, ~179 lines — generalises the lesson beyond the instance, and is
   loaded into every session. It works: sessions apply those rules without
   rediscovering them.

What is missing is the link between the two. When a new incident arrives,
nothing says **"this is the fifth time this shape has happened, and rule 7 was
supposed to have stopped it."** So a rule that is too narrow, or that is being
violated repeatedly in new places, looks exactly like a rule that is working.

This file closes that with one line per TECHLOG entry. It is deliberately NOT a
classifier: a keyword pass over the prose was tried on 2026-08-28 and matched
150 of 232 entries to a single class, because words like "window" and "average"
are everywhere. **A crude classifier that looks like learning is worse than
none**, so the class is DECLARED by whoever writes the entry, not guessed.

## How to use it

Every new `docs/TECHLOG.md` entry carries, anywhere in its body:

```
**Class:** silent-stop
**Guard:** railway/tests/test_gdelt_ledger_persistence.py
```

- `Class` is exactly one slug from the table below, or `novel`.
- `Guard` is the test that now fails on this defect, or `none` with a reason on
  the same line. `none` is an honest state; a missing tag is not.

Choosing `novel` is a real signal, not an escape hatch: it means the shape is
new, and a shape that recurs after being called novel is a candidate for a
seventeenth iron rule.

## The vocabulary

Derived from the iron rules and from the recurring shapes in 232 TECHLOG
entries. Add a slug only when an incident genuinely fits none of these — and
say so in the entry.

| slug | the shape | iron rule it belongs to |
|---|---|---|
| `silent-stop` | a mechanism stopped doing its work and no surface reported it | — (the cross-cutting one) |
| `absent-read-as-ok` | missing from a registry or ledger read as "no problem" rather than "never looked at" | *a source that never reports does not show up green* |
| `started-not-finished` | a start with no paired finish, counted as a success | *"the collector started" is not "the collector finished"* |
| `ran-but-brought-nothing` | activity mistaken for freshness; a frozen source clears a count floor | *"the collector ran" is not "brought back anything new"* |
| `true-but-empty` | a check passed because there was nothing to check (`0 of 0`) | *source health is not data integrity* |
| `guard-went-vacuous` | a test or guard stopped testing anything and stayed green | — |
| `two-copies-drifted` | duplicated logic diverged across surfaces | *retiring a source takes THREE steps* |
| `derived-value-typed-by-hand` | a computed fact hardcoded, then went stale | *never type a cadence into reader-facing copy* |
| `wrong-scope-or-key` | a dedup, cache, alarm or rotation keyed on the wrong thing | *a rotating query set must never derive its own run counter* |
| `cache-served-stale` | the origin was correct and the reader was served something older | *a version number is not the content* |
| `unmetered-spend` | a paid path outside the gate, or a retry nobody counted | *never make a paid model call outside `metered_call()`* |
| `unbounded-growth` | a store with no ceiling, or a backlog that can never drain | — |
| `novel` | none of the above fits | → candidate for a new iron rule |

## What this measures, and what it does not

It measures **recurrence**: how often a shape comes back, and whether it comes
back *after* a guard for it shipped. A class that keeps recurring after its
guard means the guard is too narrow — which is the single most useful thing
this can tell anyone, and the thing no surface says today.

It does **not** measure severity, and it must not be read as a ranking. It also
only works forward: entries before 2026-08-28 are deliberately not
back-tagged, because tagging 232 entries from prose is the same guessing this
file exists to avoid.
