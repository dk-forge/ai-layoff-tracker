<?php
/**
 * REST API endpoints (layoffs/v1).
 *
 * Authenticated (X-Layoff-API-Key header):
 *   POST /wp-json/layoffs/v1/add
 *   GET  /wp-json/layoffs/v1/check-duplicate?hash=...
 *
 * Public:
 *   GET  /wp-json/layoffs/v1/all
 *   GET  /wp-json/layoffs/v1/stats
 *   GET  /wp-json/layoffs/v1/company/{name}
 */

if (!defined('ABSPATH')) exit;

function alt_get_api_key() {
    // wp-config.php constant takes precedence over the stored option
    if (defined('AI_LAYOFF_API_KEY') && AI_LAYOFF_API_KEY) {
        return (string) AI_LAYOFF_API_KEY;
    }
    return (string) get_option('alt_api_key', '');
}

/**
 * Permission callback for authenticated routes. Fails CLOSED: if no key is
 * configured on the server, every request is rejected — an empty stored key
 * must never match an empty header.
 */
function alt_api_permission($request) {
    $stored = alt_get_api_key();
    if ($stored === '') {
        return new WP_Error(
            'alt_key_missing',
            'API key is not configured on this site. Activate the plugin (or set AI_LAYOFF_API_KEY in wp-config.php).',
            array('status' => 503)
        );
    }

    $provided = (string) $request->get_header('X-Layoff-API-Key');
    if ($provided === '' || !hash_equals($stored, $provided)) {
        return new WP_Error('alt_forbidden', 'Invalid or missing API key.', array('status' => 403));
    }
    return true;
}

function alt_register_routes() {
    register_rest_route('layoffs/v1', '/add', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_add',
        'permission_callback' => 'alt_api_permission',
    ));

    register_rest_route('layoffs/v1', '/check-duplicate', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_check_duplicate',
        'permission_callback' => 'alt_api_permission',
        'args' => array(
            'hash' => array('required' => true, 'type' => 'string'),
        ),
    ));

    register_rest_route('layoffs/v1', '/all', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_all',
        'permission_callback' => '__return_true',
    ));

    register_rest_route('layoffs/v1', '/stats', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_stats',
        'permission_callback' => '__return_true',
    ));

    register_rest_route('layoffs/v1', '/company/(?P<name>[^/]+)', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_company',
        'permission_callback' => '__return_true',
    ));

    register_rest_route('layoffs/v1', '/dedupe', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_dedupe',
        'permission_callback' => 'alt_api_permission',
    ));
}
add_action('rest_api_init', 'alt_register_routes');

/**
 * Normalize a company name to a comparison key so "Amazon", "Amazon.com Inc",
 * and "Amazon.com, Inc." all collapse to the same event when deduping.
 */
function alt_company_key($name) {
    $k = strtolower((string) $name);
    $k = preg_replace('/[^a-z0-9 ]/', ' ', $k);
    $k = preg_replace('/\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|group|holdings|holding|technologies|technology|systems|solutions|the|com)\b/', ' ', $k);
    return trim(preg_replace('/\s+/', ' ', $k));
}

/**
 * True if a published entry already exists for the same company (normalized)
 * within ~30 days of $date — i.e. probably the same event from another outlet.
 */
/**
 * Same-event fuzzy match: returns the matching post ID (truthy) when the same
 * company already has a published entry within ±30 days, else 0.
 */
function alt_fuzzy_dupe_exists($company, $date) {
    if ($company === '' || !preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
        return 0;
    }
    $key = alt_company_key($company);
    if ($key === '') return 0;

    $lo = gmdate('Y-m-d', strtotime($date . ' 00:00:00 UTC') - 30 * DAY_IN_SECONDS);
    $hi = gmdate('Y-m-d', strtotime($date . ' 00:00:00 UTC') + 30 * DAY_IN_SECONDS);
    $ids = get_posts(array(
        'post_type' => 'layoffs', 'post_status' => 'publish', 'posts_per_page' => 200,
        'fields' => 'ids', 'no_found_rows' => true,
        'meta_query' => array(array(
            'key' => 'layoff_date', 'value' => array($lo, $hi),
            'compare' => 'BETWEEN', 'type' => 'DATE',
        )),
    ));
    foreach ($ids as $id) {
        if (alt_company_key((string) get_post_meta($id, 'company_name', true)) === $key) {
            return (int) $id;
        }
    }
    return 0;
}

