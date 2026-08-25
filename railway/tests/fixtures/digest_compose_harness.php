<?php
/**
 * Renders the digest COMPOSERS against a fixture /aggregate response.
 *
 * WHY A SECOND HARNESS. tests/fixtures/digest_harness.php drives the signup
 * and confirm handlers, and to do that it carries a SQLite $wpdb and a stack
 * of request plumbing. The composers need almost none of it and need one
 * thing it does not have: a `rest_do_request` that answers with a payload the
 * test chose. Bolting a REST stub onto the signup harness would couple two
 * unrelated tests to one file, so this is its own.
 *
 * NOTHING HERE INVENTS A FIGURE. The fixture payloads are shapes copied from
 * a real /aggregate response (the column order of the top_* tuples especially,
 * which is [label, all_jobs, ai_jobs, display_label, verified_jobs,
 * ai_verified_jobs] and is the reason the country block was reading the wrong
 * tier). The composer does the arithmetic; this only feeds it.
 *
 * argv[1] = absolute path to includes/subscribe.php
 * argv[2] = absolute path to a JSON file: {"layoff": {...}, "ytd": {...},
 *           "from": "...", "to": "..."}
 * stdout  = one JSON object: {"html": ..., "text": ...} or {"null": true}
 */

error_reporting(E_ALL & ~E_DEPRECATED);

define('ABSPATH', '/tmp/');
define('DAY_IN_SECONDS', 86400);
define('HOUR_IN_SECONDS', 3600);
define('MINUTE_IN_SECONDS', 60);

function add_action(...$a) {}
function add_shortcode(...$a) {}
function wp_schedule_event(...$a) {}
function wp_next_scheduled(...$a) { return time(); }
function esc_html($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_attr($s) { return htmlspecialchars((string) $s, ENT_QUOTES); }
function esc_url($s) { return (string) $s; }
function number_format_i18n($n) { return number_format((float) $n); }
function sanitize_key($s) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower((string) $s)); }
function sanitize_text_field($s) { return trim((string) $s); }
function wp_unslash($s) { return $s; }
function wp_json_encode($d) { return json_encode($d); }
function home_url($p = '') { return 'https://asktherecruiter.com/blog' . $p; }
function admin_url($p = '') { return 'https://asktherecruiter.com/blog/wp-admin/' . $p; }
function rest_url($p = '') { return 'https://asktherecruiter.com/blog/wp-json/' . ltrim($p, '/'); }
/*
  Options the composer really reads. `alt_last_write` is the one that matters:
  alt_digest_data_cut_label() renders it as the "as of" stamp, and a harness
  that always returned the default would only ever exercise the branch where
  the stamp is missing. The fixture supplies it as a unix timestamp, which is
  what the real option holds.
*/
function get_option($k, $d = false) {
    global $FIXTURE;
    $opts = (array) ($FIXTURE['options'] ?? array());
    return array_key_exists($k, $opts) ? $opts[$k] : $d;
}
function update_option($k, $v, $a = null) { return true; }
function get_transient($k) { return false; }
function set_transient($k, $v, $t = 0) { return true; }
function apply_filters($tag, $value) { return $value; }
function wp_parse_url($url, $component = -1) { return parse_url($url, $component); }
    /*
      DROPS THE `=` ON AN EMPTY VALUE, because the real one does. Observed in
      a live preview on 2026-08-17: a caller passing '' got `&years&quarters`
      and not `&years=&quarters=`. This stub used to append `=` unconditionally
      and so passed a test about the digest's tracker link that production
      would have failed. A stub that is kinder than the function it stands in
      for is worse than no stub: it makes the assertion about the wrong thing.
    */
function add_query_arg($k, $v = null, $url = null) {
    if (is_array($k)) { $args = $k; $url = $v; } else { $args = array($k => $v); }
    $sep = strpos((string) $url, '?') === false ? '?' : '&';
    foreach ($args as $ak => $av) {
        $url .= $sep . rawurlencode($ak);
        if ((string) $av !== '') $url .= '=' . rawurlencode((string) $av);
        $sep = '&';
    }
    return $url;
}

// The shared sentence the real db.php owns. Copied verbatim so a drift shows
// up as a failing assertion rather than as a quietly missing clause.
function alt_announced_tier_sentence() {
    return 'Announced cuts are plans companies have stated that no filing or named report verifies yet.';
}

/**
 * api.php's "data last updated" stamp, fed from the fixture.
 *
 * Nothing is copied here, unlike alt_announced_tier_sentence above: the real
 * function's job is to FORMAT a timestamp out of an option, which is api.php's
 * business and not the composer's. What the composer has to get right is the
 * two branches, a stamp and no stamp, so the fixture supplies the string and a
 * fixture that omits it exercises the empty one. Absence of a stamp must print
 * no sentence, never a guess.
 */
function alt_data_last_updated_label() {
    global $FIXTURE;
    return (string) ($FIXTURE['last_updated_label'] ?? '');
}

