<?php
/**
 * The postal address every email footer prints, from ONE config value
 * (includes/postal-address.json; owner review 2026-11-11). Callers never
 * hard-code an address.
 */

if (!function_exists("alt_mail_postal_address")) {
function alt_mail_postal_address_config() {
    static $cfg = null;
    if ($cfg !== null) return $cfg;
    $raw = @file_get_contents(__DIR__ . '/postal-address.json');
    $cfg = is_string($raw) ? (array) json_decode($raw, true) : array();
    return $cfg;
}

/** "AskTheRecruiter, <street>, <locality>." with empty parts left out. */
function alt_mail_postal_address() {
    $c = alt_mail_postal_address_config();
    $parts = array();
    foreach (array('name', 'street', 'locality') as $k) {
        $v = trim((string) ($c[$k] ?? ''));
        if ($v !== '') $parts[] = $v;
    }
    if (!$parts) $parts = array('AskTheRecruiter');
    return implode(', ', $parts) . '.';
}
}
