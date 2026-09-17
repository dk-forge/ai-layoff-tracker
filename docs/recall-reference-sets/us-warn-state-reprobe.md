# US WARN eight-state re-probe

Generated 2026-09-17T17:22:10Z. Definition document: `docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md`.

This re-probes NY, IL, OH, PA, WA, GA, NJ and MI against the four eligibility criteria fixed in the definition document. **It has NOT produced a recall figure for any of these states and does not build a frame or draw a sample.** Cost: $0.00, no model calls.

| State | Prior verdict (2026-08-13) | This run | Failed criterion | HTTP | Reason |
|---|---|---|---|---|---|
| NY | out (b) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |
| IL | out (b) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |
| OH | out (a) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |
| PA | out (b) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |
| WA | out (b) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |
| GA | out (b) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |
| NJ | out (b) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |
| MI | out (b) | **OUT** | b | 200 | HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13 |

## Criteria

- **(a)** reachable under a plain browser User-Agent and permitted by robots.txt
- **(b)** statically machine-readable -- a document or a documented open-data API, not a JavaScript-only page, a proprietary BI extract, or an undocumented internal endpoint
- **(c)** complete over the window in one document or one date-bounded query
- **(d)** publishes employer, an absolute headcount, and a notice or received date

## Detail

### NY -- New York State Department of Labor
- URL: https://dol.ny.gov/warn-dashboard
- robots.txt: permitted (`https://dol.ny.gov/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- undocumented endpoint: the vizql bootstrap route carries no session id and is an undocumented internal API; not used and not promoted to eligible
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

### IL -- Illinois Department of Commerce and Economic Opportunity
- URL: https://dceo.illinois.gov/workforcedevelopment/warn.html
- robots.txt: permitted (`https://dceo.illinois.gov/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

### OH -- Ohio Department of Job and Family Services
- URL: https://jfs.ohio.gov/job-workforce-services/job-programs-and-services/submit-a-warn-notice/current-public-notices-of-layoffs-and-closures
- robots.txt: permitted (`https://jfs.ohio.gov/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

### PA -- Pennsylvania Department of Labor and Industry
- URL: https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices
- robots.txt: permitted (`https://www.pa.gov/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

### WA -- Washington State Employment Security Department
- URL: https://esd.wa.gov/employer-requirements/layoffs-and-employee-notifications/worker-adjustment-and-retraining-notification-warn-layoff-and-closure-database
- robots.txt: permitted (`https://esd.wa.gov/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

### GA -- Technical College System of Georgia
- URL: https://www.tcsg.edu/warn-public-view/
- robots.txt: permitted (`https://www.tcsg.edu/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- undocumented endpoint: sources/warn_custom.fetch_ga reads a nonce'd wp-admin/admin-ajax.php GravityView endpoint for ingestion; it is undocumented and public only by discovery, so it is not promoted to eligible under (b)
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

### NJ -- New Jersey Department of Labor and Workforce Development
- URL: https://www.nj.gov/labor/employer-services/warn/
- robots.txt: permitted (`https://www.nj.gov/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

### MI -- Michigan Department of Labor and Economic Opportunity
- URL: https://www.michigan.gov/leo/bureaus-agencies/wd/data-public-notices/warn-notices
- robots.txt: permitted (`https://www.michigan.gov/robots.txt`, HTTP 200)
- static readability: False -- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13
- undocumented endpoint: sources/warn_custom.fetch_mi reads a Sitecore SXA search results JSON endpoint for ingestion; it is an undocumented internal API and is not promoted to eligible under (b)
- verdict: **OUT** on criterion (b)
- HTTP 200 but no populated data rows found in the served markup -- the table is populated client-side, same as 2026-08-13

