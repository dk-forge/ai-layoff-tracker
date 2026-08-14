"""THE SECONDARY PAGES ARE IN THE SITE NAVIGATION, AND THEY RENDER.

WHY THIS FILE EXISTS. /methodology/, /sources/ and /press/ have been live for
months with nothing in the site header pointing at them. The header menu
carried "AI Layoff Tracker" as one flat item, so a journalist who wanted the
methodology had to already be on the tracker page and scroll: measured live on
2026-08-13 the press route sat 13,252px down at 1280x900 and 31,707px down at
375x812. A hero button fixed that ONE route from that ONE page. This is the
level above it, and includes/nav-submenu.php is the change.

WHAT IS PINNED:

  * the four children exist, in reader order, under the tracker's own item;
  * every label is the DESTINATION'S OWN <h1>, read out of the template that
    renders it, so a rename cannot leave the menu describing a page that no
    longer calls itself that. This is the rule that already binds the post
    titles and the hero press button;
  * the sync is IDEMPOTENT. Running it twice produces one item per page and,
    on the second run, no write at all;
  * a page that stops being offered LOSES ITS ITEM rather than lingering on a
    404, and a child the owner added elsewhere is untouched;
  * a submenu's children survive serialisation. serialize_block() walks
    innerContent and substitutes an innerBlock for each null; a container
    handed an empty innerContent serialises with every child silently dropped,
    which is a toggle with nothing behind it;
  * the items RENDER: real geometry, real innerText, at 1280 and at 375, with
    no horizontal bleed at either. A menu item that exists in the DOM at 0x0
    is not a menu item, and reading the markup would not have told them apart.

HOW THE RENDERED HALF MEASURES, AND WHAT IT IS NOT.

This plugin does not render the menu; WordPress core does, from a
`wp_navigation` post, through a block renderer that is in neither repo. So the
fixture is CAPTURED rather than written: railway/tests/fixtures/site_nav.json
holds the live header nav's markup and the CSS core prints for it
(wp-block-navigation, its link stylesheet, global styles, block supports and
the Twenty Twenty-Five inline sheet), taken from the bare tracker URL with a
browser User-Agent on 2026-08-13.

The tracker's submenu is then built IN THE BROWSER by cloning the "Blog" item
out of that same captured markup -- an item core itself rendered, on that page,
as a submenu with six children -- and substituting only the labels and hrefs
this plugin produces. So the shape under test is core's own output and the only
invented part is the text, which is the part this plugin owns. What this file
therefore CANNOT catch is core changing how it renders a submenu; what it does
catch is every way this plugin can put the wrong thing, or nothing, into one.

The labels and hrefs are not typed here either: they are executed out of
includes/nav-submenu.php against the real templates, so this file has no copy
of any page's name.

No Chrome, no measurement: those tests SKIP loudly rather than passing.
Absence of a signal is not a pass (CLAUDE.md).

PROVEN TO FAIL, TWICE OVER.

On the pre-fix tree (origin/main@703dbf3, 2.20.34) all 19 collectable tests
failed or errored, the first of them with

    includes/nav-submenu.php does not exist, so nothing puts the secondary
    pages in the site navigation

"the file is missing" is a weak proof, so the fix was also taken back out
BEHAVIOURALLY, with nav-submenu.php present and alt_nav_children() reduced to
('methodology', 'sources'). Nine tests fail there, including both rendered
ones at both widths:

    at 1280x900 the submenu under "AI Layoff Tracker" reads
    ['Methodology & sources', 'Data Sources'] but the pages head themselves
    ['Methodology & sources', 'Data Sources', 'Press kit and soundbites',
     "AI layoffs, in the employer's own words"]

    /press/ is missing from the SERIALISED menu. The block array may hold it
    while innerContent does not, and innerContent is what core writes out.

That second run is the one that matters, and it is why _labels() reads the
templates rather than the plugin's own output: an expectation derived from the
thing under test would have passed on a submenu that had lost half of itself.
"""
import json
import re
import shutil
import subprocess
import sys
import time
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
NAV_PHP = PLUGIN / "includes/nav-submenu.php"
SHORTCODES = PLUGIN / "includes/shortcodes.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"
FIXTURE = Path(__file__).resolve().parent / "fixtures/site_nav.json"

