# AI causation — recommended rulings, for confirmation

> ## RULED AND CONFIRMED IN PART, 2026-08-19
>
> **The speaker question is answered: `ai_explicit` requires THE EMPLOYER to have
> attributed the cuts to AI.** A report counts when it quotes or reports the
> employer saying it. A journalist's own characterisation, with no such statement
> from the employer, is the BROAD tier (`ai_linked`), not this one. The rule is now
> written where a reader can check it (methodology `#m-ai`), asked for in
> `extractor.ai_causation_prompt()` and `SYSTEM_PROMPT` rule 2, and described in
> `alt_allowed_ai_causation()`. It is no longer derived across three files and
> stated in none.
>
> **The reason for that answer, on the record.** The product already answers the
> other question separately. It runs two tiers: a strict one that is the employer's
> own words with a quote on file, and a broad one that is employer words PLUS press
> framing. Ruling "source" would collapse the two and delete the distinction. The
> broad tier exists precisely to hold press-attributed cuts.
>
> **27 of the 33 recommendations are now live rulings.** 25 were accepted as
> written; **107481 (GoKwik)** and **107491 (Snowflake)** were flipped to `false` by
> the ruling, as this file said they would be.
>
> **107375 (General Motors) stays out of the JSON and stays the owner's.** The
> speaker ruling does not settle it: GM cut IT staff in order to re-hire people with
> stronger AI skills, so nobody was replaced by a machine and the open question is
> whether an "AI skills swap" is AI causing the cuts at all.
>
> ### The ruling reaches SIX more rows than this file said it did
>
> This file named three rows as turning on the speaker question. Re-reading every
> recommended-AI row against the ruled test finds six more whose stored text carries
> **no employer attribution at all**. They are recommended `false` under the ruling
> and remain **PARKED**, because five of them are stored LIVE as `ai_explicit=1`:
>
> | id | company | who actually said AI |
> |---|---|---|
> | 70293 | Snap | "AI **push leads to** 1,000 job cuts" is the headline. No employer statement in the text. |
> | 70653 | TikTok | "**It also claims that** TikTok is looking to replace the moderators…" — a third party's claim. |
> | 54973 | Microsoft / MSN | "The layoffs are part of a bigger push **by Microsoft** to rely on AI" — the reporter's framing. |
> | 48830 | Suncor | "Driverless technology is only just starting to cause layoffs" — the reporter's, and generic. |
> | 70683 | ByteDance / TikTok | "cuts hundreds of jobs **in shift towards** AI content moderation" — headline framing. |
> | 70681 | TikTok | The company confirmed the layoffs, **not the reason**. Press purpose clause. |
>
> Confirming those five would add five rows to the corrections worklist for the
> number this product is named after, so a session does not get to make that call.
> Strip the six `rec:` prefixes to accept, or flip a value first to disagree.
>
> **Corroboration the ruling is the right one:** production already stores 107481,
> 107491 and 107469 as `ai_linked`, the broad tier. The live classifier was applying
> the speaker rule before anybody wrote it down.
>
> ### What `--rescore` actually returns now (193 gold labels, $0.00)
>
> | model | precision (pop-weighted) | recall (pop-weighted) |
> |---|---|---|
> | `deepseek/deepseek-chat` (incumbent, a labeller) | 75.8% (CI 56.0–89.4%) | 88.1% (CI 68.8–96.2%) |
> | `openai/gpt-4.1-mini` (referee, a labeller) | 82.6% (CI 62.1–92.8%) | 83.8% (CI 61.1–94.1%) |
> | `google/gemini-2.5-flash-lite` (**production**) | **78.5%** (CI 57.2–91.6%) | **78.1%** (CI 56.3–91.5%) |
>
> Fair head-to-head on the 27 adjudicated rows: referee 16/27 = 59.3%, incumbent
> 14/27 = 51.9%, candidate 13/27 = 48.1%. All three intervals overlap heavily.
>
> **VERDICT ON THE 2026-08-07 SWAP: still UNKNOWN.** Seven rows carry no label —
> GM plus the six parked. That is a legitimate UNKNOWN and must not be read as a pass.
>
> **The provisional numbers below this banner did not reproduce.** This file
> projected prec 80.9% / rec 72.6% for the candidate at 199 rows; the harness run at
> 199 rows returns **69.5% / 78.1%**. The file warned that nothing on disk could
> reproduce them, and it was right to. Quote the harness, never the projection.
>
> ### The stored-value disagreement list is now TEN, not thirteen
>
> The ruling removed three of the seven flips that would have moved a row **into**
> the AI count, which was the riskiest half of the list. Still unqueued, still for a
> separate reviewed pass:
>
> - **into** the AI count (stored `false`, ruled AI): `60800`, `107469`, `54968`, `49084`
> - **out of** the AI count (stored `true`, ruled not AI): `49090`, `26455`, `306`, `176954`, `70469`, `293`
> - `70681`, `107481`, `107491` have **left** the list: all three are ruled `false` and stored `false`, so there is nothing to correct.
> - If the six parked rows are later confirmed, five more join the **out of** side: `70293`, `70653`, `54973`, `48830`, `70683`.
>
> Nothing is queued. `/edit` sets `edited=1`, rewrites the dedup hash and publishes
> to the public corrections log.

