<?php
/**
 * Envelope encryption for the subscriber backup. PURE: no WordPress, no
 * globals, no database, no network. Include it from the route, or from a CLI
 * harness, and it behaves identically.
 *
 * WHY THIS FILE EXISTS SEPARATELY FROM subscriber-backup.php
 * ---------------------------------------------------------
 * "A restore path that has never been executed is a belief, not a backup." The
 * only way to prove the round trip is to run the REAL sealing code against a
 * throwaway key and decrypt the result. If the sealer lived inside the route
 * it could only be exercised against the live host, holding live personal
 * data, which is exactly the thing nobody should rehearse with. So the sealer
 * is a pure function of (plaintext, public key) and the drill runs it on
 * synthetic rows, offline, in CI, on every push.
 *
 * WHAT IT GUARANTEES
 * ------------------
 *   - The host writes a backup it cannot itself read. Sealing needs only the
 *     PUBLIC key, which is committed to this repository and deployed with the
 *     plugin. Opening it needs the PRIVATE key, which exists only on the
 *     owner's machine and is never on the host, never in this repository, and
 *     never in a runner.
 *   - No plaintext leaves this function. The caller gets a container of base64
 *     ciphertext and a wrapped key, and there is no branch that returns rows.
 *   - The container is AUTHENTICATED. Encrypt-then-MAC over a canonical string
 *     of every field a restore depends on, so a truncated or edited container
 *     fails loudly instead of decrypting to something plausible. CBC without a
 *     MAC is malleable, and a backup nobody can trust the integrity of is a
 *     backup nobody should restore from.
 *
 * WHY NOT age, AND WHY NOT GPG
 * ----------------------------
 * Both would be a binary this host does not have and this repository would
 * have to download into a runner holding two API keys. `openssl` is already in
 * PHP on the host, already on the owner's Mac, and already on the runner, so
 * the whole path adds no dependency and nothing for the hash-pinned lock to
 * vouch for. RSA-4096 + AES-256-CBC + HMAC-SHA256 is dull on purpose.
 *
 * THE OAEP DIGEST IS PINNED, NOT DEFAULTED. PHP's OPENSSL_PKCS1_OAEP_PADDING
 * is MGF1-SHA1 and the `openssl pkeyutl` CLI defaults the same way, but the
 * two defaults are not the same promise, and a version that moved one of them
 * would produce a container nobody could open with no error until the day it
 * was needed. The decrypt side names sha1 explicitly and the drill proves the
 * pair agrees.
 */

// Over the web this is a WordPress include and needs WordPress. On a CLI it is
// a library, which is how the offline drill exercises it. Both stated, so
// neither is an accident.
if (!defined('ABSPATH') && PHP_SAPI !== 'cli') exit;

if (!defined('ALT_SBK_FORMAT')) define('ALT_SBK_FORMAT', 'alt-subscriber-backup/1');

/** Thrown for every refusal. There is no partial success. */
class Alt_Sbk_Error extends Exception {}

/**
 * The fingerprint of a public key: sha256 of its DER SubjectPublicKeyInfo,
 * hex. Both sides compute it from the key itself, so the puller can prove the
 * host sealed to the key this repository committed and not to some other one.
 * A host that had been persuaded to use a different recipient would produce a
 * container the puller REFUSES, rather than one that silently cannot be opened.
 */
function alt_sbk_fingerprint($public_pem) {
    $der = alt_sbk_pem_to_der($public_pem);
    return hash('sha256', $der);
}

/** PEM body -> raw DER. Deliberately strict about the armour. */
function alt_sbk_pem_to_der($pem) {
    if (!preg_match('/-----BEGIN PUBLIC KEY-----(.+?)-----END PUBLIC KEY-----/s', (string) $pem, $m)) {
        throw new Alt_Sbk_Error('the recipient key is not a PEM SubjectPublicKeyInfo block');
    }
    $der = base64_decode(preg_replace('/\s+/', '', $m[1]), true);
    if ($der === false || $der === '') {
        throw new Alt_Sbk_Error('the recipient key body is not valid base64');
    }
    return $der;
}