/**
 * Canonicalize country names: "US"/"USA" -> "United States", "UK" -> "United
 * Kingdom", and vague regions or multi-country phrases ("Global", "Europe",
 * "North America", "India and US") -> "Multiple countries", because splitting
 * one event across countries would double-count the jobs. Unknown single
 * countries are returned unchanged (never lose data).
 */
function alt_normalize_country($name) {
    $raw = trim((string) $name);
    if ($raw === '') return '';
    $k = strtolower(trim(preg_replace('/\s+/', ' ', preg_replace('/[^a-z ]/i', '', $raw))));

    // Real single countries whose names contain "and" (or "&") — must be
    // recognized BEFORE the multi-country heuristics below.
    $and_countries = array(
        'trinidad and tobago' => 'Trinidad and Tobago',
        'bosnia and herzegovina' => 'Bosnia and Herzegovina',
        'antigua and barbuda' => 'Antigua and Barbuda',
        'saint kitts and nevis' => 'Saint Kitts and Nevis',
        'st kitts and nevis' => 'Saint Kitts and Nevis',
        'saint vincent and the grenadines' => 'Saint Vincent and the Grenadines',
        'sao tome and principe' => 'Sao Tome and Principe',
        'turks and caicos islands' => 'Turks and Caicos Islands',
        'turks and caicos' => 'Turks and Caicos Islands',
    );
    if (isset($and_countries[$k])) return $and_countries[$k];

    $map = array(
        'us' => 'United States', 'usa' => 'United States', 'united states' => 'United States',
        'united states of america' => 'United States', 'america' => 'United States',
        'u s' => 'United States', 'u s a' => 'United States',
        'uk' => 'United Kingdom', 'united kingdom' => 'United Kingdom', 'britain' => 'United Kingdom',
        'great britain' => 'United Kingdom', 'england' => 'United Kingdom',
        'uae' => 'UAE', 'united arab emirates' => 'UAE', 'deutschland' => 'Germany',
        // Regions / multi-country phrases: one honest bucket, no double counting
        'global' => 'Multiple countries', 'worldwide' => 'Multiple countries',
        'international' => 'Multiple countries', 'europe' => 'Multiple countries',
        'north america' => 'Multiple countries', 'south america' => 'Multiple countries',
        'latin america' => 'Multiple countries', 'asia' => 'Multiple countries',
        'asia pacific' => 'Multiple countries', 'apac' => 'Multiple countries',
        'emea' => 'Multiple countries', 'multiple' => 'Multiple countries',
        'multiple countries' => 'Multiple countries', 'various' => 'Multiple countries',
    );
    if (isset($map[$k])) return $map[$k];
    // "India and US", "US, UK and Canada", "UK/Germany" — multi-country lists.
    // Delimiters are tested against the RAW value ($k already had punctuation
    // stripped, which would make the , / & checks dead code).
    if (preg_match('/(,|\/|&|\+|\bplus\b)/i', $raw) || preg_match('/\band\b/', $k)) {
        return 'Multiple countries';
    }
    return $raw;
}

/**
 * Map freeform extracted industry strings onto a fixed taxonomy so the filter
 * dropdown doesn't fill with near-duplicates ("IT" vs "Information Technology",
 * "Airline" vs "Airlines", lowercase variants...). Keyword rules, checked in
 * order; unmatched values fall back to Title Case of the original.
 */
