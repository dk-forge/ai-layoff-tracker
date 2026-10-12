"""Every chart canvas in a plugin template carries an accessible name.

SEO route B item 5 (issue #446): a <canvas> is opaque to a screen reader and
to a crawler, so each one is `role="img"` with an `aria-label` (or an
`aria-labelledby` pointing at its visible heading). A new chart added without
one fails here instead of shipping unlabeled.
"""
import re
import unittest
from pathlib import Path

TEMPLATES = (Path(__file__).resolve().parents[2]
             / "wordpress-plugin" / "ai-layoff-tracker" / "templates")
CANVAS = re.compile(r"<canvas\b.*?</canvas>", re.S)


class EveryCanvasIsLabelled(unittest.TestCase):
    def test_every_template_canvas_has_role_img_and_a_label(self):
        found = 0
        for path in sorted(TEMPLATES.rglob("*.php")):
            for tag in CANVAS.findall(path.read_text(encoding="utf-8")):
                found += 1
                with self.subTest(file=path.name, tag=tag[:80]):
                    self.assertIn('role="img"', tag)
                    self.assertRegex(tag, r'aria-label(ledby)?="[^"]+"')
        self.assertGreater(found, 10, "no canvases found: wrong path?")


if __name__ == "__main__":
    unittest.main()
