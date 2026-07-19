"""
Pulls AI-related layoff coverage from GDELT — a free, keyless, global news index
(2017→present). GDELT returns article metadata (url/title/domain/date); we fetch
each article and extract the layoff details downstream via the same extractor.

This is the historical + global press layer: free, worldwide, back to 2024,
and it's where AI-attributed layoff language actually appears.
"""
import html
import os
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

from sources import gdelt_bq

from source_registry import discovery_terms

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT space = AND, OR must be explicit. ALL layoffs, not only AI-related —
# the extractor tags ai_explicit itself, so an AI clause here was pure
# coverage loss (Europe/world general layoffs never entered the pipeline).
# "redundancies" catches UK/Commonwealth English. GDELT Translingual machine-
# translates 65 languages into English before indexing, so these English
# keywords match Le Monde / Handelsblatt / NRC / Gazeta coverage too.
# Keep the retrieval vocabulary in the source registry rather than in an LLM
# prompt.  This makes coverage reviewable, testable, and expandable by market.
QUERY = "(" + " OR ".join(
    f'"{term}"' if " " in term else term for term in discovery_terms()
) + ")"

TRUSTED_DOMAINS = {
    # wires / national general
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "cnn.com", "nytimes.com",
    "washingtonpost.com", "latimes.com", "usatoday.com", "npr.org", "abcnews.go.com",
    "nbcnews.com", "cbsnews.com", "politico.com", "thehill.com", "axios.com",
    "theguardian.com", "independent.co.uk", "telegraph.co.uk", "foxbusiness.com",
    "foxnews.com", "aljazeera.com", "semafor.com",
    # business / finance
    "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "forbes.com", "fortune.com",
    "businessinsider.com", "businessinsider.in", "marketwatch.com", "barrons.com",
    "morningstar.com", "thestreet.com", "benzinga.com", "fastcompany.com", "inc.com",
    "hbr.org", "qz.com", "sherwood.news", "economist.com", "financialpost.com",
    # tech / trade
    "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com", "engadget.com",
    "zdnet.com", "venturebeat.com", "theregister.com", "gizmodo.com", "mashable.com",
    "digitaltrends.com", "theinformation.com", "restofworld.org", "9to5google.com",
    # regional US
    "sfgate.com", "sfchronicle.com", "mercurynews.com", "seattletimes.com",
    "chicagotribune.com", "bostonglobe.com", "dallasnews.com", "denverpost.com",
    # international (English)
    "dw.com", "france24.com", "scmp.com", "japantimes.co.jp", "straitstimes.com",
    "cbc.ca", "globalnews.ca",
    # Canada — was thin (only CBC + Global News + Financial Post), which
    # under-covered a country with no WARN/SEC/ERM equivalent. Added the
    # papers of record + national business/tech outlets.
    "theglobeandmail.com", "nationalpost.com", "thestar.com", "ctvnews.ca",
    "bnnbloomberg.ca", "montrealgazette.com", "torontosun.com", "betakit.com",
    "smh.com.au", "abc.net.au", "irishtimes.com",
    "business-standard.com", "moneycontrol.com", "ndtv.com", "ndtvprofit.com",
    "livemint.com", "hindustantimes.com", "thehindu.com",
    "timesofindia.indiatimes.com", "economictimes.indiatimes.com",
    # international (non-English majors — the extractor reads any language)
    "lemonde.fr", "lesechos.fr", "lefigaro.fr",              # France
    "handelsblatt.com", "spiegel.de", "faz.net", "zeit.de",  # Germany
    "elpais.com", "expansion.com",                            # Spain
    "corriere.it", "ilsole24ore.com",                         # Italy
    "nikkei.com", "asahi.com",                                # Japan
    "chosun.com", "hankyung.com",                             # South Korea
    "globo.com", "estadao.com.br", "folha.uol.com.br",       # Brazil
    "eleconomista.com.mx", "clarin.com",                      # Mexico / Argentina
    "nrc.nl", "volkskrant.nl",                                # Netherlands
    # --- Regional expansion: reputable national business/news outlets, added
    # to widen country coverage (a layoff only enters the tracker if a trusted
    # outlet covers it, so this list IS the reach lever). English editions
    # preferred; GDELT machine-translates the rest.
    "haaretz.com", "timesofisrael.com", "calcalistech.com",   # Israel
    "thenationalnews.com", "gulfnews.com", "khaleejtimes.com", "arabnews.com",  # Gulf
    "hurriyetdailynews.com", "dailysabah.com",                # Turkey
    "news24.com", "businesslive.co.za", "iol.co.za", "moneyweb.co.za",  # South Africa
    "premiumtimesng.com", "punchng.com",                      # Nigeria
    "nation.africa", "businessdailyafrica.com",               # Kenya
    "ahram.org.eg",                                            # Egypt
    "thejakartapost.com", "kompas.com",                       # Indonesia
    "bangkokpost.com", "nationthailand.com",                  # Thailand
    "vnexpress.net", "vietnamnews.vn",                        # Vietnam
    "thestar.com.my", "nst.com.my",                           # Malaysia
    "inquirer.net", "rappler.com", "philstar.com",            # Philippines
    "taipeitimes.com", "focustaiwan.tw",                      # Taiwan
    "koreaherald.com", "koreatimes.co.kr",                    # South Korea (English)
    "themoscowtimes.com", "kyivindependent.com",              # Russia / Ukraine
    "notesfrompoland.com",                                    # Poland (English)
    "thelocal.se", "thelocal.de", "thelocal.fr",             # Nordics / EU (English)
    "helsinkitimes.fi",                                       # Finland
    "swissinfo.ch",                                           # Switzerland
    "nzherald.co.nz", "rnz.co.nz",                            # New Zealand
    "eltiempo.com", "portafolio.co",                          # Colombia
    "df.cl",                                                   # Chile
    "elcomercio.pe",                                          # Peru
    # --- Deep coverage for the markets most likely to cite this tracker:
    # USA, Canada, UK/Europe, Australia. Papers of record + national business.
    "afr.com", "theaustralian.com.au", "news.com.au", "theage.com.au",  # Australia
    "9news.com.au", "skynews.com.au", "watoday.com.au", "brisbanetimes.com.au",
    "thetimes.co.uk", "news.sky.com", "standard.co.uk", "cityam.com",   # UK
    "euronews.com", "politico.eu", "euractiv.com",            # EU-wide
    "liberation.fr", "lexpress.fr",                           # France
    "sueddeutsche.de", "welt.de", "tagesschau.de",            # Germany
    "elmundo.es", "lavanguardia.com",                         # Spain
    "repubblica.it", "lastampa.it",                           # Italy
    "fd.nl",                                                   # Netherlands (business)
    "lesoir.be", "standaard.be",                              # Belgium
    "dn.se", "svd.se",                                        # Sweden
    "aftenposten.no", "e24.no",                              # Norway
    "politiken.dk", "borsen.dk",                             # Denmark
    "hs.fi",                                                  # Finland
    "nzz.ch", "letemps.ch",                                  # Switzerland
    "derstandard.at", "diepresse.com",                       # Austria
    "independent.ie", "rte.ie", "thejournal.ie",             # Ireland
    "expresso.pt", "publico.pt",                             # Portugal
    "startribune.com", "chron.com", "miamiherald.com",       # more US regionals
    "cnbc.com", "thehill.com",                               # (dupes are harmless; set dedups)
    # --- 2026-07 four-region research sweep (docs/COUNTRY_SOURCE_RESEARCH_2026_07.md
    # §3, "Newspapers-only fallback by country"): per-country papers of record and
    # business dailies. Allowlist-only — these mark articles as trusted when they
    # surface via GDELT/NewsAPI; we never scrape these sites directly.
    "latribune.fr",                                           # France
    "di.se",                                                  # Sweden
    "berlingske.dk",                                          # Denmark
    "dn.no",                                                  # Norway
    "kauppalehti.fi",                                         # Finland
    "pb.pl", "rp.pl",                                         # Poland
    "handelszeitung.ch",                                      # Switzerland
    "jornaldenegocios.pt", "eco.sapo.pt",                     # Portugal
    "elfinanciero.com.mx",                                    # Mexico
    "ambito.com", "cronista.com",                             # Argentina
    "latercera.com",                                          # Chile (Pulso)
    "larepublica.co",                                         # Colombia
    "hket.com",                                               # Hong Kong
    "businessdesk.co.nz",                                     # New Zealand
    "bisnis.com", "kontan.co.id",                             # Indonesia
    "theedgemalaysia.com",                                    # Malaysia
    "bworldonline.com",                                       # Philippines
    "vneconomy.vn",                                           # Vietnam
    "bangkokbiznews.com",                                     # Thailand (Krungthep Turakij)
    "globes.co.il",                                           # Israel
    "dunya.com",                                              # Turkey
    "argaam.com",                                             # Saudi Arabia
    "businessday.ng", "nairametrics.com",                     # Nigeria
    "dailynewsegypt.com",                                     # Egypt
    "kommersant.ru", "rbc.ru", "thebell.io",                  # Russia
    "epravda.com.ua",                                         # Ukraine
    # --- 2026-07-18 Challenger gap-closure R4 (docs/CHALLENGER_GAP_CLOSURE_PLAN.md):
    # reviewed US trade/regional outlets that carried missed-event coverage.
    # Healthcare trade press is the motivating sector (Challenger Jan
    # healthcare 17,107 vs ~400 in named events). xtalks.com was reviewed and
    # rejected (marketing/webinar site, not a newsroom).
    "healthcaredive.com", "fiercepharma.com",                 # healthcare trade
    "paymentsdive.com",                                       # fintech trade
    # --- 2026-07 US metro/city business press sweep: metro outlets report
    # local layoffs before national press. Allowlist-only (GDELT/NewsAPI
    # surface articles; never crawl). Paywalled entries follow the existing
    # wsj/ft posture; bot-blocked fetches drop out harmlessly.
    "bizjournals.com",            # ACBJ network — one domain, 44 metro Business Journals
    "chicagobusiness.com",        # Crain's Chicago Business
    "crainsnewyork.com",          # Crain's New York Business
    "crainsdetroit.com",          # Crain's Detroit Business (auto belt)
    "crainscleveland.com",        # Crain's Cleveland Business (healthcare/mfg)
    "crainsgrandrapids.com",      # Crain's Grand Rapids (W. Michigan mfg)
    "ajc.com",                    # Atlanta Journal-Constitution
    "inquirer.com",               # Philadelphia Inquirer
    "oregonlive.com",             # The Oregonian — Portland (Intel/Nike)
    "tampabay.com",               # Tampa Bay Times
    "post-gazette.com",           # Pittsburgh Post-Gazette
    "stltoday.com",               # St. Louis Post-Dispatch
    "azcentral.com",              # Arizona Republic — Phoenix (chips)
    "cleveland.com",              # Plain Dealer / Advance
    "freep.com", "detroitnews.com",  # Detroit dailies (auto layoffs)
    "jsonline.com",               # Milwaukee Journal Sentinel
    "dispatch.com",               # Columbus Dispatch (Intel Ohio)
    "tennessean.com",             # Nashville (healthcare HQs)
    "charlotteobserver.com",      # Charlotte (banking)
    "houstonchronicle.com",       # paywalled sibling of chron.com
    "statesman.com",              # Austin (Tesla/Oracle/Dell metro)
    "sandiegouniontribune.com",   # San Diego (biotech/defense)
    "sltrib.com",                 # Salt Lake Tribune (Silicon Slopes)
    "thebaltimorebanner.com",     # Baltimore Banner
    "reviewjournal.com",          # Las Vegas R-J (hospitality)
    "ibj.com",                    # Indianapolis Business Journal
    "geekwire.com",               # Seattle tech — breaks Amazon/Microsoft cuts early
    "marketplace.org",            # APM Marketplace
    "kuow.org",                   # Seattle NPR (Boeing/Amazon/Microsoft)
    "wbur.org",                   # Boston NPR (biotech)
    "kqed.org",                   # SF Bay NPR (tech)
    # Corporate press-release wires: PRIMARY announcement text, the exact
    # channel Challenger monitors. Allowlist-only — GDELT/NewsAPI surface the
    # releases; we never crawl the wires directly.
    "prnewswire.com", "businesswire.com", "globenewswire.com", "prweb.com",
    # --- 2026-07-18 worldwide papers-of-record expansion: built from the
    # per-country Wikipedia newspaper lists by a five-continent review pass
    # (top 2-5 active newsrooms per country; state-outlet caveats inline).
    # Allowlist-only; GDELT Translingual surfaces the articles.
    # ========== AFRICA ==========
    # --- North Africa
    "almasryalyoum.com",         # Egypt — Al-Masry Al-Youm (leading private daily)
    "enterprise.press",          # Egypt — Enterprise (leading business-news briefing)
    "leconomiste.com",           # Morocco — L'Economiste (business daily of record)
    "medias24.com",              # Morocco — Medias24 (independent business-news site)
    "hespress.com",              # Morocco — Hespress (largest news site, real newsroom)
    "elwatan-dz.com",            # Algeria — El Watan (French-language paper of record; current domain, old elwatan.com defunct)
    "elkhabar.com",              # Algeria — El Khabar (largest Arabic-language daily)
    "tsa-algerie.com",           # Algeria — TSA/Tout sur l'Algerie (leading independent online)
    "businessnews.com.tn",       # Tunisia — Business News (leading business-news site)
    "lapresse.tn",               # Tunisia — La Presse (state-owned daily of record; caveat)
    "libyaherald.com",           # Libya — Libya Herald (independent English business/news)
    "sudantribune.com",          # Sudan — Sudan Tribune (independent; exile-run, caveat)
    "dabangasudan.org",          # Sudan — Radio Dabanga (independent; exile-run, caveat)
    "alakhbar.info",             # Mauritania — Alakhbar (leading independent news agency)
    # --- West Africa
    "guardian.ng",               # Nigeria — The Guardian Nigeria (paper of record)
    "thecable.ng",               # Nigeria — TheCable (leading independent digital newsroom)
    "thisdaylive.com",           # Nigeria — ThisDay (major business/politics daily)
    "graphic.com.gh",            # Ghana — Daily Graphic (state-owned paper of record; editorially standard)
    "myjoyonline.com",           # Ghana — JoyNews/Multimedia Group (leading private newsroom)
    "thebftonline.com",          # Ghana — Business & Financial Times (leading business daily)
    "citinewsroom.com",          # Ghana — Citi Newsroom (private, business-leaning)
    "lequotidien.sn",            # Senegal — Le Quotidien (independent daily)
    "enqueteplus.com",           # Senegal — EnQuete (independent daily)
    "lesoleil.sn",               # Senegal — Le Soleil (state-owned daily of record; caveat)
    "fratmat.info",              # Cote d'Ivoire — Fraternite Matin (state-owned record; caveat)
    "sikafinance.com",           # Cote d'Ivoire — Sika Finance (BRVM/West-Africa markets news)
    "lefaso.net",                # Burkina Faso — LeFaso.net (leading independent; junta-era press limits)
    "journaldumali.com",         # Mali — Journal du Mali (independent; junta-era press limits)
    "actuniger.com",             # Niger — ActuNiger (independent online; junta-era press limits)
    "lanouvelletribune.info",    # Benin — La Nouvelle Tribune (independent daily)
    "togofirst.com",             # Togo — Togo First (business-news site)
    "guineenews.org",            # Guinea — Guineenews (leading independent)
    "awoko.org",                 # Sierra Leone — Awoko (leading independent daily)
    "thesierraleonetelegraph.com", # Sierra Leone — Sierra Leone Telegraph (independent)
    "frontpageafricaonline.com", # Liberia — FrontPage Africa (leading independent/investigative)
    "liberianobserver.com",      # Liberia — Daily Observer (oldest independent daily)
    "thepoint.gm",               # Gambia — The Point (leading independent)
    "expressodasilhas.cv",       # Cape Verde — Expresso das Ilhas (leading independent)
    # --- Central Africa
    "businessincameroon.com",    # Cameroon — Business in Cameroon (English business news)
    "journalducameroun.com",     # Cameroon — Journal du Cameroun (independent)
    "actualite.cd",              # DR Congo — Actualite.cd (leading independent newsroom)
    "radiookapi.net",            # DR Congo — Radio Okapi (UN-backed professional newsroom)
    "gabonreview.com",           # Gabon — Gabon Review (leading independent online)
    "tchadinfos.com",            # Chad — Tchadinfos (leading online newsroom)
    "adiac-congo.com",           # Congo-Brazzaville — Les Depeches de Brazzaville (only daily; gov't-close, caveat)
    "radiondekeluka.org",        # Central African Rep. — Radio Ndeke Luka (Fondation Hirondelle-backed, most credible)
    # --- East Africa
    "addisfortune.news",         # Ethiopia — Addis Fortune (leading business weekly)
    "thereporterethiopia.com",   # Ethiopia — The Reporter, English edition (major private)
    "addisstandard.com",         # Ethiopia — Addis Standard (leading independent)
    "standardmedia.co.ke",       # Kenya — The Standard (second paper of record)
    "theeastafrican.co.ke",      # Kenya — The EastAfrican (regional business weekly)
    "thecitizen.co.tz",          # Tanzania — The Citizen (leading English daily)
    "mwananchi.co.tz",           # Tanzania — Mwananchi (largest Swahili daily; GDELT translates)
    "monitor.co.ug",             # Uganda — Daily Monitor (leading independent)
    "newvision.co.ug",           # Uganda — New Vision (state-majority-owned major daily; caveat)
    "newtimes.co.rw",            # Rwanda — The New Times (most-established; gov't-aligned, caveat)
    "iwacu-burundi.org",         # Burundi — Iwacu (last major independent outlet)
    "radiotamazuj.org",          # South Sudan — Radio Tamazuj (independent; exile-run, caveat)
    "garoweonline.com",          # Somalia — Garowe Online (leading independent)
    "hiiraan.com",               # Somalia — Hiiraan Online (long-running independent)
    "lexpress.mg",               # Madagascar — L'Express de Madagascar (leading daily)
    "midi-madagasikara.mg",      # Madagascar — Midi Madagasikara (largest daily)
    "lexpress.mu",               # Mauritius — L'Express (paper of record)
    "defimedia.info",            # Mauritius — Le Defi Media Group (major private)
    "seychellesnewsagency.com",  # Seychelles — Seychelles News Agency (gov't-backed but professional; caveat)
    # ========== ASIA ==========
    # --- East Asia
    "caixin.com",                # China — Caixin (most independent mainland business outlet)
    "caixinglobal.com",          # China — Caixin Global (English edition, separate domain)
    "yicai.com",                 # China — Yicai / China Business News (state-owned Shanghai Media Group; business focus)
    "yicaiglobal.com",           # China — Yicai Global (English edition, separate domain)
    "jiemian.com",               # China — Jiemian News (business news; Shanghai United Media, state-linked)
    "yomiuri.co.jp",             # Japan — Yomiuri Shimbun (largest daily; covers japannews.yomiuri.co.jp)
    "mainichi.jp",               # Japan — Mainichi Shimbun (paper of record)
    "mk.co.kr",                  # South Korea — Maeil Business Newspaper (covers pulse.mk.co.kr English wire)
    "mingpao.com",               # Hong Kong — Ming Pao (Chinese-language paper of record)
    "thestandard.com.hk",        # Hong Kong — The Standard (English business-leaning daily, Sing Tao)
    "udn.com",                   # Taiwan — United Daily News (covers money.udn.com = Economic Daily News)
    "digitimes.com",             # Taiwan — DIGITIMES Asia (semiconductor/supply-chain trade press)
    "news.mn",                   # Mongolia — News.mn (leading news portal; has English edition)
    "ikon.mn",                   # Mongolia — Ikon (major private news site)
    "nknews.org",                # North Korea — NK News (Seoul-based specialist; no credible domestic media)
    # --- South Asia
    "indianexpress.com",         # India — The Indian Express (paper of record; biz dailies already listed)
    "dawn.com",                  # Pakistan — Dawn (paper of record)
    "brecorder.com",             # Pakistan — Business Recorder (business daily)
    "tribune.com.pk",            # Pakistan — The Express Tribune (national English daily)
    "thedailystar.net",          # Bangladesh — The Daily Star (leading English daily)
    "tbsnews.net",               # Bangladesh — The Business Standard (business daily)
    "prothomalo.com",            # Bangladesh — Prothom Alo (largest daily; covers en.prothomalo.com)
    "ft.lk",                     # Sri Lanka — Daily FT (business daily)
    "economynext.com",           # Sri Lanka — EconomyNext (leading business-news site)
    "dailymirror.lk",            # Sri Lanka — Daily Mirror (English daily, Wijeya group)
    "kathmandupost.com",         # Nepal — The Kathmandu Post (leading English daily)
    "ekantipur.com",             # Nepal — Kantipur (largest daily, same group)
    "kuenselonline.com",         # Bhutan — Kuensel (national paper; state-owned — only real newsroom)
    "mihaaru.com",               # Maldives — Mihaaru (leading daily; bilingual site)
    "tolonews.com",              # Afghanistan — TOLOnews (leading broadcaster; operates under Taliban restrictions)
    # --- Southeast Asia
    "channelnewsasia.com",       # Singapore — CNA (Mediacorp; state-owned broadcaster with real newsroom)
    "businesstimes.com.sg",      # Singapore — The Business Times (SPH business daily)
    "tempo.co",                  # Indonesia — Tempo (most independent national newsroom)
    "kiripost.com",              # Cambodia — Kiripost (independent business-news site)
    "khmertimeskh.com",          # Cambodia — Khmer Times (pro-government owner; most active business coverage)
    "laotiantimes.com",          # Laos — The Laotian Times (private English outlet; state Vientiane Times excluded)
    "irrawaddy.com",             # Myanmar — The Irrawaddy (independent; operates in exile post-coup)
    "frontiermyanmar.net",       # Myanmar — Frontier Myanmar (independent; operates in exile post-coup)
    "borneobulletin.com.bn",     # Brunei — Borneo Bulletin (main national daily)
    # --- Middle East
    "zawya.com",                 # Gulf regional — Zawya (LSEG-owned Middle East business news)
    "arabianbusiness.com",       # UAE — Arabian Business (regional business magazine/site)
    "aleqt.com",                 # Saudi Arabia — Al-Eqtisadiah (business daily; SRMG, state-aligned)
    "gulf-times.com",            # Qatar — Gulf Times (leading English daily)
    "thepeninsulaqatar.com",     # Qatar — The Peninsula (English daily, strong business pages)
    "kuwaittimes.com",           # Kuwait — Kuwait Times (oldest English daily)
    "alqabas.com",               # Kuwait — Al-Qabas (leading private Arabic daily)
    "gdnonline.com",             # Bahrain — Gulf Daily News (main English daily)
    "timesofoman.com",           # Oman — Times of Oman (leading English daily)
    "muscatdaily.com",           # Oman — Muscat Daily (private English daily)
    "jordantimes.com",           # Jordan — The Jordan Times (semi-official, Jordan Press Foundation)
    "alghad.com",                # Jordan — Al-Ghad (leading private daily)
    "lorientlejour.com",         # Lebanon — L'Orient-Le Jour (respected French-language daily)
    "annahar.com",               # Lebanon — An-Nahar (leading Arabic daily)
    "enabbaladi.net",            # Syria — Enab Baladi (independent; strongest post-Assad newsroom)
    "rudaw.net",                 # Iraq — Rudaw (largest newsroom; KDP-affiliated — caveat)
    "shafaq.com",                # Iraq — Shafaq News (regional news agency)
    "donya-e-eqtesad.com",       # Iran — Donya-e-Eqtesad (leading business daily; operates under state press constraints)
    "financialtribune.com",      # Iran — Financial Tribune (English sister of Donya-e-Eqtesad; online-only since 2023)
    "cumhuriyet.com.tr",         # Turkey — Cumhuriyet (independent/opposition; balances existing pro-govt entries)
    # --- Caucasus
    "civilnet.am",               # Armenia — CivilNet (leading independent newsroom)
    "hetq.am",                   # Armenia — Hetq (investigative outlet)
    "civil.ge",                  # Georgia — Civil Georgia (independent, English)
    "bm.ge",                     # Georgia — BM.GE (business-news broadcaster/site)
    # ========== EUROPE ==========
    # Belgium (business dailies — general dailies lesoir/standaard already listed)
    "tijd.be",                   # Belgium — De Tijd (Flemish business daily)
    "lecho.be",                  # Belgium — L'Echo (francophone business daily)
    # Spain
    "eleconomista.es",           # Spain — elEconomista (business daily; distinct from .com.mx entry)
    # Luxembourg
    "luxtimes.lu",               # Luxembourg — Luxembourg Times (English daily, Wort group)
    "paperjam.lu",               # Luxembourg — Paperjam (leading business magazine)
    # Iceland
    "mbl.is",                    # Iceland — Morgunbladid/mbl.is (paper of record)
    "visir.is",                  # Iceland — Visir (major national news site)
    # Greece
    "kathimerini.gr",            # Greece — Kathimerini (paper of record)
    "ekathimerini.com",          # Greece — eKathimerini (English edition, separate domain)
    "naftemporiki.gr",           # Greece — Naftemporiki (business daily)
    # Cyprus
    "cyprus-mail.com",           # Cyprus — Cyprus Mail (leading English daily)
    "philenews.com",             # Cyprus — Phileleftheros (largest daily)
    "stockwatch.com.cy",         # Cyprus — StockWatch (financial/business news site)
    # Malta
    "timesofmalta.com",          # Malta — Times of Malta (paper of record)
    # Czechia
    "hn.cz",                     # Czechia — Hospodarske noviny (business daily)
    "denikn.cz",                 # Czechia — Denik N (independent daily)
    "seznamzpravy.cz",           # Czechia — Seznam Zpravy (largest online newsroom)
    # Slovakia
    "sme.sk",                    # Slovakia — SME (paper of record)
    "hnonline.sk",               # Slovakia — Hospodarske noviny (business daily)
    "dennikn.sk",                # Slovakia — Dennik N (independent daily)
    # Hungary (media largely captured — these are the independent/credible picks)
    "portfolio.hu",              # Hungary — Portfolio (leading business/finance site)
    "hvg.hu",                    # Hungary — HVG (business weekly)
    "telex.hu",                  # Hungary — Telex (independent newsroom)
    # Romania
    "zf.ro",                     # Romania — Ziarul Financiar (business daily)
    "adevarul.ro",               # Romania — Adevarul (major national daily)
    "g4media.ro",                # Romania — G4Media (independent news site)
    # Bulgaria
    "capital.bg",                # Bulgaria — Capital (leading business weekly, Economedia)
    "dnevnik.bg",                # Bulgaria — Dnevnik (credible daily, Economedia)
    # Moldova
    "newsmaker.md",              # Moldova — NewsMaker (independent, RO/RU)
    "zdg.md",                    # Moldova — Ziarul de Garda (investigative weekly)
    "mold-street.com",           # Moldova — Mold-Street (business/economics news)
    # Slovenia
    "delo.si",                   # Slovenia — Delo (paper of record)
    "finance.si",                # Slovenia — Finance (business daily)
    # Croatia
    "jutarnji.hr",               # Croatia — Jutarnji list (leading daily)
    "poslovni.hr",               # Croatia — Poslovni dnevnik (business daily)
    "n1info.hr",                 # Croatia — N1 Croatia (independent TV newsroom)
    # Serbia (state-aligned press skipped — independents preferred)
    "danas.rs",                  # Serbia — Danas (independent daily)
    "n1info.rs",                 # Serbia — N1 Serbia (independent TV newsroom)
    "novaekonomija.rs",          # Serbia — Nova ekonomija (business weekly)
    # Bosnia and Herzegovina
    "klix.ba",                   # Bosnia — Klix.ba (leading news portal)
    "oslobodjenje.ba",           # Bosnia — Oslobodjenje (oldest daily)
    "n1info.ba",                 # Bosnia — N1 Bosnia (independent TV newsroom)
    # Montenegro
    "vijesti.me",                # Montenegro — Vijesti (independent daily)
    # North Macedonia
    "slobodenpecat.mk",          # North Macedonia — Sloboden Pecat (leading daily)
    "kapital.mk",                # North Macedonia — Kapital (business weekly)
    # Albania
    "panorama.com.al",           # Albania — Panorama (largest daily)
    "monitor.al",                # Albania — Monitor (business/economics magazine)
    # Kosovo
    "koha.net",                  # Kosovo — Koha Ditore (paper of record)
    "prishtinainsight.com",      # Kosovo — Prishtina Insight (BIRN, English)
    # Estonia
    "postimees.ee",              # Estonia — Postimees (paper of record)
    "err.ee",                    # Estonia — ERR (public broadcaster, incl. English news)
    "aripaev.ee",                # Estonia — Aripaev (business daily, Bonnier)
    # Latvia
    "lsm.lv",                    # Latvia — LSM (public broadcaster, incl. English)
    "delfi.lv",                  # Latvia — Delfi (leading portal with own newsroom)
    "db.lv",                     # Latvia — Dienas Bizness (business daily)
    # Lithuania
    "lrt.lt",                    # Lithuania — LRT (public broadcaster, incl. English)
    "vz.lt",                     # Lithuania — Verslo zinios (business daily)
    "delfi.lt",                  # Lithuania — Delfi Lithuania (leading portal newsroom)
    "15min.lt",                  # Lithuania — 15min (major independent portal)
    # Belarus (state media excluded — exile outlets are the credible option)
    "zerkalo.io",                # Belarus — Zerkalo (TUT.by successor, in exile)
    "nashaniva.com",             # Belarus — Nasha Niva (oldest paper, in exile)
    # Ukraine (extends existing epravda/kyivindependent coverage)
    "pravda.com.ua",             # Ukraine — Ukrainska Pravda (leading online daily)
    "liga.net",                  # Ukraine — LIGA.net (business/news portal)
    # ========== AMERICAS ==========
    "lapresse.ca",               # Canada — La Presse (French; Quebec's leading daily, Quebec layoffs often French-press-only)
    "lesaffaires.com",           # Canada — Les Affaires (French-language business outlet, Quebec)
    "eluniversal.com.mx",        # Mexico — El Universal (paper of record)
    "reforma.com",               # Mexico — Reforma (paper of record; paywalled, same posture as wsj/ft)
    "expansion.mx",              # Mexico — Expansión (leading business-news site; distinct from Spain's expansion.com)
    "exame.com",                 # Brazil — Exame (leading business magazine)
    "infomoney.com.br",          # Brazil — InfoMoney (leading finance-news site; Valor already covered via globo.com)
    "lanacion.com.ar",           # Argentina — La Nación (paper of record)
    "infobae.com",               # Argentina — Infobae (largest Spanish-language digital daily)
    "emol.com",                  # Chile — El Mercurio / EMOL (paper of record)
    "elespectador.com",          # Colombia — El Espectador (oldest national daily)
    "gestion.pe",                # Peru — Gestión (the business daily, El Comercio group)
    "eluniverso.com",            # Ecuador — El Universo (paper of record)
    "primicias.ec",              # Ecuador — Primicias (leading independent digital daily)
    "eldeber.com.bo",            # Bolivia — El Deber (leading independent daily; Página Siete defunct)
    "lostiempos.com",            # Bolivia — Los Tiempos (Cochabamba daily)
    "abc.com.py",                # Paraguay — ABC Color (paper of record)
    "ultimahora.com",            # Paraguay — Última Hora (major daily)
    "elpais.com.uy",             # Uruguay — El País (paper of record; unrelated to Spain's elpais.com)
    "elobservador.com.uy",       # Uruguay — El Observador (business-leaning daily)
    "elnacional.com",            # Venezuela — El Nacional (independent paper of record; regime-pressured, online-only)
    "efectococuyo.com",          # Venezuela — Efecto Cocuyo (independent digital newsroom; operates under state pressure)
    "prensalibre.com",           # Guatemala — Prensa Libre (paper of record; elPeriodico defunct)
    "laprensa.hn",               # Honduras — La Prensa (leading daily)
    "elheraldo.hn",              # Honduras — El Heraldo (Tegucigalpa daily)
    "laprensagrafica.com",       # El Salvador — La Prensa Gráfica (paper of record)
    "elsalvador.com",            # El Salvador — El Diario de Hoy (major daily)
    "laprensani.com",            # Nicaragua — La Prensa (paper of record; newsroom in exile, most credible option)
    "confidencial.digital",      # Nicaragua — Confidencial (independent newsroom in exile)
    "nacion.com",                # Costa Rica — La Nación (paper of record)
    "elfinancierocr.com",        # Costa Rica — El Financiero (business weekly, Grupo Nación)
    "prensa.com",                # Panama — La Prensa (paper of record)
    "laestrella.com.pa",         # Panama — La Estrella de Panamá (oldest daily)
    "amandala.com.bz",           # Belize — Amandala (leading newspaper)
    "14ymedio.com",              # Cuba — 14ymedio (independent digital daily; exile-run, only credible non-state option)
    "listindiario.com",          # Dominican Republic — Listín Diario (paper of record)
    "diariolibre.com",           # Dominican Republic — Diario Libre (major daily)
    "eldinero.com.do",           # Dominican Republic — elDinero (business weekly)
    "lenouvelliste.com",         # Haiti — Le Nouvelliste (oldest daily)
    "jamaica-gleaner.com",       # Jamaica — The Gleaner (paper of record)
    "jamaicaobserver.com",       # Jamaica — Jamaica Observer (major daily)
    "guardian.co.tt",            # Trinidad & Tobago — T&T Guardian (paper of record)
    "trinidadexpress.com",       # Trinidad & Tobago — Trinidad Express (major daily)
    "newsday.co.tt",             # Trinidad & Tobago — Newsday (major daily; energy-sector coverage)
    "tribune242.com",            # Bahamas — The Tribune (leading daily; finance hub)
    "thenassauguardian.com",     # Bahamas — The Nassau Guardian (oldest daily)
    "nationnews.com",            # Barbados — The Nation (leading daily)
    "barbadostoday.bb",          # Barbados — Barbados Today (digital daily)
    "stabroeknews.com",          # Guyana — Stabroek News (paper of record; oil-boom economy)
    "kaieteurnewsonline.com",    # Guyana — Kaieteur News (major daily)
    "starnieuws.com",            # Suriname — Starnieuws (leading news site)
    "dwtonline.com",             # Suriname — de Ware Tijd (paper of record)
    "antiguaobserver.com",       # Antigua & Barbuda — Daily Observer (leading newspaper)
    "searchlight.vc",            # St. Vincent & the Grenadines — Searchlight (leading newspaper)
    "stluciatimes.com",          # St. Lucia — St. Lucia Times (leading digital daily)
    "dominicanewsonline.com",    # Dominica — Dominica News Online (leading news outlet)
    "nowgrenada.com",            # Grenada — NOW Grenada (leading news outlet)
    "elnuevodia.com",            # Puerto Rico — El Nuevo Día (leading daily; distinct market from mainland US press)
    "royalgazette.com",          # Bermuda — The Royal Gazette (paper of record; insurance/reinsurance hub)
    "caymancompass.com",         # Cayman Islands — Cayman Compass (finance-hub newsroom)
    "antilliaansdagblad.com",    # Curaçao — Antilliaans Dagblad (Dutch Caribbean daily)
    # ========== OCEANIA ==========
    "thewest.com.au",            # Australia — The West Australian (WA paper of record; mining-sector layoffs, gap: only Nine's small watoday covers WA)
    "canberratimes.com.au",      # Australia — The Canberra Times (capital daily; public-service and gov-contractor layoffs)
    "smartcompany.com.au",       # Australia — SmartCompany (business news site; strong startup/SME layoff coverage)
    "stuff.co.nz",               # New Zealand — Stuff (largest NZ news site; owns The Post/The Press metro mastheads)
    "odt.co.nz",                 # New Zealand — Otago Daily Times (independent Allied Press daily; South Island coverage)
    "interest.co.nz",            # New Zealand — interest.co.nz (dedicated business/finance newsroom)
    "fijitimes.com.fj",          # Fiji — The Fiji Times (paper of record since 1869; site geo-slow from US but active — DNS + search verified)
    "fijivillage.com",           # Fiji — Fijivillage (Communications Fiji Ltd newsroom; fast-turnaround national news)
    "postcourier.com.pg",        # Papua New Guinea — Post-Courier (oldest daily; News Corp-affiliated)
    "thenational.com.pg",        # Papua New Guinea — The National (largest-circulation daily)
    "samoaobserver.ws",          # Samoa — Samoa Observer (independent daily of record)
    "matangitonga.to",           # Tonga — Matangi Tonga (leading independent news site)
    "dailypost.vu",              # Vanuatu — Vanuatu Daily Post (main independent daily)
    "solomonstarnews.com",       # Solomon Islands — Solomon Star (main daily; site bot-blocks fetches — harmless for allowlist-only)
    "cookislandsnews.com",       # Cook Islands — Cook Islands News (national newspaper of record)
    "guampdn.com",               # Guam — Pacific Daily News (main daily, US territory)
    "mvariety.com",              # Northern Mariana Islands — Marianas Variety (main CNMI/Micronesia daily)
    "tahiti-infos.com",          # French Polynesia — Tahiti Infos (leading daily news site; French, GDELT translates)
    "lnc.nc",                    # New Caledonia — Les Nouvelles Calédoniennes (only daily, online-only since Oct 2023; nickel-industry layoffs)
    "islandsbusiness.com",       # Pacific regional — Islands Business (Suva-based regional business magazine covering all Pacific islands)
    "techrepublic.com", "electrek.co", "gamedeveloper.com",   # tech/EV/games trade
    "chicago.suntimes.com",                                   # Chicago daily
    "wral.com",                                               # Raleigh NC (WRAL TechWire)
    "mprnews.org",                                            # Minnesota Public Radio
    "boston.com",                                             # Boston Globe Media
    "sanantonioreport.org",                                   # San Antonio nonprofit newsroom
    "fox5vegas.com",                                          # Las Vegas TV news
    "westfaironline.com",                                     # Westchester/Fairfield business
    "kvrr.com", "wwnytv.com",                                 # Fargo / Watertown TV news
    "recorder.com",                                           # Greenfield Recorder (MA)
}

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

