"""An array-shaped query param must not fatal an export mid-download.

Measured 2026-08-03: `?q[]=x` made $_GET['q'] an array, alt_db_where() handed
it to a string function, and PHP fataled INSIDE alt_export_walk - after
alt_export_throttle() had burned a rate slot, after the 200 and the
Content-Disposition header, and after the BOM and header row were on the wire.
The visitor received a CSV whose body was a PHP error and paid a throttle slot
for it. Fixed by flattening to scalars at the entry point.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPORT = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "includes" / "export.php"


class ExportParamShape(unittest.TestCase):
    def test_params_are_flattened_before_the_filter_builder(self):
        src = EXPORT.read_text()
        fn = src[src.index("function alt_export_filters"):]
        fn = fn[:fn.index("\n}")]
        self.assertIn("is_scalar", fn,
                      "alt_export_filters must drop array-shaped params before "
                      "alt_db_where sees them")
        flat = fn.index("is_scalar")
        # the RETURN's call, not the explanatory comment above it (which
        # names the function too - this test failed on its own fix once).
        call = fn.index("return alt_db_where")
        self.assertLess(flat, call,
                        "the flatten has to happen BEFORE the filter builder, "
                        "or it protects nothing")

    def test_the_raw_get_is_not_passed_through(self):
        src = EXPORT.read_text()
        fn = src[src.index("function alt_export_filters"):]
        fn = fn[:fn.index("\n}")]
        self.assertNotRegex(
            fn, r"set_query_params\(\s*\$params\s*\)",
            "the unflattened $params must not reach set_query_params")


if __name__ == "__main__":
    unittest.main()
