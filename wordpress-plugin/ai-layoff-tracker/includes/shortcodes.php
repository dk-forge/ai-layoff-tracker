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
    return ob_get_clean();
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
 */
function alt_public_page_cache_headers() {
    if (is_user_logged_in() || !alt_page_is_plugin_surface()) return;
    if (function_exists('alt_company_directory_is_request') && alt_company_directory_is_request()) return;
    header('Cache-Control: public, max-age=180, s-maxage=300, stale-while-revalidate=600');
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
    ob_start();
    ?>
    <div class="alt-header">
        <span class="alt-roo-wrap is-sleeping" id="alt-roo-wrap" aria-hidden="true"><span class="alt-zzz"><i>z</i><i>z</i><i>z</i></span><svg id="alt-roo" class="alt-roo roo-sleeping" width="60" height="64" viewBox="0 0 140 150"><g class="roo-root"><line x1="70" y1="14" x2="70" y2="26" stroke="var(--primary-deep)" stroke-width="3" stroke-linecap="round"></line><circle class="roo-bulb" cx="70" cy="10" r="5" fill="var(--accent)"></circle><rect x="26" y="24" width="88" height="40" rx="20" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3.5"></rect><g class="roo-eyes"><circle cx="51" cy="44" r="12" fill="var(--primary-soft)" stroke="var(--primary-deep)" stroke-width="2.5"></circle><g class="roo-pupil"><circle cx="53.5" cy="44" r="5.5" fill="var(--primary-deep)"></circle><circle cx="55.5" cy="42" r="1.8" fill="var(--surface)"></circle></g><g class="roo-wink-eye"><circle cx="89" cy="44" r="12" fill="var(--primary-soft)" stroke="var(--primary-deep)" stroke-width="2.5"></circle><g class="roo-pupil"><circle cx="86.5" cy="44" r="5.5" fill="var(--primary-deep)"></circle><circle cx="88.5" cy="42" r="1.8" fill="var(--surface)"></circle></g></g></g><path d="M 59 57 Q 70 61 81 57" fill="none" stroke="var(--primary-deep)" stroke-width="2.5" stroke-linecap="round"></path><g class="roo-body-group"><rect x="64" y="64" width="12" height="8" fill="var(--primary-deep)" rx="2"></rect><rect class="roo-arm-l" x="18" y="82" width="14" height="28" rx="7" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3"></rect><rect class="roo-arm-r" x="108" y="82" width="14" height="28" rx="7" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3"></rect><rect x="36" y="72" width="68" height="46" rx="10" fill="var(--surface)" stroke="var(--primary-deep)" stroke-width="3.5"></rect><rect x="48" y="80" width="44" height="30" rx="5" fill="var(--primary-tint)" stroke="var(--primary-deep)" stroke-width="2"></rect><rect class="roo-line" x="54" y="86" height="3.5" width="26" rx="1.75" fill="var(--primary-deep)"></rect><rect class="roo-line" x="54" y="93" height="3.5" width="18" rx="1.75" fill="var(--primary-deep)"></rect><rect class="roo-line" x="54" y="100" height="3.5" width="22" rx="1.75" fill="var(--primary-deep)"></rect></g><rect x="30" y="122" width="80" height="14" rx="7" fill="var(--primary-soft)" stroke="var(--primary-deep)" stroke-width="2.5"></rect><circle class="roo-tread-dot" cx="42" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="56" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="70" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="84" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle><circle class="roo-tread-dot" cx="98" cy="129" r="3" fill="var(--primary-deep)" opacity="0.55"></circle></g></svg></span>
        <span class="alt-status alt-status-working" id="alt-status-working" hidden><span id="alt-work-text">Roo is refreshing the data</span></span>
        <span class="alt-next" id="alt-next-pull"></span>
        <span class="alt-status" id="alt-status-live"><span class="alt-live-dot" aria-hidden="true"></span> Live · updated <span id="alt-live-time">twice daily · 9 AM &amp; 6 PM ET</span></span>
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
