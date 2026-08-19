#!/usr/bin/env python3
"""PER-COUNTRY COVERAGE — what exists to be found, per country, and who says so.

READ `railway/rolling_recall.py` FIRST. This is an extension of it, not a second
framework, and it borrows that module's whole vocabulary on purpose: MEASURED /
NOT_MEASURABLE / UNKNOWN at slice level, an assessment that carries a DATE and
EXPIRES, and the rule that a declared thing which cannot be computed says so
rather than dropping out of an average.

WHAT WAS WRONG
--------------
`rolling_recall` measures exactly one slice exactly: US SEC 8-K Item 2.05, where
EDGAR's structured item array enumerates the universe for a period and the
denominator is therefore not a sample. Every other country in the corpus — 72 of
them as this is written — was unmeasured, and unmeasured is not the same as
uncovered. "We cover country X" was an opinion, and the owner's stated goal is
worldwide coverage he can DEFEND per country.

THE HARD PART IS THE DENOMINATOR, AND FOR MOST COUNTRIES IT DOES NOT EXIST
--------------------------------------------------------------------------
Recall needs a count of what SHOULD exist. The reflex is to go looking for one
per country and treat a failure to find it as our gap. That reflex is wrong, and
correcting it is most of the value here. There are three genuinely different
situations and only the first is a recall problem:

  REGIME_WITH_AGGREGATE   A statutory disclosure regime exists AND a public
                          authority publishes a periodic COUNT derived from it.
                          Recall is then measurable exactly, like Item 2.05.
                          Best case and, it turns out, the rare one.

  REGIME_NO_AGGREGATE     A regime exists — an employer must notify an authority
                          before a collective dismissal — but nothing countable
                          is published. US state WARN is the type specimen: the
                          notices are public one row at a time, and there is no
                          national total anywhere because US DOL keeps no
                          database and BLS Mass Layoff Statistics ended in 2013.
                          Sampling may be possible; this register says what it
                          would cost, and does not pretend the cost is zero.

  NO_REGIME               No statutory mass-dismissal disclosure regime exists.
                          Then there is NOTHING TO BE COMPLETE AGAINST, and that
                          is a fact about the country rather than a failure of
                          ours. This is the most important category to get right
                          and the easiest to get wrong by silence, because a
                          country with no regime and a country we never checked
                          look identical on any dashboard that only counts what
                          it found.

  REFUSED                 A denominator — or the ability to establish whether
                          one exists — sits behind a block aimed at AI agents, a
                          paywall, a bot wall or a CAPTCHA. It is RECORDED AS
                          REFUSED WITH ITS REASON AND ITS HOST, and it stays
                          refused. This project does not rename an agent to get
                          around a block aimed at the agent — the reading that
                          kept Wisconsin out of the WARN slice and the FCA
                          National Storage Mechanism out of the UK set. A
                          refusal is a known, named loss, which is worth far
                          more than an unexplained gap.

                          Two shades live here and the reason field must say
                          which: the publisher demonstrably HAS the figure and
                          blocks us (France, the Philippines), or the block sits
                          upstream of even finding out (Cyprus). Both are
                          terminal rather than outstanding work, which is why
                          neither is UNASSESSED — but they are not the same
                          claim and the register must not blur them.

  UNASSESSED              Nobody has looked. UNKNOWN, never a pass, and it makes
                          the whole report UNKNOWN — see `judge`.

THERE ARE TWO QUESTIONS HERE AND THEY ARE NOT THE SAME ONE
-----------------------------------------------------------
Everything above answers "does a countable TOTAL exist", which is what makes
coverage MEASURABLE. There is a second and better question — "does a public
REGISTER exist that NAMES the employer" — which is what makes layoffs
FINDABLE, and it is the one the tracker is actually for. Conflating them is
the error to avoid: Spain publishes an excellent monthly total AND, in exactly
one of its 17 autonomous communities, a file with the company name in it, and
those are two different facts about Spain.

The second question lives in PER_EMPLOYER_REGISTERS, kept apart from the
coverage classification on purpose. As of 2026-08-19 the answer is FOUR
jurisdictions on earth: US states, Quebec, Poland's Mazowieckie voivodeship,
and the Illes Balears. Every one of them is SUB-NATIONAL except the US, which
is itself fifty separate registers. That is the shape of the finding: naming is
devolved almost everywhere it happens, so a national "no" is not an answer in a
country that devolves labour administration, and the register must say which of
the two questions any given "no" answers.

NAMING THE REGIME IS THE POINT
------------------------------
Every classification here carries the statute, the article, the authority that
receives the notification, the threshold that triggers it, and a citation. That
is what makes the claim checkable by somebody who disagrees with it. "Country X
has no layoff disclosure requirement" is a publishable, falsifiable sentence;
"we could not find data for country X" is an admission dressed as a finding.

THE CLAIM THIS SUPPORTS, AND THE ONE IT FORBIDS
------------------------------------------------
100% of all countries is not achievable and claiming it is the single thing that
could damage this product. What this register supports is:

    "100% of what is publicly disclosed, per country, with the disclosure
     regime named."

It deliberately does NOT compute a worldwide percentage. Averaging a measured
country against an unmeasurable one produces a number whose denominator is the
register's own coverage rather than the world's, and that number would be
quoted. There is no such field in the output, on purpose.

INSIDE THE EU, "NO REGIME" IS ESSENTIALLY IMPOSSIBLE — AND THAT IS NOT THE WIN
IT SOUNDS LIKE
------------------------------------------------------------------------------
Directive 98/59/EC Art. 3(1) is unconditional: "Employers shall notify the
competent public authority in writing of any projected collective redundancies."
Every EU/EEA member state has transposed it, so for roughly half this corpus the
regime question is answered before it is asked, and NO_REGIME is not an
available answer inside the bloc.

What that does NOT give is a comparable denominator, for three reasons written
into the Directive itself, and every one of them was checked against EUR-Lex
rather than remembered:

  * Art. 1(1)(a) lets each state choose between two threshold definitions —
    banded counts over 30 days, or 20 dismissals over 90 days. Two member states
    can therefore count genuinely different populations and both be compliant,
    so notification totals are NOT comparable country to country and must never
    be summed into a European figure.
  * Art. 1(2) excludes public-sector employees and fixed-term contracts
    outright. That is a permanent, structural hole in ANY notification-derived
    denominator, not a data-quality problem that better collection would close.
    NOTE the crews of seagoing vessels were ALSO excluded until Directive (EU)
    2015/1794 art. 4(1) deleted Art. 1(2)(c) — this module said otherwise for
    part of a day, on nothing but recollection, and the correction came from
    reading 32015L1794 on EUR-Lex, which states the deletion in as many words.
    The Commission's own summary page was reported still stale on the point, so
    a secondary source would have confirmed the error rather than caught it.
  * Art. 3(1) second subparagraph lets a state require notification of
    court-ordered closures only on request, and Art. 5 lets a state set a lower
    floor than the Directive's.

So the useful question in the EU is never "is there a regime" — it is "does the
receiving authority publish a count", and the answer to THAT varies enormously
between neighbours with near-identical statutes.

A PUBLISHED NATIONAL TOTAL IS NOT THE SAME DENOMINATOR AS ITEM 2.05
--------------------------------------------------------------------
This is the trap in the whole exercise and it is worth more than any entry in
the register. `rolling_recall` matches EVENTS: EDGAR enumerates a closed set of
filings and each one is found or not found in the tracker, so the ratio is
recall. What a labour ministry publishes is almost never a set of events — it is
a periodic COUNT OF AFFECTED WORKERS, or a count of procedures with no
identities attached. Dividing our stored job total for that country by that
figure produces a ratio, and that ratio IS NOT RECALL. Two reasons, both fatal
if the label is wrong:

  * The official total counts every notified collective dismissal, including the
    thirty-person cut at a regional employer no outlet will ever write about.
    A news-and-filings tracker cannot hold those and is not trying to. A low
    ratio against a national total is the expected, correct result, not a gap.
  * The periods rarely line up. A notification count is dated when the notice
    was filed; our rows carry an announcement date and an effective date that
    can be a year apart, and `country_basis` unions job-location with employer
    HQ for the table while headline stats stay strict job-location.

So a country that publishes a total is recorded here with
`denominator_basis: national_notification_aggregate` and the honest name for
what it would yield is SHARE OF THE OFFICIAL TOTAL, never "recall". The only
denominator in this project that supports the word recall is one that enumerates
identifiable events, which so far is Item 2.05 and nothing else. Do not compute
a share and print it next to the Item 2.05 band — `rolling_recall` already
refuses to ship a sampled number beside an exact one and this is the same
refusal wearing a different unit.

SCOPE IS TAKEN FROM THE LIVE DATA, NOT FROM THIS FILE
------------------------------------------------------
The countries in scope are the countries the tracker actually holds rows for,
read from /aggregate at run time. A country that appears in the corpus and not
in this register makes the report UNKNOWN and names itself. That is the same
rule as `rolling_recall`'s declared slices, pointed at a set that grows on its
own: a new country arriving in the data is a new classification owed, and it
cannot be missed by nobody happening to notice it.

NO NUMBER IS PUBLISHED TO ANY READER-FACING SURFACE by this module, and none
should be added to one by a cron. What to claim in public is the owner's
decision, made on purpose.

COST: $0.00. One public read of the tracker's own /aggregate. No model is called
on any path and none should ever be added — a measurement that spends money is a
measurement that gets switched off in a lean month.

USAGE
    python3 railway/country_coverage.py              # classify, print, 0/2/3
    python3 railway/country_coverage.py --write      # ...and commit the result
    python3 railway/country_coverage.py --regimes    # print the register alone,
                                                     # no network, for review

Env: WP_SITE_URL.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recall_goldset import PASS, FAIL, UNKNOWN                      # noqa: E402,F401
from rolling_recall import MEASURED, NOT_MEASURABLE                 # noqa: E402

HERE = Path(__file__).resolve().parent

# Committed for the reason rolling_recall_measurement.json is: the thing being
# described changes without a commit (a new country enters the corpus; a
# ministry starts publishing), so a result that lives only in a runner resets
# every night and its age can never be read.
MEASUREMENT_PATH = HERE / "country_coverage_measurement.json"

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
SITE = (os.environ.get("WP_SITE_URL") or "https://asktherecruiter.com/blog").rstrip("/")

# ---------------------------------------------------------------------------
# THE FIVE CLASSIFICATIONS. See the module docstring for why there are five and
# not two.
# ---------------------------------------------------------------------------
REGIME_WITH_AGGREGATE = "regime_with_aggregate"
REGIME_NO_AGGREGATE = "regime_no_aggregate"
NO_REGIME = "no_regime"
REFUSED = "refused"
UNASSESSED = "unassessed"

CLASSIFICATIONS = (REGIME_WITH_AGGREGATE, REGIME_NO_AGGREGATE, NO_REGIME,
                   REFUSED, UNASSESSED)

# A classification maps to one of rolling_recall's slice states. The mapping is
# explicit rather than implied, because the interesting cases are the two that
# both mean "no figure" for opposite reasons: NO_REGIME is NOT MEASURABLE and
# will stay that way for as long as the country's law does not change, whereas
# UNASSESSED is UNKNOWN and is somebody's outstanding work.
STATE_OF = {
    REGIME_WITH_AGGREGATE: MEASURED,      # measurable — see `measurable` below
    REGIME_NO_AGGREGATE: NOT_MEASURABLE,
    NO_REGIME: NOT_MEASURABLE,
    REFUSED: NOT_MEASURABLE,
    UNASSESSED: UNKNOWN,
}

# Re-check twice a year, the same ceiling and the same reasoning as
# rolling_recall.WARN_ASSESSMENT_MAX_AGE_DAYS: parliaments amend statutes and
# ministries start and stop publishing series, so a standing classification
# nobody revisits is a stale claim wearing a permanent exemption. Past this age
# an entry reports UNKNOWN and a human has to look again.
MAX_ASSESSMENT_AGE_DAYS = 183

# The register is refreshed by country-coverage.yml. Ceiling matches the real
# cadence — a 2-day ceiling on a weekly job is permanent noise that hides real
# breakage.
MAX_MEASUREMENT_AGE_DAYS = 9


# ---------------------------------------------------------------------------
# THE REGISTER
# ---------------------------------------------------------------------------
# One entry per country the tracker holds rows for. Every entry MUST carry:
#
#   class       one of CLASSIFICATIONS
#   regime      the statute and article, verbatim enough to look up, or the
#               explicit finding that there is none. NEVER a vague phrase — the
#               whole defensibility of this register is that a reader who
#               disagrees can go and check the citation.
#   authority   who receives the notification (None where there is no regime)
#   threshold   what triggers the duty (None where there is no regime)
#   aggregate   for REGIME_WITH_AGGREGATE / REFUSED: what is published and where.
#               for the others: why nothing countable is published.
#   assessed    YYYY-MM-DD. Expires after MAX_ASSESSMENT_AGE_DAYS.
#   cite        a URL a human can open.
#
# HOW TO ADD ONE: read RUNBOOK "classify a country's disclosure regime". Do not
# add an entry from memory of how a country's labour law works. Every entry
# below was checked against the publishing body's own page on its assessed date,
# and the ones that could not be checked say UNASSESSED rather than guessing —
# a plausible wrong statute is worse here than a blank, because it is the kind
# of error that survives review by looking like work.

# ---------------------------------------------------------------------------
# THE REFUSAL LEDGER — hosts that refuse us, so nobody re-probes or re-builds
# ---------------------------------------------------------------------------
# WHY THIS IS A DATA STRUCTURE AND NOT A PARAGRAPH. A refusal discovered and
# then written up in prose gets rediscovered. Somebody a month from now sees a
# gap in the register, goes looking for the obvious source, and spends an
# afternoon arriving at the same 403 — or worse, does not notice it IS a
# refusal, retries with a different agent string, and quietly turns a respected
# block into a defeated one. Both failures are prevented by the same thing:
# writing the refusal down where the next collector-builder will hit it.
#
# THE RULE THIS SERVES, stated once so it cannot be softened: read robots.txt
# BEFORE the first content request on any new host. Two of the research passes
# behind this register fetched a page first and read the directive afterwards;
# they stopped when they saw it, which is right, but the request had already
# gone. Order matters, and it is cheap to get right.
#
# WHAT IS AND IS NOT A REFUSAL. A named `Disallow: /` for ClaudeBot is the clear
# case. So is a blanket `User-agent: * / Disallow: /`. So is a server that
# returns 403 to an identifying agent string while serving a browser one —
# presenting a browser UA there would be spoofing to defeat an access control
# aimed precisely at us, which this project does not do. A JavaScript
# proof-of-work or CAPTCHA interstitial is not a robots directive but it is
# equally not ours to solve.
#
# `alternative` names a host that serves the same or adjacent material and does
# NOT refuse us. It is the useful half of the ledger: a refusal with a permitted
# alternative is a detour, and only a refusal without one is a loss.
#
# NOT EVERY ENTRY BELOW WAS VERIFIED BY THIS MODULE'S AUTHOR. Those marked
# `verified_here` were re-fetched directly; the rest come from the research
# passes and are recorded as reported. The distinction is kept because this
# ledger will be used to decide not to try something, and "somebody said it was
# blocked" is a weaker basis for that than "I read the file".
REFUSAL_LEDGER = (
    # --- verified directly by this module's author
    {"host": "dares.travail-emploi.gouv.fr", "country": "France",
     "nature": "F5/TSPD JavaScript bot defence serves a CAPTCHA instead of content; "
               "robots.txt itself is unreadable",
     "alternative": "none — data.gouv.fr carries no PSE dataset and the POEM portal 500s",
     "verified_here": False},
    {"host": "www.cliclavoro.gov.it", "country": "Italy",
     "nature": "robots.txt: 'User-agent: ClaudeBot / Disallow: /' (also CCBot, GPTBot, "
               "Google-Extended, Amazonbot, Applebot-Extended, Bytespider, "
               "meta-externalagent). Its Content-Signal line sits under 'User-agent: *' "
               "and is OVERRIDDEN by our own named group — an earlier reading of this "
               "same file wrongly concluded crawling was permitted",
     "alternative": "www.normattiva.it for the statute (Allow: /); no data alternative",
     "verified_here": True},
    {"host": "psa.gov.ph, psada.psa.gov.ph", "country": "Philippines",
     "nature": "robots.txt names ClaudeBot with 'Disallow: /'; www.dole.gov.ph returns "
               "403 on robots.txt itself",
     "alternative": "none — this is the best-shaped regime found anywhere and it is lost",
     "verified_here": True},
    {"host": "www.gov.ie", "country": "Ireland",
     "nature": "reported as robots.txt '# Anthropic AI / User-agent: ClaudeBot / "
               "Disallow: /' (also GPTBot, Google-Extended, Amazonbot, Applebot). What "
               "was verified HERE is stronger and simpler: the host returns HTTP 403 to "
               "our identifying user agent on /robots.txt itself, so the directive "
               "cannot even be read. Either way it is a refusal. "
               "www.oireachtas.ie serves a human-verification interstitial",
     "alternative": "enterprise.gov.ie is open but did not carry the series",
     "verified_here": True},
    {"host": "www.mlsi.gov.cy", "country": "Cyprus",
     "nature": "blanket 'Disallow: /' with Googlebot exempted — a block aimed at "
               "everything that is not a search engine",
     "alternative": "none found", "verified_here": False},
    {"host": "uzt.lt", "country": "Lithuania",
     "nature": "Cloudflare wall returns 403 to everything including its own robots.txt, "
               "so no crawl directive can even be read",
     "alternative": "none found", "verified_here": False},
    {"host": "psz.praca.gov.pl", "country": "Poland",
     "nature": "robots.txt names ClaudeBot specifically and disallows everything; it is "
               "the only agent named",
     "alternative": "stat.gov.pl (fully open) and the regional *.praca.gov.pl "
                    "subdomains, which carry no ClaudeBot rule",
     "verified_here": True},
    {"host": "www.austlii.edu.au, classic.austlii.edu.au", "country": "Australia",
     "nature": "robots.txt names ClaudeBot, GPTBot, CCBot, Google-Extended and others "
               "with 'Disallow: /'",
     "alternative": "legislation.gov.au (crawl-delay 10)", "verified_here": False},
    {"host": "law.moj.gov.tw", "country": "Taiwan",
     "nature": "blanket 'User-agent: * / Disallow: /'",
     "alternative": "laws.mol.gov.tw", "verified_here": False},
    {"host": "www.elegislation.gov.hk", "country": "Hong Kong",
     "nature": "'Disallow: /' for everyone, 'Allow: /' for Googlebot only",
     "alternative": "none found", "verified_here": False},
    {"host": "www.data.gov.in", "country": "India",
     "nature": "blanket 'User-agent: * / Disallow: /'",
     "alternative": "labourbureau.gov.in", "verified_here": False},
    {"host": "data.gov.au", "country": "Australia",
     "nature": "blanket 'User-agent: * / Disallow: /'",
     "alternative": "legislation.gov.au", "verified_here": False},
    {"host": "*.gov.in and *.nic.in (labour.gov.in, indiacode.nic.in, "
             "legislative.gov.in, pib.gov.in)", "country": "India",
     "nature": "an Akamai configuration returns 403 to an identifying AI-agent user "
               "agent while reportedly serving a browser one. VERIFIED HERE only in the "
               "half that can be verified without misbehaving: labour.gov.in and "
               "www.data.gov.in both answer 403 to our own agent string while "
               "labourbureau.gov.in answers 200. The browser-UA half was NOT tested and "
               "must not be — presenting a browser UA there is spoofing to defeat an "
               "access control aimed at us, the same reading that keeps Wisconsin "
               "refused. The 403 alone is sufficient to record the refusal",
     "alternative": "labourbureau.gov.in, which answered 200 to our agent",
     "verified_here": True},
    {"host": "az.government.bg", "country": "Bulgaria",
     "nature": "robots disallows /web/, which is exactly where the bulletin PDFs live; "
               "the HTML index is crawlable and the data files are not",
     "alternative": "none found", "verified_here": False},
    {"host": "nisra.gov.uk", "country": "United Kingdom (Northern Ireland)",
     "nature": "robots disallows *.xlsx",
     "alternative": "the datavis.nisra.gov.uk HTML report, reported to carry the same "
                    "figures", "verified_here": False},
    {"host": "iambweb.ams.or.at", "country": "Austria",
     "nature": "robots.txt blanket disallow on the AMS statistics host, so the "
               "publication question for Austria could not be closed from outside",
     "alternative": "none found", "verified_here": False},
    {"host": "nso.gov.mt, dier.gov.mt", "country": "Malta",
     "nature": "Cloudflare interstitial in front of both the statistics office and "
               "the labour relations department, so neither could be queried",
     "alternative": "none found", "verified_here": False},
    {"host": "pxweb.stat.si", "country": "Slovenia",
     "nature": "robots.txt names ClaudeBot on the statistical office's PxWeb "
               "database, so SURS could not be queried for a collective-dismissal table",
     "alternative": "none found", "verified_here": False},
    {"host": "ypergasias.gov.gr", "country": "Greece",
     "nature": "the labour ministry host blocks AI agents, so whether ERGANI breaks "
               "out collective dismissals could only be answered from secondary material",
     "alternative": "none found", "verified_here": False},
    {"host": "www.uwv.nl/nl/webpublicaties", "country": "Netherlands",
     "nature": "the ONLY path UWV's robots.txt disallows — and the likely home of any "
               "WMCO collective-dismissal series. Not aimed at AI agents specifically, "
               "but it applies to us",
     "alternative": "www.cbs.nl is clean; the UWV dashboard itself is JS-only",
     "verified_here": False},
    {"host": "www.leforem.be", "country": "Belgium",
     "nature": "robots.txt: 'User-agent: GPTBot / Disallow:/' and "
               "'User-agent: ClaudeBot / Disallow:/'",
     "alternative": "emploi.belgique.be, which is the actual publisher and has no "
                    "robots.txt at all", "verified_here": False},
    {"host": "statbel.fgov.be", "country": "Belgium",
     "nature": "F5/TSPD bot wall instead of a robots file",
     "alternative": "emploi.belgique.be", "verified_here": False},
    # --- bot walls: not robots directives, and equally not ours to solve
    {"host": "cao.minszw.nl", "country": "Netherlands",
     "nature": "Anubis proof-of-work interstitial", "alternative": "none found",
     "verified_here": False},
    {"host": "www.eurofound.europa.eu", "country": "EU-wide",
     "nature": "Vercel checkpoint interstitial",
     "alternative": "apps.eurofound.europa.eu, a separate host that serves normally",
     "verified_here": False},
    {"host": "whatdotheyknow.com", "country": "United Kingdom",
     "nature": "bot wall interstitial. Relevant because UK HR1 notification counts "
               "have historically surfaced through FOI requests archived there",
     "alternative": "none found", "verified_here": False},
    {"host": "cnesst.gouv.qc.ca", "country": "Canada (Quebec)",
     "nature": "bot wall interstitial on the Quebec labour standards commission",
     "alternative": "none found", "verified_here": False},
    {"host": "sso.agc.gov.sg", "country": "Singapore",
     "nature": "bot wall on Singapore Statutes Online, so the Employment Act "
               "retrenchment-notification text could not be read from primary source",
     "alternative": "none found", "verified_here": False},
    {"host": "mohrss.gov.cn", "country": "China",
     "nature": "bot wall on the human resources and social security ministry, the "
               "body that would receive Labour Contract Law art. 41 reports",
     "alternative": "none found", "verified_here": False},
    {"host": "natlex.ilo.org", "country": "international",
     "nature": "bot wall on the ILO's national labour law database — the single most "
               "useful cross-country source for exactly this register, and unusable",
     "alternative": "none found", "verified_here": False},
    {"host": "legifrance.gouv.fr", "country": "France",
     "nature": "Cloudflare managed challenge, 403 on robots.txt",
     "alternative": "none found", "verified_here": False},
    # --- added on the second sweep
    {"host": "saflii.org", "country": "South Africa",
     "nature": "robots.txt names ClaudeBot, CCBot, GPTBot and Google-Extended with "
               "'Disallow: /'. ccma.org.za, which publishes the s.189A figures, is "
               "WAF-403 and refuses its own robots.txt",
     "alternative": "none found — this is why South Africa stays unclassified",
     "verified_here": False},
    {"host": "nevo.co.il", "country": "Israel",
     "nature": "bans GPTBot, Google-Extended, Perplexity and '*' outright. "
               "taasuka.gov.il, the receiving authority, returns 403 to all automated "
               "clients",
     "alternative": "btl.gov.il serves the Employment Service Law text",
     "verified_here": False},
    {"host": "www.legislation.govt.nz", "country": "New Zealand",
     "nature": "AWS WAF bot challenge on every request, not bypassed. This is why "
               "New Zealand's apparent 'no regime' is NOT recorded as one — the "
               "Employment Relations Act 2000 was never read",
     "alternative": "employment.govt.nz guidance is permitted (Crawl-delay 5) but is "
                    "guidance, not statute", "verified_here": False},
    {"host": "www.mbie.govt.nz", "country": "New Zealand",
     "nature": "Incapsula interstitial, noindex/nofollow",
     "alternative": "www.employment.govt.nz", "verified_here": False},
    {"host": "www.servicesaustralia.gov.au", "country": "Australia",
     "nature": "connection reset on every request — the authority that receives Fair "
               "Work Act s.530 notices, so its silence cannot be distinguished from "
               "its unreachability",
     "alternative": "none found", "verified_here": False},
    {"host": "gov.im, legislation.gov.im", "country": "Isle of Man",
     "nature": "WAF 'Request Rejected' page to automated fetching across every "
               "government host, so no Manx statute could be read",
     "alternative": "none found", "verified_here": False},
    {"host": "www2.congreso.gob.pe", "country": "Peru",
     "nature": "blanket 'Disallow: /'",
     "alternative": "gob.pe for MTPE material", "verified_here": False},
    {"host": "knbs.or.ke, kenyalaw.org", "country": "Kenya",
     "nature": "knbs.or.ke serves a JavaScript bot challenge and has an expired TLS "
               "certificate; kenyalaw.org returns 403",
     "alternative": "labour.go.ke", "verified_here": False},
    # --- NOT robots refusals: environment or design blocks, recorded so nobody
    # mistakes them for a publisher saying no. These are worth RETRYING from a
    # different network, which a genuine refusal never is.
    {"host": "statdb.mol.gov.tw", "country": "Taiwan",
     "nature": "NOT A REFUSAL — no robots.txt, but /html/mon/ returns 403 and the "
               "statistics query application times out. An environment or WAF block, "
               "so Taiwan's dataset question is unanswered rather than answered "
               "negatively, and is worth retrying from another network",
     "alternative": "www.mol.gov.tw serves the publication TOCs and the statute "
                    "guidance and is permitted", "verified_here": False},
    {"host": "data.gov.tw", "country": "Taiwan",
     "nature": "NOT A REFUSAL — fully client-rendered with no server-side content, and "
               "the REST API requires an Authorization key. This is exactly where the "
               "reported real/decoy dataset pair would live and it could not be "
               "enumerated",
     "alternative": "none without a key", "verified_here": False},
    # --- added 2026-08-19, closing the backlog. The first four were read by
    # this pass directly; the rest are as reported by the sweeps that hit them.
    {"host": "www.althingi.is", "country": "Iceland",
     "nature": "robots.txt names ClaudeBot with 'Disallow: /' (also Amazonbot, "
               "Applebot-Extended, Bytespider, CCBot, CloudflareBrowserRenderingCrawler, "
               "Google-Extended, GPTBot, meta-externalagent). The parliament publishes "
               "the consolidated text of log nr. 63/2000 um hopuppsagnir, so Iceland's "
               "statute cannot be read from primary source by us",
     "alternative": "island.is, which serves Vinnumalastofnun's own pages and its monthly "
                    "hopuppsagnir posts and has no robots.txt at all",
     "verified_here": True},
    {"host": "wetten.overheid.nl", "country": "Netherlands",
     "nature": "robots.txt carries an explicit 'AI / LLM crawlers' section naming "
               "ClaudeBot, Claude-Web and anthropic-ai with 'Disallow: /', alongside "
               "GPTBot, PerplexityBot and dozens more. The WMCO text lives here",
     "alternative": "www.uwv.nl, the receiving authority, whose robots.txt disallows only "
                    "/nl/webpublicaties — its /nl/ontslag and /nl/persberichten paths "
                    "carry both the duty and the annual figure",
     "verified_here": True},
    {"host": "codulmuncii.ro", "country": "Romania",
     "nature": "robots.txt names ClaudeBot with 'Disallow: /' (also Amazonbot, "
               "Applebot-Extended, Bytespider, CCBot, "
               "CloudflareBrowserRenderingCrawler, Google-Extended, GPTBot, "
               "meta-externalagent), so Codul muncii art. 68 could not be read here",
     "alternative": "none for the statute; www.anofm.ro is fully open and carries the "
                    "data", "verified_here": True},
    {"host": "lege5.ro", "country": "Romania",
     "nature": "robots.txt ends with 'User-agent: * / Disallow: /', excepting only "
               "Googlebot, Mediapartners-Google and the Semrush crawlers. A block on "
               "everything that is not a search engine",
     "alternative": "none found", "verified_here": True},
    {"host": "heol.hu", "country": "Hungary",
     "nature": "HTTP 403 to our identifying agent. It carries county-level "
               "collective-redundancy counts that appear nowhere in the national "
               "statistics catalogue, so this is a real loss rather than a duplicate",
     "alternative": "the 20 varmegye kormanyhivatal sites, untried",
     "verified_here": False},
    {"host": "www.nzlii.org", "country": "New Zealand",
     "nature": "robots.txt names ClaudeBot with 'Disallow: /'. With legislation.govt.nz "
               "behind an AWS WAF, this was the last permitted route to the Employment "
               "Relations Act 2000 and it is closed",
     "alternative": "www.employment.govt.nz (Crawl-delay 5) — guidance, not statute",
     "verified_here": False},
    {"host": "www.oecd.org, eplex.ilo.org, webapps.ilo.org/dyn/eplex", "country": "international",
     "nature": "the two comparative databases that answer 'does this country require "
               "notification of a public authority' for the whole world, and both are "
               "shut to us: oecd.org robots excludes /content/dam/ where the EPL country "
               "notes live, the EPL dataset page returns HTTP 403, and both ILO EPLex "
               "hosts return 403 despite robots permitting them. This is why New Zealand "
               "and the Isle of Man could not be closed — the single cheapest source for "
               "a NO_REGIME finding anywhere is unavailable",
     "alternative": "none found", "verified_here": False},
    # --- NOT refusals: environment or design blocks, recorded so nobody mistakes
    # them for a publisher saying no. Worth RETRYING from a different network.
    {"host": "legislatie.just.ro", "country": "Romania",
     "nature": "NOT A REFUSAL — the socket hangs up on every request, robots.txt "
               "included, so no directive could even be read. Romania's official "
               "legislative portal, and the only permitted-looking route to Codul muncii "
               "art. 68 primary text",
     "alternative": "none — the two commercial mirrors both refuse (see above)",
     "verified_here": True},
    {"host": "www.fedlex.admin.ch", "country": "Switzerland",
     "nature": "NOT A REFUSAL — robots.txt says 'Allow: /', but the host serves a "
               "JavaScript-only shell whose body is an 'enable JavaScript' notice, so "
               "art. 335d-335g CO was never read at source",
     "alternative": "www.arbeit.swiss (SECO/ALV), fully permissive, which states the "
                    "duty and the thresholds", "verified_here": False},
    {"host": "www.riigiteataja.ee", "country": "Estonia",
     "nature": "NOT A REFUSAL — robots.txt disallows only court-decision paths and a "
               "list of individual act ids, but the acts render client-side and a plain "
               "fetch receives the 'Laeb...' loading shell, so the Employment Contracts "
               "Act text was never read",
     "alternative": "www.tootukassa.ee, the authority that receives the notification, "
                    "describing its own duty (Crawl-delay 10)", "verified_here": True},
    # --- from the 2026-08-19 sub-national sweep for per-employer registers.
    # These matter more than most: each one is a jurisdiction whose ANSWER we do
    # not have, in the exact search where a national "no" hides a regional "yes".
    {"host": "www.ti.ch", "country": "Switzerland (Ticino)",
     "nature": "robots.txt: 'User-agent: ClaudeBot / Disallow: /'. Zero content requests "
               "were made. Ticino is therefore UNKNOWN in the cantonal register sweep, "
               "not a no",
     "alternative": "none found", "verified_here": False},
    {"host": "www.saskatchewan.ca", "country": "Canada (Saskatchewan)",
     "nature": "robots.txt: 'User-agent: ClaudeBot / Disallow: /'. Zero content requests "
               "were made. Saskatchewan is UNKNOWN in the provincial register sweep, not "
               "a no",
     "alternative": "none found", "verified_here": False},
    {"host": "datos.comunidad.madrid", "country": "Spain (Madrid)",
     "nature": "blanket 'Disallow: /' — and it holds Madrid's ERE dataset, so whether "
               "Madrid names employers the way Balears does is UNVERIFIED. Of the "
               "Spanish communities this is the single most valuable unread file",
     "alternative": "datos.gob.es aggregates the catalogue but not the file",
     "verified_here": False},
    {"host": "opendata.swiss, www.canada.ca, yukon.ca, regione.toscana.it, "
             "princeedwardisland.ca", "country": "Switzerland, Canada, Italy",
     "nature": "HTTP 403 to our identifying agent (PEI behind a Radware WAF). Not "
               "retried under another identity. Yukon, PEI and Toscana are UNKNOWN in "
               "the sub-national sweep rather than negative",
     "alternative": "none found", "verified_here": False},
    {"host": "www.govdata.de, canlii.org", "country": "Germany, Canada",
     "nature": "robots-refused. canlii.org matters least (case law, not notices); "
               "govdata.de is the German federal open-data catalogue and would have been "
               "the one place a Land-level Massenentlassung dataset surfaced",
     "alternative": "the Lander portals, which were swept directly",
     "verified_here": False},
    {"host": "zentralplus.ch", "country": "Switzerland",
     "nature": "HTTP 402, a hard paywall. Not circumvented. Recorded only because a "
               "paywalled local outlet is not a public register and must never be "
               "treated as one",
     "alternative": "none needed", "verified_here": False},
    # --- from the 2026-08-19 Africa / Middle East sweep
    {"host": "pmg.org.za", "country": "South Africa",
     "nature": "robots.txt names ClaudeBot with 'Disallow: /' — twice, plus "
               "'Content-Signal: ai-train=no'. The Parliamentary Monitoring Group is the "
               "obvious archive of committee presentations carrying CCMA retrenchment "
               "figures, and it is closed to us",
     "alternative": "www.gov.za and labour.gov.za, both open — the Budget Vote speeches "
                    "carry the same indicator", "verified_here": False},
    {"host": "beoe.gov.pk", "country": "Pakistan",
     "nature": "robots.txt names ClaudeBot with 'Disallow: /'",
     "alternative": "web.archive.org", "verified_here": False},
    {"host": "nationalgovernment.co.za", "country": "South Africa",
     "nature": "HTTP 403 on robots.txt ITSELF, so permission could not even be "
               "established and nothing was fetched. It mirrors the CCMA Annual Report, "
               "which is why South Africa's FY2023/24 figure stays unverified",
     "alternative": "labour.gov.za, which permits everything except /_layouts/, "
                    "/_vti_bin/ and /_catalogs/", "verified_here": False},
    {"host": "www.loc.gov, leseco.ma, tamimi.com", "country": "United States, Morocco, "
             "Gulf",
     "nature": "403 to our identifying agent (loc.gov, leseco.ma) and a 307 redirect loop "
               "acting as a bot wall (tamimi.com). None defeated",
     "alternative": "lematin.ma for Moroccan coverage; none for the others",
     "verified_here": False},
    {"host": "kuwaitcalculator.com", "country": "Kuwait",
     "nature": "robots.txt is SELF-CONTRADICTORY — a Cloudflare-inserted ClaudeBot block "
               "followed by an explicit ClaudeBot allow. Recorded because the rule for "
               "this case is worth fixing once: an ambiguous directive is treated as the "
               "restrictive one and the host is NOT fetched",
     "alternative": "not needed — a calculator site, no primary material",
     "verified_here": False},
    {"host": "manpower.gov.kw, miepeec.gov.ma, gulfmigration.eu",
     "country": "Kuwait, Morocco",
     "nature": "NOT REFUSALS — ECONNREFUSED / timeout from this environment, robots.txt "
               "included. miepeec.gov.ma is the reason Morocco's publication question is "
               "UNKNOWN rather than answered, and it is the last plausible home of a "
               "per-employer register in the region. Worth retrying from another network",
     "alternative": "web.archive.org served the Kuwaiti labour law's own official PDF; "
                    "nothing substitutes for the Moroccan ministry",
     "verified_here": False},
    # --- from the 2026-08-19 Asia sweep
    {"host": "peraturan.bpk.go.id, learning.hukumonline.com", "country": "Indonesia",
     "nature": "both name ClaudeBot with 'Disallow: /' (hukumonline also carries "
               "'Content-Signal: ai-train=no'). peraturan.bpk.go.id is Indonesia's "
               "OFFICIAL legal database, so PP 35/2021 and UU 13/2003 cannot be read "
               "there — which is why Indonesia's regime is recorded as in doubt rather "
               "than as absent",
     "alternative": "jdih.setneg.go.id, which serves 'User-agent: * / Disallow:' — fully "
                    "permitted, and NOT YET MINED. This is the single cheapest "
                    "outstanding action in the whole register",
     "verified_here": False},
    {"host": "www.samuiforsale.com", "country": "Thailand",
     "nature": "robots.txt: 'User-agent: ClaudeBot  # Anthropic / Disallow: /'",
     "alternative": "thailandlawonline.com, which does the OPPOSITE and names ClaudeBot "
                    "in order to ALLOW it ('User-agent: ClaudeBot / Allow: /') — the "
                    "second host found anywhere in this exercise that permits us by name, "
                    "after the Swedish riksdag", "verified_here": False},
    {"host": "www.commonlii.org", "country": "Pakistan and Commonwealth",
     "nature": "robots.txt names ClaudeBot with 'Disallow: /', so the Punjab 1968 "
               "Ordinance's SO 11-A could not be read at primary source",
     "alternative": "clr.org.pk (Crawl-delay 30), which served the Sindh Act verbatim",
     "verified_here": False},
    {"host": "www.ilo.org, natlex.ilo.org (/dyn/*)", "country": "international",
     "nature": "both disallow /dyn/*, which is where every NATLEX statute PDF lives. "
               "Recorded alongside the existing natlex bot-wall entry because the "
               "DIRECTIVE is a second, independent reason not to fetch it",
     "alternative": "clr.org.pk for Pakistan, casainvest.ma for Morocco, "
                    "botswanalmo.org.bw for Botswana — national mirrors carried what "
                    "NATLEX would have", "verified_here": False},
    {"host": "satudata.kemnaker.go.id, gso.gov.vn, nso.gov.vn, labour.go.th, "
             "legal.labour.go.th, punjablaws.gov.pk, kpcode.kp.gov.pk, vbpl.vn",
     "country": "Indonesia, Vietnam, Thailand, Pakistan",
     "nature": "NOT REFUSALS — ECONNREFUSED, timeout or 502 from this environment, "
               "robots.txt included. Every publication verdict in the Asian backlog is "
               "UNKNOWN for this reason and not for a publisher's decision. Worth "
               "retrying from another network before anyone concludes anything about "
               "these four countries",
     "alternative": "none from here", "verified_here": False},
    # --- path-level disallows a production collector must honour
    {"host": "www.moel.go.kr /info/defaulter/", "country": "South Korea",
     "nature": "path-level disallow over the ONE genuine per-employer public naming "
               "register found in Korea — habitual wage-arrears employers, published "
               "under a statutory disclosure scheme. It is not a layoff register and was "
               "not fetched, but it is recorded because it proves the naming barrier for "
               "layoff filings in Korea is policy rather than statute",
     "alternative": "none needed — wrong subject", "verified_here": False},
    {"host": "www.paragraf.ba /propisi/", "country": "Bosnia and Herzegovina",
     "nature": "NOT A REFUSAL in the usual sense, recorded because it reads like one: "
               "robots disallows /propisi/ but carries an explicit 'Allow: *.html$' "
               "exception, and the consolidated labour laws are .html. A future pass "
               "must read the exception rather than stopping at the Disallow",
     "alternative": "the same paths, which are permitted", "verified_here": False},
    {"host": "donneesquebec.ca/recherche/api/, data.ontario.ca/api/, "
             "datos.gob.ar/api/, datos.gob.cl/api/, data.gov.il/api/, "
             "catalogodatos.gub.uy/api/", "country": "Canada, Argentina, Chile, "
             "Israel, Uruguay",
     "nature": "path-level 'Disallow: /api/' on the open-data portals. Recorded "
               "because two research passes queried these APIs before reading the "
               "robots file and stopped on seeing it — the rule is to read robots.txt "
               "BEFORE the first content request, and the order is what went wrong",
     "alternative": "the HTML search paths on the same hosts are permitted",
     "verified_here": False},
    {"host": "argentina.gob.ar (all PDF/DOC/XLS paths), INEGI /rnm/.../download/*, "
             "STPS /07_justicia_lab/", "country": "Argentina, Mexico",
     "nature": "path-level disallows covering exactly the document formats a "
               "statistics collector would want",
     "alternative": "the HTML pages on the same hosts", "verified_here": False},
)



# ---------------------------------------------------------------------------
# THE PER-EMPLOYER REGISTERS — the far more valuable question, asked separately
# ---------------------------------------------------------------------------
# EVERYTHING ABOVE ANSWERS "DOES A COUNTABLE TOTAL EXIST". This answers a
# different and much better question: does a public authority anywhere publish
# a list that NAMES THE EMPLOYER filing a collective-dismissal notice? A total
# makes coverage MEASURABLE. A register makes layoffs FINDABLE, which is the
# thing the tracker is actually for, and the two must never be conflated — the
# error that has bitten this project twice.
#
# The owner's question was "in most countries there is no register to search;
# do we have them all, or are there more to register with?" This is where that
# is answered, and the answer is kept apart from the coverage register on
# purpose so nobody reads "publishes a total" as "names employers".
#
# THE SHAPE OF THE WORLD, as established on 2026-08-19: at national level,
# essentially nowhere. Sweden's Arbetsformedlingen states that a varselanmalan
# is ALWAYS covered by secrecy; Canada's ESDC states that group termination
# notices are confidential and records that one bank's details "were published
# in error and have since been removed"; the canton of Aargau handles
# notifications "mit hochster Diskretion". Naming is the exception and it is
# devolved almost everywhere it happens — which is why a national NO is not an
# answer in a country that devolves labour administration, and why the search
# below went to cantons, provinces, voivodeships and autonomous communities.
#
# 165+ sub-national units were checked by name to produce this list. The
# NEAR-MISSES are recorded with it because they are what stops the next pass
# re-walking the same ground: a jurisdiction that publishes the row and omits
# the name is a decision that could change, and it is a different thing from a
# jurisdiction that publishes nothing.
PER_EMPLOYER_REGISTERS = (
    {"jurisdiction": "United States (state WARN units)", "country": "United States",
     "names_employers": True,
     "what": ("one row per WARN notice with employer, site, date and headcount. The "
              "type specimen, and the only one at national-scale coverage — because it "
              "is 50-odd separate state registers, not one"),
     "since": "varies by state", "in_tracker": True,
     "cite": "https://www.dol.gov/agencies/eta/layoffs/warn"},
    {"jurisdiction": "Quebec", "country": "Canada", "names_employers": True,
     "what": ("avis de licenciement collectif, published monthly by the ministry with "
              "employer, region and headcount. Re-verified 2026-08-19: a scrapeable "
              "monthly PDF URL pattern. THE MINISTRY'S OWN CAVEAT MATTERS — a notice is "
              "an INTENTION, and the list is NOT revised when an amendment arrives, so "
              "it is an upper bound on that employer's cut"),
     "since": "the only Canadian province of 13 that names", "in_tracker": True,
     "cite": "https://www.quebec.ca/emploi/aide-employeurs/licenciement-collectif"},
    {"jurisdiction": "Mazowieckie voivodeship", "country": "Poland",
     "names_employers": True,
     "what": ("zwolnienia grupowe listing naming the employer. Found only because "
              "somebody surveyed all 16 Polish voivodeship labour offices and exactly "
              "one named employers — the warning this whole exercise is built on"),
     "since": "one of 16 voivodeships", "in_tracker": True,
     "cite": "https://wupwarszawa.praca.gov.pl/"},
    {"jurisdiction": "Illes Balears", "country": "Spain", "names_employers": True,
     "what": ("THE FOURTH PLACE ON EARTH, found 2026-08-19 and verified by downloading "
              "the file rather than by reading a catalogue page. 'Expedients Regulacio "
              "Ocupacio (ERO i ERTO) Illes Balears', CC-BY, 49 columns, 3,817 rows: "
              "EMPRESA (populated on every row), NIF, DATA PRESENTACIO, MUNICIPI, ILLA, "
              "NUM. TOTAL TREBALLADORS, TREBALLADORS AFECTATS INICIAL, CODI CNAE 09, "
              "CAUSES and MESURA. THE CAVEAT THAT SIZES IT HONESTLY, and it is a large "
              "one: MESURA splits SUSPENSIO 1,747 / RED. JOR. 971 / blank 740 / "
              "EXTINCIO 359, and only those 359 are collective DISMISSALS — the rest is "
              "short-time work, the same near-miss that ERTE is everywhere in Spain. The "
              "companion 2023-2025 file is ERTO-only, so NAMED DISMISSAL ROWS EFFECTIVELY "
              "STOP AT 2022 and the catalogue marks the dataset 'No s'actualitza'. It "
              "settles the existence question. It is not a WARN-scale feed. "
              "CORROBORATION: ASEDIE's 2026 infomediary report finds 11 Spanish "
              "communities publish ERE/ERTE datasets and that ONLY Baleares includes the "
              "NIF or razon social"),
     "since": "2008-2022 for dismissals", "in_tracker": False,
     "verified_from_file": "2026-08-19",
     "name_column": "EMPRESA",
     "measure_column": "MESURA",
     "measure_values": ("EXTINCIO", "SUSPENSIO", "RED. JOR.", ""),
     "dismissal_measures": ("EXTINCIO",),
     "licence": "CC-BY 4.0",
     "cite": ("https://intranet.caib.es/opendatacataleg/dataset/"
              "expedients-regulacio-ocupacio-ero-erto-illes-balears")},
    # --- NEAR-MISSES. Recorded because each is a decision rather than an
    # absence, and a decision can be revisited by whoever made it.
    {"jurisdiction": "Euskadi", "country": "Spain", "names_employers": False,
     "what": ("THE BEST NEAR-MISS ON EARTH, and SETTLED 2026-08-19 BY DOWNLOADING THE "
              "FILE — which changed the answer. The survey had recorded 'the company CIF "
              "masked', a statement about the IDENTIFIER, and that left open whether a "
              "name column sat beside it. It does not. eres_cae.csv carries SIXTEEN "
              "columns and NOT ONE OF THEM IS AN EMPLOYER NAME: the employer appears "
              "only as a masked CIF, on all 216 of 216 rows, zero unmasked. So Euskadi "
              "is not one un-redaction away from being a register; the name is not in "
              "the publication at all, and restoring it would be a new column rather "
              "than a lifted mask. Everything else IS as good as it looked — CC-BY, "
              "weekly refresh, 216 rows 2021-11-08 to 2026-06-18, current where Balears "
              "stops in 2022, split Extincion 79 / Suspension 101 / Reduccion 36. The "
              "XLSX distribution was checked too and is the same single sheet with the "
              "same sixteen columns, so this is not a CSV-export artefact. SAMPLE ROW "
              "(most recent Extincion): BIZKAIA;48/2026/000013J;Territ.;Extincion;"
              "Ec:Perdidas actuales;Abadino;15/06/2026;;***7485**;2553;11;10;1;11;10;1"),
     "since": "2021", "in_tracker": False,
     "verified_from_file": "2026-08-19",
     "name_column": None,
     "verified_columns": (
         "TERRITORIO / LURRALDEA", "EXPEDIENTE / ESPEDIENTEA",
         "AUTORIDAD / AUTORITATEA", "TIPO REGULACION / ERREGULAZIO MOTA",
         "CAUSA / KAUSA", "MUNICIPIO / UDALERRIA", "FECHA / DATA",
         "FIN REGULACION / ERREGULAZIOAREN AMAIERA-DATA", "CIF / IFK",
         "CNAE / EJSN", "AFECTADOS / UKITUAK", "AFECTADOS HOMBRES / UKITU GIZONEZKOAK",
         "AFECTADAS MUJERES / UKITU EMAKUMEZKOAK",
         "TOTAL TRABAJADORES / LANGILEAK GUZTIRA",
         "TRABAJADORES HOMBRES / LANGILE GIZONEZKOAK",
         "TRABAJADORAS MUJERES / LANGILE EMAKUMEZKOAK"),
     # The tenfold trap, recorded even though nothing is wired: 79 of 216 rows
     # are dismissals and the other 137 are short-time work. Anything ever built
     # on this file filters on the measure column FIRST.
     "measure_column": "TIPO REGULACION / ERREGULAZIO MOTA",
     "measure_values": ("Extincion", "Suspension", "Reduccion"),
     "dismissal_measures": ("Extincion",),
     "licence": "CC-BY 4.0",
     "data_url": ("https://opendata.euskadi.eus/contenidos/ds_procedimientos_otros/"
                  "ertes_covid_2020/opendata/eres_cae.csv"),
     "cite": "https://opendata.euskadi.eus/"},
    {"jurisdiction": "Podlaskie voivodeship", "country": "Poland",
     "names_employers": False,
     "what": ("SETTLED 2026-08-19 from the documents themselves, and it is a WEAKER "
              "near-miss than the survey's 'same shape as Euskadi' implied. WUP "
              "Bialystok publishes one PDF PER YEAR, 2013-2026, of monthly per-notice "
              "rows under FIVE headings — Miesiace, Powiat/Miejscowosc, Branza zakladu "
              "pracy, Liczba pracownikow zgloszonych do zwolnienia, Planowany termin — "
              "and there is no employer column AND no employer identifier of any kind, "
              "not even a masked one. Euskadi at least prints a redacted CIF; Podlaskie "
              "prints the SECTOR where the employer would go, which is a category and "
              "not an entity. Verified across two years so it is structural rather than "
              "one year's choice. SAMPLE ROW (2026): 'Luty 2026 r. | augustowski | "
              "produkcja bielizny | 24 | 2 os. zwoln. w III, 11 os. zwoln. w IV'. The "
              "register is also tiny — the whole of 2026 to 07.07.2026 is three notices "
              "and 89 people — so even named it would be a rounding error beside "
              "Mazowieckie. All rows are dismissals (zwolnienia grupowe); Poland has no "
              "short-time-work measure mixed into this document, so the Spanish "
              "EXTINCIO/SUSPENSIO trap does not arise here"),
     "since": "2013", "in_tracker": False,
     "verified_from_file": "2026-08-19",
     "name_column": None,
     "verified_columns": ("Miesiace", "Powiat/Miejscowosc", "Branza zakladu pracy",
                          "Liczba pracownikow zgloszonych do zwolnienia",
                          "Planowany termin dokonania zwolnien/osoby zwolnione"),
     "measure_column": None,
     "measure_values": (),
     "dismissal_measures": (),
     "licence": ("no licence statement found on the page or in the PDFs; Polish public "
                 "information, but NOT citable terms, so nothing here is stored"),
     "data_url": "https://wupbialystok.praca.gov.pl/zgloszenia-zwolnien-grupowych",
     "cite": "https://wupbialystok.praca.gov.pl/"},
    {"jurisdiction": "federal (SPF Emploi / FOD WASO)", "country": "Belgium",
     "names_employers": False,
     "names_selectively": True,
     "what": ("PARTIAL AND SELECTIVE, which is why it is a near-miss rather than a "
              "register. The quarterly and annual collective-dismissal reports name "
              "individual firms with headcount and municipality, but in NARRATIVE prose "
              "and explicitly only the ones that drew media attention — roughly 40 named "
              "of 112 units in 2025. Useful as a named-entity target, never as a feed, "
              "and a coverage figure built on it would measure Belgian press interest"),
     "since": None, "in_tracker": False,
     "cite": ("https://emploi.belgique.be/fr/themes/restructuration/licenciement-collectif/"
              "statistiques-relatives-aux-restructurations")},
    {"jurisdiction": "14 krajske pobocky", "country": "Czechia", "names_employers": False,
     "names_selectively": True,
     "what": ("REPORTED, NOT VERIFIED. Each regional labour office's annual "
              "'Zprava o situaci na krajskem trhu prace' PDF is reported to carry "
              "hromadne propousteni counts AND to name the largest filing employers, "
              "2013-2025. Same narrative-selection objection as Belgium. Verification "
              "failed here: the PDFs are font-subset encoded and a hand-rolled text "
              "extraction silently drops every diacritic word"),
     "since": "2013", "in_tracker": False,
     "cite": "https://up.gov.cz/tiskove-zpravy"},
)

# The units swept to produce the list above, recorded so the next pass does not
# re-walk them. Named rather than counted, because "we checked Switzerland" is
# not a claim anybody can check and "we checked 14 named cantons" is.
PER_EMPLOYER_SWEPT = {
    "Switzerland": ("14 of 26 cantons by name: ZH BS AG SO ZG TG GE VD BE LU SG FR NE "
                    "JU. No cantonal naming list found. Ticino (www.ti.ch) names "
                    "ClaudeBot and disallows all, so TI is UNKNOWN, not no"),
    "Canada": ("all 13 jurisdictions plus the federal ESDC regime. ESDC states group "
               "termination notices are CONFIDENTIAL. Only Quebec names. Saskatchewan "
               "names ClaudeBot and disallows all; Yukon and PEI blocked; those three "
               "are UNKNOWN, not no"),
    "Poland": "all 16 voivodeships. Mazowieckie names; Podlaskie publishes rows with "
              "no employer column and no identifier at all (file-verified 2026-08-19); "
              "the BIP sites of the WUPs are the one surface not swept",
    "Spain": ("13 of 17 autonomous communities. Balears names; Euskadi publishes no "
              "name column at all (file-verified 2026-08-19, not merely masked). "
              "datos.comunidad.madrid is 'Disallow: /' and holds Madrid's ERE CSV, "
              "whose fields are therefore UNVERIFIED"),
    "Germany": "Bund, the Regionaldirektionen and the Lander open-data portals. Nothing "
               "per-employer, and the BA Fachstatistiken catalogue carries no "
               "Massenentlassung product at all",
    "Japan": "4 of 47 prefectural labour bureaus (Hokkaido, Aichi, Osaka, Tottori). "
             "Procedure pages only, no lists. The other 43 are UNKNOWN",
    "South Korea": "the regional employment and labour offices publish awareness notices "
                   "about the duty to file, never lists of filers",
    "Italy": ("not swept below national level, and it should be: Regione Lombardia's own "
              "page routes art. 4 filings AWAY from itself to the PROVINCES, so Italian "
              "per-employer data sits one tier below where anyone has looked"),
}

# ---------------------------------------------------------------------------
# THE ACKNOWLEDGED BACKLOG — the one concession, and why it is not an exemption
# ---------------------------------------------------------------------------
# The world is not classified yet and it will not be for some time. If `judge`
# went UNKNOWN on every unclassified country, CountryCoverageInvariant would be
# red from the day it ships until the day the last country lands, and this repo
# knows exactly what that does: the Spirit assertion reddened CI eight times in
# one afternoon and eight identical emails is how an alert channel gets
# filtered. A check that is always red is a check nobody reads.
#
# So the failure this guards is narrowed to the one that is actually a defect:
# NOT "we have not finished the world", but "a country ARRIVED in the data and
# nobody noticed". A country listed here is acknowledged, dated outstanding
# work. A country in the corpus that is in NEITHER the register NOR this list is
# undeclared, and that reddens.
#
# This is the `DECLARED_SLICES` idiom from rolling_recall pointed at a set that
# grows on its own. It is not a snooze button, and the two things that stop it
# becoming one are deliberate:
#   * every entry carries the date it was acknowledged, and ops_status [3d]
#     prints the count and the OLDEST date at the top of every session, so the
#     backlog is in front of a human constantly rather than filed away
#   * adding a country here is a code change with a reviewer, not a runtime
#     side effect. Nothing can move a country into this list by itself.
#
# Shrinking it is the work. Growing it to silence a red run is the abuse.
BACKLOG_DECLARED = "2026-08-18"

ACKNOWLEDGED_BACKLOG = {
    'Bosnia and Herzegovina': ("2026-08-18",
      "ONE ENTITY OF THREE IS NOW READ. Federation of BiH: Zakon o radu FBiH "
      "(Sl. novine FBiH 26/16, 89/18, 44/22) cl. 109 — an employer of more than "
      "30 workers intending to dismiss at least 5 for economic, technical or "
      "organisational reasons over the next three months must CONSULT the works "
      "council and the union; cl. 110 sets a 30-day consultation lead and the "
      "content of the written notice; cl. 111 is severance. Every addressee in "
      "109-111 is INTERNAL — no submission to the sluzba za zaposljavanje or "
      "any public body was found, which points to no disclosure regime in FBiH. "
      "Not recorded, for two reasons: it rests on one host (paragraf.ba, whose "
      "robots disallows /propisi/ but carries an explicit 'Allow: *.html$' "
      "exception that this path meets), and the duty could still sit in the "
      "Zakon o posredovanju u zaposljavanju, which was not read. Republika "
      "Srpska: a duty is REPORTED at Zakon o radu RS cl. 163 — the draft "
      "redundancy programme goes to the union AND the Zavod within 8 days, with "
      "cl. 164(2) obliging the Zavod to reply in 15 days — so RS and FBiH may "
      "genuinely differ and neither may be inferred from the other. Brcko "
      "District: unchecked. Publication in all three: unchecked. METHOD WARNING "
      "FOR WHOEVER PICKS THIS UP: a hand-rolled zlib/PDF-operator text "
      "extraction of the consolidated FBiH law SILENTLY DROPPED every word "
      "containing c/c/s/z, which is most of the legal vocabulary. Use the HTML "
      "or a real PDF library."
      ),
    'Cambodia': ("2026-08-18",
      "REGIME ESTABLISHED FROM PRIMARY TEXT, AND THIS FILE'S OWN CITATION WAS "
      "WRONG. Labour Law (Kram of 13 March 1997) ARTICLE 95 ALONE carries the "
      "mass-layoff duty — read verbatim, it defines mass layoff as any layoff "
      "resulting from a reduction in an establishment's activity or a foreseen "
      "internal re-organization, sets selection criteria and last-in-first-out "
      "with family weighting, a two-year re-hire priority, and the sentence "
      "that matters: 'The Labour Inspector is kept informed of the procedure "
      "covered in this article.' On a worker-representative request the "
      "Inspector may convene the parties and the Minister may issue a Prakas "
      "SUSPENDING the layoff for up to 30 days, repeatable once. ARTICLE 371 "
      "makes it mandatory rather than hortatory: dismissal under art. 95 "
      "without informing the Labour Inspector draws a fine of 61-90 days' base "
      "wage or 6 days to a month's imprisonment. CORRECTION RECORDED: the "
      "previous note paired art. 95 with art. 130. Article 130 is the WAGE "
      "GARNISHMENT ceiling and art. 131 its food-creditor exception — nothing "
      "to do with layoffs. There is NO numeric threshold and NO stated notice "
      "period; the duty is procedural. PUBLICATION UNKNOWN: no periodic count "
      "from MLVT or NIS was located, and the search was not exhaustive in "
      "Khmer, so this is UNKNOWN rather than a negative."
      ),
    'China': ("2026-08-18",
      "ART. 41 IS NOW VERIFIED AND CHARACTERISED; PUBLICATION REMAINS "
      "UNRESOLVED. Labour Contract Law art. 41: where an employer cuts 20+ "
      "workers, or fewer than 20 but more than 10% of the workforce, it must "
      "explain to the union or all employees 30 days in advance, hear their "
      "opinions, and REPORT the reduction plan to the labour administration "
      "department before implementing it. THE DISTINCTION THAT MATTERS: this is "
      "报告, a report, NOT 审批, an authorisation — so unlike India and Morocco "
      "China is a notification regime, and a count of filings would be a count "
      "of layoffs rather than of applications. Attested consistently across the "
      "Supreme People's Procuratorate commentary and provincial portals; the "
      "consolidated text was NOT read on a .gov.cn host, which is recorded as a "
      "gap rather than a doubt. PUBLICATION IS UNKNOWN AND SHOULD BE STATED AS "
      "UNKNOWN: mohrss.gov.cn — the ministry that receives these reports — "
      "serves an obfuscated JavaScript anti-bot challenge and was never "
      "attempted; stats.gov.cn returns HTTP 404 for robots.txt (so it is "
      "unrestricted) and carried nothing, but was not exhaustively searched. "
      "REJECTED NEAR-MISS: MOHRSS unemployment-insurance FUND OUTLAYS are money, "
      "not layoffs, and must never be used as a layoff series."
      ),
    'Czechia': ("2026-08-18",
      "STATUTE VERIFIED, PUBLICATION STILL OPEN, and the reason it is still "
      "open is recorded so the next pass does not repeat the same dead end. "
      "Zakonik prace (262/2006 Sb.) s.62 with s.62(5) — the duty to notify the "
      "krajska pobocka Uradu prace. TWO PUBLICATION LEADS, NEITHER CLOSED: (1) "
      "UP CR ran a DEDICATED national release carrying employers-filing and "
      "employees-covered (Dec 2013: 15 employers / 901 workers; Dec 2014: 26 / "
      "877) but the last one found is from January 2016, and recent figures "
      "reach the public through statements to CTK rather than a series. (2) "
      "each of the 14 krajske pobocky publishes an annual 'Zprava o situaci na "
      "krajskem trhu prace' PDF, 2013 through 2025, and those are REPORTED to "
      "carry counts AND to name the largest filing employers — which would make "
      "Czechia the closest thing to a per-employer source outside the three "
      "known registers, at narrative rather than per-notice granularity. "
      "VERIFICATION FAILED HERE FOR A REASON WORTH KEEPING: Rocni_OLK_2024.pdf "
      "was fetched (up.gov.cz permits us; HTTP 200, 1.2 MB) and its text "
      "extracted by decompressing the content streams, and EVERY WORD "
      "CONTAINING A CZECH DIACRITIC IS SILENTLY MISSING from that extraction — "
      "'hromadne propousteni' cannot be found because the accented glyphs live "
      "in a separate font subset. A hand-rolled PDF parser does not fail loudly "
      "here, it fails by omission, which is how it would have produced a "
      "confident wrong quote. TO CLOSE: read ONE regional report with a real "
      "PDF library."
      ),
    'Hong Kong': ("2026-08-18",
      "STRONGLY INDICATED NO_REGIME, STILL NOT RECORDED, AND NOW BETTER "
      "EVIDENCED THAN BEFORE. The Labour Department's own Concise Guide to the "
      "Employment Ordinance — on labour.gov.hk, which returns 404 for "
      "robots.txt and is therefore unrestricted — covers the whole Ordinance in "
      "13 chapters (application, contract, wages, rest days and leave, sickness "
      "allowance, maternity, paternity, end-of-year payment, termination, "
      "employment protection, severance and long service payment, anti-union "
      "discrimination, employers' criminal liability) plus three appendices, "
      "with NO collective-redundancy chapter and NO notification provision "
      "anywhere; redundancy appears only as a trigger for severance. Two "
      "independent practitioner sources state positively that Hong Kong has no "
      "concept of collective dismissal and no duty to inform or consult. Also "
      "worth recording: the Employee's Rights to Representation, Consultation "
      "and Collective Bargaining Ordinance 1997 was repealed and never revived. "
      "STILL NOT RECORDED because the guide is an authoritative DESCRIPTION of "
      "Cap. 57 rather than Cap. 57 itself: elegislation.gov.hk allows only "
      "Googlebot and Bingbot, and ILO EPLex — the one instrument note that "
      "would have settled it — returns HTTP 403 to our agent on every country "
      "page. Same rule as New Zealand."
      ),
    'Hungary': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. The "
      "instrument is Mt. 2012. evi I. tv. ss.71-76, with s.74 the notification "
      "duty, filed through the ESTAT portal to the county kormanyhivatal. "
      "NARROWED, NOT CLOSED: the COMPLETE NFSZ statistics catalogue (11 series) "
      "was enumerated and none covers collective redundancies; KSH returns only "
      "OSAP methodology guides. But county-level counts demonstrably exist and "
      "are released to local press (142 notifications in Heves varmegye "
      "2024-10 to 2025-02; a Vas varmegye release in 2025-09), and whether they "
      "are PUBLISHED or answered on request could not be established — one "
      "carrier, heol.hu, returned HTTP 403 to our agent and was not retried "
      "under another identity. So this is UNKNOWN, not 'nothing is published'. "
      "TO CLOSE: the 20 varmegye kormanyhivatal sites plus Budapest. "
      "NEAR-MISSES ALREADY REJECTED: nfsz.munka.hu/cikk/1595 is a wage subsidy "
      "to AVOID redundancy, and stat_negyedeves_felmeres is a quarterly "
      "employer SURVEY of expected headcount change."
      ),
    'India': ("2026-08-18",
      "A PERMISSION REGIME, NOT A NOTIFICATION ONE, and the distinction is "
      "load-bearing: permission can be REFUSED and the layoff then never "
      "happens, so a count of applications is not a count of layoffs. Industrial "
      "Disputes Act 1947 Ch. V-B (establishments above 100, or 300 in some "
      "states) — STATUTE NOT VERIFIED here and must not be restated from "
      "memory. One sweep reports the only published series is voluntary state "
      "returns, roughly 3 years stale, scanned-image PDFs, with implausible "
      "single-digit national case counts; another found no "
      "industrial-disputes/retrenchment series in the Labour Bureau navigation "
      "at all. Neither is verified. ACCESS: every *.gov.in and *.nic.in host "
      "403s an identifying agent; labourbureau.gov.in answers 200 and is the "
      "permitted route."
      ),
    'Indonesia': ("2026-08-18",
      "THE REGIME ITSELF IS NOW IN DOUBT, WHICH IS A STRONGER STATEMENT THAN "
      "THE PREVIOUS NOTE MADE. The notification article under UU 13/2003 as "
      "amended by UU 6/2023 with PP 35/2021 appears to be PP 35/2021 Pasal 37, "
      "and ITS ADDRESSEE IS NOT THE GOVERNMENT: the purpose and reasons of a "
      "PHK are notified by the employer TO THE WORKER AND/OR THE UNION, by "
      "surat pemberitahuan at least 14 working days ahead (7 in probation). No "
      "general duty to notify a public authority of a collective PHK was found; "
      "the state enters at the DISPUTE stage through bipartite negotiation and "
      "Disnaker mediation under UU 2/2004, and the pre-Cipta-Kerja penetapan "
      "requirement was removed. DO NOT PUBLISH NO_REGIME ON THIS: both official "
      "primary hosts REFUSED us — peraturan.bpk.go.id, the official legal "
      "database, names ClaudeBot with 'Disallow: /', and so does "
      "learning.hukumonline.com — so Pasal 37 is secondary. THE PERMITTED "
      "ALTERNATIVE IS IDENTIFIED AND NOT YET MINED: jdih.setneg.go.id serves "
      "'User-agent: * / Disallow:' (fully permitted). TO CLOSE: read PP 35/2021 "
      "arts. 37-40 and UU 13/2003 art. 151 there. SEPARATELY, a count IS "
      "published and it is exactly as mixed as suspected — Kemnaker's Satu Data "
      "publishes monthly WORKER counts by province (Jan-Jun 2026: 32,389; 2024: "
      "77,965), classified by JKP unemployment-insurance participation and "
      "excluding resignation, retirement, disability and death per PP 6/2025 "
      "and Permenaker 2/2025, compiled from regional office reports and "
      "acknowledged incomplete. THE CONSEQUENCE IS THE INTERESTING PART: a "
      "count exists that is NOT the by-product of a notification duty, so "
      "Indonesia cannot be classified as REGIME_WITH_AGGREGATE without settling "
      "the Pasal 37 addressee question first. REJECTED: BPS publishes no PHK "
      "count — its 'PHK' indicator is the percentage of HOUSEHOLDS receiving "
      "severance pay, from a household survey."
      ),
    'Isle of Man': ("2026-08-18",
      "LEANS NO_REGIME, NOW ON TWO POSITIVE SECONDARY STATEMENTS RATHER THAN "
      "ON SILENCE, AND STILL NOT RECORDED. Two independent practitioner sources "
      "(CIPD HR-inform and a Mondaq Isle of Man country chapter) state that no "
      "collective consultation rights are in force, that there is no equivalent "
      "of TULRCA's 20-employee threshold, and that the Employment Act 2006 "
      "imposes no duty to inform or consult — coherent with the Island being "
      "outside the EU and never transposing Directive 98/59/EC. BOTH ARE "
      "SECONDARY. Every Isle of Man government host (gov.im, "
      "legislation.gov.im) returns a WAF 'Request Rejected' page to automated "
      "fetching and was NOT retried, so the Act itself is unread. This register "
      "records NO_REGIME only on the instrument, so it stays outstanding."
      ),
    'Morocco': ("2026-08-18",
      "THE STATUTE IS NOW READ IN FULL AND PUBLICATION IS UNKNOWN — those are "
      "two separate states and the entry must not collapse them. Code du "
      "Travail (Loi 65-99) art. 66: an employer habitually employing TEN OR "
      "MORE workers who plans to dismiss all or some for technological, "
      "structural or economic reasons must inform the workers' delegates and "
      "union representatives at least one month ahead, and a signed "
      "proces-verbal of those consultations goes to the delegue provincial "
      "charge du travail. Art. 67: the dismissal is SUBORDINATE TO AN "
      "AUTHORISATION issued by the gouverneur of the prefecture or province "
      "within two months, on the conclusions of a provincial commission the "
      "gouverneur chairs; an economic file additionally needs a grounds "
      "report, the firm's financial position and a chartered accountant's "
      "report. Art. 69 extends it to closures, art. 70 keeps notice and "
      "severance owed whether or not the authorisation was obtained. THIS IS "
      "EX-ANTE APPROVAL, NOT NOTIFICATION, and the consequence is the same as "
      "India's: the countable state event is an APPLICATION, permission can be "
      "refused, and any aggregate must say 'granted'. PUBLICATION UNKNOWN FOR "
      "AN ENVIRONMENT REASON, NOT A REFUSAL: miepeec.gov.ma — the ministry "
      "running the Observatoire National du Marche du Travail and its annual "
      "labour-market report, the one plausible publisher — answers ECONNREFUSED "
      "from here, robots.txt included. That is also the only remaining place in "
      "this region a per-employer register could exist unseen, since the "
      "provincial commissions hold named files. REJECTED: a lawyer's newspaper "
      "assertion that no economic-dismissal authorisation was issued between "
      "2004 and 2020 is colour, never a figure. TO CLOSE: reach miepeec.gov.ma "
      "from an environment with Moroccan egress."
      ),
    'New Zealand': ("2026-08-18",
      "STRONGLY INDICATED NO_REGIME, STILL DELIBERATELY NOT RECORDED AS ONE, "
      "and the evidence is now stronger than it was. MBIE's own complete "
      "redundancy process page (employment.govt.nz, which permits us with "
      "Crawl-delay 5) was read end to end: it lays out the entire process and "
      "contains NO notification duty to any agency, NO collective threshold and "
      "NO reporting step; the only agency named is MSD, explicitly as optional "
      "employer support. That is proof by silence on the government's own "
      "complete page. THE TWO SOURCES THAT WOULD HAVE MADE IT POSITIVE BOTH "
      "REFUSED: the OECD EPL country note sits under oecd.org/content/dam/, "
      "which robots excludes, the OECD EPL dataset page returns HTTP 403, and "
      "ILO EPLex returns 403 on both of its hosts. nzlii.org names ClaudeBot "
      "with 'Disallow: /'. legislation.govt.nz's AWS WAF was never attempted. "
      "So the Employment Relations Act 2000 is STILL unread, and 'no regime "
      "exists' is the one claim this register makes only on the instrument. TO "
      "CLOSE: one human reading of the Act. REJECTED NEAR-MISS: ERA s.69O lets "
      "the Employment Relations Authority determine redundancy entitlements — a "
      "dispute-resolution power, not a disclosure duty."
      ),
    'Pakistan': ("2026-08-18",
      "PAKISTAN IS NOT NO_REGIME, AND THE PREVIOUS NOTE'S WORKING HYPOTHESIS IS "
      "OVERTURNED AT THE PROVINCIAL LEVEL — where it had to be answered. What "
      "exists is not a notification duty but a PRIOR-APPROVAL duty with a "
      "numeric threshold. SINDH, READ VERBATIM: Sindh Terms of Employment "
      "(Standing Orders) Act 2015, Standing Order 15 — no employer shall "
      "terminate the employment of MORE THAN FIFTY PERCENT OF THE WORKERS or "
      "close down the whole establishment WITHOUT PRIOR PERMISSION OF THE "
      "GOVERNMENT, except for fire, catastrophe, power stoppage, epidemic or "
      "civil commotion; an undecided application is DEEMED GRANTED after 15 "
      "days; appeal to the Labour Court within 30 days; and the explanation "
      "extends 'close down' to a lay-off beyond fourteen days that results in "
      "closure. The negative half was read too: SO 16 notice runs to the "
      "WORKER, SO 18 'Procedure for retrenchment' is last-in-first-out and "
      "nothing else, SO 19 re-employment preference goes to the workers by "
      "registered post — so ORDINARY retrenchment in Sindh has no authority "
      "duty at all. PUNJAB, SECONDARY: the 1968 Ordinance's SO 11-A, inserted "
      "in 1973, is the parent clause with ONE MATERIAL DIFFERENCE — permission "
      "runs to the LABOUR COURT, not the Government. KP (its own 2013 Act) and "
      "BALOCHISTAN (its own 2021 Act) are UNKNOWN: kpcode.kp.gov.pk timed out "
      "and the Balochistan PDF has no extractable text layer and needs OCR. All "
      "four apply to establishments of 20+ workers. PUBLICATION UNKNOWN. "
      "STRUCTURAL LEAD WORTH KEEPING: a >50%-or-closure event generates a "
      "per-employer APPLICATION FILE held by the provincial Government (Sindh) "
      "or by the Labour Court (Punjab), and Labour Court orders are adjudicative "
      "records. Whether any of it is published is untested."
      ),
    'South Korea': ("2026-08-18",
      "THE STATUTE IS NOW VERIFIED FROM PRIMARY TEXT and the publication "
      "question is still open. Korea has TWO parallel duties, and this register "
      "previously named only the first: (1) Labor Standards Act art. 24(4) with "
      "Enforcement Decree art. 10 — file a dismissal plan with the Minister of "
      "Employment and Labor 30 days ahead where dismissals within one month "
      "reach 10+ (firm under 100 staff), 10% (100-999) or 100+ (1,000+); (2) "
      "Framework Act on Employment Policy art. 33 with Enforcement Decree art. "
      "31 — notify the head of the employment security agency of a large "
      "employment change, 30+ separations in a month (firm under 300) or 10% "
      "(300+), with an EXPLICIT CARVE-OUT where an art. 24(4) filing was "
      "already made, so the two do not double-count. Both read on law.go.kr, "
      "which permits us ('User-agent:* / Allow: /'). Korea's per-firm trigger "
      "is materially LOWER than Japan's flat 30. PUBLICATION UNKNOWN, and "
      "UNKNOWN is the verdict rather than a negative: no table for either "
      "filing was found in KOSIS, laborstat.moel.go.kr renders its statistics "
      "tree in JavaScript and served navigation chrome only, and "
      "eis.work24.go.kr is an empty SPA to a fetcher. TO CLOSE, cheapest first: "
      "the Employment and Labor Statistics Yearbook PDFs (bbsId=LSS113), "
      "chapter 고용안정, which is exactly where such a count would sit. "
      "NEAR-MISS WORTH NAMING BECAUSE IT LOOKS LIKE A PER-EMPLOYER REGISTER AND "
      "IS NOT: MOEL does run a genuine statutory public NAMING register of "
      "employers — but for habitual WAGE ARREARS, not layoffs. Its path "
      "/info/defaulter/ is robots-disallowed and was not fetched. It proves the "
      "naming barrier in Korea is policy rather than statute."
      ),
    'Thailand': ("2026-08-18",
      "THE NARROW READING IS CONFIRMED AND s.75 IS RULED OUT. Labour Protection "
      "Act B.E. 2541 s.121 bites ONLY on termination by reason of reorganising "
      "work units, production process, distribution or services arising from "
      "the use of machinery, a change in machinery, or changes in TECHNOLOGY — "
      "60 days' written notice to the Labour Inspector and to the affected "
      "employees, stating date, reason and A LIST OF THE AFFECTED EMPLOYEES, "
      "with 60 days' wages in lieu for failure, and NO numeric threshold. "
      "s.75 was checked as the obvious candidate for a general economic duty "
      "and it is NOT one: it covers TEMPORARY SUSPENSION of business (3 working "
      "days' notice to the employee and the Labour Inspector, 75% of wages "
      "during suspension) and the Supreme Court confines it to genuine "
      "temporary necessity. So ordinary economic redundancy in Thailand carries "
      "NO notification to any authority, and the one duty that exists is "
      "technology-scoped — the closest statutory analogue anywhere on earth to "
      "an AI-caused-layoff filing, which is worth knowing for this tracker "
      "specifically. s.121's exact wording is SECONDARY (law-firm briefings); "
      "the Thai official hosts were unreachable. PUBLICATION UNKNOWN: "
      "labour.go.th and legal.labour.go.th answer ECONNREFUSED, and mol.go.th "
      "serves an EMPTY robots.txt (no restriction) but no statistics page was "
      "reached. NEAR-MISSES REJECTED: SSO unemployment-benefit claim counts are "
      "claimants, and s.75 suspension notices are not dismissals."
      ),
    'Vietnam': ("2026-08-18",
      "REGIME ESTABLISHED, PUBLICATION UNKNOWN FOR AN ENVIRONMENT REASON. "
      "Labour Code 45/2019/QH14 art. 42 (obligations on structural, "
      "technological or economic change) and art. 44 (the labour utilisation "
      "plan): 30 days' prior notice to the PROVINCIAL PEOPLE'S COMMITTEE, in "
      "practice received by the provincial So LDTBXH. THERE IS NO NUMERIC "
      "THRESHOLD — art. 42 triggers on affecting 'a large number of employees' "
      "and no 10/20/50 cut-off exists in the Code, which is a real finding "
      "rather than a gap in the reading. Art. 44 read in full: the plan must "
      "list the NAMES and number of employees retained, retrained, moved to "
      "part-time, retiring and terminated. Art. 42(6)'s text layer truncates "
      "mid-sentence in the official English PDF and the two hosts that could "
      "close it were down (vbpl.vn 502, MOLISA's portal on an expired "
      "certificate), so the 30-day wording is secondary-corroborated rather "
      "than primary-read. PUBLICATION: gso.gov.vn and nso.gov.vn were "
      "unreachable (ECONNREFUSED — not refusals). GSO does publish a QUARTERLY "
      "job-loss figure compiled from 'bao cao cua cac dia phuong', and the "
      "classification trap is that this is a labour-force statistic built from "
      "local administrative reports, NOT a count of art. 42 filings; do not "
      "classify Vietnam as publishing an aggregate on it. BEST PER-EMPLOYER "
      "LEAD IN ASIA: HCMC's DoLISA runs a documented intake for art. 42 "
      "notifications and instructs EPZ and industrial-park management boards to "
      "COMPILE LISTS OF THE ENTERPRISES THAT FILED and return them to the "
      "Department. A named-employer list provably exists inside at least one "
      "provincial DoLISA; no public publication was found. Worth a dedicated "
      "look at HCMC, Binh Duong, Dong Nai and Bac Ninh."
      ),
}

# The date is the FIRST element so `min()` over the backlog gives the oldest
# acknowledgement, which ops_status [3d] prints every session.

REGISTER = {

    # -----------------------------------------------------------------------
    # PUBLISHES A COUNTABLE TOTAL — a denominator exists and we may fetch it
    # -----------------------------------------------------------------------

    "United States": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("SEC 8-K Item 2.05 (costs associated with exit or disposal "
                   "activities), Securities Exchange Act s.13/15(d) — a US public "
                   "company recording a material charge for an exit activity files an "
                   "8-K carrying that code in its SGML header. SEPARATELY, state WARN "
                   "acts and the federal WARN Act 29 U.S.C. 2101 compel notice to state "
                   "dislocated-worker units"),
        "authority": "SEC (Item 2.05); state rapid-response / dislocated worker units (WARN)",
        "threshold": ("Item 2.05: any material exit-or-disposal charge, no headcount "
                      "floor. Federal WARN: 100+ employees, 50+ affected at a site"),
        "aggregate": ("MEASURED. EDGAR full-text search enumerates every Item 2.05 filing "
                      "for a period exactly, so the denominator is the universe rather "
                      "than a sample — this is the one slice in the project that supports "
                      "the word RECALL, and railway/rolling_recall.py measures it every "
                      "week. The WARN layer is a SECOND regime in the same country and it "
                      "is NOT measurable: there is no national aggregate at all (US DOL "
                      "keeps no database, BLS Mass Layoff Statistics ended 2013) and "
                      "Wisconsin, which publishes the right figure, disallows AI agents. "
                      "See rolling_recall.assess_state_warn()"),
        "denominator_basis": "closed_enumeration_primary_regulator_index",
        "assessed": "2026-08-18",
        "cite": "https://efts.sec.gov/LATEST/search-index?q=%22Item%202.05%22&forms=8-K",
    },

    "Sweden": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Varsel om driftsinskrankning under lag (1974:13) om vissa "
                   "anstallningsframjande atgarder (framjandelagen) ss.1-2. VERIFIED "
                   "AGAINST PRIMARY TEXT on the riksdag's own site, which is one of the "
                   "few hosts in this whole exercise that names Claude agents in order to "
                   "PERMIT them (crawl-delay 1). s.1: the employer 'skall ... skriftligen "
                   "varsla Arbetsformedlingen, om minst fem arbetstagare berors', and "
                   "likewise where 90 days of cuts will reach twenty. s.2 sets the notice "
                   "period on a sliding scale: 2 months up to 25 workers, 4 months for "
                   "26-100, 6 months above that"),
        "authority": "Arbetsformedlingen",
        "threshold": ("at least 5 workers affected, or 20 within 90 days — read from the "
                      "statute, not recalled. NOTE this is far BELOW the Directive "
                      "98/59/EC floor, so the Swedish count covers a WIDER population "
                      "than Denmark's (at the floor) or Norway's (10), and the three must "
                      "never be summed into a Nordic or European figure"),
        "aggregate": ("PUBLISHED, and the cleanest in the corpus. Monthly count of persons "
                      "affected by varsel, by SNI industry and by county, back to 1992-01, "
                      "as a direct .xlsx, roughly two weeks after month end. Verified live "
                      "on 2026-08-18: HTTP 200, 130,155 bytes, "
                      "openxmlformats spreadsheet. The download URL carries a generated id "
                      "and the county file lagged the industry file by four months when "
                      "checked, so an automated build must read the index page rather than "
                      "template the URL"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": ("https://www.riksdagen.se/sv/dokument-och-lagar/dokument/"
                 "svensk-forfattningssamling/"
                 "lag-197413-om-vissa-anstallningsframjande_sfs-1974-13/"),
        "data_url": ("https://arbetsformedlingen.se/download/18.1d7e68af19f87d573c91d73/"
                     "1786515252048/web-varsel-bransch-199201-2026-07.xlsx"),
    },

    "Norway": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Masseoppsigelse — arbeidsmarkedsloven s.8 (duty to notify NAV) with "
                   "arbeidsmiljoloven s.15-2 (consultation and notification on collective "
                   "redundancy)"),
        "authority": "NAV (Arbeids- og velferdsetaten)",
        "threshold": "at least 10 workers within 30 days",
        "aggregate": ("PUBLISHED. NAV's AG200 monthly .xlsx reports workplaces AND persons "
                      "affected, with masseoppsigelse broken out separately from "
                      "permittering (furlough) — the near-miss that would otherwise "
                      "dominate the series — plus splits by industry, county and cause. "
                      "History only from 2020-03, small cells suppressed, and the "
                      "attachment URL carries a fresh UUID every month so the index page "
                      "must be scraped rather than the URL templated"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": "https://www.nav.no/no/nav-og-samfunn/statistikk/arbeidssokere-og-stillinger-statistikk",
    },

    "Denmark": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Varsling om afskedigelser af storre omfang — lov om varsling m.v. i "
                   "forbindelse med afskedigelser af storre omfang, transposing Directive "
                   "98/59/EC"),
        "authority": "Det Regionale Beskaeftigelsesraad, administered via STAR",
        "threshold": ("10 in an establishment of 20-99; 10% in 100-299; 30 in 300+, "
                      "within 30 days"),
        "aggregate": ("PUBLISHED. Monthly count of persons AND companies varslet, by "
                      "region, municipality and DB07 industry, back to 2007-01, released "
                      "on the 7th business day. CONSTRAINT, stated rather than smoothed "
                      "over: the figure is readable without a credential only as HTML or "
                      "a PowerBI export; api.jobindsats.dk answers 401 'Missing bearer "
                      "token'. So an unattended pipeline would need either a credential we "
                      "do not have or a materially more brittle scrape than Sweden's plain "
                      ".xlsx"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": ("https://www.jobindsats.dk/databank/arbejdsmarked/status-pa-arbejdsmarkedet/"
                 "virksomhedernes-behov-for-arbejdskraft/antal-varslinger-om-afskedigelser/"),
    },

    "Spain": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Despido colectivo — art. 51 Estatuto de los Trabajadores with RD "
                   "1483/2012; the statistical return itself is mandated by Orden "
                   "ESS/2541/2012"),
        "authority": ("the labour authority of the autonomous community, or the Ministry's "
                      "Direccion General de Trabajo where the firm spans more than one"),
        "threshold": ("banded over 90 days: 10 in a firm under 100; 10% in 100-300; 30 in "
                      "300+; or the whole workforce where more than 5 and the firm closes"),
        "aggregate": ("PUBLISHED, and the best-shaped source found anywhere in this corpus. "
                      "Monthly XLSX and PDF on fixed calendar months with a stable URL "
                      "pattern, giving empresas, procedimientos and trabajadores afectados "
                      "split by CNAE sector, cause, firm size, sex and province. Roughly a "
                      "two-month lag; monthly figures are provisional until the annual "
                      "consolidation. Critically it SEPARATES despido colectivo from "
                      "suspension de contrato / reduccion de jornada (ERTE) and isolates "
                      "the Mecanismo RED — both short-time work and both fatal near-misses "
                      "if folded in. Verified live on 2026-08-18: HTTP "
                      "200, 484,927 bytes, openxmlformats spreadsheet"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": "https://www.mites.gob.es/estadisticas/reg/reg26may/reg_05_2026.xlsx",
        "per_employer_register": ("SEPARATELY, AND MORE VALUABLE THAN THE TOTAL: one of "
                                  "the 17 autonomous communities publishes the "
                                  "underlying notices WITH THE EMPLOYER NAMED. See "
                                  "PER_EMPLOYER_REGISTERS — Illes Balears, verified "
                                  "2026-08-19, and Euskadi publishing the same rows with "
                                  "the CIF masked. Only Balears names, of the 11 "
                                  "communities that publish an ERE/ERTE dataset at all"),
    },

    "Portugal": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": "Despedimento coletivo — Codigo do Trabalho art. 359.o and following",
        "authority": "DGERT (Direcao-Geral do Emprego e das Relacoes de Trabalho)",
        "threshold": ("2 workers in a firm under 50, or 5 in a firm of 50+, within 3 "
                      "months"),
        "aggregate": ("PUBLISHED. Monthly, quarterly and annual reports carrying BOTH "
                      "procedures and workers, back to 2012, roughly a one to two month "
                      "lag, with near-templatable filenames of the form "
                      "Relatorio-Despedimento-Coletivo-YYYY.MM.pdf. PDF only — there is no "
                      "CSV, XLSX or API, so building on it would mean adding a PDF "
                      "dependency to a hash-pinned lock for one country"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": "https://www.dgert.gov.pt/despedimento-coletivo",
    },

    "Belgium": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Licenciement collectif — CCT n.24 of 2 Oct 1975 art. 2 with the AR of "
                   "24 May 1976 (filing plus a 30-day standstill), and the loi du 13 "
                   "fevrier 1998 ('loi Renault') ch. VII artt. 62-70 for the procedural "
                   "and sanction layer"),
        "authority": ("the directeur of the subregional employment service (VDAB / FOREM / "
                      "Actiris) and the President of the SPF Emploi management committee. "
                      "ONEM/RVA does NOT receive the notification; its role is downstream "
                      "benefit administration"),
        "threshold": ("reported as: in establishments of 20+, over 60 days, 10 dismissals "
                      "at 20-99 employees; 10% at 100-299; 30 at 300+. UNVERIFIED against "
                      "CCT n.24 primary text in this pass — recorded as recollection, not "
                      "as a finding. The PUBLISHED FIGURES, by contrast, were read out of "
                      "the PDF itself and do reconcile"),
        "aggregate": ("PUBLISHED, and derived directly from the notifications: firms "
                      "announcing intent, firms notifying a project, and workers affected, "
                      "by month, region, province and sector, back to 2009. PDF only, no "
                      "CSV/XLSX/API, released quarterly as a cumulative year-to-date file "
                      "with per-month detail inside, roughly 6-7 weeks after period end. "
                      "Verified live on 2026-08-18: HTTP 200, 646,655 "
                      "bytes, application/pdf. NEAR-MISS to exclude: 'entreprises en "
                      "restructuration reconnues' is a benefit-eligibility recognition "
                      "covering firms too small for CCT 24, a different population"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": ("https://emploi.belgique.be/fr/themes/restructuration/licenciement-collectif/"
                 "statistiques-relatives-aux-restructurations"),
    },

    "Croatia": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Kolektivno zbrinjavanje viska radnika — Zakon o radu, transposing "
                   "Directive 98/59/EC"),
        "authority": "Hrvatski zavod za zaposljavanje (HZZ)",
        "threshold": "20 or more workers within 90 days",
        "aggregate": ("PUBLISHED but ANNUAL and PDF only, which is too coarse to serve as a "
                      "denominator for a tracker reporting monthly. Recorded here as a "
                      "published total because it is one; it is not a build candidate"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": "https://www.hzz.hr/statistika/",
    },

    # --- closed 2026-08-19 out of the module's own outstanding work. Six of the
    # seven below were ALREADY ESTABLISHED inside railway/national_denominators.py
    # — that module went and looked at the series while this register still
    # carried the country as unresearched backlog. Two files disagreeing about
    # the same country is the defect this closes; the evidence was never
    # missing, it was only in the other file.

    "Estonia": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Kollektiivne ulesutlemine — Toolepingu seadus (Employment Contracts "
                   "Act) ss.89-90 with the notification duty at s.101-102, transposing "
                   "Directive 98/59/EC. THE STATUTE ITSELF WAS NOT READ: "
                   "riigiteataja.ee renders its acts client-side and served only its "
                   "'Laeb...' loading shell to a plain fetch, so the text below comes "
                   "from Tootukassa — the authority that RECEIVES the notification, "
                   "describing its own duty — and is recorded as that rather than as a "
                   "read of the Act"),
        "authority": "Eesti Tootukassa (Unemployment Insurance Fund)",
        "threshold": ("within 30 calendar days: 5 workers where the employer averages up "
                      "to 19 employees; 10 where 20-99; 10% where 100-299; 30 where 300+. "
                      "NOTE the 5-worker floor, which like Sweden's sits BELOW the "
                      "Directive minimum, so the Estonian count covers a wider population "
                      "than Croatia's at 20 and the two must never be summed"),
        "aggregate": ("PUBLISHED, and already being read: avaandmed.eesti.ee carries "
                      "koondamisteated (recipients of collective redundancy notices) as "
                      "an open dataset, monthly, by county, and "
                      "railway/national_denominators.py's estonia_series() has been "
                      "collecting it since 2026-08-18. Licence CC BY-NC 3.0, so it "
                      "MEASURES and is never republished to a reader-facing surface. The "
                      "series is revised back to the start of the previous calendar year "
                      "at every release"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": "https://www.tootukassa.ee/et/teenused/tooandjatele/kollektiivne-koondamine",
        "data_url": ("https://avaandmed.eesti.ee/api/datasets?search=koondamised&limit=10"),
    },

    "Latvia": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Kolektiva atlaisana — Darba likums s.105 (definition) with s.107 "
                   "(notification to the State Employment Agency), transposing Directive "
                   "98/59/EC. Read from NVA's own English service page, the authority "
                   "that receives the notice; likumi.lv serves the whole Labour Law as "
                   "one document that truncated before s.105 on fetch, so the primary "
                   "text was NOT read end to end"),
        "authority": "Nodarbinatibas valsts agentura (NVA, State Employment Agency)",
        "threshold": ("within 30 days: at least 5 workers where the employer normally "
                      "employs more than 20 and fewer than 50; at least 10 where more "
                      "than 50 and fewer than 100; at least 10% where 100-299; at least "
                      "30 where 300+. s.107(1): collective redundancy may not begin "
                      "earlier than 30 days after the notification is filed"),
        "aggregate": ("PUBLISHED. NVA reports the count of employer notifications and the "
                      "workers covered — 42 notifications covering 2,279 workers in 2024; "
                      "79 in 2020, 40 in 2019, 32 in 2018 and 32 in 2021 — through its "
                      "own news and annual labour-market reporting. NOT BUILDABLE as a "
                      "series: railway/national_denominators.py records it as prose "
                      "inside an annual PDF roughly six months behind, which would cost a "
                      "PDF dependency in a hash-pinned lock for one country and parse "
                      "brittle prose to boot. Published is not the same as buildable and "
                      "this register records the first"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": "https://www.nva.gov.lv/en/services-case-collective-redundancies",
    },

    "Poland": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Zwolnienia grupowe — ustawa z 13 marca 2003 r. o szczegolnych zasadach "
                   "rozwiazywania z pracownikami stosunkow pracy z przyczyn niedotyczacych "
                   "pracownikow, transposing Directive 98/59/EC; notification runs to the "
                   "powiatowy urzad pracy. STATUTE NOT READ HERE — the register carried "
                   "Poland as EU-therefore-a-regime-exists and this pass closed the "
                   "PUBLICATION question only"),
        "authority": "powiatowy urzad pracy (district labour office); GUS compiles the count",
        "threshold": ("banded, within 30 days, in employers of 20+: 10 workers where "
                      "under 100 employed; 10% where 100-299; 30 where 300+. Recorded as "
                      "the Directive-standard banding the Act transposes, NOT as a read "
                      "of the Polish text"),
        "aggregate": ("PUBLISHED, and verified live on 2026-08-19 rather than inferred: "
                      "GUS's Sytuacja spoleczno-gospodarcza kraju labour-market bulletin "
                      "carries the count of establishments that notified an intent to "
                      "dismiss and the workers covered — 'W koncu czerwca br. 198 zakladow "
                      "zglosilo zamiar zwolnienia 20,7 tys. pracownikow (w tym 2,5 tys. "
                      "osob z sektora publicznego) w ramach zwolnien grupowych'. "
                      "railway/national_denominators.py holds it NOT BUILDABLE because "
                      "the figures are Polish prose rounded to 0,1 tys. and the page "
                      "carries the current period, so a history would be OUR accumulation "
                      "and not the publisher's. NOTE FOR WHOEVER REVISITS: the page as "
                      "fetched on 2026-08-19 also carried comparison tables reaching back "
                      "to June 2024. That is a lead, not a correction — nobody has "
                      "established that those tables carry the group-layoff line rather "
                      "than the unemployment series around it"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": "https://ssgk.stat.gov.pl/Rynek_pracy.html",
        "caveat_partial_refusal": ("psz.praca.gov.pl names ClaudeBot and disallows "
                                   "everything, and is never fetched. stat.gov.pl is "
                                   "'User-agent: * / Allow: /*' and ssgk.stat.gov.pl "
                                   "serves no robots.txt at all"),
    },

    "Iceland": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Hopuppsagnir — log nr. 63/2000 um hopuppsagnir (as amended by log nr. "
                   "51/2019), transposing Directive 98/59/EC through the EEA agreement. "
                   "THE ACT WAS NOT READ AND CANNOT BE FROM HERE: www.althingi.is, which "
                   "publishes the consolidated text, names ClaudeBot with 'Disallow: /'. "
                   "The thresholds below come from Vinnumalastofnun's own service page "
                   "and the ASI/SA labour-law references, and are recorded as secondary"),
        "authority": "Vinnumalastofnun (Directorate of Labour)",
        "threshold": ("within 30 days: at least 10 workers where the employer normally "
                      "has more than 20 and fewer than 100; 10% where 100-299; 30 where "
                      "300+. Dismissals take effect no earlier than 30 days after the "
                      "notification reaches Vinnumalastofnun"),
        "aggregate": ("PUBLISHED, monthly, as a news post 1-3 days after month end. "
                      "railway/national_denominators.py holds it NOT BUILDABLE, and ONE "
                      "LEG OF THAT REASONING IS NOW WRONG AND IS CORRECTED HERE: it "
                      "states that a month with no collective redundancies gets no post "
                      "at all, so absence could never be told from zero. Verified on "
                      "2026-08-19, the post 'Hopuppsagnir i juli 2026' exists and says "
                      "'Engin tilkynning um hopuppsogn barst Vinnumalastofnun i juli' — "
                      "a zero month IS posted. The other leg stands and is enough on its "
                      "own: the figure is unarchived prose in a news feed, so a series "
                      "would be our accumulation rather than the publisher's. Corrected "
                      "rather than quietly fixed, per RUNBOOK"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": "https://island.is/s/vinnumalastofnun/frett/hopuppsagnir-i-juli-2026",
    },

    "Romania": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Concediere colectiva — Codul muncii (Legea 53/2003) art. 68 "
                   "(definition), art. 69-70 (information and consultation) and art. 72 "
                   "(written notification to the territorial labour inspectorate and the "
                   "territorial employment agency at least 30 calendar days before the "
                   "dismissal decisions), transposing Directive 98/59/EC. PRIMARY TEXT "
                   "NOT READ, and the reason is recorded because all three routes failed "
                   "for different reasons: codulmuncii.ro names ClaudeBot with "
                   "'Disallow: /', lege5.ro ends with 'User-agent: * / Disallow: /' "
                   "excepting search engines, and legislatie.just.ro hangs up the socket "
                   "on every request (an environment block, not a refusal)"),
        "authority": ("Inspectoratul Teritorial de Munca (ITM) and the Agentia Judeteana "
                      "pentru Ocuparea Fortei de Munca, under ANOFM"),
        "threshold": ("within 30 days, in employers of 20+: at least 10 workers where "
                      "under 100 employed; at least 10% where 100-299; at least 30 where "
                      "300+. REPORTED, from secondary summaries of art. 68 — see the "
                      "regime field for why no permitted primary source could be read"),
        "aggregate": ("PUBLISHED, and read directly out of the source on 2026-08-19 "
                      "rather than taken from a search summary: ANOFM's Raport de "
                      "activitate pentru anul 2024 reports collective dismissals "
                      "ESTIMATED by employers at 16,007 persons for 2024 against 9,600 "
                      "actually dismissed (59.97% of the estimate), and states the "
                      "comparison runs over 2009-2024. THE GAP BETWEEN THE TWO NUMBERS IS "
                      "THE POINT: a notified intention is not a dismissal, and Romania "
                      "publishes both, which most countries do not. "
                      "railway/national_denominators.py holds it NOT BUILDABLE — annual, "
                      "PDF only, and the month-by-month detail sits inside the report, so "
                      "it would cost a PDF dependency in a hash-pinned lock for one "
                      "country"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": ("https://www.anofm.ro/wp-content/uploads/2025/05/"
                 "Raport-de-activitate-al-ANOFM-pentru-anul-2024.pdf"),
    },

    "Netherlands": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Wet melding collectief ontslag (WMCO) — notification to UWV before a "
                   "collective dismissal for business-economic reasons. THE ACT WAS NOT "
                   "READ: wetten.overheid.nl, which publishes it, carries an explicit "
                   "'AI / LLM crawlers' block naming ClaudeBot, Claude-Web and "
                   "anthropic-ai with 'Disallow: /'. What is recorded below is UWV's own "
                   "statement of the duty on a permitted page — the receiving authority "
                   "describing what it receives"),
        "authority": ("UWV, plus the trade unions with members in the firm and the works "
                      "council. UWV is the one that counts"),
        "threshold": ("20 or more proposed dismissals within one of UWV's six werkgebieden "
                      "(Friesland/Groningen/Drenthe, Overijssel/Gelderland, "
                      "Noord-Brabant/Limburg, Zuid-Holland/Zeeland, Flevoland/Utrecht, "
                      "Noord-Holland). The three-month window usually quoted alongside it "
                      "is from secondary sources and is NOT verified here"),
        "aggregate": ("PUBLISHED ANNUALLY AS PROSE, and this OVERTURNS the register's "
                      "previous position that the Netherlands was blocked outright. UWV's "
                      "own press release — on uwv.nl/nl/persberichten, which its "
                      "robots.txt permits — states '355 bedrijven deden een melding, het "
                      "hoogste aantal in 10 jaar', 42% more notifications than 2024, "
                      "'bijna 25.000 werknemers' and 36% more workers. Verified on "
                      "2026-08-19. What IS refused is the SERIES, not the figure: UWV's "
                      "robots.txt disallows exactly one path, /nl/webpublicaties, which is "
                      "where a WMCO series would live, and the current reports on "
                      "cao.minszw.nl sit behind an Anubis proof-of-work interstitial. So "
                      "the Netherlands publishes a countable total that we may read and "
                      "may not automate — recorded as published, with the block named"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": ("https://www.uwv.nl/nl/persberichten/"
                 "aantal-ww-uitkeringen-voor-het-derde-jaar-gestegen-forse-toename-"
                 "reorganisaties"),
        "caveat_partial_refusal": ("uwv.nl robots.txt: 'User-agent: * / Disallow: "
                                   "/nl/webpublicaties' — one path, and the one a series "
                                   "would live on. cao.minszw.nl serves an Anubis "
                                   "proof-of-work wall. wetten.overheid.nl names ClaudeBot. "
                                   "The press-release path and /nl/ontslag are permitted "
                                   "and are where both facts above came from"),
    },

    "Taiwan": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Da liang jie gu — Act for Worker Protection of Mass Dismissal "
                   "(大量解僱勞工保護法) art. 2 (what counts) and art. 4 (the 解僱計畫書 "
                   "dismissal plan, filed with the competent authority and publicly "
                   "announced 60 days ahead, waived for natural disaster or sudden "
                   "event). Read on 2026-08-19 from laws.mol.gov.tw, the labour "
                   "ministry's own law database, which is permitted ('User-agent: * / "
                   "Disallow: /results.aspx'). law.moj.gov.tw is blanket-disallowed and "
                   "was not used"),
        "authority": ("the local competent labour authority (municipality or county), "
                      "under 勞動部 (Ministry of Labor)"),
        "threshold": ("art. 2, size-banded over 60 days: workplace under 30 employees, "
                      "more than 10 dismissed; 30-199, more than one third or more than "
                      "20 in a single day; 200-499, more than one quarter or more than 50 "
                      "in a day; 500+, more than one fifth or more than 80 in a day; or "
                      "the business unit dismisses more than 200 in 60 days or more than "
                      "100 in a single day"),
        "aggregate": ("PUBLISHED, and being read. THIS CLOSES A DISAGREEMENT rather than "
                      "adding a finding: one earlier sweep reported an open dataset back "
                      "to 2005, a second could not reach the dataset layer at all and "
                      "verified that 大量解僱 appears zero times in the TOCs of both MOL "
                      "flagship publications. BOTH were right — the series is not in the "
                      "printed statistical yearbooks and IS on the open-data API. "
                      "railway/national_denominators.py's taiwan_series() has been "
                      "reading apiservice.mol.gov.tw under the Open Government Data "
                      "License since 2026-08-18. COUNTING UNIT TRAP, kept: 家數 counts "
                      "廠場 (plants), so one company filing for four sites counts four "
                      "times, and that column is NOT an employer count. Annual, ROC "
                      "years, roughly a six-month lag"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": "https://laws.mol.gov.tw/FLAW/FLAWDAT0202.aspx?id=FL023225",
        "data_url": ("https://apiservice.mol.gov.tw/OdService/rest/datastore/"
                     "A17000000J-020115-aUA"),
    },

    "Bulgaria": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Masovi uvolneniya — Kodeks na truda chl. 130a, the duty to inform the "
                   "employment authority of projected collective dismissals, transposing "
                   "Directive 98/59/EC"),
        "authority": "Agenciya po zaetostta (Employment Agency)",
        "threshold": ("the Directive banding as transposed in chl. 328a / chl. 130a — "
                      "recorded as transposition, NOT as a read of the Bulgarian text, "
                      "which was not obtained"),
        "aggregate": ("PUBLISHED, and read verbatim out of a bulletin rather than "
                      "summarised: the Employment Agency's Periodichni byuletini carry "
                      "EMPLOYERS FILING and WORKERS COVERED — '68 rabotodateli sa podali "
                      "uvedomleniya za masovi uvolneniya na 5336 litsa' for January-June "
                      "2011, with a May 2011 peak of 18 employers / 2,097 workers. "
                      "Quarterly cumulative (Jan-Mar / Jan-Jun / Jan-Sep) plus monthly "
                      "bulletins and annual reviews, 2008 through 2026, one to two months "
                      "behind. Sector breakdown only — no employer names. THE READABLE "
                      "PART IS THE OLD PART: bulletins up to roughly 2012 render inline "
                      "as HTML and were read; recent ones are file-link pages whose PDFs "
                      "sit under /web/, which robots disallows"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": "https://www.az.government.bg/bg/stats/3/",
        "caveat_partial_refusal": ("az.government.bg robots.txt disallows /web/, and every "
                                   "current bulletin PDF lives at /web/files/StatsFile/. "
                                   "Not fetched. The permitted /bg/stats/view/ wrapper "
                                   "carries period labels and a file inventory — enough to "
                                   "detect that a new bulletin exists, never the numbers "
                                   "in it. nsi.bg disallows only /admin/ and is the best "
                                   "untried route to the same figures"),
    },

    "Slovakia": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Hromadne prepustanie — Zakonnik prace (311/2001 Z. z.) s.73, with "
                   "s.73(3) the notification duty, transposing Directive 98/59/EC"),
        "authority": "Urad prace, socialnych veci a rodiny (UPSVR)",
        "threshold": ("the Directive banding as transposed in s.73 — recorded as "
                      "transposition, NOT as a read of the Slovak text"),
        "aggregate": ("PUBLISHED, IN A WEAK FORM, and the weakness is the finding. "
                      "Ustredie PSVR reports THREE units in its own media releases — "
                      "notifications filed, jobs THREATENED, and workers ACTUALLY "
                      "dismissed (1 Jan-15 May 2024: 36 / 3,596 / 2,766; same window "
                      "2025: 22 / 2,635). Holding the threatened and the realised figure "
                      "apart is unusual and valuable — most countries publish only the "
                      "first. But the cadence is irregular, the form is HTML prose with "
                      "no table, and there is no dataset and no archive series, so it is "
                      "published without being buildable. CHECKED AND NEGATIVE, so nobody "
                      "re-searches: the full UPSVR statistics index (11 sections), the "
                      "open-data endpoints (jobseekers and vacancies only, 2019-2026), "
                      "datasety.html (404), and the annual vykazy V05/V10/V11/V13, which "
                      "are social-services and child-protection forms. The working "
                      "hypothesis that UPSVR publishes a named collective-redundancy "
                      "statistic is NOT supported. data.slovensko.sk rendered as an empty "
                      "SPA shell and is UNKNOWN rather than negative"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": "https://www.upsvr.gov.sk/statistiky.html?page_id=1247",
    },

    "Uruguay": {
        "class": NO_REGIME,
        "regime": ("NO mass-dismissal disclosure regime exists, and this is the SECOND "
                   "country in the register where that has been established rather than "
                   "assumed. MTSS's own statement of Uruguayan dismissal law — 'despido "
                   "regimen comun' on gub.uy, the ministry's institutional pages — sets "
                   "out the whole regime as indemnity-only, differentiated between "
                   "mensuales, jornaleros and destajistas, and contains NO duty to notify "
                   "the ministry or any authority, before or after, individually or "
                   "collectively, and NO collective threshold or procedure of any kind. "
                   "THE DECISIVE CORROBORATION IS LEGISLATIVE: MTSS is currently "
                   "promoting a BILL to create exactly this duty — advance notification "
                   "to the State and to unions before mass dismissals and closures. A "
                   "government drafting a law to impose a duty is direct evidence the "
                   "duty does not yet exist. WATCH ITEM: if that bill passes, Uruguay "
                   "flips to REGIME_NO_AGGREGATE or better, and this entry expires "
                   "within 183 days anyway. REJECTED as a near-miss: the only ministry "
                   "notification found anywhere in the material is judges reporting their "
                   "own judgments to MTSS under Ley 16.713 art. 91, which is unrelated"),
        "authority": None,
        "threshold": None,
        "aggregate": ("NONE, and nothing exists for one to be derived from. NEAR-MISS "
                      "excluded with its shape stated: BPS subsidio por desempleo is a "
                      "WORKER BENEFIT CLAIM count — no employer identity, no collective "
                      "event, no threshold — and MTSS's open data covers employment "
                      "promotion contracts, not dismissals. NOTE for whoever revisits: "
                      "catalogodatos.gub.uy disallows /api/, so use the permitted HTML "
                      "path"),
        "denominator_basis": None,
        "assessed": "2026-08-19",
        "cite": ("https://www.gub.uy/ministerio-trabajo-seguridad-social/institucional/"
                 "derecho-laboral-uruguayo/despido-regimen-comun"),
    },

    # -----------------------------------------------------------------------
    # A REGIME EXISTS AND NOTHING COUNTABLE IS PUBLISHED
    # -----------------------------------------------------------------------

    "Japan": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("TWO instruments under the Act on Comprehensively Advancing Labour "
                   "Measures (労働施策総合推進法, formerly the Employment Measures Act). "
                   "Art. 27, 大量雇用変動の届出 / 大量離職届: where 30 or more workers "
                   "separate from one establishment within a month for reasons not "
                   "attributable to themselves, the employer notifies the head of the "
                   "Public Employment Security Office (Hello Work), by one month before "
                   "the last separation; public bodies file a 大量離職通知書 instead. "
                   "Art. 24, 再就職援助計画: where the same 30-in-a-month arises from "
                   "downsizing, a re-employment assistance plan is submitted to Hello "
                   "Work and certified at least one month before the first separation. "
                   "Both article numbers come from MHLW's own page; the consolidated text "
                   "on laws.e-gov.go.jp is a JavaScript application that serves no law "
                   "body to a fetcher, so e-Gov confirmation is UNKNOWN and the ministry "
                   "page is what carries this"),
        "authority": "公共職業安定所長 (the head of the Hello Work office), under MHLW",
        "threshold": "30 or more separations from one establishment within one month",
        "aggregate": ("NONE TODAY — and this is a 'had a count and lost it', which is a "
                      "different fact from Germany's 'never had one' and is recorded as "
                      "such. MHLW ran a MONTHLY national release carrying establishments "
                      "filing and workers separating: April 2011, 184 establishments / "
                      "8,811 workers; June 2012, 103 / 6,813; September 2012, 175 / "
                      "13,425. The series runs roughly 2009 to late 2012, no instance "
                      "from 2013 or later was found, and the 2012 pages now return 404 — "
                      "it is retired and being deleted. e-Stat was queried directly and "
                      "returns ZERO results for 大量雇用変動, so the figure is not inside "
                      "職業安定業務統計 either, and the 労働市場年報 that might have "
                      "carried it was abolished after FY2018. Whether MHLW still compiles "
                      "the count internally and simply does not publish it is UNKNOWN. "
                      "NEAR-MISSES REJECTED, each named: 雇用調整助成金 subsidises "
                      "RETAINING workers through short-time work, so counting it inverts "
                      "the sign; 労働経済動向調査 and 雇用動向調査 are employer SURVEYS; "
                      "雇用保険事業年報 counts all separations from all causes; and the "
                      "COVID-era 雇用への影響 series (weekly from 2020 to early 2023) was "
                      "a labour-bureau soft count of EXPECTED dismissals gathered by "
                      "interview, not the art. 27 register"),
        "assessed": "2026-08-19",
        "cite": ("https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/koyou/"
                 "kyufukin/other36/index.html"),
    },

    "United Kingdom": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("TWO regimes, because the UK has two statutes and two publishers. GREAT "
                   "BRITAIN: advance notification of redundancies on form HR1, Trade Union "
                   "and Labour Relations (Consolidation) Act 1992 s.193. NORTHERN IRELAND: "
                   "the Employment Rights (Northern Ireland) Order 1996 as amended 2006 — "
                   "NOT TULRCA, which does not extend there. A parallel sweep attributed "
                   "the GB series to ONS; that is WRONG and the correction matters, "
                   "because the ONS Labour Force Survey redundancy rate is a SURVEY "
                   "ESTIMATE and the classic near-miss here"),
        "authority": ("GB: the Insolvency Service (Redundancy Payments Service) on behalf "
                      "of the Secretary of State. NI: NISRA collects on behalf of the "
                      "Department for the Economy"),
        "threshold": "20 or more proposed dismissals at one establishment within 90 days",
        "aggregate": ("PUBLISHED IN BOTH, and this overturns the working hypothesis that UK "
                      "HR1 counts surface only through FOI. GB: a monthly management-"
                      "information table, unbroken from 2020-01, giving HR1 forms received, "
                      "total potential redundancies AND unique employers submitting. "
                      "VERIFIED DIRECTLY on 2026-08-18: HTTP 200, 80 table rows, "
                      "2020-01 (368 forms / 29,496 potential) through 2026-07 (350 / "
                      "22,280 / 319 employers). Roughly a one-month lag. THREE CAVEATS "
                      "THAT CHANGE HOW IT MAY BE USED: it is explicitly NOT Official "
                      "Statistics and is revisable; it is HTML only with no CSV or XLSX "
                      "attachment; and it is dated by MONTH OF RECEIPT, not the month "
                      "redundancies are proposed, so it runs on a different clock from "
                      "anything we date by event. NI: monthly proposed AND confirmed "
                      "redundancies with an industry split, inside the NISRA Labour Market "
                      "Report — the extra dimension GB lacks. Together they give near "
                      "complete UK coverage from a statutory notification base"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": ("https://www.gov.uk/government/publications/"
                 "publication-of-data-on-advanced-notification-of-redundancy-scheme/"
                 "management-information-on-advanced-notification-of-redundancy-scheme"),
        "caveat_partial_refusal": ("the NI workbook is robots-disallowed: nisra.gov.uk and "
                                   "economy-ni.gov.uk both carry 'Disallow: /*.xlsx' under "
                                   "'User-agent: *'. The HTML gateway pages ARE permitted "
                                   "and carry the same figures, so NI needs a deliberate "
                                   "ingestion decision rather than a fetch. economy-ni "
                                   "throttles rather than blocks AI agents "
                                   "('User-agent: ClaudeBot / Crawl-delay: 5')"),
    },

    'Chile': {
        "class": REGIME_WITH_AGGREGATE,
        "regime": (
                   "NO collective-dismissal regime exists — and the denominator exists "
                   "anyway, which is why this entry is worth reading twice. Codigo del "
                   "Trabajo art. 162 inc. 4 requires a copy of EVERY termination notice "
                   "to go to the Inspeccion del Trabajo, and art. 162 requires the "
                   "Inspecciones to keep a register of them. Art. 161 inc. 1 "
                   "('necesidades de la empresa') is the economic-redundancy ground. So "
                   "Chile publishes a usable figure through an individual-notice duty "
                   "rather than a collective one"),
        "authority": (
                   "Inspeccion del Trabajo / Direccion del Trabajo"),
        "threshold": (
                   "none — the duty attaches to every termination notice, not to a mass "
                   "threshold"),
        "aggregate": (
                   "PUBLISHED. 'Trabajadores involucrados con un unico empleador "
                   "registrado en cartas de aviso de termino de contrato', monthly PDF "
                   "back to 2020-01, roughly a two-month lag, broken out by causal "
                   "(including art. 161 inc. 1), sector, firm size and region. THREE "
                   "LIMITS THAT MUST TRAVEL WITH IT: it is WORKER-level, not event-level "
                   "— no employer grouping and no threshold, so it can never be matched "
                   "against our rows as events; it is dated by month of REGISTRATION, "
                   "not effective termination; and the Direccion del Trabajo itself "
                   "warns a registered notice may not result in an actual termination. "
                   "Describe it as an economic-dismissal WORKER denominator, never as "
                   "layoff events"),
        "denominator_basis": (
                   "national_notification_aggregate"),
        "cite": (
                   "https://www.dt.gob.cl/portal/1629/w3-propertyvalue-188840.html"),
        "assessed": "2026-08-18",
    },
    'Brazil': {
        "class": NO_REGIME,
        "regime": (
                   "NO mass-dismissal disclosure regime exists, and this is the first "
                   "and so far ONLY country in the register where that has been "
                   "established rather than assumed. CLT art. 477-A stands, and the "
                   "STF's mass-dismissal precedent — RE 999.435 / Tema 638, decided June "
                   "2022 and modulated prospectively to 2022-06-14 — requires prior "
                   "UNION negotiation, running to the union and NOT to the State. There "
                   "is no notification duty to the Ministerio do Trabalho at all. TWO "
                   "CORRECTIONS recorded because both would have been visible errors: "
                   "the precedent is Tema 638, NOT ADI 6363 (which concerned MP 936/2020 "
                   "furloughs), and 'prior union negotiation' is not a disclosure regime"),
        "authority": None,
        "threshold": None,
        "aggregate": (
                   "NONE, and there is nothing for one to be derived from. NEAR-MISS, "
                   "excluded with its magnitude stated: Novo CAGED is monthly at roughly "
                   "a 1.5-month lag and counts EVERY separation — quits, deaths, "
                   "retirements, end-of-term — as individual contract events with no "
                   "collective flag, no employer grouping and no threshold. Using it as "
                   "a layoff denominator would overstate by roughly two orders of "
                   "magnitude"),
        "cite": (
                   ""
                   "https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num=638"),
        "assessed": "2026-08-18",
    },
    "South Africa": {
        "class": REGIME_WITH_AGGREGATE,
        "regime": ("Labour Relations Act 66 of 1995 s.189 and s.189A — operational "
                   "requirements dismissals, with s.189A adding a CCMA facilitation route "
                   "for larger employers"),
        "authority": ("no ex-ante filing to a ministry: the CCMA (Commission for "
                      "Conciliation, Mediation and Arbitration) receives s.189A referrals "
                      "and is what makes the population countable"),
        "threshold": ("employers of more than 50 employees, banded by workforce size: 10 "
                      "dismissals up to 200 staff, rising to 50 at 501+"),
        "aggregate": ("PUBLISHED, AND ONE YEAR IS NOW VERIFIED FROM A PERMITTED SOURCE, "
                      "which is what this entry was waiting for. The Deputy Minister of "
                      "Employment and Labour's Budget Vote speech of 2025-07-03, on "
                      "gov.za: 'the CCMA facilitated the saving of 30 581 jobs out of "
                      "64 919 facing retrenchment' for FY2024/25 (April-March). A 2015 "
                      "CCMA statement on the same host gives 103,949 jobs saved over "
                      "2010-2015, so the series runs back at least that far. TWO "
                      "CORRECTIONS TO THE EARLIER ASSESSMENT: the lag is roughly THREE "
                      "months, not six or seven — the Budget Vote speech on gov.za is the "
                      "fastest permitted route to each year's figure and beats the annual "
                      "report — and the figures no longer rest on search-result "
                      "summaries. THE LIMIT THAT MUST TRAVEL WITH IT: the unit is "
                      "employees in s.189A matters REFERRED TO THE CCMA, not all South "
                      "African retrenchments and not all s.189 processes. Facilitation is "
                      "compulsory only on request, so an unknown share never enters the "
                      "denominator. It is a FLOOR. FY2023/24 (38,428 facing / 14,887 "
                      "saved) is still UNVERIFIED — ccma.org.za is WAF-403 and the "
                      "nationalgovernment.co.za mirror returns 403 on its own robots.txt, "
                      "so permission could not even be established"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-19",
        "cite": ("https://www.gov.za/news/speeches/deputy-minister-jomo-sibiya-employment-"
                 "and-labour-dept-budget-vote-202526-03-jul-2025"),
        "caveat_partial_refusal": ("ccma.org.za (the publisher) is WAF-403, saflii.org "
                                   "names ClaudeBot and disallows it, and pmg.org.za — "
                                   "the parliamentary monitoring archive, the obvious "
                                   "route to committee presentations of these figures — "
                                   "names ClaudeBot with 'Disallow: /' TWICE. gov.za and "
                                   "labour.gov.za are open and are the permitted route"),
    },

    "Nigeria": {
        "class": NO_REGIME,
        "regime": ("NO disclosure duty to any public authority exists, and this CORRECTS "
                   "the register's own earlier note, which said s.20 involved the "
                   "Ministry. Labour Act Cap L1 LFN 2004 s.20 was read verbatim: on "
                   "redundancy the employer shall inform THE TRADE UNION OR WORKERS' "
                   "REPRESENTATIVE of the reasons and extent, apply last-in-first-out "
                   "subject to merit, and use best endeavours to negotiate redundancy "
                   "payments. The Minister appears in s.20(2) ONLY as a regulation-making "
                   "power. There is no filing, no form, no authority and NO THRESHOLD OF "
                   "ANY KIND. The information duty is real but private, running to the "
                   "union where workers are represented — worth stating, because 'no "
                   "regime' here means no PUBLIC disclosure, not no obligation. Read on a "
                   "secondary host: the Federal Ministry's own copy at nelex.gov.ng is "
                   "robots-permitted but a scanned image with no text layer"),
        "authority": None,
        "threshold": None,
        "aggregate": ("NONE, and there is no notification stream for one to be derived "
                      "from. THE SUB-NATIONAL QUESTION IS CLOSED RATHER THAN UNSAMPLED, "
                      "which is rare and worth the words: labour is item 34 of the "
                      "EXCLUSIVE Legislative List, Second Schedule Part I of the 1999 "
                      "Constitution, and under s.4(2)-(3) the National Assembly legislates "
                      "on Exclusive List items to the exclusion of the State Houses of "
                      "Assembly. No Nigerian state CAN create a WARN-style duty, so the "
                      "36 states and the FCT need not be swept. NEAR-MISS REJECTED: the "
                      "NBS Nigeria Labour Force Survey is a household survey"),
        "denominator_basis": None,
        "assessed": "2026-08-19",
        "cite": "https://jurist.ng/labour_act/sec-20",
    },

    "Kuwait": {
        "class": NO_REGIME,
        "regime": ("NO collective-dismissal notification duty exists anywhere in Law No. 6 "
                   "of 2010 on Labour in the Private Sector, established by reading the "
                   "whole instrument — the Public Authority for Manpower's own English "
                   "translation, 76,226 characters, searched for collective, closure, "
                   "liquidation, reduction, redundancy, suspension, cessation, notify the "
                   "ministry, competent authority and approval, with every hit read. Art. "
                   "44 is individual notice from employer to employee; art. 45-47 are "
                   "unfair-dismissal restrictions; art. 50 expires the contract on "
                   "bankruptcy or final closure WITHOUT any filing; art. 61 covers wages "
                   "during a closure. THE FALSE POSITIVE THIS ENTRY EXISTS TO KILL: the "
                   "widely quoted 'inform the competent Ministry three months in advance' "
                   "clause concerns non-renewal of a COLLECTIVE (group) EMPLOYMENT "
                   "CONTRACT — a collective bargaining agreement — and has nothing to do "
                   "with collective dismissal. TWO RESIDUAL RISKS, stated rather than "
                   "buried: the ARABIC original governs and was not read, and art. 8's "
                   "returns are prescribed by ministerial decision, so a filing duty could "
                   "live outside the statute. Both are cheap to check from an environment "
                   "with Gulf egress. NOTE ON PROVENANCE: manpower.gov.kw is unreachable "
                   "from here (ECONNREFUSED, not a refusal), so the official PDF was read "
                   "through a web.archive.org snapshot of that same file"),
        "authority": None,
        "threshold": None,
        "aggregate": ("NONE. NEAR-MISSES REJECTED: art. 8's annual headcount return is a "
                      "STOCK of employees, not separations; and Kuwait's labour figures "
                      "reach ILOSTAT through a Labour Force Sample Survey"),
        "denominator_basis": None,
        "assessed": "2026-08-19",
        "cite": ("https://web.archive.org/web/20220723102143/"
                 "https://www.manpower.gov.kw/docs/LaborLaw/Labor_Law_Eng.pdf"),
    },

    "Botswana": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Employment Act Cap 47:01 s.25 (Redundancy), read verbatim: 'when an "
                   "employer forms an intention to terminate contracts of employment for "
                   "the purpose of reducing the size of his work force, he shall "
                   "forthwith give written notice of that intention to the Commissioner "
                   "and to every employee to be or likely to be directly affected'. "
                   "s.25(1) is first-in-last-out subject to operational need, s.25(3) a "
                   "six-month re-engagement priority, s.25(4) makes contravention an "
                   "offence under s.151(b)"),
        "authority": "the Commissioner of Labour, Ministry of Labour and Home Affairs",
        "threshold": ("NONE — AND THAT IS THE FINDING. The duty attaches to the INTENTION "
                      "to reduce, with no minimum number of dismissals and no minimum "
                      "employer size, which is a broader trigger than US WARN, than "
                      "Directive 98/59/EC, and than South Africa's s.189A. Botswana's "
                      "Commissioner therefore holds a thresholdless national dataset"),
        "aggregate": ("NO PERIODIC PUBLICATION, but the count demonstrably EXISTS and is "
                      "disclosed ad hoc, which is a different and more hopeful state than "
                      "Germany's. Answering a parliamentary question in February 2023 the "
                      "Minister of Labour and Home Affairs stated that 1,170 companies had "
                      "submitted notifications of intention to retrench between January "
                      "2019 and January 2023, with 3,680 workers losing jobs — reported by "
                      "the government's own Daily News, and naming NO companies. A later "
                      "PQ reportedly gives 700 companies / 5,392 employees for January "
                      "2024 to May 2026 and is UNVERIFIED. There is no cadence, no stable "
                      "unit and no format, so this is not a published series. It is the "
                      "best 'one request away from an aggregate' candidate found "
                      "anywhere: the realistic route is a direct ministry request or a "
                      "Hansard trawl of the recurring question, not a scrape. NEAR-MISSES "
                      "REJECTED: Statistics Botswana's Quarterly Labour Force Module and "
                      "Formal Employment Stats Brief are survey and stock series"),
        "assessed": "2026-08-19",
        "cite": ("https://www.botswanalmo.org.bw/system/files/"
                 "Legislation_Employment_Act.pdf"),
    },

    "Switzerland": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("TWO duties, and the second is the one a collector would otherwise "
                   "miss. (1) Massenentlassung — Code des obligations / "
                   "Obligationenrecht art. 335d (what counts), 335f (inform and consult) "
                   "and 335g (WRITTEN NOTIFICATION to the cantonal labour office, with "
                   "the employment ending no earlier than 30 days after it). (2) art. 29 "
                   "AVG with art. 53 AVV — a separate, LOWER duty to report the dismissal "
                   "of a larger number of employees or a plant closure to the competent "
                   "cantonal office as early as possible, where 'larger number' means 10 "
                   "and A CANTON MAY LOWER IT TO 6. SECO's own portal foregrounds the "
                   "second, not the first, so anything keyed only on OR 335d is keyed on "
                   "the wrong threshold. Read from arbeit.swiss (SECO/ALV), fully "
                   "permissive; fedlex.admin.ch permits us in robots but serves a "
                   "JavaScript shell with no law body, so the OR text was NOT read at "
                   "source"),
        "authority": ("the competent CANTONAL labour office — there is no federal "
                      "recipient, which is why there is no federal count"),
        "threshold": ("OR 335d, within 30 days: at least 10 dismissals in an "
                      "establishment of more than 20 and fewer than 100; at least 10% in "
                      "100-299; at least 30 in 300+. Coverage includes part-timers, "
                      "apprentices, interns, probationers and fixed-terms over 3 months. "
                      "AVG 29 / AVV 53 sits lower at 10, or 6 where a canton so provides"),
        "aggregate": ("NONE NATIONALLY. SECO's statistics pages carry no series of "
                      "Massenentlassung notifications, and its 'Die Lage auf dem "
                      "Arbeitsmarkt' is unemployment and Kurzarbeit only — Kurzarbeit "
                      "being SHORT-TIME WORK, the standard near-miss, rejected. RESIDUAL "
                      "STATED RATHER THAN SMOOTHED: BFS/OFS's catalogue was NOT "
                      "enumerated the way Germany's BA publication calendar was, so this "
                      "is 'no series found on the receiving side and none at SECO', not "
                      "the exhaustive negative Germany's entry carries. ONE CANTON DOES "
                      "PUBLISH A COUNT: St. Gallen's AWA-Barometer reports a quarterly "
                      "cantonal figure, with no names. 14 of 26 cantons were checked by "
                      "name for a per-employer list and none publishes one; Aargau "
                      "states it handles notifications 'mit hochster Diskretion'; Ticino "
                      "names ClaudeBot and disallows everything, so TI is UNKNOWN"),
        "assessed": "2026-08-19",
        "cite": ("https://www.arbeit.swiss/secoalv/en/home/menue/unternehmen/"
                 "massenentlassungen/meldepflicht.html"),
    },

    "Germany": {
        "class": REGIME_NO_AGGREGATE,
        "regime": "Massenentlassungsanzeige — s.17(1) and (3) Kundigungsschutzgesetz (KSchG)",
        "authority": "the Agentur fur Arbeit for the establishment, before the dismissals",
        "threshold": ("per establishment within 30 days: more than 5 where 21-59 employees; "
                      "10% or more than 25 where 60-499; at least 30 where 500+"),
        "aggregate": ("NONE. The Bundesagentur fur Arbeit's own complete Fachstatistiken "
                      "publication calendar was enumerated on 2026-08-18 "
                      "and contains no product for Entlassung / Massenentlassung / KSchG "
                      "at all — the s.17 filings appear to be purely administrative. This "
                      "establishes that no REGULAR SERIES exists; it does not rule out ad "
                      "hoc Sonderauswertungen or parliamentary answers, neither of which "
                      "would be a usable denominator. NEAR-MISS, excluded explicitly: BA "
                      "does publish 'Realisierte Kurzarbeit', which is SHORT-TIME WORK and "
                      "not dismissal. Germany is our fourth-largest country by volume, so "
                      "this is a significant and deliberate blank"),
        "assessed": "2026-08-18",
        "cite": "https://www.gesetze-im-internet.de/kschg/__17.html",
    },

    "Italy": {
        "class": REFUSED,
        "regime": ("Licenziamento collettivo — L. 223/1991 artt. 4 and 24. THRESHOLD AND "
                   "ARTICLE NUMBERS ARE UNVERIFIED against primary text in this pass and "
                   "are recorded as recollection, not as a finding; verify before quoting"),
        "authority": ("the competent regional office (Regione / Ispettorato Territoriale "
                      "del Lavoro), or the Ministero del Lavoro where units span more than "
                      "one region — unverified against primary text"),
        "threshold": ("reported as more than 15 employees and at least 5 dismissals within "
                      "120 days in one province — UNVERIFIED, see regime"),
        "aggregate": ("UNDETERMINED, and the honest answer changed during this assessment. "
                      "An earlier pass recorded 'the Comunicazioni Obbligatorie report "
                      "folds collective dismissal into an undifferentiated Licenziamento "
                      "total'. THAT CLAIM IS WITHDRAWN: it was never actually checked, and "
                      "it cannot now be checked, because the report lives on a host that "
                      "names ClaudeBot and disallows it. Having no positive evidence that a "
                      "count is published is NOT the same as having verified that none is, "
                      "and Italy is recorded as the second — refused — rather than the "
                      "first. NEAR-MISS that remains true and excluded either way: CIG/CIGS "
                      "hours authorised (D.Lgs 148/2015) is short-time work, not dismissal"),
        "refusal_host": "www.cliclavoro.gov.it",
        "refusal_reason": ("THE BLOCK SITS UPSTREAM OF EVEN FINDING OUT. The host serving "
                           "the Comunicazioni Obbligatorie report carries "
                           "'User-agent: ClaudeBot / Disallow: /' (also CCBot, GPTBot, "
                           "Google-Extended, Amazonbot, Applebot-Extended, Bytespider, "
                           "meta-externalagent). Its 'Content-Signal: search=yes,ai-train=no,"
                           "use=reference' line sits under 'User-agent: *' and is OVERRIDDEN "
                           "for us by our own named group — a trap worth remembering, "
                           "because an earlier reading of this same file concluded crawling "
                           "was permitted. dati.lavoro.gov.it resolves but will not connect, "
                           "and anpal.gov.it is DNS SERVFAIL: do not cite ANPAL as a live "
                           "publisher"),
        "assessed": "2026-08-18",
        "cite": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1991-07-23;223",
    },

    "Finland": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Muutosneuvottelut (formerly yhteistoimintaneuvottelut) — laki "
                   "yhteistoiminnasta yrityksissa (1333/2021), with notification to the "
                   "employment authority"),
        "authority": "the TE office / employment authority",
        "threshold": "employers of 20 or more; 10 or more workers triggers the longer process",
        "aggregate": ("NONE. The complete StatFin 'tyonv' table list was enumerated through "
                      "the PxWeb API on 2026-08-18 and contains no "
                      "muutosneuvottelut table. NEAR-MISS: the fully-furloughed stock "
                      "series is short-time work, not dismissal"),
        "assessed": "2026-08-18",
        "cite": "https://www.finlex.fi/fi/laki/ajantasa/2021/20211333",
    },

    "Austria": {
        "class": REGIME_NO_AGGREGATE,
        "regime": "Fruhwarnsystem — s.45a Arbeitsmarktforderungsgesetz (AMFG)",
        "authority": "Arbeitsmarktservice (AMS), 30 days before the dismissals",
        "threshold": ("banded within 30 days: 5 in an establishment of 21-99; 5% in "
                      "100-599; 30 in 600+; or 5 workers aged 50+ regardless of size"),
        "aggregate": ("NONE located. AMS's own statistics host iambweb.ams.or.at carries a "
                      "blanket robots.txt disallow, so the search was confined to what is "
                      "reachable elsewhere — this classification is therefore weaker than "
                      "Germany's and should be re-checked before it is quoted"),
        "assessed": "2026-08-18",
        "cite": "https://www.ris.bka.gv.at/GeltendeFassung.wxe?Abfrage=Bundesnormen&Gesetzesnummer=10008593",
    },

    "Greece": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Omadikes apolyseis — L. 1387/1983 as amended, transposing Directive "
                   "98/59/EC"),
        "authority": "the Ministry of Labour / the Supreme Labour Council (ASE)",
        "threshold": "6 in establishments of 20-150; 5% or up to 30 in larger, per month",
        "aggregate": ("NONE isolating collective dismissal. The ERGANI system publishes "
                      "monthly hiring and separation FLOWS, which is a near-miss: it does "
                      "not break out collective dismissals, and a total separations figure "
                      "is not a collective-dismissal denominator"),
        "assessed": "2026-08-18",
        "cite": "https://www.et.gr/",
    },

    "Luxembourg": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Licenciement collectif / plan de maintien dans l'emploi — Code du "
                   "travail, transposing Directive 98/59/EC"),
        "authority": "ADEM and the Comite de conjoncture",
        "threshold": "7 dismissals over 30 days, or 15 over 90 days",
        "aggregate": "NONE located in ADEM's published series",
        "assessed": "2026-08-18",
        "cite": "https://adem.public.lu/fr/publications/adem.html",
    },

    "Malta": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Collective Redundancies (Protection of Employment) Regulations, "
                   "transposing Directive 98/59/EC"),
        "authority": "the Director of Industrial and Employment Relations (DIER)",
        "threshold": "10 in establishments of 20-99; 10% in 100-299; 30 in 300+, over 30 days",
        "aggregate": ("NONE located. Both nso.gov.mt and dier.gov.mt sit behind a Cloudflare "
                      "wall, so as with Austria this is a weaker negative than Germany's"),
        "assessed": "2026-08-18",
        "cite": "https://legislation.mt/eli/sl/452.80/eng",
    },

    "Slovenia": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Odpoved vecjemu stevilu delavcev — Zakon o delovnih razmerjih (ZDR-1), "
                   "transposing Directive 98/59/EC"),
        "authority": "Zavod RS za zaposlovanje (ZRSZ)",
        "threshold": "banded from 10 workers depending on establishment size, over 30 days",
        "aggregate": ("NONE located. NOTE pxweb.stat.si names ClaudeBot in its robots.txt, "
                      "so the statistical office's own database was not queried"),
        "assessed": "2026-08-18",
        "cite": "http://www.pisrs.si/Pis.web/pregledPredpisa?id=ZAKO5944",
    },

    "Malaysia": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Retrenchment notification, Borang PK — Employment Act 1955 s.63 with "
                   "the Employment (Retrenchment) Notification 2004"),
        "authority": "the nearest Jabatan Tenaga Kerja (JTK/JTKSM) office",
        "threshold": ("filed 30 days before retrenchment for Parts I-IV; covers "
                      "retrenchment, VSS, temporary lay-off and wage reduction"),
        "aggregate": ("NONE derived from the PK filings. NEAR-MISS: PERKESO's Employment "
                      "Insurance System 'Loss of Employment' series is monthly and good "
                      "quality, but it counts INSURANCE CLAIMS rather than employer "
                      "notifications and covers a different population"),
        "assessed": "2026-08-18",
        "cite": "https://jtksm.mohr.gov.my/",
    },

    "Sri Lanka": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Termination of Employment of Workmen (Special Provisions) Act No. 45 of "
                   "1971 (TEWA) — note this is a PRIOR APPROVAL regime, stronger than mere "
                   "notification: the Commissioner General must decide within two months"),
        "authority": "Commissioner General of Labour",
        "threshold": ("employers of 15+ workmen, any non-disciplinary termination; excludes "
                      "the public sector, co-operatives and under 180 days' service"),
        "aggregate": ("NONE, and this is the instructive case in the whole register: an "
                      "APPROVAL regime generates a far stronger administrative record than "
                      "a notification regime, and Sri Lanka still publishes only "
                      "PROSECUTIONS from it. The Labour Statistics volumes for 2017-2019 "
                      "were read directly and their single TEWA table is 'Enforcement of "
                      "Labour Laws and Prosecutions' — case counts and sums recovered, not "
                      "applications received or approved. The series appears to stop at "
                      "2019. So the existence of an approval duty predicts nothing about "
                      "publication"),
        "assessed": "2026-08-18",
        "cite": "https://www.labourdept.gov.lk/",
    },

    "Bangladesh": {
        "class": REGIME_NO_AGGREGATE,
        "regime": "Bangladesh Labour Act 2006 s.20 (retrenchment) and s.16 (lay-off)",
        "authority": ("a copy of the notice goes to the Inspector General (DIFE) and the "
                      "collective bargaining agent"),
        "threshold": ("per worker with at least one year's continuous service, one month's "
                      "notice or pay in lieu. There is NO mass threshold, so the duty is "
                      "individual rather than collective and would not produce an event "
                      "count even if published"),
        "aggregate": "NONE located at dife.gov.bd, dol.gov.bd or bbs.gov.bd",
        "assessed": "2026-08-18",
        "cite": "https://dife.portal.gov.bd/",
    },

    "Canada": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Group termination — Canada Labour Code s.212(1) for federally "
                   "regulated employers, verified verbatim against the Justice Laws "
                   "consolidation, PLUS separate provincial regimes: Ontario ESA Form 1, "
                   "and Quebec's Loi sur les normes du travail RLRQ c. N-1.1 artt. 84.0.1 "
                   "and 84.0.4, verified against LegisQuebec"),
        "authority": ("federal: 'the Head' in writing, with a copy to the Minister of "
                      "Employment and Social Development and the Canada Employment "
                      "Insurance Commission. Quebec: the ministre de l'Emploi et de la "
                      "Solidarite sociale"),
        "threshold": ("federal: 50 or more within any 4-week period, at least 16 weeks "
                      "ahead. Quebec: 10 or more over 2 consecutive months, with 8, 12 or "
                      "16 weeks' notice by size"),
        "aggregate": ("NONE. A claim reached this register that Quebec publishes a monthly "
                      "PER-EMPLOYER register — a WARN-equivalent, which would have been the "
                      "only one outside the US — and it is CONTRADICTED. The whole "
                      "quebec.ca sitemap was enumerated (10,781 URLs) and exactly three "
                      "pages mention licenciement: the submission form, the employer "
                      "guidance, and its parent. No register, no listing, no statistics "
                      "page; the old Emploi-Quebec site now redirects. Federally, "
                      "open.canada.ca returns nothing for group termination, licenciement "
                      "collectif or layoff notice. Provinces other than Ontario and Quebec "
                      "were not checked"),
        "assessed": "2026-08-18",
        "cite": "https://laws-lois.justice.gc.ca/eng/acts/L-2/section-212.html",
    },

    "Australia": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Fair Work Act 2009 s.530, 'Employer to notify Centrelink of certain "
                   "proposed dismissals' — verified verbatim from the official "
                   "consolidation: an employer dismissing 15 or more employees for reasons "
                   "of an economic, technological, structural or similar nature must give "
                   "written notice stating reasons, numbers, categories and timing"),
        "authority": ("the Chief Executive Officer of the Commonwealth Services Delivery "
                      "Agency (Centrelink / Services Australia)"),
        "threshold": "15 or more employees",
        "aggregate": ("NONE FOUND — but this negative is weaker than Germany's and is "
                      "labelled so rather than levelled up. Both obvious verification "
                      "routes were unavailable: data.gov.au carries a blanket "
                      "'User-agent: * / Disallow: /' with no alternative, and "
                      "servicesaustralia.gov.au reset every connection. So this is an "
                      "inference from an incomplete search, not a completed check"),
        "assessed": "2026-08-18",
        "cite": "https://www.legislation.gov.au/C2009A00028/latest/text",
    },

    "Singapore": {
        "class": REGIME_NO_AGGREGATE,
        "regime": ("Mandatory retrenchment notification to MOM — statutory citation "
                   "DELIBERATELY ABSENT: MOM's own page names no Act or section and none "
                   "was verified, so none is recorded. The DUTY itself is quoted from "
                   "MOM: employers with a Singapore-registered business and at least 10 "
                   "employees who notify any employee of retrenchment must notify MOM "
                   "within 5 working days"),
        "authority": "Ministry of Manpower (MOM)",
        "threshold": "employers with at least 10 employees, any retrenchment notified",
        "aggregate": ("THE MOST INSTRUCTIVE NEGATIVE IN THE REGISTER, because everything "
                      "about it looks like a yes. Singapore has the cleanest notification "
                      "duty in its region AND publishes a clean quarterly retrenchment "
                      "series — and the two are NOT connected. MOM attributes the series "
                      "verbatim to 'Labour Market Survey, Manpower Research & Statistics "
                      "Department, MOM', and its own coverage note says the data pertain "
                      "to private sector establishments EACH WITH AT LEAST 25 EMPLOYEES "
                      "plus the public sector. The notification duty bites at 10. Those "
                      "are DIFFERENT UNIVERSES, and the figures are rounded to the nearest "
                      "10 besides. It is a survey near-miss and must never be described as "
                      "a notification count. Honest limit: MOM publishes no explicit "
                      "sentence saying notification data are unused, so this rests on the "
                      "source attribution and the frame, not on a disclaimer"),
        "assessed": "2026-08-18",
        "cite": "https://stats.mom.gov.sg/Pages/Retrenchment-Summary-Table.aspx",
    },

    'Argentina': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Procedimiento Preventivo de Crisis — Ley 24.013 arts. 98-105. "
                   "Structurally the closest thing to a US WARN notice anywhere in Latin "
                   "America: threshold-gated and filed before the dismissals"),
        "authority": (
                   "Secretaria de Trabajo"),
        "threshold": (
                   "more than 15% of the workforce in firms under 400, more than 10% in "
                   "400-1000, more than 5% above 1000"),
        "aggregate": (
                   "NONE PUBLISHED. The counts that circulate in the press come from Ley "
                   "27.275 freedom-of-information requests, and the ministry FORMALLY "
                   "REFUSED the breakdown by workers, sector and geography under art. 5. "
                   "So this is a FOIA play, not a scrape, and the cost of the sample is "
                   "a legal request per period rather than a fetch"),
        "cite": (
                   ""
                   "https://www.argentina.gob.ar/servicio/iniciar-procedimiento-preventivo-de-crisis-de-empresa-ppce"),
        "assessed": "2026-08-18",
    },
    'Türkiye': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Toplu isci cikarma — Is Kanunu 4857 art. 29, verified verbatim: 30 "
                   "days' written notice to the union representatives, the regional "
                   "directorate AND ISKUR"),
        "authority": (
                   "ISKUR and the regional directorate of labour"),
        "threshold": (
                   "10 workers in workplaces of 20-100; 10% in 101-300; 30 in 301+, "
                   "within one month"),
        "aggregate": (
                   "NONE, and the hypothesis was chased to a conclusion rather than "
                   "abandoned. The July 2026 ISKUR monthly bulletin (33 tables) and the "
                   "2025 yearbook (38 tables) were machine-parsed and neither carries a "
                   "toplu isci cikarma table. FALSE-FRIEND WARNING for anyone "
                   "re-checking: keyword hits on 'toplu' are all Toplum Yararina "
                   "Programlar, a different scheme entirely. ISKUR holds a statutorily "
                   "complete register and publishes none of it, which makes it the "
                   "single highest-leverage freedom-of-information target in this "
                   "register"),
        "cite": (
                   "https://www.iskur.gov.tr/kurumsal/istatistikler/"),
        "assessed": "2026-08-18",
    },
    'Israel': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Employment Service Law 1959 s.37, verified verbatim in Hebrew: an "
                   "employer dismissing 10 or more workers simultaneously or within one "
                   "month must notify the competent Employment Service bureau. "
                   "Notification only, no approval"),
        "authority": (
                   "the competent Employment Service bureau"),
        "threshold": (
                   "10 or more workers, a FLAT threshold regardless of firm size — "
                   "unlike almost every other regime here, which bands by size"),
        "aggregate": (
                   "UNKNOWN rather than established absent, and the distinction is kept: "
                   "taasuka.gov.il, which is the receiving authority and therefore the "
                   "only body that could publish it, returns 403 to all automated "
                   "clients. NEAR-MISS to reject if anyone re-checks: nevo.co.il bans "
                   "GPTBot, Google-Extended, Perplexity and '*' outright"),
        "cite": (
                   "https://www.btl.gov.il/Laws1/00_0050_000000.pdf"),
        "assessed": "2026-08-18",
    },
    'Colombia': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Ley 50 de 1990 art. 67 — PRIOR AUTHORISATION from the Ministerio del "
                   "Trabajo, not mere notification; an unauthorised collective dismissal "
                   "'no producira ningun efecto'. CORRECTION recorded: there is no 'CST "
                   "art. 66-A'; cite Ley 50/1990 arts. 66-67"),
        "authority": (
                   "Ministerio del Trabajo"),
        "threshold": (
                   "over 6 months, sliding by size: 30% in firms of 10-50, down to 5% "
                   "above 1000"),
        "aggregate": (
                   "NONE FOUND. datos.gov.co returns zero matching datasets. "
                   "mintrabajo.gov.co was unreachable, so the ministry's own microsite "
                   "is UNKNOWN rather than checked, and this negative is labelled weaker "
                   "for it"),
        "cite": (
                   ""
                   "https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=281"),
        "assessed": "2026-08-18",
    },
    'Peru': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Cese colectivo por motivos economicos — D.S. 003-97-TR arts. 46-52, "
                   "requiring MTPE authorisation"),
        "authority": (
                   "Ministerio de Trabajo y Promocion del Empleo (MTPE)"),
        "threshold": (
                   "10% of the workforce"),
        "aggregate": (
                   "NONE, chased to a conclusion: the 2022 Anuario Estadistico Sectorial "
                   "XLSX bundle (16 chapter workbooks) and the 2020 PDF (338 pages) were "
                   "machine-searched and neither carries a cese colectivo chapter. "
                   "CRITICAL FALSE FRIEND, recorded because a phrase-matching scraper "
                   "would produce a badly wrong number: MTPE's 'ceses colectivos' pages "
                   "are the Registro Nacional de Trabajadores Cesados Irregularmente, "
                   "which is a public-sector 1990-2000 compensation list and nothing to "
                   "do with current collective dismissal"),
        "cite": (
                   "https://www.gob.pe/mtpe"),
        "assessed": "2026-08-18",
    },
    'Kenya': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Employment Act 2007 s.40 — one month's notice to the union and to "
                   "the labour officer of the area"),
        "authority": (
                   "the labour officer of the area — DECENTRALISED, which likely "
                   "explains the absence of any national aggregate"),
        "threshold": (
                   "NONE. The duty bites on a single redundancy, so it would not yield "
                   "an event count comparable with any threshold-gated regime here even "
                   "if published"),
        "aggregate": (
                   "NONE FOUND, and UNKNOWN at the statistical office: knbs.or.ke serves "
                   "a JavaScript bot challenge and has an expired TLS certificate, and "
                   "kenyalaw.org returns 403. Neither was bypassed"),
        "cite": (
                   "https://www.labour.go.ke/publications"),
        "assessed": "2026-08-18",
    },
    'Serbia': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Program resavanja viska zaposlenih — Zakon o radu arts. 153-160: the "
                   "programme must be delivered within 8 days to the representative "
                   "union and to the NSZ, which returns a non-binding opinion within 15 "
                   "days"),
        "authority": (
                   "Nacionalna sluzba za zaposljavanje (NSZ)"),
        "threshold": (
                   "more than 10 employees in firms of 20-100; 10% in 100-300; 30+ above "
                   "300, over 30 days; or 20+ over 90 days regardless of size"),
        "aggregate": (
                   "NONE. The NSZ 2025 annual report was read directly: 'visak "
                   "zaposlenih' appears only as a BENEFICIARY CATEGORY in active labour "
                   "market programmes, never as a count of programmes submitted. A "
                   "secondary source claims roughly 9,000 a year from the 2015-2020 "
                   "reports and could not be verified. nsz.gov.rs is fully open "
                   "('User-agent: * / Disallow:'), so this negative is a strong one"),
        "cite": (
                   "https://www.nsz.gov.rs/sadrzaj/izvestaj-i-program-rada-nsz/4109"),
        "assessed": "2026-08-18",
    },
    'Jersey': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Employment (Jersey) Law 2003 Article 60N — where 12 or more "
                   "employees are proposed for redundancy at one establishment within 30 "
                   "days the employer must notify the Minister at least 30 days before "
                   "the first dismissal, and failure is a CRIMINAL offence. THRESHOLD "
                   "CAUTION recorded rather than smoothed over: an automated read of the "
                   "statute returned '20 or more', which is wrong; gov.je, JACS and "
                   "several law firms all say 12, and the machine reading was not "
                   "asserted"),
        "authority": (
                   "the Minister for Social Security"),
        "threshold": (
                   "12 or more employees at one establishment within 30 days"),
        "aggregate": (
                   "NONE. opendata.gov.je returns 'No datasets found for redundancy'. "
                   "The small-jurisdiction hypothesis — that a complete published list "
                   "might exist where the numbers are tiny — was tested here and did not "
                   "hold"),
        "cite": (
                   "https://www.jerseylaw.je/laws/current/l_42_2003"),
        "assessed": "2026-08-18",
    },
    'Mexico': {
        "class": REGIME_NO_AGGREGATE,
        "regime": (
                   "Terminacion colectiva de las relaciones de trabajo — Ley Federal del "
                   "Trabajo arts. 433-439, requiring approval from the labour tribunal"),
        "authority": (
                   "the Tribunal Laboral (formerly the Junta de Conciliacion y "
                   "Arbitraje)"),
        "threshold": (
                   "collective termination on the statutory economic grounds; no simple "
                   "headcount band"),
        "aggregate": (
                   "NONE FOUND. NEAR-MISS to reject: IMSS insured-employment change is a "
                   "NET employment series and says nothing about dismissals specifically"),
        "cite": (
                   "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFT.pdf"),
        "assessed": "2026-08-18",
    },
    # -----------------------------------------------------------------------
    # REFUSED — a block aimed at AI agents, recorded rather than routed around
    # -----------------------------------------------------------------------

    "France": {
        "class": REFUSED,
        "regime": ("Plan de sauvegarde de l'emploi (PSE) — Code du travail L.1233-61, with "
                   "L.1233-57-4 requiring DREETS to validate an accord or homologate a "
                   "unilateral document within 15 or 21 days"),
        "authority": "DREETS (the regional directorate), which validates or homologates",
        "threshold": "10 or more dismissals within 30 days in a firm of 50 or more",
        "aggregate": ("EXISTS AND IS PUBLISHED — DARES issues the PSE series (procedures and "
                      "employees concerned) quarterly as XLSX — AND WE MAY NOT FETCH IT. "
                      "This is the largest single loss in the register: France is our "
                      "fifth-largest country by volume and the figure is exactly the right "
                      "shape. No crawlable mirror exists: the DARES organisation on "
                      "data.gouv.fr carries 35 datasets and none is PSE, the one "
                      "'licenciements economiques' dataset there is abandoned with a 2010Q4 "
                      "file on a dead host, and the POEM portal's PSE page returns HTTP 500 "
                      "with no PSE export in its catalogue"),
        "refusal_host": "dares.travail-emploi.gouv.fr (also travail-emploi.gouv.fr, legifrance.gouv.fr)",
        "refusal_reason": ("THE PUBLISHER DEMONSTRABLY HAS THE FIGURE AND BLOCKS US. The host "
                           "serves an F5/TSPD JavaScript bot defence instead of content; "
                           "robots.txt itself is unreadable and a plain fetch of the data "
                           "page returned an explicit human-verification CAPTCHA. "
                           "legifrance.gouv.fr sits behind a Cloudflare managed challenge "
                           "(403 on robots.txt). No attempt was made to route around any of "
                           "these, and none should be"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": "https://dares.travail-emploi.gouv.fr/donnees/les-licenciements",
    },

    "Philippines": {
        "class": REFUSED,
        "regime": ("Labor Code art. 298 (ex-283) — 30 days' written notice of retrenchment, "
                   "redundancy or closure, filed as the Establishment Termination Report "
                   "(RKS Form 5)"),
        "authority": "the DOLE Regional Office, and the affected worker",
        "threshold": "30 days before the intended date; any retrenchment, redundancy or closure",
        "aggregate": ("EXISTS AND IS THE BEST-SHAPED REGIME FOUND ANYWHERE — the PSA's Job "
                      "Displacement Monitoring System is built explicitly from "
                      "'all establishments reporting shutdown/retrenchments to DOLE Regional "
                      "Offices', which is precisely a notification-derived denominator. "
                      "Catalogue entries were visible for 2000, 2001, 2004, 2011 and 2012; "
                      "whether it is still current could NOT be established, because the "
                      "host refuses us"),
        "refusal_host": "psa.gov.ph and psada.psa.gov.ph (also www.dole.gov.ph)",
        "refusal_reason": ("THE PUBLISHER HAS THE FIGURE AND BLOCKS US BY NAME. Both PSA "
                           "hosts carry 'User-agent: ClaudeBot / Disallow: /' (alongside "
                           "GPTBot, CCBot, Google-Extended, Amazonbot, Applebot-Extended, "
                           "Bytespider and meta-externalagent), with a Content-Signal of "
                           "'search=yes,ai-train=no,use=reference'. www.dole.gov.ph returns "
                           "403 on robots.txt itself, so it is behind a bot wall too"),
        "denominator_basis": "national_notification_aggregate",
        "assessed": "2026-08-18",
        "cite": "https://psada.psa.gov.ph/index.php/catalog/155",
    },

    "Ireland": {
        "class": REFUSED,
        "regime": ("Collective redundancy notification — Protection of Employment Act 1977 "
                   "s.12, transposing Directive 98/59/EC"),
        "authority": "the Minister for Enterprise, Trade and Employment (DETE)",
        "threshold": ("banded over 30 days: 5 in an establishment of 21-49; 10 in 50-99; "
                      "10% in 100-299; 30 in 300+"),
        "aggregate": ("UNDETERMINED, because the department's own host blocks us. What is "
                      "known: the Redundancy Payments Scheme statistics are a NEAR-MISS "
                      "(payment claims, not notifications) and must not be used. Whether "
                      "DETE publishes a count of s.12 notifications could not be "
                      "established from what remains reachable"),
        "refusal_host": "www.gov.ie (also www.oireachtas.ie)",
        "refusal_reason": ("THE BLOCK SITS UPSTREAM OF EVEN FINDING OUT — this is the second "
                           "shade of refusal, not France's. www.gov.ie carries "
                           "'User-agent: ClaudeBot / Disallow: /' (also GPTBot, "
                           "Google-Extended, Amazonbot, Applebot) and oireachtas.ie serves a "
                           "human-verification interstitial, so the publication question "
                           "itself is unanswerable rather than answered negatively. "
                           "enterprise.gov.ie IS open and did not carry the series"),
        "assessed": "2026-08-18",
        "cite": "https://www.irishstatutebook.ie/eli/1977/act/7/enacted/en/html",
    },

    "Cyprus": {
        "class": REFUSED,
        "regime": ("Collective redundancy notification under the Termination of Employment "
                   "Law, transposing Directive 98/59/EC — so a regime certainly exists "
                   "(Directive 98/59/EC art. 3(1) is unconditional); what is unknown is "
                   "whether anything is published from it"),
        "authority": "the Ministry of Labour and Social Insurance",
        "threshold": "banded from 10 workers over 30 days, per the Directive floor",
        "aggregate": ("UNDETERMINED — the ministry host blocks us, so we cannot say whether "
                      "a count is published. Recorded as refused rather than as 'no "
                      "aggregate', which would be an unearned negative"),
        "refusal_host": "www.mlsi.gov.cy",
        "refusal_reason": ("THE BLOCK SITS UPSTREAM OF EVEN FINDING OUT. Blanket "
                           "'Disallow: /' with Googlebot exempted, which is a block aimed at "
                           "everything that is not a search engine, ourselves included"),
        "assessed": "2026-08-18",
        "cite": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A31998L0059",
    },

    "Lithuania": {
        "class": REFUSED,
        "regime": ("Grupes darbuotoju atleidimas — Darbo kodeksas, transposing Directive "
                   "98/59/EC"),
        "authority": "Uzimtumo tarnyba (the employment service)",
        "threshold": "banded from 10 workers over 30 days, per the Directive floor",
        "aggregate": ("UNDETERMINED. A published series is plausible — the employment "
                      "service is the notified authority and publishes other labour series "
                      "— but it could not be verified"),
        "refusal_host": "uzt.lt",
        "refusal_reason": ("THE BLOCK SITS UPSTREAM OF EVEN FINDING OUT. A Cloudflare wall "
                           "returns 403 to everything including its own robots.txt, so no "
                           "crawl directive could even be read"),
        "assessed": "2026-08-18",
        "cite": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A31998L0059",
    },

}



# Not a country. `country` in the corpus carries one bucket that is a SCOPE
# rather than a place: a cut announced as worldwide with no per-country split.
# It has no legislature and therefore no disclosure regime, and classifying it
# as NO_REGIME would be a category error that reads as a finding about a real
# place. It is excluded by name, and the exclusion is counted and printed so it
# cannot be mistaken for something nobody looked at.
NOT_A_COUNTRY = {"Multiple countries"}

# Two spellings of one country, both live in the corpus on 2026-08-18: "Korea"
# alongside "South Korea", and "People's Republic of China" alongside "China".
# This register maps them to the entry for the country they name, because the
# Republic of Korea's statute does not change with the spelling used to store a
# row — but the duplication is a REAL defect in the stored vocabulary and it is
# reported (see `vocabulary_duplicates` in the output) rather than absorbed
# quietly. Absorbing it silently would let this register be the thing that hides
# it. Fixing it belongs to `alt_normalize_country`, not here.
ALIASES = {
    "Korea": "South Korea",
    "People's Republic of China": "China",
}


def canonical(name):
    return ALIASES.get(name, name)


# ---------------------------------------------------------------------------
# scope — read from the live corpus, never from this file
# ---------------------------------------------------------------------------

def _http(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def live_countries(fetch=None):
    """[(country, jobs, entries)] for every country the tracker holds rows for.

    Raises on any transport or shape fault. A partial scope list would silently
    shrink the set of countries owed a classification, and this register's whole
    job is to notice a country nobody has classified — so a failure here must be
    UNKNOWN, never a short list that looks complete.
    """
    fetch = fetch or _http
    url = (SITE + "/wp-json/layoffs/v1/aggregate?"
           + urllib.parse.urlencode({"cb": os.urandom(5).hex()}))
    payload = json.loads(fetch(url)) or {}
    rows = payload.get("map_countries")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("aggregate returned no map_countries — scope is UNKNOWN, "
                           "and an empty scope must never read as 'nothing to classify'")
    out = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or not row:
            raise RuntimeError(f"unreadable map_countries row: {row!r}")
        name = row[0]
        jobs = row[1] if len(row) > 1 else None
        entries = row[2] if len(row) > 2 else None
        out.append((name, jobs, entries))
    return out


# ---------------------------------------------------------------------------
# assessment — per country, three states, an expiry, and no averaging
# ---------------------------------------------------------------------------

def _age_days(stamp, today=None):
    try:
        then = date(*(int(x) for x in str(stamp).split("-")))
    except (TypeError, ValueError):
        return None
    return ((today or date.today()) - then).days


REQUIRED_FIELDS = ("class", "regime", "aggregate", "assessed", "cite")
# A refusal must name the host that refused and say which shade it is, or it
# becomes the register's dumping ground for anything awkward. See REFUSED in the
# module docstring.
REFUSAL_FIELDS = ("refusal_host", "refusal_reason")


def entry_for(country, today=None):
    """The register's finding for one country, with its expiry already applied.

    An entry whose assessment is older than MAX_ASSESSMENT_AGE_DAYS does NOT
    keep reporting its old classification. It reports UNKNOWN and says how old
    it is. A standing "no regime exists here" that nobody has revisited since a
    parliament sat is a stale claim wearing a permanent exemption, which is the
    defect benchmark_freshness.py exists to catch one floor down.
    """
    raw = REGISTER.get(canonical(country))
    if raw is None:
        return {"class": UNASSESSED, "state": UNKNOWN,
                "detail": ("no entry in the register — this country appears in the "
                           "corpus and nobody has established whether a disclosure "
                           "regime exists. UNKNOWN, and it is somebody's outstanding "
                           "work, not a pass")}
    missing = [f for f in REQUIRED_FIELDS if not raw.get(f)]
    if raw.get("class") == REFUSED:
        missing += [f for f in REFUSAL_FIELDS if not raw.get(f)]
    if missing:
        return dict(raw, state=UNKNOWN,
                    detail=(f"register entry is incomplete (missing {', '.join(missing)}) "
                            f"— an entry without its citation is an assertion, not a "
                            f"finding"))
    if raw["class"] not in CLASSIFICATIONS:
        return dict(raw, state=UNKNOWN,
                    detail=f"unknown classification {raw['class']!r}")
    age = _age_days(raw["assessed"], today)
    if age is None:
        return dict(raw, state=UNKNOWN,
                    detail=f"unreadable assessed date {raw['assessed']!r}")
    if age > MAX_ASSESSMENT_AGE_DAYS:
        return dict(raw, state=UNKNOWN, age_days=age,
                    detail=(f"assessed {raw['assessed']}, {age} days ago (max "
                            f"{MAX_ASSESSMENT_AGE_DAYS}) — statutes are amended and "
                            f"ministries start and stop publishing, so this is "
                            f"UNVERIFIED rather than still true. Re-check per RUNBOOK "
                            f"'classify a country's disclosure regime'"))
    return dict(raw, state=STATE_OF[raw["class"]], age_days=age)


def classify_all(today=None, fetch=None):
    """The whole register against the live corpus. Never raises."""
    today = today or date.today()
    report = {
        "note": ("Per-country disclosure-regime register. What EXISTS to be found, per "
                 "country, with the regime named — not a coverage percentage. There is "
                 "deliberately no worldwide average in this file: averaging a measured "
                 "country against an unmeasurable one produces a number whose "
                 "denominator is this register rather than the world. Written by "
                 "country-coverage.yml; NEVER hand-edit a classification, edit "
                 "REGISTER in railway/country_coverage.py and re-run."),
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_assessment_age_days": MAX_ASSESSMENT_AGE_DAYS,
    }
    try:
        rows = live_countries(fetch=fetch)
    except Exception as exc:                       # noqa: BLE001
        report.update(scope_state=UNKNOWN, detail=(
            f"could not read the live country scope ({type(exc).__name__}: {exc}) — "
            f"the set of countries owed a classification is UNKNOWN. This is not a "
            f"finding about any country"))
        return report

    countries, tallies = {}, {c: 0 for c in CLASSIFICATIONS}
    duplicates, excluded = [], []
    for name, jobs, entries in rows:
        if name in NOT_A_COUNTRY:
            excluded.append({"name": name, "jobs": jobs, "entries": entries,
                             "why": "a scope, not a place — no legislature, no regime"})
            continue
        if name in ALIASES:
            duplicates.append({"stored": name, "canonical": ALIASES[name],
                               "jobs": jobs, "entries": entries})
        rec = entry_for(name, today)
        rec.update(stored_name=name, jobs=jobs, entries=entries)
        # Two spellings of one country share one entry; count the country once.
        key = canonical(name)
        if key in countries:
            countries[key].setdefault("also_stored_as", []).append(name)
            continue
        countries[key] = rec
        tallies[rec.get("class", UNASSESSED)] += 1

    in_backlog = sorted(k for k in countries
                        if countries[k].get("class") == UNASSESSED
                        and k in ACKNOWLEDGED_BACKLOG)
    undeclared = sorted(k for k in countries
                        if countries[k].get("class") == UNASSESSED
                        and k not in ACKNOWLEDGED_BACKLOG)
    report.update(
        scope_state=MEASURED,
        scope_basis="countries the tracker holds rows for, read live from /aggregate",
        countries_in_scope=len(countries),
        countries=countries,
        tallies=tallies,
        excluded_not_a_country=excluded,
        # Reported, never absorbed. Fixing it belongs to alt_normalize_country.
        vocabulary_duplicates=duplicates,
        unassessed=sorted(k for k, v in countries.items()
                          if v.get("class") == UNASSESSED),
        # Acknowledged, dated outstanding work — reported loudly, not alarmed on.
        backlog=in_backlog,
        backlog_oldest=min((ACKNOWLEDGED_BACKLOG[k][0] for k in in_backlog), default=None),
        # In the corpus, in neither the register nor the backlog. THIS is the
        # defect: a country that arrived in the data and nobody noticed.
        undeclared=undeclared,
        expired=sorted(k for k, v in countries.items()
                       if v.get("state") == UNKNOWN and v.get("class") != UNASSESSED),
        exactly_measurable=sorted(k for k, v in countries.items()
                                  if v.get("class") == REGIME_WITH_AGGREGATE),
        refused=sorted(k for k, v in countries.items()
                       if v.get("class") == REFUSED),
        # Carried in the committed file on purpose: the ledger's job is to stop
        # a future session re-probing a host that already said no, and a ledger
        # that lives only in a module docstring is one nobody reads before
        # writing a collector.
        refusal_ledger=[dict(r) for r in REFUSAL_LEDGER],
        refusal_hosts=len(REFUSAL_LEDGER),
        # A DIFFERENT QUESTION FROM EVERYTHING ELSE IN THIS REPORT, carried
        # here so it is in front of a human every session: not "can coverage be
        # measured" but "does anybody publish a list that names employers".
        per_employer_registers=[dict(r) for r in PER_EMPLOYER_REGISTERS],
        per_employer_naming=sorted(r["jurisdiction"] for r in PER_EMPLOYER_REGISTERS
                                   if r.get("names_employers")),
        per_employer_swept=dict(PER_EMPLOYER_SWEPT),
    )
    return report


# ---------------------------------------------------------------------------
# the verdict — one definition, imported by data_integrity, ops_status and tests
# ---------------------------------------------------------------------------

def _days_since(stamp, now=None):
    try:
        then = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return ((now or datetime.now(timezone.utc)) - then).total_seconds() / 86400.0


def judge(report, now=None):
    """(state, detail) for the whole register.

    THERE IS NO FLOOR AND THERE IS NO PERCENTAGE, for the same reason
    rolling_recall.judge has neither. A country moving from
    REGIME_WITH_AGGREGATE to REGIME_NO_AGGREGATE because a ministry stopped
    publishing is not a coverage regression on our side, and alarming on it
    would train the owner to ignore the channel. What this enforces is that
    every country in the corpus HAS a classification, that no classification has
    aged past its expiry, and that the register is being recomputed at all.

    The failure it exists to catch is the one that made this module necessary:
    a country quietly entering the data and nobody ever establishing what there
    was to find in it.
    """
    if not isinstance(report, dict):
        return UNKNOWN, ("no per-country coverage register has been written yet — what "
                         "exists to be found per country is UNESTABLISHED, not fine. "
                         "Run `python3 railway/country_coverage.py --write`")
    age = _days_since(report.get("measured_at"), now)
    if age is None:
        return UNKNOWN, f"register has no readable timestamp: {report.get('measured_at')!r}"
    if age > MAX_MEASUREMENT_AGE_DAYS:
        return UNKNOWN, (f"the per-country register is {age:.0f} days old (max "
                         f"{MAX_MEASUREMENT_AGE_DAYS}) — either this checkout is behind "
                         f"main or country-coverage.yml has stopped. UNVERIFIED, not "
                         f"passing")
    if report.get("scope_state") != MEASURED:
        return UNKNOWN, (report.get("detail")
                         or "the country scope could not be read; nothing was classified")
    undeclared = report.get("undeclared") or []
    if undeclared:
        return UNKNOWN, (f"{len(undeclared)} countr{'y' if len(undeclared) == 1 else 'ies'} "
                         f"in the corpus that nobody has either classified OR acknowledged: "
                         f"{', '.join(undeclared[:6])}"
                         f"{' ...' if len(undeclared) > 6 else ''} — a country that arrived "
                         f"in the data unnoticed is UNKNOWN, and UNKNOWN is not 'no regime'")
    expired = report.get("expired") or []
    if expired:
        return UNKNOWN, (f"{len(expired)} classification(s) past "
                         f"{MAX_ASSESSMENT_AGE_DAYS} days and therefore UNVERIFIED: "
                         f"{', '.join(expired[:6])}{' ...' if len(expired) > 6 else ''}")
    t = report.get("tallies") or {}
    backlog = report.get("backlog") or []
    tail = (f"; {len(backlog)} still unclassified and acknowledged as outstanding work "
            f"(oldest declared {report.get('backlog_oldest')})") if backlog else ""
    # "1 have no disclosure regime at all" is the line this verdict actually
    # printed on its first green run. NO_REGIME is the count most likely to sit
    # at exactly one for a long time — it is the hardest claim in the register
    # to earn — so the agreement is not decoration.
    def _n(count, plural, singular):
        return f"{count} {singular if count == 1 else plural}"
    return PASS, (f"{report.get('countries_in_scope')} countries in scope: "
                  f"{_n(t.get(REGIME_WITH_AGGREGATE, 0), 'publish', 'publishes')} a "
                  f"countable total, "
                  f"{_n(t.get(REGIME_NO_AGGREGATE, 0), 'have', 'has')} a regime that "
                  f"publishes no aggregate, "
                  f"{_n(t.get(NO_REGIME, 0), 'have', 'has')} no disclosure regime at "
                  f"all, {t.get(REFUSED, 0)} refused (publisher blocks AI agents)" + tail)


def load_measurement(path=None):
    try:
        return json.loads(Path(path or MEASUREMENT_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_measurement(report, path=None):
    path = Path(path or MEASUREMENT_PATH)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------

_LABEL = {
    REGIME_WITH_AGGREGATE: "PUBLISHES A COUNTABLE TOTAL",
    REGIME_NO_AGGREGATE:   "REGIME, NO AGGREGATE",
    NO_REGIME:             "NO DISCLOSURE REGIME",
    REFUSED:               "REFUSED (publisher disallows AI agents)",
    UNASSESSED:            "UNASSESSED",
}


def _render(report):
    lines = [f"PER-COUNTRY COVERAGE  measured_at={report.get('measured_at')}"]
    if report.get("scope_state") != MEASURED:
        lines.append(f"  [UNKNOWN] {report.get('detail')}")
        state, detail = judge(report)
        lines.append(f"  VERDICT {state.upper()}: {detail}")
        return "\n".join(lines)
    t = report.get("tallies") or {}
    for cls in CLASSIFICATIONS:
        names = sorted(k for k, v in (report.get("countries") or {}).items()
                       if v.get("class") == cls)
        if not names:
            continue
        if cls == UNASSESSED:
            # Two very different things wear this class and they must not print
            # as one list: acknowledged outstanding work, and a country that
            # arrived unnoticed. Only the second is a defect.
            undeclared = report.get("undeclared") or []
            backlog = report.get("backlog") or []
            if undeclared:
                lines.append(f"  UNDECLARED — in the corpus, in neither the register nor "
                             f"the backlog  ({len(undeclared)})")
                for name in undeclared:
                    lines.append(f"      {name}")
            if backlog:
                lines.append(f"  ACKNOWLEDGED BACKLOG — outstanding work, declared "
                             f"{report.get('backlog_oldest')}  ({len(backlog)})")
                lines.append(f"      {', '.join(backlog)}")
            continue
        lines.append(f"  {_LABEL[cls]}  ({t.get(cls, 0)})")
        for name in names:
            rec = report["countries"][name]
            flag = "  ** EXPIRED" if rec.get("state") == UNKNOWN else ""
            lines.append(f"      {name}{flag}")
            lines.append(f"          regime: {rec.get('regime')}")
            lines.append(f"          {rec.get('aggregate')}")
    ledger = report.get("refusal_ledger") or []
    if ledger:
        verified = sum(1 for r in ledger if r.get("verified_here"))
        lines.append(f"  REFUSAL LEDGER  ({len(ledger)} hosts, {verified} re-verified here) "
                     f"— do not re-probe, do not build against these")
        for r in ledger:
            alt = r.get("alternative") or "none found"
            lines.append(f"      {r['host']}  [{r.get('country')}]")
            lines.append(f"          alternative: {alt}")
    regs = report.get("per_employer_registers") or []
    naming = [r for r in regs if r.get("names_employers")]
    if regs:
        lines.append(f"  PER-EMPLOYER REGISTERS — authorities that NAME the employer "
                     f"filing a notice  ({len(naming)} found)")
        for r in regs:
            mark = "NAMES" if r.get("names_employers") else "near-miss"
            held = "in tracker" if r.get("in_tracker") else "NOT ingested"
            lines.append(f"      [{mark}] {r['jurisdiction']} ({r['country']}) — {held}")
            lines.append(f"          {r['what']}")
    for dup in report.get("vocabulary_duplicates") or []:
        lines.append(f"  VOCABULARY  '{dup['stored']}' is stored alongside "
                     f"'{dup['canonical']}' — one country, two spellings "
                     f"(alt_normalize_country, not this register)")
    state, detail = judge(report)
    lines.append(f"  VERDICT {state.upper()}: {detail}")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--regimes" in argv:
        # No network. For reviewing the register itself.
        for name in sorted(REGISTER):
            r = REGISTER[name]
            print(f"{name}\n  [{r['class']}] assessed {r['assessed']}\n"
                  f"  regime:    {r['regime']}\n"
                  f"  authority: {r.get('authority')}\n"
                  f"  threshold: {r.get('threshold')}\n"
                  f"  aggregate: {r['aggregate']}\n"
                  f"  cite:      {r['cite']}\n")
        print(f"{len(REGISTER)} entries")
        return 0
    report = classify_all()
    if "--write" in argv:
        print(f"wrote {write_measurement(report)}", file=sys.stderr)
    print(_render(report))
    state, _ = judge(report)
    return {PASS: 0, FAIL: 2, UNKNOWN: 3}[state]


if __name__ == "__main__":
    sys.exit(main())
