<?php
/** Standalone, frame-safe, noindex single-chart embed. Loaded only by
 *  alt_render_chart_embed_route (?alt_chart_embed=1&chart=<id>&<filters>). */
if (!defined('ABSPATH')) exit;

// Allowed charts → card type. Anything else falls back to the trend line.
//
// Titles are the dashboard's own card titles, verbatim. A reader who follows
// an embed back has to land on the card they were looking at, and a renamed
// copy makes that a search rather than a recognition.
//
// Kept in step with EMBED_OK in assets/layoffs.js by
// test_partial_period_and_chart_basis.py: that map decides which cards offer
// an embed button, this one decides which the route will actually render, and
// a card listed in only one of them either offers a button that 404s into the
// trend line or hides a route that works.
$alt_embed_charts = array(
    'alt-chart-weekly'         => array('canvas', 'Jobs cut per month'),
    'alt-chart-ai-share-trend' => array('canvas', 'AI share of verified cuts'),
    'alt-chart-ai-cumulative'  => array('canvas', 'Cumulative AI-attributed cuts'),
    'alt-chart-yoy'            => array('canvas', 'This year vs last year'),
    'alt-chart-reasons'        => array('canvas', 'Reasons cited'),
    'alt-chart-aimap'          => array('map',    'The map of job cuts'),
    'alt-bars-industries'      => array('bars',   'By industry'),
    'alt-bars-states'          => array('bars',   'Layoffs by US state'),
    'alt-bars-countries'       => array('bars',   'Layoffs by country'),
    'alt-bars-roles'           => array('bars',   'Roles most impacted'),
    'alt-bars-sourcetypes'     => array('bars',   'By data source'),
    'alt-bars-leaders'         => array('bars',   'Largest single job cuts'),
    'alt-bars-repeat'          => array('bars',   'Repeat layoffs'),
    'alt-bars-ai-intensity'    => array('bars',   'AI intensity by industry'),
);
$alt_chart = isset($_GET['chart']) ? preg_replace('/[^a-z0-9\-]/', '', (string) $_GET['chart']) : 'alt-chart-weekly';
if (!isset($alt_embed_charts[$alt_chart])) $alt_chart = 'alt-chart-weekly';
list($alt_ctype, $alt_ctitle) = $alt_embed_charts[$alt_chart];

// Build the aggregate filter params from the URL (allowlisted + sanitized).
$alt_embed_params = array();
$alt_pass = array('years','quarters','months','industry','country','state','sources','reasons','roles','from','to','q','company','keyword','stage','date_basis');
foreach ($alt_pass as $k) {
    if (isset($_GET[$k]) && $_GET[$k] !== '') $alt_embed_params[$k] = sanitize_text_field(wp_unslash($_GET[$k]));
}
if (isset($_GET['min_jobs'])) { $mj = (int) $_GET['min_jobs']; if ($mj > 0) $alt_embed_params['min_jobs'] = $mj; }
if (isset($_GET['ai']) && $_GET['ai'] === '1') $alt_embed_params['ai'] = '1';
if (isset($_GET['ai_broad']) && $_GET['ai_broad'] === '1') $alt_embed_params['ai_broad'] = '1';

$alt_cfg = array(
    'apiUrl'      => esc_url_raw(rest_url('layoffs/v1/')),
    'embed'       => true,
    'embedParams' => $alt_embed_params,
    'embedChart'  => $alt_chart,
);
$alt_tracker_url = add_query_arg($alt_embed_params, home_url('/ai-layoff-tracker/'));
$alt_need_geo = ($alt_chart === 'alt-chart-aimap');
?><!doctype html>
<html <?php language_attributes(); ?>><head>
<meta charset="<?php bloginfo('charset'); ?>">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title><?php echo esc_html($alt_ctitle); ?> · AI Layoff Tracker</title>
<link rel="stylesheet" href="<?php echo esc_url(ALT_PLUGIN_URL . 'assets/layoffs.css?ver=' . ALT_VERSION); ?>">
<style>
  html,body{margin:0;background:var(--alt-page)}
  .alt-embed-shell{padding:10px 12px 30px;box-sizing:border-box}
  .alt-embed-shell .alt-chart-card{border:1px solid var(--alt-border);border-radius:12px;padding:12px 14px;box-shadow:none}
  .alt-embed-shell .alt-chart-box{height:300px}
  .alt-embed-foot{position:fixed;bottom:0;left:0;right:0;font:600 11px system-ui,-apple-system,sans-serif;
    text-align:center;padding:5px;background:var(--alt-surface);border-top:1px solid var(--alt-border)}
  .alt-embed-foot a{color:var(--alt-accent);text-decoration:none}
  .alt-chart-head .alt-chart-h{min-width:0}
  @media (max-width:560px){
    .alt-chart-head{flex-wrap:wrap;align-items:flex-start}
    .alt-chart-head .alt-chart-h{flex:1 1 100%}
    .alt-chart-head .alt-chart-btns{margin-top:8px}
  }
