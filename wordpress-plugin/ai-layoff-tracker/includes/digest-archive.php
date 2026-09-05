<?php
/**
 * The public edition archive: every digest that goes out, kept at a permanent
 * URL, forever.
 *
 * WHY THIS EXISTS, AND SEO IS THE SECOND REASON.
 *
 * The whole pitch of this product is that every number is traceable. A digest
 * broke that promise: its figures were read once, at compose time, and then
 * they only ever existed inside somebody's inbox. A reporter who wanted to
 * quote "5,000 verified US job cuts in Week 33" had nowhere to point, and the
 * live tracker does not answer for them, because it keeps moving. An archived
 * edition is a dated, immutable statement of what was published and when,
 * which is the artifact a citation actually needs. Browsing and search
 * visibility follow from that; they did not motivate it.
 *
 * WHAT IS ARCHIVED, AND WHAT MAY NEVER BE.
 *
 * The composed CONTENT, never a rendered message. A message is per recipient:
 * it carries that person's unsubscribe token, their manage link, their
 * address, and the "you get this because you subscribed" and tracking
 * disclosure lines, all of which are recipient context and none of which
 * belongs on a public page. So this file archives what the three composers
 * produced for the window, re-composed with send_id = 0.
 *
 * SEND ID ZERO IS THE WHOLE PRIVACY DESIGN, and it is a property rather than a
 * promise. alt_digest_track_link() returns the destination UNCHANGED when the
 * send id is zero (includes/subscribe.php), so a section composed at zero
 * cannot contain a click-counter URL, and the composers never see a recipient
 * at all. The archived copy is therefore free of both recipient-scoped and
 * send-scoped values by construction, not by remembering to strip them.
 *
 * It is checked anyway, by shape, on the way in AND on the way out:
 * alt_edition_public_safe() is an ALLOWLIST (permitted URL paths, permitted
 * query keys) in the spirit of assert_nameless in railway/tracker_diff.py.
 * A section that fails is not archived and not rendered. Fail closed.
 *
 * IMMUTABILITY. An edition states what was published at that moment. Nothing
 * in this file updates a stored section: capture refuses to touch a published
 * row, publishing writes one timestamp, and a later revision attaches as a
 * dated CORRECTION note beside the original text. Silently rewriting history
 * is the opposite of what this product sells.
 */

if (!defined('ABSPATH')) exit;

/* ------------------------------------------------------------------ */
/* Store                                                               */
/* ------------------------------------------------------------------ */

function alt_editions_table() {
    global $wpdb;
    return $wpdb->prefix . 'alt_digest_editions';
}

/**
 * Create the table if it is missing, exactly as includes/blog-claps.php does
 * it: an FTP deploy can serve a request before any installer has run, and the
 * capture path is a writer, so it verifies first.
 */
function alt_editions_table_ready() {
    global $wpdb;
    $table = alt_editions_table();
    if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table) {
        return true;
    }
    if (!function_exists('dbDelta')) {
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    }
    if (!function_exists('dbDelta')) return false;
    $charset = $wpdb->get_charset_collate();
    // `sections` is the composed content as JSON, written ONCE. There is no
    // code path in this plugin that updates it, and that is the point.
    dbDelta("CREATE TABLE $table (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        send_id BIGINT UNSIGNED NOT NULL DEFAULT 0,
        freq VARCHAR(6) NOT NULL DEFAULT 'weekly',
        slug VARCHAR(20) NOT NULL,
        window_from DATE NOT NULL,
        window_to DATE NOT NULL,
        data_cut VARCHAR(120) NOT NULL DEFAULT '',
        composed_at DATETIME NOT NULL,
        published_at DATETIME NULL,
        sections LONGTEXT NOT NULL,
        corrections LONGTEXT NULL,
        PRIMARY KEY (id),
        UNIQUE KEY edition (freq, slug),
        KEY published (published_at)
    ) $charset;");
    return $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
}

/** Readers never install. Absent table is "we cannot see it", not "it is empty". */
function alt_editions_table_present() {
    global $wpdb;
    $table = alt_editions_table();
    return $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
}

/**
 * The three streams, in the SITE's order, keyed to the composer that builds
 * each one. Driven by hand rather than by iteration for the same reason the
 * recipient loop in digest-api.php is: a fourth stream should be a deliberate
 * edit here.
 */
function alt_edition_streams() {
    return array(
        'layoff'   => 'alt_digest_compose_layoff',
        'talent'   => 'alt_digest_compose_talent',
        'articles' => 'alt_digest_compose_articles',
    );
}

/**
 * THE INDEXING SPLIT, IN ONE PLACE.
 *
 * Search Console currently reports ~6,500 URLs on this site as "Discovered,
 * currently not indexed" with no crawl date: parameterised report URLs and the
 * thin company pages. Google is declining to spend crawl budget on large sets
 * of similar pages, and a daily archive is ~365 near-identical pages a year,
 * which is exactly that shape.
 *
 * So a weekly edition is indexable (about 52 a year, each substantial and
 * genuinely different) and a daily edition is archived at a permanent URL and
 * kept OUT of the index. Links never break; crawl budget is not diluted.
 *
 * This function is the only place that decision is written down. The robots
 * filters, the canonical, the sitemap and the reader-facing note on the page
 * all read it, so the split cannot be true in one place and false in another.
 */