function alt_normalize_industry($value) {
    $raw = trim((string) $value);
    if ($raw === '') return '';
    $k = strtolower($raw);

    // Exact-value shortcuts that keyword rules can't safely catch
    // (a bare "it" substring would match half the alphabet).
    $exact = array('it' => 'Technology', 'ai' => 'Technology', 'ml' => 'Technology');
    if (isset($exact[$k])) return $exact[$k];

    // Order matters: specific compound sectors (biotech, fintech, edtech) must
    // be matched BEFORE the generic Technology rule, whose 'tech' keyword would
    // otherwise swallow them.
    $rules = array(
        'Healthcare & Pharma'    => array('pharma', 'biotech', 'bio-tech', 'health', 'medical', 'genomic', 'dermatolog', 'biopharma', 'life science', 'regenerative'),
        'Finance & Insurance'    => array('bank', 'fintech', 'fin-tech', 'insurtech', 'financ', 'insurance', 'investment', 'crypto', 'payments', 'lending', 'mortgage'),
        'Education'              => array('education', 'university', 'school', 'edtech', 'ed-tech', 'learning'),
        'Aerospace & Defense'    => array('aerospace', 'defense', 'aviation product'),
        'Airlines & Travel'      => array('airline', 'air travel', 'travel', 'cruise'),
        'Automotive'             => array('automotive', 'auto', 'electric vehicle', 'ev', 'used car', 'car marketplace', 'car dealer'),
        'Technology'             => array('artificial intelligence', 'ai/', 'robotic', 'software', 'cloud', 'cyber', 'saas', 'semiconductor', 'chip', 'information technology', 'tech', 'internet', 'computing', 'data center', 'it services'),
        'Telecom'                => array('telecom', 'broadband', 'connectivity', 'wireless'),
        'Media & Entertainment'  => array('media', 'broadcast', 'radio', 'news', 'entertainment', 'gaming', 'game', 'streaming', 'publishing', 'film'),
        'Retail & E-commerce'    => array('retail', 'e-commerce', 'ecommerce', 'grocery', 'apparel', 'fashion'),
        'Food & Hospitality'     => array('hospitality', 'hotel', 'restaurant', 'food', 'beverage'),
        'Energy'                 => array('energy', 'oil', 'gas', 'coal', 'solar', 'nuclear', 'renewable', 'utilit'),
        'Logistics & Transport'  => array('logistic', 'transport', 'trucking', 'shipping', 'freight', 'rail', 'delivery', 'supply chain'),
        'Real Estate & Construction' => array('real estate', 'construction', 'reit', 'housing', 'property'),
        'Manufacturing'          => array('manufactur', 'industrial', 'paper', 'containerboard', 'steel', 'chemical', 'machinery', 'production'),
        'Consumer Goods'         => array('consumer', 'cannabis', 'cbd', 'household', 'cosmetic', 'toy'),
        'Professional Services'  => array('consult', 'professional', 'legal', 'accounting', 'staffing', 'recruit', 'hr', 'scientific and technical'),
        'Agriculture'            => array('agricultur', 'farm'),
        'Government & Nonprofit' => array('government', 'public sector', 'nonprofit', 'non-profit'),
    );

    foreach ($rules as $canonical => $keywords) {
        foreach ($keywords as $kw) {
            // Short keywords match on word boundaries only, so 'oil' can't hit
            // 'Boiler', 'gas' can't hit 'Gastroenterology', 'rail' 'Trailer'...
            if (strlen($kw) <= 4) {
                if (preg_match('/\b' . preg_quote($kw, '/') . '\b/', $k)) return $canonical;
            } elseif (strpos($k, $kw) !== false) {
                return $canonical;
            }
        }
    }
    return ucwords($k);
}

/**
 * Return a 2-letter US state code, or '' if not a recognizable US state.
 * Accepts codes ("ca") or full names ("California").
 */