</style>
</head><body>
<div class="alt-embed-shell">
  <div class="alt-mini alt-chart-card" id="alt-map-card">
    <div class="alt-chart-head">
      <div class="alt-chart-h"><?php echo esc_html($alt_ctitle); ?></div>
      <?php if ($alt_ctype === 'map') : ?>
      <span class="alt-chart-btns"><span class="alt-map-toggle">
        <button type="button" class="alt-map-scope alt-map-scope-on" data-scope="world">World</button>
        <button type="button" class="alt-map-scope" data-scope="us">US states</button>
      </span></span>
      <?php endif; ?>
    </div>
    <?php if ($alt_ctype === 'canvas') : ?>
      <div class="alt-chart-box"><canvas id="<?php echo esc_attr($alt_chart); ?>"></canvas></div>
      <?php // Same reason as the bar note below: the caption that says the last
            // point is an unfinished month, or what basis the bars are on, is
            // written by id into an element the dashboard has and this shell
            // did not. Three of these four charts can end on a part month, and
            // an embed that drops the sentence publishes a plunge with no
            // explanation on a page we do not control. The ids are the
            // renderers' own, so they cannot be renamed here by accident.
            $alt_canvas_notes = array(
                'alt-chart-weekly'         => 'alt-trend-partial',
                'alt-chart-yoy'            => 'alt-yoy-partial',
                'alt-chart-ai-share-trend' => 'alt-ai-share-partial',
                'alt-chart-reasons'        => 'alt-chart-reasons-basis',
            );
            if (isset($alt_canvas_notes[$alt_chart])) :
                // The partial-month notes carry the dashboard's extra class so
                // they are styled here exactly as they are there; the reasons
                // card's basis line is a plain note on both surfaces.
                $alt_note_cls = ($alt_chart === 'alt-chart-reasons')
                    ? 'alt-chart-note' : 'alt-chart-note alt-chart-note-partial'; ?>
      <p class="<?php echo esc_attr($alt_note_cls); ?>" id="<?php echo esc_attr($alt_canvas_notes[$alt_chart]); ?>" hidden></p>
      <?php endif; ?>
    <?php elseif ($alt_ctype === 'map') : ?>
      <div class="alt-chart-box alt-map-box"><div id="alt-chart-aimap"></div></div>
      <p class="alt-map-total alt-muted" id="alt-map-total"></p>
      <p class="alt-map-empty alt-muted" id="alt-map-note" style="display:none"></p>
    <?php else : ?>
      <div class="alt-barlist" id="<?php echo esc_attr($alt_chart); ?>"></div>
      <?php // THE BASIS SENTENCE TRAVELS WITH THE BARS.
            //
            // barBasisNote() in layoffs.js states what the drawn rows cover,
            // of what, and where the remainder is, because a top-N of a long
            // tail does not sum to the headline and a reader cannot see why.
            // It writes into "<chart-id>-basis". This shell never shipped that
            // element, so every bar embed since the route existed has left the
            // page carrying bars with the caveat stripped off - the one surface
            // where it matters most, since an embed is read on somebody else's
            // site with none of the dashboard around it.
            //
            // The AI-intensity card writes its own sparse-data label into
            // "-note" instead (a 1,000-cut floor means it often draws one row,
            // and the emptiness gets a label rather than a fix). Both are
            // emitted; each renderer fills the one it owns and leaves the
            // other hidden. ?>
      <p class="alt-chart-note" id="<?php echo esc_attr($alt_chart); ?>-basis"></p>
      <p class="alt-chart-note" id="<?php echo esc_attr($alt_chart); ?>-note" hidden></p>
    <?php endif; ?>
  </div>
</div>
<p class="alt-embed-foot"><a href="<?php echo esc_url($alt_tracker_url); ?>" target="_top">AI Layoff Tracker · AskTheRecruiter.com &#8599;</a></p>
<?php // Same hex flags page-tracker.php uses on its own bootstrap. Without them a
      // value containing "</script>" ends the block early and the rest of the
      // JSON is parsed as HTML; wp_json_encode's defaults escape neither the
      // tag characters nor the quotes. The embed is the surface most likely to
      // be iframed on somebody else's page, so it is the last one that should
      // have been left on the weaker encoding. ?>
<script>window.altData=<?php echo wp_json_encode($alt_cfg, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT); ?>;</script>
<script src="<?php echo esc_url(includes_url('js/jquery/jquery.min.js')); ?>"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<?php if ($alt_need_geo) : ?>
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js"></script>
<?php endif; ?>
<script src="<?php echo esc_url(ALT_PLUGIN_URL . 'assets/layoffs.js?ver=' . ALT_VERSION); ?>"></script>
</body></html>
