# Country source research — July 2026 sweep

Compiled 2026-07-18 by a four-region parallel research pass (Europe, Americas,
Asia-Pacific, Middle East/Africa/other) plus a synthesis stage; 93 sources
were checked against the tracker's admission rules. Nothing was signed up
for, registered, or scraped during this research. This document extends —
and does not replace — `OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md`: every
admission still requires the permitted-interface, fixtures, evidence-retention
and health-reporting gates recorded there, and no country may be claimed
covered without a tested permitted connector.

# EU/Americas/APAC/MEA source synthesis — admission pipeline

## 1. Top-10 admission shortlist (permitted + machine-readable, highest value first)

| # | Source | Why | Admission plan (fixture / test / health gate) |
|---|--------|-----|-----------------------------------------------|
| 1 | **Brazil — CVM IPE filings index** (dados.cvm.gov.br, ODbL) | Company-level Fatos Relevantes, weekly CSV/ZIP since 2003 — a true 8-K analog with an explicit commercial license | Discovery-only client on the yearly CSV index; fixture = one real CSV slice with a Fato Relevante row; test = category filter + doc-URL construction + ODbL attribution string; health gate = index fetched AND row count > 0 per run; persist cursor only after full index parse; PT-language prompt fixture for the extractor |
| 2 | **Canada (Quebec) — MESS monthly licenciements collectifs PDF** | Only Canadian WARN analog with employer names + enterprise numbers; predictable URL pattern verified 2024-09→2026-05 | PDF-parser collector (warn_import-style bulk upsert); fixture = one committed real monthly PDF; test = parser extracts employer/address/date rows and fails loudly on layout drift; health gate = current-month PDF exists at pattern URL; send licensing-courtesy email to avislicenciementcollectif@mess.gouv.qc.ca before go-live |
| 3 | **Singapore — MOM retrenchment stats via data.gov.sg** | Singapore Open Data Licence explicitly permits commercial reuse; keyless datastore JSON API | announcement-survey-style reconciliation series (not events); fixture = recorded datastore_search JSON; test = quarterly aggregate parse + attribution link; health gate = latest quarter present within expected lag |
| 4 | **Taiwan — MOL mass-layoff open data (datasets 27505/27508)** | OGDL v1 (commercial OK), verified working JSON REST endpoints | Annual-aggregate stats collector; fixture = downloaded JSON; test = year/firms/headcount schema guard (it must NOT be mistaken for company-level); health gate = endpoint 200 + newest year ≥ last seen |
| 5 | **Italy — INPS CIG open data** | CC-BY 4.0 via dati.gov.it, monthly CSV/XML authorized-hours by region/sector | Reconciliation/context series; fixture = one monthly CSV; test = region/sector aggregation totals; health gate = new month within ~45 days |
| 6 | **Italy — Ministero del Lavoro weekly CIGS decree lists** (conditional) | Only company-level official EU source in the set; weekly, per-company causale/decree/period | Blocked on: license confirmation with ministry + labeling decrees as "restructuring precursor," not layoff counts; fixture = one committed UTF-16 Word-HTML file; test = tolerant parser that hard-fails on structure drift; health gate = weekly index updated in last 10 days |
| 7 | **Norway — NAV mass-dismissal monthly Excel** | Stable monthly .xlsx, history to 1960 | Verify NLOD applicability first; aggregate reconciliation series; fixture = one .xlsx; test = businesses/employees split parse; health gate = new file each month |
| 8 | **Belgium — FOD Werkgelegenheid quarterly PDFs** (conditional) | Official, names companies with headcounts — but narrative prose, 3–12 mo lag | Confirm reuse terms with FOD first; quarterly manual-assisted parse (LLM extraction over PDF text with human review), not fully automated; fixture = 2025 annual PDF excerpt; health gate = quarterly report published |
| 9 | **Spain (Madrid) — ERE record-level CKAN** | CC-BY 4.0, CSV/JSON verified — but anonymized and regional | Enrichment-only adapter (never creates entries): match Madrid expedientes to existing news events by date/municipality/CNAE; test = header schema guard confirming no company-name field; health gate = dataset refresh timestamp |
| 10 | **Denmark — Jobindsats varsel API** | Documented JSON/CSV API v3, monthly at ~8–10 working days lag | Blocked on: key application to jobindsats-api@star.dk (user decision — it is a registration); once keyed, EDINET-style env-var credential client; fixture = recorded API JSON; health gate = new month + key-validity check with secret-free errors |

