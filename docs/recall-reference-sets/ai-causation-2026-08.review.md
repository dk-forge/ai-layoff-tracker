# AI causation — rows that need the owner's eye

Built 2026-08-18T23:59:08Z by `railway/ab_ai_causation.py` over `docs/recall-reference-sets/ai-causation-2026-08.sample.json`.

## How to use this file

Read the TEXT. The only question is: **does this text explicitly say AI, automation, machine learning or robots CAUSED these cuts, in a phrase quoted from the text itself?** A company's AI strategy, AI investment, AI products, or AI used to pick who goes is NOT a cause. That is the production rule, verbatim.

Write your call into `docs/recall-reference-sets/ai-causation-2026-08.adjudications.json` as `{"<id>": true|false}` — `true` means the text supports `ai_explicit`. Anything you leave out stays UNADJUDICATED and is scored nowhere; it is never quietly defaulted.

**Section 1 is the one that must be filled in** (25 rows): the two independent labellers disagreed, so there is no label at all. **Section 2** (9 rows) is optional and is where the candidate model disagrees with a label the two labellers agreed on. Filling it in removes the one bias left in the score — a two-model agreement standing in for truth exactly where the candidate objects.

---

## Section 1 — the labellers disagree (25 rows, REQUIRED)

### id 70293 — Snap  
`A_positive` · news · economictimes.indiatimes.com · 2026-04-23 · 1000 jobs  
source: https://economictimes.indiatimes.com/news/international/us/snap-layoffs-grow-as-ai-push-leads-to-1000-job-cuts-and-major-cost-savings/articleshow/130478491.cms

> Snap layoffs grow as AI push leads to 1,000 job cuts and major cost savings. The company is cutting workers to save money and improve speed using new technology.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='Evan Spiegel memo: "rapid advancements in artificial intelligence enable our teams to reduce repetitive work, increase velocity, and better support our community, partners, and advertisers." (TechCrunch)'  
**owner's call (70293): [ ] AI    [ ] not AI**

### id 26455 — Amazon Web Services  
`A_positive` · news · telecom.economictimes.indiatimes.com · 2025-07-18 · 100 jobs  
source: https://telecom.economictimes.indiatimes.com/news/internet/amazons-aws-cloud-computing-unit-cuts-at-least-hundreds-of-jobs/122717029

> Amazon AWS cloud computing unit cuts at least hundreds of jobs, ETTelecom wo sources said, just a month after CEO Andy Jassy warned that adoption of generative AI tools would trigger a workforce reduction.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='adoption of generative AI tools would trigger a workforce reduction'  
**owner's call (26455): [ ] AI    [ ] not AI**

### id 70653 — TikTok  
`A_positive` · news · theguardian.com · 2025-10-13 · 439 jobs  
source: https://www.theguardian.com/technology/2025/oct/13/uk-mps-tiktok-plans-cut-content-moderator-jobs

> It also claims that TikTok is looking to replace the moderators with artificial intelligence-driven systems and with workers in countries such as Kenya and the Philippines.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='TikTok is looking to replace the moderators with artificial intelligence-driven systems'  
**owner's call (70653): [ ] AI    [ ] not AI**

### id 107375 — General Motors  
`A_positive` · news · TechCrunch · 2026-05-11 · 600 jobs  
source: https://techcrunch.com/2026/05/11/gm-just-laid-off-hundreds-of-it-workers-to-hire-those-with-stronger-ai-skills/

> TechCrunch headline: "GM just laid off hundreds of IT workers to hire those with stronger AI skills" — press explicitly attributed the cuts to an AI skills swap; GM's own statement was only "GM is transforming its Information Technology organization to better position the company for the future" (no AI mention by the company; loose/press attribution).

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='General Motors cut about 600 roles in May 2026; TechCrunch lists GM among 2026 employers that explicitly cited AI in the announcement (TechCrunch running list, July 6, 2026)'  
**owner's call (107375): [ ] AI    [ ] not AI**

### id 306 — BlackRock  
`A_positive` · news · fortune.com · 2024-05-19 · 600 jobs  
source: https://fortune.com/2024/05/19/ai-jobs-replacing-workers-learning-to-use-gen-ai-technology-ups-ibm-google/

> financial giant BlackRock said it would eliminate about 600 positions , couching the cuts as an effort to prepare for coming shifts in the asset management industry, of which AI is among several drivers.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='AI to automate tasks these workers performed'  
**owner's call (306): [ ] AI    [ ] not AI**