REQUEST_DELAY = 5.0       # GDELT asks for gentle use; 429s under load, so pace well below the shared limit
RAW_TEXT_LIMIT = 3000
MAX_DOC_BYTES = 400_000
FETCH_WORKERS = max(1, min(6, int(os.environ.get("GDELT_FETCH_WORKERS", "4"))))
# Five patient attempts with a longer base backoff: a rate-limited shared API
# rewards waiting, and the cursor design means an abandoned window is retried
# next run anyway — so patience here converts "degraded" runs into "ok" runs
# without any extra request volume.
QUERY_ATTEMPTS = max(1, min(6, int(os.environ.get("GDELT_QUERY_ATTEMPTS", "5"))))
QUERY_BACKOFF_SECONDS = max(1, min(120, int(os.environ.get("GDELT_QUERY_BACKOFF_SECONDS", "40"))))


def _retry_delay(response, attempt):
    """Honor a bounded Retry-After hint, with jitter for shared API fairness."""
    hinted = 0
    try:
        hinted = int((response.headers.get("Retry-After") or "").strip()) if response else 0
    except (AttributeError, TypeError, ValueError):
        hinted = 0
    return min(180, max(QUERY_BACKOFF_SECONDS * (attempt + 1), hinted)) + random.uniform(0, 3)


