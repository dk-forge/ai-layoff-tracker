<?php
/**
 * Visible breadcrumb trails (owner request 2026-10-12).
 *
 * ONE trail per page, and both the visible <nav> and the BreadcrumbList
 * JSON-LD are drawn from it, so what a reader sees and what Google reads can
 * never disagree. A trail is a list of array('name' => .., 'url' => ..); the
 * last item is the current page and renders as plain text.
 *
 * Every ancestor URL must be a page that exists. There is no /state-layoffs/,
 * /country-layoffs/ or /industry-layoffs/ index (all 404 on 2026-10-12), so
 * those sections link to the nearest real hub instead: the US WARN registry
 * for states, the tracker for countries and industries. Before 2.20.237 the
 * JSON-LD pointed the section crumb at the page's own URL.
 *
 * Ordinary blog posts, pages and archives are Rank Math's: its BreadcrumbList
 * is already in its @graph, so for those we print only its visible trail (or,
 * if its breadcrumb setting is off, our own from WP data) and never a second
 * JSON-LD block. Plugin routes keep their own trail and skip Rank Math's.
 */
if (!defined('ABSPATH')) exit;

/** Root of every tracker trail. */
function alt_breadcrumbs_root() {
    return array(
        array('name' => 'Blog', 'url' => home_url('/')),
        array('name' => 'AI Layoff Tracker', 'url' => home_url('/ai-layoff-tracker/')),
    );
}

/** Facet page trail: Blog > AI Layoff Tracker > Section > Page. */
function alt_breadcrumbs_facet_trail($data, $heading) {
    $sections = array(
        'state'    => array('US states', home_url('/ai-layoff-tracker/us-warn-registry/')),
        'country'  => array('Countries', home_url('/ai-layoff-tracker/')),
        'industry' => array('Industries', home_url('/ai-layoff-tracker/')),
    );
    $s = $sections[$data['dim']] ?? $sections['industry'];
    return array_merge(alt_breadcrumbs_root(), array(
        array('name' => $s[0], 'url' => $s[1]),
        array('name' => (string) $heading, 'url' => (string) $data['url']),
    ));
}

/** Company page trail: Blog > AI Layoff Tracker > Companies > Acme layoffs. */
function alt_breadcrumbs_company_trail($name, $url) {
    return array_merge(alt_breadcrumbs_root(), array(
        array('name' => 'Companies', 'url' => home_url('/company-layoffs/')),
        array('name' => (string) $name, 'url' => (string) $url),
    ));
}

/** The visible trail. Pure: no WP state read. */
function alt_breadcrumbs_html($trail) {
    $trail = array_values((array) $trail);
    $n = count($trail);
    if ($n < 2) return '';
    $out = '<nav class="alt-breadcrumbs" aria-label="Breadcrumb"><ol>';
    foreach ($trail as $i => $c) {
        $out .= '<li>';
        if ($i > 0) $out .= '<span class="alt-bc-sep" aria-hidden="true">&#8250;</span>';
        if ($i === $n - 1) {
            $out .= '<span aria-current="page">' . esc_html($c['name']) . '</span>';
        } else {
            $out .= '<a href="' . esc_url($c['url']) . '">' . esc_html($c['name']) . '</a>';
        }
        $out .= '</li>';
    }
    return $out . '</ol></nav>' . alt_breadcrumbs_style();
}