---

**Status: RECOMMENDATION. Nothing here is decided.** Produced 2026-08-19 by a
Claude session that read each row's stored text against the **written** rubric
and nothing else. No model was asked to break a tie, no labeller vote was
consulted, no paid call was made. Your job here is *read and confirm*, not read
and decide.

Rulings live in `ai-causation-2026-08.adjudications.json`, **parked** under a
`rec:` prefix. The prefix is a guard, not a label: `read_adjudications()` does
not see a `rec:` key as a ruling, so **a `--rescore` run today folds in zero of
them** — coverage stays 175 of 200 and the verdict stays UNKNOWN. Every run
prints how many are parked, so the next session finds pending work rather than
an empty file. `railway/tests/test_adjudication_parking.py` pins it.

**To confirm a row**, strip its prefix — `"rec:70293": true` becomes
`"70293": true`. **To disagree**, flip its `true`/`false` first. **To send it
back to unadjudicated**, delete the line. **To confirm the lot in one edit:**

```bash
sed -i '' 's/"rec:/"/' docs/recall-reference-sets/ai-causation-2026-08.adjudications.json
# then set "_confirmed_by" to your name, and:
python3 railway/ab_ai_causation.py --rescore
```

---

## The rubric, as it was applied

It is not written in one place. It is four fragments that agree:

1. **`railway/extractor.py :: ai_causation_prompt()`** — the production ask, verbatim:
   *"AI is primary/contributing only if this text explicitly says AI, automation,
   machine learning or robots caused the cuts. A general AI strategy, investment,
   or use of AI in operations is not causal. Never infer. The phrase must be an
   exact quote from the supplied text."*
2. **`finalize_ai_causation()`** — a causal label whose quote is not verbatim in the
   text is downgraded to `unknown`. The receipt is half the rule.
3. **methodology page `#m-ai`** — five classes; only `primary_cause` and
   `contributing_cause` earn the tag; *"AI investment, projections about future
   automation, and AI used to select workers do not qualify on their own."*
4. **`cpt.php :: alt_allowed_ai_causation()`** — `ai_linked` is the *broad* bucket:
   *"cuts the company or press tied to AI loosely (funding an AI pivot, AI-driven
   market disruption, press AI framing). It never sets `ai_explicit`."*

Reduced to a test, applied identically to all 34 rows:

- **TRUE** — the text names AI / automation / machine learning / robots **and**
  asserts a causal or substitutive relation to *these* cuts: AI does the work the
  cut staff did, or the cuts were made *because of* / *in order to* AI.
- **FALSE** — the text only **associates**: "amid", "as", "while", an AI strategy,
  an AI investment or pivot, an AI product line, AI as a market driver, a forecast
  about future automation, AI used to pick *who* goes, or no AI vocabulary at all.
- **Speaker is not the discriminator.** `ai_linked` puts "the company **or press**"
  on the loose side, so what separates strict from broad is how explicit the
  causal claim is, not who made it. See the caveat at the bottom — this is the one
  part of the rubric that is *derived*, not stated.

---

## Section 1 — the 25 the labellers could not agree on (24 ruled, 1 left to you)

