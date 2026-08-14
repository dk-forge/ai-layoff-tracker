<?php
/**
 * THE SECONDARY PAGES ARE IN THE SITE NAVIGATION, UNDER THE TRACKER.
 *
 * WHY THIS FILE EXISTS. The methodology, the source list and the press kit
 * have been live for months and were reachable only from inside the tracker
 * page itself, near its foot. Measured on the live page on 2026-08-13, the
 * press route's link sat 13,252px down at 1280x900 and 31,707px down at
 * 375x812. 2.20.35 put a control for it in the hero, which fixes ONE of those
 * pages from ONE of those pages. A journalist who lands on /methodology/, or
 * who lands anywhere at all and wants the source list, still has nothing in
 * the site navigation to follow: "AI Layoff Tracker" is one flat item in the
 * header menu with no children.
 *
 * So the plugin puts them there itself. The owner asked for "a submenu under
 * each tracker in WP admin"; this is that outcome, done from the plugin, so it
 * survives a deploy, a menu edit and a page rename without anybody clicking
 * through wp-admin again.
 *
 * WHAT THE HEADER MENU ACTUALLY IS. Twenty Twenty-Five is a block theme and
 * this site's header nav is a core/navigation block, so the menu is not the
 * classic nav_menu taxonomy: it is block markup stored as the post_content of
 * a `wp_navigation` post ("ATR Main Menu"). Read live 2026-08-13, its top
 * level is Pricing, Blog (a submenu with six children), AI Layoff Tracker,
 * Talent Intelligence Tracker; the two trackers are flat
 * `core/navigation-link` blocks. This file converts OUR one to a
 * `core/navigation-submenu` carrying the same label and url, with our children
 * inside it, using parse_blocks()/serialize_blocks() so the shape is core's
 * own and not a string this plugin invented. If no wp_navigation post carries
 * our URL, nothing happens and it retries later; the classic taxonomy is not
 * handled because this site does not use it, and a menu we are not in is not a
 * menu we may create.
 *
 * THE LABELS HAVE ONE AUTHOR AND IT IS THE PAGE. Every child label is
 * alt_template_heading() off the template that renders the destination, the
 * same rule that already binds the post titles (alt_sync_secondary_page_titles)
 * and the hero press button. A heading that cannot be read verbatim yields '',
 * and '' aborts the whole sync rather than naming a menu item from a guess.
 * Rename a page's <h1> and the menu follows on the next deploy.
 *
 * NOTHING IS ORPHANED. The child set is rebuilt from ALT_NAV_CHILDREN, and a
 * page only earns an item if it EXISTS and still contains the shortcode that
 * renders it, which is the same ownership test the title sync uses (a slug is
 * not ownership). Any existing child under our tracker path that is not in the
 * rebuilt set is DROPPED, so a retired or renamed page's item goes with it
 * instead of lingering on a 404. Children pointing anywhere else are left
 * exactly as the owner left them.
 *
 * RETRY UNTIL VERIFIED, never one-shot on a version bump. FTP deploys bypass
 * every WordPress hook and land files one at a time, so a hook that fires
 * mid-upload sees half a plugin. This keeps checking until the database agrees
 * with what it meant to write, the shape alt_ensure_contact_page_once() and
 * alt_sync_secondary_page_titles() already use for the same reason.
 *
 * IT SHARES THE MENU WITH THE SIBLING TRACKER, AND THAT IS WHY THE LOCK IS
 * NOT NAMED AFTER THIS PLUGIN. "Talent Intelligence Tracker" is the item next
 * to ours in the same wp_navigation post, and its plugin does exactly this on
 * the same `init`. Two plugins that each read the post, edit their own subtree
 * and write the whole post back will, on an unlucky interleave, drop the
 * other's children -- and each would have verified its own write and set its
 * own done-flag, so neither would ever retry. ALT_NAV_LOCK_OPTION is therefore
 * a deliberate cross-plugin convention: the same literal option name is used by
 * the talent tracker's tit_nav_submenu_sync(). add_option() is the lock because
 * wp_options.option_name is UNIQUE, so exactly one of two concurrent callers
 * gets true out of it; a transient is a cache read and races.
 */

if (!defined('ABSPATH')) exit;

/**
 * The cross-plugin lock. Both trackers write the same wp_navigation post, so
 * the name must NOT contain "alt". Changing it here without changing it in the
 * sibling plugin removes the only thing serialising the two writers.
 */
const ALT_NAV_LOCK_OPTION = 'atr_nav_children_lock';
const ALT_NAV_LOCK_TTL    = 60;      // seconds; a crashed run must not wedge it
const ALT_NAV_RETRY_EVERY = 300;     // seconds between attempts while unresolved

