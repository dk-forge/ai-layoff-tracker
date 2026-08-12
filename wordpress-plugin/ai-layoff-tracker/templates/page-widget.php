<?php
/** Standalone state/national widget; loaded only by alt_render_widget_route. */
if (!defined('ABSPATH')) exit;

$alt_widget_year = isset($_GET['tracker_year']) ? absint(wp_unslash($_GET['tracker_year'])) : (int) gmdate('Y');
$alt_widget_year = max(2015, min((int) gmdate('Y'), $alt_widget_year));
$alt_widget_state = isset($_GET['state']) ? strtoupper(sanitize_text_field(wp_unslash($_GET['state']))) : '';
$alt_widget_state = function_exists('alt_normalize_state') ? alt_normalize_state($alt_widget_state) : '';

// ONE PARAM SET FEEDS BOTH THE FIGURE AND THE LINK UNDER IT, so the basis has
// to be named rather than left to whatever the tracker's default is that month.
// This array is sent to /aggregate AND used to build trackerUrl. Naming
// 'effective' keeps the embedded number exactly what it has always been (the
// server default before 2.20.4) while making "View sources and filters" open a
// page that recounts it the same way. Left unnamed, the widget published one
// basis and linked to the other.
$alt_widget_params = array('years' => (string) $alt_widget_year, 'country' => 'United States',
                           'date_basis' => 'effective');
if ($alt_widget_state !== '') $alt_widget_params['state'] = $alt_widget_state;
$alt_widget_label = $alt_widget_state !== '' ? $alt_widget_state . ' layoffs' : 'US layoffs';
$alt_widget_tracker_url = add_query_arg($alt_widget_params, home_url('/ai-layoff-tracker/'));
$alt_widget_config = array(
    'apiUrl' => rest_url('layoffs/v1/'),
    'params' => $alt_widget_params,
    'trackerUrl' => $alt_widget_tracker_url,
    'label' => $alt_widget_label,
    'year' => $alt_widget_year,
);
?><!doctype html>
<html <?php language_attributes(); ?>><head>
<meta charset="<?php bloginfo('charset'); ?>">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title><?php echo esc_html($alt_widget_label . ' ' . $alt_widget_year); ?> | AskTheRecruiter</title>
<link rel="stylesheet" href="<?php echo esc_url(ALT_PLUGIN_URL . 'assets/widget.css?ver=' . ALT_VERSION); ?>">
</head><body>
<main class="alt-widget" aria-labelledby="alt-widget-title">
    <p class="alt-widget-brand">ASKTHERECRUITER · AI LAYOFF TRACKER</p>
    <h1 id="alt-widget-title"><?php echo esc_html($alt_widget_label); ?> · <?php echo (int) $alt_widget_year; ?></h1>
    <p class="alt-widget-value" id="alt-widget-value" aria-live="polite">Loading…</p>
    <p class="alt-widget-label" id="alt-widget-label">Source-linked job cuts</p>
    <p class="alt-widget-note">Source-linked events only; coverage varies by source and location.</p>
    <a class="alt-widget-link" id="alt-widget-link" href="<?php echo esc_url($alt_widget_tracker_url); ?>" target="_blank" rel="noopener">View sources &amp; filters <span aria-hidden="true">↗</span></a>
</main>
<?php // Hex flags, for the same reason page-chart-embed.php now has them: this is
      // the other bootstrap that ships to a third-party page. ?>
<script>window.altWidgetData=<?php echo wp_json_encode($alt_widget_config, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT); ?>;</script>
<script src="<?php echo esc_url(ALT_PLUGIN_URL . 'assets/widget.js?ver=' . ALT_VERSION); ?>" defer></script>
</body></html>