### id 54973 — Microsoft  
`A_positive` · news · theverge.com · 2020-05-30 · 50 jobs  
source: https://www.theverge.com/2020/5/30/21275524/microsoft-news-msn-layoffs-artificial-intelligence-ai-replacements

> Microsoft is laying off dozens of journalists and editorial workers at its Microsoft News and MSN organizations. The layoffs are part of a bigger push by Microsoft to rely on artificial intelligence to pick news and content that’s presented on MSN.com, inside Microsoft’s Edge browser, and in the company’s various Microsoft News apps.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='Microsoft is laying off more than 50 journalists to replace them with AI for Microsoft News and MSN'  
**owner's call (54973): [ ] AI    [ ] not AI**

### id 107465 — Upwork  
`A_positive` · news · Upwork press release / SEC Form 8-K · 2026-05-07 · 150 jobs  
source: https://www.sec.gov/Archives/edgar/data/0001627475/000162747526000033/upwork1q26-pressrelease.htm

> "Two pizza teams are dead. AI means smaller, differently resourced teams in product and engineering can make a bigger impact than ever." — Company's 8-K press release (verified directly at SEC) announces a restructuring reducing total workforce by approximately 24%; press coverage puts that at ~150 positions (trackers list 145-151; no named outlet confirms exactly 151, so 150 is used). $16M-$23M pre-tax charges, substantially complete Q4 2026. The quote is from CEO Hayden Brown's May 7 memo to employees on Upwork's press page (https://www.upwork.com/press/releases/upwork-ceo-hayden-brown-shared-the-following-message-with-employees-on-may-7-2026, quoted by OfficeChai); the earnings release also quotes Brown: 'The nature of work continues to shift as AI advances, and we continue to build Upwork for where work is headed.' Geography not broke

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='Two pizza teams are dead. AI means smaller, differently resourced teams in product and engineering can make a bigger impact than ever. (Upwork press release / SEC Form 8-K)'  
**owner's call (107465): [ ] AI    [ ] not AI**

### id 49090 — Allstate  
`A_positive` · news · chicagotribune.com · 2017-09-07 · 500 jobs  
source: http://www.chicagotribune.com/business/ct-white-collar-job-automation-0910-biz-20170907-story.html

> Allstate quietly laid off more than 500 employees this year. Most were casualties of the Northbrook-based insurer’s QuickFoto Claim feature, which lets customers send in photos of their damaged vehicles rather than waiting for in-person visits from claims adjusters, the company said.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='Automation is hitting office jobs in Chicago'  
**owner's call (49090): [ ] AI    [ ] not AI**

### id 107459 — Skai  
`A_positive` · news · CTech by Calcalist · 2026-06-03 · 100 jobs  
source: https://www.calcalistech.com/ctechnews/article/jmjuqzfe6

> "made several changes to the way work is conducted in light of new technologies, with an emphasis on artificial intelligence" — Marketing-tech firm Skai (formerly Kenshoo) laying off ~100 employees, 20% of workforce, in Israel and worldwide (headline: 'Skai lays off 20% of staff, citing AI-driven transformation'). Company attributed the cuts to AI's impact on operations after launching AI-based products — explicit company AI attribution per CTech, 2026-06-03. Second round after ~80 cut in 2024.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='made several changes to the way work is conducted in light of new technologies, with an emphasis on artificial intelligence (CTech by Calcalist)'  
**owner's call (107459): [ ] AI    [ ] not AI**

### id 107479 — Mews  
`A_positive` · news · Hotel Dive · 2026-07-07 · 203 jobs  
source: https://www.hoteldive.com/news/mews-cuts-staff-ai-native-future/824687/

> "the hospitality operating system of the future is an AI-native one" — Approx 203 employees, 15% of 1,350 staff. Founder Richard Valtr's post explicitly cited AI, saying AI now handles much of the execution layer of the work at scale and that AI is fundamentally changing the economics of hospitality. Story broken by Skift on 2026-07-07 (paywalled/403 on fetch); employees notified that Tuesday. Also covered by PhocusWire and NL Times. Customer-facing roles largely unaffected.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='the hospitality operating system of the future is an AI-native one (Hotel Dive)'  
**owner's call (107479): [ ] AI    [ ] not AI**

### id 48830 — Suncor Energy  
`A_positive` · news · globalnews.ca · 2018-02-01 · 400 jobs  
source: https://globalnews.ca/news/4000125/suncor-union-outcry-automation-oilsands-jobs/