function alt_edition_tier_indexable() {
    return apply_filters('alt_edition_tier_indexable',
                         array('weekly' => true, 'daily' => false));
}

function alt_edition_indexable($freq) {
    $map = alt_edition_tier_indexable();
    return !empty($map[(string) $freq]);
}

/* ------------------------------------------------------------------ */
/* Identity                                                            */
/* ------------------------------------------------------------------ */

/**
 * The permanent name of an edition.
 *
 * Weekly is the ISO week the edition reports, "2026-W33", taken from
 * alt_digest_iso_week() so the slug and the printed week number cannot
 * disagree. It is the ISO year and not the calendar year, which is the trap
 * that ships silently and is found the following January.
 *
 * Daily is the window's own end date, "2026-08-18".
 *
 * A PATH SEGMENT AND NOT A QUERY PARAMETER, deliberately. Both of the URL
 * clusters Search Console is sitting on are parameterised, and there is no
 * reason to add a third.
 */
function alt_edition_slug($freq, $from, $to) {
    $freq = function_exists('alt_digest_valid_freq') ? alt_digest_valid_freq($freq) : 'weekly';
    $from = substr(trim((string) $from), 0, 10);
    $to = substr(trim((string) $to), 0, 10);
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $from)) return '';
    if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $to)) return '';
    if ($freq === 'weekly') {
        $iso = function_exists('alt_digest_iso_week') ? alt_digest_iso_week($from) : null;
        return $iso === null ? '' : sprintf('%04d-W%02d', $iso[0], $iso[1]);
    }
    return $to;
}

/** Is this a slug this archive could ever have minted? Shape only. */
function alt_edition_valid_slug($freq, $slug) {
    $slug = (string) $slug;
    if ($freq === 'weekly') return (bool) preg_match('/^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$/', $slug);
    return (bool) preg_match('/^\d{4}-\d{2}-\d{2}$/', $slug);
}

function alt_edition_index_url() {
    return home_url('/ai-layoff-tracker/editions/');
}

function alt_edition_url($freq, $slug) {
    return alt_edition_index_url() . rawurlencode((string) $freq) . '/' . rawurlencode((string) $slug) . '/';
}

/**
 * "Aug 10-16, 2026" / "Aug 19, 2026". The edition's title, from the shared
 * helpers, and it OPENS WITH THE SAME STRING THE SUBJECT LINE OPENS WITH.
 *
 * A subscriber reads "Aug 10-16: 16,842 verified job cuts" in the inbox and
 * follows a link here. If the page called the same edition something else, the
 * two surfaces would read as two things that happen to be about one week. So
 * the subject's period token is a literal PREFIX of this title, and
 * tests/test_digest_subject_never_inflates_ai.py fails if that ever drifts.
 *
 * THE YEAR IS HERE AND NOT IN THE SUBJECT, and the split is deliberate. A
 * subject is skimmed in an inbox that already stamps the date, so six
 * characters are better spent on the metric. This page is CITED, so it carries
 * the year, and a window crossing a new year carries both ("Dec 28 - Jan 3,
 * 2026-2027"), which is the only shape where dropping one would publish a
 * wrong year.
 *
 * THE ISO WEEK IS NOT IN THIS HEADING AND HAS NOT BEEN LOST. 2026-W33 is the
 * archive URL, which is what a researcher cites and what sorts, and it is on
 * the edition's own dateline inside. The week number is precise for citation
 * and opaque for skimming, so it lives where people cite.
 *
 * A DAILY EDITION IS NAMED BY ITS DATE AND NOT BY ITS WINDOW, for the same
 * reason the subject is: the daily window is two days and the subject names
 * the day it went out, which is the masthead convention. A newspaper's front
 * page carries the publication date and the stories inside state their own
 * spans. The edition's dateline still states the full window it covers.
 */
function alt_edition_label($row) {
    $from = (string) $row['window_from'];
    $to = (string) $row['window_to'];
    // The SAME token the subject line uses, asked for rather than rebuilt, so
    // the prefix relationship holds by construction instead of by care.
    if (function_exists('alt_digest_subject_period')) {
        $period = alt_digest_subject_period((string) $row['freq'], $from, $to);
        if ($period !== '') {
            $fy = substr($from, 0, 4);
            $ty = substr($to, 0, 4);
            // A weekly names its window, so a window that straddles a new year
            // needs both. A daily names its day, so it takes that day's year.
            $years = ((string) $row['freq'] === 'weekly' && $fy !== '' && $fy !== $ty)
                ? $fy . '-' . $ty : $ty;
            if ($years !== '') return $period . ', ' . $years;
        }
    }
    if (function_exists('alt_digest_date_range')) {
        $range = alt_digest_date_range($to, $to);
        if ($range !== '') return $range;
    }
    return $to;
}

/* ------------------------------------------------------------------ */
/* The privacy gate                                                    */
/* ------------------------------------------------------------------ */