| id | company | deciding phrase from the text | rec | why, under the rubric |
|---|---|---|---|---|
| 70293 | Snap | "AI **push leads to** 1,000 job cuts" | **AI** | Explicit causal verb tying the AI push to the cuts. Not "amid". |
| 26455 | AWS | "**just a month after** CEO Andy Jassy warned that … **would trigger** a workforce reduction" | **not AI** | A prior *projection*, joined to these cuts by nothing but time. "Never infer"; projections do not qualify. |
| 70653 | TikTok | "looking to **replace the moderators with** artificial intelligence-driven systems" | **AI** | Substitution stated: AI takes over the cut workers' function. |
| 306 | BlackRock | "coming shifts in the asset management industry, **of which AI is among several drivers**" | **not AI** | AI as a *market* driver, cuts made to *prepare for* it. That is verbatim the `ai_linked` bucket. |
| 54973 | Microsoft/MSN | "**The layoffs are part of** a bigger push … **to rely on artificial intelligence to pick news and content**" | **AI** | AI performs the journalists' own job, and the text ties the layoffs to it. |
| 107465 | Upwork | "**AI means smaller**, differently resourced teams … can make a bigger impact" | **AI** | CEO's own memo announcing a 24% cut gives AI as the reason the teams are smaller. *Close call.* |
| 49090 | Allstate | *(no AI/automation word appears anywhere in the text)* | **not AI** | QuickFoto is described as a customer self-service feature. The stored quote "Automation is hitting office jobs" is the article title, not in the text. Fails the verbatim rule outright. |
| 107459 | Skai | "in light of new technologies, **with an emphasis on artificial intelligence**" + "Company attributed the cuts to AI's impact on operations" | **AI** | Company's own attribution of these cuts. |
| 107479 | Mews | "**AI now handles much of the execution layer of the work** at scale" | **AI** | Founder states AI does the work. Substitution. |
| 48830 | Suncor | "Driverless technology is only just **starting to cause layoffs**" | **AI** | Robots named as the cause, in those words. |
| 70683 | ByteDance/TikTok | "cuts hundreds of jobs **in shift towards AI content moderation**" | **AI** | Same fact pattern as 70653 and 70681; the cut function is the one AI assumes. |
| 176954 | Statista | "cuts 80 jobs **amid** AI-driven data automation **strategy**" | **not AI** | "amid" + "strategy" — co-occurrence with an AI strategy, twice excluded. |
| 177188 | Key Tronic | "**In order to** better align costs … **and boost automation**, the Company cut approximately 300 jobs" | **AI** | The company's own 8-K gives automation as a purpose of the cuts. "automation" is in the rubric's vocabulary. |
| 107477 | Elementor | "Company statement **explicitly framed the cuts as a reset for an AI era**" + "AI agents are becoming key builders" | **AI** | Company attribution, AI agents doing the work. |
| 70681 | TikTok | "lay off hundreds globally … **to improve AI-driven content moderation**" | **AI** | Purpose clause. Must match 70653/70683 — one fact pattern, one ruling. *(Flips a stored `false`.)* |
| 48844 | Amazon 2019 | "deploying machines … to automate the process of packing" | **not AI** | The text never connects the machines to any job loss. "Never infer." |
| 60800 | State Street | "Workforce reduction of 6% … **as the Company realizes benefits of automation** and standardized global processes" | **AI** | The company's own filing gives automation as the enabling reason, in the same clause. *Close call — the connective is "as", and offshoring/standardisation are bundled in.* |
| 286 | NAB | "The union says … **banks** replace them with offshoring and automation" | **not AI** | Generic sector commentary about "banks", not an attribution of NAB's 400 roles. |
| 177401 | Google | "AI 不該是變相砍人藉口" (*AI should not be a pretext for cutting people*) | **not AI** | Employees **disputing** AI as the reason. Nearer an explicit denial than an attribution. |
| 107519 | Shopify | "The cuts **come as** the company continues reducing headcount **while** pushing employees to adopt AI tools" | **not AI** | Two co-occurrence connectives, and AI-tool adoption is "use of AI in operations". Text itself notes the company did not name AI and the Lutke memo predates the round. |
| 69997 | Omron | "to cut 2,000 jobs **on slow China automation ops**" | **not AI** | Automation is Omron's *product market*. Weak demand caused the cuts. |
| 107469 | InvestCloud | "Yabuki cited '**accelerating AI productivity and time-to-market gains**' **among three drivers**" | **AI** | CEO's memo names AI productivity as a driver of the reduction. Contributing cause is enough. *(Flips a stored `false`.)* |
| 107481 | GoKwik | "**The layoffs were part of** the startup's **AI push as it seeks to automate more of its operations**" | **AI** | Explicit: the cuts belong to an operations-automation programme. **Turns on the speaker question — see below.** *(Flips a stored `false`.)* |
| 51765 | Meta | "alleging **AI-driven layoff picks**" | **not AI** | AI used to select *who* goes. Named exclusion, verbatim. |
| **107375** | **General Motors** | "GM just laid off hundreds of IT workers **to hire those with stronger AI skills**" | **LEFT TO YOU** | See below. |

## Section 2 — the 9 the candidate disputes (all 9 ruled)

