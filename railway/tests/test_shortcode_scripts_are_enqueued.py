"""A SHORTCODE MUST NOT PRINT AN INLINE <script>. THE LIVE PAGE STRIPS THEM.

WHY THIS FILE EXISTS. The contact form's behaviour lived as an inline
``<script>`` inside its shortcode output and NEVER RAN in production. Measured
2026-09-12 against asktherecruiter.com: the rendered page carried the markup
the same function emits (``alt-tip-only``, ``data-alt-hints``) and not one line
of the script, while five other script tags on the same page survived. So
something in the stack strips script out of post content, it had been doing so
the whole time, and the tip-only "Company that had the layoff" field had never
appeared for a single visitor.

Nothing reported it and nothing could. A behaviour that never runs raises no
error, logs nothing, and leaves a page that looks correct. It was found only by
fetching the deployed page and grepping for a function name that should have
been in it.

WHAT IS PINNED HERE: no file under includes/ prints a ``<script>`` tag with a
body into shortcode output. Scripts ship as files under assets/ through
``wp_enqueue_script``, which is the shape that demonstrably survives
(assets/blog-claps.js, assets/health.js), with their data passed by
``wp_add_inline_script``, which attaches to an enqueued handle rather than to
content.

NOT pinned, and each exemption is a decision rather than a hole:

  * ``<script src=...>`` with no body. Third-party widget loaders (reCAPTCHA,
    Turnstile) are handed to us as a tag to place and carry no logic of ours.
  * ``<script type="application/ld+json">``. That is DATA in a script tag, not
    code: nothing executes it, so nothing can silently fail to run, and the
    four in company-directory.php and facet-pages.php are emitted from
    ``wp_head`` rather than into content. The live page carries them. This
    exemption was written after the first version of this guard flagged all
    four and they were checked against the deployed page; the rule is about
    code that is expected to RUN.
"""

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
INCLUDES = PLUGIN / "includes"

#: Loader tags for third-party widgets: a src and no body of ours.
_ALLOWED_SRC_ONLY = re.compile(
    r"<script\b[^>]*\bsrc=[^>]*>\s*</script>", re.I | re.S
)
#: Structured data in a script tag. Nothing executes it.
_ALLOWED_LD_JSON = re.compile(
    r"<script\b[^>]*\btype=[\"\']?application/ld\+json[\"\']?[^>]*>.*?</script>",
    re.I | re.S,
)
#: A script tag carrying statements. This is the shape that vanishes.
_SCRIPT_WITH_BODY = re.compile(r"<script\b(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.I | re.S)


def _php_sources():
    return sorted(INCLUDES.glob("*.php"))


class NoShortcodePrintsAScriptItExpectsToRun(unittest.TestCase):
    def test_no_include_emits_an_inline_script_with_a_body(self):
        offenders = []
        for path in _php_sources():
            text = path.read_text(encoding="utf-8")
            stripped = _ALLOWED_SRC_ONLY.sub("", text)
            stripped = _ALLOWED_LD_JSON.sub("", stripped)
            for match in _SCRIPT_WITH_BODY.finditer(stripped):
                body = match.group(1).strip()
                if not body:
                    continue
                line = stripped[: match.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}")
        self.assertEqual(
            offenders,
            [],
            "inline <script> with a body in shortcode output does not reach the "
            "live page (measured 2026-09-12, contact form). Move it to a file "
            "under assets/ and wp_enqueue_script it, passing any data with "
            "wp_add_inline_script. Offenders: " + ", ".join(offenders),
        )

    def test_the_contact_script_is_a_file_that_is_enqueued(self):
        self.assertTrue(
            (PLUGIN / "assets" / "contact.js").is_file(),
            "assets/contact.js is missing, so the contact form has no behaviour",
        )
        contact = (INCLUDES / "contact.php").read_text(encoding="utf-8")
        self.assertIn("wp_enqueue_script(", contact)
        self.assertIn("assets/contact.js", contact)

    def test_the_endpoint_reaches_the_file_without_being_printed_into_content(self):
        contact = (INCLUDES / "contact.php").read_text(encoding="utf-8")
        self.assertIn("wp_add_inline_script(", contact)
        self.assertIn("ALT_CONTACT_CHALLENGE_URL", contact)
        js = (PLUGIN / "assets" / "contact.js").read_text(encoding="utf-8")
        self.assertIn("window.ALT_CONTACT_CHALLENGE_URL", js)
        self.assertNotIn(
            "<?php", js, "a .js file cannot carry PHP; the URL arrives as a global"
        )

    def test_the_script_still_does_everything_the_inline_one_did(self):
        """The lift must not drop behaviour. These are the four things the
        inline version did, and the tip-only field is the one that had never
        worked for anyone."""
        js = (PLUGIN / "assets" / "contact.js").read_text(encoding="utf-8")
        for needle in ("alt-tip-only", "data-alt-question", "alt-c-topic-hint",
                       "alt_contact_nonce", "alt_ts", "alt_token"):
            self.assertIn(needle, js, "the enqueued script lost %r" % needle)

    def test_it_is_only_loaded_on_the_page_that_has_the_form(self):
        contact = (INCLUDES / "contact.php").read_text(encoding="utf-8")
        self.assertIn("has_shortcode(", contact)


if __name__ == "__main__":
    unittest.main()
