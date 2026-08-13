# What a UK reference event IS — written before any number was measured

This document was committed **before** any UK recall figure existed, on purpose.
The US set works because its definition is precise and was fixed before the
first tracker query: *employers filing SEC Form 8-K carrying structured item
code 2.05, in a stated window, counted on the filing date.* 52 of 57, 91.2%,
Wilson 95% CI [81.1%, 96.2%], adjudicated by the owner on 2026-08-12.

The United Kingdom is the tracker's second-largest market by jobs (about 1.82
million all time) and has never been measured. This is the definition it gets,
and the evidence for why it is not simply "the US definition with UK spelling".

---

## 1. The UK has no Item 2.05, and its nearest instrument is closed

The US Item 2.05 set is possible because a US public company is *required* to
disclose a workforce reduction to a regulator, on a form, with a structured item
code, into a **public, full-text-searchable index**. Every one of those four
properties has to hold. In the UK:

| Property | US (8-K Item 2.05) | UK |
|---|---|---|
| A mandatory notification of collective redundancy exists | yes | **yes — Form HR1** |
| It carries the employer's name and a headcount | yes | yes |
| It is published | yes | **no** |
| It is full-text searchable by anyone | yes (EDGAR FTS) | no |

Under s193 of the Trade Union and Labour Relations (Consolidation) Act 1992 an
employer proposing to dismiss 20 or more employees at one establishment must
notify the Secretary of State on **Form HR1**. That is the closest thing the UK
has to a WARN notice and, in scope, a closer analogue to Item 2.05 than anything
else in this document. **It is not published at employer level, and the evidence
says it will not be.**