> Driverless technology is only just starting to cause layoffs. The company has been testing the 400-tonne capacity Komatsu trucks for about four years and has nine now. It announced Tuesday it will gradually build a fleet of more than 150 driverless trucks over the next six years, starting with the North Steepbank mine at its Base Camp north of Fort McMurray, making Suncor the first oilsands mining operation to adopt this technology.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='Union outcry as automation eats up 400 oilsands jobs'  
**owner's call (48830): [ ] AI    [ ] not AI**

### id 70683 — ByteDance TikTok  
`A_positive` · news · straitstimes.com · 2024-10-09 · 500 jobs  
source: https://www.straitstimes.com/asia/se-asia/bytedance-cuts-over-700-jobs-in-malaysia-in-shift-towards-ai-moderation-sources-say

> ByteDance TikTok cuts hundreds of jobs in shift towards AI content moderation, owned by China’s ByteDance, later clarified that fewer than 500 employees in the country were affected.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='shifts focus towards a greater use of artificial intelligence (AI) in content moderation'  
**owner's call (70683): [ ] AI    [ ] not AI**

### id 176954 — Statista  
`A_positive` · news · PPC Land · 2025-10-15 · 80 jobs  
source: https://news.google.com/rss/articles/CBMihgFBVV95cUxOSEV1akx3ZUFVMkpkM2xLTmxfU2hGbjV1TWpaNjVEYnAxZG16R203RHk3UGxxZlNsTGR4MW83bzRWdFBHemdzMnk5S2NkZFd4YU5QN2ZDd2pITVlFT2VKTnc3SUoyV2lXQUgxanBOTEtEdFBQRTJ0ejAtT1pheEctNmFkZjU0Zw?oc=5

> Statista cuts 80 jobs amid AI-driven data automation strategy.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='AI-driven data automation strategy'  
**owner's call (176954): [ ] AI    [ ] not AI**

### id 177188 — KEY TRONIC CORP  
`A_positive` · 8K · SEC EDGAR 8-K · 2025-08-27 · 300 jobs  
source: https://www.sec.gov/Archives/edgar/data/719733/000071973325000074/q42025exhibit991.htm

> In order to better align costs with current customer demand and boost automation, the Company cut approximately 300 jobs during the fourth quarter of fiscal year 2025, for a total headcount reduction during fiscal year 2025 of approximately 800.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='boost automation'  
**owner's call (177188): [ ] AI    [ ] not AI**

### id 107477 — Elementor  
`A_positive` · news · Calcalist / Ctech · 2026-06-29 · 100 jobs  
source: https://www.calcalistech.com/ctechnews/article/sycgn6yxze

> "AI agents are becoming key builders, users, and navigators" — About 30% of workforce, most affected employees in Israel. Company statement explicitly framed the cuts as a reset for an AI era in which, alongside humans, AI agents build and navigate websites. CEO Yoni Luksenberg cited underestimating 'the speed of technological disruption'. Also covered by Globes and The Jerusalem Post.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='AI agents are becoming key builders, users, and navigators (Calcalist / Ctech)'  
**owner's call (107477): [ ] AI    [ ] not AI**

### id 70681 — TikTok  
`B_hard_negative` · news · livemint.com · 2024-10-11 · 500 jobs  
source: https://www.livemint.com/technology/tech-news/tiktok-announces-global-layoffs-as-it-shifts-focus-to-ai-powered-content-moderation-11728650141534.html

> TikTok plans to lay off hundreds globally, including many in Malaysia, to improve AI-driven content moderation. The company confirmed fewer than 500 layoffs in Malaysia, primarily affecting content moderation teams, who were notified via email last Wednesday.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=False` `selection_or_operations` quote='as part of its broader plan to enhance its content moderation operations through artificial intelligence (AI)'  
**owner's call (70681): [ ] AI    [ ] not AI**

### id 48844 — Amazon  
`B_hard_negative` · news · usatoday.com · 2019-05-13 · 24 jobs  
source: https://www.usatoday.com/story/tech/news/2019/05/13/amazon-rolling-out-machines-automate-packing-orders/1187392001/

> The tech giant is deploying machines to warehouses to automate the process of packing customer orders, reports Reuters. Citing "two people who worked on the project," Reuters reports the machines scan goods on a conveyor belt, then place them in custom-built boxes.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=False` `context_only` quote=None  
**owner's call (48844): [ ] AI    [ ] not AI**

### id 60800 — STATE STREET CORP  
`B_hard_negative` · 8K · SEC EDGAR · 2019-01-18 · 1500 jobs  
source: https://www.sec.gov/Archives/edgar/data/93751/000009375119000005/exhibit991-4q18earningspre.htm

