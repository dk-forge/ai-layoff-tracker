"""Workflow reads use the same cap and remove stale output on refusal."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import blog_read_cli as cli
from blog_read_cache import ReadLimited


class Command(unittest.TestCase):
    def test_body_written_without_printing_a_key(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp, 'response.json')
            response = io.BytesIO(b'{"ok":true}')
            response.status = 200
            with patch.object(cli, 'urlopen', return_value=response) as send, \
                 patch.dict('os.environ', {'SYNTHETIC_API_KEY': 'synthetic-private-key'}):
                self.assertEqual(0, cli.main(['https://asktherecruiter.com/blog/wp-json/layoffs/v1/query',
                                             '--output', str(out), '--key-env', 'SYNTHETIC_API_KEY']))
            self.assertEqual(b'{"ok":true}', out.read_bytes())
            self.assertEqual('synthetic-private-key', send.call_args.args[0].get_header('X-layoff-api-key'))

    def test_rate_refusal_never_leaves_an_old_success_file(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp, 'response.json')
            out.write_bytes(b'old result')
            with patch.object(cli, 'urlopen', side_effect=ReadLimited()):
                self.assertEqual(75, cli.main(['https://asktherecruiter.com/blog/', '--output', str(out)]))
            self.assertFalse(out.exists())