def _strip_html(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _domain(a):
    d = (a.get("domain") or "").lower()
    return d[4:] if d.startswith("www.") else d


def _is_trusted(dom):
    return any(dom == d or dom.endswith("." + d) for d in TRUSTED_DOMAINS)


def _seen_to_iso(seendate):
    s = re.sub(r"[^0-9]", "", seendate or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) >= 8 else ""


def _fetch_article(url):
    """Fetch an article and return a text window centered on the layoff mention."""
    resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=25)
    resp.raise_for_status()
    text = _strip_html(resp.text[:MAX_DOC_BYTES])
    lowered = text.lower()
    for kw in discovery_terms():
        idx = lowered.find(kw)
        if idx != -1:
            start = max(0, idx - 400)
            return text[start:start + RAW_TEXT_LIMIT]
    return text[:RAW_TEXT_LIMIT]


# Segmented recall sweeps: a broad "layoffs" query ranks global mega-stories
# first, so smaller country/state/industry announcements can fall below the
# maxrecords cutoff and never enter the pipeline. Each run therefore ALSO
# runs a few narrow queries chosen by deterministic daily rotation, so the
# whole matrix is covered every ~6 days at twice-daily cadence without
# increasing per-run volume beyond a handful of extra requests. Expand the
# matrix freely — rotation, not volume, absorbs growth.
SEGMENT_TERMS = (
    # US states with the highest layoff volume
    '"California"', '"New York"', '"Texas"', '"Washington"', '"Florida"',
    '"Illinois"', '"Massachusetts"', '"Georgia"', '"Michigan"', '"Ohio"',
    '"Pennsylvania"', '"New Jersey"',
    # countries (Translingual matches non-English coverage too)
    '"Germany"', '"France"', '"United Kingdom"', '"Canada"', '"India"',
    '"Japan"', '"Brazil"', '"Spain"', '"Italy"', '"Netherlands"',
    '"Sweden"', '"South Korea"', '"Singapore"', '"Israel"', '"Mexico"',
    '"Poland"', '"Switzerland"', '"Ireland"', '"Australia"',
    # industries
    '"manufacturing"', '"software"', '"banking"', '"retail"',
    '"healthcare"', '"automotive"', '"media"', '"logistics"',
    '"pharmaceutical"', '"insurance"', '"telecom"', '"aerospace"',
    # AI-attribution phrasings the broad vocabulary can rank too low
    '"AI layoffs"', '"replaced by AI"', '"because of AI"',
    '"artificial intelligence" "job cuts"', '"automation" "restructuring"',
)
SEGMENT_QUERIES_PER_RUN = max(0, min(8, int(os.environ.get("GDELT_SEGMENT_QUERIES", "4"))))