/*
  api.php's US state map, LIFTED FROM api.php RATHER THAN COPIED.

  alt_digest_place() expands "KY" to "Kentucky" through alt_us_state_names(),
  which is api.php's single definition and also the source of the state page
  slugs. Requiring the whole of api.php here would drag in the REST plumbing
  this harness deliberately does not have, and pasting the array in would give
  the project a second copy of a list whose whole point is that there is one.
  So the function is read out of the real file at load time. When it cannot be
  found the composer falls back to the stored code, which is the same thing
  production does, so the test still runs and still means something.
*/
/*
  THE ARCHIVE'S OWN TWO FUNCTIONS, LIFTED RATHER THAN STUBBED.

  The layoff section links to the edition's permalink, and it derives the slug
  through alt_edition_slug(), the archive's single definition. Requiring the
  whole of includes/digest-archive.php here would drag in the table plumbing
  and the rewrite rules this harness deliberately does not have, and writing a
  stub would give the project a second definition of a URL whose whole point is
  that a reader can cite it. So the two pure functions are read out of the real
  file at load time, exactly as alt_us_state_names() is below. When they cannot
  be found the composer's function_exists guard prints no link, which is the
  same thing production does when the archive is not loaded.
*/
$alt_archive_php = dirname($argv[1]) . '/digest-archive.php';
if (is_readable($alt_archive_php)) {
    $alt_arch_src = file_get_contents($alt_archive_php);
    foreach (array('alt_edition_index_url', 'alt_edition_url', 'alt_edition_slug') as $alt_fn) {
        if (function_exists($alt_fn)) continue;
        if (preg_match('/function\s+' . $alt_fn . '\([^)]*\)\s*\{.*?\n\}/s',
                       $alt_arch_src, $alt_am)) {
            $alt_sig = substr($alt_am[0], strlen('function ' . $alt_fn));
            $alt_sig = substr($alt_sig, 0, strpos($alt_sig, ')') + 1);
            eval('function ' . $alt_fn . $alt_sig . ' '
                 . substr($alt_am[0], strpos($alt_am[0], '{')));
        }
    }
}

/*
  api.php's two vocabularies the composer maps through, LIFTED not stubbed for
  the same reason the state map is: alt_us_state_names() expands the state block
  and alt_role_categories() is the label->slug reverse the roles block links
  through. Both are api.php's single definition; copying either here would give
  the project a second list whose whole point is that there is one. When a lift
  cannot find a function the composer's function_exists guard degrades exactly
  as production does (the state code prints unchanged, the role row drops its
  link), so the test still runs and still means something.
*/
$alt_api_php = dirname($argv[1]) . '/api.php';
if (is_readable($alt_api_php)) {
    $alt_api_src = file_get_contents($alt_api_php);
    foreach (array('alt_us_state_names', 'alt_role_categories') as $alt_fn) {
        if (function_exists($alt_fn)) continue;
        if (preg_match('/function\s+' . $alt_fn . '\(\)\s*\{.*?\n\}/s',
                       $alt_api_src, $alt_m)) {
            eval('function ' . $alt_fn . '() '
                 . substr($alt_m[0], strpos($alt_m[0], '{')));
        }
    }
}

class WP_REST_Request {
    public $method, $route, $params = array();
    public function __construct($method, $route) { $this->method = $method; $this->route = $route; }
    public function set_param($k, $v) { $this->params[$k] = $v; }
    public function get_param($k) { return $this->params[$k] ?? null; }
}

class WP_REST_Response_Stub {
    private $data, $error;
    public function __construct($data, $error = false) { $this->data = $data; $this->error = $error; }
    public function is_error() { return $this->error; }
    public function get_data() { return $this->data; }
}

$FIXTURE = json_decode(file_get_contents($argv[2]), true);

/**
 * The stub REST layer. Chooses a fixture by the window the composer asked
 * for, so the year-to-date call and the period call cannot be confused: the
 * composer sending the wrong `from` is exactly the kind of bug worth failing.
 */
/*
  EVERY REQUEST THE COMPOSER REALLY MADE, RECORDED.

  A test can read the links out of the rendered body, but the other half of the
  question "does the link land on the basis these figures were counted on?" is
  the parameter the composer sent to /aggregate, and that was invisible from
  outside. Recording it here means the assertion compares two things the real
  composer did, rather than one thing it did against a string a test remembers.
*/
$GLOBALS['__requests'] = array();

