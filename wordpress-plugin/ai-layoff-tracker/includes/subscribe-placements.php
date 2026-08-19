<?php
/**
 * WHERE OUR OWN SIGNUP RENDERS, BEYOND THE TWO TRACKER PAGES.
 *
 * The signup itself lives in includes/subscribe.php and is not duplicated
 * here: this file decides only WHICH surfaces call it, and calls it once each.
 * There is one form, one table, one route and one double opt-in flow, and this
 * file adds none of those.
 *
 * THE PROBLEM IT ANSWERS. alt_digest_subscribe_form() rendered on the layoff
 * tracker page and on the sibling talent tracker page, and nowhere else. Those
 * are two URLs. The plugin also renders the company profile pages, the
 * country/state/industry pages and the layoff entry permalinks, which is where
 * search actually lands people, and the site publishes articles that the
 * plugin styles (includes/blog-typography.php) and never offered anything on.
 *
 * THE FOUR SURFACES, and why each one and not another:
 *
 *   post     single blog posts, appended to the article by the_content. Gated
 *            exactly as includes/blog-typography.php gates its stylesheet, on
 *            is_singular('post'), so the two cannot disagree about what an
 *            article is.
 *   company  /company-layoffs/<slug>/, one employer's assembled history.
 *   facet    /country-layoffs/, /state-layoffs/, /industry-layoffs/.
 *   entry    the layoffs CPT permalink, one row with its sources.
 *
 * DELIBERATELY NOT ADDED: the methodology, sources, health, press, report,
 * dashboard and quarterly pages. Those are tracker sub-pages reached from the
 * tracker, which already carries the signup and a hero button pointing at it,
 * and a signup on every page of one site section is the pattern this project
 * would call spam if a competitor shipped it.
 *
 * ONE PLACEMENT PER PAGE. A request renders one of these surfaces, never two,
 * so the counter below is a backstop rather than the mechanism: the real
 * separation is that a blog post is not a plugin template and a plugin
 * template is not a blog post. What the counter actually catches is
 * the_content firing more than once for one article, which WordPress does
 * routinely (SEO description passes, excerpt generation, some wp_head work).
 * That is the same multiple-render behaviour that makes a function defined in
 * a template a fatal error, seen here as a form that would otherwise print
 * twice, with two identical id="alt-digest" anchors.
 *
 * THE THIRD-PARTY SIGNUP IS NOT TOUCHED. Blog posts currently also carry
 * div.atr-capture, a cross-origin Mailjet iframe injected from WordPress (a
 * WPCode snippet), which the owner is retiring by hand in wp-admin. It is not
 * in this repository, its contents are cross-origin and unreachable, and
 * nothing here styles it, hides it, waits for it or depends on it. Until the
 * owner deletes it both boxes are on the page, so this block is built to read
 * correctly as the second of two signups and not only as the only one.
 */

if (!defined('ABSPATH')) exit;

/**
 * The contexts this file places, in the order a reader is most likely to meet
 * them. Read by the tests, so the list cannot drift from what ships.
 */
function alt_digest_placement_contexts() {
    return array('post', 'company', 'facet', 'entry', 'editions');
}

/**
 * Render the signup for one surface, at most once per request.
 *
 * Returns '' when the signup is unavailable (an FTPS deploy can land this file
 * before includes/subscribe.php, and a hard call would fatal the page) and ''
 * when something already placed it. Both are real outcomes, and both are
 * silence rather than a broken page.
 */
function alt_digest_placement($context) {
    static $placed = false;
    if ($placed) return '';
    if (!function_exists('alt_digest_subscribe_form')) return '';
    if (!in_array($context, alt_digest_placement_contexts(), true)) return '';
    $placed = true;
    return alt_digest_subscribe_form($context);
}

/**
 * Append the signup to the end of a single blog post.
 *
 * Priority 25: after wpautop (10) and after the site's own content filters, so
 * this markup is appended as finished HTML and never fed through a paragraph
 * wrapper that would break the form open.
 *
 * The three gates are not belt and braces, they are three different things.
 * is_singular('post') is the surface. is_main_query() plus in_the_loop() is
 * "this is the article, not a related-posts widget rendering the same content
 * again". The excerpt check is the one that actually bites: get_the_excerpt()
 * runs the_content filters to build a summary, and an SEO plugin does that
 * during wp_head, which is BEFORE the article renders. Without it the static
 * in alt_digest_placement() would be spent on a meta description nobody sees
 * and the reader would get no form at all.
 */
function alt_digest_append_to_post($content) {
    if (is_admin() || is_feed() || is_embed()) return $content;
    if (doing_filter('get_the_excerpt')) return $content;
    if (!is_singular('post')) return $content;
    if (!in_the_loop() || !is_main_query()) return $content;
    return $content . alt_digest_placement('post');
}
add_filter('the_content', 'alt_digest_append_to_post', 25);