def _segment_queries_for_now():
    """Deterministic daily rotation over the segment matrix (0 disables)."""
    if not SEGMENT_QUERIES_PER_RUN:
        return []
    now = datetime.now(timezone.utc)
    run_of_day = 0 if now.hour < 17 else 1  # the two Railway cron slots
    start_idx = ((now.timetuple().tm_yday * 2 + run_of_day) * SEGMENT_QUERIES_PER_RUN) % len(SEGMENT_TERMS)
    picked = [SEGMENT_TERMS[(start_idx + i) % len(SEGMENT_TERMS)] for i in range(SEGMENT_QUERIES_PER_RUN)]
    return [f"{QUERY} {term}" for term in picked]


def _query_window(query, start, end, max_records):
    """One GDELT ArtList query with patient 429 backoff.

    Returns (articles, saw_rate_limit, last_error); articles is None when the
    window was abandoned after all attempts.
    """
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "sortby": "datedesc",
        # No sourcelang restriction: the trusted-domain list is the quality
        # gate, and it now includes major non-English outlets (Le Monde,
        # Handelsblatt, Nikkei, Globo...). The extractor reads any language.
        "startdatetime": start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
    }
    articles = None
    last_error = None
    saw_rate_limit = False
    delay = REQUEST_DELAY
    for attempt in range(QUERY_ATTEMPTS):
        time.sleep(delay)
        try:
            resp = requests.get(GDELT_URL, params=params,
                                headers={"User-Agent": BROWSER_UA}, timeout=30)
            if resp.status_code == 429:
                saw_rate_limit = True
                last_error = "HTTP 429"
                delay = _retry_delay(resp, attempt)
                print(f"GDELT 429 (attempt {attempt + 1}/{QUERY_ATTEMPTS}), retrying after {delay:.0f}s")
                continue
            resp.raise_for_status()
            articles = resp.json().get("articles", []) or []
            break
        except Exception as e:
            last_error = str(e)
            print(f"GDELT query error (attempt {attempt + 1}/{QUERY_ATTEMPTS}): {e}")
    return articles, saw_rate_limit, last_error