function alt_normalize_state($value) {
    $v = trim((string) $value);
    if ($v === '') return '';
    $abbr = array('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL',
        'IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV',
        'NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX',
        'UT','VT','VA','WA','WV','WI','WY','DC');
    $up = preg_replace('/[^A-Z]/', '', strtoupper($v));
    if (in_array($up, $abbr, true)) return $up;
    $names = array(
        'alabama'=>'AL','alaska'=>'AK','arizona'=>'AZ','arkansas'=>'AR','california'=>'CA',
        'colorado'=>'CO','connecticut'=>'CT','delaware'=>'DE','florida'=>'FL','georgia'=>'GA',
        'hawaii'=>'HI','idaho'=>'ID','illinois'=>'IL','indiana'=>'IN','iowa'=>'IA','kansas'=>'KS',
        'kentucky'=>'KY','louisiana'=>'LA','maine'=>'ME','maryland'=>'MD','massachusetts'=>'MA',
        'michigan'=>'MI','minnesota'=>'MN','mississippi'=>'MS','missouri'=>'MO','montana'=>'MT',
        'nebraska'=>'NE','nevada'=>'NV','new hampshire'=>'NH','new jersey'=>'NJ','new mexico'=>'NM',
        'new york'=>'NY','north carolina'=>'NC','north dakota'=>'ND','ohio'=>'OH','oklahoma'=>'OK',
        'oregon'=>'OR','pennsylvania'=>'PA','rhode island'=>'RI','south carolina'=>'SC',
        'south dakota'=>'SD','tennessee'=>'TN','texas'=>'TX','utah'=>'UT','vermont'=>'VT',
        'virginia'=>'VA','washington'=>'WA','west virginia'=>'WV','wisconsin'=>'WI','wyoming'=>'WY',
        'district of columbia'=>'DC','washington dc'=>'DC',
    );
    $key = trim(preg_replace('/\s+/', ' ', str_replace('.', '', strtolower($v))));
    return isset($names[$key]) ? $names[$key] : '';
}

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

function alt_hash_exists($hash) {
    $query = new WP_Query(array(
        'post_type'      => 'layoffs',
        'post_status'    => 'any',
        'meta_key'       => 'dedup_hash',
        'meta_value'     => $hash,
        'fields'         => 'ids',
        'posts_per_page' => 1,
        'no_found_rows'  => true,
    ));
    return $query->have_posts();
}

function alt_entry_to_array($post_id) {
    $tags = get_post_meta($post_id, 'reason_tags', true);
    if (!is_array($tags)) {
        $tags = ($tags === '' || $tags === false || $tags === null) ? array() : (array) $tags;
    }

    $ticker      = (string) get_post_meta($post_id, 'ticker', true);
    $ai_language = (string) get_post_meta($post_id, 'ai_language', true);

    return array(
        'id'                 => (int) $post_id,
        'company_name'       => (string) get_post_meta($post_id, 'company_name', true),
        'ticker'             => $ticker !== '' ? $ticker : null,
        'job_count'          => (int) get_post_meta($post_id, 'job_count', true),
        'layoff_date'        => (string) get_post_meta($post_id, 'layoff_date', true),
        'industry'           => (string) get_post_meta($post_id, 'industry', true),
        'country'            => (string) get_post_meta($post_id, 'country', true),
        'state'              => (string) get_post_meta($post_id, 'state', true),
        'roles'              => (string) get_post_meta($post_id, 'roles', true),
        'source_type'        => (string) get_post_meta($post_id, 'source_type', true),
        'source_name'        => (string) get_post_meta($post_id, 'source_name', true),
        'verification_level' => (string) get_post_meta($post_id, 'verification_level', true),
        'source_url'         => (string) get_post_meta($post_id, 'source_url', true),
        'ai_explicit'        => (bool) get_post_meta($post_id, 'ai_explicit', true),
        'ai_language'        => $ai_language !== '' ? $ai_language : null,
        'reason_tags'        => array_values(array_map('strval', $tags)),
        'excerpt'            => (string) get_post_meta($post_id, 'excerpt', true),
        'permalink'          => get_permalink($post_id),
    );
}

/**
 * All published entries, newest layoff first, cached for 5 minutes (the
 * front-end fetches this on every tracker/dashboard page view).
 *
 * Sorting happens in PHP rather than via a meta_value orderby: WP_Query's
 * meta orderby INNER JOINs on the meta key, which would silently drop posts
 * created manually in wp-admin that lack a layoff_date meta row.
 */
