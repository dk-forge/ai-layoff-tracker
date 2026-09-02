"""
Pulls AI-related layoff coverage from GDELT — a free, keyless, global news index
(2017→present). GDELT returns article metadata (url/title/domain/date); we fetch
each article and extract the layoff details downstream via the same extractor.

This is the historical + global press layer: free, worldwide, back to 2024,
and it's where AI-attributed layoff language actually appears.
"""
import hashlib
import html
import json
import os
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests

from sources import gdelt_bq

import gdelt_reach
import run_slice

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
    # Startup/VC newsrooms. Added 2026-07-23: our tech coverage sits well below
    # the tech-only trackers, and the difference is START-UP cuts (20-200 people)
    # that never reach a national wire. These are editorial newsrooms we can cite
    # directly - unlike crowdsourced trackers, which may only ever be a discovery
    # signal to verify against a primary source, never a source themselves.
    "news.crunchbase.com",                                    # United States
    "sifted.eu", "tech.eu",                                   # EU-wide
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
    # Added 2026-07-24 with the native-language query sweep: these countries
    # gained native search terms (varsel/zwolnienia/despedimento) but had no
    # allowlisted outlet, so every native hit would have died at the trust
    # gate. Papers of record + business dailies only.
    "di.se", "dn.se", "svd.se",                               # Sweden
    "rp.pl", "pb.pl",                                         # Poland
    "publico.pt", "jornaldenegocios.pt",                      # Portugal
    # --- Regional expansion: reputable national business/news outlets, added
    # to widen country coverage (a layoff only enters the tracker if a trusted
    # outlet covers it, so this list IS the reach lever). English editions
    # preferred; GDELT machine-translates the rest.
    "haaretz.com", "timesofisrael.com", "calcalistech.com",   # Israel
    "thenationalnews.com", "gulfnews.com", "khaleejtimes.com",  # United Arab Emirates
    "arabnews.com",                                             # Saudi Arabia
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
    "thelocal.se",                                           # Sweden
    "thelocal.de",                                           # Germany
    "thelocal.fr",                                           # France
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
    # --- 2026-07-23 international depth audit. Per-country counts showed the
    # same shape as the US finding: national dailies present, BUSINESS and TRADE
    # press absent - and that tier is what reports mid-size layoffs. Canada was
    # the worst: its only two outlets were French-language Quebec, so no
    # English-Canadian cut was visible at all. Comments are BARE country names
    # on purpose: the country-table parser drops any comment containing words
    # like business/press/trade/regional into an unattributed bucket.
    "thelogic.co", "biv.com", "obj.ca", "calgaryherald.com",  # Canada
    "winnipegfreepress.com", "canadianmanufacturing.com", "investmentexecutive.com", "canadiangrocer.com",  # Canada
    "mining.com",  # Canada
    "thetimes.com", "business-live.co.uk", "thebusinessdesk.com", "insidermedia.com",  # United Kingdom
    "insider.co.uk", "retailgazette.co.uk", "retail-week.com", "thegrocer.co.uk",  # United Kingdom
    "themanufacturer.com", "pressgazette.co.uk", "pmlive.com", "irishnews.com",  # United Kingdom
    "thehindubusinessline.com", "financialexpress.com", "cnbctv18.com", "businesstoday.in",  # India
    "entrackr.com", "the-ken.com", "fortuneindia.com", "medianama.com",  # India
    "businesspost.ie", "irishexaminer.com", "thecurrency.news", "siliconrepublic.com",  # Ireland
    "businessplus.ie", "breakingnews.ie", "checkout.ie", "farmersjournal.ie",  # Ireland
    "agriland.ie", "shelflife.ie", "echolive.ie",  # Ireland
    "theedgesingapore.com", "dealstreetasia.com", "asia.nikkei.com", "e27.co",  # Singapore
    "zaobao.com.sg", "hrmasia.com", "humanresourcesonline.net", "marketing-interactive.com",  # Singapore
    "splash247.com",  # Singapore
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
    # --- 2026-07-18 Survey gap-closure R4 (docs/SURVEY_GAP_CLOSURE_PLAN.md):
    # reviewed US trade/regional outlets that carried missed-event coverage.
    # Healthcare trade press is the motivating sector (Survey Jan
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
    # Added via the discovery-learning loop: a local-business newsroom carried a
    # Seattle HQ layoff our allowlist did not admit. Family-owned daily (est.
    # 1895), own editorial staff, covers business/construction/real-estate/legal.
    "djc.com",                    # United States — Seattle Daily Journal of Commerce (local business daily)
    "marketplace.org",            # APM Marketplace
    "kuow.org",                   # Seattle NPR (Boeing/Amazon/Microsoft)
    "wbur.org",                   # Boston NPR (biotech)
    "kqed.org",                   # SF Bay NPR (tech)
    # Corporate press-release wires: PRIMARY announcement text, the exact
    # channel Survey monitors. Allowlist-only — GDELT/NewsAPI surface the
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
    # --- Southern Africa (South Africa itself is already covered in the
    # regional expansion above: news24, businesslive, iol, moneyweb)
    "diggers.news",              # Zambia — News Diggers! (leading independent daily)
    "lusakatimes.com",           # Zambia — Lusaka Times (largest online newsroom; bot-blocks fetches — harmless for allowlist-only)
    "daily-mail.co.zm",          # Zambia — Zambia Daily Mail (state-owned daily of record; caveat)
    "newsday.co.zw",             # Zimbabwe — NewsDay (leading independent daily, Alpha Media)
    "theindependent.co.zw",      # Zimbabwe — The Zimbabwe Independent (business weekly)
    "newzimbabwe.com",           # Zimbabwe — NewZimbabwe.com (major independent online)
    "herald.co.zw",              # Zimbabwe — The Herald (state-owned daily of record; caveat; bot-blocks fetches)
    "mmegi.bw",                  # Botswana — Mmegi (leading independent daily)
    "sundaystandard.info",       # Botswana — Sunday Standard (independent investigative weekly)
    "gazettebw.com",             # Botswana — The Botswana Gazette (independent weekly)
    "namibian.com.na",           # Namibia — The Namibian (paper of record)
    "namibiansun.com",           # Namibia — Namibian Sun (major private daily, NMH)
    "neweralive.na",             # Namibia — New Era (state-owned daily; caveat)
    "thebrief.com.na",           # Namibia — The Brief (business-news digital daily)
    "mwnation.com",              # Malawi — The Nation (leading independent daily)
    "times.mw",                  # Malawi — The Daily Times / Times Group (major private daily)
    "nyasatimes.com",            # Malawi — Nyasa Times (independent online; diaspora-founded)
    "opais.co.mz",               # Mozambique — O País (leading private daily; site geo-slow from US but active — DNS + search verified)
    "jornalnoticias.co.mz",      # Mozambique — Notícias (largest daily; state-linked, caveat)
    "cartamz.com",               # Mozambique — Carta de Moçambique (independent online newsroom)
    "zitamar.com",               # Mozambique — Zitamar News (English business-news specialist)
    "jornaldeangola.ao",         # Angola — Jornal de Angola (state-owned daily of record; caveat)
    "expansao.co.ao",            # Angola — Expansão (leading business weekly)
    "novojornal.co.ao",          # Angola — Novo Jornal (major private weekly)
    "verangola.net",             # Angola — VerAngola (independent online, PT/EN)
    "lestimes.com",              # Lesotho — Lesotho Times (leading independent weekly)
    "sundayexpress.co.ls",       # Lesotho — Sunday Express (sister weekly, same newsroom)
    "publiceyenews.com",         # Lesotho — Public Eye (independent weekly)
    "times.co.sz",               # Eswatini — Times of Eswatini (only private daily; site geo-slow from US but active — DNS + search verified)
    "eswatiniobserver.com",      # Eswatini — Eswatini Observer (royal-conglomerate-owned daily; caveat; old observer.org.sz redirects here)
    "lexpress.mg",               # Madagascar — L'Express de Madagascar (leading daily)
    "midi-madagasikara.mg",      # Madagascar — Midi Madagasikara (largest daily)
    "lexpress.mu",               # Mauritius — L'Express (paper of record)
    "defimedia.info",            # Mauritius — Le Defi Media Group (major private)
    "seychellesnewsagency.com",  # Seychelles — Seychelles News Agency (gov't-backed but professional; caveat)
    "nation.sc",                 # Seychelles — Seychelles Nation (state-owned national daily; caveat)
    "alwatwan.net",              # Comoros — Al-Watwan (state-owned national daily; caveat — only daily)
    "lagazettedescomores.com",   # Comoros — La Gazette des Comores (leading private weekly)
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
    "zawya.com",                 # United Arab Emirates
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
    "islandsbusiness.com",       # Fiji
    "techrepublic.com", "electrek.co", "gamedeveloper.com",   # tech/EV/games trade
    # Games trade press — studio layoffs are a large, well-documented segment
    # these editorial outlets cover first (added 2026-07-19 after the ZA/UM
    # "up to 32" cuts appeared on IGN but nowhere in the then-allowlist).
    "ign.com", "gamesindustry.biz", "pcgamer.com", "polygon.com",
    "eurogamer.net", "kotaku.com", "videogameschronicle.com", "rockpapershotgun.com",
    # Sector trade press (added 2026-07-19 after the work-backwards audit:
    # Acrisure/Cigna/Disney-scale announcements ran here first and nowhere in
    # the then-allowlist). The Industry Dive network is corporate-announcement
    # dense and low-noise.
    "variety.com", "hollywoodreporter.com", "deadline.com",           # entertainment trade
    "insurancejournal.com", "businessinsurance.com",                  # insurance trade
    "hrexecutive.com", "hrdive.com", "cfodive.com", "ciodive.com",    # HR/finance/IT trade
    "healthcaredive.com", "fiercehealthcare.com", "fiercebiotech.com",# healthcare trade
    "beckershospitalreview.com", "beckerspayerissues.com",            # hospital/payer trade
    "retaildive.com", "supplychaindive.com", "bankingdive.com",       # retail/logistics/banking trade
    "utilitydive.com", "constructiondive.com",                        # utility/construction trade
    # --- 2026-07-23 backfill-diff sweep. A curated H1-2026 research pass found
    # 29 events we were missing, and the SOURCE pattern was the finding: we
    # already held every national-wire story (Amazon, Block, eBay, Intuit,
    # Atlassian, Snap, Disney...), and what we missed ran ONLY in state business
    # journals and vertical trade press. NJBIZ alone carried 4 of the 29. That
    # 200-1,500-employee band is exactly what fills the sector gaps, so the
    # allowlist was structurally blind to it. Same allowlist-only rules apply.
    "njbiz.com", "westfaironline.com", "mercerme.com",                # NJ/NY metro business press
    "insideindianabusiness.com", "crainsdetroit.com",                 # midwest business press
    "fooddive.com", "grocerydive.com", "restaurantdive.com",          # food/grocery trade
    "progressivegrocer.com", "fooddistributionmagazine.com",          # grocery/distribution trade
    "biospace.com", "endpts.com", "modernhealthcare.com",             # biotech/pharma/health trade
    "medtechdive.com", "biopharmadive.com", "drugdeliverybusiness.com",  # medtech/pharma trade
    "americanbanker.com", "manufacturingdive.com", "automotivedive.com",  # banking/manufacturing/auto trade
    "packagingdive.com", "agriculturedive.com", "truckingdive.com",   # packaging/ag/trucking trade
    # Startup/tech press surfaced by the 2026-07-19 aggregator diff (their
    # entries cited these outlets; most of the missed small/mid AI events
    # ran here first)
    # WARN-gap states (2026-07-19): MO and NM publish no usable notices and
    # HI/OK omit headcounts, so their strongest local press carries the load
    # for official-channel gaps. All four states remain covered via SEC + news.
    "kansascity.com",            # Missouri/Kansas — Kansas City Star
    "abqjournal.com",            # New Mexico — Albuquerque Journal
    "santafenewmexican.com",     # New Mexico — Santa Fe New Mexican
    "staradvertiser.com",        # Hawaii — Honolulu Star-Advertiser
    "civilbeat.org",             # Hawaii — Honolulu Civil Beat
    "oklahoman.com",             # Oklahoma — The Oklahoman
    "tulsaworld.com",            # Oklahoma — Tulsa World
    "inc42.com",                 # India — startup/tech press (Paytm, GoKwik-class events)
    "techinasia.com",            # Singapore
    "skift.com",                 # travel-industry trade (Mews, lastminute-class events)
    "chicago.suntimes.com",                                   # Chicago daily
    "wral.com",                                               # Raleigh NC (WRAL TechWire)
    "mprnews.org",                                            # Minnesota Public Radio
    "boston.com",                                             # Boston Globe Media
    "sanantonioreport.org",                                   # San Antonio nonprofit newsroom
    "fox5vegas.com",                                          # Las Vegas TV news
    "westfaironline.com",                                     # Westchester/Fairfield business
    "kvrr.com", "wwnytv.com",                                 # Fargo / Watertown TV news
    "recorder.com",                                           # Greenfield Recorder (MA)
    # --- 2026-09-02 reviewed outlets: BEGIN
    # The worldwide-coverage audit (TECHLOG 2026-09-02) measured the allowlist
    # keeping 2 of 244 Spanish candidates, 0 of 39 French and 0 of 50 Turkish
    # after the native-vocabulary fix landed, so those three are allowlist
    # failures, not language failures. Every domain between BEGIN and END is a
    # REVIEWED claim in railway/reviewed_outlets.json (outlet, language,
    # standing, caveat, date) and tests/test_reviewed_outlets.py fails on a
    # domain here that the registry does not argue for, on a registry entry
    # the allowlist does not carry, and on any allowlist domain that matches a
    # host in country_coverage.REFUSAL_LEDGER. Additive only.
    "efe.com",                   # Spain - Agencia EFE (state news agency, the wire)
    "europapress.es",            # Spain - Europa Press (largest private agency)
    "rtve.es",                   # Spain - RTVE (public broadcaster)
    "abc.es",                    # Spain - ABC (national daily of record)
    "larazon.es",                # Spain - La Razon (national daily)
    "elconfidencial.com",        # Spain - El Confidencial (digital daily, companies desk)
    "elespanol.com",             # Spain - El Espanol (digital daily; Invertia rides the suffix)
    "eldiario.es",               # Spain - elDiario.es (digital daily, labour desk)
    "elperiodico.com",           # Spain - El Periodico de Catalunya (Barcelona)
    "lavozdegalicia.es",         # Spain - La Voz de Galicia (largest regional daily)
    "elcorreo.com",              # Spain - El Correo (Basque industrial belt)
    "francetvinfo.fr",           # France - franceinfo (public broadcaster)
    "bfmtv.com",                 # France - BFM TV / BFM Business
    "ouest-france.fr",           # France - Ouest-France (largest-circulation daily)
    "leparisien.fr",             # France - Le Parisien / Aujourd'hui en France
    "la-croix.com",              # France - La Croix (national daily)
    "lepoint.fr",                # France - Le Point (carries the AFP economy wire)
    "challenges.fr",             # France - Challenges (business weekly)
    "capital.fr",                # France - Capital (business magazine)
    "usinenouvelle.com",         # France - L'Usine Nouvelle (industrial trade press, plant-level PSEs)
    "rfi.fr",                    # France - RFI (public international broadcaster)
    "lavoixdunord.fr",           # France - La Voix du Nord (Hauts-de-France industry)
    "aa.com.tr",                 # Turkey - Anadolu Ajansi (state news agency, the wire)
    "trthaber.com",              # Turkey - TRT Haber (public broadcaster)
    "bloomberght.com",           # Turkey - Bloomberg HT (business broadcaster)
    "ekonomim.com",              # Turkey - Dunya / Ekonomim (business daily; dunya.com is its old host)
    "hurriyet.com.tr",           # Turkey - Hurriyet (largest daily; Turkish edition)
    "haberturk.com",             # Turkey - Haberturk (news channel, economy desk)
    "sozcu.com.tr",              # Turkey - Sozcu (largest opposition daily)
    "t24.com.tr",                # Turkey - T24 (independent digital daily)
    "evrensel.net",              # Turkey - Evrensel (labour daily; union-aligned)
    "dha.com.tr",                # Turkey - DHA (largest private domestic agency)
    # --- 2026-09-02 reviewed outlets: END
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
# How long to wait for ONE query. Was a hardcoded 30 until 2026-08-29, which
# made an operator who set an environment variable for it change nothing at
# all -- the silent no-op this repo keeps finding.
#
# 30s sits BELOW the endpoint's measured answering latency (19.8-75s+ on
# 2026-08-29), so some windows are abandoned by our own clock rather than by
# GDELT. Raising it recovers those AND multiplies the wall clock of a run that
# is already timing out: run 33094996142 self-cancelled at 45 minutes.
#
# So it is CLAMPED, like every other knob here. The ceiling is 90s because
# QUERY_ATTEMPTS(5) x 90s is already 7.5 minutes for a single window before
# backoff, and the backfill's own deadline has to survive it. The default is
# unchanged, so this commit alters no behaviour by itself.
def _clamped_query_timeout(raw=None):
    """Seconds to wait for ONE query, clamped. Pure, so it is testable WITHOUT
    reloading this module.

    That matters: the first version of this test reloaded the module to observe
    the constant, which rebuilt `_THROTTLE_BODY_RX` -- and `gdelt_backfill`
    imports that object BY REFERENCE, so the identity assertion pinning the two
    to one definition started failing on main. A test that reloads a module
    other modules hold references into breaks them, and the breakage lands
    somewhere else entirely.
    """
    if raw is None:
        raw = os.environ.get("GDELT_QUERY_TIMEOUT", "30")
    return max(5, min(90, int(raw)))


