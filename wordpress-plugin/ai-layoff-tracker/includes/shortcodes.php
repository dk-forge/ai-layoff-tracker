<?php
/**
 * Shortcodes:
 *   [alt_tracker]                            Full filterable results list (cards)
 *   [alt_stats_bar]                          Headline stats
 *   [alt_dashboard]                          All charts
 *   [alt_ai_tracker]                         AI displacement view
 *   [alt_company_history company="amazon"]   Per-company timeline
 *   [alt_export_buttons]                     CSV + JSON downloads
 */

if (!defined('ABSPATH')) exit;

/**
 * Render a template file with local variables, returning the output.
 */
function alt_template($file, $vars = array()) {
    $path = ALT_PLUGIN_DIR . 'templates/' . $file;
    if (!file_exists($path)) {
        return '<!-- AI Layoff Tracker: missing template ' . esc_html($file) . ' -->';
    }
    if (!empty($vars)) {
        extract($vars, EXTR_SKIP); // phpcs:ignore WordPress.PHP.DontExtract
    }
    ob_start();
    include $path;
    // The build stamp rides out with the body it belongs to, emitted once per
    // request from the funnel every plugin surface renders through. It says
    // which BYTES produced this page, which is the one thing a version string
    // cannot say: on 2.20.21 a page rendered mid-upload carried the new version
    // around the previous template and every check read green. See
    // includes/build-stamp.php.
    return alt_build_stamp_comment() . ob_get_clean();
}

function alt_shortcode_tracker() {
    $GLOBALS['alt_tracker_rendered'] = true;
    return alt_template('page-tracker.php');
}
add_shortcode('alt_tracker', 'alt_shortcode_tracker');

/*
 * DO NOT ADD A SELF-GUARD TO THESE SHORTCODES. Investigated and refused
 * 2026-07-30; refused once before on 2026-07-29. The reasoning is not "we did
 * not get to it" — it is that the obvious fix is known to break the live page.
 *
 * The tempting change is to make each shortcode render only its FIRST call, the
 * way alt_dashboard already yields to alt_tracker below. It has been tried here
 * and it took the flagship page down, twice, in three commits on 2026-07-23:
 *
 *   e277e8b (2.19.164)  define()-based once-flag, set before the emit.
 *                       The tracker never appeared on the live page: a
 *                       non-visible the_content pass claimed the single emit
 *                       into discarded output.
 *   2a4b260 (2.19.165)  fixed it the obvious way — !doing_action('wp_head')
 *                       plus set-the-flag-only-after-echo. STILL BROKEN.
 *   cd88c00 (2.19.167)  reverted both. THIS THEME RENDERS POST CONTENT DURING
 *                       wp_head, and that pass's output is what reaches the
 *                       body. So "skip the wp_head pass" suppresses the only
 *                       pass that matters, and a flag set by an earlier
 *                       discarded pass blanks the real render.
 *
 * That rules out the discriminators one would reach for: doing_action('wp_head')
 * and did_action('wp_head') are inverted here, and in_the_loop()/is_main_query()
 * are untested against a theme that renders content inside wp_head. The plugin
 * itself never re-renders (it registers no the_content/the_excerpt filter and
 * calls do_shortcode nowhere), so every extra pass comes from the theme or from
 * Rank Math / Easy Table of Contents — none of which this repo can simulate.
 * See the postmortem comment at templates/page-tracker.php:23-35.
 *
 * The hazard being guarded against is also currently ABSENT, measured: 0
 * duplicate element IDs across all 9 public pages in raw HTML and 0 in the live
 * DOM (195 id nodes, 174 bar buttons, 6 canvases). So a self-guard would be
 * prophylaxis against a hazard measured absent, carrying a failure mode measured
 * present on this exact template.
 *
 * WHAT WOULD SETTLE IT (the only thing that can — the HTML cannot distinguish
 * "rendered once" from "rendered twice, first copy discarded"): deploy a
 * counter that OBSERVES and never suppresses. Increment a request-scoped counter
 * in each shortcode callback, record current_filter() and did_action('wp_head')
 * at each call, and emit the tally as an HTML comment on the LAST shutdown hook.
 * Load the tracker page and read the comment. If it says 1, there is no pre-pass
 * on this theme and a first-render-wins guard is safe. If it says 2+, the tally
 * also names which pass came first, which is the fact every attempt so far has
 * been missing. Until that number exists, adding a guard is guessing, and the
 * downside of guessing wrong is a blank flagship page that still returns 200.
 *
 * Note the guard below carries a milder form of the same hazard already: the
 * flag is set on ENTRY to alt_tracker (line above), not after a successful emit,
 * so a discarded pre-pass would permanently suppress alt_dashboard for the rest
 * of the request. It has never bitten only because the two are not co-located on
 * any page. Do not copy this pattern to a shortcode that shares a page.
 */
