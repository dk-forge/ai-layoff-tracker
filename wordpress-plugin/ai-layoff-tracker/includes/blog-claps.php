<?php
/**
 * APPLAUSE ON A BLOG POST. ONE INTEGER PER ARTICLE, AND NOTHING ELSE.
 *
 * A reader taps a button at the end of an article and a number goes up. That
 * is the whole feature. What follows is why it is built the way it is, because
 * every interesting decision here is a decision about what NOT to store.
 *
 * WHY THIS IS ANONYMOUS AND AGGREGATE, AND WHY THAT IS NOT A LIMITATION.
 * The site publishes that it holds no visitor identity, and includes/subscribe.php
 * argues the same case for digest link clicks: "no subscriber id, no IP, no
 * user agent, no per-click row. Two identical clicks and two different people
 * clicking are the same event to this store, which is the point." The same
 * reasoning transfers without change. A per-reader applause store would need a
 * durable id for a stranger who never asked for one, so the reasonable design
 * is a counter that CANNOT answer "who", and the schema below is the proof of
 * that rather than a promise about it: two columns, both integers, one of them
 * a post id. There is no third column an id could be dropped into by a later
 * session in a hurry, and adding one would be an obvious edit rather than a
 * quiet one.
 *
 * WHY THE NUMBER IS PRESENTED AS APPROXIMATE, PLAINLY, ON THE PAGE.
 * There are no accounts here. Anyone can send the write request again, and the
 * only thing standing between a determined person and a large number is a
 * short-lived throttle they can outlast or spread out. So this is not a metric
 * and the copy never calls it one. It is a rough show of hands. The defences
 * below are sized to stop casual double counting (a held button, a refreshed
 * page, an impatient reader) and are honest about stopping nothing more:
 *
 *   in the browser  one reader may add at most ALT_CLAPS_READER_MAX to one
 *                   article, remembered in localStorage. That is per browser,
 *                   so it is a courtesy, not a control.
 *   per request     at most ALT_CLAPS_PER_REQUEST, enforced server side, so a
 *                   single call can never carry a large number.
 *   per connection  a transient counts increments per address per article for
 *                   five minutes. Past the ceiling the request still succeeds
 *                   and returns the true total, it just does not add. The same
 *                   shape the digest click limiter uses: rate limit the
 *                   counter, never the reader.
 *
 * THE THROTTLE KEY IS THE ONE PLACE AN ADDRESS IS TOUCHED, AND IT NEVER LANDS.
 * It is hashed, it lives in a transient with a five minute expiry, and it goes
 * nowhere near the counter table. Nothing in this file writes an address, a
 * user id, a user agent, a referrer or a timestamp to storage. If a future
 * session wants per reader numbers, the answer is accounts and consent, not a
 * fingerprint.
 *
 * WHY A CUSTOM TABLE RATHER THAN POST META.
 * Post meta would work and it is the smaller change, so it needs an argument
 * against it. Three, in order of weight. First, meta_value is LONGTEXT, so an
 * atomic `meta_value = meta_value + 1` leans on an implicit string to number
 * cast for the one operation that must never be approximate. Second, a counter
 * in meta arrives inside every get_post_meta() payload on every surface that
 * touches the post, which is exactly the shape of accident that grows a
 * "harmless" field into a record. Third, and the reason this is not a close
 * call: a two column integer table is a claim a reader can check. "No identity
 * is stored" is enforced by the schema, not by everyone remembering.
 *
 * THE INCREMENT IS ONE SQL STATEMENT, AND THE TEST PROVES IT UNDER LOAD.
 * `UPDATE ... SET claps = claps + %d WHERE post_id = %d` is resolved by the
 * database under a row lock. A read in PHP followed by a write in PHP is the
 * same feature with a race in it, and under two simultaneous taps it loses one.
 * railway/tests/test_blog_claps.py runs sixteen real processes at one row and
 * asserts the total, then runs the read-modify-write version through the same
 * harness and asserts that it LOSES counts, so the test cannot quietly stop
 * being able to detect the defect it exists for.
 *
 * THE BATCH READ EXISTS BEFORE ITS CALLER DOES, ON PURPOSE.
 * alt_claps_counts() takes a set of post ids and issues ONE query. A post
 * listing that called a single row helper in a loop would issue one query per
 * card, which is the standard way a counter becomes a performance incident on
 * an archive page. The single post render calls the batch helper with one id,
 * so there is no second code path to keep honest.
 */

if (!defined('ABSPATH')) exit;

/** Most a single request may add. A tap is one; a batch of taps is capped here. */
if (!defined('ALT_CLAPS_PER_REQUEST')) define('ALT_CLAPS_PER_REQUEST', 10);