QUERY_TIMEOUT_SECONDS = _clamped_query_timeout()

# --- Window coverage: bisection, the work ledger, and the run verdict --------
#
# The old worldwide path had three silent coverage leaks, each measured in
# production (a run showing 900 returned / 99 kept / 801 dropped, one query
# capped, one window abandoned):
#
#   1. `sortby=datedesc` + `maxrecords=250` (or the mirror's `LIMIT 900`) over a
#      36-hour window means a busy window is TRUNCATED at the newest N and the
#      tail is invisible. `_collect_window` splits a capped window in half and
#      re-queries each half until every sub-window returns UNDER the cap (or a
#      sensible floor is reached and it is recorded `partial`, never dropped).
#   2. A window the public API abandoned but the BigQuery mirror recovered used
#      to RETURN EARLY, skipping every other sweep for that run. It no longer
#      does: the recovered articles are ASSIGNED and the run CONTINUES.
#   3. An unfinished window vanished. Now every (query-family, window) slot is
#      written to a committed ledger as queued/attempted/complete/partial/failed
#      and RETRIED across runs until complete.
#
# The ledger is a committed JSON file, mirroring alert_state.json /
# source_state.json / headline_incidents.json: any session can read what is
# still owed, and an unfinished cursor survives the run. (Transport caveat: the
# live cron runs on Railway, which cannot git-commit; the ledger persists wher-
# ever the file does — a checkout, a backfill, a runner that commits — and is
# harmless where it does not. See the PR notes.)
WORK_LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gdelt_work_ledger.json")