PARENT_URL = "https://asktherecruiter.com/blog/ai-layoff-tracker/"

# The four, and the two that are deliberately out. Named here so a change to
# either list is a decision somebody made in a diff, not a drift.
EXPECTED_SLUGS = ["methodology", "sources", "press", "ai-quotes"]
EXCLUDED_SLUGS = ["ai-tracker-health", "publisher-tools"]


def php():
    return shutil.which("php")


def template_h1(name):
    src = (PLUGIN / "templates" / name).read_text(encoding="utf-8")
    m = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S | re.I)
    inner = m.group(1)
    for ent, ch in (("&amp;", "&"), ("&#038;", "&"), ("&rsquo;", "’"),
                    ("&#8217;", "’"), ("&quot;", '"'), ("&#039;", "'")):
        inner = inner.replace(ent, ch)
    return re.sub(r"\s+", " ", inner).strip()


# ---------------------------------------------------------------------------
# The WordPress shim.
#
# It loads the REAL includes/nav-submenu.php rather than extracting fragments
# of it, so a function this file never names is still the one under test. Only
# the WordPress side is stubbed, and the two block functions are core's own
# algorithms rather than approximations of them: serialize_block() drives the
# output off innerContent and substitutes an innerBlock for each null, which is
# precisely the behaviour the innerContent test below exists to pin.
# ---------------------------------------------------------------------------
SHIM = r"""
define('ABSPATH', 1);
define('ALT_PLUGIN_DIR', %(dir)s);
define('ALT_VERSION', 'test');
define('OBJECT', 'OBJECT');

$GLOBALS['pages'] = json_decode(%(pages)s, true);
$GLOBALS['options'] = array();
$GLOBALS['writes'] = array();

function add_action() {}
function add_filter() {}
function get_option($k, $d = false) { return array_key_exists($k, $GLOBALS['options']) ? $GLOBALS['options'][$k] : $d; }
function update_option($k, $v, $a = null) { $GLOBALS['options'][$k] = $v; return true; }
function add_option($k, $v, $x = '', $a = null) {
    if (array_key_exists($k, $GLOBALS['options'])) return false;
    $GLOBALS['options'][$k] = $v; return true;
}
function delete_option($k) { unset($GLOBALS['options'][$k]); return true; }

function get_page_by_path($path, $out = null, $type = 'page') {
    if (!isset($GLOBALS['pages'][$path])) return null;
    return (object) array('ID' => crc32($path), 'post_content' => $GLOBALS['pages'][$path]['content'],
                          'post_name' => basename($path), 'path' => $path);
}
function get_permalink($page) { return 'https://asktherecruiter.com/blog/' . $page->path . '/'; }
function has_shortcode($content, $tag) { return strpos((string) $content, '[' . $tag . ']') !== false; }

function get_posts($args) { return $GLOBALS['menus']; }
function wp_update_post($args) {
    foreach ($GLOBALS['menus'] as $m) {
        if ((int) $m->ID === (int) $args['ID']) { $m->post_content = $args['post_content']; }
    }
    $GLOBALS['writes'][] = (int) $args['ID'];
    return $args['ID'];
}

/* --- core's block grammar, both directions --- */
function parse_blocks($content) {
    $tok = '/<!--\s+(\/)?wp:([a-z][a-z0-9_-]*\/?[a-z0-9_-]*)\s*(\{.*?\})?\s*(\/)?-->/s';
    preg_match_all($tok, $content, $m, PREG_OFFSET_CAPTURE | PREG_SET_ORDER);
    $stack = array(array('blockName' => null, 'attrs' => array(), 'innerBlocks' => array(),
                         'innerHTML' => '', 'innerContent' => array()));
    $pos = 0;
    foreach ($m as $t) {
        $at = $t[0][1];
        $text = substr($content, $pos, $at - $pos);
        if (trim($text) !== '') {
            $top = count($stack) - 1;
            $stack[$top]['innerContent'][] = $text;
        }
        $pos = $at + strlen($t[0][0]);
        $closing = $t[1][0] === '/';
        $name = strpos($t[2][0], '/') === false ? 'core/' . $t[2][0] : $t[2][0];
        $attrs = (isset($t[3]) && $t[3][0] !== '') ? json_decode($t[3][0], true) : array();
        $self = isset($t[4]) && $t[4][0] === '/';
        if ($closing) {
            $done = array_pop($stack);
            $top = count($stack) - 1;
            $stack[$top]['innerBlocks'][] = $done;
            $stack[$top]['innerContent'][] = null;
        } elseif ($self) {
            $top = count($stack) - 1;
            $stack[$top]['innerBlocks'][] = array('blockName' => $name, 'attrs' => $attrs,
                'innerBlocks' => array(), 'innerHTML' => '', 'innerContent' => array());
            $stack[$top]['innerContent'][] = null;
        } else {
            $stack[] = array('blockName' => $name, 'attrs' => $attrs, 'innerBlocks' => array(),
                             'innerHTML' => '', 'innerContent' => array());
        }
    }
    return $stack[0]['innerBlocks'];
}

function get_comment_delimited_block_content($name, $attrs, $content) {
    $short = strpos($name, 'core/') === 0 ? substr($name, 5) : $name;
    $json = $attrs ? json_encode($attrs, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . ' ' : '';
    if ($content === '') return '<!-- wp:' . $short . ' ' . $json . '/-->';
    return '<!-- wp:' . $short . ' ' . $json . '-->' . $content . '<!-- /wp:' . $short . ' -->';
}

function serialize_block($block) {
    $content = '';
    $i = 0;
    foreach ($block['innerContent'] as $chunk) {
        $content .= is_string($chunk) ? $chunk : serialize_block($block['innerBlocks'][$i++]);
    }
    if (empty($block['blockName'])) return $content;
    return get_comment_delimited_block_content($block['blockName'], $block['attrs'], $content);
}

function serialize_blocks($blocks) {
    $out = '';
    foreach ($blocks as $b) { $out .= serialize_block($b); }
    return $out;
}

%(shortcodes)s
require %(nav)s;

$GLOBALS['menus'] = array();
foreach (json_decode(%(menus)s, true) as $id => $content) {
    $GLOBALS['menus'][] = (object) array('ID' => (int) $id, 'post_content' => $content);
}
"""

