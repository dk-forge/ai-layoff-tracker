# AI causation — recommended rulings, for confirmation

> ## RULED AND CONFIRMED IN FULL, 2026-08-19
>
> **All 34 open rows now carry a ruling. Nothing is parked. Gold coverage is
> 200 of 200.** The three questions this file raised are all answered, and the
> two that were rules rather than row calls are published where a reader can
> check them, on methodology `#m-ai`.
>
> **1. The speaker question: `ai_explicit` requires THE EMPLOYER to have
> attributed the cuts to AI.** A report counts when it quotes or reports the
> employer saying it. A journalist's own characterisation, with no such statement
> from the employer, is the BROAD tier (`ai_linked`), not this one. Ruled by the
> owner; written into `#m-ai`, `extractor.ai_causation_prompt()`, `SYSTEM_PROMPT`
> rule 2 and `alt_allowed_ai_causation()` at 2.20.102. The reason, on the record:
> the product already runs two tiers, a strict one that is the employer's own
> words with a quote on file and a broad one that also holds press framing.
> Ruling "the source text suffices" would collapse the two and delete the
> distinction the broad tier exists to carry.
>
> **2. The AI-skills-swap question: 107375 (General Motors) is `false`.** GM's own
> words do name AI, so the speaker ruling did not dispose of it. The test the owner
> accepted: **did the work go away, or did the required skill change?** If a system
> now does the work, that is an AI layoff. If the same work still needs doing by
> different people, that is restructuring. Written into `#m-ai` at 2.20.104.
>
> **3. The six speaker rows are CONFIRMED `false`** — `70293` Snap, `70653` TikTok,
> `54973` Microsoft/MSN, `48830` Suncor, `70683` ByteDance/TikTok, `70681` TikTok.
> The owner deferred this one ruling to a session on 2026-08-19, and what he
> authorised was narrow: **the mechanical application of his own speaker rule to six
> rows he had already seen, not a fresh judgement and not a new rule.** Each row's
> stored text was re-read against `#m-ai` before confirming rather than confirmed on
> the strength of the earlier summary. None carries an employer attribution:
>
> | id | company | who actually said AI, in the stored text |
> |---|---|---|
> | 70293 | Snap | "AI **push leads to** 1,000 job cuts" is the headline; the second sentence is the reporter's summary. No employer statement. |
> | 70653 | TikTok | "**It also claims that** TikTok is looking to replace the moderators…" — a third party's claim, not TikTok's. |
> | 54973 | Microsoft / MSN | "The layoffs are part of a bigger push **by Microsoft** to rely on AI" — The Verge's framing. "by Microsoft" says whose push, not who spoke. |
> | 48830 | Suncor | "Driverless technology is only just **starting to cause layoffs**" — the reporter's, and generic; the union is in the headline. The Suncor statement in the text announces a truck fleet. |
> | 70683 | ByteDance / TikTok | "cuts hundreds of jobs **in shift towards** AI content moderation" — a "sources say" headline. The company confirmed only the count. |
> | 70681 | TikTok | Press purpose clause. The company confirmed the layoffs, **not the reason**. |
>
> ### What `--rescore` returns now (200 gold labels, $0.00, no model called)
>
> | model | precision (pop-weighted) | recall (pop-weighted) |
> |---|---|---|
> | `deepseek/deepseek-chat` (incumbent, a labeller — INFLATED by construction) | 68.3% (CI 49.2–83.7%) | 88.1% (CI 68.8–96.2%) |
> | `openai/gpt-4.1-mini` (referee, a labeller — INFLATED by construction) | 75.2% (CI 54.0–89.2%) | 83.8% (CI 61.1–94.1%) |
> | `google/gemini-2.5-flash-lite` (**production**) | **69.5%** (CI 49.0–85.4%) | **78.1%** (CI 56.3–91.5%) |
>
> Fair head-to-head on the 34 adjudicated rows: referee 20/34 = 58.8% (CI 42.2–73.6%),
> incumbent 17/34 = 50.0% (CI 34.1–65.9%), candidate 16/34 = 47.1% (CI 31.5–63.3%).
> Symmetric referee agreement, which needs no adjudication and is the only comparison
> not rigged by who wrote the key: incumbent 175/200 = 87.5% (CI 82.2–91.4%),
> candidate 176/200 = 88.0% (CI 82.8–91.8%).
>
> **The six cost the production candidate ~9 points of precision, and that is the
> most interesting thing in this file.** They are exactly where it is weakest: gold
> is `false` on all six, and flash-lite called AI on four of them (70293, 48830,
> 70683, 70681) against three each for the incumbent and the referee. Press-framed
> AI attribution is the normal shape of an AI layoff story, so this stratum is not
> exotic. It is also six rows, and six rows settle nothing.
>
> **VERDICT ON THE 2026-08-07 SWAP: UNKNOWN — and now a SETTLED UNKNOWN, not a
> blocked one.** Every previous UNKNOWN here was procedural: rows carried no label.
> That reason is gone; adjudication is complete at 200 of 200. What remains is
> substantive. On the one unrigged measure the incumbent and the candidate are
> level (87.5% vs 88.0%, intervals almost identical); on the fair adjudicated
> subset they are one row apart with intervals overlapping heavily; the candidate
> trades recall for precision against the incumbent and every interval is wide.
> **The swap is neither vindicated nor condemned at n=200.** Do not read this as a
> pass, and do not move a production model on it. The harness prints UNKNOWN by
> construction and has no branch that prints anything else, because choosing a
> production model is the owner's call and not a score's.
>
> **Do not quote the projections below this banner.** This file once projected
> prec 80.9% / rec 72.6% for the candidate; the harness returns the table above.
> The file warned that nothing on disk could reproduce the projections, and it was
> right to. Quote the harness.
>
> ### The stored-value disagreement list: five were CORRECTED LIVE on 2026-08-19
>
> The corrections are applied, published to the public corrections log, and
> `edited=1` pins each row against re-import. Live effect: strict AI
> **203,858 → 201,869 jobs (−1,989)** over **96 → 91 entries**, with
> `ai_broad_jobs` unchanged at 232,573 — the jobs moved to the labeled broad tier
> rather than vanishing.
>
> - **Corrected out of the strict AI count** (`ai_explicit=0`, `ai_causation=ai_linked`):
>   `70653` TikTok 439, `54973` Microsoft 50, `48830` Suncor 400, `70683`
>   ByteDance/TikTok 500, `107375` General Motors 600.
> - **`70293` Snap was DELIBERATELY NOT corrected, and this is the one thing here
>   that still needs the owner.** Its gold label is `false` and correct: the gold set
>   judges the stored snippet, and that snippet has no employer attribution. But the
>   LIVE row's `ai_language` carries an **Evan Spiegel memo quote** — the CEO's own
>   words, "rapid advancements in artificial intelligence enable our teams to reduce
>   repetitive work, increase velocity…" — sourced to TechCrunch and appearing
>   nowhere in this row's own source text. So the speaker rule does **not**
>   mechanically condemn the live row: there IS an employer speaker. What the row
>   actually has is the **missing-receipt** defect (the same shape as row 292 TCS,
>   below), and the verbatim rule sends a quote-less causal label to `unknown`, not
>   to `false`. Correcting it would have been a judgement, not an application, so it
>   was left alone.
> - **Still unqueued, still for a separate reviewed pass** — into the AI count
>   (stored `false`, ruled AI): `60800`, `107469`, `54968`, `49084`; out of it
>   (stored `true`, ruled not AI): `49090`, `26455`, `306`, `176954`, `70469`, `293`.
>   `70681`, `107481`, `107491` are ruled `false` and stored `false`, so there is
>   nothing to correct on them.
>
> **Corroboration the speaker ruling is the right one:** production already stores
> 107481, 107491 and 107469 as `ai_linked`. The live classifier was applying the
> rule before anybody wrote it down.
---

> **EVERYTHING BELOW THIS LINE IS THE ORIGINAL RECOMMENDATION PASS, KEPT AS A
> RECORD OF WHAT WAS PROPOSED AND WHY.** It is superseded by the banner above:
> every row is now ruled, nothing is parked, and the mechanics it describes
> ("coverage stays 175 of 200", "strip the prefix to confirm") have already been
> carried out. Read it for a row's deciding phrase and the rubric reason. Do not
> read its status lines, its counts, or its provisional score tables as current.

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
| **107375** | **General Motors** | "GM just laid off hundreds of IT workers **to hire those with stronger AI skills**" | **not AI** (RULED) | The work did not go away, the required skill changed. Restructuring, not an AI layoff. Ruled by the owner 2026-08-19; see below. |

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

## RULED 2026-08-19: 107375, General Motors, is `false`

The section below is kept as written, because it states the question fairly and the
ruling is only readable against it. **The answer: the required skill changed, the work
did not go away, so this is restructuring and not an AI layoff.** That test now lives on
the methodology page in `#m-ai`, beside the speaker rule.

### The question, as it stood

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