function rest_do_request($req) {
    global $FIXTURE;
    $GLOBALS['__requests'][] = array('route' => $req->route, 'params' => $req->params);
    if (strpos($req->route, '/talent/') === 0) {
        /*
          THE ROUTE, NOT ONLY THE WINDOW. The talent section reads TWO routes
          over the same window: /aggregate for the headline and /query for the
          ranked rows. Keying on `since` alone handed the query call the
          aggregate payload, which carries no `rows`, so the ranked list could
          never be rendered here at all. A fixture without `talent_q` keeps the
          old behaviour, so existing cases are unaffected.
        */
        if (strpos($req->route, '/query') !== false && !empty($FIXTURE['talent_q'])) {
            return new WP_REST_Response_Stub($FIXTURE['talent_q']);
        }
        /*
          THE CATEGORY CALLS ARE THEIR OWN ANSWERS, NOT THE HEADLINE'S.

          "Other talent activity" asks /aggregate three more times over the
          SAME window, each narrowed by one filter. Keying on `since` alone
          handed all three the headline payload, so the harness printed the
          same total three times and a test could not tell a working category
          count from a broken one.

          A fixture that does not supply a category answers with an ERROR,
          which is what a talent plugin that cannot serve that filter really
          does, and the composer's documented response to it is to print no
          line for that category rather than a zero. So existing fixtures keep
          exercising the absent branch instead of acquiring an invented count.
        */
        foreach (array('pillar', 'funding', 'direction') as $filter) {
            $value = $req->get_param($filter);
            if ($value === null || $value === '') continue;
            $key = 'talent_cat_' . $filter . '_' . $value;
            if (!isset($FIXTURE[$key])) return new WP_REST_Response_Stub(null, true);
            return new WP_REST_Response_Stub($FIXTURE[$key]);
        }
        $key = ($req->get_param('since') === $FIXTURE['from']) ? 'talent' : 'talent_ytd';
        if (empty($FIXTURE[$key])) return new WP_REST_Response_Stub(null, true);
        return new WP_REST_Response_Stub($FIXTURE[$key]);
    }
    /*
      THREE WINDOWS NOW, NOT TWO. The layoff composer asks for the period, the
      PRIOR period (the week-on-week comparison added 2026-08-19) and the year
      to date, and keying on "is this the period, else it is the year" handed
      the prior-week call the year-to-date payload. That would have made the
      comparison silently enormous and the test would have passed.

      A fixture with no `prior` key answers the prior-week call with an ERROR,
      which is the real behaviour when the endpoint cannot serve that window,
      and the composer's documented response to it is to print no comparison at
      all. So the existing fixtures keep exercising the no-comparison branch
      rather than acquiring an invented one.
    */
    $from = $req->get_param('from');
    if ($from === $FIXTURE['from']) $key = 'layoff';
    elseif (isset($FIXTURE['prior_from']) && $from === $FIXTURE['prior_from']) $key = 'prior';
    else $key = 'ytd';
    if (empty($FIXTURE[$key])) return new WP_REST_Response_Stub(null, true);
    return new WP_REST_Response_Stub($FIXTURE[$key]);
}

/**
 * The blog posts, for `compose: articles`. Stubbed rather than faked out: the
 * composer reads the title, the permalink, the excerpt, the GMT publish date
 * and the body word count, so the fixture supplies exactly those five and
 * nothing invents one. A fixture item with no `content` gets no read time,
 * which is the real behaviour for a post whose body cannot be counted.
 */
/*
  THE DATE WINDOW IS HONOURED, because the composer's whole caption is about
  it. The real get_posts() is given a `date_query` on post_date_gmt and returns
  only posts inside the window; this stub returned every fixture post, so a
  render could print "12 posts we published on 17 and 18 August 2026" over a
  list spanning two months. A stub that is more generous than the function it
  stands in for makes the assertion about the wrong thing.
*/
function get_posts($args = array()) {
    global $FIXTURE;
    $after = '';
    $before = '';
    foreach ((array) ($args['date_query'] ?? array()) as $clause) {
        $after = substr((string) ($clause['after'] ?? ''), 0, 10);
        $before = substr((string) ($clause['before'] ?? ''), 0, 10);
    }
    $out = array();
    foreach (($FIXTURE['posts'] ?? array()) as $p) {
        $day = substr((string) ($p['date'] ?? ''), 0, 10);
        if ($after !== '' && $day !== '' && $day < $after) continue;
        if ($before !== '' && $day !== '' && $day > $before) continue;
        $o = new stdClass();
        $o->post_title = (string) ($p['title'] ?? '');
        $o->post_excerpt = (string) ($p['excerpt'] ?? '');
        $o->post_date_gmt = (string) ($p['date'] ?? '');
        $o->post_content = (string) ($p['content'] ?? '');
        $o->permalink = (string) ($p['link'] ?? '');
        $out[] = $o;
    }
    return $out;
}
function get_the_title($p) { return $p->post_title; }
function get_permalink($p) { return $p->permalink; }
function get_the_excerpt($p) { return $p->post_excerpt; }
function wp_strip_all_tags($s) { return strip_tags((string) $s); }

require $argv[1];

$which = $FIXTURE['compose'] ?? 'layoff';
if ($which === 'talent') {
    $out = alt_digest_compose_talent($FIXTURE['from'], $FIXTURE['to'], 0);
} elseif ($which === 'articles') {
    $out = alt_digest_compose_articles($FIXTURE['from'], $FIXTURE['to'], 0);
} else {
    $out = alt_digest_compose_layoff($FIXTURE['from'], $FIXTURE['to'], 0);
}

if ($out === null) {
    echo json_encode(array('null' => true, 'requests' => $GLOBALS['__requests']));
} else {
    $out['requests'] = $GLOBALS['__requests'];
    echo json_encode($out);
}