function alt_shortcode_dashboard() {
    // The tracker embeds the same charts (same element IDs); rendering both on
    // one page would duplicate IDs and leave the second set dead.
    if (!empty($GLOBALS['alt_tracker_rendered'])) {
        return '<!-- alt_dashboard skipped: alt_tracker already renders these charts on this page -->';
    }
    return alt_template('page-dashboard.php');
}
add_shortcode('alt_dashboard', 'alt_shortcode_dashboard');

function alt_shortcode_ai_tracker() {
    return alt_template('page-ai-tracker.php');
}
add_shortcode('alt_ai_tracker', 'alt_shortcode_ai_tracker');

function alt_shortcode_tracker_health() {
    return alt_template('page-health.php');
}
add_shortcode('alt_tracker_health', 'alt_shortcode_tracker_health');

function alt_shortcode_publisher_tools() {
    return alt_template('page-publisher.php');
}
add_shortcode('alt_publisher_tools', 'alt_shortcode_publisher_tools');

function alt_shortcode_press_media() {
    return alt_template('page-press.php');
}
add_shortcode('alt_press_media', 'alt_shortcode_press_media');

function alt_shortcode_sources() {
    return alt_template('page-sources.php');
}
add_shortcode('alt_sources', 'alt_shortcode_sources');

function alt_shortcode_report() {
    return alt_template('page-report.php');
}
add_shortcode('alt_report', 'alt_shortcode_report');

function alt_shortcode_ai_quotes() {
    return alt_template('page-ai-quotes.php');
}
add_shortcode('alt_ai_quotes', 'alt_shortcode_ai_quotes');

function alt_shortcode_methodology() {
    return alt_template('page-methodology.php');
}
add_shortcode('alt_methodology', 'alt_shortcode_methodology');

/**
 * ONE <h1> IN THE HTML THAT LEAVES THE SERVER, not one on the screen.
 *
 * Six pages ship two <h1> elements: the block theme renders the WordPress post
 * title, and the plugin template renders its own heading below it. Since
 * 2.20.x the stylesheet hides the theme's copy (`body:has(.alt-wrap h1)
 * h1.wp-block-post-title{display:none}`), and measured live on 2026-08-13 in a
 * real browser that rule fires: the reader sees ONE heading on all six. So the
 * duplicate is not a visual defect any more. It is still a MARKUP defect, and
 * a stylesheet is the wrong place to fix markup:
 *
 *   - a consumer that does not run CSS (most feed readers, link unfurlers, the
 *     crawlers that do not render) sees two <h1> elements whose text disagrees:
 *     "Press & Media" over "Press kit and soundbites", "Methodology & Sources"
 *     over "Methodology & sources",
 *   - the rule depends on :has(), so an older engine shows the page's name
 *     twice, in two wordings, at the same size,
 *   - and a stylesheet that fails to load takes the fix with it.
 *
 * So the theme's copy is removed at the source, on exactly the pages whose
 * template supplies a heading of its own. NOTHING A READER SEES CHANGES. The
 * <title> element and the WordPress editor are untouched: this drops the
 * core/post-title BLOCK from the body, nothing else.
 *
 * WHICH COPY SURVIVES: the template's. It lives in this repository, so it is
 * reviewable and testable, and the post title lives in a database nothing here
 * can keep in step. It is also the decision the owner made by hand on
 * 2026-08-13 (2.20.24), when the press page was renamed to the name every link
 * to it uses. Demoting the template heading to <h2> instead would un-hide the
 * theme title (the :has() rule stops matching), print the page's name twice on
 * screen for the first time, and revert that rename on four pages.
 *
 * SCOPE. Three gates, because stripping a title on a page that needed it is a
 * worse defect than the one being fixed: the block must be core/post-title, the
 * request must be a singular page, and the post being rendered must BE the
 * queried page (so a post-title inside a query loop on one of our pages keeps
 * its own title). The dashboard and /report/ are absent from the list on
 * purpose: neither renders an <h1> of its own, so the theme title is the only
 * heading they have.
 */
