<?php
/**
 * "OPEN ROLES NOW" IN THE TALENT DIGEST (owner ruling 2026-11-13, "yes,
 * employer links"; within 2026-11-12, no public job listings).
 *
 * The section is COMPOSED BY THE TALENT PLUGIN, in-process, the same way
 * talent follows are: tit_open_roles_email_section() in
 * talent-intelligence-tracker/includes/open_roles.php. This file only:
 *   - asks it per recipient with that reader's country and topic, and
 *   - owns those two preferences (columns talent_country, talent_family).
 * When the talent plugin is absent, or its daily copy is over 30h old, the
 * section is simply not there.
 *
 * ROLE LINKS ARE NEVER CLICK-TRACKED. They go straight to the employer's own
 * Greenhouse, Lever or Ashby posting; only the "See all matches for your CV"
 * button goes through alt_digest_track_link. A tracking redirect on a role
 * would route the reader through our site, which the ruling forbids.
 *
 * Talent-list readers only, daily and weekly only, appended after their
 * consented sections by both senders (subscribe.php and the relay), exactly
 * like talent_follow_section. Never a reason to send on its own.
 */
if (!defined('ABSPATH')) exit;

/** ISO2 or '' (everywhere). */
function alt_open_roles_country($row) {
    $c = strtoupper(trim((string) ($row['talent_country'] ?? '')));
    return preg_match('/^[A-Z]{2}$/', $c) ? $c : '';
}

/** Role family slug or '' (all topics). */
function alt_open_roles_family($row) {
    $f = strtolower(trim((string) ($row['talent_family'] ?? '')));
    return preg_match('/^[a-z_]{2,40}$/', $f) ? $f : '';
}

/**
 * The per-recipient section: array('html', 'text') or null.
 * $freq is the tier being sent; monthly gets none (the ruling names daily and weekly).
 */
function alt_open_roles_section_for($row, $freq, $send_id = 0) {
    $freq = strtolower(trim((string) $freq));
    if ($freq !== 'daily' && $freq !== 'weekly') return null;
    if (!function_exists('tit_open_roles_email_section')) return null;
    $send_id = (int) $send_id;
    $link = function ($u) use ($send_id) {
        return function_exists('alt_digest_track_link') ? alt_digest_track_link($send_id, $u) : $u;
    };
    $s = tit_open_roles_email_section($freq, array(
        'country' => alt_open_roles_country($row),
        'family'  => alt_open_roles_family($row),
        'link'    => $link,
    ));
    if (!is_array($s) || trim((string) ($s['html'] ?? '')) === '' || trim((string) ($s['text'] ?? '')) === '') return null;
    return array('html' => (string) $s['html'], 'text' => (string) $s['text']);
}

/** The settings fieldset: '' when the talent plugin has no current choices. */
function alt_open_roles_prefs_fieldset($row) {
    if (!function_exists('tit_open_roles_choices')) return '';
    $c = tit_open_roles_choices();
    if (empty($c['countries']) && empty($c['families'])) return '';
    $cur_c = alt_open_roles_country($row);
    $cur_f = alt_open_roles_family($row);
    $html = '<fieldset><legend>Open roles in the talent email</legend>'
          . '<p class="note">Choose where and what. Leave both on "All" to see everything.</p>'
          . '<label for="alt_talent_country">Country</label> '
          . '<select id="alt_talent_country" name="alt_talent_country"><option value="">All countries</option>';
    foreach ((array) $c['countries'] as $code => $name) {
        $html .= '<option value="' . esc_attr($code) . '"' . ($cur_c === $code ? ' selected' : '') . '>' . esc_html($name) . '</option>';
    }
    $html .= '</select> <label for="alt_talent_family">Topic</label> '
           . '<select id="alt_talent_family" name="alt_talent_family"><option value="">All topics</option>';
    foreach ((array) $c['families'] as $slug => $label) {
        $html .= '<option value="' . esc_attr($slug) . '"' . ($cur_f === $slug ? ' selected' : '') . '>' . esc_html($label) . '</option>';
    }
    return $html . '</select></fieldset>';
}

/**
 * The two values to save from a posted settings form, or null when the form
 * did not carry them. A value outside the current choices saves as '' (All):
 * the choice narrows mail, so no confirmation click is needed.
 */
function alt_open_roles_prefs_from_post($post) {
    if (!array_key_exists('alt_talent_country', $post) && !array_key_exists('alt_talent_family', $post)) return null;
    $c = function_exists('tit_open_roles_choices') ? tit_open_roles_choices() : array('countries' => array(), 'families' => array());
    $country = alt_open_roles_country(array('talent_country' => (string) ($post['alt_talent_country'] ?? '')));
    $family = alt_open_roles_family(array('talent_family' => (string) ($post['alt_talent_family'] ?? '')));
    if ($country !== '' && !isset($c['countries'][$country])) $country = '';
    if ($family !== '' && !isset($c['families'][$family])) $family = '';
    return array('talent_country' => $country === '' ? null : $country,
                 'talent_family' => $family === '' ? null : $family);
}