> Workforce reduction of 6%, or approximately 1,500 employees, in high cost locations as the Company realizes benefits of automation and standardized global processes

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=False` `context_only` quote='our automation efforts have not moved fast enough'  
**owner's call (60800): [ ] AI    [ ] not AI**

### id 286 — NAB  
`B_hard_negative` · news · abc.net.au · 2025-09-10 · 400 jobs  
source: https://www.abc.net.au/news/2025-09-10/nab-to-cut-400-jobs-as-union-slams-banks-after-anz-job-losses/105757024

> NAB to axe more than 400 jobs , union slams banks after ANZ plan to slash 3 , 500 roles ome new roles will be created in Australia. The union says workers face uncertainty while banks replace them with offshoring and automation.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=False` `unknown` quote=None  
**owner's call (286): [ ] AI    [ ] not AI**

### id 177401 — Google  
`B_hard_negative` · news · T客邦 · 2026-07-23 · 4500 jobs  
source: https://news.google.com/rss/articles/CBMihgFBVV95cUxNX0puaUE4SXRoLXZCVjJ6RUt0eVRiamI0WVE3MlhKT3FUc21xczBuQ25rWXVGTDlXY3hscmdLVEpDVUxiSnUxZVlYNHoyb0F2Z0JYY3RIX2cyWEgxcmpFTkg1OVpneDhwbDQyZy1DVzZTNnZ1QVRWT2lmOV9hMkRXWHRCSkhFZw?oc=5

> Google員工怒了！4500人聯名上書CEO拒絕「Email裁員」：AI 不該是變相砍人藉口 - T客邦. Google員工怒了！4500人聯名上書CEO拒絕「Email裁員」：AI 不該是變相砍人藉口 T客邦

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=False` `context_only` quote='AI 不該是變相砍人藉口'  
**owner's call (177401): [ ] AI    [ ] not AI**

### id 107519 — Shopify  
`B_hard_negative` · news · The Logic · 2026-05-04 · 30 jobs  
source: https://thelogic.co/news/exclusive/shopify-layoffs-revenue-operations-restructure/

> "The cuts come as the Canadian e-commerce company continues reducing headcount while pushing employees to adopt AI tools more aggressively." — At least 30 laid off in a reorganization of operations, customer support and revenue teams; cuts took place in April 2026, reported ~May 4 by The Logic (exclusive, paywalled). Shopify's official statement (comms director Ben McConaghy) did NOT name AI — changes will 'sharpen focus on our highest priorities'. Press coverage frames it around AI: Tech Newsday headline 'Shopify cuts operations staff amid AI-driven restructuring' (May 7, credits The Logic); Shopifreaks (May 4): 'with AI cited as partial cause'. CEO Lutke's 'reflexive AI usage is now a baseline expectation' memo referenced by press predates these layoffs by over a year and is not an attribution of this round to AI.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=False` `ai_linked` quote='The cuts come as the Canadian e-commerce company continues reducing headcount while pushing employees to adopt AI tools more aggressively. (The Logic)'  
**owner's call (107519): [ ] AI    [ ] not AI**

### id 69997 — Omron  
`B_hard_negative` · news · asia.nikkei.com · 2024-02-26 · 2000 jobs  
source: https://asia.nikkei.com/Business/Electronics/Japan-s-Omron-to-cut-2-000-jobs-globally-on-slow-China-automation-ops

> Japan Omron to cut 2 , 000 jobs globally on slow China automation ops - Nikkei Asia

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=False` `context_only` quote=None  
**owner's call (69997): [ ] AI    [ ] not AI**

### id 107469 — InvestCloud  
`B_hard_negative` · news · Citywire RIA · 2026-03-09 · 150 jobs  
source: https://citywire.com/ria/news/investcloud-lays-off-150-sources/a2485606

> "accelerating AI productivity and time-to-market gains" — Citywire (Mar 10, 2026) confirms ~150 cuts (roughly 5% of staff, second such round in six months) announced internally Monday Mar 9, concentrated in the geographically dispersed Digital Wealth division (financial planning, advisor and client experience software); APL managed accounts and Private Markets Network spared. Citywire carries no company AI statement; the AI attribution and quote come from CEO Jeff Yabuki's internal memo as reviewed by WealthTech Today (https://wealthtechtoday.com/2026/03/09/investcloud-layoffs-2026/), which reports Yabuki cited 'accelerating AI productivity and time-to-market gains' among three drivers — treat the exact wording as memo language reported by a trade outlet. Task hint date 2026-03-10 corresponds to the Citywire article date; announcement was

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=False` `ai_linked` quote='accelerating AI productivity and time-to-market gains (Citywire RIA)'  
**owner's call (107469): [ ] AI    [ ] not AI**