/**
 * The canonical bytes the MAC covers. Field ORDER is part of the format and
 * both implementations hard-code the same list: a MAC over "whatever keys the
 * JSON happened to have" is a MAC that changes meaning when somebody adds a
 * field.
 */
function alt_sbk_canonical(array $h) {
    return implode("\n", array(
        $h['format'],
        $h['created_at'],
        (string) $h['schema_version'],
        (string) $h['rows'],
        implode(',', $h['columns']),
        $h['key_fingerprint'],
        $h['wrapped_key'],
        $h['iv'],
        $h['ciphertext'],
    ));
}

/**
 * Seal $plaintext for the holder of $public_pem.
 *
 * $meta carries only the facts a restore needs and a human can read without
 * the key: how many rows, which columns, when, which plugin build. There is no
 * field here that a value from the table could reach.
 */
function alt_sbk_seal($plaintext, $public_pem, array $meta) {
    if (!function_exists('openssl_public_encrypt')) {
        throw new Alt_Sbk_Error('this PHP has no openssl extension, so nothing can be sealed');
    }
    $key = openssl_pkey_get_public($public_pem);
    if ($key === false) {
        throw new Alt_Sbk_Error('the recipient public key did not parse');
    }
    $details = openssl_pkey_get_details($key);
    if (!$details || !isset($details['type']) || $details['type'] !== OPENSSL_KEYTYPE_RSA) {
        throw new Alt_Sbk_Error('the recipient key is not RSA');
    }
    if (!isset($details['bits']) || (int) $details['bits'] < 3072) {
        // Not a style rule. This container is meant to outlive the host and
        // possibly the decade, and a key chosen once is a key nobody revisits.
        throw new Alt_Sbk_Error('the recipient key is smaller than 3072 bits');
    }

    // One content-encryption key per container. Never reused, never stored.
    $cek = random_bytes(32);
    $iv  = random_bytes(16);

    $gz = gzencode($plaintext, 9);
    if ($gz === false) {
        throw new Alt_Sbk_Error('could not compress the payload');
    }
    $ct = openssl_encrypt($gz, 'aes-256-cbc', $cek, OPENSSL_RAW_DATA, $iv);
    if ($ct === false) {
        throw new Alt_Sbk_Error('aes-256-cbc encryption failed');
    }

    $wrapped = '';
    if (!openssl_public_encrypt($cek, $wrapped, $key, OPENSSL_PKCS1_OAEP_PADDING)) {
        throw new Alt_Sbk_Error('could not wrap the content key for the recipient');
    }

    $header = array(
        'format'          => ALT_SBK_FORMAT,
        'created_at'      => gmdate('Y-m-d\TH:i:s\Z'),
        'schema_version'  => (int) $meta['schema_version'],
        'rows'            => (int) $meta['rows'],
        'columns'         => array_values($meta['columns']),
        'key_fingerprint' => alt_sbk_fingerprint($public_pem),
        'wrapped_key'     => base64_encode($wrapped),
        'iv'              => base64_encode($iv),
        'ciphertext'      => base64_encode($ct),
    );
    // Encrypt-then-MAC, with the MAC key derived from the CEK rather than
    // being the CEK. Same secret, different purpose, separated so neither use
    // constrains the other.
    $mac_key = hash_hmac('sha256', 'alt-sbk/1 mac', $cek, true);
    $header['mac'] = base64_encode(hash_hmac('sha256', alt_sbk_canonical($header), $mac_key, true));
    $header['cipher'] = 'aes-256-cbc';
    $header['wrap'] = 'rsa-oaep-mgf1-sha1';
    $header['compression'] = 'gzip';
    $header['plugin_version'] = isset($meta['plugin_version']) ? (string) $meta['plugin_version'] : '';

    // The CEK dies here. Nothing else in this request may see it.
    $cek = null;
    $mac_key = null;

    return $header;
}
