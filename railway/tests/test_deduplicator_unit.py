"""Legacy diagnostic lookup fails open; ingestion does not use it to skip sources."""
import unittest
from unittest.mock import Mock, patch
from railway import deduplicator as lookup


class DiagnosticLookup(unittest.TestCase):
    def call(self, result=None, error=None, value="fixture-hash"):
        with patch.dict(lookup.os.environ, {"WP_SITE_URL": "https://example.invalid/blog/", "WP_API_KEY": "fixture-only"}, clear=True), patch.object(lookup.blog_reads, "get", return_value=result, side_effect=error) as get, patch("builtins.print"):
            found = lookup.is_duplicate(value)
            return found, get

    def test_checks_payload_and_preserves_key_and_browserish_agent(self):
        found, get = self.call(Mock(status_code=200, json=lambda: {"exists": True}))
        self.assertTrue(found)
        args, kwargs = get.call_args
        self.assertEqual(args, ("https://example.invalid/blog/wp-json/layoffs/v1/check-duplicate",))
        self.assertEqual(kwargs["params"], {"hash": "fixture-hash"})
        self.assertEqual(kwargs["headers"]["X-Layoff-API-Key"], "fixture-only")
        self.assertEqual(kwargs["headers"]["User-Agent"], "AiLayoffTracker/1.0 (+https://asktherecruiter.com)")
        self.assertEqual(kwargs["timeout"], 15)

    def test_missing_hash_or_configuration_never_fetches(self):
        found, get = self.call(value="")
        self.assertFalse(found); get.assert_not_called()
        with patch.dict(lookup.os.environ, {}, clear=True), patch.object(lookup.blog_reads, "get") as get, patch("builtins.print"):
            self.assertFalse(lookup.is_duplicate("fixture")); get.assert_not_called()

    def test_missing_exists_false_http_error_and_network_fail_open(self):
        for response in [Mock(status_code=200, json=lambda: {}), Mock(status_code=200, json=lambda: {"exists": False}), Mock(status_code=503, text="unavailable")]:
            self.assertFalse(self.call(response)[0])
        self.assertFalse(self.call(error=OSError("fixture timeout"))[0])
        self.assertFalse(self.call(Mock(status_code=200, json=Mock(side_effect=ValueError("bad JSON"))))[0])