function alt_own_h1_shortcodes() {
    return array('alt_methodology', 'alt_sources', 'alt_press_media',
                 'alt_ai_quotes', 'alt_publisher_tools', 'alt_tracker_health');
}

function alt_page_supplies_its_own_h1($post = null) {
    if ($post === null) $post = get_post();
    if (!$post || empty($post->post_content)) return false;
    foreach (alt_own_h1_shortcodes() as $shortcode) {
        if (has_shortcode($post->post_content, $shortcode)) return true;
    }
    return false;
}

function alt_drop_theme_post_title($block_content, $block) {
    if (!is_array($block) || empty($block['blockName'])) return $block_content;
    if ($block['blockName'] !== 'core/post-title') return $block_content;
    if (!is_singular()) return $block_content;
    $post = get_post();
    if (!$post || (int) $post->ID !== (int) get_queried_object_id()) return $block_content;
    if (!alt_page_supplies_its_own_h1($post)) return $block_content;
    return '';
}
add_filter('render_block', 'alt_drop_theme_post_title', 10, 2);

/**
 * THE PAGE'S NAME HAS EXACTLY ONE AUTHOR, AND IT IS THE TEMPLATE.
 *
 * Dropping the theme's <h1> (above) fixed what a reader sees in the body and
 * nothing else. The WordPress post title still drives the browser tab, the
 * og:title, the editor and any listing built from it, and on four of the six
 * pages it said something different from the heading the page renders:
 *
 *     /press/            "Press & Media"            vs "Press kit and soundbites"
 *     /methodology/      "Methodology & Sources"    vs "Methodology & sources"
 *     /publisher-tools/  "Embed the Layoff Tracker" vs "Embed the layoff tracker"
 *     /ai-quotes/        "AI layoffs, in their own words"
 *                                 vs "AI layoffs, in the employer's own words"
 *
 * The titles were typed once into the alt_ensure_*_page_once() creators and the
 * headings typed again into the templates, so the two drifted the moment either
 * was edited - which is exactly what happened on 2026-08-13, when the press
 * page was renamed to the name every link to it uses and its post title was not.
 *
 * So the heading is READ OUT OF THE TEMPLATE that renders it. The creators and
 * the title sync both call alt_template_heading(); neither carries a copy of
 * the string. There is one author for each of these six names and it is the
 * <h1> in the file next to this one.
 *
 * The reader REFUSES to guess. It takes the first <h1> in the file and returns
 * '' unless the text inside it is plain: no nested markup, no PHP. A template
 * that grows a dynamic heading, or one that is half uploaded when a hook fires
 * mid-deploy, yields nothing, and every caller treats nothing as "not yet"
 * rather than as a title.
 */
function alt_secondary_pages() {
    // page path (under the tracker parent) => template, the shortcode that page
    // must contain for this plugin to consider the page its own.
    return array(
        'ai-layoff-tracker/methodology'       => array('page-methodology.php', 'alt_methodology'),
        'ai-layoff-tracker/sources'           => array('page-sources.php', 'alt_sources'),
        'ai-layoff-tracker/press'             => array('page-press.php', 'alt_press_media'),
        'ai-layoff-tracker/ai-quotes'         => array('page-ai-quotes.php', 'alt_ai_quotes'),
        'ai-layoff-tracker/publisher-tools'   => array('page-publisher.php', 'alt_publisher_tools'),
        'ai-layoff-tracker/ai-tracker-health' => array('page-health.php', 'alt_tracker_health'),
    );
}