function alt_get_all_entries() {
    $cached = get_transient('alt_all_cache');
    if (is_array($cached)) {
        return $cached;
    }

    $query = new WP_Query(array(
        'post_type'      => 'layoffs',
        'post_status'    => 'publish',
        'posts_per_page' => -1,
        'no_found_rows'  => true,
    ));

    $rows = array();
    foreach ($query->posts as $post) {
        $rows[] = alt_entry_to_array($post->ID);
    }

    usort($rows, function ($a, $b) {
        return strcmp($b['layoff_date'], $a['layoff_date']); // undated entries sink
    });

    set_transient('alt_all_cache', $rows, 5 * MINUTE_IN_SECONDS);
    return $rows;
}

function alt_flush_caches() {
    delete_transient('alt_all_cache');
    delete_transient('alt_stats_cache');
    // Invalidate every cached /query and /aggregate response at once: their
    // cache keys embed this version, so bumping it orphans the old entries.
    update_option('alt_data_ver', (int) get_option('alt_data_ver', 1) + 1, false);
}
// Manual edits/deletes in wp-admin must also invalidate the caches
add_action('save_post_layoffs', 'alt_flush_caches');
add_action('deleted_post', 'alt_flush_caches');

/* ------------------------------------------------------------------ */
/* Route callbacks                                                     */
/* ------------------------------------------------------------------ */

