<?php
/**
 * Named author / about box + Person schema (owner scope 2026-09-24).
 *
 * TODO_OWNER_BIO: fill ALT_AUTHOR_PROFILE below with the owner's own name,
 * title, bio and profile links. Until 'name' AND 'bio' are both non-empty the
 * box and its Person JSON-LD are not rendered anywhere (no placeholder ever
 * reaches a live page). Rendered on the report, company, US state, methodology
 * and press pages. Runbook: docs/RUNBOOK_GROWTH.md, "Author box".
 */
if (!defined('ABSPATH')) exit;

if (!defined('ALT_AUTHOR_PROFILE')) {
    define('ALT_AUTHOR_PROFILE', array(
        'name'     => '',   // TODO_OWNER_BIO: full name as it should be cited
        'job_title' => '',  // TODO_OWNER_BIO: e.g. "Founder, AskTheRecruiter.com"
        'bio'      => '',   // TODO_OWNER_BIO: two or three plain sentences, no HTML
        'url'      => '',   // TODO_OWNER_BIO: an about page on asktherecruiter.com
        'same_as'  => array(), // TODO_OWNER_BIO: LinkedIn / other public profiles
    ));
}

/** Pure: the box + Person JSON-LD for a profile, or '' when it is not filled. */
function alt_author_box_html($p) {
    $name = trim((string) ($p['name'] ?? ''));
    $bio = trim((string) ($p['bio'] ?? ''));
    if ($name === '' || $bio === '') return '';
    $title = trim((string) ($p['job_title'] ?? ''));
    $url = trim((string) ($p['url'] ?? ''));
    $same = array_values(array_filter(array_map('strval', (array) ($p['same_as'] ?? array()))));
    $person = array('@context' => 'https://schema.org', '@type' => 'Person', 'name' => $name, 'description' => $bio);
    if ($title !== '') $person['jobTitle'] = $title;
    if ($url !== '') $person['url'] = $url;
    if ($same) $person['sameAs'] = $same;
    $person['worksFor'] = array('@type' => 'Organization', 'name' => 'AskTheRecruiter.com', 'url' => 'https://asktherecruiter.com');
    $head = $url !== '' ? '<a href="' . esc_url($url) . '">' . esc_html($name) . '</a>' : esc_html($name);
    return '<aside class="alt-author-box" aria-label="About the author">'
        . '<span class="alt-detail-h">About the author</span>'
        . '<p class="alt-author-name"><b>' . $head . '</b>' . ($title !== '' ? ', ' . esc_html($title) : '') . '</p>'
        . '<p class="alt-author-bio">' . esc_html($bio) . '</p></aside>'
        . '<script type="application/ld+json">' . wp_json_encode($person, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . '</script>';
}

/** What templates call. */
function alt_author_box() {
    return alt_author_box_html(ALT_AUTHOR_PROFILE);
}