function alt_template_heading($file) {
    $path = ALT_PLUGIN_DIR . 'templates/' . $file;
    if (!is_readable($path)) return '';
    $src = file_get_contents($path);
    if ($src === false || $src === '') return '';
    if (!preg_match('#<h1[^>]*>(.*?)</h1>#si', $src, $m)) return '';
    $inner = $m[1];
    /* A '<' inside catches both nested markup and an opening PHP tag; a closing
       PHP tag catches a heading that steps back out to HTML. Either means the
       rendered text is not this string, so there is nothing here to copy.
       (Written as a block comment on purpose: a closing PHP tag inside a //
       comment ends PHP mode, in this file as much as in any other.) */
    if (strpos($inner, '<') !== false || strpos($inner, '?' . '>') !== false) return '';
    $text = html_entity_decode($inner, ENT_QUOTES, 'UTF-8');
    return trim(preg_replace('/\s+/u', ' ', $text));
}

/**
 * The label to use when one of our pages links to another.
 *
 * WHY THIS EXISTS. The heading, the post title and every link to a page were
 * three separate strings, so renaming one moved one. On 2026-08-13 the press
 * page was renamed and its tab kept the old wording until a sync was built;
 * five links to /ai-quotes/ still said "AI, in their own words" and "AI
 * layoffs, in their own words" while the page itself was headed "AI layoffs,
 * in the employer's own words". A reader following a link landed on a page
 * that appeared to be something else.
 *
 * So a link asks the destination what it calls itself. `$fallback` is not
 * decoration: alt_template_heading() returns '' for a heading it cannot read
 * verbatim (nested markup, a PHP expression, a half-uploaded file), and a link
 * with an empty label is worse than a stale one.
 */
function alt_page_link_label($file, $fallback) {
    $h = alt_template_heading($file);
    return $h !== '' ? $h : $fallback;
}

/**
 * Suppress the site's Easy Table of Contents on pages this plugin renders.
 * The injected TOC indexes our app sections as if they were article
 * headings, overlaps the hero on phones, and adds nothing a data dashboard
 * needs. Detection is by our own shortcodes/routes, so ordinary blog posts
 * keep their TOC.
 */
function alt_page_is_plugin_surface() {
    if (function_exists('alt_company_directory_is_request') && alt_company_directory_is_request()) return true;
    $post = get_post();
    if (!$post || empty($post->post_content)) return false;
    foreach (array('alt_tracker', 'alt_tracker_health', 'alt_publisher_tools', 'alt_quarterly_report', 'alt_dashboard', 'alt_ai_tracker', 'alt_company_history', 'alt_sources', 'alt_report') as $shortcode) {
        if (has_shortcode($post->post_content, $shortcode)) return true;
    }
    return false;
}
function alt_disable_toc_on_plugin_pages() {
    if (!alt_page_is_plugin_surface()) return;
    add_filter('ez_toc_maybe_apply_the_content_filter', '__return_false', 99);
    add_filter('ez_toc_modify_process_page_content', '__return_empty_string', 99);
}
add_action('wp', 'alt_disable_toc_on_plugin_pages');

