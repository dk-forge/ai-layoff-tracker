# AI causation — rows that need the owner's eye

Built 2026-08-19T05:26:09Z by `railway/ab_ai_causation.py` over `docs/recall-reference-sets/ai-causation-2026-08.sample.json`.

## How to use this file

Read the TEXT. The only question is: **does this text explicitly say AI, automation, machine learning or robots CAUSED these cuts, in a phrase quoted from the text itself?** A company's AI strategy, AI investment, AI products, or AI used to pick who goes is NOT a cause. That is the production rule, verbatim.

Write your call into `docs/recall-reference-sets/ai-causation-2026-08.adjudications.json` as `{"<id>": true|false}` — `true` means the text supports `ai_explicit`. Anything you leave out stays UNADJUDICATED and is scored nowhere; it is never quietly defaulted.

**Section 1 is the one that must be filled in** (6 rows): the two independent labellers disagreed, so there is no label at all. **Section 2** (0 rows) is optional and is where the candidate model disagrees with a label the two labellers agreed on. Filling it in removes the one bias left in the score — a two-model agreement standing in for truth exactly where the candidate objects.

---

## Section 1 — the labellers disagree (6 rows, REQUIRED)

### id 70293 — Snap  
`A_positive` · news · economictimes.indiatimes.com · 2026-04-23 · 1000 jobs  
source: https://economictimes.indiatimes.com/news/international/us/snap-layoffs-grow-as-ai-push-leads-to-1000-job-cuts-and-major-cost-savings/articleshow/130478491.cms

> Snap layoffs grow as AI push leads to 1,000 job cuts and major cost savings. The company is cutting workers to save money and improve speed using new technology.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='Evan Spiegel memo: "rapid advancements in artificial intelligence enable our teams to reduce repetitive work, increase velocity, and better support our community, partners, and advertisers." (TechCrunch)'  
**owner's call (70293): [ ] AI    [ ] not AI**

### id 70653 — TikTok  
`A_positive` · news · theguardian.com · 2025-10-13 · 439 jobs  
source: https://www.theguardian.com/technology/2025/oct/13/uk-mps-tiktok-plans-cut-content-moderator-jobs

> It also claims that TikTok is looking to replace the moderators with artificial intelligence-driven systems and with workers in countries such as Kenya and the Philippines.

votes: **deepseek/deepseek-chat**: not AI | **openai/gpt-4.1-mini**: AI  
currently stored: `ai_explicit=True` `contributing_cause` quote='TikTok is looking to replace the moderators with artificial intelligence-driven systems'  
**owner's call (70653): [ ] AI    [ ] not AI**

### id 54973 — Microsoft  
`A_positive` · news · theverge.com · 2020-05-30 · 50 jobs  
source: https://www.theverge.com/2020/5/30/21275524/microsoft-news-msn-layoffs-artificial-intelligence-ai-replacements

> Microsoft is laying off dozens of journalists and editorial workers at its Microsoft News and MSN organizations. The layoffs are part of a bigger push by Microsoft to rely on artificial intelligence to pick news and content that’s presented on MSN.com, inside Microsoft’s Edge browser, and in the company’s various Microsoft News apps.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=True` `primary_cause` quote='Microsoft is laying off more than 50 journalists to replace them with AI for Microsoft News and MSN'  
**owner's call (54973): [ ] AI    [ ] not AI**

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

### id 70681 — TikTok  
`B_hard_negative` · news · livemint.com · 2024-10-11 · 500 jobs  
source: https://www.livemint.com/technology/tech-news/tiktok-announces-global-layoffs-as-it-shifts-focus-to-ai-powered-content-moderation-11728650141534.html

> TikTok plans to lay off hundreds globally, including many in Malaysia, to improve AI-driven content moderation. The company confirmed fewer than 500 layoffs in Malaysia, primarily affecting content moderation teams, who were notified via email last Wednesday.

votes: **deepseek/deepseek-chat**: AI | **openai/gpt-4.1-mini**: not AI  
currently stored: `ai_explicit=False` `selection_or_operations` quote='as part of its broader plan to enhance its content moderation operations through artificial intelligence (AI)'  
**owner's call (70681): [ ] AI    [ ] not AI**

---

## Section 2 — the candidate objects to a model-agreed label (0 rows, optional)

_None._

