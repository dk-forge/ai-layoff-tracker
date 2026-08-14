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
 * COST: ~40 files, ~2MB, one sha256 pass, memoised per request, and only ever
 * called on a plugin surface (which is cached for 60s) or on /status. Not
 * memoised ACROSS requests on purpose: a stamp cached during the upload window
 * would outlive the race that produced it and turn a two-minute mismatch into a
 * permanent one.
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
 * A short, stable fingerprint of this build's bytes, or '' if it cannot be read.
 */
function alt_build_stamp() {
    static $stamp = null;
    if ($stamp !== null) return $stamp;
    $files = alt_build_files();
    if (!$files) return $stamp = '';
    $manifest = '';
    foreach ($files as $rel) {
        $one = @hash_file('sha256', ALT_PLUGIN_DIR . $rel);
        if (!is_string($one) || $one === '') return $stamp = '';
        $manifest .= $one . '  ' . $rel . "\n";
    }
    return $stamp = substr(hash('sha256', $manifest), 0, 16);
}

/**
 * The comment a rendered plugin surface carries. Emitted ONCE per request, by
 * alt_template(), so it is produced by the same render as the body around it.
 * Anywhere else it would be another version string with extra steps.
 */
function alt_build_stamp_comment() {
    static $emitted = false;
    if ($emitted) return '';
    $stamp = alt_build_stamp();
    if ($stamp === '') return '';          // UNKNOWN is not something to publish
    $emitted = true;
    return "<!-- alt-build ver=" . ALT_VERSION . " build=" . $stamp . " -->\n";
}
