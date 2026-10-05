<?php
/**
 * Duplicate featured image on blog posts (2026-10-05).
 *
 * The theme renders a post's featured image above the title. Posts published
 * with that same image ALSO inserted as the first image block of post_content
 * showed it twice (~122 posts). Two halves:
 *
 *   1. RENDER: on a single post, the_content drops the first block whose <img>
 *      is the featured attachment, so a post published that way in future can
 *      no longer show the image twice, whatever tool wrote it.
 *   2. CLEANUP: keyed GET/POST layoffs/v1/blog-dup-images lists (and with
 *      apply=1 rewrites) stored posts, driven by .github/workflows/
 *      blog-dup-images.yml with dry_run defaulting to true.
 *
 * A post is touched ONLY when an image matches its featured image (same
 * attachment id via wp-image-ID / "id":ID, or the same uploaded file in any
 * size variant). Tests: railway/tests/test_blog_dup_images.py.
 */
if (!defined('ABSPATH')) exit;

/** Upload path with host, query, -WxH and -scaled suffixes removed. */
function alt_dup_image_norm_url($url) {
    $path = (string) parse_url(html_entity_decode((string) $url), PHP_URL_PATH);
    if ($path === '') return '';
    $path = preg_replace('~-(\d+x\d+|scaled)(?=\.[a-z0-9]+$)~i', '', $path);
    $path = preg_replace('~-(\d+x\d+|scaled)(?=\.[a-z0-9]+$)~i', '', $path);
    $pos = strpos($path, '/wp-content/uploads/');
    return strtolower($pos === false ? $path : substr($path, $pos));
}

function alt_dup_image_img_matches($img, $thumb_id, $thumb_norm) {
    $thumb_id = (int) $thumb_id;
    if ($thumb_id > 0 && preg_match('~\bwp-image-' . $thumb_id . '\b~', $img)) return true;
    if ($thumb_norm !== '' && preg_match('~\ssrc\s*=\s*["\']([^"\']+)~i', $img, $m)) {
        return alt_dup_image_norm_url($m[1]) === $thumb_norm;
    }
    return false;
}

/** [start, length] of the first block duplicating the featured image, or null. */
function alt_dup_image_find($content, $thumb_id, $thumb_url) {
    $content = (string) $content;
    $thumb_norm = alt_dup_image_norm_url($thumb_url);
    if ((int) $thumb_id <= 0 && $thumb_norm === '') return null;
    if (!preg_match_all('~<img\b[^>]*>~i', $content, $all, PREG_OFFSET_CAPTURE)) return null;
    foreach ($all[0] as $hit) {
        list($img, $off) = $hit;
        if (!alt_dup_image_img_matches($img, $thumb_id, $thumb_norm)) continue;
        $end = $off + strlen($img);
        $before = substr($content, 0, $off);
        // 1. Gutenberg image block around it.
        $bs = strrpos($before, '<!-- wp:image');
        if ($bs !== false && strpos(substr($content, $bs, $off - $bs), '<!-- /wp:image -->') === false) {
            $close = strpos($content, '<!-- /wp:image -->', $end);
            if ($close !== false) return alt_dup_image_span($content, $bs, $close + strlen('<!-- /wp:image -->'));
        }
        // 2. <figure> around it.
        $fs = strripos($before, '<figure');
        if ($fs !== false && stripos(substr($content, $fs, $off - $fs), '</figure>') === false) {
            $close = stripos($content, '</figure>', $end);
            if ($close !== false) return alt_dup_image_span($content, $fs, $close + 9);
        }
        // 3. Optional <a> and <p> wrappers holding nothing else.
        $s = $off; $e = $end;
        if (preg_match('~<a\b[^>]*>\s*$~i', substr($content, 0, $s), $m) && preg_match('~^\s*</a>~i', substr($content, $e), $n)) {
            $s -= strlen($m[0]); $e += strlen($n[0]);
        }
        if (preg_match('~<p\b[^>]*>\s*$~i', substr($content, 0, $s), $m) && preg_match('~^\s*</p>~i', substr($content, $e), $n)) {
            $s -= strlen($m[0]); $e += strlen($n[0]);
        }
        return alt_dup_image_span($content, $s, $e);
    }
    return null;
}

/** Span plus the blank lines that followed it, so no empty gap is left. */
function alt_dup_image_span($content, $s, $e) {
    if (preg_match('~^\s*~', substr($content, $e), $ws)) $e += strlen($ws[0]);
    return array($s, $e - $s);
}

function alt_dup_image_strip($content, $thumb_id, $thumb_url) {
    $span = alt_dup_image_find($content, $thumb_id, $thumb_url);
    if ($span === null) return (string) $content;
    return substr((string) $content, 0, $span[0]) . substr((string) $content, $span[0] + $span[1]);
}

function alt_dup_image_thumb($post_id) {
    $tid = (int) get_post_thumbnail_id($post_id);
    return array($tid, $tid > 0 ? (string) wp_get_attachment_url($tid) : '');
}

// RENDER: priority 1, before do_blocks (9) parses the raw markup.
add_filter('the_content', function ($content) {
    if (!function_exists('is_singular') || !is_singular('post') || !in_the_loop() || !is_main_query()) return $content;
    list($tid, $url) = alt_dup_image_thumb(get_the_ID());
    return $tid > 0 ? alt_dup_image_strip($content, $tid, $url) : $content;
}, 1);

// CLEANUP route.
add_action('rest_api_init', function () {
    if (!function_exists('alt_api_permission')) return;
    register_rest_route('layoffs/v1', '/blog-dup-images', array(
        'methods'             => array('GET', 'POST'),
        'permission_callback' => 'alt_api_permission',
        'callback'            => 'alt_dup_images_route',
    ));
});

function alt_dup_images_route($request) {
    $apply = (string) $request->get_param('apply') === '1' && $request->get_method() === 'POST';
    $ids = get_posts(array(
        'post_type' => 'post', 'post_status' => 'publish', 'numberposts' => -1,
        'fields' => 'ids', 'meta_key' => '_thumbnail_id', 'suppress_filters' => true,
    ));
    $found = array(); $fixed = array();
    foreach ($ids as $pid) {
        list($tid, $url) = alt_dup_image_thumb($pid);
        if ($tid <= 0) continue;
        $raw = (string) get_post_field('post_content', $pid, 'raw');
        $span = alt_dup_image_find($raw, $tid, $url);
        if ($span === null) continue;
        $found[] = array('id' => (int) $pid, 'thumb' => $tid,
                         'removed' => substr(substr($raw, $span[0], $span[1]), 0, 300));
        if ($apply) {
            $new = substr($raw, 0, $span[0]) . substr($raw, $span[0] + $span[1]);
            $r = wp_update_post(wp_slash(array('ID' => $pid, 'post_content' => $new)), true);
            if (!is_wp_error($r)) $fixed[] = (int) $pid;
        }
    }
    return rest_ensure_response(array('scanned' => count($ids), 'count' => count($found),
        'posts' => $found, 'applied' => $apply, 'fixed' => $fixed));
}
