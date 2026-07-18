<?php
/** Standalone state/national widget; loaded only by alt_render_widget_route. */
if (!defined('ABSPATH')) exit;

$alt_widget_year = isset($_GET['year']) ? absint(wp_unslash($_GET['year'])) : (int) gmdate('Y');
$alt_widget_year = max(2015, min((int) gmdate('Y'), $alt_widget_year));
$alt_widget_state = isset($_GET['state']) ? strtoupper(sanitize_text_field(wp_unslash($_GET['state']))) : '';
$alt_widget_state = function_exists('alt_normalize_state') ? alt_normalize_state($alt_widget_state) : '';

$alt_widget_params = array('years' => (string) $alt_widget_year, 'country' => 'United States');
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
<script>window.altWidgetData=<?php echo wp_json_encode($alt_widget_config); ?>;</script>
<script src="<?php echo esc_url(ALT_PLUGIN_URL . 'assets/widget.js?ver=' . ALT_VERSION); ?>" defer></script>
</body></html>
