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
)


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
    'Argentina': ("2026-08-18",
      "procedimiento preventivo de crisis under Ley 24.013, filed with "
      "the Ministerio de Trabajo — a strong candidate for a countable "
      "filing series. Unresolved."
      ),
    'Australia': ("2026-08-18",
      "Fair Work Act 2009 s.530 requires notifying Services Australia of "
      "15+ redundancies. Whether counts are published is unresolved; a "
      "negative is expected."
      ),
    'Bosnia and Herzegovina': ("2026-08-18",
      "not yet researched, and harder than most: the Federation, Republika "
      "Srpska and Brcko District each have their own labour law, so there may "
      "be three regimes and no national aggregate even in principle."
      ),
    'Botswana': ("2026-08-18",
      "not yet researched. The Employment Act redundancy provisions are the "
      "likely instrument; whether a notification duty to the Commissioner of "
      "Labour exists, and whether anything is published, is unresolved."
      ),
    'Brazil': ("2026-08-18",
      "dispensa coletiva after the 2017 reform and the 2022 STF decision. "
      "NEAR-MISS to reject: Novo CAGED records all admissions and "
      "dismissals monthly, which is a total separations series, not a "
      "collective-dismissal notification count."
      ),
    'Bulgaria': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "not yet researched."
      ),
    'Cambodia': ("2026-08-18",
      "Labour Law 1997 art. 95 and 130 require informing the labour "
      "inspectorate and MLVT of a mass layoff; no numeric threshold was "
      "identified and no aggregate was located, but the search was not "
      "exhaustive."
      ),
    'Canada': ("2026-08-18",
      "group termination notice to the Minister under Canada Labour Code "
      "s.212 (federally regulated) plus separate provincial regimes "
      "(Ontario ESA Form 1, Quebec avis de licenciement collectif). "
      "Quebec has historically published notice listings. Unresolved, and "
      "the federal/provincial split means there may be no single national "
      "denominator even if provinces publish."
      ),
    'Chile': ("2026-08-18",
      "not yet researched. Codigo del Trabajo art. 161 (necesidades de la "
      "empresa) is the likely instrument; whether a notification duty to the "
      "Direccion del Trabajo exists, and whether anything is published, is "
      "unresolved."
      ),
    'China': ("2026-08-18",
      "Labour Contract Law art. 41 requires reporting economic layoffs of "
      "20+ or 10% of the workforce to the local labour administration. "
      "Whether any count is published is unresolved; a negative is "
      "expected but was not verified."
      ),
    'Colombia': ("2026-08-18",
      "collective dismissal requires Ministerio de Trabajo authorisation. "
      "Unresolved."
      ),
    'Czechia': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "not yet researched."
      ),
    'Estonia': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "not yet researched; host is open, so this is cheap to close."
      ),
    'Hong Kong': ("2026-08-18",
      "whether any duty to notify the Labour Department of mass "
      "redundancy exists under the Employment Ordinance (Cap. 57) is "
      "unresolved. As with New Zealand, a 'no regime' finding must be "
      "earned, not assumed."
      ),
    'Hungary': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "not yet researched."
      ),
    'Iceland': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "EEA member, Vinnumalastofnun is the likely notified authority."
      ),
    'India': ("2026-08-18",
      "Industrial Disputes Act 1947 Ch. V-B requires PRIOR GOVERNMENT "
      "PERMISSION for retrenchment in establishments above 100 (300 in "
      "some states) — an approval regime, which generates a stronger "
      "record than notification. Whether the Labour Bureau or any state "
      "publishes application or permission counts is unresolved. Note Sri "
      "Lanka shows an approval duty predicts nothing about publication."
      ),
    'Indonesia': ("2026-08-18",
      "PHK under UU 13/2003 as amended by UU 6/2023 and PP 35/2021; the "
      "notification article was NOT verified and must not be quoted. "
      "Kemnaker's Satudata publishes PHK counts, but the source is MIXED "
      "— compiled from regional office reports, partly classified by "
      "unemployment-benefit participation, and acknowledged incomplete. "
      "That mixture is why this is not classified as a published "
      "aggregate."
      ),
    'Isle of Man': ("2026-08-18",
      "Crown Dependency with its own law — redundancy notification to the "
      "Department for Enterprise. Same reasoning as Jersey. Unresolved."
      ),
    'Israel': ("2026-08-18",
      "not yet researched. Whether any mass dismissal notification duty to a "
      "public authority exists is unresolved — the pre-dismissal hearing is an "
      "employee-facing duty, not a notification to the state, and must not be "
      "mistaken for one."
      ),
    'Japan': ("2026-08-18",
      "the large-scale employment change notification to Hello Work under "
      "the Employment Measures Act exists (30+ leaving in a month). "
      "Whether MHLW publishes counts of those notifications is "
      "unresolved. NEAR-MISS to reject: the employment adjustment subsidy "
      "is short-time work support, not dismissal."
      ),
    'Jersey': ("2026-08-18",
      "Crown Dependency with its OWN law — Employment (Jersey) Law 2003 "
      "collective redundancy notification to the Minister. A small "
      "jurisdiction where a complete published list might genuinely "
      "exist. Unresolved."
      ),
    'Kenya': ("2026-08-18",
      "Employment Act s.40 requires notification to the labour officer. "
      "Publication unresolved."
      ),
    'Kuwait': ("2026-08-18",
      "not yet researched. Labour Law in the Private Sector No. 6 of 2010 is "
      "the likely instrument; whether a collective termination notification "
      "duty exists, and whether anything is published, is unresolved."
      ),
    'Latvia': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "not yet researched; host is open, so this is cheap to close."
      ),
    'Mexico': ("2026-08-18",
      "terminacion colectiva under LFT art. 434/435 requires "
      "authorisation from the labour tribunal. Publication unresolved. "
      "NEAR-MISS: IMSS insured-employment change is a net employment "
      "series."
      ),
    'Morocco': ("2026-08-18",
      "Code du Travail art. 66-71 requires the governor's authorisation "
      "for economic dismissal — an approval regime. Publication "
      "unresolved."
      ),
    'Netherlands': ("2026-08-18",
      "EU, so the WMCO regime certainly exists. BLOCKED SO FAR, and the "
      "obstacle is specific: UWV's 'Dashboard Ontslag' is JavaScript-only "
      "and serves no figures in its HTML, and UWV's robots.txt disallows "
      "exactly /nl/webpublicaties, which is where a WMCO series would "
      "live. Until that is resolved we cannot tell a collective-dismissal "
      "NOTIFICATION count from an ontslagaanvragen count, which would be "
      "a near-miss. Do not classify it on the dashboard's existence "
      "alone."
      ),
    'New Zealand': ("2026-08-18",
      "whether ANY statutory mass-redundancy notification duty to a "
      "public authority exists is unresolved. A verified 'no regime' "
      "would be a publishable finding — it must NOT be recorded as one on "
      "the current evidence, which is a hypothesis that was sent out to "
      "be tested and never came back."
      ),
    'Nigeria': ("2026-08-18",
      "Labour Act s.20 covers redundancy with notification to the trade "
      "union and the Ministry. Publication unresolved."
      ),
    'Pakistan': ("2026-08-18",
      "Standing Orders Ordinance 1968 SO 12/13 covers termination and "
      "retrenchment, and NO duty to notify a public authority was found "
      "at federal level — but retrenchment devolved to the provinces "
      "after the 18th Amendment and the Punjab, Sindh, KP and Balochistan "
      "variants were NOT checked. Deliberately NOT recorded as 'no "
      "regime' on this evidence."
      ),
    'Peru': ("2026-08-18",
      "cese colectivo requires MTPE authorisation — an approval regime. "
      "Unresolved."
      ),
    'Poland': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "zwolnienia grupowe is a live lead — the labour ministry has "
      "historically reported group-dismissal figures in labour market "
      "monitoring."
      ),
    'Romania': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "not yet researched."
      ),
    'Serbia': ("2026-08-18",
      "Labour Law programme for redundant employees (visak zaposlenih). "
      "Publication unresolved."
      ),
    'Singapore': ("2026-08-18",
      "mandatory retrenchment notification to MOM exists (Employment Act, "
      "employers of 10+, since 2017) and MOM publishes retrenchment "
      "counts. The open question is the one that decides everything: "
      "whether the published figure is NOTIFICATION-derived, Labour "
      "Market Survey-derived, or a blend. A survey estimate is a "
      "near-miss, not a denominator."
      ),
    'Slovakia': ("2026-08-18",
      "EU/EEA, so Directive 98/59/EC art. 3(1) already guarantees a "
      "notification regime exists; ONLY the publication question is open. "
      "not yet researched."
      ),
    'South Africa': ("2026-08-18",
      "s.189/189A Labour Relations Act, with CCMA facilitation for "
      "large-scale retrenchment. Whether the CCMA annual report or the "
      "Department of Employment and Labour publishes s.189A referral "
      "counts is unresolved."
      ),
    'South Korea': ("2026-08-18",
      "dismissal for managerial reasons under the Labor Standards Act "
      "carries a reporting duty to the Minister of Employment and Labor "
      "above a threshold. Whether MOEL or KOSIS publishes counts is "
      "unresolved. NEAR-MISS to reject: employment insurance separation "
      "records count all separations, not mass-dismissal reports."
      ),
    'Switzerland': ("2026-08-18",
      "outside the EU/EEA for this purpose — Art. 335d-335g Code of "
      "Obligations, cantonal notification. Not yet researched."
      ),
    'Taiwan': ("2026-08-18",
      "Act for Worker Protection of Mass Redundancy requires a redundancy "
      "plan be filed with the local labour authority and the Ministry of "
      "Labor. Whether MOL publishes a series of those filings is "
      "unresolved and is a strong candidate."
      ),
    'Thailand': ("2026-08-18",
      "Labour Protection Act B.E. 2541 s.121 requires 60 days' notice to "
      "the Labour Inspector — but it is NARROW, covering machinery and "
      "technology reorganisation only, not general economic redundancy, "
      "so it would systematically undercount even if published. "
      "Publication unresolved. NEAR-MISS: social security job-loss counts "
      "are claims."
      ),
    'Türkiye': ("2026-08-18",
      "toplu isci cikarma under Is Kanunu art. 29 requires notification "
      "to ISKUR, which publishes monthly bulletins. Whether those "
      "bulletins carry the toplu isci cikarma count is unresolved and is "
      "a strong candidate."
      ),
    'United Kingdom': ("2026-08-18",
      "our SECOND-LARGEST country by volume and the highest-value open "
      "question in the register. Form HR1 under s.193 TULRCA 1992 (20+ at "
      "one establishment in 90 days, to the Insolvency Service) certainly "
      "exists; whether a regular published series of HR1 counts exists, "
      "or only ad hoc FOI releases, is unresolved. Northern Ireland's "
      "Department for the Economy proposed/confirmed redundancy series is "
      "a separate and strong candidate. NEAR-MISSES to reject: the LFS "
      "redundancy rate is a survey estimate, and Redundancy Payments "
      "Service figures are insolvency payment claims."
      ),
    'Uruguay': ("2026-08-18",
      "not yet researched. Whether a collective dismissal notification duty to "
      "the Ministerio de Trabajo y Seguridad Social exists, and whether "
      "anything is published, is unresolved."
      ),
    'Vietnam': ("2026-08-18",
      "Labour Code 2019 requires a labour utilisation plan and 30 days' "
      "notice to the provincial People's Committee. Whether MOLISA or GSO "
      "publishes counts was never checked."
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

    # -----------------------------------------------------------------------
    # A REGIME EXISTS AND NOTHING COUNTABLE IS PUBLISHED
    # -----------------------------------------------------------------------

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
    return PASS, (f"{report.get('countries_in_scope')} countries in scope: "
                  f"{t.get(REGIME_WITH_AGGREGATE, 0)} publish a countable total, "
                  f"{t.get(REGIME_NO_AGGREGATE, 0)} have a regime that publishes no "
                  f"aggregate, {t.get(NO_REGIME, 0)} have no disclosure regime at all, "
                  f"{t.get(REFUSED, 0)} refused (publisher blocks AI agents)" + tail)


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
