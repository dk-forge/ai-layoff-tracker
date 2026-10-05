"""Duplicate featured image on blog posts (includes/blog-dup-images.php).

The theme already renders a post's featured image above the title. ~122 posts
ALSO carried that same image as the first block of post_content, so readers saw
it twice. The include (a) strips that duplicate at render time so any future
post published the same way cannot show it twice, and (b) exposes a keyed
route the cleanup workflow uses to remove it from stored content.

These run the REAL PHP functions against sample HTML. Rule under test: only a
block whose <img> is the SAME attachment (wp-image-ID / data-id / same file,
any size variant) as the featured image is removed, only the first one, and a
post without a match is returned byte-identical. No PHP binary -> SKIP.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

PHP_FILE = Path(__file__).resolve().parents[2] / "wordpress-plugin/ai-layoff-tracker/includes/blog-dup-images.php"
URL = "https://asktherecruiter.com/blog/wp-content/uploads/2026/05/hero.jpg"


def strip(content, thumb_id=42, thumb_url=URL):
    code = (
        "define('ABSPATH','/');function add_filter(){}function add_action(){}"
        f"require {json.dumps(str(PHP_FILE))};"
        "$a=json_decode(stream_get_contents(STDIN),true);"
        "echo json_encode(alt_dup_image_strip($a[0],$a[1],$a[2]));"
    )
    out = subprocess.run(["php", "-r", code], input=json.dumps([content, thumb_id, thumb_url]),
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@unittest.skipUnless(shutil.which("php"), "no php binary: SKIPPED, not passed")
class DupImageStrip(unittest.TestCase):
    def test_gutenberg_image_block_with_same_id_removed(self):
        html = ('<!-- wp:image {"id":42,"sizeSlug":"large"} -->\n<figure class="wp-block-image size-large">'
                '<img src="https://asktherecruiter.com/blog/wp-content/uploads/2026/05/hero-1024x683.jpg" '
                'alt="" class="wp-image-42"/></figure>\n<!-- /wp:image -->\n\n<!-- wp:paragraph -->\n<p>Body</p>\n<!-- /wp:paragraph -->')
        self.assertEqual(strip(html).strip(), '<!-- wp:paragraph -->\n<p>Body</p>\n<!-- /wp:paragraph -->')

    def test_classic_figure_matched_by_url_size_variant(self):
        html = ('<figure><img src="/blog/wp-content/uploads/2026/05/hero-300x200.jpg"></figure><p>Body</p>'
                '<figure><img src="' + URL + '"></figure>')
        out = strip(html, thumb_id=0)
        self.assertEqual(out, '<p>Body</p><figure><img src="' + URL + '"></figure>')  # only the FIRST

    def test_paragraph_wrapped_linked_img_removed(self):
        html = '<p><a href="x"><img class="alignnone wp-image-42" src="a.jpg"></a></p><p>Body</p>'
        self.assertEqual(strip(html), '<p>Body</p>')

    def test_different_image_untouched(self):
        html = ('<!-- wp:image {"id":7} --><figure><img src="/blog/wp-content/uploads/2026/05/other.jpg" '
                'class="wp-image-7"></figure><!-- /wp:image --><p>Body</p>')
        self.assertEqual(strip(html), html)

    def test_no_featured_image_untouched(self):
        html = '<figure><img class="wp-image-42" src="' + URL + '"></figure>'
        self.assertEqual(strip(html, thumb_id=0, thumb_url=""), html)

    def test_similar_filename_is_not_a_match(self):
        html = '<img src="/blog/wp-content/uploads/2026/05/hero-banner.jpg"><p>x</p>'
        self.assertEqual(strip(html, thumb_id=0), html)


class Notices(unittest.TestCase):
    def test_summary_and_per_post(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from blog_dup_images import notices
        lines = notices({"count": 2, "scanned": 9, "fixed": [], "posts": [
            {"id": 5, "thumb": 42, "removed": "<figure>\n<img></figure>"}, {"id": 8, "thumb": 3, "removed": ""}]}, True)
        self.assertEqual(lines[0], "::notice title=dup-images::count=2 dry_run=1 scanned=9 fixed=0 ids=5,8")
        self.assertEqual(len(lines), 3)
        self.assertNotIn("\n", lines[1])


if __name__ == "__main__":
    unittest.main()
