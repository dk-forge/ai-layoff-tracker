"""Metadata extraction from local HTML strings only."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from static_parity_html import FIELDS, extract

URL = "https://example.invalid/blog/page/"
CTA = '<a href="https://asktherecruiter.com/resume-score?utm_source=fixture&amp;utm_medium=referral&amp;utm_campaign=page">Check my resume, free</a>'


class ParityMetadata(unittest.TestCase):
    def test_extracts_normalised_headings_relative_links_and_json(self):
        page = extract('<title> A   title </title><h1>Main <b>heading</b></h1><meta name="description" content="Summary"><link rel="canonical" href="/canonical/"><link rel="alternate" hreflang="EN" href="/en/"><script type="application/ld+json">{"z":2,"a":1}</script>', URL)
        self.assertEqual(page.values["title"], ["A title"])
        self.assertEqual(page.values["h1"], ["Main heading"])
        self.assertEqual(page.values["description"], ["Summary"])
        self.assertEqual(page.values["canonical"], ["https://example.invalid/canonical/"])
        self.assertEqual(page.values["hreflang"], [("en", "https://example.invalid/en/")])
        self.assertEqual(page.values["jsonld"], [json.dumps({"a": 1, "z": 2}, sort_keys=True)])
        self.assertFalse(page.invalid_jsonld)

    def test_empty_document_has_no_metadata_or_cta(self):
        page = extract("", URL)
        self.assertEqual(page.values, {field: [] for field in FIELDS})
        self.assertFalse(page.cta)

    def test_malformed_json_is_flagged_instead_of_becoming_a_schema(self):
        page = extract('<script type="application/ld+json">not JSON</script>', URL)
        self.assertTrue(page.invalid_jsonld)
        self.assertEqual(page.values["jsonld"], [])

    def test_only_visible_tracked_match_links_count(self):
        self.assertTrue(extract(CTA, URL).cta)
        for markup in ['<div hidden>' + CTA + '</div>', '<div style="display:none">' + CTA + '</div>', CTA.replace('utm_campaign=page', 'untracked=page'), CTA.replace('asktherecruiter.com', 'example.invalid')]:
            with self.subTest(markup=markup):
                self.assertFalse(extract(markup, URL).cta)

    def test_wrong_document_type_is_rejected(self):
        with self.assertRaises(TypeError):
            extract(None, URL)
