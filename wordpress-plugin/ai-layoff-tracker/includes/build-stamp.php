<?php
/**
 * The build stamp: which BYTES rendered this page, not which version string.
 *
 * ALT_VERSION lives in one file. An FTPS deploy uploads files one at a time, so
 * there is a window in which that one file has landed and the templates have
 * not, and a page rendered in that window carries the NEW version around the
 * OLD body. On 2026-08-12 the deploy's own reader check requested the bare URL
 * inside that window, WP Super Cache stored the result, and every reader was
 * served 2.20.21's asset stamps wrapped around 2.20.20's tracker template for
 * about twenty-five minutes. `reader_freshness.py` compared version to version,
 * found 2.20.21 on both sides, and returned PASS the whole time.
 *
 * So this hashes the files themselves, at render time, and the page carries the
 * answer. A template that has not landed yet is a different file, so it is a
 * different stamp, and a body that predates the change it is being checked for
 * can no longer report itself as current.
 *
 * WHAT IS COVERED: every file the deploy mirrors, minus the two globs the
 * deploy itself excludes (`.git*`, `*.zip`). Defining the set by the same rule
 * as `lftp mirror --reverse --delete` is deliberate: the stamp then means "the
 * bytes this deploy uploads", and there is no second list to drift.
 *
 * THREE STATES, HERE TOO. If any file cannot be read the answer is '' — not a
 * partial hash, not a hash of what happened to be readable. An empty stamp is
 * emitted nowhere, and a page with no stamp resolves to UNKNOWN downstream,
 * never to a pass.
 *
 * COST, AND WHY IT IS CACHED ACROSS REQUESTS SINCE 2.20.194. Until then this
 * was ~66 files, ~3.1 MB, one sha256 pass on EVERY uncached render of every
 * plugin surface (and the contact page since 2.20.191), memoised per request
 * only. The docblock refused a cross-request cache on purpose: a stamp cached
 * during the upload window would outlive the race that produced it and turn
 * a two-minute mismatch into a permanent one. On 2026-09-12/13 the shared host
 * fell over four times in twenty hours and per-request plugin work ranked
 * third among the causes, so the guarantee is now kept a cheaper way. The
 * stamp is held in a transient keyed by ALT_VERSION plus a stat pass over the
 * same file set (alt_build_stat_key: count, sizes, mtimes). A half-uploaded
 * tree has a different key from the finished one, so a stamp cached
 * mid-upload is invalidated by the next file that lands, and an ordinary
 * render costs one directory walk of stat() calls, not 66 digests.
 * alt_build_stamp(true) bypasses the cache and rehashes; /status?build=1 uses
 * it, because that is what reader_freshness.py grades a deploy against.
 * Without WordPress (a mid-upload request, or the php CLI in tests) there is
 * no transient and it hashes as before.
 *
 * The Python half is `checkout_build_stamp()` in railway/reader_freshness.py.
 * `tests/test_deploy_reaches_readers.py` EXECUTES this file and requires the
 * two to agree, because two implementations of one number is a drift risk.
 */

if (!defined('ABSPATH')) exit;

/** Relative paths of every file the deploy mirrors, sorted bytewise. */
function alt_build_files($dir = null) {
    $dir = $dir === null ? ALT_PLUGIN_DIR : trailingslashit($dir);
    if (!is_dir($dir)) return array();
    $out = array();
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::SELF_FIRST);
    foreach ($it as $path => $info) {
        if (!$info->isFile()) continue;
        $rel = str_replace('\\', '/', substr($path, strlen($dir)));
        if ($rel === '' || alt_build_file_excluded($rel)) continue;
        $out[] = $rel;
    }
    // strcmp, not sort(): PHP's default comparison would order two numeric-looking
    // names numerically and disagree with Python's bytewise sorted().
    usort($out, 'strcmp');
    return $out;
}

/** The deploy's own --exclude-globs, and nothing else. */
function alt_build_file_excluded($rel) {
    foreach (explode('/', $rel) as $part) {
        if (strpos($part, '.git') === 0) return true;
        if (substr($part, -4) === '.zip') return true;
    }
    return false;
}

/**
 * What a stat pass says is on disk: the version, the file count, and every
 * file's size and mtime folded into one digest. Cheap (no file is read), and
 * it changes whenever any deployed file changes in size or lands anew, which
 * is what makes it safe to key a cached stamp on. '' if the tree is unreadable.
 */