/**
 * The site stack sends "no-cache, no-store" on page HTML, so every anonymous
 * visit pays a full ~2s shared-host render before the app even starts. The
 * plugin surfaces are static shells whose numbers load client-side from the
 * (cached) API, so a short public cache is safe and cuts most of the wait.
 * Logged-in views and the admission-sensitive company pages stay uncached.
 *
 * The lifetime is short and carries NO stale-while-revalidate, because a deploy
 * has no way to purge what sits in front of this. Measured 2026-08-05: readers
 * requesting the bare URL were served HTML built by 2.19.272 for eighteen
 * minutes after 2.19.274 shipped, while the same URL with a query string, and
 * the no-store /status endpoint, both answered 2.19.274. The origin was right
 * the whole time. TWO independent shared caches sit above it,
 *
 *     reader -> Cloudflare -> Railway proxy (x-cache-status) -> Bluehost -> PHP
 *
 * each keeps its own entry with its own timer, and their windows ADD rather
 * than overlap. At s-maxage=300 + stale-while-revalidate=600 that was up to
 * 900s per hop. The copy healed itself the second Cloudflare's age reached 300,
 * which is what proves it was TTL and not a hook that failed to run: no PHP
 * cache flush can reach a cache PHP is never consulted by.
 *
 * So the bound is set here, where it is the only lever we hold. s-maxage=60
 * over two hops bounds a reader to roughly two minutes behind a deploy.
 * stale-while-revalidate is gone: it buys latency we do not need and pays for
 * it in staleness we cannot purge. stale-if-error KEEPS the outage protection
 * that swr was incidentally providing, and only applies when the origin is
 * failing, which is the one case where a stale page beats the host's 504.
 *
 * The public API keeps the longer lifetime on purpose (see htaccess.php): its
 * responses are data, not build output, a few minutes behind is correct there,
 * and the edge cache on those endpoints was measured working.
 */
function alt_public_page_cache_headers() {
    if (is_user_logged_in() || !alt_page_is_plugin_surface()) return;
    if (function_exists('alt_company_directory_is_request') && alt_company_directory_is_request()) return;
    header('Cache-Control: public, max-age=60, s-maxage=60, stale-if-error=600');
}
add_action('template_redirect', 'alt_public_page_cache_headers', PHP_INT_MAX);

/** Frozen, server-generated quarterly research snapshot. */
function alt_shortcode_quarterly_report($atts) {
    $atts = shortcode_atts(array('report' => ''), $atts, 'alt_quarterly_report');
    $report_id = sanitize_text_field($atts['report']);
    if ($report_id === '' && isset($_GET['report'])) $report_id = sanitize_text_field(wp_unslash($_GET['report']));
    return alt_template('page-quarterly-report.php', array('report_id' => $report_id));
}
add_shortcode('alt_quarterly_report', 'alt_shortcode_quarterly_report');

function alt_shortcode_company_history($atts) {
    $atts = shortcode_atts(array('company' => ''), $atts, 'alt_company_history');
    $company = sanitize_text_field($atts['company']);
    if ($company === '') {
        return '<p class="alt-error">[alt_company_history] needs a company attribute, e.g. [alt_company_history company="amazon"].</p>';
    }
    return alt_template('page-company.php', array('company' => $company));
}
add_shortcode('alt_company_history', 'alt_shortcode_company_history');

function alt_shortcode_stats_bar() {
    // On the page that also renders [alt_tracker], the tracker template hosts
    // this exact header inside its freshness panel (top-right of the hero),
    // so the shortcode emits nothing there: the ids inside must stay unique
    // for layoffs.js renderStatus(). Other pages keep the standalone strip.
    global $post;
    if ($post && has_shortcode((string) $post->post_content, 'alt_tracker')) return '';
    return alt_render_status_header();
}

