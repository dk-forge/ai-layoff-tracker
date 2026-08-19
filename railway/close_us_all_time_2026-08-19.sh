#!/usr/bin/env bash
# CLOSURE PACKAGE - headline_containment / us_all_time - prepared 2026-08-19.
#
# READ THIS, THEN RUN IT (or do not). It is a yes/no, not an investigation.
# Nothing here edits railway/headline_incidents.json or any baseline by hand:
# the single command at the bottom is the only path that writes both.
#
# ---------------------------------------------------------------------------
# PRECONDITION. As of 2026-08-19T02:10Z railway/headline_incidents.json still
# reads `"open": {}`, so `--close-incident` has nothing to target yet and will
# raise. A containment FAIL opens its incident under the SUBSET slice only when
# the recorder runs (.github/workflows/data-integrity.yml, 17:30 UTC daily, or
# `gh workflow run data-integrity.yml`). Run the recorder first, confirm
# `us_all_time` appears under `open`, then run this.
#
# ---------------------------------------------------------------------------
# THE PAIR IS ONE OBSERVATION, so it is judgeable. Both halves of the
# containment pair in railway/headline_baseline.json carry the SAME recorder
# stamp:
#     us_all_time         recorded_in 2026-08-18T18:27:14Z
#     worldwide_all_time  recorded_in 2026-08-18T18:27:14Z
# Not a straddled pair, not UNKNOWN. The difference below is a complement.
#
# ---------------------------------------------------------------------------
# THE ARITHMETIC, and it closes on BOTH axes with zero residual.
#
#   baseline 2026-08-18T18:27:14Z    us  6,958,685 / 43,529
#                                    ww 20,430,889 / 63,840
#   live     2026-08-19T02:05Z       us  7,038,434 / 43,570
#                                    ww 20,476,335 / 65,036
#   delta                            us    +79,749 / +41
#                                    ww    +45,446 / +1,196
#   complement (ww - us)                  -34,303 / +1,155     <- the FAIL
#
#   THE ONE INDEPENDENTLY MEASURED TERM is the employer_country fill. GitHub
#   Actions run 32200656641 ("Employer-domicile curated backfill", finished
#   2026-08-19T00:17:44Z, from PR #112 merged 00:16:55Z) printed 47 `setting
#   id=<n>: <country>` lines. 28 of them say United States. Their job counts,
#   read back off the LIVE site (CSV export, country=United States,
#   country_basis=employer), total 75,893: the 27 blank-country rows sum to
#   71,393, plus id 176883 Dow Inc. 4,500 whose country is "Multiple countries".
#
#   country_basis=any matches country OR employer_country, so all 28 entered
#   us_all_time. NONE of them changed worldwide_all_time: a blank country and
#   "Multiple countries" never excluded a row from the worldwide slice, so they
#   were already inside it. That asymmetry is the entire negative term.
#
#   us:          +79,749 = 75,893 (fill)  + 3,856 arriving jobs on +13 rows
#   worldwide:   +45,446 = 0 (fill)       + 45,446 arriving jobs on +1,196 rows
#   non-US arrivals: 45,446 - 3,856 = 41,590 jobs on 1,196 - 13 = 1,183 rows
#   complement jobs:    41,590 - 75,893 = -34,303   exact
#   complement entries:  1,183 -     28 =  +1,155   exact
#
#   WHY THIS IS "ENTIRELY EXPLAINED" AND NOT MERELY "CONSISTENT WITH":
#   the fill is measured, not fitted. Subtract it and the residual is
#   non-negative on all four axes (+3,856 / +13 US, +41,590 / +1,183 non-US).
#   A second, unnoticed re-scoring would have to show up as a NEGATIVE arrival
#   count somewhere, and there is no negative left to hide in. The average
#   arriving row is 297 jobs (US) and 35 jobs (non-US), both ordinary.
#
#   The 1,183 non-US arrivals are the Quebec and Mazovia register work that
#   landed the same evening (commits f05b72f, b6b4d53) plus routine WARN and
#   news. They are worth an eye because 1,183 rows in 7.6 hours is a lot, but
#   they CANNOT manufacture this FAIL: an arrival can only push the complement
#   positive.
#
# ---------------------------------------------------------------------------
# THE 28 AFFECTED ROW IDS, enumerated. company, jobs, country before the fill:
#   60834  Google 12,000 (blank)          176911 Estee Lauder 9,000 (blank)
#   60872  Xerox 3,000 (blank)            177067 Etsy 220 (blank)
#   176541 Cornerstone OnDemand 270       177158 Stryker 3 (blank)
#   176544 Sabre 800 (blank)              177159 SLB Limited/NV 224 (blank)
#   176546 Groupon 2,700 (blank)          177181 Wolfspeed 570 (blank)
#   176607 Harley-Davidson 500 (blank)    177187 NL Industries 2 (blank)
#   176684 Stepan 100 (blank)             177191 Dixie Group 14,826 (blank)
#   176688 Amazon 16,000 (blank)          177194 Humacyte 45 (blank)
#   176733 Digi International 20 (blank)  177216 Applied Aerospace 4,320 (blank)
#   176736 Tilray 1 (blank)               177221 PlayStudios 177 (blank)
#   176770 Cornerstone OnDemand 115       177222 SunPower 820 (blank)
#   176863 Hyster-Yale 575 (blank)        177340 BILL Holdings 30 (blank)
#   176883 Dow Inc. 4,500 (Multiple countries)
#   176903 Alector 75 (blank)             177401 Google 4,500 (blank)
#   176909 Graphic Packaging 500 (blank)
#
# ---------------------------------------------------------------------------
# THE PROPOSED REPLACEMENT BASELINE is the live reading itself, because nothing
# is wrong with it: 7,038,434 jobs on 43,570 entries, read 2026-08-19T02:05Z.
# The fill is correct behaviour and the documented purpose of country_basis=any
# (a US-headquartered company's unplaced global cut is findable under a US
# filter). No row is mis-scored, so no correction is proposed and the figure to
# adopt is the one the site is publishing.
#
# RE-READ IT BEFORE YOU RUN THIS. Hours will have passed and rows arrive twice
# a day. Substitute the two numbers below with what this prints:
#   curl -s -A 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)' \
#     "https://asktherecruiter.com/blog/wp-json/layoffs/v1/aggregate?country=United+States&country_basis=any&cb=$RANDOM" \
#     | python3 -c "import json,sys;t=json.load(sys.stdin)['totals'];print(t['jobs'],t['entries'])"
#
# AFTER CLOSING, the pair reports UNKNOWN and not PASS until the next recorder
# run advances us_all_time and worldwide_all_time together. That is by design
# (close_incident gives the closed slice its own epoch) and is the same thing
# the 2026-08-15 ai_all_time note warned about. It is not a second failure.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

