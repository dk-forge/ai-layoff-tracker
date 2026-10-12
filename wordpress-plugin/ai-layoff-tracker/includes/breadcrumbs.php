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
    echo alt_breadcrumbs_html($trail);
}

/* ------------------------------------------------------------------ */
/* Ordinary blog posts, pages and archives                             */
/* ------------------------------------------------------------------ */

function alt_breadcrumbs_is_plugin_route() {
    foreach (array('alt_facet_is_request', 'alt_company_directory_is_request', 'alt_company_index_is_request') as $f) {
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
    static $done = false;
    if ($done || is_admin() || is_front_page() || is_home() || alt_breadcrumbs_is_plugin_route()) return $content;
    $name = $block['blockName'] ?? '';
    $want = (is_singular() && $name === 'core/post-title')
         || ((is_category() || is_tag() || is_tax()) && $name === 'core/query-title');
    if (!$want) return $content;
    if ($name === 'core/post-title' && (int) get_the_ID() !== (int) get_queried_object_id()) return $content;
    $bc = alt_breadcrumbs_blog_html();
    if ($bc === '') return $content;
    $done = true;
    return $bc . $content;
}
add_filter('render_block', 'alt_breadcrumbs_render_block', 10, 2);