function alt_build_stat_key() {
    $files = alt_build_files();
    if (!$files) return '';
    $ver = defined('ALT_VERSION') ? (string) ALT_VERSION : '';
    $acc = '';
    foreach ($files as $rel) {
        $path = ALT_PLUGIN_DIR . $rel;
        $size = @filesize($path);
        $mtime = @filemtime($path);
        if ($size === false || $mtime === false) return '';
        $acc .= $rel . "\0" . $size . "\0" . $mtime . "\n";
    }
    return $ver . '|' . count($files) . '|' . substr(hash('sha256', $acc), 0, 32);
}

/**
 * A short, stable fingerprint of this build's bytes, or '' if it cannot be read.
 *
 * $fresh = true skips the cross-request cache and rehashes the tree. The
 * per-request memo is kept either way, so one render still emits one answer.
 */
function alt_build_stamp($fresh = false) {
    static $stamp = null;
    if ($stamp !== null && !$fresh) return $stamp;
    $transient = 'alt_build_stamp';
    $key = '';
    if (!$fresh && function_exists('get_transient')) {
        $key = alt_build_stat_key();
        if ($key !== '') {
            $cached = get_transient($transient);
            if (is_array($cached) && isset($cached['key'], $cached['stamp'])
                && $cached['key'] === $key && is_string($cached['stamp'])
                && preg_match('/^[a-f0-9]{16}$/', $cached['stamp'])) {
                return $stamp = $cached['stamp'];
            }
        }
    }
    $files = alt_build_files();
    if (!$files) return $stamp = '';
    $manifest = '';
    foreach ($files as $rel) {
        $one = @hash_file('sha256', ALT_PLUGIN_DIR . $rel);
        if (!is_string($one) || $one === '') return $stamp = '';
        $manifest .= $one . '  ' . $rel . "\n";
    }
    $stamp = substr(hash('sha256', $manifest), 0, 16);
    // Written under the key of the tree that was just hashed. A tree that is
    // still uploading yields a key no finished tree will match, so the entry
    // can only ever be served to requests that see exactly these files.
    if (function_exists('set_transient')) {
        if ($key === '') $key = alt_build_stat_key();
        if ($key !== '') set_transient($transient, array('key' => $key, 'stamp' => $stamp), DAY_IN_SECONDS_ALT());
    }
    return $stamp;
}

/** 86400 without depending on WordPress having defined DAY_IN_SECONDS yet. */
function DAY_IN_SECONDS_ALT() {
    return defined('DAY_IN_SECONDS') ? DAY_IN_SECONDS : 86400;
}

/**
 * The stamp a rendered plugin surface carries. Emitted ONCE per request, by
 * alt_template(), so it is produced by the same render as the body around it.
 * Anywhere else it would be another version string with extra steps.
 *
 * IT IS NOT ONLY A COMMENT, AND THE COMMENT ALONE DOES NOT REACH READERS.
 * The stamp shipped as an HTML comment in 2.20.38 and the deploy's own reader
 * check failed on the first run that used it: the origin was coherent at
 * 2.20.38/af2cbcb8 and every reader view read `build=None`. Something in front
 * of the rendered body on this host strips HTML comments. Measured on the live
 * page rather than guessed: `id="alt-active-filters"` is served, and the
 * `<!-- Active-filter summary` comment written directly above it in
 * templates/page-tracker.php is not, on the bare URL and with a cache buster
 * alike. Only WP-Super-Cache's own three comments survive, and it appends
 * those after the strip.
 *
 * So the carrier is an ELEMENT, which no minifier is free to drop, and the
 * comment stays beside it because it costs one line and is the more readable
 * of the two in a view-source. Both say the same thing from the same render;
 * reader_freshness.py accepts either and requires them to agree when it sees
 * both. Do NOT "simplify" this back to the comment alone.
 */
function alt_build_stamp_comment() {
    static $emitted = false;
    if ($emitted) return '';
    $stamp = alt_build_stamp();
    if ($stamp === '') return '';          // UNKNOWN is not something to publish
    $emitted = true;
    // Escaped WITHOUT esc_attr() on purpose. This file is required before the
    // rest of the plugin and is deliberately WP-independent, so that it can
    // still answer during a mid-upload request -- the exact condition it exists
    // to describe. Reaching for a WP function here fatals the page instead of
    // stamping it. Neither value is user input (one is our own constant, the
    // other a hex digest), and the whitelist below is narrower than esc_attr:
    // anything outside [A-Za-z0-9._-] cannot reach an attribute at all.
    $ver = preg_replace('/[^A-Za-z0-9._-]/', '', (string) ALT_VERSION);
    $stamp = preg_replace('/[^a-f0-9]/', '', $stamp);
    return "<!-- alt-build ver=" . $ver . " build=" . $stamp . " -->\n"
         . '<span class="alt-build" hidden aria-hidden="true"'
         . ' data-alt-build-ver="' . $ver . '"'
         . ' data-alt-build="' . $stamp . '"></span>' . "\n";
}