/**
 * Query keys an archived link may carry. An ALLOWLIST, so a key nobody thought
 * about is refused rather than admitted. `t` (the confirm/unsubscribe token),
 * `s` and `l` (the click counter's send id and link hash), `action`, `key` and
 * `email` are absent because absence is how they are refused, and adding one
 * would have to be a deliberate edit to this list.
 */
function alt_edition_allowed_query_keys() {
    return array('from', 'to', 'date_basis', 'country', 'country_basis', 'state',
                 'industry', 'sources', 'reasons', 'roles', 'company', 'keyword',
                 'min_jobs', 'q', 'years', 'quarters', 'months', 'ai', 'period',
                 'scope', 'view', 'page', 'sort');
}

/**
 * Path shapes an archived link may point at, with this install's own prefix
 * (/blog) already stripped. An ALLOWLIST for the same reason.
 *
 * The tracker pattern refuses `confirm` and `unsubscribe` explicitly rather
 * than relying on the token ban below to catch them: a token-shaped run is a
 * second, independent net, and neither should be the only one.
 *
 * wp-admin and wp-json match nothing here, which is what refuses
 * admin-post.php?action=alt_digest_unsub and the /click redirect.
 */
function alt_edition_allowed_paths() {
    return array(
        '#^$#',
        '#^ai-layoff-tracker(?!/(confirm|unsubscribe)(/|$))(/[a-z0-9][a-z0-9\-]*)*/?$#',
        /*
          AN EDITION'S OWN PERMALINK, WHICH THE GENERAL TRACKER PATTERN CANNOT
          MATCH. The weekly slug is "2026-W33" and that W is uppercase, so
          `[a-z0-9][a-z0-9\-]*` refuses it. The layoff section links to its own
          archived edition since 2.20.123, and without this line every archived
          edition refuses to publish itself.

          WRITTEN AS THE TWO SLUG SHAPES RATHER THAN BY RELAXING THE RULE
          ABOVE. Allowing uppercase in every tracker path segment to admit one
          known slug would widen the whole surface to buy one URL. These are
          exactly the two forms alt_edition_slug() can mint, and
          alt_edition_valid_slug() is the same shapes on the reading side.

          IT IS NOT A FILTERED VIEW and needs no basis: an archived edition is
          a fixed record of what was sent, with nothing for a date basis to
          reinterpret. See alt_edition_is_filtered_view.
        */
        '#^ai-layoff-tracker/editions/(weekly/\d{4}-W\d{2}|daily/\d{4}-\d{2}-\d{2})/?$#',
        '#^layoff/[a-z0-9][a-z0-9\-]*/?$#',
        '#^company-layoffs/[a-z0-9][a-z0-9\-]*/?$#',
        '#^(country|state|industry)-layoffs/[a-z0-9][a-z0-9\-]*/?$#',
        '#^contact/?$#',
        // Blog permalinks: the articles stream links to our own posts.
        '#^[a-z0-9][a-z0-9\-]*/?$#',
    );
}

/** The tracker page itself: a FILTERED VIEW, so a link to it must name a basis. */
function alt_edition_is_filtered_view($path) {
    return (string) $path === 'ai-layoff-tracker';
}

/**
 * Is this whole document safe to publish?
 *
 * Returns array('ok' => bool, 'rule' => string). The rule NAMES THE RULE and
 * never quotes the offending value, so the reason can be logged without the
 * log becoming the leak the check exists to prevent.
 *
 * Three families:
 *
 *   1. Every URL is on our own host, its path matches the path allowlist, and
 *      every query key is on the key allowlist.
 *   2. A link to the tracker page carries `date_basis`. The tracker page
 *      defaults to the FILING basis while every digest figure is counted on
 *      the EFFECTIVE basis, so a link without the basis lands on a page
 *      showing a different number under the same label. This is the same rule
 *      railway/tests/test_digest_link_basis.py holds on the email path; a
 *      public, citable copy has more need of it, not less.
 *   3. Two shapes that could appear OUTSIDE a URL are refused anywhere in the
 *      document: an email address, and a run of 32 or more hex characters
 *      (the click hash is 32, an unsubscribe token is 64).
 */
/**
 * The copy of a section the archive may publish: off-host links unlinked.
 *
 * On 2026-08-20 the talent section gained a link per hiring signal and on
 * 2026-08-25 the layoff section gained a source link per biggest cut. Both
 * point at other sites, and the gate below admits no host but our own, so
 * from those dates every daily edition archived the blog section alone and
 * said so only in error_log. The reader page showed one section and no notice;
 * ops_status has no view of a WordPress error_log.
 *
 * The gate stays exactly as strict: it still judges what is stored, and what
 * is stored is this copy. An off-host anchor becomes its own text followed by
 * the outlet's host in parentheses, so the archive still says WHERE a figure
 * came from without publishing a link to it; a bare off-host URL in the text
 * version becomes that host. Links on our own host are untouched. The email
 * itself is not changed by this; only the archived copy is.
 */