| id | company | deciding phrase from the text | rec | why, under the rubric |
|---|---|---|---|---|
| 70469 | Standard Chartered | "**For years** the bank has helped colleagues 'whose roles may be displaced by automation'" | **not AI** | The only automation phrase in the text describes a long-running reskilling programme, not these 7,800 roles. Joining them is inference. *Close call, and it flips a stored `true`.* |
| 26465 | TCS | "its steepest job-cuts ever **due to the AI boom** and the strained India-US ties" | **AI** | "due to" — explicit, company's own cuts, contributing cause alongside geopolitics. |
| 293 | Commonwealth Bank | "announced 45 job cuts …, **as** it introduced an AI 'voice-bot'" | **not AI** | The supplied snippet only places the cuts next to the voice-bot. The stored quote "due to artificial intelligence" is **not in this text**. *Close call — the underlying ABC article is stronger than the snippet; see the snippet caveat.* |
| 176687 | ING | "950 Job Cuts in the Netherlands **Due to AI** and Digitalization" | **AI** | "Due to AI", verbatim, about these cuts. |
| 54968 | Bounce | "We let go of about four … **because we have a lot of automation**" | **AI** | The CEO's own words: "because". Automation is in the vocabulary. *(Flips a stored `false`.)* |
| 278 | WiseTech | "**amid** AI overhaul" / "artificial-intelligence-**linked** job reductions" | **not AI** | The text uses the broad tier's own vocabulary — "amid", "linked". |
| 49084 | Infosys | "11,000 jobs have been **released due to automation**" | **AI** | Company's AGM statement, "due to". *(Flips a stored `false`.)* |
| 107497 | MercadoLibre | "**as part of** its artificial intelligence **expansion efforts**"; "the decision **was not driven by direct substitution** of employees by automated systems" | **not AI** | An AI *expansion* is a pivot (broad tier), and the company denies substitution. |
| 107491 | Snowflake | "**work absorbed by AI** 'Project SnowWork'" | **AI** | The documentation team's work is taken over by AI. Substitution stated. **Turns on the speaker question.** *(Flips a stored `false`.)* |

---

## The one row the rubric does not answer: 107375, General Motors

> "GM just laid off hundreds of IT workers **to hire those with stronger AI skills**" — press
> attribution; GM's own statement named no AI.

The **speaker** half of this is answerable (see below). What is left is not:

> **Are cuts made to re-staff with AI-skilled *humans* "AI causing the cuts"?**

Nobody was replaced by a machine here. AI is the reason the required skill set
changed, and the cuts are the means. The rubric's inclusion test ("explicitly
says AI … caused the cuts") arguably catches it; its exclusion list ("a general
AI strategy … is not causal") arguably does not exclude it, because this is not
a strategy statement but a stated reason for these specific cuts. Both readings
are honest readings of the same written words. So it stays yours. It is left out
of the JSON entirely, which scores it nowhere.

Answering it once settles a recurring shape — the "AI skills swap" layoff — and
one sentence in `#m-ai` would close it for good.

## The question worth more than the 34 rulings: whose statement counts?

`ai_explicit` has never been told, in one place, whether it means **"the employer
said AI"** or **"the source text explicitly says AI"**.

- The production prompt says "**this text** explicitly says" — no speaker at all.
- `alt_allowed_ai_causation()` puts "**the company or press**" on the *loose* side of
  `ai_linked` — so speaker cannot be what separates strict from broad, or the
  comment would not name both.