function alt_api_add($request) {
    $meta_in = $request->get_param('meta');
    if (!is_array($meta_in)) {
        return new WP_Error('alt_bad_request', 'Missing "meta" object.', array('status' => 400));
    }

    $company = sanitize_text_field($meta_in['company_name'] ?? '');
    if ($company === '') {
        return new WP_Error('alt_bad_request', 'company_name is required.', array('status' => 400));
    }

    $job_count = absint($meta_in['job_count'] ?? 0);
    if ($job_count < 1) {
        return new WP_Error('alt_bad_request', 'job_count must be a positive integer.', array('status' => 400));
    }

    $layoff_date = sanitize_text_field($meta_in['layoff_date'] ?? '');
    if ($layoff_date !== '' && !preg_match('/^\d{4}-\d{2}-\d{2}$/', $layoff_date)) {
        $layoff_date = '';
    }

    $dedup_hash = strtolower(sanitize_text_field($meta_in['dedup_hash'] ?? ''));
    if (!preg_match('/^[a-f0-9]{32}$/', $dedup_hash)) {
        return new WP_Error('alt_bad_request', 'dedup_hash must be an md5 hex string.', array('status' => 400));
    }

    // Server-side dedup re-check — the Railway pre-check fails open, so this
    // is the authoritative guard against duplicates
    if (alt_hash_exists($dedup_hash)) {
        return new WP_Error('alt_duplicate', 'An entry with this dedup_hash already exists.', array('status' => 409));
    }

    // Fuzzy same-event guard: a different outlet reporting the same company's
    // layoff with a slightly different count/date shouldn't create a 2nd entry.
    // WARN notices are exempt: one company can legitimately file several within
    // 30 days (e.g. separate store closures), so they rely on the exact hash.
    $incoming_source = sanitize_text_field($meta_in['source_type'] ?? '');
    if ($incoming_source !== 'warn' && ($match_id = alt_fuzzy_dupe_exists($company, $layoff_date))) {
        // Don't discard information with the duplicate: if the incoming report
        // carries an explicit AI attribution the existing entry lacks (common
        // when a WARN filing landed first and the news explains WHY), graft the
        // AI flag + exact quote onto the existing entry before rejecting.
        if (!empty($meta_in['ai_explicit']) && !get_post_meta($match_id, 'ai_explicit', true)) {
            update_post_meta($match_id, 'ai_explicit', true);
            $quote = sanitize_text_field($meta_in['ai_language'] ?? '');
            if ($quote !== '' && (string) get_post_meta($match_id, 'ai_language', true) === '') {
                update_post_meta($match_id, 'ai_language', $quote);
            }
            $tags = (array) get_post_meta($match_id, 'reason_tags', true);
            if (!in_array('ai_automation', $tags, true)) {
                $tags[] = 'ai_automation';
                update_post_meta($match_id, 'reason_tags', array_values(array_filter($tags)));
            }
            if (function_exists('alt_db_sync_post')) alt_db_sync_post($match_id);
            alt_flush_caches();
            return new WP_Error('alt_duplicate', 'Same-company entry exists; AI attribution merged into it.', array('status' => 409));
        }
        return new WP_Error('alt_duplicate', 'A same-company entry within ~30 days already exists.', array('status' => 409));
    }

    $verification = sanitize_text_field($meta_in['verification_level'] ?? '');
    if (!in_array($verification, alt_allowed_verification_levels(), true)) {
        $verification = 'bronze';
    }

    $source_type = sanitize_text_field($meta_in['source_type'] ?? '');
    if (!in_array($source_type, alt_allowed_source_types(), true)) {
        $source_type = 'news';
    }

    $tags_in = $meta_in['reason_tags'] ?? array();
    $tags    = array();
    if (is_array($tags_in)) {
        $tags = array_values(array_intersect(
            array_map('sanitize_key', $tags_in),
            alt_allowed_reason_tags()
        ));
    }

    $title = sanitize_text_field((string) $request->get_param('title'));
    if ($title === '') {
        $title = sprintf('%s — %s jobs — %s', $company, number_format_i18n($job_count), $layoff_date);
    }

    $slug = sanitize_title($company . '-' . ($layoff_date !== '' ? $layoff_date : 'filing'));
    $post_id = wp_insert_post(array(
        'post_type'   => 'layoffs',
        'post_status' => 'publish',
        'post_title'  => $title,
        'post_name'   => $slug,
    ), true);

    if (is_wp_error($post_id)) {
        return new WP_Error('alt_insert_failed', $post_id->get_error_message(), array('status' => 500));
    }

    $meta_values = array(
        'company_name'       => $company,
        'ticker'             => sanitize_text_field($meta_in['ticker'] ?? ''),
        'job_count'          => $job_count,
        'layoff_date'        => $layoff_date,
        'industry'           => alt_normalize_industry(sanitize_text_field($meta_in['industry'] ?? '')),
        'country'            => alt_normalize_country(sanitize_text_field($meta_in['country'] ?? '')),
        'state'              => alt_normalize_state(sanitize_text_field($meta_in['state'] ?? '')),
        'roles'              => sanitize_text_field($meta_in['roles'] ?? ''),
        'source_url'         => esc_url_raw($meta_in['source_url'] ?? ''),
        'source_type'        => $source_type,
        'source_name'        => sanitize_text_field($meta_in['source_name'] ?? ''),
        'verification_level' => $verification,
        'excerpt'            => sanitize_textarea_field($meta_in['excerpt'] ?? ''),
        'reason_tags'        => $tags,
        'ai_explicit'        => !empty($meta_in['ai_explicit']),
        'ai_language'        => sanitize_text_field($meta_in['ai_language'] ?? ''),
        'dedup_hash'         => $dedup_hash,
    );
    foreach ($meta_values as $key => $value) {
        update_post_meta($post_id, $key, $value);
    }

    // Mirror into the fast-query table now that all meta is set (the save_post
    // hook fires before meta exists, so sync explicitly here).
    if (function_exists('alt_db_sync_post')) {
        alt_db_sync_post($post_id);
    }

    alt_flush_caches();

    return new WP_REST_Response(array('id' => $post_id, 'created' => true), 201);
}

function alt_api_check_duplicate($request) {
    $hash = strtolower(sanitize_text_field($request->get_param('hash')));
    return rest_ensure_response(array(
        'exists' => $hash !== '' && alt_hash_exists($hash),
    ));
}

function alt_api_all() {
    $entries = alt_get_all_entries();
    return rest_ensure_response(array(
        'generated'     => gmdate('Y-m-d\TH:i:s\Z'),
        'total_records' => count($entries),
        'data'          => $entries,
    ));
}

