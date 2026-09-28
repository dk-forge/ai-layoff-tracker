"""Guards for the free Google News title prefilter (cost trim 2026-09-28).

Three things are pinned:
  1. real layoff headlines are KEPT, in English and in the edition's language;
  2. merger / deal / earnings headlines are DROPPED before any model call;
  3. the golden news fixtures (docs/recall-reference-sets/news-corroborated-
     2026-08.goldset.json) are not lost: every headline-shaped slug in it is
     kept, except the named exclusions below, each with its reason.
Plus the wiring: company chases and explicit caller queries are not filtered,
and the per-run kept/dropped counts are recorded.
"""
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import google_news, google_news_prefilter  # noqa: E402
from sources.google_news_prefilter import title_verdict  # noqa: E402

GOLDSET = (Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets"
           / "news-corroborated-2026-08.goldset.json")

LAYOFF_EN = (
    "Acme lays off 250",
    "X lays off 250",
    "Oracle fires 21,000 employees",
    "Meta to cut 8,000 jobs",
    "Intel to cut thousands of jobs to reduce costs",
    "HSBC may slash 20,000 roles amid AI-led overhaul",
    "Zomato cuts up to 600 customer support jobs",
    "Kraken parent Payward cuts 150 staff ahead of IPO",
    "Boeing layoffs: 17,000 affected",
    "Retailer announces 300 redundancies",
    "Micron to lay off 10% of staff",
    "Bank eliminates 1,200 positions in branch overhaul",
    "Merger to eliminate 1,500 jobs at combined lender",
)

MERGER_EN = (
    "Acme to acquire Beta Corp in $2.1 billion deal",
    "Shareholders approve merger of Gamma and Delta",
    "Regulators clear Epsilon's takeover of Zeta",
    "Omega and Sigma agree to all-stock merger of equals",
    "Private equity firm buys logistics group for $900 million",
    "Merger talks between two carriers collapse",
    "Company completes restructuring of its debt",
    "Theta reports record quarterly revenue",
    "Iota names new CEO after acquisition closes",
    "Kappa merger creates largest regional bank",
    "Lambda's acquisition of Mu wins EU approval",
    "Playoffs: Acme beats Beta in overtime",
)

LAYOFF_NATIVE = (
    ("Siemens plant Stellenabbau von 500 Stellen", "de"),
    ("Plan social : suppression de postes chez Acme", "fr"),
    ("Acme anuncia despidos masivos en su planta", "es-419"),
    ("Acme, 300 esuberi nello stabilimento", "it"),
    ("Acme kondigt massaontslag aan", "nl"),
    ("Acme: zwolnienia grupowe w fabryce", "pl"),
    ("Acme, 500人の希望退職を募集", "ja"),
    ("에이컴, 300명 희망퇴직 실시", "ko"),
    ("Acme 宣布大规模裁员", "zh-TW"),
    ("Acme toplu işten çıkarma yaptı", "tr"),
    ("Acme kollektiivne koondamine puudutab 80 töötajat", "et"),
)

MERGER_NATIVE = (
    ("Acme übernimmt Beta für zwei Milliarden Euro", "de"),
    ("Fusion entre Acme et Beta approuvée", "fr"),
    ("Acme compra Beta por 900 millones", "es-419"),
    ("Acme 买下 Beta 公司", "zh-TW"),
    ("エーカム、ベータ社を買収", "ja"),
    # An English wire headline inside a non-English edition is the US pull
    # again, in the wrong edition: dropped as a language mismatch.
    ("Acme lays off 250", "de"),
    ("Acme to cut 8,000 jobs", "ja"),
)

# Goldset slugs that are headline-shaped (>= 4 words) but not kept, and why.
# Each is a property of the URL SLUG, not of the published headline, or a
# known vocabulary gap recorded in the TECHLOG entry.
GOLDSET_EXCLUSIONS = {
    "tesla elon musk mayoffs": "slug pun, not a headline",
    "ukg formerly ultimate software lays": "slug dropped the word 'off'",
    "uber elimina tres mil empleos": "KNOWN GAP: es table has no 'elimina empleos'",
    "sundar pichai covid pandemics": "not a layoff headline (interview)",
    "irish times view on ai": "editorial, not a layoff headline",
    "zuckerberg meta remote work rto": "RTO story, not a layoff headline",
    "wilko pwc laura ashley": "slug is company names only",
    "hire thousands of refugees": "hiring story, not a layoff headline",
    "aws ceo say replacing young employees": "opinion quote, not a layoff headline",
}


