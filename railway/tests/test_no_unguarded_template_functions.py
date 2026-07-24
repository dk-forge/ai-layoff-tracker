"""Guard against the recurring fatal: a function defined in a TEMPLATE.

WordPress evaluates a page's content (and thus a shortcode's template) more than
once per request (SEO/meta-description and excerpt passes, some during wp_head).
A template that DEFINES a top-level function therefore hits "Cannot redeclare
function" - a PHP FATAL - on the second render. This has caused live outages
(alt_country_flag, 2.19.157). The deploy's `php -l` gate cannot catch it: a
redeclare is a runtime error, not a syntax error.

This test makes the class impossible to reintroduce: every top-level function
defined under templates/ must be wrapped in an `if (!function_exists('name'))`
guard, UNLESS its file is loaded exactly once via require_once (allowlisted).
CI (.github/workflows/tests.yml) runs it on every push.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
TEMPLATES = os.path.join(PLUGIN, "templates")

# Files loaded exactly ONCE via require_once in the main plugin file, so their
# functions cannot double-declare. Keep this list tiny and justified.
REQUIRE_ONCE_SAFE = {
    "warn-state-urls.php",   # require_once'd at ai-layoff-tracker.php:~35 (a pure
                             # generated helper map, never rendered as a shortcode)
}

_FUNC_RE = re.compile(r"^\s*function\s+(alt_[a-z0-9_]+)\s*\(", re.M)


def _php_files(root):
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".php"):
                yield os.path.join(dirpath, f)


class NoUnguardedTemplateFunctions(unittest.TestCase):
    def test_every_template_function_is_guarded_or_require_once(self):
        offenders = []
        for path in _php_files(TEMPLATES):
            base = os.path.basename(path)
            if base in REQUIRE_ONCE_SAFE:
                continue
            src = open(path, encoding="utf-8").read()
            for m in _FUNC_RE.finditer(src):
                name = m.group(1)
                # The guard must appear within the ~3 lines before the definition.
                head = src[:m.start()]
                preceding = head.rsplit("\n", 4)[-4:]
                guard = f"function_exists('{name}')"
                if not any(guard in ln for ln in preceding):
                    line = head.count("\n") + 1
                    offenders.append(f"{base}:{line} function {name}() is not "
                                     f"wrapped in if (!{guard})")
        self.assertFalse(offenders, (
            "Template-defined functions must be guarded against double-declare "
            "(a template renders more than once per request => FATAL). Wrap each "
            "in `if (!function_exists('name')) { ... }`, or (rarely) load the file "
            "once via require_once and allowlist it. Offenders:\n  "
            + "\n  ".join(offenders)))

    def test_allowlist_files_still_exist(self):
        # A stale allowlist entry hides a real gap; keep it honest.
        for base in REQUIRE_ONCE_SAFE:
            found = any(os.path.basename(p) == base for p in _php_files(TEMPLATES))
            self.assertTrue(found, f"allowlisted {base} no longer exists; remove it")


if __name__ == "__main__":
    unittest.main()