def pull_gdelt_between(start, end, max_records=250):
    """Return raw layoff-news entries (trusted domains) filed in [start, end]."""
    # Quota policy (sandbox: 1 TB scanned/month): the BigQuery mirror is
    # PREFERRED for historical sweeps (GDELT_PREFER_BQ=1 in those workflows —
    # bounded windows, where shared-endpoint 429s actually lose data) and is
    # the FALLBACK for live pulls when the public API abandons a window. Both
    # directions keep monthly scans far inside quota; every query also has a
    # hard bytes cap.
    prefer_bq = os.environ.get("GDELT_PREFER_BQ", "") in ("1", "true", "yes")
    if gdelt_bq.available() and prefer_bq:
        try:
            from source_registry import discovery_terms as _terms
            bq_articles = gdelt_bq.query_window_articles(start, end, _terms())
            print(f"GDELT via BigQuery mirror: {len(bq_articles)} article(s), no rate limits")
            return _fetch_trusted(bq_articles)
        except Exception as e:
            print(f"GDELT BigQuery mirror failed ({e}); falling back to public API")

    # GDELT throttles aggressively on historical sweeps — back off and retry
    # instead of surrendering the whole month window (a 72-window backfill
    # once lost 63 windows to 429s without this).
    articles, saw_rate_limit, last_error = _query_window(QUERY, start, end, max_records)
    if articles is None:
        # A 429 followed by a malformed/empty upstream response is still an
        # upstream availability incident. Preserve the 429 marker so the
        # caller leaves the cursor in place and reports the source as
        # deferred, rather than classifying the final parser symptom as a
        # repository failure.
        if gdelt_bq.available():
            try:
                from source_registry import discovery_terms as _terms
                bq_articles = gdelt_bq.query_window_articles(start, end, _terms())
                print(f"GDELT public API abandoned; BigQuery mirror recovered {len(bq_articles)} article(s)")
                return _fetch_trusted(bq_articles)
            except Exception as e:
                print(f"BigQuery fallback also failed: {e}")
        if saw_rate_limit:
            last_error = f"HTTP 429 (followed by upstream response error: {last_error or 'unknown error'})"
        raise RuntimeError(f"GDELT window abandoned after {QUERY_ATTEMPTS} attempts: {last_error or 'unknown error'}")

    # Rotating narrow sweeps ride the same window. Only the broad query is
    # health-bearing: a segment that stays rate-limited is skipped with a log
    # line and rotates back around within days, so it must not fail the run.
    for segment_query in _segment_queries_for_now():
        seg_articles, _, seg_error = _query_window(segment_query, start, end, max_records)
        if seg_articles is None:
            print(f"GDELT segment skipped ({seg_error}): {segment_query[-60:]}")
            continue
        print(f"GDELT segment {segment_query[-48:]}: {len(seg_articles)} article(s)")
        articles.extend(seg_articles)

    return _fetch_trusted(articles)


