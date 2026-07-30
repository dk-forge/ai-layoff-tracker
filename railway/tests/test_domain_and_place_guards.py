"""Offline guards for three matching bugs of the same family: a list of names
compared as SUBSTRINGS instead of as structured hosts or vocabulary tokens.

All three shipped, and all three failed silently in the direction that is
hardest to notice:

  * process_tips._domain_trusted searched the whole URL for "warn"/"edgar"/
    ".gov", so warnerbros.com cleared the allowlist gate that feeds auto-publish.
  * warn_custom._nv_place_split's caller required a space before the county, so
    a pdfplumber-glued multi-site NV line stored its city and county AS PART OF
    the employer name (live on the tracker as
    "Spirit Airlines Las Vegas/RenoClark/Washoe").
  * tracker_diff.outlet_suggestions treated an outlet's first label as a
    substring of any trusted domain, suppressing real allowlist candidates.

No network, no stubs of first-party modules (a faked sources.* entry in
sys.modules persists and shadows the real module for the rest of the suite).
"""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from process_tips import _domain_trusted, _host_of, _is_official_host
from sources.warn_custom import _nv_place_split
from tracker_diff import outlet_suggestions


class HostParsingTests(unittest.TestCase):
    def test_port_and_www_are_stripped(self):
        self.assertEqual(_host_of("https://www.wsj.com:443/a/b"), "wsj.com")

    def test_www_strip_does_not_eat_real_leading_chars(self):
        # str.lstrip('www.') would turn wsj.com into sj.com
        self.assertEqual(_host_of("https://wsj.com/x"), "wsj.com")

    def test_unparseable_url_is_empty_not_trusted(self):
        self.assertEqual(_host_of("not a url"), "")
        self.assertFalse(_domain_trusted("not a url"))


class OfficialHostGateTests(unittest.TestCase):
    """The bug: these were trusted because the substring appeared ANYWHERE."""

    def test_lookalike_company_hosts_are_not_official(self):
        for url in (
            "https://www.warnerbros.com/studio-tour",
            "https://warnermedia.com/press",
            "https://blog.example.com/warning-signs",
            "https://example.com/?q=edgar",
            "https://notreal.com/fake.gov/x",
            "https://mygov.org/a",
            "https://notgov.com/a",
            "https://fake.gov.evil.com/a",
        ):
            with self.subTest(url=url):
                self.assertFalse(_domain_trusted(url), url)

    def test_real_government_hosts_are_official(self):
        for url in (
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
            "https://efts.sec.gov/LATEST/search-index",
            "https://edd.ca.gov/en/jobs_and_training/Layoff_Services_WARN",
            "https://www.dol.gov/agencies/eta",
            "https://www.gov.uk/government/statistics",
        ):
            with self.subTest(url=url):
                self.assertTrue(_domain_trusted(url), url)

    def test_non_gov_state_warn_portals_stay_official(self):
        # Derived from sources.warn.STATE_WARN_URL, so this cannot drift from
        # the map the importer stamps onto notices.
        for url in (
            "https://reactwarn.floridajobs.org/WarnList/Records",
            "https://www.dllr.state.md.us/employment/warn.shtml",
            "https://www.kansasworks.com/search/warn_lookups",
            "https://www.laworks.net/Downloads/WARN.asp",
        ):
            with self.subTest(url=url):
                self.assertTrue(_domain_trusted(url), url)

    def test_warn_label_must_be_a_whole_host_label(self):
        self.assertTrue(_is_official_host("warn.dllr.state.md.us"))
        self.assertFalse(_is_official_host("warnerbros.com"))

    def test_trusted_outlet_allowlist_still_admits_subdomains(self):
        self.assertTrue(_domain_trusted("https://www.reuters.com/business/x"))
        self.assertFalse(_domain_trusted("https://reuters.com.evil.example/x"))


