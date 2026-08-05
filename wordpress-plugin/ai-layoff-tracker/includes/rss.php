<?php
/**
 * Custom RSS feed of the latest layoff entries.
 * Available at /feed/layoffs (pretty permalinks) or /?feed=layoffs.
 */

if (!defined('ABSPATH')) exit;

function alt_register_feed() {
    add_feed('layoffs', 'alt_render_rss_feed');
}
add_action('init', 'alt_register_feed');

/**
 * esc_xml() exists since WP 5.5; fall back for older installs.
 */
function alt_xml($value) {
    if (function_exists('esc_xml')) {
        return esc_xml((string) $value);
    }
    return htmlspecialchars((string) $value, ENT_XML1 | ENT_QUOTES, 'UTF-8');
}

function alt_render_rss_feed() {
    $query = new WP_Query(array(
        'post_type'      => 'layoffs',
        'post_status'    => 'publish',
        'posts_per_page' => 50,
        'orderby'        => 'date',
        'order'          => 'DESC',
        'no_found_rows'  => true,
    ));

    header('Content-Type: ' . feed_content_type('rss2') . '; charset=' . get_option('blog_charset'), true);

    echo '<?xml version="1.0" encoding="' . esc_attr(get_option('blog_charset')) . '"?>' . "\n";
    ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
    <title><?php echo alt_xml(get_bloginfo('name') . ': AI Layoff Tracker'); ?></title>
    <link><?php echo alt_xml(home_url('/ai-layoffs')); ?></link>
    <description>Layoffs we verified from SEC filings and trusted news outlets. Covers cuts the employer tied to AI, and all the others too.</description>
    <language><?php echo alt_xml(get_bloginfo('language')); ?></language>
    <lastBuildDate><?php echo alt_xml(gmdate('D, d M Y H:i:s +0000')); ?></lastBuildDate>
    <atom:link href="<?php echo alt_xml(home_url('/feed/layoffs')); ?>" rel="self" type="application/rss+xml" />
<?php foreach ($query->posts as $post) :
        $entry = alt_entry_to_array($post->ID);
        // esc_url_raw drops javascript:/data: schemes a manual meta edit could inject
        $link  = esc_url_raw($entry['source_url']);
        if ($link === '') {
            $link = get_permalink($post);
        }
        $description = sprintf(
            '%s: %s jobs (%s). %s',
            $entry['company_name'],
            number_format_i18n($entry['job_count']),
            $entry['layoff_date'] !== '' ? $entry['layoff_date'] : 'date unknown',
            $entry['excerpt']
        );
?>
    <item>
        <title><?php echo alt_xml(get_the_title($post)); ?></title>
        <link><?php echo alt_xml($link); ?></link>
        <guid isPermaLink="false"><?php echo alt_xml('alt-' . $post->ID . '-' . get_post_meta($post->ID, 'dedup_hash', true)); ?></guid>
        <pubDate><?php echo alt_xml(get_post_time('D, d M Y H:i:s +0000', true, $post)); ?></pubDate>
        <description><?php echo alt_xml($description); ?></description>
        <category><?php echo alt_xml($entry['verification_level']); ?></category>
<?php if ($entry['ai_explicit']) : ?>
        <category>ai_attributed</category>
<?php endif; ?>
    </item>
<?php endforeach; ?>
</channel>
</rss>
<?php
    exit;
}