/** BreadcrumbList JSON-LD for the SAME trail. Pure. */
function alt_breadcrumbs_jsonld($trail) {
    $items = array();
    foreach (array_values((array) $trail) as $i => $c) {
        $items[] = array('@type' => 'ListItem', 'position' => $i + 1, 'name' => $c['name'], 'item' => $c['url']);
    }
    return '<script type="application/ld+json">' . wp_json_encode(array(
        '@context' => 'https://schema.org',
        '@type'    => 'BreadcrumbList',
        'itemListElement' => $items,
    ), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . "</script>\n";
}

/**
 * Inline, once per page, because the trail also renders on blog posts where
 * layoffs.css is not loaded. Colours are currentColor so contrast is the body
 * text's own in light and dark; wraps at any width, never scrolls sideways.
 */
function alt_breadcrumbs_style() {
    static $done = false;
    if ($done) return '';
    $done = true;
    return '<style id="alt-breadcrumbs-css">'
        . '.alt-breadcrumbs,.rank-math-breadcrumb{font-size:.875rem;line-height:1.5;margin:0 0 .75rem;max-width:100%;overflow-wrap:anywhere}'
        . '.alt-breadcrumbs ol{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:.125rem .25rem}'
        . '.alt-breadcrumbs li{display:inline;margin:0;padding:0;min-width:0}'
        . '.alt-breadcrumbs a,.rank-math-breadcrumb a{color:inherit;text-decoration:underline;text-underline-offset:2px}'
        . '.alt-bc-sep{margin-right:.25rem}.rank-math-breadcrumb p{margin:0}'
        . '</style>';
}

/** Print a trail (templates call this right after the page header). */
function alt_breadcrumbs_render($trail) {
    $html = alt_breadcrumbs_html($trail);
    if ($html !== '') alt_breadcrumbs_done(true);
    echo $html;
}

/** Has a visible trail been printed on this request? One flag, every path. */
function alt_breadcrumbs_done($set = false) {
    static $done = false;
    if ($set) $done = true;
    return $done;
}

/** Email archive: Blog > AI Layoff Tracker > Digest archive [> edition]. */
function alt_breadcrumbs_edition_trail($edition = null, $label = '') {
    $trail = array_merge(alt_breadcrumbs_root(), array(
        array('name' => 'Digest archive', 'url' => alt_edition_index_url()),
    ));
    if ($edition) {
        $trail[] = array('name' => (string) $label, 'url' => alt_edition_url($edition['freq'], $edition['slug']));
    }
    return $trail;
}

/** Single layoff entry: Blog > AI Layoff Tracker > Company. */
function alt_breadcrumbs_layoff_trail($name, $url) {
    return array_merge(alt_breadcrumbs_root(), array(array('name' => (string) $name, 'url' => (string) $url)));
}

/**
 * Put a trail at the top of rendered content: inside our own
 * <main class="alt-wrap ..."> when there is one (so it lines up with the
 * page), else before everything. Pure.
 */
function alt_breadcrumbs_insert($content, $bc) {
    if (preg_match('#<main\b[^>]*class="[^"]*\balt-wrap\b[^"]*"[^>]*>#', $content, $m, PREG_OFFSET_CAPTURE)) {
        $at = $m[0][1] + strlen($m[0][0]);
        return substr($content, 0, $at) . $bc . substr($content, $at);
    }
    return $bc . $content;
}

/** Remove a Rank Math trail an author pasted into a post body. Pure. */
function alt_breadcrumbs_strip_content_trail($content) {
    return preg_replace('#<nav\b[^>]*class="rank-math-breadcrumb"[^>]*>.*?</nav>#s', '', $content);
}

/**
 * Rank Math adds a one-item "Home" BreadcrumbList to every virtual route, so
 * a tracker page carried two lists that disagreed. Where we emit our own, drop
 * Rank Math's entity and the WebPage pointer to it. Pure.
 */
function alt_breadcrumbs_strip_rank_math($data, $ours) {
    if (!$ours || !is_array($data)) return $data;
    foreach ($data as $k => $entity) {
        if (!is_array($entity)) continue;
        if (($entity['@type'] ?? '') === 'BreadcrumbList') { unset($data[$k]); continue; }
        if (isset($entity['breadcrumb'])) unset($data[$k]['breadcrumb']);
    }
    return $data;
}

/* ------------------------------------------------------------------ */
/* Ordinary blog posts, pages and archives                             */
/* ------------------------------------------------------------------ */

function alt_breadcrumbs_is_plugin_route() {
    foreach (array('alt_facet_is_request', 'alt_company_directory_is_request', 'alt_company_index_is_request',
                   'alt_edition_is_index_request', 'alt_edition_is_single_request') as $f) {
        if (function_exists($f) && $f()) return true;
    }
    return is_singular('layoffs');
}

/** Rank Math's visible trail, or ours from WP data when its setting is off. */
function alt_breadcrumbs_blog_html() {
    if (function_exists('rank_math_get_breadcrumbs')) {
        $html = (string) rank_math_get_breadcrumbs();
        if (trim($html) !== '') {
            // Rank Math marks the current item <span class="last">; give it
            // aria-current so the trail reads the same as ours.
            $html = str_replace('<span class="last">', '<span class="last" aria-current="page">', $html);
            return $html . alt_breadcrumbs_style();
        }
    }
    $trail = array(array('name' => 'Blog', 'url' => home_url('/')));
    if (is_singular()) {
        $id = get_queried_object_id();
        if (get_post_type($id) === 'post') {
            $cats = get_the_category($id);
            if ($cats) $trail[] = array('name' => $cats[0]->name, 'url' => get_category_link($cats[0]->term_id));
        } else {
            foreach (array_reverse(get_post_ancestors($id)) as $a) {
                $trail[] = array('name' => get_the_title($a), 'url' => get_permalink($a));
            }
        }
        $trail[] = array('name' => wp_strip_all_tags(get_the_title($id)), 'url' => get_permalink($id));
    } elseif (is_category() || is_tag() || is_tax()) {
        $t = get_queried_object();
        $trail[] = array('name' => $t->name, 'url' => get_term_link($t));
    } elseif (is_author()) {
        $a = get_queried_object();
        $trail[] = array('name' => $a ? $a->display_name : 'Author', 'url' => $a ? get_author_posts_url($a->ID) : '');
    } elseif (is_search()) {
        $trail[] = array('name' => 'Search results for "' . get_search_query(false) . '"', 'url' => '');
    } elseif (is_404()) {
        $trail[] = array('name' => 'Page not found', 'url' => '');
    } elseif (is_archive()) {
        $trail[] = array('name' => wp_strip_all_tags(get_the_archive_title()), 'url' => '');
    } else {
        return '';
    }
    return alt_breadcrumbs_html($trail);
}

/**
 * Theme-agnostic placement for a block theme (twentytwentyfive): just before
 * the main post title on a single post/page, and before the archive title.
 * Once per request; never on the front page or plugin routes.
 */
function alt_breadcrumbs_render_block($content, $block) {
    if (alt_breadcrumbs_done() || is_admin() || is_front_page() || is_home() || alt_breadcrumbs_is_plugin_route()) return $content;
    $name = $block['blockName'] ?? '';
    $main = $name === 'core/group' && ($block['attrs']['tagName'] ?? '') === 'main';
    $want = (is_singular() && $name === 'core/post-title')
         || ((is_archive() || is_search()) && $name === 'core/query-title')
         || $main;
    if (!$want) return $content;
    if ($name === 'core/post-title' && (int) get_the_ID() !== (int) get_queried_object_id()) return $content;
    $bc = alt_breadcrumbs_blog_html();
    if ($bc === '') return $content;
    alt_breadcrumbs_done(true);
    if ($main) {
        // Last resort (404, or a template with no title block): first thing
        // inside <main>. Inner blocks render first, so this only fires when
        // nothing in the page printed a trail.
        $at = strpos($content, '<main');
        $end = $at === false ? false : strpos($content, '>', $at);
        return $end === false ? $bc . $content : substr($content, 0, $end + 1) . $bc . substr($content, $end + 1);
    }
    return $bc . $content;
}
add_filter('render_block', 'alt_breadcrumbs_render_block', 10, 2);

/**
 * Pages whose block template has no title (every shortcode page: sources,
 * methodology, ai-quotes, press, publisher tools, health, US WARN registry):
 * the trail goes inside the plugin's <main class="alt-wrap">, above its <h1>.
 * Runs after do_shortcode (11). Also removes a Rank Math trail pasted into a
 * post body once ours is on the page, so no page shows two.
 */
function alt_breadcrumbs_content_fallback($content) {
    if (is_admin() || is_feed() || !is_singular() || is_front_page() || alt_breadcrumbs_is_plugin_route()) return $content;
    if ((int) get_the_ID() !== (int) get_queried_object_id()) return $content;
    if (!alt_breadcrumbs_done()) {
        $bc = alt_breadcrumbs_blog_html();
        if ($bc === '') return $content;
        alt_breadcrumbs_done(true);
        return alt_breadcrumbs_insert(alt_breadcrumbs_strip_content_trail($content), $bc);
    }
    return alt_breadcrumbs_strip_content_trail($content);
}
add_filter('the_content', 'alt_breadcrumbs_content_fallback', 12);

/** Single entries and the email archive: JSON-LD for the trail they print. */
function alt_breadcrumbs_head() {
    if (is_singular('layoffs')) {
        $id = get_queried_object_id();
        echo alt_breadcrumbs_jsonld(alt_breadcrumbs_layoff_trail(alt_breadcrumbs_layoff_name($id), get_permalink($id)));
    } elseif (function_exists('alt_edition_is_index_request') && alt_edition_is_index_request()) {
        echo alt_breadcrumbs_jsonld(alt_breadcrumbs_edition_trail());
    } elseif (function_exists('alt_edition_is_single_request') && alt_edition_is_single_request()
              && ($ed = alt_edition_current())) {
        echo alt_breadcrumbs_jsonld(alt_breadcrumbs_edition_trail($ed, alt_edition_label($ed)));
    }
}
add_action('wp_head', 'alt_breadcrumbs_head', 21);

/** Name the single-entry template prints; one place, two callers. */
function alt_breadcrumbs_layoff_name($id) {
    $e = function_exists('alt_entry_to_array') ? (array) alt_entry_to_array($id) : array();
    return (string) ($e['company_name'] ?? '') !== '' ? (string) $e['company_name'] : wp_strip_all_tags(get_the_title($id));
}

function alt_breadcrumbs_rank_math_filter($data) {
    return alt_breadcrumbs_strip_rank_math($data, alt_breadcrumbs_is_plugin_route());
}
add_filter('rank_math/json_ld', 'alt_breadcrumbs_rank_math_filter', 99);