Honorable mentions (watchlist, not shortlist): Mexico IMSS open data (permitted CSV but aggregate + http-only), Israel TASE Maya API ($130/mo budget decision), Argentina CNV / Colombia SIMEV / Chile CMF (public but no documented interface yet — re-check for JSON backends), Turkey KAP (contact MKK).

## 2. Do-not-ingest (with reasons)

**Exchange terms prohibit automated reuse/redistribution** (same class as the prior ASX/LSE decisions):
- India NSE/BSE — redistribution requires signed paid data agreement
- Singapore SGX — copying/storing requires written permission
- Hong Kong HKEX — explicit ban on scripted access and text/data mining
- New Zealand NZX — distributor agreement required; "view-only" ToU
- Indonesia IDX — non-commercial only + explicit scraping ban
- Philippines PSE EDGE — anti-automation terms, IP-blocking reserved
- Thailand SET — announcement feeds are paid licensed products
- South Africa JSE SENS — commercial/derived use expressly prohibited
- Nigeria NGX — terms forbid copying/redistribution
- Saudi Tadawul — bot-blocking host, no permitted programmatic interface
- Egypt EGX — connection resets on non-browser clients, terms unverifiable
- Russia e-disclosure.ru — structurally incomplete by design (sanctions carve-outs) + sanctions exposure

**Statutory notification exists but is never published (no public interface):**
- Germany BA §17 KSchG (protected social data), Netherlands UWV WMCO, Finland TE-offices, Ireland DETE CRN1, Switzerland cantonal notices, Austria AMS Frühwarnsystem, Canada federal ESDC + Ontario/BC, Mexico STPS, Argentina PPCE, Colombia MinTrabajo, Vietnam DOLISA, Israel Employment Service, Turkey İŞKUR, UAE MOHRE

**Aggregate-only under restrictive terms:**
- Portugal DGERT — all-rights-reserved PDFs
- Chile Dirección del Trabajo — aggregate PDFs, no employer names

## 3. Newspapers-only fallback by country (GDELT/NewsAPI allowlist ONLY — never direct scraping)