### id 107481 — GoKwik  
`B_hard_negative` · news · Inc42 · 2026-07-11 · 120 jobs  
source: https://inc42.com/buzz/exclusive-gokwik-lays-off-around-120-employees-amid-ai-push/

> "The layoffs were part of the startup's AI push as it seeks to automate more of its operations" — Around 100-120 employees over the weeks preceding the 2026-07-11 Inc42 exclusive; customer onboarding, implementation and tech teams hardest hit. AI attribution comes from unnamed sources via the article, not the company — GoKwik did not respond to Inc42's questions, so ai_company_explicit is false.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=False` `ai_linked` quote="The layoffs were part of the startup's AI push as it seeks to automate more of its operations (Inc42)"  
**owner's call (107481): [ ] AI    [ ] not AI**

### id 51765 — Meta  
`B_hard_negative` · news · apnews.com · 2021-03-10 · 26 jobs  
source: https://apnews.com/article/pandemics-boston-economy-coronavirus-pandemic-683be0593b21ac86dff43da28b6da10c

> 26 Meta employees sue, alleging AI-driven layoff picks hit workers on medical and parental leave

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=False` `unknown` quote=None  
**owner's call (51765): [ ] AI    [ ] not AI**

---

## Section 2 — the candidate objects to a model-agreed label (9 rows, optional)

### id 70469 — Standard Chartered  
`A_positive` · news · bbc.co.uk · 2026-05-22 · 7800 jobs  
source: https://www.bbc.co.uk/news/articles/c98rqld1j3yo

> He said the bank had shared its expectation that back-office roles would be cut by about 15% over the next four years - about 7,800 roles. For years the bank has helped colleagues "whose roles may be displaced by automation to build the skills needed for new opportunities within our organisation"

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: AI | **google/gemini-2.5-flash-lite**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='Discussing how automation was likely to lead to thousands of job cuts at the bank'  
**owner's call (70469): [ ] AI    [ ] not AI**

### id 26465 — Tata Consultancy Services (TCS)  
`A_positive` · news · economictimes.indiatimes.com · 2025-09-30 · 19755 jobs  
source: https://economictimes.indiatimes.com/news/international/global-trends/us-news-over-100000-job-cuts-rattle-tech-industry-in-2025-amazon-meta-google-intel-lay-off-thousands-of-employees-check-full-list-of-companies/articleshow/125029264.cms

> TCS, India's largest IT exporter and private-sector employer, said it is reorganising teams to focus more on automation and AI-led growth. The company announced its steepest job-cuts ever due to the AI boom and the strained India-US ties.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: AI | **google/gemini-2.5-flash-lite**: not AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='AI-driven shifts'  
**owner's call (26465): [ ] AI    [ ] not AI**

### id 293 — Commonwealth Bank  
`A_positive` · news · abc.net.au · 2025-07-21 · 45 jobs  
source: https://www.abc.net.au/news/2025-08-21/cba-backtracks-on-ai-job-cuts-as-chatbot-lifts-call-volumes/105679492

> Commonwealth Bank announced 45 job cuts last month, as it introduced an AI 'voice-bot', but has now reversed its decision.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: not AI | **google/gemini-2.5-flash-lite**: AI  
currently stored: `ai_explicit=True` `primary_cause` quote='describing its decision to axe 45 roles due to artificial intelligence'  
**owner's call (293): [ ] AI    [ ] not AI**

### id 176687 — ING  
`A_positive` · news · OECD AI Policy Observatory · 2025-10-28 · 950 jobs  
source: https://news.google.com/rss/articles/CBMiV0FVX3lxTE95SVBQUHJ4QTRGTUszX0V5SUU0VWhsTGdHeDBHV0Y2VmExZ3ZMWkFnZ0Q1REZvbE9tUHJ4dlotR2pRQm1pUzZiWlE5SkdtbFpQY3o2RTZ6WQ?oc=5

> ING Forecasts Up to 950 Job Cuts in the Netherlands Due to AI and Digitalization - OECD AI Policy Observatory.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: AI | **google/gemini-2.5-flash-lite**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='Due to AI and Digitalization'  
**owner's call (176687): [ ] AI    [ ] not AI**

### id 54968 — Bounce  
`B_hard_negative` · news · economictimes.indiatimes.com · 2020-03-20 · 20 jobs  
source: https://economictimes.indiatimes.com/small-biz/startups/newsbuzz/as-growth-dips-startups-shed-jobs-and-conserve-cash-to-stay-afloat/articleshow/74722253.cms

> However, Vivekananda HR, CEO of Bounce, denied this, “We let go of about four in engineering and product, a few in the customer care team – about 20-30 – because we have a lot of automation.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: not AI | **google/gemini-2.5-flash-lite**: AI  
currently stored: `ai_explicit=False` `unknown` quote=None  
**owner's call (54968): [ ] AI    [ ] not AI**

### id 278 — WiseTech Global  
`B_hard_negative` · news · economictimes.indiatimes.com · 2026-02-25 · 2000 jobs  
source: https://economictimes.indiatimes.com/tech/technology/australias-wisetech-global-plans-2000-job-cuts-amid-ai-overhaul/articleshow/128767352.cms

> Australia WiseTech Global plans 2,000 job cuts amid AI overhaul tware firm WiseTech Global will axe about 2,000 jobs, nearly a third of its global workforce, in a two-year restructuring that could rank among the country's largest artificial intelligence-linked job reductions.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: not AI | **google/gemini-2.5-flash-lite**: AI  
currently stored: `ai_explicit=False` `unknown` quote=None  
**owner's call (278): [ ] AI    [ ] not AI**

### id 49084 — Infosys  
`B_hard_negative` · news · hindustantimes.com · 2017-07-14 · 11000 jobs  
source: http://www.hindustantimes.com/business-news/hiring-10-000-in-us-in-2-years-we-do-that-in-india-in-2-quarters-infosys/story-UnUWpHre4PRJ1aFOY0DsXL.html

> Interestingly, Infosys -- at its 36th annual general meeting last month -- had said more than 11,000 jobs have been released due to automation. This comes at a time when there are concerns of large- scale layoffs across companies like Tech Mahindra, Wipro and Infosys.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: AI | **google/gemini-2.5-flash-lite**: not AI  
currently stored: `ai_explicit=False` `unknown` quote=None  
**owner's call (49084): [ ] AI    [ ] not AI**

### id 107497 — MercadoLibre  
`B_hard_negative` · news · Investing.com (relaying Folha de S.Paulo) · 2026-01-12 · 119 jobs  
source: https://www.investing.com/news/stock-market-news/mercadolibre-lays-off-119-employees-amid-ai-expansion-93CH-4443283

> "MercadoLibre (NASDAQ:MELI) has laid off 119 employees as part of its artificial intelligence expansion efforts" — COUNT CORRECTION: 119, not ~116. Cuts across Latin America (38 in Brazil), concentrated in UX/content-writing teams; most dismissals Jan 8, reported Jan 12, 2026. Reuters also carried it as 'MercadoLibre lays off 119 people due to its AI expansion, Folha reports'. AI attribution is from Folha/press only; the company reportedly said the decision was not driven by direct substitution of employees by automated systems - so company-explicit=false.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: not AI | **google/gemini-2.5-flash-lite**: AI  
currently stored: `ai_explicit=False` `ai_linked` quote='MercadoLibre (NASDAQ:MELI) has laid off 119 employees as part of its artificial intelligence expansion efforts (Investing.com (relaying Folha de S.Paulo))'  
**owner's call (107497): [ ] AI    [ ] not AI**

### id 107491 — Snowflake  
`B_hard_negative` · news · Benzinga · 2026-03-19 · 70 jobs  
source: https://www.benzinga.com/markets/tech/26/03/51408543/snowflake-cuts-entire-team-joins-amazon-canva-in-ai-push

> "one of the most aggressive pivots toward AI-generated content in the enterprise software sector" — ~70 roles (~1% of workforce), essentially the entire technical writing/documentation team; work absorbed by AI 'Project SnowWork' after a $200M OpenAI partnership. Surfaced week of Mar 17-19 via affected employees; Benzinga piece published Mar 23. Company spokesperson statement ('targeted adjustments to align our teams with Snowflake's long-term strategy') does not name AI, so company-explicit=false. Location not stated by Benzinga; team reportedly US-based.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: AI | **google/gemini-2.5-flash-lite**: not AI  
currently stored: `ai_explicit=False` `ai_linked` quote='one of the most aggressive pivots toward AI-generated content in the enterprise software sector (Benzinga)'  
**owner's call (107491): [ ] AI    [ ] not AI**

