"""A keyed GET to our own host must never be answered from the Cloudflare edge.

2026-09-28: the owner's Cloudflare Cache Rule (2026-07-15, docs/ARCHITECTURE.md)
edge-caches EVERY GET under /blog/wp-json/layoffs/v1/* and its Edge TTL overrides
the origin's no-store. /archive-candidates lives under that path, so the
archive backfill's second fetch in a run got the FIRST response back, byte for
byte: same 420 URLs it had just recorded, same coverage dict (archived 22,940
before AND after ten archives landed). The server fix of 2026-09-27 (#419) was
real but could not show, and archive_recheck_cadence stayed red.

A request carrying the API key is a job reading live state, never a public read,
so get_json gives it a query value no cache has seen. Public reads (no key) are
left alone: they are what the edge cache is for.

No network. Offline, no keys.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import host_call


class _Ok:
    status_code = 200
    headers = {"Content-Type": "application/json"}
    text = "{}"

    def raise_for_status(self):
        return None

    def json(self):
        return {}


class KeyedGetBypassesEdgeCache(unittest.TestCase):
    def _params_sent(self, headers, params=None, calls=1):
        seen = []

        def fake(url, params=None, headers=None, timeout=60):
            seen.append(dict(params or {}))
            return _Ok()

        with mock.patch.object(host_call.http_retry, "get_with_retry", side_effect=fake):
            for _ in range(calls):
                host_call.get_json("https://example.com/blog/wp-json/layoffs/v1/archive-candidates",
                                   params=params, headers=headers)
        return seen

    def test_two_keyed_fetches_never_share_a_cache_key(self):
        seen = self._params_sent({"X-Layoff-API-Key": "k"}, params={"limit": 2000}, calls=2)
        self.assertEqual(seen[0]["limit"], 2000)
        self.assertIn("_fresh", seen[0])
        self.assertNotEqual(seen[0], seen[1])

    def test_callers_params_are_not_mutated(self):
        params = {"limit": 5}
        self._params_sent({"X-Layoff-API-Key": "k"}, params=params)
        self.assertEqual(params, {"limit": 5})

    def test_public_read_without_key_is_left_cacheable(self):
        seen = self._params_sent({"User-Agent": "x"}, params={"limit": 5})
        self.assertEqual(seen[0], {"limit": 5})


if __name__ == "__main__":
    unittest.main()