/** The tracker page this plugin owns, and whose menu item gains the children. */
function alt_nav_parent_path() {
    return 'ai-layoff-tracker';
}

/**
 * THE FOUR, IN THE ORDER A READER NEEDS THEM.
 *
 * Ordered by what somebody arriving cold has to answer, not by what exists:
 * how do you know this (methodology), where did it come from (sources), what
 * may I quote (press kit), what did the employers actually say (the quote
 * library, which is the evidence under this tracker's one editorial claim).
 *
 * TWO OF THE SIX SECONDARY PAGES ARE DELIBERATELY OUT.
 *
 *   ai-tracker-health   an operations dashboard. It was unlinked from the
 *                       public pages on purpose (2026-07-19) and is noindexed
 *                       by alt_page_should_be_noindex(); putting a "sources
 *                       degraded" screen in the site header would contradict
 *                       both decisions in the same session.
 *   publisher-tools     embed codes, for somebody who has already decided to
 *                       republish a chart. It is one click from the press kit,
 *                       which is where that reader already is.
 *
 * A submenu of six is a list to be read; a submenu of four is a route. If a
 * fifth ever earns a place, it earns it by displacing one of these.
 *
 * Each entry is a slug under the tracker page. The template and the shortcode
 * come from alt_secondary_pages(), which stays the single source of truth for
 * both -- this list may only name slugs that exist there, and
 * alt_nav_desired_children() enforces that rather than trusting it.
 */
function alt_nav_children() {
    return array('methodology', 'sources', 'press', 'ai-quotes');
}

/**
 * The children we intend the menu to carry, in order, each
 * array('url' => the canonical permalink, 'label' => the page's own <h1>).
 *
 * Returns an EMPTY array for "not ready", never a partial set: a half-built
 * submenu written to the live menu is worse than none, and the caller treats
 * empty as "try again on the next request". Not-ready means any one of: a
 * template whose <h1> cannot be read verbatim (mid-upload, or a heading that
 * grew markup), a page that does not exist yet, or a page that no longer
 * carries the shortcode that renders it.
 */
function alt_nav_desired_children() {
    if (!function_exists('alt_secondary_pages') || !function_exists('alt_template_heading')) return array();
    $secondary = alt_secondary_pages();
    $parent = alt_nav_parent_path();
    $out = array();

    foreach (alt_nav_children() as $slug) {
        $path = $parent . '/' . $slug;
        // Naming a slug alt_secondary_pages() does not carry is a bug in this
        // file, and it must not become a menu item pointing at nothing.
        if (!isset($secondary[$path])) return array();
        list($template, $shortcode) = $secondary[$path];

        $label = alt_template_heading($template);
        if ($label === '') return array();          // never a label from a guess

        $page = get_page_by_path($path, OBJECT, 'page');
        if (!$page) return array();                 // never a link to a 404
        // Ownership is the shortcode, never the slug on its own: a page the
        // owner repurposed at that path is not ours to advertise.
        if (!has_shortcode((string) $page->post_content, $shortcode)) return array();

        $out[] = array('url' => get_permalink($page), 'label' => $label);
    }
    return $out;
}

/** The desired set as normalised-url => label, which is what verification compares. */
function alt_nav_desired_map($desired) {
    $map = array();
    foreach ($desired as $child) {
        $map[alt_nav_normalize_url($child['url'])] = $child['label'];
    }
    return $map;
}

/**
 * One spelling for a URL, so "is this the same destination" is answerable.
 *
 * The menu stores absolute URLs typed by hand; get_permalink() returns the
 * canonical one. They differ by scheme, by host case and by trailing slash,
 * and a comparison that missed any of those would add a second item for a
 * destination already in the menu on every single deploy.
 */
function alt_nav_normalize_url($url) {
    $url = trim((string) $url);
    if ($url === '') return '';
    $url = preg_replace('#^https?://#i', '', $url);
    $url = preg_replace('#^www\.#i', '', $url);
    $url = rtrim($url, '/');
    return strtolower($url);
}

/** Our tracker page's own URL, normalised, or '' if the page is not there. */
function alt_nav_parent_url() {
    $page = get_page_by_path(alt_nav_parent_path(), OBJECT, 'page');
    return $page ? alt_nav_normalize_url(get_permalink($page)) : '';
}

/**
 * Is this block a top-level menu entry pointing at $url?
 *
 * Both block names are accepted because the item may already have been
 * converted by a previous run (navigation-submenu) or may still be flat
 * (navigation-link). That is what makes the second run a no-op.
 */