# The menu, as block markup. Reconstructed from the live rendered header nav
# captured in fixtures/site_nav.json: same items, same order, same URLs, with
# "Blog" as the one existing submenu. Its shape is core's serialiser output,
# which the round-trip test below holds this file's parser to.
MENU = (
    '<!-- wp:navigation-link {"label":"Pricing","type":"custom","url":"/pricing","kind":"custom","isTopLevelLink":true} /-->'
    '<!-- wp:navigation-submenu {"label":"Blog","type":"custom","url":"/blog/","kind":"custom","isTopLevelItem":true} -->'
    '<!-- wp:navigation-link {"label":"Resume Writing","type":"custom","url":"/blog/category/resume-writing/","kind":"custom"} /-->'
    '<!-- wp:navigation-link {"label":"Cover Letters","type":"custom","url":"/blog/category/cover-letters/","kind":"custom"} /-->'
    '<!-- /wp:navigation-submenu -->'
    '<!-- wp:navigation-link {"label":"AI Layoff Tracker","type":"custom","url":"'
    + PARENT_URL + '","kind":"custom","isTopLevelLink":true} /-->'
    '<!-- wp:navigation-link {"label":"Talent Intelligence Tracker","type":"custom",'
    '"url":"https://asktherecruiter.com/blog/talent-intelligence-tracker/","kind":"custom","isTopLevelLink":true} /-->'
)


def php_fn(src, name):
    """One function's source, lifted whole.

    includes/shortcodes.php registers shortcodes as it loads, so requiring it
    would need a stub for every WordPress function it touches at load time.
    The two functions the nav sync depends on are lifted instead, the same way
    test_secondary_surface_consistency.py lifts them, so both files execute the
    real reader rather than a description of it.
    """
    needle = "function %s(" % name
    assert needle in src, (
        "%s() is gone from includes/shortcodes.php, so nothing derives a menu "
        "label from the heading the destination renders" % name)
    body = src[src.index(needle):]
    return body[:body.index("\n}\n") + 3]


def shortcode_fns():
    src = SHORTCODES.read_text(encoding="utf-8")
    return php_fn(src, "alt_secondary_pages") + php_fn(src, "alt_template_heading")