REASON='Correct behaviour, not bad data, and explained to the job and to the row with zero residual. Between the 2026-08-18T18:27:14Z baseline and the 2026-08-19T02:05Z reading, GitHub Actions run 32200656641 (Employer-domicile curated backfill, from PR #112) wrote employer_country on 47 rows and set 28 of them to United States. Those 28 carry 75,893 jobs, measured back off the live site: the 27 blank-country rows total 71,393 and id 176883 Dow Inc. adds 4,500 on a Multiple countries row. country_basis=any matches country OR employer_country, so all 28 entered us_all_time, while none of them changed worldwide_all_time, because a blank country and Multiple countries never excluded a row from the worldwide slice. That asymmetry is the whole negative term. Arithmetic: us moved +79,749 jobs on +41 entries = 75,893 fill plus 3,856 arriving jobs on 13 rows; worldwide moved +45,446 on +1,196, all arrivals, of which 41,590 jobs on 1,183 rows are non-US; the complement is 41,590 minus 75,893 = -34,303 jobs and 1,183 minus 28 = +1,155 entries, which is the finding exactly. The fill is the only independently measured term, and subtracting it leaves a residual that is non-negative on all four axes, so no second re-scoring can be hiding here: it would have to appear as a negative arrival count. The 1,183 non-US arrivals are the Quebec and Mazovia register work of the same evening plus routine WARN and news, and an arrival can only push the complement positive, so they cannot cause this FAIL. The fill is the documented purpose of country_basis=any: a US-headquartered employer unplaced global cut becomes findable under a US filter. No row is mis-scored and no correction is required, so the replacement baseline is the published figure itself.'

python3 data_integrity.py --close-incident us_all_time \
  --reviewed-by "dak (adjudicated; findings independently re-verified in a Claude Code session 2026-08-19)" \
  --reason "$REASON" \
  --rows 60834 60872 176541 176544 176546 176607 176684 176688 176733 176736 \
         176770 176863 176883 176903 176909 176911 177067 177158 177159 177181 \
         177187 177191 177194 177216 177221 177222 177340 177401 \
  --replacement-jobs 7038434 \
  --replacement-entries 43570