function alt_nav_block_points_at($block, $url) {
    $name = isset($block['blockName']) ? $block['blockName'] : '';
    if ($name !== 'core/navigation-link' && $name !== 'core/navigation-submenu') return false;
    $attrs = isset($block['attrs']) && is_array($block['attrs']) ? $block['attrs'] : array();
    if (!isset($attrs['url'])) return false;
    return alt_nav_normalize_url($attrs['url']) === $url;
}

/**
 * The child blocks our parent should end up with, given the ones it has.
 *
 * REBUILD OURS, KEEP THEIRS. Every existing child whose URL sits under the
 * tracker path is discarded and re-derived from $desired, which is what makes
 * a retired page's item disappear rather than linger. Every other child is
 * carried through untouched and in order, because the owner may have added one
 * and this plugin has no standing to decide about it.
 */
function alt_nav_rebuild_children($existing, $desired, $parent_url) {
    $kept = array();
    foreach ((array) $existing as $child) {
        $attrs = isset($child['attrs']) && is_array($child['attrs']) ? $child['attrs'] : array();
        $url = isset($attrs['url']) ? alt_nav_normalize_url($attrs['url']) : '';
        // Ours to manage: anything below the tracker page. Note the '/' so the
        // parent's own URL is not treated as one of its own children.
        if ($url !== '' && $parent_url !== '' && strpos($url, $parent_url . '/') === 0) continue;
        $kept[] = $child;
    }

    $mine = array();
    foreach ($desired as $child) {
        $mine[] = array(
            'blockName'    => 'core/navigation-link',
            'attrs'        => array(
                'label' => $child['label'],
                'type'  => 'custom',
                'kind'  => 'custom',
                'url'   => $child['url'],
            ),
            'innerBlocks'  => array(),
            'innerHTML'    => '',
            'innerContent' => array(),
        );
    }
    // Ours first: they are the reason the submenu exists, and an owner-added
    // item appended later stays where the owner put it relative to itself.
    return array_merge($mine, $kept);
}

/**
 * The parent block, converted to a submenu carrying $children.
 *
 * innerContent IS NOT DECORATION. serialize_block() walks innerContent and
 * substitutes the next innerBlock for each null it finds; it never reads
 * innerBlocks directly. A submenu handed innerContent => array() therefore
 * serialises with its children silently dropped, which is a menu item that
 * gained a toggle and lost everything behind it. One null per child.
 */
function alt_nav_as_submenu($block, $children) {
    $attrs = isset($block['attrs']) && is_array($block['attrs']) ? $block['attrs'] : array();
    unset($attrs['isTopLevelLink']);
    $attrs['isTopLevelItem'] = true;
    return array(
        'blockName'    => 'core/navigation-submenu',
        'attrs'        => $attrs,
        'innerBlocks'  => array_values($children),
        'innerHTML'    => '',
        'innerContent' => $children ? array_fill(0, count($children), null) : array(),
    );
}

/**
 * Walk $blocks, convert our parent item, and report whether anything changed.
 *
 * Recursive because a navigation block may wrap its items in a group, and the
 * tracker item could in principle already sit inside something. It stops at
 * the first match: one destination is offered once.
 *
 * $changed is by reference and is the ONLY signal the caller writes on. A run
 * that finds the item already correct returns the blocks untouched and
 * $changed false, which is the whole of the idempotence guarantee: the second
 * call performs no write at all.
 */
function alt_nav_apply(&$blocks, $parent_url, $desired, &$changed, &$found) {
    foreach ($blocks as $i => $block) {
        if (alt_nav_block_points_at($block, $parent_url)) {
            $found = true;
            $existing = isset($block['innerBlocks']) ? $block['innerBlocks'] : array();
            $children = alt_nav_rebuild_children($existing, $desired, $parent_url);
            $next = alt_nav_as_submenu($block, $children);
            if (serialize_blocks(array($next)) !== serialize_blocks(array($block))) {
                $blocks[$i] = $next;
                $changed = true;
            }
            return true;
        }
        if (!empty($block['innerBlocks'])) {
            $inner = $block['innerBlocks'];
            if (alt_nav_apply($inner, $parent_url, $desired, $changed, $found)) {
                $blocks[$i]['innerBlocks'] = $inner;
                return true;
            }
        }
    }
    return false;
}