/**
 * Most one browser may add to one article.
 *
 * 50, the number Medium settled on, and the reason to copy it is that it has
 * been read by more people than anything we would invent. It is high enough
 * that enthusiasm is not clipped (nobody taps fifty times by accident) and low
 * enough that a held button stops being a source of numbers within a second or
 * two. It is a courtesy limit in the reader's own browser, so it is worth
 * exactly what a browser side limit is ever worth, and the server side caps
 * above are what actually bound a request.
 */
if (!defined('ALT_CLAPS_READER_MAX')) define('ALT_CLAPS_READER_MAX', 50);

/** Increments one address may contribute to one article in five minutes. */
if (!defined('ALT_CLAPS_RATE_CEILING')) define('ALT_CLAPS_RATE_CEILING', 60);

function alt_claps_table() {
    global $wpdb;
    return $wpdb->prefix . 'alt_post_claps';
}

/**
 * Create the table. Idempotent, and deliberately NOT part of alt_db_install():
 * this feature owns its own storage, so the two integer columns and the comment
 * explaining them cannot drift apart across two files.
 */
function alt_claps_install() {
    global $wpdb;
    if (!function_exists('dbDelta')) {
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    }
    $charset = $wpdb->get_charset_collate();
    $table = alt_claps_table();
    // Two columns. Both integers. One of them is a post id and the other is a
    // count. There is nowhere here to record who, when, or from where, and that
    // absence is the feature. See the file header.
    dbDelta("CREATE TABLE $table (
        post_id BIGINT UNSIGNED NOT NULL,
        claps INT UNSIGNED NOT NULL DEFAULT 0,
        PRIMARY KEY (post_id)
    ) $charset;");
}

/**
 * Self-heal, the same shape alt_source_runs_table_ready() uses. An FTPS deploy
 * serves requests while files are still arriving, so a writer verifies the
 * table before using it and runs the idempotent installer if it is missing.
 * Cached per request: this must not add a SHOW TABLES to every page view.
 */
function alt_claps_table_ready() {
    global $wpdb;
    static $ready = null;
    if ($ready !== null) return $ready;
    $table = alt_claps_table();
    $exists = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table)));
    if ($exists === $table) {
        $ready = true;
        return true;
    }
    alt_claps_install();
    $ready = $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($table))) === $table;
    return $ready;
}

/**
 * Counts for a SET of posts, in ONE query.
 *
 * This is the helper a post listing calls. Returns a map of post id to integer
 * covering EVERY id asked for, so a caller never has to distinguish "no row
 * yet" from "zero claps": both are 0, because they mean the same thing to a
 * reader. Unknown ids come back as 0 rather than being dropped, which keeps the
 * caller's loop free of isset() checks.
 */
function alt_claps_counts($post_ids) {
    global $wpdb;
    $ids = array();
    foreach ((array) $post_ids as $id) {
        $id = (int) $id;
        if ($id > 0) $ids[$id] = 0;
    }
    if (!$ids) return array();
    if (!alt_claps_table_ready()) return $ids;
    // One statement for the whole set. The ids are cast to int above, so the
    // IN list is built from integers this function produced, never from input.
    $in = implode(',', array_keys($ids));
    $rows = $wpdb->get_results(
        'SELECT post_id, claps FROM ' . alt_claps_table() . ' WHERE post_id IN (' . $in . ')',
        ARRAY_A);
    foreach ((array) $rows as $row) {
        $ids[(int) $row['post_id']] = (int) $row['claps'];
    }
    return $ids;
}

/** One post's count, through the batch helper so there is one read path. */
function alt_claps_count($post_id) {
    $counts = alt_claps_counts(array($post_id));
    return (int) ($counts[(int) $post_id] ?? 0);
}

/**
 * May this id be applauded?
 *
 * The write endpoint is public because it has to be, so this is the gate that
 * decides what "a post" means, and it is deliberately narrow. A published post
 * of type `post`. Not a page, not a layoffs entry, not an attachment, not a
 * revision, not a draft, not a private post, not a password protected one. A
 * counter row for an unpublished post would also be a small disclosure: it
 * confirms an id exists before its author published it.
 */
function alt_claps_post_is_eligible($post_id) {
    $post_id = (int) $post_id;
    if ($post_id <= 0) return false;
    $post = get_post($post_id);
    if (!$post) return false;
    if ($post->post_type !== 'post') return false;
    if ($post->post_status !== 'publish') return false;
    if (!empty($post->post_password)) return false;
    return true;
}

/**
 * Add to a post's count and return the new total.
 *
 * INSERT IGNORE then UPDATE, the same two steps alt_digest_track_link() uses,
 * and the split matters. The INSERT creates a row at zero and is a no-op if one
 * exists; it reads nothing and so cannot race. The INCREMENT is the single
 * statement below, resolved inside the database. Nothing in this function reads
 * the count and then writes a number PHP computed.
 */