# Bisection floor: never split a window below this. A busy hour that still caps
# is recorded `partial` (we took the newest N of it) rather than split into
# minute-slivers that each cost a full rate-limited request for diminishing
# return. One hour is the granularity `seendate` itself resolves to.
MIN_BISECT_WINDOW = timedelta(hours=1)

# How long an incomplete slot is worth retrying. A window older than this is a
# past gap, not present work; it is pruned with a log line rather than queued
# forever. Two weeks mirrors the orphan-report window in run_completion.py.
LEDGER_RETRY_HORIZON = timedelta(days=14)

# Cap the retry fan-out so a backlog cannot make one run issue unbounded extra
# queries. Oldest-incomplete first; the rest wait for the next run.
MAX_RETRY_SLOTS_PER_RUN = max(0, min(20, int(os.environ.get("GDELT_MAX_RETRY_SLOTS", "6"))))

# The run verdict, read by cron.py to decide the health status. A run is
# `degraded` (not silently green) when ANY planned slot did not COMPLETE — a
# capped-to-floor window, an abandoned sweep, a mirror walk that hit its page
# ceiling. A fully-abandoned broad window still RAISES (loud, non-zero); this
# flag is for the partial case that keeps its rows.
_LAST_RUN_INCOMPLETE = False


def last_run_status():
    """'ok' if every planned slot completed last run, else 'degraded'.

    cron.py reports gdelt health with this, so a capped or abandoned window is
    visible on the health page instead of being buried under a green 'ok'.
    """
    return "degraded" if _LAST_RUN_INCOMPLETE else "ok"