/** The Roo status header, shared by [alt_stats_bar] and the tracker hero. */
function alt_render_status_header() {
    ob_start();
    ?>
    <div class="alt-header">
        <span class="alt-roo-wrap is-sleeping" id="alt-roo-wrap" aria-hidden="true"><span class="alt-zzz"><i>z</i><i>z</i><i>z</i></span><svg id="alt-roo" class="alt-roo roo-sleeping" width="60" height="64" viewBox="0 0 140 150"><g class="roo-root"><line x1="70" y1="14" x2="70" y2="26" stroke="var(--primary-deep)" stroke-width="3" stroke-linecap="round"></line><circle class="roo-bulb" cx="70" cy="10" r="5" fill="var(--accent)"></circle><rect x="26" y="24" width="88" height="40" rx="20" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3.5"></rect><g class="roo-eyes"><circle cx="51" cy="44" r="12" fill="var(--primary-soft)" stroke="var(--primary-deep)" stroke-width="2.5"></circle><g class="roo-pupil"><circle cx="53.5" cy="44" r="5.5" fill="var(--primary-deep)"></circle><circle cx="55.5" cy="42" r="1.8" fill="var(--surface)"></circle></g><g class="roo-wink-eye"><circle cx="89" cy="44" r="12" fill="var(--primary-soft)" stroke="var(--primary-deep)" stroke-width="2.5"></circle><g class="roo-pupil"><circle cx="86.5" cy="44" r="5.5" fill="var(--primary-deep)"></circle><circle cx="88.5" cy="42" r="1.8" fill="var(--surface)"></circle></g></g></g><path d="M 59 57 Q 70 61 81 57" fill="none" stroke="var(--primary-deep)" stroke-width="2.5" stroke-linecap="round"></path><g class="roo-body-group"><rect x="64" y="64" width="12" height="8" fill="var(--primary-deep)" rx="2"></rect><rect class="roo-arm-l" x="18" y="82" width="14" height="28" rx="7" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3"></rect><rect class="roo-arm-r" x="108" y="82" width="14" height="28" rx="7" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3"></rect><rect x="36" y="72" width="68" height="46" rx="10" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3.5"></rect><rect x="48" y="80" width="44" height="30" rx="5" fill="var(--primary-tint)" stroke="var(--primary-deep)" stroke-width="2"></rect><rect class="roo-line" x="54" y="86" height="3.5" width="26" rx="1.75" fill="var(--primary-deep)"></rect><rect class="roo-line" x="54" y="93" height="3.5" width="18" rx="1.75" fill="var(--primary-deep)"></rect><rect class="roo-line" x="54" y="100" height="3.5" width="22" rx="1.75" fill="var(--primary-deep)"></rect></g><rect x="30" y="122" width="80" height="14" rx="7" fill="var(--primary-soft)" stroke="var(--primary-deep)" stroke-width="2.5"></rect><circle class="roo-tread-dot" cx="42" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="56" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="70" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="84" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="98" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle></g></svg></span>
        <span class="alt-status alt-status-working" id="alt-status-working" hidden><span id="alt-work-text">Roo is refreshing the data</span></span>
        <span class="alt-next" id="alt-next-pull"></span>
        <?php
        // Cadence derived from the REAL cron (data/ingest-schedule.json via
        // alt_ingest_times_label, DST-correct), never typed: the old literal
        // "9 AM & 6 PM ET" was wrong half the year because the cron is
        // UTC-fixed. Without a schedule we promise only the cadence.
        $alt_ing = function_exists('alt_ingest_schedule') ? alt_ingest_schedule() : null;
        $alt_ing_n = $alt_ing ? count($alt_ing['utc_hours']) : 0;
        $alt_ing_label = function_exists('alt_ingest_times_label') ? alt_ingest_times_label() : '';
        $alt_cadence = ($alt_ing_n === 2 ? 'twice daily' : ($alt_ing_n === 1 ? 'daily' : ($alt_ing_n > 2 ? $alt_ing_n . '× daily' : 'twice daily')))
            . ($alt_ing_label ? ' · ' . $alt_ing_label : '');
        ?>
        <span class="alt-status" id="alt-status-live"><span class="alt-live-dot" aria-hidden="true"></span> Live · updated <span id="alt-live-time"><?php echo esc_html($alt_cadence); ?></span></span>
        <span class="alt-brand">by <strong>AskTheRecruiter.com</strong></span>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('alt_stats_bar', 'alt_shortcode_stats_bar');

function alt_shortcode_export_buttons() {
    $csv_url  = admin_url('admin-post.php?action=alt_export_csv');
    $json_url = admin_url('admin-post.php?action=alt_export_json');
    ob_start();
    ?>
    <div class="alt-export-buttons">
        <a class="alt-btn alt-btn-primary" href="<?php echo esc_url($csv_url); ?>">Download CSV</a>
        <a class="alt-btn" href="<?php echo esc_url($json_url); ?>">Download JSON</a>
        <p class="alt-export-note">Free to use with attribution to asktherecruiter.com.
           Journalists can also query the public API at
           <code><?php echo esc_html(rest_url('layoffs/v1/all')); ?></code>.</p>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('alt_export_buttons', 'alt_shortcode_export_buttons');