def secondary_pages():
    """path => (template, shortcode), read out of the plugin rather than typed."""
    src = SHORTCODES.read_text(encoding="utf-8")
    body = src[src.index("function alt_secondary_pages("):]
    body = body[:body.index("\n}\n")]
    out = {}
    for m in re.finditer(r"'([^']+)'\s*=>\s*array\('([^']+)',\s*'([^']+)'\)", body):
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


class PHPHarness:
    """Runs an expression against the real nav-submenu.php under the shim."""

    def __init__(self, pages=None, menus=None):
        self.pages = pages if pages is not None else self.default_pages()
        self.menus = menus if menus is not None else {"72": MENU}

    @staticmethod
    def default_pages():
        pages = {}
        for path, (_tpl, shortcode) in secondary_pages().items():
            pages[path] = {"content": "[%s]" % shortcode}
        pages["ai-layoff-tracker"] = {"content": "[alt_tracker]"}
        return pages

    def run(self, php_body):
        shim = SHIM % {
            "dir": json.dumps(str(PLUGIN) + "/"),
            "shortcodes": shortcode_fns(),
            "nav": json.dumps(str(NAV_PHP)),
            "pages": json.dumps(json.dumps(self.pages)),
            "menus": json.dumps(json.dumps(self.menus)),
        }
        proc = subprocess.run([php(), "-r", shim + "\n" + php_body],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            raise AssertionError(proc.stderr or proc.stdout)
        return json.loads(proc.stdout)


class TheFileIsLoaded(unittest.TestCase):
    def test_the_plugin_requires_it(self):
        self.assertTrue(
            NAV_PHP.exists(),
            "includes/nav-submenu.php does not exist, so nothing puts the "
            "secondary pages in the site navigation")
        self.assertIn(
            "includes/nav-submenu.php", MAIN.read_text(encoding="utf-8"),
            "the plugin does not load includes/nav-submenu.php, so nothing "
            "puts the secondary pages in the site navigation")


class TheChildrenAreTheRightPages(unittest.TestCase):
    def setUp(self):
        if not php():
            self.skipTest("php not installed")
        self.h = PHPHarness()

    def test_the_curated_four_in_reader_order(self):
        got = self.h.run("echo json_encode(alt_nav_children());")
        self.assertEqual(
            got, EXPECTED_SLUGS,
            "the submenu offers %r; the four a reader needs, in the order they "
            "need them, are %r" % (got, EXPECTED_SLUGS))

    def test_the_operator_and_republisher_pages_stay_out(self):
        got = self.h.run("echo json_encode(alt_nav_children());")
        for slug in EXCLUDED_SLUGS:
            self.assertNotIn(
                slug, got,
                "/%s/ is in the site header. The health page is an operations "
                "dashboard, unlinked on purpose and noindexed; publisher-tools "
                "is one click from the press kit. Neither is a route a reader "
                "arriving cold needs in the navigation." % slug)

    def test_it_can_only_name_pages_the_plugin_already_owns(self):
        known = {p.rsplit("/", 1)[1] for p in secondary_pages()}
        for slug in EXPECTED_SLUGS:
            self.assertIn(
                slug, known,
                "%r is not in alt_secondary_pages(), so the menu would carry an "
                "item for a page this plugin does not render" % slug)

    def test_every_label_is_the_destinations_own_h1(self):
        got = self.h.run("echo json_encode(alt_nav_desired_children());")
        pages = secondary_pages()
        want = [template_h1(pages["ai-layoff-tracker/" + s][0]) for s in EXPECTED_SLUGS]
        self.assertEqual(
            [c["label"] for c in got], want,
            "the menu would read %r while the pages head themselves %r, so a "
            "rename left the navigation describing something else"
            % ([c["label"] for c in got], want))

    def test_every_child_points_at_its_own_page(self):
        got = self.h.run("echo json_encode(alt_nav_desired_children());")
        self.assertEqual(
            [c["url"] for c in got],
            [PARENT_URL + s + "/" for s in EXPECTED_SLUGS])

    def test_no_dash_in_any_label(self):
        # style_check.py needs 12 characters and 3 real words before a string is
        # eligible, so a menu label slips past it. Checked here by eye's proxy.
        got = self.h.run("echo json_encode(alt_nav_desired_children());")
        for child in got:
            for dash in ("—", "–"):
                self.assertNotIn(
                    dash, child["label"],
                    "the menu label %r carries a dash the UI copy rule forbids "
                    "and style_check.py is too short to see" % child["label"])

    def test_a_page_that_lost_its_shortcode_stops_the_whole_sync(self):
        pages = PHPHarness.default_pages()
        pages["ai-layoff-tracker/press"]["content"] = "the owner repurposed this"
        got = PHPHarness(pages=pages).run("echo json_encode(alt_nav_desired_children());")
        self.assertEqual(
            got, [],
            "a page that no longer carries its shortcode still produced a menu "
            "set. A partial submenu written to the live menu is worse than "
            "none; the caller must see empty and retry.")

    def test_a_missing_page_stops_the_whole_sync(self):
        pages = PHPHarness.default_pages()
        del pages["ai-layoff-tracker/methodology"]
        got = PHPHarness(pages=pages).run("echo json_encode(alt_nav_desired_children());")
        self.assertEqual(got, [], "a menu item was built for a page that does not exist")


class TheSyncIsIdempotent(unittest.TestCase):
    """Register twice, get one item."""

    def setUp(self):
        if not php():
            self.skipTest("php not installed")

    def _twice(self, menus=None, pages=None):
        h = PHPHarness(pages=pages, menus=menus)
        return h.run(r"""
$GLOBALS['options']['alt_nav_submenu_last_try'] = 0;
alt_nav_submenu_sync();
$after_one = $GLOBALS['menus'][0]->post_content;
$writes_one = count($GLOBALS['writes']);

// A second registration, exactly as a second request would run it: the
// done-flag and the retry throttle are cleared so nothing but the code under
// test can be what makes the second run a no-op.
unset($GLOBALS['options']['alt_nav_submenu_synced']);
$GLOBALS['options']['alt_nav_submenu_last_try'] = 0;
alt_nav_submenu_sync();
$after_two = $GLOBALS['menus'][0]->post_content;

$blocks = parse_blocks($after_two);
$item = alt_nav_find($blocks, alt_nav_normalize_url(%s));
$kids = array();
foreach ($item['innerBlocks'] as $c) { $kids[] = $c['attrs']['url']; }
echo json_encode(array('one' => $after_one, 'two' => $after_two,
                       'writes_one' => $writes_one,
                       'writes_total' => count($GLOBALS['writes']),
                       'name' => $item['blockName'], 'kids' => $kids,
                       'synced' => get_option('alt_nav_submenu_synced')));
""" % json.dumps(PARENT_URL))

    def test_the_second_run_writes_nothing(self):
        r = self._twice()
        self.assertEqual(r["writes_one"], 1, "the first run did not write once")
        self.assertEqual(
            r["writes_total"], 1,
            "registering twice wrote the menu %d times. The second run must "
            "find the item already correct and perform no write at all."
            % r["writes_total"])

    def test_registering_twice_leaves_one_item_per_page(self):
        r = self._twice()
        self.assertEqual(
            r["kids"], [PARENT_URL + s + "/" for s in EXPECTED_SLUGS],
            "after two registrations the submenu holds %r. Each destination is "
            "offered once." % (r["kids"],))
        self.assertEqual(len(r["kids"]), len(set(r["kids"])),
                         "a destination appears twice in the submenu")

    def test_the_menu_is_byte_identical_after_the_second_run(self):
        r = self._twice()
        self.assertEqual(r["one"], r["two"],
                         "the second registration changed the stored menu")

    def test_the_item_became_a_submenu_and_the_flag_was_set(self):
        r = self._twice()
        self.assertEqual(r["name"], "core/navigation-submenu")
        self.assertEqual(r["synced"], "test",
                         "the sync never verified, so it would rewrite the menu "
                         "on every request forever")


class NothingIsOrphaned(unittest.TestCase):
    def setUp(self):
        if not php():
            self.skipTest("php not installed")

    def _sync_and_read(self, menu):
        return PHPHarness(menus={"72": menu}).run(r"""
$GLOBALS['options']['alt_nav_submenu_last_try'] = 0;
alt_nav_submenu_sync();
$blocks = parse_blocks($GLOBALS['menus'][0]->post_content);
$item = alt_nav_find($blocks, alt_nav_normalize_url(%s));
$kids = array();
if ($item) { foreach ($item['innerBlocks'] as $c) { $kids[] = $c['attrs']['url']; } }
echo json_encode(array('kids' => $kids, 'content' => $GLOBALS['menus'][0]->post_content,
                       'writes' => count($GLOBALS['writes'])));
""" % json.dumps(PARENT_URL))

    def test_a_retired_page_loses_its_item(self):
        stale = PARENT_URL + "publisher-tools/"
        menu = MENU.replace(
            '"url":"' + PARENT_URL + '","kind":"custom","isTopLevelLink":true} /-->',
            '"url":"' + PARENT_URL + '","kind":"custom","isTopLevelItem":true} -->'
            '<!-- wp:navigation-link {"label":"Embed the layoff tracker","type":"custom",'
            '"url":"' + stale + '","kind":"custom"} /-->'
            '<!-- /wp:navigation-submenu -->')
        r = self._sync_and_read(menu)
        self.assertNotIn(
            stale, r["kids"],
            "a page that is no longer offered kept its menu item. A retired or "
            "renamed page's item must follow it, not linger pointing at a page "
            "the navigation still claims is there.")
        self.assertEqual(r["kids"], [PARENT_URL + s + "/" for s in EXPECTED_SLUGS])

    def test_a_child_the_owner_added_elsewhere_survives(self):
        theirs = "https://asktherecruiter.com/blog/contact/"
        menu = MENU.replace(
            '"url":"' + PARENT_URL + '","kind":"custom","isTopLevelLink":true} /-->',
            '"url":"' + PARENT_URL + '","kind":"custom","isTopLevelItem":true} -->'
            '<!-- wp:navigation-link {"label":"Contact","type":"custom",'
            '"url":"' + theirs + '","kind":"custom"} /-->'
            '<!-- /wp:navigation-submenu -->')
        r = self._sync_and_read(menu)
        self.assertIn(
            theirs, r["kids"],
            "a child the owner put under the tracker pointing outside it was "
            "deleted. This plugin manages the items below its own page and "
            "nothing else.")

    def test_the_sibling_trackers_item_is_untouched(self):
        r = self._sync_and_read(MENU)
        self.assertIn(
            '"label":"Talent Intelligence Tracker"', r["content"],
            "the sibling tracker's menu item was lost. Both plugins write this "
            "one post; that is what ALT_NAV_LOCK_OPTION exists for.")
        self.assertIn('"label":"Blog"', r["content"])
        self.assertIn('"label":"Pricing"', r["content"])

    def test_a_parent_in_no_menu_writes_nothing(self):
        r = self._sync_and_read(
            '<!-- wp:navigation-link {"label":"Pricing","type":"custom",'
            '"url":"/pricing","kind":"custom"} /-->')
        self.assertEqual(
            r["writes"], 0,
            "the tracker is in no menu on this site and the sync wrote anyway. "
            "A menu we are not in is not a menu we may create items in.")

    def test_the_children_survive_serialisation(self):
        # The innerContent trap: serialize_block() substitutes an innerBlock for
        # each null in innerContent and never reads innerBlocks directly, so a
        # container built with an empty innerContent serialises as a submenu
        # with no children at all - a toggle with nothing behind it.
        r = self._sync_and_read(MENU)
        for slug in EXPECTED_SLUGS:
            self.assertIn(
                PARENT_URL + slug + "/", r["content"],
                "/%s/ is missing from the SERIALISED menu. The block array may "
                "hold it while innerContent does not, and innerContent is what "
                "core writes out." % slug)


class TheBlockGrammarShimIsFaithful(unittest.TestCase):
    """The shim's parser is this file's, so it is held to a round trip.

    If parse_blocks/serialize_blocks here disagreed with core's grammar, every
    assertion above would be measuring a fiction. A byte-identical round trip
    of core-shaped markup is the check that they do not.
    """

    def setUp(self):
        if not php():
            self.skipTest("php not installed")

    def test_the_menu_round_trips_byte_for_byte(self):
        got = PHPHarness().run(
            "echo json_encode(serialize_blocks(parse_blocks(%s)));" % json.dumps(MENU))
        self.assertEqual(got, MENU)


# ---------------------------------------------------------------------------
# Rendered
# ---------------------------------------------------------------------------
BUILD = r"""
(function (children) {
  var nav = document.querySelector('nav.wp-block-navigation');
  var items = nav.querySelectorAll('li');
  var blog = null, ours = null;
  Array.prototype.forEach.call(items, function (li) {
    var a = li.querySelector(':scope > a.wp-block-navigation-item__content');
    if (!a) return;
    var t = a.textContent.trim();
    if (t === 'Blog' && li.classList.contains('has-child')) blog = li;
    if (t === 'AI Layoff Tracker') ours = li;
  });
  if (!blog || !ours) return 'no seed item: blog=' + !!blog + ' ours=' + !!ours;

  // Core rendered this submenu on this page. Clone its exact shape and change
  // only the text and the hrefs, so nothing about the markup is invented here.
  var next = blog.cloneNode(true);
  var head = next.querySelector(':scope > a.wp-block-navigation-item__content');
  head.setAttribute('href', ours.querySelector('a').getAttribute('href'));
  head.querySelector('.wp-block-navigation-item__label').textContent = 'AI Layoff Tracker';
  var toggle = next.querySelector(':scope > button.wp-block-navigation-submenu__toggle');
  toggle.setAttribute('aria-label', 'AI Layoff Tracker submenu');

  var sub = next.querySelector(':scope > ul.wp-block-navigation__submenu-container');
  var seed = sub.querySelector('li');
  sub.textContent = '';
  children.forEach(function (c) {
    var li = seed.cloneNode(true);
    var a = li.querySelector('a');
    a.setAttribute('href', c.url);
    li.querySelector('.wp-block-navigation-item__label').textContent = c.label;
    sub.appendChild(li);
  });
  next.setAttribute('data-alt-tracker-item', '1');
  ours.parentNode.replaceChild(next, ours);
  return 'ok';
})(%s)
"""

OPEN_DESKTOP = r"""
(function () {
  // What a reader's click produces. Core opens on hover or on the toggle
  // reporting aria-expanded=true; only the second is reachable from here.
  var t = document.querySelector('[data-alt-tracker-item] > button.wp-block-navigation-submenu__toggle');
  t.setAttribute('aria-expanded', 'true');
  return true;
})()
"""

OPEN_MOBILE = r"""
(function () {
  // What core's interactivity store sets when the hamburger is tapped.
  var c = document.querySelector('.wp-block-navigation__responsive-container');
  c.classList.add('is-menu-open', 'has-modal-open');
  document.documentElement.classList.add('has-modal-open');
  return true;
})()
"""

MEASURE = r"""
(function () {
  var item = document.querySelector('[data-alt-tracker-item]');
  if (!item) return { error: 'the tracker item is not in the menu' };
  var sub = item.querySelector(':scope > ul.wp-block-navigation__submenu-container');
  var cs = getComputedStyle(sub);
  var sr = sub.getBoundingClientRect();
  var out = [];
  Array.prototype.forEach.call(sub.querySelectorAll(':scope > li'), function (li) {
    var a = li.querySelector('a');
    var r = a.getBoundingClientRect();
    out.push({
      // innerText off the rendered ancestor, never textContent: a hidden
      // submenu still carries textContent for text no reader can read.
      text: (li.innerText || '').trim().replace(/\s+/g, ' '),
      href: a.getAttribute('href'),
      w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
      x: Math.round(r.left * 10) / 10, y: Math.round(r.top * 10) / 10,
      right: Math.round(r.right * 10) / 10
    });
  });
  return {
    visibility: cs.visibility, display: cs.display, opacity: cs.opacity,
    subW: Math.round(sr.width * 10) / 10, subH: Math.round(sr.height * 10) / 10,
    subRight: Math.round(sr.right * 10) / 10,
    docW: document.documentElement.scrollWidth,
    winW: window.innerWidth,
    items: out
  };
})()
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(css)s</style>
<style>body{margin:0;background:#fff;color:#16181d;font-family:system-ui,sans-serif}</style>
</head><body class="wp-singular page"><div class="wp-site-blocks"><header class="wp-block-template-part">
%(nav)s
</header></div></body></html>
"""


class TheSubmenuRenders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not php():
            raise unittest.SkipTest("php not installed")
        if not find_chrome():
            raise unittest.SkipTest("no Chrome: geometry cannot be measured, "
                                    "and absence of a signal is not a pass")
        fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.html = PAGE % {"css": fx["css"], "nav": fx["nav_html"]}
        cls.children = PHPHarness().run("echo json_encode(alt_nav_desired_children());")

    def _render(self, width, height, opener):
        url = "data:text/html;charset=utf-8," + urllib.parse.quote(self.html)
        try:
            with Browser(width=width, height=height) as b:
                b.navigate(url, settle=1.0)
                built = b.eval_js(BUILD % json.dumps(self.children))
                self.assertEqual(built, "ok", built)
                b.eval_js(opener)
                # The container carries `transition: opacity .1s linear`, so a
                # measurement taken in the same tick reads opacity 0 on a
                # submenu that is opening correctly.
                time.sleep(0.4)
                return b.eval_js(MEASURE)
        except CDPUnavailable as exc:
            self.skipTest("Chrome unavailable: %s" % exc)

    def _labels(self):
        """What the four pages head themselves, read from the templates.

        Deliberately NOT [c["label"] for c in self.children]: the rendered
        markup is built from what the plugin produced, so comparing it back to
        the same source would pass on a submenu that had lost two of the four.
        The expectation comes from the destinations.
        """
        pages = secondary_pages()
        return [template_h1(pages["ai-layoff-tracker/" + s][0]) for s in EXPECTED_SLUGS]

    def test_the_four_read_as_the_pages_head_themselves_at_1280(self):
        r = self._render(1280, 900, OPEN_DESKTOP)
        self.assertNotIn("error", r, r.get("error"))
        got = [i["text"] for i in r["items"]]
        self.assertEqual(
            got, self._labels(),
            'at 1280x900 the submenu under "AI Layoff Tracker" reads %r but the '
            "pages head themselves %r" % (got, self._labels()))

    def test_every_item_has_real_geometry_at_1280(self):
        r = self._render(1280, 900, OPEN_DESKTOP)
        self.assertEqual(r["visibility"], "visible",
                         "the submenu container computes visibility:%s, so none "
                         "of its items is on the page" % r["visibility"])
        self.assertGreater(
            float(r["opacity"]), 0.0,
            "the open submenu computes opacity:%s, so it has geometry a reader "
            "cannot see" % r["opacity"])
        for item in r["items"]:
            self.assertGreater(
                item["w"] * item["h"], 0,
                "at 1280x900 %r renders %sx%s. An item in the DOM at zero size "
                "is not a menu item." % (item["text"], item["w"], item["h"]))

    def test_the_four_read_as_the_pages_head_themselves_at_375(self):
        r = self._render(375, 812, OPEN_MOBILE)
        got = [i["text"] for i in r["items"]]
        self.assertEqual(
            got, self._labels(),
            "at 375x812 the submenu reads %r but the pages head themselves %r"
            % (got, self._labels()))

    def test_every_item_has_real_geometry_at_375(self):
        r = self._render(375, 812, OPEN_MOBILE)
        for item in r["items"]:
            self.assertGreater(
                item["w"] * item["h"], 0,
                "at 375x812 %r renders %sx%s" % (item["text"], item["w"], item["h"]))

    def test_nothing_bleeds_horizontally_at_375(self):
        r = self._render(375, 812, OPEN_MOBILE)
        self.assertLessEqual(
            r["docW"], r["winW"],
            "the document scrolls to %spx inside a %spx viewport once the menu "
            "is open. Nothing on this project may bleed horizontally on a "
            "phone." % (r["docW"], r["winW"]))
        for item in r["items"]:
            self.assertLessEqual(
                item["right"], r["winW"] + 0.5,
                "at 375px %r ends at %spx, past the %spx viewport"
                % (item["text"], item["right"], r["winW"]))

    def test_nothing_bleeds_horizontally_at_1280(self):
        r = self._render(1280, 900, OPEN_DESKTOP)
        self.assertLessEqual(
            r["docW"], r["winW"],
            "the document scrolls to %spx inside a %spx viewport with the "
            "submenu open" % (r["docW"], r["winW"]))
        self.assertLessEqual(
            r["subRight"], r["winW"] + 0.5,
            "the open submenu's right edge is %spx, past the %spx viewport, so "
            "the longest label pushes it off screen" % (r["subRight"], r["winW"]))


if __name__ == "__main__":
    unittest.main()