| Country | Outlets |
|---|---|
| Germany | Handelsblatt, FAZ |
| Netherlands | FD, NRC |
| France | Les Echos, La Tribune |
| Sweden | Dagens Industri, SvD Näringsliv |
| Denmark | Børsen, Berlingske |
| Norway | Dagens Næringsliv, E24 (mostly free) |
| Finland | Kauppalehti, Helsingin Sanomat |
| Ireland | Irish Times, Irish Independent, RTÉ (free) |
| Poland | Puls Biznesu, Rzeczpospolita |
| Switzerland | NZZ, Handelszeitung |
| Austria | Die Presse, Der Standard (free) |
| Portugal | Jornal de Negócios, ECO (free) |
| Canada (non-QC) | Globe and Mail, Financial Post |
| Mexico | El Economista, El Financiero |
| Argentina | Ámbito, El Cronista |
| Chile | Diario Financiero, La Tercera/Pulso |
| Colombia | La República, Portafolio |
| India | Economic Times, Mint |
| Hong Kong | SCMP, HKET |
| New Zealand | NZ Herald, BusinessDesk |
| Indonesia | Bisnis Indonesia, Kontan |
| Malaysia | The Edge Malaysia, The Star |
| Philippines | BusinessWorld, Inquirer Business |
| Vietnam | VnExpress, VnEconomy |
| Thailand | Bangkok Post, Krungthep Turakij |
| Israel | CTech/Calcalist (free, dedicated layoffs tag), Globes EN |
| Turkey | Dünya, Hürriyet Daily News |
| UAE | The National, Gulf News |
| Saudi Arabia | Argaam EN (relays Tadawul disclosures), Arab News |
| South Africa | Moneyweb, BusinessLIVE (do not use Moneyweb's SENS archive as a SENS backdoor) |
| Nigeria | BusinessDay NG, Nairametrics |
| Egypt | Ahram Online, Daily News Egypt |
| Russia | Kommersant, RBC, The Bell (censorship caveat) |
| Ukraine | Ekonomichna Pravda, Kyiv Independent |

## 4. Existing-pattern mapping (which collector each candidate resembles)

Existing patterns in `/Users/dakotta/Projects/atr-layoff-tracker/railway/sources/`: **EDINET JP** = keyed official document-list API, discovery-only, cursor after complete list call; **OpenDART KR** = keyed paged disclosure-list API with non-English docs + evidence-only doc stage; **Companies House UK** = keyed read-only enrichment lookup, never creates events. Two keyless patterns also apply: `warn_import.py` (official-notice bulk upsert, no LLM) and `survey_reconcile.py` (aggregate reconciliation series).

| Candidate | Closest pattern | Notes |
|---|---|---|
| Brazil CVM IPE | **EDINET JP** | Dated filing-list index → doc URLs → LLM extraction; keyless, weekly CSV instead of daily JSON; needs PT fixtures like OpenDART's Korean ones |
| Quebec MESS | **warn_import.py** (none of the three) | Keyless official-notice bulk upsert; WARN dedup-exemption logic likely applies |
| Singapore data.gov.sg | **survey_reconcile.py** | Keyless JSON API; EDINET-shaped list call but stats, not events |
| Taiwan MOL open data | **survey_reconcile.py** | Keyless REST, annual aggregates |
| Italy INPS CIG | **survey_reconcile.py** | Keyless CSV downloads |
| Italy CIGS decrees | **warn_import.py** with EDINET-style index→doc split | Keyless scrape of official bulletin; fragile-format hard-fail required |
| Norway NAV | **survey_reconcile.py** | Keyless monthly Excel |
| Belgium FOD | **warn_import.py** (degraded: PDF + human review) | Keyless quarterly bulletin |
| Madrid ERE | **Companies House UK** | Enrichment-only, never creates events, keyless |
| Denmark Jobindsats | **OpenDART KR / EDINET JP** | The only true credential match: env-var API key, secret-free error classification, keyed JSON list endpoint |

## Appendix: all 93 assessed sources

| Country | Source | Type | Access | Recommendation |
|---|---|---|---|---|
| Argentina | CNV — Hechos Relevantes portal | exchange_disclosure | free | research_further — legally public information with an open-government mandate, but no documented ingest interface yet; check whether the SitioWeb portal exposes a stable JSON backend before deciding. |
| Argentina | News fallback: Ámbito Financiero + El Cronista | reputable_newspaper | free | research_further — primary practical event source given PPCE filings are not public. |
| Argentina | Procedimiento Preventivo de Crisis (PPCE) — Secretaría de Trabajo | official_bulletin | unclear | do_not_ingest — the filing system is real but has no public interface; revisit if datos.gob.ar ever publishes a PPCE dataset. |
| Austria | AMS Frühwarnsystem (§45a AMFG early-warning notifications) | official_bulletin | unclear | do_not_ingest — no public interface; news fallback Die Presse (diepresse.com), Der Standard (derstandard.at, free access) |
| Austria | Die Presse (diepresse.com) / Der Standard (derstandard.at) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Belgium | FOD Werkgelegenheid (FPS Employment) — collective-dismissal notification statistics & quarterly | official_bulletin | free | research_further — company names are official and citable but only inside quarterly narrative PDFs (3-12 month lag, fragile parsing); confirm reuse terms with FOD before automated ingest |
| Brazil | CVM Portal de Dados Abertos — Cias Abertas IPE filings index (includes Fatos Relevantes) | official_api | free | admit_candidate — stable, documented, explicitly licensed machine-readable interface; the strongest new source in the Americas (Brazilian 8-K analog). Note weekly cadence and Portuguese-language documents for the LLM ext |
| Brazil | Novo CAGED microdata (PDET, Ministério do Trabalho e Emprego) | statistical_agency | free | research_further — permitted and machine-readable but structurally unable to produce company-attributed layoff events; useful only as a macro indicator. |
| Canada | News fallback: The Globe and Mail (Report on Business) + Financial Post | reputable_newspaper | paid | research_further — use only as GDELT/NewsAPI source-whitelist hints for ON/BC/federal layoffs that Quebec's list won't catch. |
| Canada (Ontario/BC) | Ontario ESA Form 1 mass-termination notices / BC group termination notices | official_bulletin | unclear | do_not_ingest — no public data product; Quebec is the only Canadian province publishing notices. |
| Canada (Quebec) | Ministère de l'Emploi et de la Solidarité sociale (MESS) — Liste mensuelle des avis de licencie | official_bulletin | free | admit_candidate — the only true WARN analog in Canada with public employer-level data; stable monthly official publication, but requires a PDF parser and a licensing-courtesy note (factual data, no explicit license). |
| Canada (federal) | ESDC — Canada Labour Code group termination notices (form ESDC-LAB1197) | official_bulletin | unclear | do_not_ingest — filing obligation exists but there is no public interface to ingest. |
| Chile | CMF — Hechos Esenciales (material events of securities issuers) | exchange_disclosure | free | research_further — public and free with an official push channel (email subscription) that could be a permitted ingest path; confirm subscription terms before building. |
| Chile | Dirección del Trabajo — termination-notice (carta de aviso) statistics | statistical_agency | free | do_not_ingest — aggregate PDFs with no company attribution; not worth a collector. |
| Chile | News fallback: Diario Financiero | reputable_newspaper | paid | research_further — news fallback for company-attributed layoff events. |
| Colombia | Ministerio del Trabajo — collective-dismissal (despido colectivo) authorizations | official_bulletin | unclear | do_not_ingest — authorization regime exists but is not published; monitor datos.gov.co for a future dataset. |
| Colombia | News fallback: La República + Portafolio | reputable_newspaper | free | research_further — practical event-level fallback given the ministry registry is not public. |
| Colombia | Superintendencia Financiera — Información Relevante (SIMEV/RNVE) | exchange_disclosure | free | research_further — public and free but web-portal-only today; check for a Socrata mirror or portal JSON backend before committing. |
| Denmark | Børsen (borsen.dk) / Berlingske (berlingske.dk) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Denmark | STAR / Jobindsats.dk — antal varslinger om afskedigelser (notified dismissals) + Jobindsats API | statistical_agency | free_with_key | research_further — clean documented API but aggregate-only and key requires application; useful for reconciliation stats, not entries; news fallback Børsen (borsen.dk), Berlingske (berlingske.dk) |
| Egypt | EGX (Egyptian Exchange) company disclosures/news | exchange_disclosure | unclear | do_not_ingest — no stable or verifiably permitted interface; Egypt is newspapers-only. |
| Egypt | News fallback: Ahram Online (english.ahram.org.eg) + Daily News Egypt (dailynewsegypt.com) | reputable_newspaper | free | research_further — allowlist Ahram Online and Daily News Egypt; note EnterpriseAM as a paid option if Egypt coverage ever becomes a priority. |
| Finland | Kauppalehti (kauppalehti.fi) / Helsingin Sanomat (hs.fi) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Finland | No government register (TE-office change-negotiation notifications unpublished); SAK union yt/c | official_bulletin | free | do_not_ingest (no official interface); news fallback Kauppalehti (kauppalehti.fi), Helsingin Sanomat (hs.fi); optionally research SAK's list as a manual cross-check only |
| France | DARES — PSE / ruptures collectives dashboards (data from RUPCO); RUPCO portal itself | statistical_agency | free | research_further — aggregate-only and anti-bot on the primary site; no public company-level register exists; news fallback Les Echos (lesechos.fr), La Tribune (latribune.fr) |
| France | Les Echos (lesechos.fr) / La Tribune (latribune.fr) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Germany | Bundesagentur für Arbeit — Anzeigen über Entlassungen (§17 KSchG mass-dismissal notifications) | statistical_agency | unclear | do_not_ingest — no public interface exists; a formal data request to BA Statistik-Service is the only route (out of scope per no-signup rule); rely on news fallback |
| Germany | Handelsblatt (handelsblatt.com) / Frankfurter Allgemeine Zeitung (faz.net) | reputable_newspaper | paid | research_further — use only via existing GDELT/NewsAPI ingest and for manual verification; do not scrape directly |
| Hong Kong | HKEXnews listed-company announcements | exchange_disclosure | free | do_not_ingest — express prohibition on automated access and redistribution |
| Hong Kong | South China Morning Post (scmp.com) — news fallback; runner-up: Hong Kong Economic Times (hket. | reputable_newspaper | free | research_further — news fallback via GDELT allowlist since HK has no official layoff register and HKEX is blocked |
| India | Labour Bureau (Ministry of Labour & Employment) — Statistics on Industrial Disputes, Closures,  | statistical_agency | free | research_further — permitted and official but annual aggregate PDFs with multi-year lag; unusable for event-level tracking, possibly useful for context stats |
| India | NSE / BSE corporate announcements (exchange filing feeds) | exchange_disclosure | free | do_not_ingest — public site exists but redistribution is contractually prohibited without a paid NSE/BSE data agreement |
| India | The Economic Times (economictimes.indiatimes.com) — news fallback; runner-up: Mint (livemint.co | reputable_newspaper | free | research_further — treat as priority outlets inside the existing GDELT/NewsAPI pipeline since India's official channels are blocked or lagged |
| Indonesia | Bisnis Indonesia (bisnis.com) — news fallback; runner-up: Kontan (kontan.co.id) | reputable_newspaper | free | research_further — GDELT allowlist outlets given IDX is blocked and Kemnaker is aggregate-only |
| Indonesia | IDX (Indonesia Stock Exchange) listed-company disclosures | exchange_disclosure | free | do_not_ingest — non-commercial-only plus explicit scraping ban, same class as ASX |
| Indonesia | Kemnaker Satudata (Ministry of Manpower employment data portal, PHK/layoff statistics) | statistical_agency | unclear | research_further — official and current but aggregate-only with unverified licensing; check for a downloadable dataset and licence terms before ingest |
| Ireland | DETE — collective redundancy notifications to the Minister (Protection of Employment Act 1977) | official_bulletin | unclear | do_not_ingest — nothing published; news fallback The Irish Times (irishtimes.com), Irish Independent (independent.ie); RTÉ (rte.ie) is a free alternative |
| Ireland | The Irish Times (irishtimes.com) / Irish Independent (independent.ie) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Israel | Israel Employment Service collective-dismissal notifications (10+ dismissals/month must be repo | official_bulletin | unclear | do_not_ingest — notification data is not published; there is no WARN-equivalent public feed in Israel. |
| Israel | News fallback: CTech by Calcalist (calcalistech.com) + Globes English (en.globes.co.il) | reputable_newspaper | free | research_further — best-in-region news fallback; add both domains to the trusted-outlet allowlist in the existing GDELT/NewsAPI pipeline rather than ingesting directly. |
| Israel | TASE Maya announcements feed (TASE Data Hub / Open API) | exchange_disclosure | paid | research_further — the only permitted programmatic interface is paid; a $130/mo internal-use subscription would make this a clean candidate, but it is not free, so it is a budget decision, not an admit. Do not scrape the |
| Italy | INPS Open Data — Osservatorio ore autorizzate di CIG | official_api | free | research_further — permitted, machine-readable, but aggregate-only; useful for reconciliation/context stats, cannot generate company entries |
| Italy | Ministero del Lavoro — elenco decreti CIGS (weekly company-level CIGS decree lists) | official_bulletin | free | research_further — the only company-level official source in this region set and stable/weekly, BUT CIGS decrees authorize short-time-work/restructuring (a layoff precursor, not a layoff count), the Word-HTML format is f |
| Malaysia | Bursa Malaysia company announcements | exchange_disclosure | free | research_further — verify the site terms/disclaimer text directly before any ingest decision; do not ingest meanwhile |
| Malaysia | PERKESO Employment Insurance System (EIS) loss-of-employment statistics (fed by mandatory Boran | statistical_agency | unclear | research_further — official aggregate stats exist but access reliability and licence are unverified; per-company PK data is not public |
| Malaysia | The Edge Malaysia (theedgemalaysia.com) — news fallback; runner-up: The Star Business (thestar. | reputable_newspaper | free | research_further — GDELT allowlist outlets while official per-company data stays unpublished |
| Mexico | BMV — Eventos Relevantes (via EMISNET) | exchange_disclosure | unclear | research_further — free to view but undocumented for automated reuse; do not ingest until terms are confirmed or a permitted feed is found. |
| Mexico | IMSS Datos Abiertos — puestos de trabajo / asegurados (monthly formal employment) | statistical_agency | free | research_further — clean, permitted, machine-readable, but only usable as a macro context indicator, not an event source. |
| Mexico | News fallback: El Economista + El Financiero | reputable_newspaper | free | research_further — best event-level fallback given no official Mexican notification register. |
| Mexico | STPS / labor-court collective-termination process (no WARN analog) | official_bulletin | unclear | do_not_ingest — no official event-level interface exists; rely on securities disclosures and news. |
| Netherlands | Het Financieele Dagblad (fd.nl) / NRC (nrc.nl) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only; do not scrape directly |
| Netherlands | UWV / SZW — Wet melding collectief ontslag (WMCO) notifications & annual reports | official_bulletin | free | do_not_ingest — no company-level or machine-readable data exists; rely on news fallback (FD, NRC) |
| New Zealand | NZX market announcements (nzx.com + official mirror announcements.nzx.com) | exchange_disclosure | free | do_not_ingest — redistribution requires an NZX market-data agreement; same practical outcome as ASX |
| New Zealand | The New Zealand Herald (nzherald.co.nz) — news fallback; runner-up: BusinessDesk (businessdesk. | reputable_newspaper | free | research_further — news fallback via GDELT allowlist; no official register exists and NZX is blocked |
| Nigeria | NGX (Nigerian Exchange) corporate disclosures | exchange_disclosure | free | do_not_ingest — website terms expressly forbid the copying/redistribution ingest requires. |
| Nigeria | News fallback: BusinessDay Nigeria (businessday.ng) + Nairametrics (nairametrics.com) | reputable_newspaper | free | research_further — allowlist both as the Nigeria fallback; this is the only permitted channel. |
| Norway | Dagens Næringsliv (dn.no) / E24 (e24.no) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Norway | NAV — Melding om permittering og masseoppsigelser (mass-dismissal/layoff notifications statisti | statistical_agency | free | research_further — stable monthly Excel but aggregate-only; verify NLOD applicability; news fallback Dagens Næringsliv (dn.no), E24 (e24.no) |
| Philippines | BusinessWorld (bworldonline.com) — news fallback; runner-up: Philippine Daily Inquirer Business | reputable_newspaper | free | research_further — GDELT allowlist outlets given no public official register |
| Philippines | DOLE Establishment Termination Reports (RKS Form 5) / Establishment Report System | official_bulletin | unclear | research_further — the statutory reporting exists but no public data interface; watch for DOLE regional displacement bulletins/press releases |
| Philippines | PSE EDGE disclosure portal | exchange_disclosure | free | do_not_ingest — no permitted programmatic interface and anti-automation terms |
| Poland | MRPiPS / Publiczne Służby Zatrudnienia — zwolnienia grupowe statistics | statistical_agency | free | research_further — aggregate-only; news fallback Puls Biznesu (pb.pl), Rzeczpospolita (rp.pl) |
| Poland | Puls Biznesu (pb.pl) / Rzeczpospolita (rp.pl) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Portugal | DGERT — despedimentos coletivos monthly reports | official_bulletin | free | do_not_ingest — aggregate PDFs under all-rights-reserved terms; news fallback Jornal de Negócios (jornaldenegocios.pt), ECO (eco.pt, free access) |
| Portugal | Jornal de Negócios (jornaldenegocios.pt) / ECO (eco.pt) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Russia | e-disclosure.ru (Interfax Corporate Information Disclosure Center) — assessed and rejected; new | official_bulletin | free | do_not_ingest — official channel is unreliable by design and sanctions-risky; keep Russia news-fallback-only through the existing GDELT pipeline with the above outlets, treating domestic reporting with caution. |
| Saudi Arabia | News fallback: Argaam English (argaam.com/en) + Arab News (arabnews.com) | reputable_newspaper | free | research_further — allowlist both as the Saudi fallback; Argaam effectively relays Tadawul disclosures in a form the news pipeline can legitimately pick up. |
| Saudi Arabia | Saudi Exchange (Tadawul) issuer announcements | exchange_disclosure | unclear | do_not_ingest — no permitted, documented programmatic interface; the only paths are paid market-data contracts or scraping a bot-blocking site. |
| Singapore | Ministry of Manpower retrenchment statistics via data.gov.sg (e.g. Retrenched Employees by Indu | statistical_agency | free | admit_candidate — stable documented API, licence explicitly permits commercial reuse; ingest as country-level quarterly statistics (not company events) |
| Singapore | SGX company announcements | exchange_disclosure | free | do_not_ingest — copying/storing announcements requires written SGX permission; same class of block as LSE RNS |
| South Africa | CCMA section 189A large-scale retrenchment data | statistical_agency | free | research_further — free and official but aggregate-only, so unusable as a per-company event source; possibly worth citing as context statistics on a country page, nothing more. |
| South Africa | JSE SENS (Stock Exchange News Service) | exchange_disclosure | paid | do_not_ingest — same posture as the ASX decision: non-personal/commercial reuse expressly prohibited without a paid license. |
| South Africa | News fallback: Moneyweb (moneyweb.co.za) + Business Day / BusinessLIVE (businesslive.co.za) | reputable_newspaper | free | research_further — allowlist both; s189/s189A retrenchments at named companies are reliably reported in both outlets. |
| Spain | Comunidad de Madrid open data — Expedientes de Regulación de Empleo (record-level) | official_api | free | research_further — permitted and machine-readable but anonymized (no company names) and regional; unusable for named entries, possible enrichment only |
| Spain | Ministerio de Trabajo y Economía Social — Estadística de Regulación de Empleo (REG) | statistical_agency | free | research_further — aggregate-only; company names must come from news (Expansión expansion.com, Cinco Días cincodias.elpais.com); TLS quirk would need pinning/workaround |
| Sweden | Arbetsförmedlingen — statistik om varsel (notified redundancies) | statistical_agency | free | research_further — aggregate-only (good announcement-survey-style reconciliation series, not entries); company names for Sweden must come from news (Dagens Industri di.se, SvD Näringsliv svd.se) |
| Sweden | Dagens Industri (di.se) / SvD Näringsliv (svd.se) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Switzerland | Neue Zürcher Zeitung (nzz.ch) / Handelszeitung (handelszeitung.ch) | reputable_newspaper | paid | research_further — use via existing GDELT/NewsAPI ingest only |
| Switzerland | No central register — cantonal mass-dismissal notifications (art. 335f/g CO); SECO labour-marke | statistical_agency | free | do_not_ingest — no public register; news fallback NZZ (nzz.ch), Handelszeitung (handelszeitung.ch) |
| Taiwan | Ministry of Labor mass-layoff notification open data (data.gov.tw datasets 27505 mass-layoff no | statistical_agency | free | research_further — interface is stable, documented, and commercially licensed, but aggregate-only; admit as annual statistics if that granularity is wanted, keep hunting for a per-company feed |
| Taiwan | Municipal labor bureau mass-layoff bulletins (e.g. Taipei City Department of Labor 大量解僱勞工通報; Ta | official_bulletin | free | research_further — the statutory system exists but per-company data is scattered across municipal HTML pages; would need per-city scrapers and terms review before ingest |
| Thailand | Bangkok Post (bangkokpost.com) — news fallback; runner-up: Krungthep Turakij (bangkokbiznews.co | reputable_newspaper | free | research_further — GDELT allowlist outlets given SET is paid and no official register exists |
| Thailand | Department of Labour Protection and Welfare open data (opendata.labour.go.th, catalogued on dat | statistical_agency | free | research_further — open-licensed portal exists but a layoff-specific dataset was not located; needs catalogue-level search in Thai |
| Thailand | SET (Stock Exchange of Thailand) company news / SETSMART / PRS news feed | exchange_disclosure | paid | do_not_ingest — announcement feeds are paid licensed products |
| Turkey | KAP — Public Disclosure Platform (kap.org.tr), operated by MKK | exchange_disclosure | free | research_further — most promising official source in the region, but the permitted programmatic path runs through MKK vendor contracts and site reuse terms are unpublished; contact MKK before building a collector. Do not |
| Turkey | News fallback: Dünya (dunya.com) + Hürriyet Daily News (hurriyetdailynews.com, English) | reputable_newspaper | free | research_further — allowlist both in the existing news pipeline as the Turkey fallback; KAP material-event disclosures remain the verification source when a layoff involves a listed company. |
| Turkey | İŞKUR collective-dismissal notifications (Labor Law Art. 29) | official_bulletin | unclear | do_not_ingest — WARN-like notification duty exists but the data is never made public. |
| UAE | DFM / ADX listed-company disclosures | exchange_disclosure | free | research_further — low priority; verify site terms in a browser before considering any collector, and expect low yield since layoffs there rarely surface in exchange filings. |
| UAE | MOHRE (Ministry of Human Resources & Emiratisation) redundancy notifications | official_bulletin | unclear | do_not_ingest — no public official system; UAE is newspapers-only. |
| UAE | News fallback: The National (thenationalnews.com) + Gulf News (gulfnews.com) | reputable_newspaper | free | research_further — allowlist as the UAE fallback; this is effectively the only permitted channel for UAE layoff events. |
| Ukraine | News fallback: Ekonomichna Pravda (epravda.com.ua) + Kyiv Independent (kyivindependent.com) — n | reputable_newspaper | free | research_further — news-fallback-only as scoped: allowlist these outlets in GDELT; revisit SMIDA only after wartime disclosure rules normalize. |
| Vietnam | Labor ministry (ex-MOLISA; labor functions absorbed into Ministry of Home Affairs in the 2025 g | official_bulletin | unclear | do_not_ingest — no public interface exists; rely on news fallback |
| Vietnam | VnExpress / VnExpress International (e.vnexpress.net) — news fallback; runner-up: VnEconomy (vn | reputable_newspaper | free | research_further — GDELT allowlist outlets; only practical Vietnam coverage path |