function alt_edition_publishable_copy($html, $text) {
    $hosts = function_exists('alt_digest_link_hosts') ? alt_digest_link_hosts() : array();
    $host_of = function ($url) {
        $h = wp_parse_url(rtrim(html_entity_decode((string) $url, ENT_QUOTES, 'UTF-8'), '.,;'), PHP_URL_HOST);
        return is_string($h) ? strtolower(preg_replace('/^www\./', '', $h)) : '';
    };
    $off_host = function ($url) use ($hosts, $host_of) {
        $h = $host_of($url);
        return $h !== '' && !in_array($h, $hosts, true) && !in_array('www.' . $h, $hosts, true);
    };
    $html = preg_replace_callback(
        '#<a\s[^>]*href\s*=\s*"([^"]*)"[^>]*>(.*?)</a>#is',
        function ($m) use ($off_host, $host_of) {
            if (!$off_host($m[1])) return $m[0];
            $label = trim(wp_strip_all_tags($m[2]));
            $host = $host_of($m[1]);
            if ($label === '') return esc_html($host);
            return stripos($label, $host) !== false
                ? esc_html($label) : esc_html($label) . ' (' . esc_html($host) . ')';
        },
        (string) $html);
    $text = preg_replace_callback(
        '#https?://[^\s"<>\)]+#i',
        function ($m) use ($off_host, $host_of) {
            return $off_host($m[0]) ? $host_of($m[0]) : $m[0];
        },
        (string) $text);
    return array('html' => (string) $html, 'text' => (string) $text);
}

function alt_edition_public_safe($doc) {
    $doc = (string) $doc;
    if ($doc === '') return array('ok' => false, 'rule' => 'empty document');

    if (preg_match('/[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}/', $doc)) {
        return array('ok' => false, 'rule' => 'an address-shaped string is present');
    }
    if (preg_match('/[0-9a-fA-F]{32,}/', $doc)) {
        return array('ok' => false, 'rule' => 'a token-shaped run of hex is present');
    }

    $urls = array();
    if (preg_match_all('/href\s*=\s*"([^"]*)"/i', $doc, $m)) {
        foreach ($m[1] as $u) $urls[] = html_entity_decode($u, ENT_QUOTES, 'UTF-8');
    }
    if (preg_match_all('#https?://[^\s"<>\)]+#i', $doc, $m)) {
        foreach ($m[0] as $u) $urls[] = html_entity_decode($u, ENT_QUOTES, 'UTF-8');
    }

    $hosts = function_exists('alt_digest_link_hosts') ? alt_digest_link_hosts() : array();
    $home_path = trim((string) wp_parse_url(home_url('/'), PHP_URL_PATH), '/');
    foreach ($urls as $url) {
        $parts = wp_parse_url(rtrim($url, '.,;'));
        if (!is_array($parts) || empty($parts['host'])) {
            return array('ok' => false, 'rule' => 'a link is not an absolute URL');
        }
        if (isset($parts['user']) || isset($parts['pass'])) {
            return array('ok' => false, 'rule' => 'a link carries credentials');
        }
        if (!in_array(strtolower($parts['host']), $hosts, true)) {
            return array('ok' => false, 'rule' => 'a link points off our own host');
        }
        $path = trim(rawurldecode((string) ($parts['path'] ?? '')), '/');
        if ($home_path !== '' && $path === $home_path) {
            $path = '';
        } elseif ($home_path !== '' && strpos($path, $home_path . '/') === 0) {
            $path = substr($path, strlen($home_path) + 1);
        }
        $matched = false;
        foreach (alt_edition_allowed_paths() as $pattern) {
            if (preg_match($pattern, $path)) { $matched = true; break; }
        }
        if (!$matched) {
            return array('ok' => false, 'rule' => 'a link path is not on the allowlist');
        }
        $query = array();
        if (isset($parts['query']) && $parts['query'] !== '') {
            parse_str($parts['query'], $query);
        }
        foreach (array_keys($query) as $key) {
            if (!in_array((string) $key, alt_edition_allowed_query_keys(), true)) {
                return array('ok' => false, 'rule' => 'a link carries a query key that is not on the allowlist');
            }
        }
        if ($query && alt_edition_is_filtered_view(rtrim($path, '/'))
            && !array_key_exists('date_basis', $query)) {
            return array('ok' => false, 'rule' => 'a filtered tracker link does not name its date_basis');
        }
    }
    return array('ok' => true, 'rule' => '');
}

/**
 * The tags an archived section may render as, checked on the way OUT.
 *
 * The composers emit email markup: a presentation table, headings, paragraphs
 * marked with data-alt so a stylesheet can tell a stat from a caption. This is
 * the second allowlist and it is about markup rather than about privacy;
 * alt_edition_public_safe is what holds the privacy line.
 */
