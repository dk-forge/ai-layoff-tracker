"""PHP URL rendering from synthetic mappings; no generated app files are written."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import generate_warn_urls as generator


class WarnUrlRendering(unittest.TestCase):
    def test_sorts_states_and_escapes_url_quotes(self):
        text = generator.render_php({"ZZ": "https://example.invalid/last", "AA": "https://example.invalid/it's"})
        self.assertLess(text.index("'AA' =>"), text.index("'ZZ' =>"))
        self.assertIn("it\\'s", text)
        self.assertIn("strtoupper(trim((string) $state))", text)

    def test_empty_mapping_keeps_the_lookup_fallback(self):
        text = generator.render_php({})
        self.assertIn("return array(\n    );", text)
        self.assertIn("isset($map[$state]) ? $map[$state] : ''", text)

    def test_invalid_url_value_fails_instead_of_writing_a_partial(self):
        with self.assertRaises(AttributeError):
            generator.render_php({"AA": None})

    def test_main_writes_the_rendered_mapping_through_the_mock(self):
        mapping = {"AA": "https://example.invalid/list"}
        handle = mock_open()
        with patch.object(generator, "STATE_WARN_URL", mapping), patch("builtins.open", handle), contextlib.redirect_stdout(io.StringIO()):
            generator.main()
        handle().write.assert_called_once_with(generator.render_php(mapping))
