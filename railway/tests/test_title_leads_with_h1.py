"""Every tracker page's <title> leads with that page's own H1 (2026-10-13).

A live sweep of the sitemaps found pages whose tab and search snippet said one
thing and whose heading said another: every dated report (archive, year,
quarter, month) printed the theme H1 "Monthly Job Cuts Report" under a title
naming its own period; the US WARN registry said "by State" in the title and
"by Jurisdiction" in the H1; the edition archive, the A-Z company browse pages
and the state WARN pages each worded the two differently. Static checks, the
same shape as test_facet_pages.py, because the live check needs the site.
"""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin/ai-layoff-tracker"


def _read(rel):
    return (PLUGIN / rel).read_text()


def _h1(template):
    m = re.search(r"<h1>(.*?)</h1>", template, re.S)
    assert m, "template has no literal <h1>"
    return m.group(1)


class TitleLeadsWithH1(unittest.TestCase):
    def test_state_warn_title_starts_with_the_state_h1_wording(self):
        tpl = _read("templates/page-facet.php")
        mod = _read("includes/facet-pages.php")
        self.assertIn("' layoffs and WARN notices'", tpl)
        self.assertIn("' layoffs and WARN notices ' . (int) $data['warn']['year']", mod)
        self.assertNotIn("' WARN notices ' . (int) $data['warn']['year']\n             . ': layoffs", mod)

    def test_company_browse_h1_matches_the_title(self):
        tpl = _read("templates/page-company-index.php")
        mod = _read("includes/company-index.php")
        self.assertIn("<h1>Employers starting with <?php", tpl)
        self.assertIn("'Employers starting with ' . strtoupper($cur) . ': layoff records'", mod)

    def test_edition_archive_title_leads_with_its_h1(self):
        h1 = "Every edition we have emailed"
        self.assertIn("<h1>" + h1 + "</h1>", _read("templates/page-editions.php"))
        m = re.search(r"alt_edition_is_index_request\(\)\) \{\s*return '([^']+)';",
                      _read("includes/digest-archive.php"))
        self.assertTrue(m)
        self.assertTrue(m.group(1).lower().startswith(h1.lower()), (m.group(1), h1))

    def test_registry_title_leads_with_its_h1(self):
        h1 = _h1(_read("templates/page-us-registry.php"))
        mod = _read("includes/us-registry.php")
        m = re.search(r"\? '(US WARN Registry[^']+)'", mod)
        self.assertTrue(m, "registry has no title filter")
        self.assertTrue(m.group(1).startswith(h1 + ":"), (m.group(1), h1))
        for hook in ("wpseo_title", "rank_math/frontend/title", "document_title_parts"):
            self.assertIn(hook, mod)

    def test_dated_report_h1_is_the_head_of_its_title(self):
        mod = _read("includes/report-seo.php")
        self.assertIn("add_filter('the_title', 'alt_report_filter_post_title'", mod)
        body = mod[mod.index("function alt_report_filter_post_title"):]
        # only the queried page, never menus, other posts or wp-admin
        self.assertIn("get_queried_object_id()", body)
        self.assertIn("is_admin()", body)
        self.assertIn("alt_report_is_report_page()", body)
        head = mod[mod.index("function alt_report_heading_text"):]
        self.assertIn("alt_report_seo_title('')", head)
        self.assertIn("strpos($title, ': ')", head)


if __name__ == "__main__":
    unittest.main()