function alt_edition_allowed_html() {
    $inline = array('data-alt' => true);
    return array(
        'h2' => $inline, 'h3' => $inline, 'h4' => $inline,
        'p' => $inline, 'span' => $inline, 'div' => $inline,
        'strong' => array(), 'em' => array(), 'b' => array(), 'i' => array(),
        'br' => array(), 'hr' => array(), 'code' => $inline,
        'ul' => $inline, 'ol' => $inline, 'li' => $inline,
        'a' => array('href' => true, 'data-alt' => true, 'rel' => true),
        'table' => array('role' => true, 'width' => true, 'cellpadding' => true,
                         'cellspacing' => true, 'border' => true, 'data-alt' => true),
        'thead' => $inline, 'tbody' => $inline, 'tr' => $inline,
        'td' => array('width' => true, 'align' => true, 'data-alt' => true),
        'th' => array('width' => true, 'align' => true, 'data-alt' => true),
    );
}

/**
 * One stored section, ready to print, CHECKED AGAIN on the way out.
 *
 * The click redirect judges its destination when the link is stored and again
 * when it is redeemed, so a row that reached the table by another path still
 * cannot be followed. Same idea: a stored section that no longer passes the
 * publication gate is withheld rather than rendered. It cannot happen through
 * any path in this plugin, which is exactly why the second check is cheap.
 */
function alt_edition_render_section($html) {
    $check = alt_edition_public_safe((string) $html);
    if (!$check['ok']) {
        return '<p class="alt-ed-withheld">This section is withheld: it no longer '
             . 'passes the archive\'s publication check.</p>';
    }
    return wp_kses((string) $html, alt_edition_allowed_html());
}

/* ------------------------------------------------------------------ */
/* Capture (at compose time, which is the only honest moment)          */
/* ------------------------------------------------------------------ */

/**
 * Archive the edition for this window.
 *
 * WHY COMPOSE TIME AND NOT SEND TIME OR LATER. The archive has to say what was
 * PUBLISHED, and the data behind it keeps moving: filings and WARN notices
 * arrive for weeks. Reconstructing an edition from live data next month would
 * produce a page that disagrees with the email people were actually sent,
 * which is worse than having no archive at all. So the content is taken at the
 * moment the senders take theirs, from the same composers, over the same
 * window.
 *
 * IT IS RE-COMPOSED AT SEND ID ZERO rather than copied from the message. That
 * is one extra pass over the site's own in-process endpoints, twice a day, and
 * it buys the property this whole file rests on: a section composed at zero
 * cannot carry a click-counter URL, because alt_digest_track_link() returns
 * the plain destination when the send id is zero.
 *
 * The row is stored UNPUBLISHED. It becomes public only when a send is
 * recorded, so a preview, a dry run, a nominated test send and a run that
 * finds nobody due all leave nothing on the archive.
 *
 * Returns the row id, or 0 when nothing was archived.
 */
function alt_edition_capture($freq, $from, $to, $send_id = 0) {
    global $wpdb;
    if (!function_exists('alt_digest_valid_freq')) return 0;
    $freq = alt_digest_valid_freq($freq);
    $slug = alt_edition_slug($freq, $from, $to);
    if ($slug === '' || !alt_editions_table_ready()) return 0;
    $table = alt_editions_table();

    $existing = $wpdb->get_row($wpdb->prepare(
        "SELECT id, published_at FROM $table WHERE freq = %s AND slug = %s", $freq, $slug), ARRAY_A);
    if ($existing && $existing['published_at'] !== null) {
        // IMMUTABLE. An edition that has gone out is never recomposed, even
        // over the same window: it is a statement about a moment that has
        // passed. A later revision attaches as a correction.
        return (int) $existing['id'];
    }

    $sections = array();
    foreach (alt_edition_streams() as $name => $fn) {
        if (!function_exists($fn)) continue;
        // SEND ID ZERO. See the file header. $freq is passed so the layoff
        // composer archives the monthly masthead and Indeed backdrop, and the
        // talent composer carries that backdrop on daily/weekly and defers it to
        // the layoff section on monthly (one home per edition, so the combined
        // archive page never shows it twice); the articles composer ignores the
        // extra argument (PHP permits it).
        $part = $fn($from, $to, 0, $freq);
        if (!is_array($part) || empty($part['html']) || empty($part['text'])) continue;
        // The archive publishes a COPY with off-host links unlinked (see
        // alt_edition_publishable_copy); the gate judges that copy, unchanged.
        $part = alt_edition_publishable_copy($part['html'], $part['text']);
        $check = alt_edition_public_safe($part['html'] . "\n" . $part['text']);
        if (!$check['ok']) {
            // Fail closed, and say which RULE refused it, never what tripped it.
            error_log('alt: the ' . $name . ' section was not archived: ' . $check['rule']);
            continue;
        }
        $sections[$name] = array(
            'html'    => (string) $part['html'],
            'text'    => (string) $part['text'],
            'heading' => function_exists('alt_digest_section_heading')
                         ? alt_digest_section_heading((string) $part['text']) : '',
        );
    }
    if (!$sections) return 0;

    $row = array(
        'send_id'     => (int) $send_id,
        'freq'        => $freq,
        'slug'        => $slug,
        'window_from' => substr((string) $from, 0, 10),
        'window_to'   => substr((string) $to, 0, 10),
        'data_cut'    => function_exists('alt_digest_data_cut_label')
                         ? substr((string) alt_digest_data_cut_label(), 0, 120) : '',
        'composed_at' => gmdate('Y-m-d H:i:s'),
        'sections'    => wp_json_encode($sections),
    );
    if ($existing) {
        $wpdb->update($table, $row, array('id' => (int) $existing['id']));
        return (int) $existing['id'];
    }
    $wpdb->insert($table, $row);
    return (int) $wpdb->insert_id;
}

