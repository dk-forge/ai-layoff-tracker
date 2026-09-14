<?php
/**
 * Country coverage tiers for the country pages, read from a generated file.
 *
 * data/country-coverage.json is written by railway/generate_country_tiers.py
 * from the committed disclosure-regime register (country_coverage.REGISTER),
 * the collectors' own scopes (ERM, EDGAR, the per-employer registers, the
 * GDELT allowlist, the local-language markets, the regional and national
 * feeds) and the committed recall and national-denominator measurements. The
 * tier is derived there by one documented rule; nothing here assigns one.
 *
 * The live half is the source-health ledger: the newest 'ok' completion among
 * the collectors that serve the country is the page's "last successful
 * collection". An absent file, an absent country or an absent ledger row each
 * render as absence, never as a default a reader could mistake for a fact.
 */
if (!defined('ABSPATH')) exit;

/** The whole generated file, or null when missing or malformed. */
function alt_country_coverage_data() {
    static $memo = false;
    if ($memo !== false) return $memo;
    $memo = null;
    $path = ALT_PLUGIN_DIR . 'data/country-coverage.json';
    if (!is_readable($path)) return null;
    $j = json_decode((string) file_get_contents($path), true);
    if (!is_array($j) || empty($j['countries']) || !is_array($j['countries'])) return null;
    $memo = $j;
    return $memo;
}

/**
 * One country's coverage row, by the display name a facet page carries.
 * Stored spellings that the register folds into one entry (its `aliases`)
 * resolve to that entry. Null when the country is not in the file.
 */
function alt_country_coverage($display) {
    $data = alt_country_coverage_data();
    if (!$data) return null;
    $name = trim((string) $display);
    if ($name === '') return null;
    if (isset($data['aliases'][$name])) $name = (string) $data['aliases'][$name];
    if (!isset($data['countries'][$name]) || !is_array($data['countries'][$name])) return null;
    $row = $data['countries'][$name];
    $row['name'] = $name;
    $row['gdelt_index_note'] = (string) ($data['gdelt_index_note'] ?? '');
    $row['tier_labels'] = isset($data['tier_labels']) && is_array($data['tier_labels']) ? $data['tier_labels'] : array();
    return $row;
}

/**
 * The newest 'ok' completion among the collectors serving a country, from the
 * masked health ledger. '' when none of them has completed a run.
 */
function alt_country_coverage_last_ok($row) {
    if (!function_exists('alt_source_health_masked')) return '';
    $health = alt_source_health_masked();
    $best = '';
    foreach ((array) ($row['health_ids'] ?? array()) as $id) {
        if (!isset($health[$id]) || !is_array($health[$id])) continue;
        if (($health[$id]['status'] ?? '') !== 'ok') continue;
        $at = (string) ($health[$id]['checked_at'] ?? '');
        if ($at !== '' && ($best === '' || strcmp($at, $best) > 0)) $best = $at;
    }
    return $best;
}

/** Reader-facing definition of each tier, keyed by tier number. */
function alt_country_coverage_tier_definitions() {
    return array(
        1 => 'an official body publishes an employer-level dataset that we read straight into the tracker',
        2 => 'an official body publishes collective-dismissal figures we can compare against, but no employer-level register we can ingest',
        3 => 'nothing official is published in a countable form, so every entry rests on a filing or a named report',
        4 => 'the country is in our news-scan scope but no disclosure regime has been classified for it',
    );
}

/** A percentage string from a 0..1 share, or '' when the share is not a number. */
function alt_country_coverage_pct($share) {
    if ($share === null || $share === '' || !is_numeric($share)) return '';
    return number_format(100 * (float) $share, 1) . '%';
}