function alt_claps_add($post_id, $amount) {
    global $wpdb;
    $post_id = (int) $post_id;
    $amount = (int) $amount;
    if ($amount < 1) $amount = 1;
    if ($amount > ALT_CLAPS_PER_REQUEST) $amount = ALT_CLAPS_PER_REQUEST;
    if (!alt_claps_table_ready()) return alt_claps_count($post_id);
    $table = alt_claps_table();
    $wpdb->query($wpdb->prepare(
        'INSERT IGNORE INTO ' . $table . ' (post_id, claps) VALUES (%d, 0)', $post_id));
    $wpdb->query($wpdb->prepare(
        'UPDATE ' . $table . ' SET claps = claps + %d WHERE post_id = %d', $amount, $post_id));
    return alt_claps_count($post_id);
}

/**
 * The per connection throttle.
 *
 * Returns true when this request may count. The key is a hash of the address
 * and the post id, held in a transient for five minutes and never written
 * anywhere durable, exactly as the digest click limiter does it. Past the
 * ceiling the caller still gets a real answer, the tap simply does not add.
 */
function alt_claps_may_count($post_id) {
    $ip = (string) ($_SERVER['REMOTE_ADDR'] ?? '');
    $key = 'alt_clap_' . md5($ip . '|' . (int) $post_id);
    $hits = (int) get_transient($key);
    set_transient($key, $hits + 1, 5 * MINUTE_IN_SECONDS);
    return $hits < ALT_CLAPS_RATE_CEILING;
}

/**
 * POST /layoffs/v1/clap
 *
 * The only public write in this plugin, and the only thing it can write is one
 * integer going up on one row. There is no parameter that names a column, a
 * table or a value to store, and there is no sibling route: `id` selects a
 * published post and `n` is clamped to a small ceiling before it reaches SQL.
 */
function alt_api_clap($request) {
    $post_id = (int) $request->get_param('id');
    if (!alt_claps_post_is_eligible($post_id)) {
        return new WP_Error('alt_clap_bad_post', 'That is not a published post.',
                            array('status' => 404));
    }
    $amount = (int) $request->get_param('n');
    if ($amount < 1) $amount = 1;
    if ($amount > ALT_CLAPS_PER_REQUEST) $amount = ALT_CLAPS_PER_REQUEST;

    if (!alt_claps_may_count($post_id)) {
        $resp = new WP_REST_Response(array(
            'post_id' => $post_id,
            'claps'   => alt_claps_count($post_id),
            'counted' => false,
        ), 200);
        $resp->header('Cache-Control', 'no-store');
        return $resp;
    }
    $total = alt_claps_add($post_id, $amount);
    $resp = new WP_REST_Response(array(
        'post_id' => $post_id,
        'claps'   => (int) $total,
        'counted' => true,
    ), 200);
    $resp->header('Cache-Control', 'no-store');
    return $resp;
}

function alt_claps_register_routes() {
    register_rest_route('layoffs/v1', '/clap', array(
        'methods'             => 'POST',
        'callback'            => 'alt_api_clap',
        // Public by necessity: readers are anonymous and the page is cached, so
        // there is no session to gate on and a nonce would be stale HTML. What
        // bounds this route is the eligibility check, the per request cap and
        // the per connection throttle above, not a credential.
        'permission_callback' => '__return_true',
        'args' => array(
            'id' => array('required' => true, 'type' => 'integer'),
            'n'  => array('required' => false, 'type' => 'integer'),
        ),
    ));
}
add_action('rest_api_init', 'alt_claps_register_routes');

/** "1 clap" / "12 claps", so the label is never wrong for one. */
function alt_claps_label($count) {
    $count = (int) $count;
    return $count === 1 ? 'clap' : 'claps';
}

/**
 * The control itself.
 *
 * WITHOUT JAVASCRIPT THE PAGE IS STILL RIGHT. The count is server rendered
 * text, so it reads correctly with scripting off, and the button ships
 * `disabled`. An enabled button that silently does nothing is the worse
 * failure: a screen reader announces it as available and a reader taps it
 * twice. blog-claps.js removes the attribute on load, so the control is
 * enabled exactly when it can work.
 */