/**
 * The edition went out. Make it public, once.
 *
 * Called from the moment a send is RECORDED, which is the only moment either
 * sender knows a message reached the relay. published_at is written once and
 * never rewritten: a second run over the same window finds it published and
 * leaves it alone.
 */
function alt_edition_publish($send_id, $freq = '') {
    global $wpdb;
    if (!alt_editions_table_present()) return 0;
    $table = alt_editions_table();
    $send_id = (int) $send_id;
    $now = gmdate('Y-m-d H:i:s');
    if ($send_id > 0) {
        return (int) $wpdb->query($wpdb->prepare(
            "UPDATE $table SET published_at = %s WHERE send_id = %d AND published_at IS NULL",
            $now, $send_id));
    }
    // No send row on this install (the sends table is absent), so the newest
    // unpublished edition for the tier is the one this run composed.
    $freq = function_exists('alt_digest_valid_freq') ? alt_digest_valid_freq($freq) : '';
    if ($freq === '') return 0;
    $id = (int) $wpdb->get_var($wpdb->prepare(
        "SELECT id FROM $table WHERE freq = %s AND published_at IS NULL ORDER BY id DESC LIMIT 1", $freq));
    if ($id <= 0) return 0;
    return (int) $wpdb->query($wpdb->prepare(
        "UPDATE $table SET published_at = %s WHERE id = %d AND published_at IS NULL", $now, $id));
}

/* ------------------------------------------------------------------ */
/* Reading                                                             */
/* ------------------------------------------------------------------ */

function alt_edition_decode($row) {
    if (!is_array($row)) return null;
    $row['sections'] = json_decode((string) $row['sections'], true);
    if (!is_array($row['sections']) || !$row['sections']) return null;
    $row['corrections'] = json_decode((string) ($row['corrections'] ?? ''), true);
    if (!is_array($row['corrections'])) $row['corrections'] = array();
    return $row;
}

/** One published edition, or null. Unpublished editions are not readable. */
function alt_edition_get($freq, $slug) {
    global $wpdb;
    if (!alt_editions_table_present()) return null;
    if (!alt_edition_valid_slug($freq, $slug)) return null;
    $table = alt_editions_table();
    return alt_edition_decode($wpdb->get_row($wpdb->prepare(
        "SELECT * FROM $table WHERE freq = %s AND slug = %s AND published_at IS NOT NULL",
        $freq, $slug), ARRAY_A));
}

/** Every published edition, newest window first. */
function alt_edition_all() {
    global $wpdb;
    if (!alt_editions_table_present()) return array();
    $table = alt_editions_table();
    $rows = $wpdb->get_results(
        "SELECT * FROM $table WHERE published_at IS NOT NULL ORDER BY window_to DESC, id DESC",
        ARRAY_A);
    $out = array();
    foreach ((array) $rows as $row) {
        $row = alt_edition_decode($row);
        if ($row) $out[] = $row;
    }
    return $out;
}

/**
 * Is there anything in the archive at all?
 *
 * The signup form asks this on every render, on every page the form appears
 * on, so it is a cached yes/no rather than a query. An hour of staleness costs
 * nothing: the answer flips once, on the first send, and never flips back.
 */
function alt_edition_any() {
    global $wpdb;
    $cached = get_transient('alt_edition_any');
    if ($cached !== false) return $cached === 'yes';
    if (!alt_editions_table_present()) return false;
    $n = (int) $wpdb->get_var('SELECT COUNT(*) FROM ' . alt_editions_table()
                              . ' WHERE published_at IS NOT NULL');
    set_transient('alt_edition_any', $n > 0 ? 'yes' : 'no', HOUR_IN_SECONDS);
    return $n > 0;
}

/** The edition before and after this one on the same tier, for reader paths. */
function alt_edition_neighbours($row, $all = null) {
    $all = $all === null ? alt_edition_all() : $all;
    $tier = array();
    foreach ($all as $r) { if ($r['freq'] === $row['freq']) $tier[] = $r; }
    $prev = $next = null;
    foreach ($tier as $i => $r) {
        if ((string) $r['slug'] !== (string) $row['slug']) continue;
        $next = isset($tier[$i - 1]) ? $tier[$i - 1] : null;   // newer
        $prev = isset($tier[$i + 1]) ? $tier[$i + 1] : null;   // older
        break;
    }
    return array($prev, $next);
}

/* ------------------------------------------------------------------ */
/* Corrections (they attach; they never overwrite)                     */
/* ------------------------------------------------------------------ */

/**
 * Attach a dated correction to a published edition.
 *
 * A figure that is later revised does NOT change here. The original text
 * stands, and the note says what moved and when it was noticed, above the
 * edition it corrects. That is the only shape consistent with a product whose
 * pitch is that a published number can be checked afterwards.
 *
 * Keyed, like every other write in this plugin, so the archive cannot be
 * annotated by a stranger.
 */