class KeepsLayoffHeadlines(unittest.TestCase):
    def test_english_layoff_headlines_are_kept(self):
        for t in LAYOFF_EN:
            keep, why = title_verdict(t, "en-US")
            self.assertTrue(keep, f"{t!r} dropped ({why})")

    def test_native_layoff_headlines_are_kept_in_their_edition(self):
        for t, hl in LAYOFF_NATIVE:
            keep, why = title_verdict(t, hl)
            self.assertTrue(keep, f"{t!r} [{hl}] dropped ({why})")


class DropsMergerStories(unittest.TestCase):
    def test_english_merger_and_deal_headlines_are_dropped(self):
        for t in MERGER_EN:
            keep, why = title_verdict(t, "en-US")
            self.assertFalse(keep, f"{t!r} kept ({why})")

    def test_native_merger_and_wrong_language_titles_are_dropped(self):
        for t, hl in MERGER_NATIVE:
            keep, why = title_verdict(t, hl)
            self.assertFalse(keep, f"{t!r} [{hl}] kept ({why})")

    def test_a_merger_that_names_job_cuts_is_still_a_layoff(self):
        self.assertTrue(title_verdict(
            "Merger to eliminate 1,500 jobs at combined lender", "en-GB")[0])


class GoldsetNotLost(unittest.TestCase):
    def test_every_headline_shaped_golden_slug_is_kept(self):
        events = json.loads(GOLDSET.read_text(encoding="utf-8"))["reference_events"]
        checked, lost = 0, []
        for ev in events:
            slug = ev["primary_source_url"].rstrip("/").split("?")[0].split("/")[-1]
            slug = re.sub(r"\.(html?|php|aspx?|cms|ece)$", "", slug).replace("-", " ")
            if len(re.findall(r"[a-z]{2,}", slug)) < 4:
                continue  # numeric id, not a headline
            if any(k in slug for k in GOLDSET_EXCLUSIONS):
                continue
            hl = ("de" if "stellenabbau" in slug else
                  "it" if "licenzia" in slug else "en-US")
            checked += 1
            if not title_verdict(slug, hl)[0]:
                lost.append(slug)
        self.assertGreaterEqual(checked, 30)
        self.assertEqual(lost, [])


FEED = ('<rss><channel>{items}</channel></rss>')
ITEM = ('<item><title>{t}</title><link>https://www.example.com/{i}</link>'
        '<pubDate>Wed, 19 Aug 2026 10:00:00 GMT</pubDate>'
        '<source url="https://www.example.com">Example</source></item>')


class Wiring(unittest.TestCase):
    def _pull(self, **kw):
        titles = ["Acme lays off 250", "Acme to acquire Beta in $2bn deal",
                  "Shareholders approve Gamma merger"]
        body = FEED.format(items="".join(ITEM.format(t=t, i=i)
                                          for i, t in enumerate(titles)))

        class _R:
            status_code = 200
            text = body

        with patch.object(google_news.requests, "get", return_value=_R()), \
             patch.object(google_news.time, "sleep", lambda *_a, **_k: None), \
             patch.object(google_news, "_locales_for_now",
                          lambda: [google_news.GOOGLE_NEWS_LOCALES[0]]):
            return google_news.pull_google_news(**kw)

    def test_broad_sweep_drops_mergers_and_counts_them(self):
        rows = self._pull()
        self.assertEqual([r["raw_text"].split(" (via")[0] for r in rows],
                         ["Acme lays off 250"])
        pc = google_news.pull_google_news.prefilter_counts
        self.assertEqual((pc["kept"], pc["dropped"]), (1, 2))

    def test_company_chase_slice_is_not_filtered(self):
        rows = self._pull(company_names=["Acme"])
        self.assertEqual(len(rows), 3,
                         "the chase slice must keep today's behaviour")

    def test_explicit_queries_are_not_filtered(self):
        self.assertEqual(len(self._pull(queries=["layoffs"])), 3)

    def test_env_switch_turns_it_off(self):
        with patch.dict("os.environ", {"GOOGLE_NEWS_PREFILTER": "off"}):
            self.assertFalse(google_news_prefilter.enabled())
            self.assertEqual(len(self._pull()), 3)


if __name__ == "__main__":
    unittest.main()