What *is* published is a monthly aggregate — forms received, total potential
redundancies, unique employers — for Great Britain, on
[gov.uk](https://www.gov.uk/government/publications/publication-of-data-on-advanced-notification-of-redundancy-scheme).
No names, no rows.

**The refusal precedent is direct and systemic, not case-specific.**

- **FOI 142** (29 Dec 2020) — a request for HR1 forms received 23 Sep to 27 Nov
  2020 returned aggregate monthly figures only; the identifying detail was
  withheld under **FOIA s43(2)** (prejudice to commercial interests), reasoning
  about reputational damage to the employer and distress to affected employees.
- **FOI22/23-021** — a request merely for *the date* on which one named company
  submitted an HR1 was refused as a **neither-confirm-nor-deny** under **s31(3)**
  and **s43(3)**. The load-bearing sentence is general: *companies would be less
  likely to submit HR1 forms if they thought the process would not be
  confidential.* That argument applies with more force to a bulk employer-level
  request than to a single date.
- **Northern Ireland is not a loophole.** NISRA, which collects the NI HR1 for
  the Department for the Economy, states that no individual business can be
  identified from the statistics it produces.
- **Scotland is not a loophole.** The PACE collection on gov.scot is client
  surveys and evaluations, not a register, and names no employers. PACE is a
  support service rather than a statutory notification, so it would be a poor
  reference set even if it did.

**And HR1 would have a coverage hole even if it were published.** FOI21/22-181
(4 Apr 2022): the Insolvency Service *did not hold* an HR1 from P&O Ferries for
the 2022 redundancies — the most notorious UK mass redundancy of the decade. A
perfect HR1 feed would have missed it.

**Verdict: an HR1-based UK reference set is not possible without FOI, and the
precedent says an FOI would be refused.** What it would take is set out in §6.

---

## 2. What the tracker actually holds for the UK, and why the number below is
   not the interesting part

Measured live on 2026-08-13 against the public read API, window
2025-07-01..2026-06-30, `country_basis=any` (the basis the reader's own filter
uses):

    UK events held in the window     18
    UK jobs held in the window       48,318

Against the official HR1 aggregate for exactly the same twelve months, Great
Britain:

    HR1 forms received               4,724
    potential redundancies notified  319,488
    unique employers per month       221 to 412 (not summable across months)

So the tracker holds **18 UK events against 4,724 statutory notifications**, and
**48,318 jobs against 319,488 notified** — at most 15.1% of the notified jobs,
and that ceiling is generous because several of the 18 are global programmes
counted in full (HSBC 20,000; ANZ 3,500) rather than their UK share.

Over the reference set's actual window, **2024-07-01..2026-06-30**, the same two
sources give:

    tracker: UK events held        40
    tracker: UK jobs held          66,832
    HR1: forms received            9,044
    HR1: potential redundancies    606,470

which is **11.0% of the notified jobs and 0.4% of the notifications**, and again
the jobs figure is generous because several of the 40 are global programmes
counted in full.

This is a **coverage bound, not recall**. It has no per-event matching, no
adjudication and no confidence interval, and it compares two things that are not
the same unit: an HR1 is per establishment, ours is per event. It is in this
document because it is computed entirely from an official source with no
enumeration effort at all, it is independent of everything we do, and it bounds
the honest claim before any sampling argument starts.

The year-by-year UK row counts explain the shape:

    2018  149    2021    8    2024   18
    2019  146    2022    1    2025   22
    2020  247    2023   21    2026   15

UK coverage collapses after 2020. The pre-2021 volume is European Restructuring
Monitor data; Eurofound's ERM stopped covering the United Kingdom, and nothing
replaced it. Since then the UK is covered by the general worldwide news layer
only, at roughly twenty events a year.

---

## 3. The independence rule, restated, because it is what makes the number worth
   having

A reference set must be enumerated from a source **independent of our own
collection**: barred from our database, our repo, our registry and our site. A
commercial data service or a competitor listing may be used to work out *where*
to look and never to populate the set — if one source feeds both discovery and
the gold set, the measurement scores us against what we tuned ourselves to
match, and the number is worthless. No commercial service name appears anywhere
in this repo.

This rules out, for enumeration:

- **GDELT** and **Google News RSS** — our two live discovery channels.
- **Eurofound ERM** — a live collector.
- **The tracker's own API, database, permalinks, sources page and registry.**
- Any aggregator or vendor layoff list.

It does **not** rule out a corpus we also happen to read. The US set is
enumerated from EDGAR, which our own collector reads: the set is independent of
our *selection*, not of our *design*, and it says so. The same allowance applies
here and must be disclosed the same way.

---

## 4. The routes that were tested, and what each one actually returns

Every verdict below is from a live probe, not from an assumption.

| Route | Public? | Names employer | States a count | Enumerable by date + text | Verdict |
|---|---|---|---|---|---|
| HR1 (Insolvency Service) | aggregate only | no | aggregate | no | **out** — §1 |
| The Gazette (official public record) | yes, free API | yes | **no** | yes | **out** — no counts |
| Companies House filings | yes (free key) | yes | only inside PDFs | metadata only | see §5 |
| RNS via FCA National Storage Mechanism | yes (web UI) | yes | sometimes | yes, but see below | **out on robots** |
| London Stock Exchange news explorer | yes | yes | in body only | **no free-text body search** | **out** |
| UK Parliament (Hansard) | yes, open API | yes | rarely, and never as the citation | yes | **used as the frame — §5** |
| National press — BBC | — | — | — | — | **out on terms** |
| National press — Guardian | — | — | — | — | **out on robots** |

**The Gazette.** Probed 2026-08-13. The free Atom/JSON API supports date bounds
and free text and is permitted by robots.txt (crawl-delay 10). A full-text search
for "redundancies" across 2025-07-01..2025-07-31 returns **two** notices, both
matching on a *company name* containing the word ("CFS Redundancy Payments Ltd",
"The Redundancy Lady Ltd"). Statutory insolvency notices name the company and the
appointment but do not state how many people lost their jobs. The Gazette is a
perfectly good register of insolvency *events* and carries none of the quantity
this tracker records.

**London Stock Exchange.** `robots.txt` disallows `/en-gb/`. The News Explorer at
`/news?tab=news-explorer` loads and is permitted, but it filters by company,
index, sector and headline type — there is **no free-text search over
announcement bodies**. A UK redundancy announcement is almost never in the
headline as a number ("Trading Statement", "Strategic Update"), so headline
search cannot enumerate the population. There *is* a keyless headline search
(`/api/gw/lse/search/autocomplete`, HTTP 200, no key) and it proves the point:
`q=redundancy` returns zero news items, because RNS headlines say "Restructuring"
or "Cost Reduction Programme". The date-bounded view is **issuer-scoped by
design** — the SPA's own URL builder returns `"#"` unless an issuer code is
supplied — so LSE can answer "what did this company announce in this window"
and cannot answer "what did the market announce in this window" without
iterating every issuer.

**FCA National Storage Mechanism — the one that should have worked.** The NSM
is the FCA's appointed mechanism for *regulated information*, which the FCA
Handbook glossary defines to include disclosures under **MAR Article 17** —
public disclosure of inside information, i.e. exactly the restructuring and
trading announcements a UK Item-2.05 analogue would live in. **DTR 8.4.30R**
requires every primary information provider to supply all regulated information
it disseminates to the FCA, which is why the NSM is the only *complete* UK index
and why no single PIP's own archive can substitute for it. The FCA's own page
says NSM search covers company name, LEI, filing date and **keywords or phrases
in the document content**, with CSV export. On content scope it is the right
corpus and the only right corpus.

It is **out on access, and the reason is an explicit publisher instruction**.
`https://data.fca.org.uk/robots.txt` carries, alongside `User-agent: * / Allow:
/`:

    User-agent: ClaudeBot
    Disallow: /

with the same for Amazonbot, Bytespider, CCBot, GPTBot, Google-Extended and
meta-externalagent. A pipeline running as `AiLayoffTracker/1.0` would formally
fall under the wildcard. **Renaming the agent to evade a block aimed at the
agent is not a reading of robots.txt this project is willing to make**, so the
NSM was not enumerated and its search API was never probed. There is also no
documented public read API: every API reference in FCA material is for PIPs
*submitting*, not for anyone reading, and the front end is behind a terms-of-use
acceptance that a session may not click on the owner's behalf.

That is the whole ballgame for a UK Item-2.05 analogue. **The only complete
index of UK regulatory announcements exists, is free, is searchable by
document text, and asks agents like this one not to read it.**

**BBC.** `robots.txt` states, in its own words, no scraping or systematic
extraction, no dataset creation, no text and data mining, no retrieval-augmented
generation. Whatever the legal status of those lines, they are an explicit
publisher instruction and this project does not enumerate against them. The BBC
is also already one of our own collected domains.

**Guardian.** `robots.txt` carries `Disallow: /search`, so the search index —
the only thing that could enumerate a window — is off limits. The Guardian is
also already one of our own collected domains, and the Guardian Open Platform
API requires creating an account, which this session may not do.

The press position is worth stating plainly rather than burying: **the two UK
national outlets that could plausibly anchor a press-based enumeration both
forbid the enumeration, and both are sources we already read** — so a press set
built from them would have been weakly independent even if it had been
permitted.

---

## 5. The definition

**A UK reference event is: a UK employer named in the official report of the UK
Parliament in connection with redundancies, whose redundancy programme is
confirmed by an ORIGINAL PUBLISHER stating an absolute count of jobs, roles or
posts to be cut, announced in 2024-07-01..2026-06-30.**

### The window is twenty-four months, and why it is not twelve

It started as twelve, matching the US set exactly. The first verification pass
sent that choice back: of the first 34 candidates checked, **14 were dropped
solely because the announcement predated 2025-07-01** — Tata Port Talbot, British
Steel Scunthorpe, Petroineos Grangemouth, the University of Edinburgh, Lancaster
University, and others. **Parliament debates a redundancy programme months after
the employer announces it.** A frame that lags, sampled over a window as short as
the lag, throws away most of what it finds and leaves a denominator too small to
carry an interval.

So the window was widened to twenty-four months and **the earlier twelve months
were re-enumerated from scratch through the same two search terms**. That
distinction is the whole difference between a method correction and a
results-driven one: the extra events were not harvested from the drop pile of a
window that had already been sampled, which would have kept only the events
Parliament happened to discuss late. Every candidate in both years reaches the
set by the same route.

The cost is that **the UK window is no longer the US window**, so the two
figures describe overlapping but different periods and must not be differenced.

Counted on the **announcement date at the original publisher**, not on the date
an MP mentioned it and not on the effective date.

**This is a different event type from the US set, and it is a different KIND of
set.** The US set enumerates a *filing*: the reference document and the citation
are the same object, and completeness is provable from the regulator's own item
code. Here the reference document and the citation are **two different things**:
Parliament is the **frame** (what to look at) and the employer's own
announcement is the **citation** (what the number means). That is a weaker
construction than the US one and it is labelled as weaker rather than dressed up
to match.

Why this frame and not another: it is the only index found that is
**official, primary, free, keyless, date-bounded, full-text searchable, permitted
to read, and not a corpus this tracker collects from**. Every other route in §4
fails at least one of those.

**The inclusion rules are the US set's rules, verbatim in effect**, so the two
sets disagree about the country and agree about everything else:

- an **absolute** count of jobs/roles/posts — the same bar `extractor.py`'s
  `_count_in_text` and `_percent_only_mention` guards apply;
- a **percentage only**, a **retained headcount**, a **pre-cut total**, or a
  count that must be **derived** by arithmetic → excluded, and the exclusion is
  recorded with its reason, because including them would score a documented
  design decision as a miss;
- a **range** counts as its lower bound; **"up to N"** counts as N.

**Biases, stated before the number rather than after it.** The frame
over-represents what is politically salient — constituency employers,
universities, refineries, steel, shipyards, hospices, councils, the NHS — and
under-represents London finance, professional services, technology, and foreign
multinationals cutting UK white-collar roles. Recess months are thin: August
2025 returned zero contributions for the primary term. **The net direction of
that bias on the measured recall is not known and is not asserted**: political
salience means wider reporting, which should push recall up, while regional and
sectoral coverage often sits with local outlets outside the pipeline's
trusted-domain list, which should push it down. The curation step that decides
which capitalised span is an employer is human judgement; the full mechanical
candidate list is retained so it can be audited rather than trusted.

**Nothing in the set is adjudicated.** Every event ships `not_matched`, which is
the same state the US set was in on 2026-08-12 before the owner decided the 29.
The numerator counts only what an editor has confirmed, so the editor-confirmed
figure starts at zero by construction and the machine's proposals are reported
separately as an upper bound. On the US set the machine's loose rule scored 31
where the editor scored 24; there is no reason to expect it to be kinder here.

---

## 6. If the honest answer is "this needs FOI or paid data"

That is a legitimate result and it is recorded here rather than papered over
with a set that looks like the US one and is not.

**FOI route.** A request to the Insolvency Service Information Rights Team
(foi@insolvency.gov.uk), 20 working days statutory, for employer-level HR1 rows
in a closed window. Expected outcome on the precedent in §1: refused under
s43(2)/s43(3), possibly NCND under s31(3); then internal review; then an ICO
complaint and a decision notice, several months to a year. Two further
obstacles: **s12** cost limits on any bulk extract, and **s40(2)** where a small
employer's identity is personal data. A partial win — say, employers above a
size threshold — is the realistic best case and would still need a second FOI to
cover a second window.

**Paid route.** A commercial RNS full-text archive would solve the enumeration
problem in an afternoon and **must not be used to populate a reference set**, by
the rule in §3. It may legitimately be used to establish *where* to look. Its
name does not appear in this repo and will not.

**What that leaves.** Whatever is enumerated in §5, reported with its interval
and its biases, plus the coverage bound in §2 — which needs no permission from
anybody.
