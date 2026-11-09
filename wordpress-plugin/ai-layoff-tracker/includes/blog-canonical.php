<?php
/**
 * Self-canonical for the blog posts index (/blog/ and /blog/page/N/).
 *
 * Live 2026-11-09 the SEO plugin served canonical ".../blog/blog/" (a 404) on
 * every page of the posts index, including ?utm_* and ?ref= variants. Google
 * drops a canonical that points at a 404 and picks its own, which Search
 * Console reports as "Duplicate without user-selected canonical". On the posts
 * index (on this install the static front page, page 36, slug "blog") we name the request path itself, minus any query string.
 */
if (!defined('ABSPATH')) { exit; }

function alt_blog_index_canonical($canonical) {
    if (!is_home() && !is_front_page()) { return $canonical; }
    $path = (string) parse_url(isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '/', PHP_URL_PATH);
    if ($path === '' || strpos($path, '..') !== false) { return $canonical; }
    $home = parse_url(home_url('/'));
    if (empty($home['host'])) { return $canonical; }
    $scheme = isset($home['scheme']) ? $home['scheme'] : 'https';
    return $scheme . '://' . $home['host'] . rtrim($path, '/') . '/';
}
add_filter('wpseo_canonical', 'alt_blog_index_canonical', 20);
add_filter('rank_math/frontend/canonical', 'alt_blog_index_canonical', 20);
