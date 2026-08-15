<?php
/**
 * THE BLOG'S READING SURFACE, SHIPPED FROM A TRACKER-NAMED PLUGIN.
 *
 * Say the awkward part out loud: this is the AI Layoff Tracker plugin styling
 * asktherecruiter.com's ARTICLES, which is not where this belongs. It is here
 * because the plugin's FTPS deploy is the only write channel this project has
 * to the site. There is no wp-admin access from a session, so a child theme
 * and Additional CSS - both of which are the correct home for this - can only
 * be created by a human in the dashboard. See docs/RUNBOOK.md, "the blog
 * reading surface", for the exact steps to move it later. Everything here is
 * one stylesheet and one @font-face, so the move is a copy and a delete.
 *
 * SCOPE. is_singular('post') only. Every tracker surface is a `page` and every
 * entry is the `layoffs` CPT, so neither can match, and the stylesheet's own
 * selectors are all prefixed `body.single-post` as a second, independent gate.
 * Nothing here can reach the tracker, the health page or the sources page.
 *
 * THE FONT. Twenty Twenty-Five ships Vollkorn's variable roman and italic
 * inside the active theme, already on this origin. The theme does not REGISTER
 * them (theme.json declares only Manrope and Fira Code), so no @font-face for
 * them is emitted and nothing downloads them today. This declares the two
 * faces from the theme's own directory. No CDN is contacted, no new host is
 * introduced, and if a future theme does not carry the files the @font-face is
 * simply not emitted and the stylesheet's Charter/Georgia fallback stack takes
 * over cleanly - which is why the file_exists() check below is not optional.
 */

if (!defined('ABSPATH')) exit;

/**
 * The Vollkorn faces this theme happens to carry, relative to the theme root.
 * Roman first: if the italic is missing the roman still ships and the browser
 * synthesises an oblique, which is a worse italic but a working page. If the
 * ROMAN is missing there is no point declaring the family at all.
 */
function alt_blog_reading_font_faces() {
    return array(
        'normal' => 'assets/fonts/vollkorn/Vollkorn-VariableFont_wght.woff2',
        'italic' => 'assets/fonts/vollkorn/Vollkorn-Italic-VariableFont_wght.woff2',
    );
}

/**
 * Build the @font-face CSS, or '' when the active theme does not carry the
 * files. Returning '' is a real outcome, not a failure: the stylesheet names a
 * system-serif fallback for exactly this case.
 */
function alt_blog_reading_font_css() {
    $out = '';
    foreach (alt_blog_reading_font_faces() as $style => $rel) {
        $path = get_theme_file_path($rel);
        if (!$path || !file_exists($path)) {
            // No roman, no family: a declared family whose only file 404s
            // costs a request and still falls back, so skip the lot.
            if ($style === 'normal') return '';
            continue;
        }
        $out .= sprintf(
            "@font-face{font-family:Vollkorn;font-style:%s;font-weight:400 700;"
            . "font-display:swap;src:url('%s') format('woff2');}\n",
            $style,
            esc_url(get_theme_file_uri($rel))
        );
    }
    return $out;
}

/**
 * Enqueue on single posts only.
 *
 * Versioned by ALT_VERSION + file mtime for the same reason every other asset
 * here is: an FTPS deploy uploads the PHP before the CSS, and a request in
 * that window would otherwise let Autoptimize cache the OLD file body under
 * the NEW ver= key for the whole release (incident 2026-07-19).
 */
function alt_blog_reading_enqueue() {
    if (!is_singular('post')) return;

    $rel = 'assets/blog-reading.css';
    $mtime = @filemtime(ALT_PLUGIN_DIR . $rel);
    $ver = ALT_VERSION . ($mtime ? '.' . $mtime : '');

    wp_enqueue_style('alt-blog-reading', ALT_PLUGIN_URL . $rel, array(), $ver);

    $faces = alt_blog_reading_font_css();
    if ($faces !== '') {
        wp_add_inline_style('alt-blog-reading', $faces);
    }
}
// Priority 20: after the theme and after the site's own inline styles are
// registered, so ours is the later sheet when specificity ties.
add_action('wp_enqueue_scripts', 'alt_blog_reading_enqueue', 20);