function alt_claps_render($post_id) {
    $post_id = (int) $post_id;
    if (!alt_claps_post_is_eligible($post_id)) return '';
    $count = alt_claps_count($post_id);
    $label = alt_claps_label($count);
    $out  = '<div class="alt-clap" data-alt-clap data-post="' . esc_attr($post_id) . '"'
          . ' data-max="' . esc_attr(ALT_CLAPS_READER_MAX) . '"'
          . ' data-per-request="' . esc_attr(ALT_CLAPS_PER_REQUEST) . '">';
    $out .= '<button type="button" class="alt-clap-btn" data-alt-clap-btn disabled'
          . ' aria-describedby="alt-clap-note-' . esc_attr($post_id) . '">';
    // Decorative: a hand and three motion marks. Inline, so there is no image
    // request, no icon font and no third party host. The promise on the site is
    // no images and no tracking pixels, and an icon fetched from anywhere is
    // both a request and a log line on someone else's server.
    $out .= '<svg class="alt-clap-icon" viewBox="0 0 24 24" width="20" height="20"'
          . ' aria-hidden="true" focusable="false">'
          . '<g fill="none" stroke="currentColor" stroke-width="1.6"'
          . ' stroke-linecap="round" stroke-linejoin="round">'
          . '<path d="M8.6 13.1V5.4a1.3 1.3 0 0 1 2.6 0v5.9"/>'
          . '<path d="M11.2 11.3V4.3a1.3 1.3 0 0 1 2.6 0v7"/>'
          . '<path d="M13.8 11.5V5.8a1.3 1.3 0 0 1 2.6 0v6.6"/>'
          . '<path d="M16.4 12.4V8.6a1.3 1.3 0 0 1 2.6 0v6.1c0 3.1-2.2 5.3-5.3 5.3h-1.3'
          . 'c-1.9 0-3.1-.8-4-2.2l-2.5-4.3a1.3 1.3 0 0 1 2-1.6l1.6 1.6"/>'
          . '<path d="M4.7 4.3 3.5 3.1M7.3 2.7 7 1.3M2.7 7.5 1.3 7.3"/>'
          . '</g></svg>';
    $out .= '<span class="alt-clap-btn-text">Applaud</span>';
    $out .= '</button>';
    $out .= '<span class="alt-clap-count" data-alt-clap-count>'
          . '<span class="alt-clap-num" data-alt-clap-num>' . esc_html(number_format_i18n($count)) . '</span> '
          . '<span class="alt-clap-word" data-alt-clap-word>' . esc_html($label) . '</span>'
          . '</span>';
    $out .= '<p class="alt-clap-note" id="alt-clap-note-' . esc_attr($post_id) . '">'
          . 'Anonymous and approximate. We store one number for this article and nothing about you.'
          . '</p>';
    // The announcement. Empty at render, because a live region that already has
    // text says nothing when the text is replaced by the same words.
    $out .= '<p class="alt-clap-live" data-alt-clap-live role="status" aria-live="polite"></p>';
    $out .= '</div>';
    return $out;
}

/**
 * Append the control to a single blog post.
 *
 * Gated exactly as includes/subscribe-placements.php gates the signup, which in
 * turn matches how the blog stylesheet gates itself, so the three cannot
 * disagree about what an article is. Priority 24, one ahead of the signup at
 * 25, so the order down the page is article, applause, signup: the small ask
 * before the large one.
 *
 * The excerpt gate is the one that bites. get_the_excerpt() runs the_content
 * filters during wp_head to build a meta description, and without this line the
 * control would render into a summary nobody sees.
 */
function alt_claps_append_to_post($content) {
    if (is_admin() || is_feed() || is_embed()) return $content;
    if (doing_filter('get_the_excerpt')) return $content;
    if (!is_singular('post')) return $content;
    if (!in_the_loop() || !is_main_query()) return $content;
    static $placed = false;
    if ($placed) return $content;
    $placed = true;
    return $content . alt_claps_render(get_the_ID());
}
add_filter('the_content', 'alt_claps_append_to_post', 24);

/**
 * Assets, on single posts and nowhere else.
 *
 * Versioned by ALT_VERSION plus the file's own mtime, the same way
 * alt_enqueue_assets() versions the tracker's assets: a plugin version bump
 * cache-busts everything, and a file that changed without one still busts
 * itself.
 */
function alt_claps_enqueue() {
    if (!is_singular('post')) return;
    $ver = function ($rel) {
        $t = @filemtime(ALT_PLUGIN_DIR . $rel);
        return ALT_VERSION . ($t ? '.' . $t : '');
    };
    wp_enqueue_style('alt-blog-claps', ALT_PLUGIN_URL . 'assets/blog-claps.css',
                     array(), $ver('assets/blog-claps.css'));
    wp_enqueue_script('alt-blog-claps', ALT_PLUGIN_URL . 'assets/blog-claps.js',
                      array(), $ver('assets/blog-claps.js'),
                      array('in_footer' => true, 'strategy' => 'defer'));
    wp_add_inline_script('alt-blog-claps',
        'window.ALT_CLAPS_ENDPOINT = ' . wp_json_encode(rest_url('layoffs/v1/clap')) . ';',
        'before');
}
add_action('wp_enqueue_scripts', 'alt_claps_enqueue');