function alt_api_stats() {
    $cached = get_transient('alt_stats_cache');
    if (is_array($cached)) {
        return rest_ensure_response($cached);
    }

    $entries       = alt_get_all_entries();
    $current_month = current_time('Y-m');
    $current_year  = current_time('Y');

    // Current week, Monday–Sunday, in the site's timezone
    $now_ts     = current_time('timestamp');
    $dow        = (int) date('N', $now_ts);              // 1 = Mon … 7 = Sun
    $monday_ts  = strtotime('-' . ($dow - 1) . ' days', $now_ts);
    $sunday_ts  = strtotime('+6 days', $monday_ts);
    $week_start = date('Y-m-d', $monday_ts);
    $week_end   = date('Y-m-d', $sunday_ts);

    $stats = array(
        'generated'     => gmdate('Y-m-d\TH:i:s\Z'),
        'total_entries' => count($entries),
        'total_jobs'    => 0,
        'ai_entries'    => 0,
        'ai_jobs'       => 0,
        'week_entries'  => 0,
        'week_jobs'     => 0,
        'month_entries' => 0,
        'month_jobs'    => 0,
        'year_entries'  => 0,
        'year_jobs'     => 0,
        // Labels that name the actual period and roll over automatically
        'week_range'    => date('M j', $monday_ts) . ' – ' . date('M j', $sunday_ts),
        'month_label'   => current_time('F Y'),
        'year_label'    => current_time('Y'),
        'coverage_start'   => '',   // earliest layoff date on record, e.g. "Jan 2024"
        'companies_count'  => 0,
        'industries_count' => 0,
        'countries_count'  => 0,
    );

    $min_date   = '';
    $companies  = array();
    $industries = array();
    $countries  = array();
    foreach ($entries as $entry) {
        $jobs = (int) $entry['job_count'];
        $stats['total_jobs'] += $jobs;

        $cn = strtolower(trim((string) $entry['company_name']));
        if ($cn !== '') { $companies[$cn] = true; }
        if ((string) $entry['industry'] !== '') { $industries[strtolower(trim($entry['industry']))] = true; }
        if ((string) $entry['country'] !== '') { $countries[strtolower(trim($entry['country']))] = true; }

        if (!empty($entry['ai_explicit'])) {
            $stats['ai_entries']++;
            $stats['ai_jobs'] += $jobs;
        }

        $date = (string) $entry['layoff_date'];
        if ($date !== '') {
            if ($min_date === '' || $date < $min_date) {
                $min_date = $date;
            }
            // ISO dates sort lexicographically, so string comparison is a valid range check
            if ($date >= $week_start && $date <= $week_end) {
                $stats['week_entries']++;
                $stats['week_jobs'] += $jobs;
            }
            if (strpos($date, $current_month) === 0) {
                $stats['month_entries']++;
                $stats['month_jobs'] += $jobs;
            }
            if (strpos($date, $current_year) === 0) {
                $stats['year_entries']++;
                $stats['year_jobs'] += $jobs;
            }
        }
    }

    if ($min_date !== '') {
        $stats['coverage_start'] = date('M Y', strtotime($min_date));
    }
    $stats['companies_count']  = count($companies);
    $stats['industries_count'] = count($industries);
    $stats['countries_count']  = count($countries);

    $latest = get_posts(array(
        'post_type' => 'layoffs', 'post_status' => 'publish', 'posts_per_page' => 1,
        'orderby' => 'date', 'order' => 'DESC', 'fields' => 'ids', 'no_found_rows' => true,
    ));
    $stats['last_updated'] = $latest ? get_post_time('c', true, $latest[0]) : '';

    set_transient('alt_stats_cache', $stats, 5 * MINUTE_IN_SECONDS);
    return rest_ensure_response($stats);
}

function alt_api_company($request) {
    $name = sanitize_text_field(urldecode((string) $request['name']));
    if ($name === '') {
        return new WP_Error('alt_bad_request', 'Company name is required.', array('status' => 400));
    }

    $query = new WP_Query(array(
        'post_type'      => 'layoffs',
        'post_status'    => 'publish',
        'posts_per_page' => -1,
        'no_found_rows'  => true,
        'meta_query'     => array(
            array(
                'key'     => 'company_name',
                'value'   => $name,
                'compare' => 'LIKE',
            ),
        ),
    ));

    $rows = array();
    foreach ($query->posts as $post) {
        $rows[] = alt_entry_to_array($post->ID);
    }

    // Newest layoff first; empty dates sink to the bottom
    usort($rows, function ($a, $b) {
        return strcmp($b['layoff_date'], $a['layoff_date']);
    });

    return rest_ensure_response(array(
        'company'       => $name,
        'total_records' => count($rows),
        'total_jobs'    => array_sum(wp_list_pluck($rows, 'job_count')),
        'data'          => $rows,
    ));
}