function alt_edition_add_correction($freq, $slug, $note) {
    global $wpdb;
    $note = trim(wp_strip_all_tags((string) $note));
    if ($note === '' || !alt_editions_table_present()) return false;
    if (!alt_edition_valid_slug($freq, $slug)) return false;
    $table = alt_editions_table();
    $row = $wpdb->get_row($wpdb->prepare(
        "SELECT id, corrections FROM $table WHERE freq = %s AND slug = %s AND published_at IS NOT NULL",
        $freq, $slug), ARRAY_A);
    if (!$row) return false;
    $notes = json_decode((string) $row['corrections'], true);
    if (!is_array($notes)) $notes = array();
    $notes[] = array('at' => gmdate('Y-m-d'), 'note' => substr($note, 0, 1000));
    $wpdb->update($table, array('corrections' => wp_json_encode($notes)),
                  array('id' => (int) $row['id']));
    return true;
}

function alt_api_edition_correction($request) {
    $body = $request->get_json_params();
    if (!is_array($body)) $body = array();
    $ok = alt_edition_add_correction(
        (string) ($body['freq'] ?? ''), (string) ($body['slug'] ?? ''),
        (string) ($body['note'] ?? ''));
    return new WP_REST_Response(array('ok' => $ok), $ok ? 200 : 400);
}

add_action('rest_api_init', function () {
    register_rest_route('layoffs/v1', '/edition-correction', array(
        'methods'  => 'POST',
        'callback' => 'alt_api_edition_correction',
        'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
    ));
});

/* ------------------------------------------------------------------ */
/* Routing                                                             */
/* ------------------------------------------------------------------ */

add_action('init', function () {
    add_rewrite_rule('^ai-layoff-tracker/editions/?$',
                     'index.php?alt_edition_index=1', 'top');
    add_rewrite_rule('^ai-layoff-tracker/editions/(daily|weekly)/([0-9A-Za-z\-]+)/?$',
                     'index.php?alt_edition_freq=$matches[1]&alt_edition_slug=$matches[2]', 'top');
}, 1);

add_filter('query_vars', function ($vars) {
    $vars[] = 'alt_edition_index';
    $vars[] = 'alt_edition_freq';
    $vars[] = 'alt_edition_slug';
    $vars[] = 'alt_edition_sitemap';
    return $vars;
});

// FTP deploys never fire an activation hook, so a new rewrite rule would 404
// until something else happened to flush. Once per version, on its own option.
add_action('init', function () {
    if (get_option('alt_edition_rewrite_version') === ALT_VERSION) return;
    flush_rewrite_rules(false);
    update_option('alt_edition_rewrite_version', ALT_VERSION, false);
}, 99);

function alt_edition_is_index_request() {
    return (string) get_query_var('alt_edition_index') !== '';
}

function alt_edition_is_single_request() {
    return (string) get_query_var('alt_edition_freq') !== ''
        && (string) get_query_var('alt_edition_slug') !== '';
}

/** The requested edition, resolved once per request. */
function alt_edition_current() {
    if (!alt_edition_is_single_request()) return null;
    if (array_key_exists('alt_edition_current', $GLOBALS)) return $GLOBALS['alt_edition_current'];
    $GLOBALS['alt_edition_current'] = alt_edition_get(
        (string) get_query_var('alt_edition_freq'), (string) get_query_var('alt_edition_slug'));
    return $GLOBALS['alt_edition_current'];
}

add_action('template_redirect', function () {
    if (!alt_edition_is_single_request() && !alt_edition_is_index_request()) return;
    if (alt_edition_is_single_request() && !alt_edition_current()) {
        global $wp_query;
        $wp_query->set_404();
        status_header(404);
        if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
        nocache_headers();
        return;
    }
    // An archived edition never changes, so it may be cached hard. The index
    // gains a row twice a day.
    if (!headers_sent()) {
        header('Cache-Control: public, max-age=' . (alt_edition_is_single_request() ? 86400 : 600));
    }
}, 1);

add_filter('template_include', function ($template) {
    if (!alt_edition_is_index_request() && !(alt_edition_is_single_request() && alt_edition_current())) {
        return $template;
    }
    $custom = ALT_PLUGIN_DIR . 'templates/page-editions.php';
    return file_exists($custom) ? $custom : $template;
});

/* ------------------------------------------------------------------ */
/* SEO head                                                            */
/* ------------------------------------------------------------------ */

/** Does the current request belong in the index? One reading, four callers. */
function alt_edition_request_indexable() {
    if (alt_edition_is_index_request()) return true;
    $row = alt_edition_current();
    return $row ? alt_edition_indexable($row['freq']) : true;
}

function alt_edition_request_canonical() {
    if (alt_edition_is_index_request()) return alt_edition_index_url();
    $row = alt_edition_current();
    return $row ? alt_edition_url($row['freq'], $row['slug']) : '';
}