def _fetch_trusted(articles):
    """Trusted-domain gate + concurrent article fetch, shared by both the
    BigQuery-mirror and public-API paths."""
    candidates, seen = [], set()
    for a in articles:
        url = a.get("url")
        dom = _domain(a)
        if not url or url in seen or not _is_trusted(dom):
            continue
        seen.add(url)
        candidates.append((a, url, dom))

    def fetch_candidate(candidate):
        a, url, dom = candidate
        try:
            # Gentle staggering plus a small worker pool prevents one slow or
            # dead publisher from serially blocking an entire global window.
            time.sleep(0.2)
            text = _fetch_article(url)
        except Exception as e:
            print(f"GDELT fetch error {url}: {e}")
            return None
        if not text.strip():
            return None
        return {
            "source_type": "news",
            "source_name": dom,
            "verification_level": "bronze",
            "raw_text": f"{a.get('title', '')} {text}",
            "source_url": url,
            "company_name": None,
            "ticker": None,
            "filing_date": _seen_to_iso(a.get("seendate")),
        }

    results = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = [pool.submit(fetch_candidate, candidate) for candidate in candidates]
        for future in as_completed(futures):
            entry = future.result()
            if entry:
                results.append(entry)

    print(f"GDELT: {len(articles)} matched, {len(candidates)} trusted, {len(results)} fetched")
    return results
