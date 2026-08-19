# AI causation — rows that need the owner's eye

Built 2026-08-19T06:07:06Z by `railway/ab_ai_causation.py` over `docs/recall-reference-sets/ai-causation-2026-08.sample.json`.

## How to use this file

Read the TEXT. The only question is: **does this text explicitly say AI, automation, machine learning or robots CAUSED these cuts, in a phrase quoted from the text itself?** A company's AI strategy, AI investment, AI products, or AI used to pick who goes is NOT a cause. That is the production rule, verbatim.

Write your call into `docs/recall-reference-sets/ai-causation-2026-08.adjudications.json` as `{"<id>": true|false}` — `true` means the text supports `ai_explicit`. Anything you leave out stays UNADJUDICATED and is scored nowhere; it is never quietly defaulted.

**Section 1 is the one that must be filled in** (0 rows): the two independent labellers disagreed, so there is no label at all. **Section 2** (0 rows) is optional and is where the candidate model disagrees with a label the two labellers agreed on. Filling it in removes the one bias left in the score — a two-model agreement standing in for truth exactly where the candidate objects.

---

## Section 1 — the labellers disagree (0 rows, REQUIRED)

_None. The two labellers agreed on every row._

---

## Section 2 — the candidate objects to a model-agreed label (0 rows, optional)

_None._