function alt_edition_request_title() {
    if (alt_edition_is_index_request()) {
        return 'Digest Archive: Every Edition We Have Emailed';
    }
    $row = alt_edition_current();
    if (!$row) return '';
    return alt_edition_label($row) . ': The Layoff Digest As It Was Sent';
}

function alt_edition_request_description() {
    if (alt_edition_is_index_request()) {
        return 'Every edition of the AskTheRecruiter layoff, talent and article '
             . 'digests, kept permanently at its own URL. Each one is a dated, '
             . 'unchanged record of the figures we published that day.';
    }
    $row = alt_edition_current();
    if (!$row) return '';
    return 'The digest we sent for ' . alt_edition_label($row) . ', kept exactly as '
         . 'it was published, with the window it covers and the moment the '
         . 'figures were read.';
}

add_filter('wp_robots', function ($robots) {
    if (!alt_edition_is_index_request() && !alt_edition_is_single_request()) return $robots;
    if (!alt_edition_request_indexable()) $robots['noindex'] = true;
    return $robots;
});
add_filter('wpseo_robots', function ($robots) {
    if (!alt_edition_is_index_request() && !alt_edition_is_single_request()) return $robots;
    return alt_edition_request_indexable() ? $robots : 'noindex, follow';
});
add_filter('rank_math/frontend/robots', function ($robots) {
    if (!alt_edition_is_index_request() && !alt_edition_is_single_request()) return $robots;
    return alt_edition_request_indexable() ? $robots : array('noindex', 'follow');
});

function alt_edition_canonical_filter($canonical) {
    $url = alt_edition_request_canonical();
    if ($url === '') return $canonical;
    return alt_edition_request_indexable() ? $url : false;
}
add_filter('wpseo_canonical', 'alt_edition_canonical_filter');
add_filter('rank_math/frontend/canonical', 'alt_edition_canonical_filter');

add_filter('document_title_parts', function ($parts) {
    $title = alt_edition_request_title();
    if ($title !== '') $parts['title'] = $title;
    return $parts;
}, 5);
function alt_edition_seo_title($title) {
    $own = alt_edition_request_title();
    return $own === '' ? $title : $own;
}
add_filter('wpseo_title', 'alt_edition_seo_title', 5);
add_filter('rank_math/frontend/title', 'alt_edition_seo_title', 5);

function alt_edition_seo_description($desc) {
    $own = alt_edition_request_description();
    return $own === '' ? $desc : $own;
}
add_filter('wpseo_metadesc', 'alt_edition_seo_description', 5);
add_filter('rank_math/frontend/description', 'alt_edition_seo_description', 5);

/** No-SEO-plugin fallback, guarded so we never print a second canonical. */
add_action('wp_head', function () {
    if (!alt_edition_is_index_request() && !alt_edition_is_single_request()) return;
    if (defined('WPSEO_VERSION') || class_exists('RankMath')) return;
    $desc = alt_edition_request_description();
    if ($desc !== '') echo '<meta name="description" content="' . esc_attr($desc) . '" />' . "\n";
    if (alt_edition_request_indexable()) {
        echo '<link rel="canonical" href="' . esc_url(alt_edition_request_canonical()) . '" />' . "\n";
    } else {
        echo '<meta name="robots" content="noindex, follow" />' . "\n";
    }
}, 1);

/* ------------------------------------------------------------------ */
/* Sitemap                                                             */
/* ------------------------------------------------------------------ */

/**
 * The hub and the INDEXABLE editions only. A noindex page in a sitemap is a
 * request to crawl something we then decline to have indexed, which is the
 * crawl-budget waste this whole split exists to avoid.
 */
function alt_edition_sitemap_urls() {
    $urls = array(alt_edition_index_url());
    foreach (alt_edition_all() as $row) {
        if (alt_edition_indexable($row['freq'])) {
            $urls[] = alt_edition_url($row['freq'], $row['slug']);
        }
    }
    return $urls;
}

function alt_edition_sitemap_url() { return home_url('/layoff-editions-sitemap.xml'); }

add_action('init', function () {
    add_rewrite_rule('^layoff-editions-sitemap\.xml$', 'index.php?alt_edition_sitemap=1', 'top');
}, 1);

add_action('template_redirect', function () {
    if ((string) get_query_var('alt_edition_sitemap') === '') return;
    if (!defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);
    status_header(200);
    header('Content-Type: application/xml; charset=UTF-8');
    header('X-Robots-Tag: noindex, follow');
    echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
    foreach (alt_edition_sitemap_urls() as $url) {
        echo '  <url><loc>' . esc_url($url) . '</loc></url>' . "\n";
    }
    echo '</urlset>';
    exit;
}, 0);

function alt_edition_sitemap_index_entry($xml) {
    if (!alt_editions_table_present()) return $xml;
    return $xml . '<sitemap><loc>' . esc_url(alt_edition_sitemap_url()) . '</loc></sitemap>' . "\n";
}
add_filter('wpseo_sitemap_index', 'alt_edition_sitemap_index_entry');
add_filter('rank_math/sitemap/index', 'alt_edition_sitemap_index_entry');
