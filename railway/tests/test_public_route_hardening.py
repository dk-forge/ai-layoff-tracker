"""Four cheap hardenings from the 2026-09-05 security review, pinned.

1. The micro-cache key is shaped by a WHITELIST of param names. It used to be
   every query param except `_` and `cb`, so `?x=<random>` was a new key on
   every request: a cold /aggregate compute (8-19 s) and a new 30-minute row in
   wp_options each time, from one anonymous loop. The whitelist must name every
   param a cached route actually reads, or a real filter would be dropped from
   the key and a wrong cached answer served: this file scans the cached routes
   and alt_db_where for get_param() literals and fails on one the list omits.
2. A free-text term (q, company, keyword) is capped in length before it becomes
   a leading-wildcard LIKE plus a REGEXP over the whole table.
3. `?q[]=x` no longer throws (esc_like on an array was an unauthenticated 500).
4. Every JSON-LD block is encoded with JSON_HEX_TAG, so a `</script>` inside a
   company name cannot close the block. The writers strip tags today; the sink
   must not depend on that.
5. The reader digest never prints a provider exception unscrubbed.

Static and offline: reads the PHP and Python as text, executes nothing.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
DB = (PLUGIN / "includes/db.php").read_text(encoding="utf-8")

GET_PARAM = re.compile(r"get_param\('([a-zA-Z_]+)'\)")


def php_function_body(src, name):
    start = src.index(f"function {name}(")
    depth, i = 0, src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError(f"unbalanced braces after {name}")


def php_array_literals(body):
    return set(re.findall(r"'([a-zA-Z_]+)'", body))


class CacheKeyIsAWhitelist(unittest.TestCase):
    def whitelist(self):
        names = php_array_literals(php_function_body(DB, "alt_cached_route_param_names"))
        names |= php_array_literals(php_function_body(DB, "alt_filter_param_names"))
        return names

    def test_the_key_is_built_from_the_whitelist_only(self):
        body = php_function_body(DB, "alt_api_cached")
        self.assertIn("array_intersect_key($r->get_query_params(), array_flip(alt_cached_route_param_names()))", body)
        self.assertNotIn("unset($params['_']", body, "the old strip-two-names shape is back")

    def test_every_param_a_cached_route_reads_is_in_the_key(self):
        cached = re.findall(r"function (alt_api_[a-z_]+)\(WP_REST_Request \$r\) \{\n\s+return alt_api_cached\('", DB)
        self.assertGreaterEqual(len(cached), 4, cached)
        read = set()
        for fn in cached + [fn + "_compute" for fn in cached if f"function {fn}_compute(" in DB] + ["alt_db_where"]:
            read |= set(GET_PARAM.findall(php_function_body(DB, fn)))
        # alt_db_where also reads list dims through a closure: $int_in('years', ...)
        read |= set(re.findall(r"\$int_in\('([a-z_]+)'", php_function_body(DB, "alt_db_where")))
        missing = sorted(read - self.whitelist())
        self.assertEqual(missing, [], f"cached routes read params the cache key ignores: {missing}")


class FreeTextIsBounded(unittest.TestCase):
    def test_term_is_capped_and_array_safe(self):
        body = php_function_body(DB, "alt_freetext_clause")
        self.assertIn("mb_substr((string) $term, 0, ALT_FREETEXT_MAX_CHARS)", body)
        self.assertIn("if (is_array($term))", body)
        self.assertRegex(DB, r"define\('ALT_FREETEXT_MAX_CHARS', (\d+)\)")
        cap = int(re.search(r"define\('ALT_FREETEXT_MAX_CHARS', (\d+)\)", DB).group(1))
        self.assertLessEqual(cap, 255, "the cap must be at most one company column")
        # the cap must be applied BEFORE the term reaches esc_like
        self.assertLess(body.index("mb_substr((string) $term"), body.index("$wpdb->esc_like("))


def unhexed_ld_json(src):
    """Line numbers of ld+json script statements (single or multi-line) whose
    json_encode call is missing JSON_HEX_TAG."""
    out = []
    pos = 0
    while True:
        i = src.find("application/ld+json", pos)
        if i < 0:
            return out
        end = src.find("</script>", i)
        stmt = src[i:end if end > 0 else len(src)]
        if "json_encode" in stmt and "JSON_HEX_TAG" not in stmt:
            out.append(src.count("\n", 0, i) + 1)
        pos = i + 1


class JsonLdCannotCloseItsOwnScript(unittest.TestCase):
    def test_every_ld_json_sink_uses_hex_tag(self):
        bad = []
        for f in sorted(PLUGIN.rglob("*.php")):
            bad += [f"{f.relative_to(ROOT)}:{n}" for n in unhexed_ld_json(f.read_text(encoding="utf-8"))]
        self.assertEqual(bad, [], "JSON-LD encoded without JSON_HEX_TAG:\n" + "\n".join(bad))

    def test_the_scanner_would_catch_the_old_line(self):
        one = '    echo \'<script type="application/ld+json">\' . wp_json_encode($node, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\\n";\n'
        multi = '    echo \'<script type="application/ld+json">\' . wp_json_encode(array(\n        1,\n    ), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\\n";\n'
        self.assertEqual(unhexed_ld_json(one), [1])
        self.assertEqual(unhexed_ld_json(multi), [1])
        self.assertEqual(unhexed_ld_json(multi.replace("UNICODE)", "UNICODE | JSON_HEX_TAG)")), [])


class DigestNeverPrintsAnAddress(unittest.TestCase):
    def test_exception_prints_in_the_send_loop_are_scrubbed(self):
        src = (ROOT / "railway/digest_send.py").read_text(encoding="utf-8")
        loop = src[src.index("except TransportError as exc:"):src.index("except TransportError as exc:") + 900]
        for name in ("retry_exc", "exc"):
            for m in re.finditer(r"\{(%s)\}" % name, loop):
                self.fail(f"digest_send.py prints {{{name}}} unscrubbed: {loop[max(0, m.start()-60):m.end()]!r}")
        self.assertIn("_scrub(retry_exc)", loop)
        self.assertIn("_scrub(exc)", loop)


if __name__ == "__main__":
    unittest.main()