def _win_stamp(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slot_key(family, query, start, end):
    """Stable identity for one (query-family, window) unit of work.

    The query text is folded in via a short hash so two segment queries over the
    same window are distinct slots, without spelling the query into the key.
    """
    qh = hashlib.sha1((query or "").encode("utf-8")).hexdigest()[:10]
    return f"{family}|{qh}|{_win_stamp(start)}|{_win_stamp(end)}"


# --- Ledger transport: the live cron cannot keep a file ---------------------
#
# WORK_LEDGER_PATH is the right store for a CHECKOUT (a backfill, a test, a
# session) and the wrong one for the LIVE CRON. Railway runs this in an
# ephemeral container with no volume and no git identity, so the file written
# at the end of a run is discarded along with the container. From PR #223 until
# 2026-08-28 that made the entire retry-unfinished-work mechanism INERT in
# production: the committed ledger held 0 slots for the whole period while a
# single production run abandoned 7 of 12 windows, and every one of those
# windows was LOST rather than retried. Nothing reported it, because the health
# page's `degraded` reads as "known partial coverage, queued for retry" —
# which is exactly what the ledger was supposed to make true.
#
# The fix is the transport cron.py already uses for its spend records: POST to
# the keyed /tracker-meta endpoint, which any checkout can read back. The file
# is KEPT as well, because it is what a local run, a test and a reviewer read.
#
# Best-effort in BOTH directions, deliberately: a ledger is bookkeeping, and
# bookkeeping must never take down an ingest run. A failed sync costs one run
# of retry memory, which is strictly better than the status quo of all of it.
LEDGER_REMOTE_TIMEOUT = 30

# Two process-level guards, because `pull_gdelt_between` is called ONCE per run
# by the live cron but ONCE PER WEEK-WINDOW by gdelt_backfill.py. A multi-year
# backfill is hundreds of windows, and this host is a shared Bluehost account
# that has returned 504 under load (TECHLOG 2026-07-31). Un-guarded, the sync
# would add two requests per window to a job that already posts two health
# notes per window.
#
#   * the remote READ is needed once per process: after the first union, the
#     file written at the end of each window carries the state forward.
#   * the remote WRITE is skipped when the slot payload is byte-identical to
#     the last one accepted, so an idle stretch of windows costs nothing.
#
# Neither guard can turn a needed sync into a skipped one: the read flag is set
# only on a SUCCESSFUL union, and the write hash only on a 200.
_REMOTE_LEDGER_READ = False
_REMOTE_LEDGER_PUSHED = None

# How often the ledger may be pushed DURING a run. The end-of-run save cannot
# be the only one: railway-cron wrote no end-of-run record on 2026-08-16,
# 2026-08-19 or 2026-08-26, and ops_status [2e] shows the matching collector
# runs starting and never finishing -- so the runs that lose their ledger are
# exactly the ones whose abandoned windows most need retrying. Two minutes is
# chosen against the 5s REQUEST_DELAY: a run cannot issue enough queries in
# that time for the sync to be a meaningful share of its request budget.
LEDGER_SYNC_INTERVAL_SECONDS = 120
_LAST_MID_RUN_SYNC = None


def _remote_tracker_meta(body=None):
    """POST to the keyed /tracker-meta endpoint; return the stored meta or None.

    An EMPTY body is the documented read — the endpoint returns the whole meta
    blob — which is the same call spend.py uses to harvest Railway's run
    records. Returns None whenever the endpoint cannot be used, and a None is
    always UNKNOWN (could not sync), never "nothing is owed".
    """
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return None
    try:
        resp = requests.post(
            f"{site}/wp-json/layoffs/v1/tracker-meta",
            json=body or {},
            headers={"X-Layoff-API-Key": key,
                     # ModSecurity blocks python-requests against this host.
                     "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"},
            timeout=LEDGER_REMOTE_TIMEOUT)
        if resp.status_code != 200:
            print(f"GDELT work ledger: /tracker-meta HTTP {resp.status_code} — "
                  f"this run's retry memory is local only")
            return None
        return resp.json()
    except Exception as exc:
        print(f"GDELT work ledger: /tracker-meta unreachable ({exc}) — "
              f"this run's retry memory is local only")
        return None


def _merge_slots(local, remote):
    """Union two slot maps, keeping the more recently UPDATED record per key.

    Neither side is authoritative and that is the point: a checkout holds slots
    the cron never saw (a backfill's windows) and the cron holds slots no
    checkout ever will. Ties go to LOCAL, so a run that just recorded an
    outcome is never overwritten by the copy it read at startup.
    """
    out = {k: v for k, v in (remote or {}).items() if isinstance(v, dict)}
    for key, slot in (local or {}).items():
        if not isinstance(slot, dict):
            continue
        other = out.get(key)
        if (not isinstance(other, dict)
                or str(slot.get("updated") or "") >= str(other.get("updated") or "")):
            out[key] = slot
    return out


def _load_work_ledger(path=WORK_LEDGER_PATH, remote=True):
    """Read the work ledger — the committed file UNIONED with the live one.

    A ledger that cannot be parsed is not a ledger that says nothing is owed, but
    an ingest run must never be taken down by its own bookkeeping — so an
    unreadable file starts an empty one and the run proceeds (and re-records).
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or not isinstance(data.get("slots"), dict):
            raise ValueError("work ledger shape")
    except FileNotFoundError:
        data = {"slots": {}}
    except Exception as exc:
        print(f"GDELT work ledger unreadable ({exc}); starting fresh")
        data = {"slots": {}}
    global _REMOTE_LEDGER_READ
    if remote and not _REMOTE_LEDGER_READ:
        meta = _remote_tracker_meta()
        if isinstance(meta, dict) and isinstance(meta.get("gdelt_ledger"), dict):
            _REMOTE_LEDGER_READ = True
            before = len(data["slots"])
            data["slots"] = _merge_slots(data["slots"], meta["gdelt_ledger"])
            gained = len(data["slots"]) - before
            if gained:
                print(f"GDELT work ledger: recovered {gained} slot(s) from "
                      f"/tracker-meta that this container had no copy of")
    return data


def _pruned_slots(ledger, *, quiet=False):
    """The slots worth keeping: drop what is finished or too old to retry."""
    now = datetime.now(timezone.utc)
    kept = {}
    for key, slot in ledger.get("slots", {}).items():
        end = _parse_stamp(slot.get("window_end"))
        aged_out = end is not None and (now - end) > LEDGER_RETRY_HORIZON
        if slot.get("status") == "complete":
            # Keep a completed slot only briefly, as a dedupe guard against
            # re-queuing the same window inside one horizon; then let it go.
            if aged_out:
                continue
        elif aged_out:
            # An incomplete window older than the horizon is a past gap, not
            # present work. Drop it loudly rather than retry it forever --
            # but only from the END-of-run save, or a throttled mid-run sync
            # would reprint the same line every couple of minutes.
            if not quiet:
                print(f"GDELT work ledger: dropping aged-out incomplete slot {key}")
            continue
        kept[key] = slot
    return {k: kept[k] for k in sorted(kept)}


def _push_slots_remote(slots):
    """Push the slot map unless it is byte-identical to the last ACCEPTED push."""
    global _REMOTE_LEDGER_PUSHED
    fingerprint = json.dumps(slots, sort_keys=True)
    if fingerprint == _REMOTE_LEDGER_PUSHED:
        # Nothing moved since the last accepted push. A backfill's quiet
        # window costs no request at all.
        return False
    if _remote_tracker_meta({"set_gdelt_ledger": slots}) is None:
        return False
    _REMOTE_LEDGER_PUSHED = fingerprint
    return True


def _sync_ledger_mid_run(ledger):
    """Throttled mid-run push, so a run that DIES does not lose what it learned.

    The end-of-run save is not enough on its own, because dying mid-run is a
    thing this job measurably does: railway-cron wrote no end-of-run record on
    2026-08-16, 2026-08-19 or 2026-08-26, and `ops_status [2e]` shows the
    matching `gdelt`/`local_news`/`regional_feeds` runs starting and never
    finishing. A ledger that is only written at the end is lost in exactly the
    runs whose abandoned windows most need retrying.

    Throttled to one push per LEDGER_SYNC_INTERVAL_SECONDS, and skipped
    entirely when nothing changed (`_push_slots_remote`), so the worst case is
    a handful of requests across a long run rather than one per slot.
    """
    global _LAST_MID_RUN_SYNC
    now = time.monotonic()
    if _LAST_MID_RUN_SYNC is not None and (now - _LAST_MID_RUN_SYNC) < LEDGER_SYNC_INTERVAL_SECONDS:
        return
    _LAST_MID_RUN_SYNC = now
    _push_slots_remote(_pruned_slots(ledger, quiet=True))


def _save_work_ledger(ledger, path=WORK_LEDGER_PATH, remote=True):
    """Persist the ledger, pruning what is finished or too old to retry."""
    payload = {"slots": _pruned_slots(ledger)}
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")
    except OSError as exc:
        # A read-only or absent path is survivable now that the remote copy
        # below is the one the live cron actually depends on.
        print(f"GDELT work ledger: could not write {path} ({exc})")
    if remote and _push_slots_remote(payload["slots"]):
        print(f"GDELT work ledger: {len(payload['slots'])} slot(s) persisted "
              f"to /tracker-meta")


def _parse_stamp(stamp):
    try:
        return datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _retry_delay(response, attempt):
    """Honor a bounded Retry-After hint, with jitter for shared API fairness."""
    hinted = 0
    try:
        hinted = int((response.headers.get("Retry-After") or "").strip()) if response else 0
    except (AttributeError, TypeError, ValueError):
        hinted = 0
    return min(180, max(QUERY_BACKOFF_SECONDS * (attempt + 1), hinted)) + random.uniform(0, 3)


# --- GDELT signals overload with HTTP 200 and a sentence -------------------
#
# MEASURED 2026-08-29, production query shape (broad QUERY, maxrecords=250,
# 36h window), from a single address at >=5s spacing. The DOC 2.0 API does not
# reliably use status codes. Of the responses that were not usable JSON, the
# bodies observed were:
#
#     HTTP 200  "Your query was too short or too long."
#     HTTP 200  "Please limit requests to one every 5 seconds."
#     HTTP 429  "Please limit requests to one every 5 seconds."
#
# The first is NOT a statement about the query. The identical 941-character
# query was rejected and then accepted, twice, minutes apart, with a short
# control query succeeding throughout — so it is a load-shed message wearing a
# validation message's words. Do not "fix" it by shortening the vocabulary:
# that was tested (16 terms rejected, 24 terms accepted, 26 rejected) and the
# boundary does not reproduce.
#
# WHY THIS MATTERS MORE THAN IT LOOKS. `resp.raise_for_status()` passes on a
# 200, `resp.json()` then raises `JSONDecodeError`, and the generic `except`
# below recorded `last_error = "Expecting value: line 1 column 1 (char 0)"`
# with `saw_rate_limit` still False. Three things followed, all of them wrong
# information rather than wrong behaviour:
#
#   1. `gdelt_reach` recorded `rate_limited=0` on a throttled run. Telling
#      "throttled" from "broken" is the entire reason that module exists, and
#      it was blind to the throttle signal this endpoint actually sends.
#   2. The RuntimeError raised for a fully-abandoned broad window quoted a JSON
#      parser at the reader instead of the server's own sentence.
#   3. `gdelt_backfill._is_upstream_throttle` greps the error text for "429" /
#      "rate limit" / "timeout". A JSONDecodeError matches none of them, so an
#      upstream throttle RAISED — a red run and a breakage email that no human
#      can act on, which is precisely what that function's comment says it
#      exists to prevent.
#
# This classifier changes no cadence and issues no extra request: the retry
# schedule, QUERY_ATTEMPTS and REQUEST_DELAY are untouched. It only reads the
# sentence the server already sent. A longer backoff is deliberately NOT the
# answer here (see CLAUDE.md); the answer is to stop discarding the diagnosis.
_THROTTLE_BODY_RX = re.compile(
    r"limit\s+requests|one\s+every\s+\d+\s*sec|rate\s*limit|too\s+many\s+requests",
    re.I)
# A short non-JSON body is an error message; a long one is a page we should not
# try to summarise into a health `detail` capped at 240 characters.
_MAX_SIGNAL_BODY = 200


def _upstream_text_signal(body):
    """Classify a non-JSON GDELT body. Returns (kind, message) or None.

    kind is "throttle" when the server told us to slow down (in any of the
    status codes it says it under), else "upstream" for any other plain-text
    refusal. None means the body looks like the JSON we asked for.
    """
    text = body or ""
    # Sniff the first non-space characters only. A good response is a
    # half-megabyte of JSON and this runs on every successful query; stripping
    # or splitting the whole body to learn it starts with `{` would copy it
    # twice for nothing. The expensive normalisation below is reached only by
    # bodies already known NOT to be the JSON we asked for.
    head = text[:64].lstrip()
    if not head or head[0] in "{[":
        return None
    message = " ".join(text.split())[:_MAX_SIGNAL_BODY]
    if _THROTTLE_BODY_RX.search(message):
        # The message is passed through VERBATIM, not rewritten into words a
        # downstream matcher happens to grep for. `_THROTTLE_BODY_RX` is the
        # one definition of "the server told us to slow down", and
        # gdelt_backfill._is_upstream_throttle imports THIS regex rather than
        # keeping a second list that can drift out of agreement with it.
        return "throttle", message
    return "upstream", message


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


def window_article_markup(markup):
    """The text window this collector feeds the extractor, from page markup.

    Split out from the fetch so a caller that already holds the bytes -- the
    model comparison reads FROZEN archive snapshots, which need their own
    retry and pacing -- gets the identical window instead of a second
    implementation of it. Pure: no network, no clock.
    """
    text = _strip_html(markup[:MAX_DOC_BYTES])
    lowered = text.lower()
    for kw in discovery_terms():
        idx = lowered.find(kw)
        if idx != -1:
            start = max(0, idx - 400)
            return text[start:start + RAW_TEXT_LIMIT]
    return text[:RAW_TEXT_LIMIT]


def _fetch_article(url):
    """Fetch an article and return a text window centered on the layoff mention."""
    resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=25)
    resp.raise_for_status()
    return window_article_markup(resp.text)


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
    # WARN-gap states get dedicated rotation slots: their official channels
    # are silent, so press discovery must not miss them
    '"Missouri"', '"New Mexico"', '"Hawaii"', '"Oklahoma"',
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
    # Corporate-announcement phrasings (2026-07-19 audit: Survey-style
    # events surface in earnings-call coverage that says "restructuring" or
    # "workforce reduction", not "layoff" — these segments pull that slice
    # above the maxrecords cutoff)
    '"workforce reduction" percent', '"restructuring" "severance"',
    '"job cuts" "earnings"', '"redundancy" "consultation"',
    '"voluntary separation"', '"reduction in force" employees',
    '"cut" "workforce" "announced"', '"eliminate" "positions"',
    # AI-framing phrasings taken from how aggregator-tracked events were
    # actually headlined (2026-07-19 diff): loose attributions surface with
    # these words, feeding the ai_linked broad tier
    '"amid AI push"', '"to focus on AI"', '"AI-first" layoffs',
    '"AI reshapes"', '"invest in AI" jobs', '"AI transformation" cuts',
    '"AI restructuring"', '"shift to AI"',
    # Adjacent-automation vocabulary (2026-07-24 audit): employers and press
    # increasingly name the MECHANISM (agents, chatbots, robots, generative
    # AI) rather than the word "AI". Discovery-side only - the attribution
    # gate is untouched, so these can surface candidates but never loosen
    # what counts as an AI-attributed cut (verbatim employer quote required).
    '"AI agents" "jobs"', '"agentic AI" workforce', '"generative AI" "job cuts"',
    '"chatbots" "laid off"', '"chatbot" "replaced"', '"robots" "replace workers"',
    '"automated" "positions eliminated"', '"automation" "job losses"',
    '"digital workers" jobs', '"AI adoption" "headcount"',
    # Dialect-synonym segments (rarer phrasings ride the rotation instead of
    # the base OR-set): Commonwealth/African/Asian English + translated press
    '"sackings"', '"job shedding"', '"shed jobs"', '"slash jobs"',
    '"voluntary separation scheme"', '"mass termination"',
    '"jobs terminated"', '"staff reduction"', '"retrenched workers"',
    # Public-sector and education segments (2026-07-19 Survey sector
    # decomposition: government + education + nonprofit are ~9% of their
    # total and never file WARN or 8-K — but the big events make the press)
    '"school district" "layoffs"', '"university" "job cuts"',
    '"state employees" "layoffs"', '"federal employees" "layoffs"',
    '"city workers" "laid off"', '"nonprofit" "layoffs"',
    '"hospital" "layoffs"', '"school" "positions eliminated"',
    # Government-sector expansion (#31): federal RIFs, agencies, and local
    # government cuts leave no WARN/8-K, so press rotation is the only channel.
    '"federal agency" "job cuts"', '"public sector" "layoffs"',
    '"reduction in force" "federal"', '"government agency" "workforce"',
    '"municipal" "layoffs"', '"county" "job cuts"',
    '"public employees" "laid off"', '"agency" "eliminate positions"',
    # More AI-attribution framings (2026-07-20) — broaden AI recall beyond the
    # existing block; the employer's AI story surfaces in these phrasings too.
    '"generative AI" "layoffs"', '"AI-driven" "job cuts"', '"AI efficiency"',
    '"AI adoption" "jobs"', '"cost cutting" "AI"', '"AI investment" "workforce"',
    '"agentic AI" "roles"', '"automate" "roles"',
    # Buyouts / attrition / early-retirement — the announcement-survey slice
    # that files no WARN/8-K yet is widely reported (helps close the coverage gap).
    '"buyouts" "employees"', '"early retirement" "program"',
    '"deferred resignation"', '"attrition" "reduce"', '"voluntary exit"',
    '"hiring freeze" "cuts"',
)
SEGMENT_QUERIES_PER_RUN = max(0, min(8, int(os.environ.get("GDELT_SEGMENT_QUERIES", "4"))))

# Native-language layoff terms, run STANDALONE (never ANDed with the English
# base: segments require the English vocabulary to co-match, which native-
# language originals cannot do). This closes the euphemism-translation gap:
# Swedish press says "varsel" which machine-translates to "notice", Italian
# says "esuberi" -> "surpluses" - words the English net deliberately ignores,
# so those stories never surfaced. Terms below are the PRECISION-SELECTED
# subset of a 12-language terminology sweep (2026-07-24, three independent
# model consultations agreed; each term verified unambiguous - it only ever
# means mass job cuts). Deliberately EXCLUDED as too ambiguous alone: bare
# "varsel" (also weather warnings), "optimering"/"优化"-style euphemisms,
# "Restrukturierung"/"reorganisatie" (M&A noise) - candidates for a sampled
# second wave, not a blind add. Same downstream gates as everything else:
# trusted-domain allowlist + extractor + verbatim-count check (which already
# accepts EU number formats like 1.200).
NATIVE_TERMS = (
    '"Stellenabbau"',            # de: job reduction (the German press headline word)
    '"Massenentlassung"',        # de: mass dismissal (legal)
    '"suppression de postes"',   # fr: elimination of positions
    '"licenciement collectif"',  # fr: collective dismissal (legal)
    '"despido colectivo"',       # es: collective dismissal (legal)
    '"recorte de plantilla"',    # es: workforce cut (press)
    '"licenziamento collettivo"',# it: collective dismissal (legal)
    '"esuberi"',                 # it: redundancies (the Italian headline word)
    '"massaontslag"',            # nl: mass dismissal
    '"zwolnienia grupowe"',      # pl: group dismissals (legal)
    '"varsel om uppsägning"',    # sv: redundancy notice (two-word precise form)
    '"demissão em massa"',       # pt-BR: mass dismissal
    '"despedimento coletivo"',   # pt-PT: collective dismissal (legal)
    '"大规模裁员"',                # zh: large-scale layoffs
)
# English corporate-doublespeak sweep, SAME standalone mechanism as the native
# terms and for the same reason: a segment query ANDs the base layoff vocabulary
# in front, so "delayering the management structure" (no base word) could never
# match a segment — the exact article the euphemism hunt exists for (audit
# 2026-07-25; they were originally shipped as paired segments, i.e. dead).
# Each pairs the euphemism with a headcount word for precision, NOT with the
# base vocabulary. Same downstream gates as everything else.
EUPHEMISM_TERMS = (
    '"cost optimization" jobs', '"efficiency program" roles',
    '"operating model" redundancies', '"transformation program" "job cuts"',
    '"strategic realignment" employees', '"delayering" management',
    '"flattening" "management layers"', '"headcount optimization"',
    '"early retirement" buyout employees', '"buyout" "reduce headcount"',
    '"store rationalization"', '"branch" "optimization" jobs',
    '"capacity reduction" plant', '"plant optimization" workers',
    '"service line" consolidation staff', '"network optimization" jobs',
)
NATIVE_QUERIES_PER_RUN = max(0, min(4, int(os.environ.get("GDELT_NATIVE_QUERIES", "2"))))
EUPHEMISM_QUERIES_PER_RUN = max(0, min(4, int(os.environ.get("GDELT_EUPHEMISM_QUERIES", "2"))))
# Standalone EUROPEAN-LANGUAGE sweep: works-council-driven cuts (a Spanish ERE,
# German Stellenabbau, French plan social) surface in national business press
# before/without English coverage, and European HQs never file an SEC 8-K.
# One language per run. This ring picked its slice with `tm_yday % 4` until
# 2026-09-02 -- a hand-rolled run counter the ring guard did not catch because
# its pattern looked for `tm_yday * N`. At one run a day it happened to step by
# one; at any other cadence it would repeat or skip. It is a ring like the
# other three now: `run_slice.rotate`, read by tests/test_rotation_covers_ring.
# Toggle: GDELT_EURO_SWEEP=0 (kept) or GDELT_EURO_QUERIES=0.
EURO_TERMS = (
    '"Stellenabbau" OR "Entlassungen" OR "Arbeitsplätze streichen"',
    '"plan social" OR "licenciements" OR "suppressions de postes"',
    '"expediente de regulación de empleo" OR "despidos colectivos"',
    '"licenziamenti" OR "esuberi"',
)
EURO_QUERIES_PER_RUN = max(0, min(4, int(os.environ.get("GDELT_EURO_QUERIES", "1"))))


def _segment_queries_for_now():
    """Deterministic rotation over the segment matrix (0 disables).

    The slice comes from `run_slice.rotate`, which steps by exactly one run.
    This used to compute its own index from `tm_yday * 2 + (hour < 17)`, a
    hardcoded twice-a-day cadence that stopped being true on 2026-08-14 and
    stretched this ring's full sweep from 15 days to 44 with no signal.
    """
    picked = run_slice.rotate(SEGMENT_TERMS, SEGMENT_QUERIES_PER_RUN)
    return [f"{QUERY} {term}" for term in picked]


def _query_window(query, start, end, max_records, reach_label="broad"):
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
                                headers={"User-Agent": BROWSER_UA},
                                timeout=QUERY_TIMEOUT_SECONDS)
            if resp.status_code == 429:
                saw_rate_limit = True
                last_error = "HTTP 429"
                delay = _retry_delay(resp, attempt)
                print(f"GDELT 429 (attempt {attempt + 1}/{QUERY_ATTEMPTS}), retrying after {delay:.0f}s")
                continue
            resp.raise_for_status()
            # A 200 is not an answer. GDELT refuses in plain text at 200 as
            # readily as at 429 (see _upstream_text_signal); parsing that as
            # JSON threw away the diagnosis and left a throttle looking like a
            # broken parser. Cadence is unchanged — this classifies, it does
            # not wait longer or ask again.
            signal = _upstream_text_signal(resp.text)
            if signal:
                kind, message = signal
                if kind == "throttle":
                    saw_rate_limit = True
                last_error = f"HTTP {resp.status_code} {message}"
                print(f"GDELT {kind} body (attempt {attempt + 1}/{QUERY_ATTEMPTS}): {message}")
                continue
            articles = resp.json().get("articles", []) or []
            break
        except Exception as e:
            last_error = str(e)
            print(f"GDELT query error (attempt {attempt + 1}/{QUERY_ATTEMPTS}): {e}")
    # Measurement only (see railway/gdelt_reach.py). `articles is None` is an
    # ABANDONED window and is recorded as such, never as a zero: "GDELT said
    # there was nothing" and "we never found out" are different days.
    gdelt_reach.current().note_query(
        reach_label, None if articles is None else len(articles),
        max_records, abandoned=articles is None, rate_limited=saw_rate_limit)
    return articles, saw_rate_limit, last_error


def _collect_window(query, start, end, max_records, reach_label, floor=MIN_BISECT_WINDOW):
    """Query one window via the public API, BISECTING it when it caps.

    Returns (articles, status, saw_rate_limit, last_error):
      * articles is None only when the FIRST query of a window was abandoned
        after every attempt (an availability incident the caller handles).
      * status is "complete" (returned under the cap), "partial" (capped and
        either at the split floor or with a capped/abandoned sub-window), or
        "abandoned" (articles is None).

    `sortby=datedesc` + `maxrecords` truncates a busy window at the newest N and
    drops the tail with no trace. Splitting until each half returns under the cap
    walks the WHOLE window instead. Overlap at the split point is harmless: the
    trusted-domain gate dedupes by URL downstream.
    """
    articles, saw_rl, err = _query_window(query, start, end, max_records, reach_label)
    if articles is None:
        return None, "abandoned", saw_rl, err
    if len(articles) < max_records:
        return articles, "complete", saw_rl, err
    # Capped: the window is truncated at the newest max_records.
    span = end - start
    if span <= floor:
        print(f"GDELT [{reach_label}] window capped at floor "
              f"{_win_stamp(start)}..{_win_stamp(end)}: keeping newest {len(articles)}, PARTIAL")
        return articles, "partial", saw_rl, err
    mid = start + span / 2
    left, ls, _, _ = _collect_window(query, start, mid, max_records, reach_label, floor)
    right, rs, _, _ = _collect_window(query, mid, end, max_records, reach_label, floor)
    combined = list(articles)  # keep the capped parent page too; dedup is downstream
    if left:
        combined.extend(left)
    if right:
        combined.extend(right)
    status = "complete" if (ls == "complete" and rs == "complete") else "partial"
    return combined, status, saw_rl, err


def _collect_mirror(start, end):
    """Walk the BigQuery mirror to completion. Returns (articles, status).

    Deterministic (date, url) pagination, so a capped window is walked page by
    page instead of losing everything past the first 900 rows. status is
    "complete" unless the walk hit its page ceiling (then "partial").
    """
    from source_registry import discovery_terms as _terms
    from sources.native_layoff_terms import mirror_title_terms
    # The mirror matches ORIGINAL-language page titles, and until 2026-09-02 the
    # regex held only the English vocabulary: a "Stellenabbau" headline reached
    # the pipeline only if GDELT's theme tagger had also filed it under
    # UNEMPLOYMENT. The native phrases ride the same scan (the regex grows, the
    # partition filter does not), so this costs bytes nothing and candidates
    # something -- which the allowlist and the gate then judge as usual.
    arts, complete = gdelt_bq.query_window_walk(start, end, _terms() + mirror_title_terms())
    # SAY whether coverage was lost; do not let note_query infer it. The walk
    # already knows -- `complete` is false only when it hit MAX_PAGES -- and
    # MIRROR_LIMIT is a PAGE size, so the "returned >= max_records" inference
    # reads a full first page as a truncated answer. That is why every mirror
    # run since 2026-08-26 reported a binding cap on a window it had walked to
    # the bottom. The limit is still passed because it is a true fact about the
    # request and [2d] prints it.
    gdelt_reach.current().note_query("mirror", len(arts), gdelt_bq.MIRROR_LIMIT,
                                     truncated=not complete)
    return arts, ("complete" if complete else "partial")


def _span_of(articles):
    """(oldest, newest) GDELT seendate over a set of articles, or (None, None)."""
    stamps = sorted(a.get("seendate") for a in articles if a.get("seendate"))
    return (stamps[0], stamps[-1]) if stamps else (None, None)


def _record_slot(ledger, family, query, start, end, status, articles, *, cap_hit=False):
    """Fold one (family, window) outcome into the work ledger. Returns its key.

    The query text is stored for sweeps (our OWN discovery vocabulary — never a
    name), so a partial/failed slot can be re-issued verbatim on a later run.
    The broad query is rebuilt from module QUERY at retry time, not stored.
    """
    key = _slot_key(family, query, start, end)
    now_iso = _win_stamp(datetime.now(timezone.utc))
    oldest, newest = _span_of(articles)
    slot = ledger["slots"].get(key, {})
    slot.update({
        "family": family,
        "window_start": _win_stamp(start),
        "window_end": _win_stamp(end),
        "status": status,
        "returned": len(articles),
        "cap_hit": bool(cap_hit),
        "oldest": oldest,
        "newest": newest,
        # A slot QUEUED by the outage breaker was never attempted this run, so
        # queueing does not spend one of its attempts.
        "attempts": int(slot.get("attempts", 0)) + (0 if status == "queued" else 1),
        "first_seen": slot.get("first_seen", now_iso),
        "updated": now_iso,
    })
    if family != "broad":
        slot["query_text"] = query
    ledger["slots"][key] = slot
    # The one place a slot changes, so the one place worth syncing from. The
    # call is throttled and skips an unchanged ledger, so this is cheap.
    _sync_ledger_mid_run(ledger)
    return key


def _rebuild_query(slot):
    """The query string to re-issue for a persisted slot, or None if unknown."""
    if slot.get("family") == "broad":
        return QUERY
    return slot.get("query_text")


def _run_sweep_slot(ledger, family, query, start, end, max_records, collected, incomplete):
    """Run one non-broad slot: never raises, records the outcome, retried later.

    A rate-limited or capped sweep does NOT fail the run — it is skipped with a
    log line, written to the ledger as failed/partial, and retried next run. It
    DOES mark the run degraded (visible on the health page), because a planned
    slot that did not complete is a coverage gap, not a green day.

    Returns the slot's status ("abandoned" / "partial" / "complete") so the
    caller's outage breaker can see a dead public API (see pull_gdelt_between).
    """
    arts, status, _saw_rl, err = _collect_window(query, start, end, max_records, family)
    if arts is None:
        print(f"GDELT {family} skipped ({err}): {query[-60:]}")
        _record_slot(ledger, family, query, start, end, "failed", [])
        incomplete.append(f"{family}:abandoned")
        return "abandoned"
    cap_hit = status != "complete"
    print(f"GDELT {family} {query[-48:]}: {len(arts)} article(s)"
          + (" (capped -> bisected, PARTIAL)" if cap_hit else ""))
    collected.extend(arts)
    _record_slot(ledger, family, query, start, end,
                 "complete" if status == "complete" else "partial", arts, cap_hit=cap_hit)
    if status != "complete":
        incomplete.append(f"{family}:partial")
    return status


def _planned_sweeps():
    """The (family, query) sweeps scheduled for THIS run, deterministically."""
    plan = []
    for segment_query in _segment_queries_for_now():
        plan.append(("segment", segment_query))
    if NATIVE_QUERIES_PER_RUN:
        for native_query in run_slice.rotate(NATIVE_TERMS, NATIVE_QUERIES_PER_RUN):
            plan.append(("native", native_query))
    if EUPHEMISM_QUERIES_PER_RUN:
        for eu_query in run_slice.rotate(EUPHEMISM_TERMS, EUPHEMISM_QUERIES_PER_RUN):
            plan.append(("euphemism", eu_query))
    # Standalone THEME sweep: GDELT's GKG topic classifier tags a story's subject
    # matter independent of our keyword vocabulary. NARROW, strictly-additive:
    # the trusted-domain allowlist still gates every article downstream and the
    # extractor validates each candidate. Toggle off with GDELT_THEME_SWEEP=0.
    if os.environ.get("GDELT_THEME_SWEEP", "1") != "0":
        plan.append(("theme",
                     "(theme:WB_2806_DISMISSAL_PROCEDURES OR "
                     "theme:WB_2790_LABOR_REDUNDANCY OR "
                     "theme:WB_2792_COLLECTIVE_REDUNDANCY_PROCEDURES)"))
    # Standalone EUROPEAN-LANGUAGE sweep (see EURO_TERMS): one language per run,
    # stepped by run_slice.rotate like every other ring here.
    if os.environ.get("GDELT_EURO_SWEEP", "1") != "0" and EURO_QUERIES_PER_RUN:
        for eq in run_slice.rotate(EURO_TERMS, EURO_QUERIES_PER_RUN):
            plan.append(("euro", eq))
    return plan


def _retry_pending_slots(ledger, end, max_records, collected, incomplete, done_keys):
    """Re-issue unfinished slots from prior runs (cursor persists between runs).

    Bounded to MAX_RETRY_SLOTS_PER_RUN, oldest-incomplete first, only within the
    retry horizon and never re-running a slot already attempted this run. An
    unfinished slot is NOT abandoned after N tries — it is queued until it
    completes or ages out of the horizon.
    """
    if not MAX_RETRY_SLOTS_PER_RUN:
        return
    horizon_start = end - LEDGER_RETRY_HORIZON
    pending = []
    for key, slot in ledger["slots"].items():
        if key in done_keys:
            continue
        if slot.get("status") not in ("partial", "failed", "queued"):
            continue
        we = _parse_stamp(slot.get("window_end"))
        ws = _parse_stamp(slot.get("window_start"))
        if ws is None or we is None or we < horizon_start or we > end:
            continue
        pending.append((ws, we, key, slot))
    pending.sort(key=lambda t: t[0])  # oldest window first
    for ws, we, key, slot in pending[:MAX_RETRY_SLOTS_PER_RUN]:
        family = slot.get("family", "segment")
        if family not in gdelt_reach.QUERY_LABELS or family == "mirror":
            family = "segment"
        query = _rebuild_query(slot)
        if not query:
            continue
        print(f"GDELT retry pending slot {key} (attempt {int(slot.get('attempts', 0)) + 1})")
        status = _run_sweep_slot(ledger, family, query, ws, we, max_records,
                                 collected, incomplete)
        if status == "abandoned":
            # Same outage breaker as the planned sweeps: a slot abandoned after
            # every attempt means the public API is not answering, and grinding
            # the remaining pending slots through the full retry schedule is
            # what ran the 2026-08-27 sweep into its workflow ceiling. The
            # untouched slots simply stay pending; a later run resumes them.
            print("GDELT public API unreachable; leaving the remaining pending "
                  "slots for a later run")
            break


def pull_gdelt_between(start, end, max_records=250, ledger_path=WORK_LEDGER_PATH, deadline=None):
    """Return raw layoff-news entries (trusted domains) filed in [start, end].

    Every planned unit of work (the broad window plus each rotating sweep) is a
    ledger SLOT: attempted, recorded complete/partial/failed, and retried across
    runs until it completes. A capped window is bisected, an abandoned window is
    recovered from the BigQuery mirror WITHOUT skipping the other sweeps, and a
    run with any incomplete slot reports degraded (see last_run_status), so a
    truncated or lost window is visible instead of silently green.

    `deadline`, when given, is an absolute `time.monotonic()` cutoff (run
    33094996142, 2026-08-27: the broad slot cleared via the BigQuery mirror in
    seconds, then ten rotating sweeps hit the throttled public API one after
    another, each patient with QUERY_ATTEMPTS x QUERY_BACKOFF_SECONDS of its
    own backoff and no clock, and the job was killed by timeout-minutes with a
    sweep still retrying). It is consulted before STARTING each sweep, never
    mid-query, so a sweep already retrying is left to finish rather than cut
    off part-way; a skipped sweep is simply not attempted this run and stays
    (or becomes) a ledger slot that the next run retries — no coverage is lost,
    only deferred.
    """
    global _LAST_RUN_INCOMPLETE
    _LAST_RUN_INCOMPLETE = False
    ledger = _load_work_ledger(ledger_path)
    collected = []
    incomplete = []
    done_keys = set()

    # Quota policy (sandbox: 1 TB scanned/month): the BigQuery mirror is
    # PREFERRED for historical sweeps (GDELT_PREFER_BQ=1 in those workflows —
    # bounded windows, where shared-endpoint 429s actually lose data) and is
    # the FALLBACK for live pulls when the public API abandons a window.
    prefer_bq = os.environ.get("GDELT_PREFER_BQ", "") in ("1", "true", "yes")

    # --- BROAD slot (health-bearing) -------------------------------------
    broad_articles = None
    broad_status = None
    broad_cap = False
    if gdelt_bq.available() and prefer_bq:
        try:
            broad_articles, broad_status = _collect_mirror(start, end)
            broad_cap = broad_status != "complete"
            print(f"GDELT via BigQuery mirror: {len(broad_articles)} article(s), no rate limits")
        except Exception as e:
            print(f"GDELT BigQuery mirror failed ({e}); falling back to public API")
            broad_articles = None

    if broad_articles is None:
        arts, status, saw_rl, err = _collect_window(QUERY, start, end, max_records, "broad")
        if status == "abandoned":
            # The public API abandoned the WHOLE window. Try the mirror to
            # RECOVER it — and if it recovers, CONTINUE with the sweeps rather
            # than returning early (the old early return cost the run every
            # other sweep). A recovered window is RECOVERED, not lost.
            if gdelt_bq.available():
                try:
                    broad_articles, broad_status = _collect_mirror(start, end)
                    broad_cap = broad_status != "complete"
                    print(f"GDELT public API abandoned; BigQuery mirror recovered "
                          f"{len(broad_articles)} article(s) (RECOVERED, not lost)")
                except Exception as e:
                    print(f"BigQuery fallback also failed: {e}")
                    broad_articles = None
            if broad_articles is None:
                # Neither delivered nor recovered. Fail loudly (cron -> degraded,
                # non-zero) and persist nothing: the whole run failed and the
                # window is retried next run.
                if saw_rl:
                    err = f"HTTP 429 (followed by upstream response error: {err or 'unknown error'})"
                raise RuntimeError(
                    f"GDELT window abandoned after {QUERY_ATTEMPTS} attempts: {err or 'unknown error'}")
        else:
            broad_articles, broad_status, broad_cap = arts, status, (status != "complete")

    collected.extend(broad_articles)
    done_keys.add(_record_slot(ledger, "broad", QUERY, start, end,
                               "complete" if broad_status == "complete" else "partial",
                               broad_articles, cap_hit=broad_cap))
    if broad_status != "complete":
        incomplete.append(f"broad:{broad_status}")

    # --- Rotating sweeps: never return early, each is its own retriable slot ---
    #
    # OUTAGE BREAKER (2026-08-28). One sweep slot ABANDONED means the public
    # API failed every one of QUERY_ATTEMPTS tries in a row — with the 429
    # backoff schedule that is up to ~18 minutes spent learning the API is not
    # answering, and this run plans up to ~10 sweeps plus 6 pending retries.
    # On 2026-08-27 (run 33094996142) api.gdeltproject.org went dark, every
    # sweep ground through its full retry schedule, and the historical-sweep
    # workflow cancelled ITSELF at its 45-minute ceiling — which also lost the
    # ledger save and left an orphaned 'running' health note. So: after the
    # first abandoned sweep the remaining planned sweeps are recorded QUEUED
    # (window + query text in the ledger, no attempt spent) and picked up by
    # _retry_pending_slots on a later run. A false trip costs one run of
    # sweeps, all of which are queued, none lost; not tripping costs the whole
    # run, ledger included. The run still reports degraded either way.
    api_down = False
    out_of_time = False
    for family, query in _planned_sweeps():
        # TWO INDEPENDENT BRAKES, in this order, because they answer different
        # questions and a run can hit either. The WALL CLOCK asks "is there time
        # left?" — a throttled-but-answering API can burn the whole
        # timeout-minutes budget one slow request at a time (#231). The OUTAGE
        # BREAKER asks "is the endpoint answering at all?". BOTH queue the
        # remaining slots. The deadline branch used to `break` with a log line
        # promising "ledger retries them next run", and nothing had written
        # them to the ledger: a sweep the clock skipped was simply gone, and
        # on every daily run from 2026-08-30 to 2026-09-01 that was every sweep
        # (queries=2: the broad slot and the mirror, no native, euro or theme
        # query ever issued). Queueing is a ledger write and no request, so it
        # is affordable exactly when time is not.
        if deadline is not None and time.monotonic() >= deadline:
            if not out_of_time:
                print(f"GDELT sweep collection past its wall-time budget before {family}; "
                      "remaining sweeps queued in the ledger for the next run")
                out_of_time = True
            done_keys.add(_record_slot(ledger, family, query, start, end, "queued", []))
            incomplete.append(f"{family}:deadline")
            continue
        if api_down:
            done_keys.add(_record_slot(ledger, family, query, start, end, "queued", []))
            incomplete.append(f"{family}:queued")
            continue
        before = set(ledger["slots"])
        status = _run_sweep_slot(ledger, family, query, start, end, max_records,
                                 collected, incomplete)
        done_keys |= (set(ledger["slots"]) - before)
        done_keys.add(_slot_key(family, query, start, end))
        if status == "abandoned":
            api_down = True
            print(f"GDELT public API unreachable (a sweep abandoned after "
                  f"{QUERY_ATTEMPTS} attempts); queueing the remaining sweeps "
                  f"for the next run instead of grinding into the workflow ceiling")

    # --- Pick up unfinished work from earlier runs ------------------------
    # Same two brakes on the retry walk. Either one alone is a reason to stop:
    # out of time, or the endpoint is dark. The slots stay pending either way.
    if deadline is not None and time.monotonic() >= deadline:
        print("GDELT sweep collection past its wall-time budget; skipping pending-slot retries")
    elif api_down:
        print("GDELT pending-slot retries skipped this run: the public API is "
              "not answering, and the slots stay pending for a later run")
    else:
        _retry_pending_slots(ledger, end, max_records, collected, incomplete, done_keys)

    _LAST_RUN_INCOMPLETE = bool(incomplete)
    if incomplete:
        print(f"GDELT run has {len(incomplete)} incomplete slot(s): "
              f"{', '.join(sorted(set(incomplete)))} -> health degraded")
    _save_work_ledger(ledger, ledger_path)
    return _fetch_trusted(collected)


def _fetch_trusted(articles):
    """Trusted-domain gate + concurrent article fetch, shared by both the
    BigQuery-mirror and public-API paths."""
    reach = gdelt_reach.current()
    candidates, seen = [], set()
    for a in articles:
        url = a.get("url")
        dom = _domain(a)
        # Every candidate is attributed to exactly ONE outcome, so the columns
        # add up to the number GDELT returned. Order matters and matches the
        # gate below it: a same-run repeat is counted as a repeat even when its
        # domain is also untrusted, because that is the question being asked
        # ("was it dropped at the allowlist?") and double-counting would
        # inflate the allowlist's share. Measurement only -- the `continue`
        # below is the pre-existing behaviour, unchanged.
        if not url:
            reach.note(dom, "empty_text")
            continue
        if url in seen:
            reach.note(dom, "duplicate_url")
            continue
        if not _is_trusted(dom):
            reach.note(dom, "not_allowlisted")
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
            reach.note(dom, "fetch_failed")
            return None
        if not text.strip():
            reach.note(dom, "empty_text")
            return None
        reach.note(dom, "kept")
        return {
            "_reach_cc": gdelt_reach.country_of(dom),
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
    for line in reach.report_lines():
        print(line)
    return results