/**
 * Collapse cross-outlet duplicates: same company (normalized) reported by
 * different sources within ~30 days = the same layoff event. Keeps the
 * best-sourced entry (highest verification, then highest job count), preserves
 * any AI attribution found in the cluster, and trashes the rest.
 */
function alt_api_dedupe($request) {
    $window = 30 * DAY_IN_SECONDS;
    $rank = array('gold' => 3, 'silver' => 2, 'bronze' => 1);

    $ids = get_posts(array(
        'post_type' => 'layoffs', 'post_status' => 'publish', 'posts_per_page' => -1,
        'fields' => 'ids', 'no_found_rows' => true,
    ));

    // Canonicalize country variants (US / USA → "United States", etc.) across
    // all entries. SEC 8-K filers are US registrants by definition, so a gold
    // entry with no stated country is United States.
    foreach ($ids as $id) {
        $c = (string) get_post_meta($id, 'country', true);
        $n = alt_normalize_country($c);
        if ($n === '' && get_post_meta($id, 'verification_level', true) === 'gold') {
            $n = 'United States';
        }
        if ($n !== $c) {
            update_post_meta($id, 'country', $n);
        }
    }

    $groups = array();
    foreach ($ids as $id) {
        // WARN notices are authoritative government filings; a company can file
        // several legitimately close together, so never cross-collapse them.
        if (get_post_meta($id, 'source_type', true) === 'warn') {
            continue;
        }
        $company = (string) get_post_meta($id, 'company_name', true);
        $date = (string) get_post_meta($id, 'layoff_date', true);
        if ($company === '' || !preg_match('/^\d{4}-\d{2}-\d{2}$/', $date)) {
            continue; // leave undated / unnamed entries untouched
        }
        $key = alt_company_key($company);
        if ($key === '') continue;
        $groups[$key][] = array(
            'id'      => $id,
            'ts'      => strtotime($date . ' 00:00:00 UTC'),
            'jobs'    => (int) get_post_meta($id, 'job_count', true),
            'verif'   => $rank[(string) get_post_meta($id, 'verification_level', true)] ?? 0,
            'ai'      => (bool) get_post_meta($id, 'ai_explicit', true),
            'ai_lang' => (string) get_post_meta($id, 'ai_language', true),
        );
    }

    $trashed = 0;
    $merged  = 0;
    foreach ($groups as $list) {
        if (count($list) < 2) continue;
        usort($list, function ($a, $b) { return $a['ts'] - $b['ts']; });

        // chain consecutive entries within the window into one cluster
        $cluster = array();
        $prev_ts = null;
        $flush = function ($cluster) use (&$trashed, &$merged) {
            if (count($cluster) < 2) return;
            $merged++;
            usort($cluster, function ($a, $b) {
                if ($b['verif'] !== $a['verif']) return $b['verif'] - $a['verif'];
                return $b['jobs'] - $a['jobs'];
            });
            $keeper = $cluster[0];
            if (!$keeper['ai']) {
                foreach ($cluster as $c) {
                    if ($c['ai'] && $c['ai_lang'] !== '') {
                        update_post_meta($keeper['id'], 'ai_explicit', true);
                        update_post_meta($keeper['id'], 'ai_language', $c['ai_lang']);
                        break;
                    }
                }
            }
            for ($i = 1; $i < count($cluster); $i++) {
                wp_trash_post($cluster[$i]['id']);
                $trashed++;
            }
        };
        foreach ($list as $e) {
            if ($prev_ts !== null && ($e['ts'] - $prev_ts) > $window) {
                $flush($cluster);
                $cluster = array();
            }
            $cluster[] = $e;
            $prev_ts = $e['ts'];
        }
        $flush($cluster);
    }

    alt_flush_caches();
    return rest_ensure_response(array('merged_events' => $merged, 'trashed' => $trashed));
}
