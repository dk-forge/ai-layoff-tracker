"""Every copy of the reason-tag vocabulary names every tag (#478 item 8).

The canonical list is alt_allowed_reason_tags() in includes/cpt.php. The
extractor keeps its own set (it rejects unknown tags before a batch is sent),
two prompts spell the tags out for the model, and four reader surfaces carry a
label map. When the vocabulary widened on 2.19.211 the two email label maps
were missed and stayed at ten tags for months: a bankruptcy row in a digest
printed its raw slug or nothing. Widening it again (tariffs_trade,
contract_loss, funding_loss) is the moment to pin every copy at once.

Offline and static: reads files as text, imports the extractor, calls nothing.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
sys.path.insert(0, str(ROOT / "railway"))

NEW_TAGS = {"tariffs_trade", "contract_loss", "funding_loss"}


def _canonical():
    text = (PLUGIN / "includes/cpt.php").read_text()
    start = text.index("function alt_allowed_reason_tags(")
    end = text.index("\n}", start)
    return set(re.findall(r"'([a-z_]+)'", text[start:end]))


class ReasonVocabularyMirrors(unittest.TestCase):
    def setUp(self):
        self.canon = _canonical()

    def test_new_tags_are_canonical(self):
        self.assertTrue(NEW_TAGS <= self.canon, sorted(NEW_TAGS - self.canon))
        self.assertGreaterEqual(len(self.canon), 15)

    def test_extractor_set_matches_canonical(self):
        import extractor
        self.assertEqual(self.canon, set(extractor.ALLOWED_REASON_TAGS))

    def test_extractor_prompts_define_every_tag(self):
        src = (ROOT / "railway/extractor.py").read_text()
        for tag in self.canon:
            # A definition line "- tag:" in each of the two prompts.
            self.assertGreaterEqual(
                len(re.findall(r"^- %s:" % tag, src, re.M)), 2,
                "%s is not defined in both the system prompt and the reason-tag prompt" % tag)
        listed = re.search(r'"reason_tags":\["zero or more of: ([a-z_, ]+)"\]', src)
        self.assertIsNotNone(listed, "the reason-tag response list moved; this guard is blind")
        self.assertEqual(self.canon, {t.strip() for t in listed.group(1).split(",")})

    def test_js_labels_cover_every_tag(self):
        js = (PLUGIN / "assets/layoffs.js").read_text()
        for tag in self.canon:
            self.assertRegex(js, r"\b%s: '" % tag, "layoffs.js has no label for %s" % tag)

    def test_dropdown_offers_every_tag(self):
        tpl = (PLUGIN / "templates/page-tracker.php").read_text()
        sel = re.search(r'<select id="alt-f-reasons".*?</select>', tpl, re.S).group(0)
        self.assertEqual(self.canon, set(re.findall(r'<option value="([a-z_]+)"', sel)))

    def test_email_label_maps_cover_every_tag(self):
        for rel in ("includes/digest-extras.php", "includes/subscribe.php"):
            text = (PLUGIN / rel).read_text()
            for tag in self.canon:
                self.assertRegex(text, r"'%s'\s+=> '" % tag, "%s has no label for %s" % (rel, tag))

    def test_methodology_names_new_tags(self):
        page = (PLUGIN / "templates/page-methodology.php").read_text()
        for label in ("Tariffs / trade", "Contract loss", "Funding loss"):
            self.assertIn("<b>%s</b>" % label, page)


if __name__ == "__main__":
    unittest.main()