- But the methodology page draws a speaker line for the **reason tags** ("*AI or
  automation* means the employer names AI"; "*AI press-linked* means the press ties
  the cuts to AI without the employer saying it") and then says those tags are "a
  different measure from the AI headline tiles" — **without saying how they differ**.

These recommendations take the first two as governing: **speaker does not
discriminate; explicitness does.** That is a defensible reading, but it is
*derived across three files and stated in none*, and it is the single assumption
under the most rulings. Three rows turn on it directly — **107481 GoKwik**,
**107491 Snowflake**, **107375 GM** — and the class recurs monthly, because
press-attributed-without-company is the normal shape of an AI layoff story.

**Rule it once, in `#m-ai`, and this stops being a judgement call.**

**Either answer is one edit here.** If you rule *the employer must say it*: flip
`rec:107481` (GoKwik) and `rec:107491` (Snowflake) to `false`, and 107375 (GM)
stays out — it was press-only too. If you rule *the source text suffices*:
confirm those two as they stand, and GM still needs its own separate answer,
because its question survives yours. Either way it is two characters and the
class is settled.

The 13 rulings that disagree with a stored live value (below) **also wait on
this**, since it may change several of them. Nothing has been queued for
correction.

## A caveat on what was judged

The gold set judges the **stored snippet**, not the underlying article. For a few
rows the snippet is thinner than the source — **293 (Commonwealth Bank)** most
clearly, where the ABC piece does report the bank attributing the cuts to AI but
the stored text does not. Ruling `not AI` there is a correct reading of the text
in front of the labellers, and it is *not* a statement that the live row is
wrong. Both readings are defensible; a stored-text pass is the right way to fix
it, not an adjudication.

## Live rows this exercise says are worth a separate look

**Change nothing on the live site from this file, and nothing is queued.**
`/edit` sets `edited=1`, rewrites the dedup hash and publishes to the public
corrections log, so a wrong write there is expensive and public. Seven of the
thirteen below would flip a row **into** the AI count — the number this product
is named after. They wait for the speaker ruling first.

- **id 292 — Tata Consultancy Services, `ai_explicit=1`, `contributing_cause`.** Not one
  of the 34 (all three models agreed it is not AI). Its stored text is *"Tata
  Consultancy Services (TCS) laid off 12,000 jobs in July."* — no AI vocabulary at
  all — while the stored quote reads "The rise of AI and automation has accelerated
  this shift", which appears nowhere in that text. This is a **legacy keyword-era
  flag**, not a model decision, and it is exactly what `reclassify_legacy_ai.py`
  exists to clear. Its `review_status` is `verified`, so the legacy sweep will
  never reach it. Worth checking how many other `verified` rows carry an
  `ai_language` quote that is not present in their own `raw_text`.
- **Stored values these recommendations disagree with**, if confirmed — for a reviewed
  corrections pass, not a bulk write: `70681`, `60800`, `107469`, `107481`, `54968`,
  `49084`, `107491` (stored `false`, recommended AI) and `49090`, `26455`, `306`,
  `176954`, `70469`, `293` (stored `true`, recommended not AI).

---

## Provisional scores — what `--rescore` returns IF these stand

These were measured once, by hand, with the rulings temporarily un-parked, and
then the artifacts were reverted. **Nothing on disk can reproduce them
automatically** — that is deliberate. `goldset.json` carries `labels` for 175
rows and `parked_recommendations: 33`, and a `--rescore` today prints the 175-row
score, not this one. These numbers describe a gold set that does not exist until
you confirm it. No model was called; `$0.00` was spent.

Gold coverage would go from **175 rows (all by two models agreeing, 0 human)** to
**199 of 200** — 166 by agreement, 33 by adjudication, 1 (GM) still open.

| model | before: 175 model-agreed rows | after: 199 rows, 33 adjudicated |
|---|---|---|
| `deepseek/deepseek-chat` (incumbent, a labeller) | prec 100.0% · rec 100.0% | prec **79.9%** · rec **80.2%** |
| `openai/gpt-4.1-mini` (referee, a labeller) | prec 100.0% · rec 100.0% | prec **89.3%** · rec **79.5%** |
| `google/gemini-2.5-flash-lite` (**candidate, in production since 2026-08-07**) | prec 84.6% · rec 80.6% | prec **80.9%** · rec **72.6%** |

Both labellers' 100% was the inflation the harness warned about, and adjudication
removes most of it — which is the point of doing this at all.

**The fair head-to-head becomes available**, on the 33 adjudicated rows, the only
subset where no model's own vote helped write the answer:

| model | correct on the 33 |
|---|---|
| `openai/gpt-4.1-mini` (referee) | 21/33 = 63.6% (CI 46.6–77.8%) |
| `deepseek/deepseek-chat` (pre-swap incumbent) | 17/33 = 51.5% (CI 35.2–67.5%) |
| `google/gemini-2.5-flash-lite` (**current production**) | 15/33 = 45.5% (CI 29.8–62.0%) |

Read this carefully before drawing a conclusion about the swap. These 33 rows are
**the hardest 17% of the corpus by construction** — every one is a row where two
models disagreed or the candidate objected. Nobody scores well on them and nobody
was meant to. The candidate is lowest, the incumbent is 2 rows above it, and the
intervals overlap heavily: **that is not evidence the 2026-08-07 swap was wrong.**
The symmetric referee-agreement measure, which needs no adjudication, still has
them level (87.5% incumbent vs 88.0% candidate).

What the exercise *does* say, if confirmed: on the hard-negative stratum the
candidate runs precision 55.6% and recall 50.0%, below the incumbent's 66.7% /
60.0% — the "AI-adjacent but not AI-caused" story is where the swap is most
plausibly costing something, and it is where the tracker's headline number is
most exposed. That is a reason to widen the hard-negative stratum, not a reason to
revert a model on 9 rows.

The harness verdict stays **UNKNOWN pending adjudication** while GM is open, which
is correct.