class NvPlaceSplitTests(unittest.TestCase):
    def test_glued_multi_city_multi_county_line_splits(self):
        # The exact live defect: pdfplumber emitted "...Las Vegas/RenoClark/Washoe"
        company, city = _nv_place_split("Spirit Airlines Las Vegas/RenoClark/Washoe")
        self.assertEqual(company, "Spirit Airlines")
        self.assertEqual(city, "Las Vegas/Reno")

    def test_ordinary_single_city_and_county(self):
        self.assertEqual(_nv_place_split("SK Food Group, Inc. Reno Washoe"),
                         ("SK Food Group, Inc.", "Reno"))

    def test_longest_city_wins_over_its_suffix(self):
        self.assertEqual(_nv_place_split("Acme Corp North Las Vegas Clark"),
                         ("Acme Corp", "North Las Vegas"))

    def test_company_ending_in_city_word_is_not_truncated_twice(self):
        # "Boulder City Hospital" is the employer; the city is Boulder City.
        self.assertEqual(_nv_place_split("Boulder City Hospital Boulder City Clark"),
                         ("Boulder City Hospital", "Boulder City"))

    def test_unknown_city_leaves_company_whole_and_city_blank(self):
        # Deliberate: never guess by stripping a trailing place-like word.
        company, city = _nv_place_split("Bob's Widgets Sunrise Manor Clark")
        self.assertEqual(city, "")
        self.assertEqual(company, "Bob's Widgets Sunrise Manor")

    def test_city_only_line_yields_no_company_so_entry_is_dropped(self):
        self.assertEqual(_nv_place_split("Las Vegas Clark"), ("", "Las Vegas"))

    def test_remote_is_a_city_when_the_county_column_follows_it(self):
        # Real NV lines carry city AND county; "Remote"/"Statewide"/"Various"
        # appear in both vocabularies, so the county strip must take only the
        # LAST token and leave the city for the city strip.
        self.assertEqual(_nv_place_split("Conduent Remote Various"),
                         ("Conduent", "Remote"))
        self.assertEqual(_nv_place_split("SMBC Manubank Remote Various"),
                         ("SMBC Manubank", "Remote"))

    def test_lone_place_token_is_read_as_the_county(self):
        # Pins pre-existing behaviour rather than changing it: with no county
        # column there is nothing to distinguish city from county, so the single
        # token is stripped as the county and the city stays blank. Same result
        # as before this refactor.
        self.assertEqual(_nv_place_split("Conduent Remote"), ("Conduent", ""))

    def test_empty_input_is_safe(self):
        self.assertEqual(_nv_place_split(""), ("", ""))
        self.assertEqual(_nv_place_split(None), ("", ""))


class OutletSuggestionTests(unittest.TestCase):
    TRUSTED = ["apnews.com", "ft.com", "washingtonpost.com", "reuters.com"]

    def test_substring_lookalikes_are_no_longer_suppressed(self):
        wins = {"news.example.com": 3, "ft.co.za": 2, "post.co.uk": 2}
        got = dict(outlet_suggestions(wins, self.TRUSTED))
        for outlet in wins:
            self.assertIn(outlet, got, f"{outlet} was wrongly treated as covered")

    def test_allowlisted_host_and_its_subdomain_are_covered(self):
        wins = {"reuters.com": 5, "feeds.reuters.com": 4}
        self.assertEqual(outlet_suggestions(wins, self.TRUSTED), [])

    def test_country_suffix_is_ignored_when_matching(self):
        wins = {"reuters.com · Germany": 3, "sifted.eu · Germany": 3}
        got = dict(outlet_suggestions(wins, self.TRUSTED))
        self.assertNotIn("reuters.com · Germany", got)
        self.assertIn("sifted.eu · Germany", got)

    def test_single_win_is_not_a_candidate(self):
        self.assertEqual(outlet_suggestions({"sifted.eu": 1}, self.TRUSTED), [])

    def test_outlet_name_still_matches_its_allowlisted_domain(self):
        # Google News wins are keyed by RSS outlet NAME, not host. That path
        # must keep working: 'washingtonpost' names washingtonpost.com.
        self.assertEqual(outlet_suggestions({"washingtonpost": 4}, self.TRUSTED), [])

    def test_outlet_name_matches_the_whole_first_label_only(self):
        # 'post' must NOT be read as washingtonpost.com, and 'news' must not be
        # read as apnews.com.
        got = dict(outlet_suggestions({"post": 3, "news": 3, "globes english": 2},
                                      self.TRUSTED))
        for name in ("post", "news", "globes english"):
            self.assertIn(name, got, f"{name} was wrongly treated as covered")


if __name__ == "__main__":
    unittest.main()