/**
 * Take the cross-plugin lock, or report that somebody else holds it.
 *
 * add_option() is an INSERT against a UNIQUE column, so of two concurrent
 * callers exactly one gets true. A lock older than ALT_NAV_LOCK_TTL is a
 * crashed run, not a live one, and is cleared so this can never wedge the
 * sibling plugin permanently.
 */
function alt_nav_lock() {
    if (add_option(ALT_NAV_LOCK_OPTION, (string) time(), '', 'no')) return true;
    $held = (int) get_option(ALT_NAV_LOCK_OPTION, 0);
    if ($held && (time() - $held) > ALT_NAV_LOCK_TTL) {
        delete_option(ALT_NAV_LOCK_OPTION);
    }
    return false;
}

function alt_nav_unlock() {
    delete_option(ALT_NAV_LOCK_OPTION);
}

/**
 * Put the four children under the tracker's menu item, and keep them there.
 *
 * Verified means re-read from the database and re-derived, not "wp_update_post
 * did not return an error". The done-flag stores ALT_VERSION, so every deploy
 * re-checks -- which is what makes a renamed heading reach the menu.
 */
function alt_nav_submenu_sync() {
    if (get_option('alt_nav_submenu_synced') === ALT_VERSION) return;

    $last = (int) get_option('alt_nav_submenu_last_try', 0);
    if ($last && (time() - $last) < ALT_NAV_RETRY_EVERY) return;
    update_option('alt_nav_submenu_last_try', time(), false);

    $parent_url = alt_nav_parent_url();
    if ($parent_url === '') return;
    $desired = alt_nav_desired_children();
    if (!$desired) return;                      // not ready; never a partial menu

    if (!alt_nav_lock()) return;                // the sibling is writing; retry
    try {
        $menus = get_posts(array(
            'post_type'        => 'wp_navigation',
            'post_status'      => array('publish', 'draft'),
            'numberposts'      => 20,
            'suppress_filters' => false,
        ));
        $found_anywhere = false;

        foreach ($menus as $menu) {
            $blocks  = parse_blocks((string) $menu->post_content);
            $changed = false;
            $found   = false;
            alt_nav_apply($blocks, $parent_url, $desired, $changed, $found);
            if (!$found) continue;
            $found_anywhere = true;
            if (!$changed) continue;            // already right: no write at all

            wp_update_post(array(
                'ID'           => (int) $menu->ID,
                'post_content' => serialize_blocks($blocks),
            ));
        }

        // The parent is in no menu on this site. Nothing to do and nothing to
        // create: a menu we are not in is not a menu we may write to. Leave
        // the flag unset so a later menu edit is picked up.
        if (!$found_anywhere) return;

        if (alt_nav_verify($parent_url, $desired)) {
            update_option('alt_nav_submenu_synced', ALT_VERSION, false);
        }
    } finally {
        alt_nav_unlock();
    }
}
add_action('init', 'alt_nav_submenu_sync', 24);

/**
 * Re-read every menu and confirm our item is a submenu carrying exactly the
 * intended children in the intended order. A write that landed half way, or
 * that the sibling plugin overwrote between the write and here, fails this and
 * leaves the flag unset so the next request tries again.
 */
function alt_nav_verify($parent_url, $desired) {
    $menus = get_posts(array(
        'post_type'        => 'wp_navigation',
        'post_status'      => array('publish', 'draft'),
        'numberposts'      => 20,
        'suppress_filters' => false,
    ));
    $seen = false;
    foreach ($menus as $menu) {
        $blocks = parse_blocks((string) $menu->post_content);
        $item   = alt_nav_find($blocks, $parent_url);
        if ($item === null) continue;
        $seen = true;
        if ($item['blockName'] !== 'core/navigation-submenu') return false;
        $got = array();
        foreach ((array) $item['innerBlocks'] as $child) {
            $attrs = isset($child['attrs']) && is_array($child['attrs']) ? $child['attrs'] : array();
            $url = isset($attrs['url']) ? alt_nav_normalize_url($attrs['url']) : '';
            if ($url !== '' && strpos($url, $parent_url . '/') === 0) {
                $got[$url] = isset($attrs['label']) ? $attrs['label'] : '';
            }
        }
        if ($got !== alt_nav_desired_map($desired)) return false;
    }
    return $seen;
}

/** The block for $url, or null. Shares alt_nav_block_points_at's matching. */
function alt_nav_find($blocks, $url) {
    foreach ($blocks as $block) {
        if (alt_nav_block_points_at($block, $url)) return $block;
        if (!empty($block['innerBlocks'])) {
            $hit = alt_nav_find($block['innerBlocks'], $url);
            if ($hit !== null) return $hit;
        }
    }
    return null;
}
