<?php
/**
 * Reference data: official statistics stored as labelled MACRO CONTEXT.
 *
 *   GET  /layoffs/v1/reference/<source>          public, the stored document
 *   POST /layoffs/v1/reference-ingest/<source>   keyed, replaces it wholesale
 *
 * Same pattern as /claims + /claims-ingest (db.php): one non-autoloaded option
 * per source, written by a scheduled collector in railway/ and never read by
 * the layoff table, ingest or event classification. These figures are survey
 * estimates from all causes; they are never summed into tracker counts.
 *
 * A source must be named in alt_reference_sources() to be stored, so the
 * endpoint cannot be turned into a general-purpose key/value store.
 */
if (!defined('ABSPATH')) exit;

/** Allowed source ids => option name. Add a source here with its collector. */
function alt_reference_sources() {
    return array(
        'bls_jolts_cps' => 'alt_ref_bls_jolts_cps',
        'oecd_unemployment' => 'alt_ref_oecd_unemployment',
    );
}

/** Largest document accepted, in bytes of JSON (the BLS pull is ~200 KB). */
if (!defined('ALT_REFERENCE_MAX_BYTES')) define('ALT_REFERENCE_MAX_BYTES', 3 * 1024 * 1024);

add_action('rest_api_init', function () {
    $ids = implode('|', array_map('preg_quote', array_keys(alt_reference_sources())));
    register_rest_route('layoffs/v1', '/reference/(?P<source>' . $ids . ')', array(
        'methods'  => 'GET',
        'callback' => 'alt_api_reference_get',
        'permission_callback' => '__return_true',
    ));
    register_rest_route('layoffs/v1', '/reference-ingest/(?P<source>' . $ids . ')', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_reference_ingest',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
});

function alt_api_reference_get(WP_REST_Request $r) {
    $map = alt_reference_sources();
    $src = (string) $r['source'];
    if (!isset($map[$src])) return new WP_Error('alt_not_found', 'Unknown reference source.', array('status' => 404));
    $data = get_option($map[$src], array());
    return rest_ensure_response(is_array($data) ? $data : array());
}

function alt_api_reference_ingest(WP_REST_Request $r) {
    $map = alt_reference_sources();
    $src = (string) $r['source'];
    if (!isset($map[$src])) return new WP_Error('alt_not_found', 'Unknown reference source.', array('status' => 404));
    if (strlen((string) $r->get_body()) > ALT_REFERENCE_MAX_BYTES) {
        return new WP_Error('alt_too_large', 'Reference document too large.', array('status' => 413));
    }
    $body = $r->get_json_params();
    if (!is_array($body) || ($body['source'] ?? '') !== $src || empty($body['datasets'])
        || !is_array($body['datasets']) || empty($body['rows']) || empty($body['attribution'])) {
        return new WP_Error('alt_bad_request', 'Expected a reference payload with source, datasets, rows and attribution.', array('status' => 400));
    }
    update_option($map[$src], $body, false);
    return rest_ensure_response(array(
        'stored'  => true,
        'source'  => $src,
        'updated' => isset($body['updated']) ? $body['updated'] : gmdate('c'),
        'rows'    => (int) $body['rows'],
        'latest'  => isset($body['latest']) ? $body['latest'] : null,
    ));
}
