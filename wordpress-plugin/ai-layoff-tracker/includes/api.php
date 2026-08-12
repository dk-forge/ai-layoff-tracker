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

    // Operational alert: a collector reports a breakage (drift/stale) and this
    // emails the owner a specific, actionable notice. API-key gated so only the
    // pipeline can trigger it.
    register_rest_route('layoffs/v1', '/alert', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_alert',
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

    // Freshness of the Nevada WARN mirror (this host re-fetches DETR's master PDF
    // daily because Bluehost's IP clears the Akamai bot-wall that blocks CI).
    // Metadata only, safe to be public; used to confirm the mirror is current.
    register_rest_route('layoffs/v1', '/nv-mirror-status', array(
        'methods'             => 'GET',
        'callback'            => 'alt_api_nv_mirror_status',
        'permission_callback' => '__return_true',
    ));

    // Live badge status. GET is public + uncached (so the phase flips within
    // the badge's 60s poll); POST is key-protected (data jobs report phase).
    register_rest_route('layoffs/v1', '/status', array(
        array(
            'methods'             => 'GET',
            'callback'            => 'alt_api_status_get',
            'permission_callback' => '__return_true',
        ),
        array(
            'methods'             => 'POST',
            'callback'            => 'alt_api_status',
            'permission_callback' => function_exists('alt_api_permission') ? 'alt_api_permission' : '__return_false',
        ),
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
    // Every canonical event exposes all retained primary/corroborating source
    // reports. `id` is the public /query row id, not a WordPress post id.
    register_rest_route('layoffs/v1', '/event/(?P<id>\d+)/sources', array(
        'methods' => 'GET', 'callback' => 'alt_api_event_sources', 'permission_callback' => '__return_true',
    ));

    // Announced-vs-executed reconciliation — the moat product. Per employer:
    // what was ANNOUNCED (news/SEC) vs what was legally EXECUTED (WARN filings),
    // with follow-through % and announcement->execution lag. No competitor can
    // build this — it needs both tiers source-linked.
    register_rest_route('layoffs/v1', '/reconciliation', array(
        'methods' => 'GET', 'callback' => 'alt_api_reconciliation', 'permission_callback' => '__return_true',
    ));
}

/**
 * Announced (news/SEC) vs executed (WARN) per employer, for a year. Entity keys
 * are alias-normalized, so a company's global announcement and its US WARN
 * filings roll up together. Honest caveat returned inline: WARN is US-only and
 * threshold-limited, so follow-through is a FLOOR, not a completion rate — the
 * value is the relative signal + the lag, not an absolute percentage.
 */
function alt_api_reconciliation($r) {
    global $wpdb;
    $t = alt_db_table();
    $year = (int) ($r->get_param('year') ?: gmdate('Y'));
    if ($year < 2015 || $year > (int) gmdate('Y') + 2) $year = (int) gmdate('Y');
    $limit = max(1, min(200, (int) ($r->get_param('limit') ?: 60)));
    $rows = $wpdb->get_results($wpdb->prepare(
        "SELECT company_key,
                SUBSTRING_INDEX(GROUP_CONCAT(company ORDER BY job_count DESC SEPARATOR '||'), '||', 1) AS company,
                COALESCE(SUM(CASE WHEN source_type IN ('news','sec') THEN job_count END),0) AS announced_jobs,
                COALESCE(SUM(CASE WHEN source_type='warn' THEN job_count END),0) AS executed_jobs,
                MIN(CASE WHEN source_type IN ('news','sec') THEN COALESCE(announcement_date, layoff_date) END) AS first_announced,
                MIN(CASE WHEN source_type='warn' THEN layoff_date END) AS first_executed
         FROM $t
         WHERE YEAR(layoff_date) = %d AND company_key <> ''
         GROUP BY company_key
         HAVING announced_jobs > 0 AND executed_jobs > 0
         ORDER BY announced_jobs DESC
         LIMIT %d", $year, $limit), ARRAY_A);
    $out = array();
    foreach ((array) $rows as $row) {
        $ann = (int) $row['announced_jobs'];
        $exe = (int) $row['executed_jobs'];
        $lag = null;
        if (!empty($row['first_announced']) && !empty($row['first_executed'])) {
            $lag = (int) round((strtotime($row['first_executed']) - strtotime($row['first_announced'])) / DAY_IN_SECONDS);
        }
        $out[] = array(
            'company'            => $row['company'],
            'announced_jobs'     => $ann,
            'executed_warn_jobs' => $exe,
            'warn_coverage_pct'  => $ann ? round(100 * min($exe, $ann) / $ann) : null,
            'announced_date'     => $row['first_announced'] ?: null,
            'first_warn_date'    => $row['first_executed'] ?: null,
            'lag_days'           => $lag,
        );
    }
    return rest_ensure_response(array(
        'year'    => $year,
        'note'    => 'WARN is US-only and only captures large single-site filings, so warn_coverage_pct is a FLOOR, not a completion rate. Use it as a relative signal + lag, not an absolute follow-through.',
        'rows'    => $out,
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
    // Trailing geographic qualifiers name the same employer ("Oracle America" is
    // Oracle, "Amazon.com" already handled). Strip them so a US-subsidiary WARN
    // row and the parent's news event share a key for fuzzy dedup + display
    // grouping. (WARN's exact hash is unaffected; WARN rows never fuzzy-merge.)
    $k = preg_replace('/\b(america|americas|usa|us|international|global|worldwide|na)\b/', ' ', $k);
    $k = trim(preg_replace('/\s+/', ' ', $k));
    return alt_canonical_company($k);
}

/**
 * Entity resolution: fold aliases/subsidiaries/rebrands onto ONE canonical key so
 * "Alphabet" and "Google", "Meta" and "Facebook", or a subsidiary and its parent
 * dedupe as the same employer instead of two separate events (the review's
 * "Google vs Alphabet double-count"). Keyed on the already-suffix-stripped key.
 * Extend freely — every pair added prevents a class of double-count forever.
 */
function alt_canonical_company($stripped_key) {
    static $map = null;
    if ($map === null) {
        $map = array(
            'google' => 'alphabet', 'youtube' => 'alphabet', 'waymo' => 'alphabet',
            'facebook' => 'meta', 'meta platforms' => 'meta', 'instagram' => 'meta', 'whatsapp' => 'meta',
            'twitter' => 'x', 'x twitter' => 'x',
            'amazon com' => 'amazon', 'amazon web services' => 'amazon', 'aws' => 'amazon', 'twitch' => 'amazon',
            'aws amazon' => 'amazon', 'amazon fresh' => 'amazon',
            'optum' => 'unitedhealth', 'unitedhealth' => 'unitedhealth', 'unitedhealthcare' => 'unitedhealth', 'united health' => 'unitedhealth',
            'block square' => 'block', 'square' => 'block', 'cash app' => 'block',
            'linkedin' => 'microsoft', 'github' => 'microsoft', 'xbox' => 'microsoft', 'activision blizzard' => 'microsoft', 'bungie' => 'microsoft',
            'hewlett packard' => 'hp', 'hewlett-packard' => 'hp', 'hp inc' => 'hp',
            'paramount skydance' => 'paramount', 'paramount global' => 'paramount', 'cbs' => 'paramount',
            'warner bros discovery' => 'warner bros', 'wbd' => 'warner bros', 'cnn' => 'warner bros', 'hbo' => 'warner bros',
            'nbcuniversal' => 'comcast', 'nbc universal' => 'comcast', 'xfinity' => 'comcast', 'versant' => 'comcast',
            'saks fifth avenue' => 'saks', 'saks global' => 'saks', 'neiman marcus' => 'saks',
            'blueoval sk' => 'ford', 'blueoval' => 'ford', 'bosk' => 'ford',
            'ultium cells' => 'general motors', 'factory zero' => 'general motors', 'gm' => 'general motors',
            'conduent commercial' => 'conduent', 'conduent federal' => 'conduent',
            'conduent state local' => 'conduent', 'conduent business process' => 'conduent',
            'conduent education' => 'conduent', 'conduent state healthcare' => 'conduent',
            'conduent corporate' => 'conduent', 'conduent commercial solutions' => 'conduent',
            'tata consultancy services' => 'tcs',
            'bristol myers squibb' => 'bristol myers', 'bristol-myers squibb' => 'bristol myers', 'bms' => 'bristol myers',
            'alphabet' => 'alphabet', 'meta' => 'meta',
        );
    }
    return $map[$stripped_key] ?? $stripped_key;
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
 * Curated company-level industry overrides — they beat whatever sector label
 * a source supplies. Sources classify by economic activity codes and disagree
 * with common usage (Eurofound filed Booking.com under "Hotel/Restaurant" in
 * 2020/2025 but "Information/Computing" in 2018); readers expect the press
 * classification. Keys are matched as substrings of the lowercased company
 * name. Keep this list SMALL and obvious — anything debatable goes through
 * the corrections process instead.
 */
function alt_industry_override($company) {
    $overrides = apply_filters('alt_industry_overrides', array(
        'booking.com'  => 'Technology',
        'bookings.com' => 'Technology',
        'expedia'      => 'Technology',
        'airbnb'       => 'Technology',
        'tripadvisor'  => 'Technology',
    ));
    $c = strtolower((string) $company);
    foreach ($overrides as $needle => $industry) {
        if ($needle !== '' && strpos($c, $needle) !== false) return $industry;
    }
    return '';
}

/** Canonical industry label => match keywords, shared by the normalizer and vocabulary. */
function alt_industry_rules() {
    // Order matters: specific compound sectors (biotech, fintech, edtech) must
    // be matched BEFORE the generic Technology rule, whose 'tech' keyword would
    // otherwise swallow them.
    return array(
        'Healthcare & Pharma'    => array('pharma', 'biotech', 'bio-tech', 'health', 'medical', 'genomic', 'dermatolog', 'biopharma', 'life science', 'regenerative'),
        'Finance & Insurance'    => array('bank', 'fintech', 'fin-tech', 'insurtech', 'financ', 'insurance', 'investment', 'crypto', 'payments', 'lending', 'mortgage'),
        'Education'              => array('education', 'university', 'school', 'edtech', 'ed-tech', 'learning'),
        'Aerospace & Defense'    => array('aerospace', 'defense', 'aviation product'),
        'Airlines & Travel'      => array('airline', 'air travel', 'travel', 'cruise'),
        'Automotive'             => array('automotive', 'auto', 'electric vehicle', 'ev', 'used car', 'car marketplace', 'car dealer'),
        'Technology'             => array('artificial intelligence', 'ai/', 'robotic', 'software', 'cloud', 'cyber', 'saas', 'semiconductor', 'chip', 'information technology', 'tech', 'internet', 'computing', 'data center', 'it services'),
        'Telecom'                => array('telecom', 'broadband', 'connectivity', 'wireless'),
        'Media & Entertainment'  => array('media', 'broadcast', 'radio', 'news', 'entertainment', 'gaming', 'game', 'streaming', 'publishing', 'film', 'arts', 'sports'),
        'Retail & E-commerce'    => array('retail', 'e-commerce', 'ecommerce', 'grocery', 'apparel', 'fashion'),
        'Food & Hospitality'     => array('hospitality', 'hotel', 'restaurant', 'food', 'beverage'),
        // 'electric'/'electricity', extractive 'mining'/'quarrying', and 'water'/
        // 'waste' utilities all belong under Energy (were falling through to raw
        // NACE labels like "Electricity", "Mining / Quarrying", "Water / Waste").
        'Energy'                 => array('energy', 'oil', 'gas', 'coal', 'solar', 'nuclear', 'renewable', 'utilit', 'electric', 'mining', 'quarry', 'water', 'waste'),
        'Logistics & Transport'  => array('logistic', 'transport', 'trucking', 'shipping', 'freight', 'rail', 'delivery', 'supply chain'),
        'Real Estate & Construction' => array('real estate', 'construction', 'reit', 'housing', 'property'),
        'Manufacturing'          => array('manufactur', 'industrial', 'paper', 'containerboard', 'steel', 'chemical', 'machinery', 'production'),
        'Consumer Goods'         => array('consumer', 'cannabis', 'cbd', 'household', 'cosmetic', 'toy'),
        // 'administrative'/'support services' (and the source's "Adminstrative"
        // misspelling) map here instead of leaking a typo'd bucket to the filter.
        'Professional Services'  => array('consult', 'professional', 'legal', 'accounting', 'staffing', 'recruit', 'hr', 'scientific and technical', 'administrative', 'adminstrative', 'support services', 'other services'),
        'Agriculture'            => array('agricultur', 'farm'),
        // 'public administration' / British 'defence' (the combined NACE label)
        // belong with Government, not the raw "Public Administration / Defence".
        'Government & Nonprofit' => array('government', 'public sector', 'public administr', 'defence', 'nonprofit', 'non-profit'),
    );
}

/**
 * The closed set of canonical industry labels. The /industry-backfill writer
 * accepts ONLY these values: alt_normalize_industry()'s Title-Case fallback is
 * fine for source-supplied freeform sectors, but an automated classifier must
 * never mint a new label. Mirrored in railway/industry_backfill.py.
 */
function alt_industry_vocabulary() {
    return array_keys(alt_industry_rules());
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

    foreach (alt_industry_rules() as $canonical => $keywords) {
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
 * Fixed role-category vocabulary (slug => public label). Slugs are shared with
 * the Python role-extraction worker; 'unknown' is a legal STORED marker
 * ("checked, source doesn't say") but deliberately not part of this public
 * vocabulary, so it can never appear on a chart.
 */
function alt_role_categories() {
    return array(
        'engineering'          => 'Engineering & IT',
        'product_design'       => 'Product & design',
        'customer_support'     => 'Customer support & success',
        'sales_marketing'      => 'Sales & marketing',
        'hr_recruiting'        => 'HR & recruiting',
        'operations_warehouse' => 'Operations & warehouse',
        'content_trust_safety' => 'Content & trust and safety',
        'finance_admin'        => 'Finance & admin',
        'manufacturing'        => 'Manufacturing & production',
        'retail_staff'         => 'Retail staff',
    );
}

/**
 * Map the freeform "roles affected" text onto the fixed role-category
 * vocabulary. Unlike industries, one source often names SEVERAL teams
 * ("engineering, product and design"), so this returns EVERY matching
 * category. Empty/unmatched text returns an empty array — nothing is ever
 * guessed into a category (the evidence-only backfill handles rows whose
 * roles are stated only in the stored excerpt).
 */
function alt_normalize_roles($value) {
    $raw = trim((string) $value);
    if ($raw === '') return array();
    $k = strtolower($raw);
    // "People Operations" is an HR org, not logistics — rewrite the compound
    // before the generic 'operations' keyword can see it.
    $k = str_replace(array('people operations', 'people ops'), 'human resources', $k);

    $rules = array(
        'engineering'          => array('engineer', 'developer', 'software', 'programmer', 'devops', 'data scientist', 'machine learning', 'infrastructure', 'information technology', 'it staff', 'it department', 'it workers', 'technical staff', 'quality assurance', 'qa', 'it'),
        'product_design'       => array('product manag', 'product team', 'product and design', 'product, design', 'designer', 'design team', 'ux', 'ui'),
        'customer_support'     => array('customer support', 'customer service', 'customer success', 'customer care', 'customer experience', 'call center', 'call centre', 'contact center', 'contact centre', 'help desk', 'helpdesk', 'support team', 'support staff', 'support agent'),
        'sales_marketing'      => array('sales', 'marketing', 'advertis', 'business development', 'account manag', 'commercial team', 'go-to-market'),
        'hr_recruiting'        => array('human resources', 'recruit', 'talent acquisition', 'people team', 'hr'),
        'operations_warehouse' => array('operations', 'warehouse', 'logistics', 'fulfillment', 'fulfilment', 'driver', 'delivery', 'supply chain', 'distribution', 'dispatch'),
        'content_trust_safety' => array('trust and safety', 'trust & safety', 'content moderat', 'moderation', 'content review', 'content team', 'editorial', 'journalist', 'newsroom', 'writer', 'curation'),
        'finance_admin'        => array('finance', 'accounting', 'accountant', 'administrative', 'back office', 'back-office', 'payroll', 'legal', 'compliance', 'admin'),
        'manufacturing'        => array('manufactur', 'production worker', 'production staff', 'production line', 'assembly', 'factory', 'plant worker', 'machinist', 'fabrication'),
        'retail_staff'         => array('retail', 'store associate', 'store employee', 'store staff', 'store worker', 'cashier', 'shop floor', 'sales floor'),
    );

    $found = array();
    foreach ($rules as $canonical => $keywords) {
        foreach ($keywords as $kw) {
            // Short keywords match on word boundaries only ('it' must not hit
            // 'recruiting', 'qa' must not hit 'Qatar-adjacent' strings...).
            $hit = strlen($kw) <= 4
                ? (bool) preg_match('/\b' . preg_quote($kw, '/') . '\b/', $k)
                : strpos($k, $kw) !== false;
            if ($hit) { $found[] = $canonical; break; }
        }
    }
    return $found;
}

/**
 * US state code => display name. The INVERSE of alt_normalize_state().
 *
 * One definition, because two lists drift and this one already had three
 * copies: page-press.php carried two byte-identical inline arrays and the
 * facet pages needed a third. It is the source of the state page slugs
 * (`/state-layoffs/california/`), so an edit here moves a live URL — the codes
 * are the stored values and must not be renamed, and DC is spelled the way the
 * press page has always spelled it.
 */
function alt_us_state_names() {
    return array(
        'AL'=>'Alabama','AK'=>'Alaska','AZ'=>'Arizona','AR'=>'Arkansas','CA'=>'California',
        'CO'=>'Colorado','CT'=>'Connecticut','DE'=>'Delaware','DC'=>'Washington, D.C.',
        'FL'=>'Florida','GA'=>'Georgia','HI'=>'Hawaii','ID'=>'Idaho','IL'=>'Illinois',
        'IN'=>'Indiana','IA'=>'Iowa','KS'=>'Kansas','KY'=>'Kentucky','LA'=>'Louisiana',
        'ME'=>'Maine','MD'=>'Maryland','MA'=>'Massachusetts','MI'=>'Michigan','MN'=>'Minnesota',
        'MS'=>'Mississippi','MO'=>'Missouri','MT'=>'Montana','NE'=>'Nebraska','NV'=>'Nevada',
        'NH'=>'New Hampshire','NJ'=>'New Jersey','NM'=>'New Mexico','NY'=>'New York',
        'NC'=>'North Carolina','ND'=>'North Dakota','OH'=>'Ohio','OK'=>'Oklahoma','OR'=>'Oregon',
        'PA'=>'Pennsylvania','RI'=>'Rhode Island','SC'=>'South Carolina','SD'=>'South Dakota',
        'TN'=>'Tennessee','TX'=>'Texas','UT'=>'Utah','VT'=>'Vermont','VA'=>'Virginia',
        'WA'=>'Washington','WV'=>'West Virginia','WI'=>'Wisconsin','WY'=>'Wyoming',
    );
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

function alt_table_layoff_id_for_hash($hash) {
    global $wpdb;
    if (!function_exists('alt_db_table')) return 0;
    return (int) $wpdb->get_var($wpdb->prepare("SELECT id FROM " . alt_db_table() . " WHERE dedup_hash = %s", $hash));
}

function alt_api_event_sources(WP_REST_Request $request) {
    $id = (int) $request->get_param('id');
    if (!$id || !function_exists('alt_event_sources_for_layoff')) {
        return new WP_Error('alt_not_found', 'Event not found.', array('status' => 404));
    }
    return rest_ensure_response(array('layoff_id' => $id, 'sources' => alt_event_sources_for_layoff($id)));
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
        'employer_country'   => (string) get_post_meta($post_id, 'employer_country', true),
        'state'              => (string) get_post_meta($post_id, 'state', true),
        'roles'              => (string) get_post_meta($post_id, 'roles', true),
        'source_type'        => (string) get_post_meta($post_id, 'source_type', true),
        'source_name'        => (string) get_post_meta($post_id, 'source_name', true),
        'verification_level' => (string) get_post_meta($post_id, 'verification_level', true),
        'source_url'         => (string) get_post_meta($post_id, 'source_url', true),
        'ai_explicit'        => (bool) get_post_meta($post_id, 'ai_explicit', true),
        'ai_causation'       => alt_normalize_ai_causation(get_post_meta($post_id, 'ai_causation', true)),
        'confidence'         => min(100, max(0, (int) get_post_meta($post_id, 'confidence', true))),
        'review_status'      => alt_normalize_review_status(get_post_meta($post_id, 'review_status', true)),
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
    delete_transient('alt_faq_numbers'); // server-rendered FAQ figures
    delete_transient('alt_coverage_counts'); // intro line country/state counts
    // Real "last data changed" timestamp, for the live badge.
    update_option('alt_last_write', time(), false);
    // Invalidate every cached /query and /aggregate response at once: their
    // cache keys embed this version, so bumping it orphans the old entries.
    update_option('alt_data_ver', (int) get_option('alt_data_ver', 1) + 1, false);
    // Announce the change to IndexNow (Bing/ChatGPT search, Yandex). The
    // listener throttles to once a day and never blocks the request.
    do_action('alt_data_written');
}
// Manual edits/deletes in wp-admin must also invalidate the caches
add_action('save_post_layoffs', 'alt_flush_caches');
add_action('deleted_post', 'alt_flush_caches');

/**
 * Pipeline status for the live badge. Data jobs POST their phase when they
 * start; the phase auto-expires to "live" after 50 minutes so a missed
 * end-call never leaves the badge stuck. Phases: "refreshing" (pulling new
 * filings/notices/news) and "cleaning" (dedup + fact-check).
 */
/**
 * Honest "data last updated" label = the timestamp of the last ACTUAL write to
 * the table (set on every ingest via alt_last_write), NOT the page-render time.
 * Returns '' if nothing has ever been written. Used on the report/press/sources
 * pages so a reader can spot-check that the data genuinely moved.
 */
function alt_data_last_updated_label() {
    $ts = (int) get_option('alt_last_write', 0);
    if ($ts <= 0) return '';
    try {
        return (new DateTime('@' . $ts))->setTimezone(new DateTimeZone('America/New_York'))
            ->format('M j, Y · g:i A T');
    } catch (Exception $e) {
        return '';
    }
}

function alt_pipeline_phase() {
    $s = get_option('alt_pipeline_status');
    if (!is_array($s) || empty($s['at']) || (time() - (int) $s['at']) > 50 * MINUTE_IN_SECONDS) {
        return array('phase' => 'live', 'at' => (int) get_option('alt_last_write', 0));
    }
    return array('phase' => $s['phase'], 'at' => (int) $s['at']);
}
function alt_api_status(WP_REST_Request $r) {
    $phase = sanitize_key((string) $r->get_param('phase'));
    if (!in_array($phase, array('refreshing', 'cleaning', 'live'), true)) {
        return new WP_Error('alt_bad_request', 'phase must be refreshing|cleaning|live', array('status' => 400));
    }
    update_option('alt_pipeline_status', array('phase' => $phase, 'at' => time()), false);
    return rest_ensure_response(array('phase' => $phase));
}
function alt_api_status_get() {
    $ph = alt_pipeline_phase();
    $last = (int) get_option('alt_last_write', 0);
    $resp = rest_ensure_response(array(
        'version'        => ALT_VERSION,                         // running plugin version (cache-immune deploy probe)
        'pipeline_phase' => $ph['phase'],                        // live | refreshing | cleaning
        'pipeline_since' => $ph['at'] ? gmdate('c', $ph['at']) : '',
        'last_updated'   => $last ? gmdate('c', $last) : '',
    ));
    $resp->header('Cache-Control', 'no-store, max-age=0');
    return $resp;
}

/* ------------------------------------------------------------------ */
/* Route callbacks                                                     */
/* ------------------------------------------------------------------ */

/**
 * Open CI alerts, keyed on CAUSE.
 *
 * Deliberately an option and not a transient: a transient can be evicted by an
 * object cache at any moment, and an evicted "we already told them" record
 * re-sends an alert the owner has already read, while an evicted "this is open"
 * record silently swallows the RECOVERED notice. Neither failure announces
 * itself. Stored with autoload = false, so it costs nothing on normal requests.
 */
function alt_alert_state() {
    $state = get_option('alt_ci_alert_state', array());
    return is_array($state) ? $state : array();
}

function alt_alert_state_save($state) {
    // A caller looping on a mutating cause key could otherwise grow wp_options
    // without bound. Keep the newest 200 and drop the rest.
    if (count($state) > 200) {
        uasort($state, function ($a, $b) {
            return ((int) ($a['first'] ?? 0)) <=> ((int) ($b['first'] ?? 0));
        });
        $state = array_slice($state, -200, null, true);
    }
    update_option('alt_ci_alert_state', $state, false);
}

/**
 * Mail the owner that something needs a human.
 *
 * THREE CALLING SHAPES, and the difference is the whole point:
 *
 *   {subject, body}                — legacy. Suppressed by SUBJECT for 3 days.
 *                                    health_digest.py, link_check.py,
 *                                    openrouter_balance_check.py, process_tips.py.
 *   {subject, body, dedupe_key}    — an alarm is RAISED for that cause key. The
 *                                    same key stays quiet until it is resolved.
 *   {subject, body, resolve_scope} — an alarm is CLEARED. Mails once if anything
 *                                    was open under that scope, silent if not.
 *
 * WHY DEDUPE BY CAUSE RATHER THAN BY RUN. On 2026-07-30 one assertion (Spirit
 * Airlines counting 11,069 jobs instead of ~7,069) reddened CI eight consecutive
 * times in an afternoon. Eight identical emails would have taught the owner to
 * filter this sender, which recreates the original problem — an alarm nobody
 * reads — in a new form. This repo has already paid for that lesson once: a
 * `newsapi` staleness alarm sat at a 2-day ceiling over a WEEKLY job, so it read
 * red five days in seven forever, and that un-clearable amber was the ONLY thing
 * ops_status showed on the day Spirit was live and wrong.
 *
 * The caller normalises run-to-run numbers out of the message before hashing it,
 * so 11,069 and 11,071 are one cause and mail once, while a genuinely different
 * assertion mails immediately.
 *
 * AND IT CLEARS. `resolve_scope` is posted on every green run, so a fixed
 * breakage says so exactly once. That is what lets the owner stop worrying
 * without going and checking, which is the actual ask.
 */
function alt_api_alert($request) {
    $subject = sanitize_text_field((string) $request->get_param('subject'));
    $body    = (string) $request->get_param('body');
    if ($subject === '' || trim($body) === '') {
        return new WP_REST_Response(array('ok' => false, 'error' => 'subject and body required'), 400);
    }

    $to      = defined('ALT_CONTACT_TO') ? ALT_CONTACT_TO : get_option('admin_email');
    $dedupe  = sanitize_text_field((string) $request->get_param('dedupe_key'));
    $resolve = sanitize_text_field((string) $request->get_param('resolve_scope'));
    $safe    = '/^[a-z0-9][a-z0-9:._-]{0,159}$/';

    // ---- RECOVERY -------------------------------------------------------
    if ($resolve !== '') {
        if (!preg_match($safe, $resolve)) {
            return new WP_REST_Response(array('ok' => false, 'error' => 'bad resolve_scope'), 400);
        }
        $state = alt_alert_state();
        $open  = array();
        foreach ($state as $k => $v) {
            if (strpos($k, $resolve . ':') === 0) { $open[] = $k; }
        }
        if (!$open) {
            // The overwhelmingly common case: a green run of something that was
            // already green. Silence here is what makes it safe to post a
            // resolve on EVERY success without the clear becoming noise itself.
            return new WP_REST_Response(array('ok' => true, 'sent' => false,
                'reason' => 'nothing was open for this scope'), 200);
        }
        $extra = "\n\nThis clears " . count($open) . " open alert(s):\n";
        foreach ($open as $k) {
            $extra .= '  - ' . (string) ($state[$k]['subject'] ?? $k) . "\n";
        }
        $sent = wp_mail($to, '[AI Layoff Tracker] ' . $subject,
                        wp_strip_all_tags($body . $extra));
        // Cleared whether or not the mail landed. The flag answers "is there an
        // unresolved failure", and the answer is now no; leaving it open would
        // suppress the NEXT genuine alert for this cause, which is the more
        // expensive mistake of the two.
        foreach ($open as $k) { unset($state[$k]); }
        alt_alert_state_save($state);
        return new WP_REST_Response(array('ok' => (bool) $sent, 'sent' => (bool) $sent,
            'cleared' => count($open)), 200);
    }

    // ---- CAUSE-KEYED ALARM ----------------------------------------------
    if ($dedupe !== '') {
        if (!preg_match($safe, $dedupe)) {
            return new WP_REST_Response(array('ok' => false, 'error' => 'bad dedupe_key'), 400);
        }
        $state = alt_alert_state();
        $now   = time();
        $first = $now;
        if (isset($state[$dedupe])) {
            $first = (int) ($state[$dedupe]['first'] ?? $now);
            $last  = (int) ($state[$dedupe]['last'] ?? $first);
            if (($now - $last) < 14 * DAY_IN_SECONDS) {
                return new WP_REST_Response(array('ok' => true, 'sent' => false,
                    'reason' => 'suppressed: this exact cause is already open (raised '
                                . human_time_diff($first, $now) . ' ago)'), 200);
            }
            // One reminder a fortnight, no more. Total silence until a green run
            // would mean a breakage the owner missed once is never mentioned
            // again; twice a month is a reminder, not alarm fatigue.
            $subject = 'STILL FAILING: ' . $subject;
        }
        $sent = wp_mail($to, '[AI Layoff Tracker] ' . $subject, wp_strip_all_tags($body));
        if ($sent) {
            // Only recorded on a successful send. An alarm that was never
            // delivered is not "already reported" — the next failure must retry.
            $state[$dedupe] = array('first' => $first, 'last' => $now, 'subject' => $subject);
            alt_alert_state_save($state);
        }
        return new WP_REST_Response(array('ok' => (bool) $sent, 'sent' => (bool) $sent), 200);
    }

    // ---- LEGACY: suppress by subject for 3 days --------------------------
    $key = 'alt_alert_' . md5($subject);
    if (get_transient($key)) {
        return new WP_REST_Response(array('ok' => true, 'sent' => false, 'reason' => 'suppressed (alerted within 3 days)'), 200);
    }
    $sent = wp_mail($to, '[AI Layoff Tracker] ' . $subject, wp_strip_all_tags($body));
    if ($sent) {
        set_transient($key, 1, 3 * DAY_IN_SECONDS);
    }
    return new WP_REST_Response(array('ok' => (bool) $sent, 'sent' => (bool) $sent), 200);
}

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
        // The event is already counted, but this may be a distinct article or
        // filing. Retain that evidence on the canonical event before telling
        // the ingest worker it is a duplicate.
        $existing_row = alt_table_layoff_id_for_hash($dedup_hash);
        if ($existing_row && function_exists('alt_event_register_report_for_layoff')) {
            alt_event_register_report_for_layoff($existing_row, $meta_in);
        }
        return new WP_Error('alt_duplicate', 'An entry with this dedup_hash already exists.', array('status' => 409));
    }

    // Editorially removed/corrected entries stay removed: reject before a CPT
    // post is created (the table-level guard alone would leave an orphan post).
    if (function_exists('alt_is_suppressed') && alt_is_suppressed($dedup_hash)) {
        return new WP_Error('alt_suppressed', 'This entry was editorially removed or corrected; the import must not re-create it.', array('status' => 409));
    }

    // Fuzzy same-event guard: a different outlet reporting the same company's
    // layoff with a slightly different count/date shouldn't create a 2nd entry.
    // WARN notices are exempt: one company can legitimately file several within
    // 30 days (e.g. separate store closures), so they rely on the exact hash.
    $incoming_source = sanitize_text_field($meta_in['source_type'] ?? '');
    if ($incoming_source !== 'warn' && ($match_id = alt_fuzzy_dupe_exists($company, $layoff_date))) {
        global $wpdb;
        $existing_row = (int) $wpdb->get_var($wpdb->prepare("SELECT id FROM " . alt_db_table() . " WHERE post_id = %d", $match_id));
        if ($existing_row && function_exists('alt_event_register_report_for_layoff')) {
            alt_event_register_report_for_layoff($existing_row, $meta_in);
        }
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

    // Zombie/rebadge guard: content farms republish OLD layoffs stamped with a
    // fresh date (Zoom's Feb-2023 "1,300 / 15%" resurfaced labeled "Feb 2026").
    // Same company + IDENTICAL count as an entry >180 days older is almost never
    // a new event, so reject loudly — a fake receipt must not enter the dataset.
    // Genuine repeat rounds nearly always differ in count; a true identical-count
    // recurrence can still be added via /edit after human review. WARN is exempt
    // (legal filings carry authoritative dates and repeat counts legitimately).
    if ($incoming_source !== 'warn' && $job_count > 0) {
        global $wpdb;
        $alt_prior = $wpdb->get_var($wpdb->prepare(
            "SELECT layoff_date FROM " . alt_db_table() .
            " WHERE company_key = %s AND job_count = %d AND layoff_date < DATE_SUB(%s, INTERVAL 180 DAY)"
            . " ORDER BY layoff_date DESC LIMIT 1",
            alt_company_key($company), (int) $job_count, $layoff_date));
        if ($alt_prior) {
            return new WP_Error('alt_rebadge_suspect',
                sprintf('Same company with identical count (%d) already recorded on %s; likely a republished old event, not a new one.', (int) $job_count, $alt_prior),
                array('status' => 409));
        }
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
        $title = sprintf('%s: %s jobs (%s)', $company, number_format_i18n($job_count), $layoff_date);
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

    $ai_causation = alt_normalize_ai_causation($meta_in['ai_causation'] ?? 'unknown');
    $ai_quote = sanitize_text_field($meta_in['ai_language'] ?? '');
    // Third-party writers can call /add, so retain the same minimum invariant
    // as the Python extractor: no causal AI claim without evidence text.
    if (in_array($ai_causation, array('primary_cause', 'contributing_cause'), true) && $ai_quote === '') {
        $ai_causation = 'unknown';
    }
    $meta_values = array(
        'company_name'       => $company,
        'ticker'             => sanitize_text_field($meta_in['ticker'] ?? ''),
        'job_count'          => $job_count,
        'job_count_max'      => max($job_count, absint($meta_in['job_count_max'] ?? $job_count)),
        'layoff_date'        => $layoff_date,
        'announcement_date'  => alt_db_valid_date((string) ($meta_in['announcement_date'] ?? '')),
        'industry'           => alt_normalize_industry(sanitize_text_field($meta_in['industry'] ?? '')),
        'country'            => alt_normalize_country(sanitize_text_field($meta_in['country'] ?? '')),
        'employer_country'   => alt_normalize_country(sanitize_text_field($meta_in['employer_country'] ?? '')),
        'employer_country_evidence' => sanitize_textarea_field($meta_in['employer_country_evidence'] ?? ''),
        'announcement_evidence' => sanitize_textarea_field($meta_in['announcement_evidence'] ?? ''),
        'state'              => alt_normalize_state(sanitize_text_field($meta_in['state'] ?? '')),
        'roles'              => sanitize_text_field($meta_in['roles'] ?? ''),
        'source_url'         => esc_url_raw($meta_in['source_url'] ?? ''),
        'source_type'        => $source_type,
        'source_name'        => sanitize_text_field($meta_in['source_name'] ?? ''),
        'verification_level' => $verification,
        'excerpt'            => sanitize_textarea_field($meta_in['excerpt'] ?? ''),
        'reason_tags'        => $tags,
        'ai_explicit'        => in_array($ai_causation, array('primary_cause', 'contributing_cause'), true),
        'ai_causation'       => $ai_causation,
        'confidence'         => min(100, max(0, (int) ($meta_in['confidence'] ?? 0))),
        'review_status'      => alt_normalize_review_status($meta_in['review_status'] ?? 'provisional'),
        'announced'          => !empty($meta_in['announced']),
        'ai_language'        => $ai_quote,
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
    if (function_exists('alt_event_register_report_for_layoff')) {
        global $wpdb;
        $layoff_id = (int) $wpdb->get_var($wpdb->prepare("SELECT id FROM " . alt_db_table() . " WHERE post_id = %d", $post_id));
        if ($layoff_id) alt_event_register_report_for_layoff($layoff_id, $meta_values);
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

// Report the freshness of the Nevada WARN mirror (see alt_nv_mirror_refresh in
// the main plugin file). Metadata only — safe to be public.
function alt_api_nv_mirror_status() {
    $path   = function_exists('alt_nv_mirror_path') ? alt_nv_mirror_path() : '';
    $exists = $path && file_exists($path);
    return rest_ensure_response(array(
        'mirror_url' => function_exists('alt_nv_mirror_url') ? alt_nv_mirror_url() : '',
        'exists'     => $exists,
        'bytes'      => $exists ? filesize($path) : 0,
        'last'       => get_option('alt_nv_mirror_status', array()),
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
        'week_range'    => date('M j', $monday_ts) . ' to ' . date('M j', $sunday_ts),
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
    $post_time = $latest ? get_post_time('U', true, $latest[0]) : 0;
    // Prefer the real last-write timestamp (covers bulk WARN/ERM imports that
    // never create a CPT post); fall back to the newest post.
    $last = max((int) get_option('alt_last_write', 0), (int) $post_time);
    $stats['last_updated'] = $last ? gmdate('c', $last) : '';
    $ph = alt_pipeline_phase();
    $stats['pipeline_phase'] = $ph['phase'];      // live | refreshing | cleaning
    $stats['pipeline_since'] = $ph['at'] ? gmdate('c', $ph['at']) : '';

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
