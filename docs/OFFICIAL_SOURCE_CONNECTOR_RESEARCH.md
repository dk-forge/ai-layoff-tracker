# Official-source connector research

This is a decision log for country-specific connectors. It exists to prevent a
future implementation from turning a search page, a paid feed, or an
unlicensed corpus into an implied live data source.

## Admission rule

Add a direct official-source connector only when all of these are true:

1. The publisher permits this automated, commercial/public-interest use, or
   gives written permission.
2. A stable, documented public interface can provide a bounded incremental
   feed or search without bypassing access controls.
3. The connector keeps the original document URL, retrieval timestamp and
   source text needed to substantiate an event.
4. Fixtures cover parsing, pagination, date boundaries and source-link output.
5. The scheduled job reports `running`, `ok` and `degraded` status through the
   existing source-health endpoint before the source is named live anywhere.

The source registry's `candidate_official_sources` field is a research queue;
it is not a coverage claim. Move a source to `live_sources` only in the same
change that ships the connector, tests, workflow and public methodology.

## Findings reviewed 2026-07-17

| Market / source | What the official publisher makes public | Decision |
|---|---|---|
| Canada — SEDAR+ | The official search page supports searching public filings and downloading public documents. SEDAR+ says continuous-disclosure documents such as news releases are immediately public. | **Candidate, not live.** No documented, permissioned incremental/bulk interface has been established for this project. Do not scrape the interactive application or imply SEDAR+ coverage. |
| United Kingdom — LSE RNS | LSE says RNS news remains searchable on its website (two years of history), but its former RSS/RNS RSS services are disabled. | **Blocked pending a licensed/API route.** Do not implement a browser scraper as a substitute for the retired feed. |
| Australia — ASX announcements | ASX publishes current and historical announcement search pages, but its current announcements page states that the content must not be used for commercial purposes. | **Do not ingest** unless ASX grants permission or a suitable licence is obtained. Public availability is not reuse permission. |
| Japan — EDINET | The Financial Services Agency provides a documented EDINET API, including a dated document-list endpoint. | **Scheduled discovery probe live (2026-07-18); connector not live.** `cron.py` now lists the previous day's official metadata twice daily and reports `edinet_jp` source health, so the public page shows the probe running — but nothing is downloaded, extracted, written as an event or claimed as coverage. Promotion still needs Japanese-language fixtures, a persisted replay cursor and an evidence-only document stage. |
| South Korea — OpenDART | The Financial Supervisory Service provides documented JSON disclosure-list endpoints. | **Scheduled discovery probe live (2026-07-18); connector not live.** `cron.py` now pages the previous day's disclosure metadata twice daily and reports `opendart_kr` source health under the same no-ingestion rule. Promotion still needs Korean-language body/evidence fixtures, a persisted replay cursor and an evidence-only document stage. |
| United Kingdom — Companies House | Companies House provides an authenticated public company-information API. | **Credential access verified for identity enrichment only; not a layoff source.** It may eventually evidence employer domicile/registered identity, but must never create or inflate a UK layoff event. |

### Primary references

- [SEDAR+ public document search](https://www.sedarplus.ca/csa-party/service/create.html?targetAppCode=csa-security&service=searchDocuments)
- [SEDAR+ explanation of public documents](https://www.sedarplus.ca/onlinehelp/filings/view-a-filing/information-shown-on-a-submitted-filing/)
- [LSE RNS access and RSS policy](https://www.londonstockexchange.com/welcome-to-london-stock-exchange)
- [ASX today's announcements](https://www.asx.com.au/asx/v2/statistics/todayAnns.do)
- [EDINET API authentication](https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1)
- [OpenDART API](https://opendart.fss.or.kr/)
- [Companies House API](https://developer.company-information.service.gov.uk/)

## Credential-access boundary

On 2026-07-17, the manual, read-only GitHub Actions workflow
`official-connector-credential-smoke.yml` successfully authenticated to
EDINET, OpenDART and Companies House (run `29605524613`). It did not download,
retain or publish filings; it only confirms that the configured secrets can
make bounded official requests. The secrets themselves are never stored in this
repository, test fixtures, workflow output or documentation.

Credential success is deliberately not an admission decision. Each source must
still pass the five admission-rule gates above, and must be marked
`discovery_only` in `railway/source_registry.py` until its complete connector
is tested and deployed.

### Read-only Companies House foundation

`railway/sources/companies_house.py` is a deliberately non-publishing
identity adapter. It accepts an already-known exact company number, returns the
official public company-profile URL and calls the address country
`registered_office_country`. It cannot search by name, create a layoff event,
set employer domicile, or infer an affected-job location. It is a future
evidence-review aid only—not a collector, coverage claim, or enrichment job.

## Next safe research order

1. Ask SEDAR+ / the Canadian Securities Administrators whether its data
   distribution service offers a public-interest licence and incremental API.
2. Ask LSE Data & Analytics for an RNS licence/API appropriate for a
   source-linked public research dataset.
3. Research public labour-ministry sources that publish event-level employer,
   count and document links, starting with the countries already named in the
   public gaps section. Apply the admission rule above before coding.

Until a connector clears this checklist, worldwide GDELT/news discovery and
reviewed company feeds remain the only described coverage path for that market.
