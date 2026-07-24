<?php if (!defined('ABSPATH')) exit;
// Year-by-year stats straight from the fast table, cached an hour. The press
// page must never show a number the tracker itself cannot reproduce.
$alt_press_years = get_transient('alt_press_year_stats_' . ALT_VERSION);
if (!is_array($alt_press_years)) {
    global $wpdb;
    $alt_t = alt_db_table();
    $alt_press_years = $wpdb->get_results(
        "SELECT YEAR(layoff_date) y, COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs
         FROM $alt_t WHERE layoff_date >= '2015-01-01' AND layoff_date <= CURDATE()
         GROUP BY YEAR(layoff_date) ORDER BY y DESC", ARRAY_A) ?: array();
    set_transient('alt_press_year_stats_' . ALT_VERSION, $alt_press_years, HOUR_IN_SECONDS);
}

// Data-backed soundbite LIBRARY, grouped, live, source-reproducible sentences,
// one per chart/metric across two periods (this year to date + latest month)
// plus a per-region/country set. No em-dashes. Cached hourly; raw text stored
// (the template esc_html()s at render). Every link uses ONLY params the
// tracker front-end actually parses (restoreFiltersFromUrl in layoffs.js):
// years/months/from/to/industry/country/state/roles/company/ai/ai_broad.
$alt_sb_groups = get_transient('alt_press_sb_groups_' . ALT_VERSION);
if (!is_array($alt_sb_groups)) {
    global $wpdb; $alt_t = alt_db_table();
    $alt_tk = home_url('/ai-layoff-tracker/');
    $alt_y = (int) gmdate('Y');
    $alt_ytd_from = sprintf('%04d-01-01', $alt_y); $alt_ytd_to = gmdate('Y-m-d');
    $alt_lm = strtotime(gmdate('Y-m-01') . ' -1 day');
    $alt_m_from = gmdate('Y-m-01', $alt_lm); $alt_m_to = gmdate('Y-m-t', $alt_lm);
    $alt_m_label = gmdate('F Y', $alt_lm);
    $alt_lk = function ($args) use ($alt_tk) { return esc_url(add_query_arg($args, $alt_tk)); };
    $alt_stmap = array('AL'=>'Alabama','AK'=>'Alaska','AZ'=>'Arizona','AR'=>'Arkansas','CA'=>'California','CO'=>'Colorado','CT'=>'Connecticut','DE'=>'Delaware','DC'=>'Washington, D.C.','FL'=>'Florida','GA'=>'Georgia','HI'=>'Hawaii','ID'=>'Idaho','IL'=>'Illinois','IN'=>'Indiana','IA'=>'Iowa','KS'=>'Kansas','KY'=>'Kentucky','LA'=>'Louisiana','ME'=>'Maine','MD'=>'Maryland','MA'=>'Massachusetts','MI'=>'Michigan','MN'=>'Minnesota','MS'=>'Mississippi','MO'=>'Missouri','MT'=>'Montana','NE'=>'Nebraska','NV'=>'Nevada','NH'=>'New Hampshire','NJ'=>'New Jersey','NM'=>'New Mexico','NY'=>'New York','NC'=>'North Carolina','ND'=>'North Dakota','OH'=>'Ohio','OK'=>'Oklahoma','OR'=>'Oregon','PA'=>'Pennsylvania','RI'=>'Rhode Island','SC'=>'South Carolina','SD'=>'South Dakota','TN'=>'Tennessee','TX'=>'Texas','UT'=>'Utah','VT'=>'Vermont','VA'=>'Virginia','WA'=>'Washington','WV'=>'West Virginia','WI'=>'Wisconsin','WY'=>'Wyoming');

    // Query helpers (columns are fixed literals, not user input).
    $alt_stats = function ($from, $to, $cty) use ($wpdb, $alt_t) {
        // v = verified job cuts; aiv = strict AI (employer's own words); aib = the
        // broad AI-linked measure (matches the ai_broad_jobs aggregate exactly:
        // ai_explicit OR ai_causation='ai_linked'). Both AI measures share the
        // verified-tier (announced=0) denominator so their percentages compare.
        $sql = "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                       COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) aiv,
                       COALESCE(SUM(CASE WHEN (ai_explicit=1 OR ai_causation='ai_linked') AND announced=0 THEN job_count END),0) aib
                FROM $alt_t WHERE layoff_date BETWEEN %s AND %s";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_top = function ($col, $from, $to, $cty) use ($wpdb, $alt_t) {
        $sql = "SELECT $col k, SUM(job_count) j FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND $col <> ''";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        $sql .= " GROUP BY $col ORDER BY j DESC LIMIT 1";
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_bigcut = function ($from, $to, $cty) use ($wpdb, $alt_t) {
        $sql = "SELECT company, job_count FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND job_count > 0";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        $sql .= " ORDER BY job_count DESC, id DESC LIMIT 1";
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_toprole = function ($from, $to) use ($wpdb, $alt_t) {
        if (!function_exists('alt_role_categories')) return null;
        $best = null; $bj = 0; $bs = '';
        foreach (alt_role_categories() as $slug => $lab) {
            $j = (int) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(job_count),0) FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND role_categories LIKE %s", $from, $to, '%,' . $slug . ',%'));
            if ($j > $bj) { $bj = $j; $best = $lab; $bs = $slug; }
        }
        return $best ? array('label' => $best, 'slug' => $bs, 'j' => $bj) : null;
    };

    // Build one period's chart soundbites (worldwide). Copy rule: one number,
    // one period, at most one context clause. The methodology caveat lives
    // ONCE at the top of the page, never inside the bites.
    $alt_period_items = function ($from, $to, $when, $periodarg, $reportlink) use ($alt_stats, $alt_top, $alt_bigcut, $alt_toprole, $alt_lk, $alt_stmap) {
        $items = array();
        $s = $alt_stats($from, $to, ''); $v = (int) ($s->v ?? 0); $aiv = (int) ($s->aiv ?? 0); $aib = (int) ($s->aib ?? 0);
        $pct = $v ? round(100 * $aiv / $v) : 0; $pctb = $v ? round(100 * $aib / $v) : 0;
        if ($v) $items[] = array('label' => 'Headline', 'text' => 'The AI Layoff Tracker verified ' . number_format($v) . ' job cuts worldwide in ' . $when . '. Employers themselves blamed AI for ' . $pct . '% of them; counting every cut with any AI link, the share reaches ' . $pctb . '%.', 'link' => $alt_lk($periodarg), 'linklabel' => 'See the rows behind this number');
        $ind = $alt_top('industry', $from, $to, '');
        if ($ind && $ind->k) $items[] = array('label' => 'Top industry', 'text' => $ind->k . ' was the hardest-hit industry in ' . $when . ', with ' . number_format((int) $ind->j) . ' recorded job cuts.', 'link' => $alt_lk(array_merge($periodarg, array('industry' => $ind->k))), 'linklabel' => 'See the ' . $ind->k . ' rows');
        $ctry = $alt_top('country', $from, $to, '');
        if ($ctry && $ctry->k) $items[] = array('label' => 'Top country', 'text' => $ctry->k . ' led the world in recorded job cuts in ' . $when . ', with ' . number_format((int) $ctry->j) . '.', 'link' => $alt_lk(array_merge($periodarg, array('country' => $ctry->k))), 'linklabel' => 'See the ' . $ctry->k . ' rows');
        $st = $alt_top('state', $from, $to, 'United States');
        if ($st && $st->k) $items[] = array('label' => 'Top US state', 'text' => (isset($alt_stmap[$st->k]) ? $alt_stmap[$st->k] : $st->k) . ' recorded the most US layoffs in ' . $when . ', with ' . number_format((int) $st->j) . '.', 'link' => $alt_lk(array_merge($periodarg, array('country' => 'United States', 'state' => $st->k))), 'linklabel' => 'See the ' . (isset($alt_stmap[$st->k]) ? $alt_stmap[$st->k] : $st->k) . ' rows');
        $r = $alt_toprole($from, $to);
        if ($r) $items[] = array('label' => 'Roles hit hardest', 'text' => $r['label'] . ' was the job function hit hardest in ' . $when . ', across ' . number_format($r['j']) . ' cuts where the source named the team affected.', 'link' => $alt_lk(array_merge($periodarg, array('roles' => $r['slug']))), 'linklabel' => 'See the ' . $r['label'] . ' rows');
        $big = $alt_bigcut($from, $to, '');
        if ($big && $big->company) $items[] = array('label' => 'Largest single cut', 'text' => 'The largest single layoff in ' . $when . ': ' . $big->company . ', at ' . number_format((int) $big->job_count) . ' jobs.', 'link' => $alt_lk(array_merge($periodarg, array('company' => $big->company))), 'linklabel' => 'See the ' . $big->company . ' entries');
        return $items;
    };

    $alt_sb_groups = array();
    $ytd_items = $alt_period_items($alt_ytd_from, $alt_ytd_to, $alt_y . ' so far', array('years' => $alt_y), '');
    if ($ytd_items) $alt_sb_groups[] = array('id' => 'sb-ytd', 'title' => $alt_y . ' year to date', 'items' => $ytd_items);
    $m_items = $alt_period_items($alt_m_from, $alt_m_to, $alt_m_label, array('years' => $alt_y, 'months' => (int) gmdate('n', $alt_lm)), '');
    if ($m_items) $alt_sb_groups[] = array('id' => 'sb-month', 'title' => 'Latest complete month (' . $alt_m_label . ')', 'items' => $m_items);

    // Per-region / country (year to date). Worldwide first, then key markets.
    $alt_places = array(
        array('World', '', 'Worldwide, '),
        array('the United States', 'United States', 'In the United States, '),
        array('Germany', 'Germany', 'In Germany, '),
        array('the United Kingdom', 'United Kingdom', 'In the United Kingdom, '),
        array('France', 'France', 'In France, '),
        array('Canada', 'Canada', 'In Canada, '),
        array('Australia', 'Australia', 'In Australia, '),
        array('India', 'India', 'In India, '),
    );
    $geo_items = array();
    foreach ($alt_places as $p) {
        $s = $alt_stats($alt_ytd_from, $alt_ytd_to, $p[1]); $v = (int) ($s->v ?? 0); $aiv = (int) ($s->aiv ?? 0); $aib = (int) ($s->aib ?? 0);
        $pct = $v ? round(100 * $aiv / $v) : 0; $pctb = $v ? round(100 * $aib / $v) : 0;
        $flag = alt_country_flag($p[1] === '' ? 'World' : $p[1]);
        if ($v > 0) $geo_items[] = array('label' => ($flag ? $flag . ' ' : '') . $p[0], 'text' => $p[2] . number_format($v) . ' job cuts are on record for ' . $alt_y . '. Employers blamed AI for ' . $pct . '% of them; ' . $pctb . '% carry any AI link.', 'link' => $alt_lk($p[1] === '' ? array('years' => $alt_y) : array('years' => $alt_y, 'country' => $p[1])), 'linklabel' => 'See the rows behind this number');
    }
    if ($geo_items) $alt_sb_groups[] = array('id' => 'sb-geo', 'title' => 'By region and country (' . $alt_y . ')', 'items' => $geo_items);

    set_transient('alt_press_sb_groups_' . ALT_VERSION, $alt_sb_groups, HOUR_IN_SECONDS);
}

// ---------------------------------------------------------------------------
// PRESS STATEMENTS ("Numbers you can use right now") + AI EVIDENCE LADDER DATA
//
// Soundbites are one sentence. Reporters also need a short paragraph they can
// paste into a pitch, with the filtered view already built so the claim can be
// checked in one click. Everything below is generated from live data, cached
// hourly, and every statement carries the preset link that reproduces it.
// ---------------------------------------------------------------------------
$alt_ps = get_transient('alt_press_statements_' . ALT_VERSION);
if (!is_array($alt_ps)) {
    global $wpdb; $alt_pt = alt_db_table();
    $alt_ptk = home_url('/ai-layoff-tracker/');
    $alt_plk = function ($args) use ($alt_ptk) { return esc_url(add_query_arg($args, $alt_ptk)); };
    $alt_pn = function ($v) { return number_format((int) $v); };

    // Evidence tiers. These are not new labels: they are the ai_causation values
    // already stored on every row, surfaced so a reporter can choose the
    // strictness their story needs instead of trusting one blended number.
    $alt_tiers = $wpdb->get_row(
        "SELECT COALESCE(SUM(CASE WHEN ai_causation='primary_cause' AND announced=0 THEN job_count END),0) t1,
                COALESCE(SUM(CASE WHEN ai_causation='contributing_cause' AND announced=0 THEN job_count END),0) t2,
                COALESCE(SUM(CASE WHEN ai_causation='ai_linked' AND announced=0 THEN job_count END),0) t3
         FROM $alt_pt WHERE YEAR(layoff_date) = " . (int) gmdate('Y'));

    // One period's figures.
    $alt_pstats = function ($from, $to) use ($wpdb, $alt_pt) {
        return $wpdb->get_row($wpdb->prepare(
            "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                    COALESCE(SUM(CASE WHEN announced=1 THEN job_count END),0) a,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai,
                    COUNT(DISTINCT CASE WHEN announced=0 THEN company_key END) co
             FROM $alt_pt WHERE layoff_date BETWEEN %s AND %s", $from, $to));
    };
    $alt_ptopcol = function ($col, $from, $to, $ai_only) use ($wpdb, $alt_pt) {
        $extra = $ai_only ? " AND ai_explicit=1" : "";
        return $wpdb->get_row($wpdb->prepare(
            "SELECT $col k, SUM(job_count) j FROM $alt_pt
             WHERE layoff_date BETWEEN %s AND %s AND $col <> '' AND announced=0 $extra
             GROUP BY $col ORDER BY j DESC LIMIT 1", $from, $to));
    };
    $alt_pbig = function ($from, $to) use ($wpdb, $alt_pt) {
        return $wpdb->get_row($wpdb->prepare(
            "SELECT company, job_count, country FROM $alt_pt
             WHERE layoff_date BETWEEN %s AND %s AND announced=0 AND job_count > 0
             ORDER BY job_count DESC, id DESC LIMIT 1", $from, $to));
    };
    $alt_stn = array('AL'=>'Alabama','AK'=>'Alaska','AZ'=>'Arizona','AR'=>'Arkansas','CA'=>'California','CO'=>'Colorado','CT'=>'Connecticut','DE'=>'Delaware','DC'=>'Washington, D.C.','FL'=>'Florida','GA'=>'Georgia','HI'=>'Hawaii','ID'=>'Idaho','IL'=>'Illinois','IN'=>'Indiana','IA'=>'Iowa','KS'=>'Kansas','KY'=>'Kentucky','LA'=>'Louisiana','ME'=>'Maine','MD'=>'Maryland','MA'=>'Massachusetts','MI'=>'Michigan','MN'=>'Minnesota','MS'=>'Mississippi','MO'=>'Missouri','MT'=>'Montana','NE'=>'Nebraska','NV'=>'Nevada','NH'=>'New Hampshire','NJ'=>'New Jersey','NM'=>'New Mexico','NY'=>'New York','NC'=>'North Carolina','ND'=>'North Dakota','OH'=>'Ohio','OK'=>'Oklahoma','OR'=>'Oregon','PA'=>'Pennsylvania','RI'=>'Rhode Island','SC'=>'South Carolina','SD'=>'South Dakota','TN'=>'Tennessee','TX'=>'Texas','UT'=>'Utah','VT'=>'Vermont','VA'=>'Virginia','WA'=>'Washington','WV'=>'West Virginia','WI'=>'Wisconsin','WY'=>'Wyoming');

    // Build the statement set for one cadence. Copy rule: the number, the
    // period, one context sentence, the link. The "documented floor vs survey
    // estimates" framing is said ONCE at the top of the page, not per card.
    $alt_build = function ($from, $to, $label, $linkargs) use ($alt_pstats, $alt_ptopcol, $alt_pbig, $alt_plk, $alt_pn, $alt_stn) {
        $s = $alt_pstats($from, $to);
        $v = (int) ($s->v ?? 0); $a = (int) ($s->a ?? 0);
        $ai = (int) ($s->ai ?? 0); $co = (int) ($s->co ?? 0);
        if ($v <= 0) return array();
        $out = array();
        $pct = $v > 0 ? round(100 * $ai / $v) : 0;

        // A short window can legitimately contain no explicit AI attribution.
        // Saying "0 (0%)" reads like a broken statistic; say it plainly instead.
        $aiclause = $ai > 0
            ? sprintf('Employers themselves blamed AI or automation for %s of those jobs (%d%%), each with the quote on file.',
                      $alt_pn($ai), $pct)
            : 'No employer has named AI as a cause in this window yet. That is normal for a short window: filings record a cut\'s size, date and location first, and the company\'s stated reason often arrives later.';
        $annclause = $a > 0
            ? sprintf(' A further %s announced cuts are tracked in a separate tier until they take effect, and are never mixed into this figure.', $alt_pn($a))
            : '';
        $out[] = array(
            'label' => 'The documented floor',
            'text'  => sprintf(
                'For %s, %s job cuts are documented worldwide, across %s companies, each counted on the day it takes effect. %s%s',
                $label, $alt_pn($v), $alt_pn($co), $aiclause, $annclause),
            'link' => $alt_plk($linkargs), 'linklabel' => 'See the rows behind this number');

        $st = $alt_ptopcol('state', $from, $to, false);
        if ($st && $st->k && isset($alt_stn[$st->k])) {
            $stai = $alt_ptopcol('state', $from, $to, true);
            $aitxt = ($stai && $stai->k === $st->k)
                ? sprintf(' %s of those carry the employer\'s own AI attribution.', $alt_pn($stai->j))
                : '';
            $out[] = array(
                'label' => alt_country_flag('United States') . ' Top US state',
                'text'  => sprintf(
                    '%s recorded more documented job cuts than any other US state for %s: %s jobs.%s Every row names the employer, the site and the effective date, straight from the state\'s WARN notice or the company\'s SEC filing.',
                    $alt_stn[$st->k], $label, $alt_pn($st->j), $aitxt),
                'link' => $alt_plk(array_merge($linkargs, array('country' => 'United States', 'state' => $st->k))),
                'linklabel' => 'See the ' . $alt_stn[$st->k] . ' rows');
        }

        $ind = $alt_ptopcol('industry', $from, $to, false);
        if ($ind && $ind->k) {
            $out[] = array(
                'label' => 'Sector concentration',
                'text'  => sprintf(
                    '%s took the biggest hit of any sector for %s, with %s documented job cuts. Industry labels come from a fixed list, so the same filter always reproduces this breakdown.',
                    $ind->k, $label, $alt_pn($ind->j)),
                'link' => $alt_plk(array_merge($linkargs, array('industry' => $ind->k))),
                'linklabel' => 'See the ' . $ind->k . ' rows');
        }

        $big = $alt_pbig($from, $to);
        if ($big && $big->company) {
            $out[] = array(
                'label' => 'Largest single documented cut',
                'text'  => sprintf(
                    'The largest single documented cut for %s: %s, at %s jobs. The entry links to the filing or named report that put the number on the record, so it can be checked at source before it is quoted.',
                    $label, $big->company, $alt_pn($big->job_count)),
                'link' => $alt_plk(array_merge($linkargs, array('company' => $big->company))),
                'linklabel' => 'See the ' . $big->company . ' entries');
        }
        return $out;
    };

    $alt_y2 = (int) gmdate('Y');
    $alt_wk_from = gmdate('Y-m-d', strtotime('-7 days'));
    $alt_wk_to   = gmdate('Y-m-d');
    $alt_lmts    = strtotime(gmdate('Y-m-01') . ' -1 day');
    $alt_mo_from = gmdate('Y-m-01', $alt_lmts); $alt_mo_to = gmdate('Y-m-t', $alt_lmts);
    $alt_mo_lab  = gmdate('F Y', $alt_lmts);

    $alt_ps = array(
        'generated' => gmdate('j F Y, H:i') . ' UTC',
        'tiers'     => array(
            't1' => (int) ($alt_tiers->t1 ?? 0),
            't2' => (int) ($alt_tiers->t2 ?? 0),
            't3' => (int) ($alt_tiers->t3 ?? 0),
            'year' => $alt_y2,
        ),
        'sets' => array(
            array('id' => 'weekly', 'title' => 'This week', 'sub' => 'rolling 7 days to ' . gmdate('j F Y'),
                  'items' => $alt_build($alt_wk_from, $alt_wk_to, 'the last seven days',
                                        array('from' => $alt_wk_from, 'to' => $alt_wk_to))),
            array('id' => 'monthly', 'title' => $alt_mo_lab, 'sub' => 'complete calendar month',
                  'items' => $alt_build($alt_mo_from, $alt_mo_to, $alt_mo_lab,
                                        array('from' => $alt_mo_from, 'to' => $alt_mo_to))),
            array('id' => 'yearly', 'title' => $alt_y2 . ' year to date', 'sub' => '1 January to today',
                  'items' => $alt_build(sprintf('%04d-01-01', $alt_y2), gmdate('Y-m-d'), $alt_y2 . ' so far',
                                        array('years' => $alt_y2))),
        ),
    );

    // Rolling archive: every earlier month this year and each prior year, so a
    // statement stays reachable after its cadence rolls over.
    $alt_arch = array();
    for ($i = 2; $i <= 13; $i++) {
        $ts = strtotime(gmdate('Y-m-01') . " -$i month");
        $f = gmdate('Y-m-01', $ts); $t = gmdate('Y-m-t', $ts);
        $st = $alt_pstats($f, $t);
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_arch[] = array('label' => gmdate('F Y', $ts), 'v' => (int) $st->v, 'ai' => (int) $st->ai,
                            'link' => $alt_plk(array('from' => $f, 'to' => $t)));
    }
    for ($yy = $alt_y2 - 1; $yy >= $alt_y2 - 6; $yy--) {
        $st = $alt_pstats(sprintf('%04d-01-01', $yy), sprintf('%04d-12-31', $yy));
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_arch[] = array('label' => 'Full year ' . $yy, 'v' => (int) $st->v, 'ai' => (int) $st->ai,
                            'link' => $alt_plk(array('years' => $yy)));
    }
    $alt_ps['archive'] = $alt_arch;
    // Monthly release index, computed here (inside the cache build) because
    // $alt_pstats only exists on a cache MISS. Referencing it from the render
    // path would fatal on every cached page load.
    $alt_rel = array();
    for ($i = 1; $i <= 12; $i++) {
        $ts = strtotime(gmdate('Y-m-01') . " -$i month");
        $f = gmdate('Y-m-01', $ts); $t = gmdate('Y-m-t', $ts);
        $st = $alt_pstats($f, $t);
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_rel[] = array(
            'label'    => gmdate('F Y', $ts),
            'released' => gmdate('j M Y', strtotime(gmdate('Y-m-01', $ts) . ' +1 month')),
            'v' => (int) $st->v, 'ai' => (int) $st->ai,
            'report'   => esc_url(add_query_arg(array('period' => gmdate('Y-m', $ts)),
                                                home_url('/ai-layoff-tracker/report/'))),
        );
    }
    $alt_ps['releases'] = $alt_rel;
    set_transient('alt_press_statements_' . ALT_VERSION, $alt_ps, HOUR_IN_SECONDS);
}
?>
<main class="alt-wrap alt-press-page">
  <?php if (function_exists('alt_dataset_jsonld') && !defined('ALT_PRESS_LD_DONE')) { define('ALT_PRESS_LD_DONE', 1); alt_output_jsonld(array(alt_dataset_jsonld())); } ?>
  <p class="alt-eyebrow">AskTheRecruiter · press &amp; media kit</p>
  <h1>Press &amp; Media Kit</h1>
  <p class="alt-lead"><span class="alt-lead-text">Live layoff numbers you can quote, each with a link to the exact rows behind it. Figures update automatically from the tracker's database and are reproducible from the public API.</span></p>
  <p class="alt-sb-disclaimer"><b>Every number on this page traces to an SEC filing, a state WARN notice, or a named news report. Nothing is estimated.</b> That makes our totals a documented floor, deliberately smaller than announcement surveys: surveys count intentions, including multi-year plans and cuts with no public paper trail. We count what can be verified, on the day each cut takes effect.</p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">How every number is built</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="<?php echo esc_url(home_url('/contact/')); ?>">Contact us</a></p>

  <nav class="alt-press-toc" aria-label="On this page">
    <span class="alt-toc-label">On this page</span>
    <a href="#alt-press-statements">Numbers to use now</a>
    <a href="#alt-soundbites">Soundbites</a>
    <a href="#alt-evidence-ladder">What counts as AI</a>
    <a href="#alt-monthly-release">Monthly releases</a>
    <a href="#alt-key-stats">Yearly totals</a>
    <a href="#alt-cite">How to cite us</a>
    <a href="#alt-boilerplate">About</a>
    <a href="#alt-press-signup">Contact &amp; brief</a>
  </nav>

  <h2 id="alt-press-statements">Numbers you can use right now</h2>
  <p>This week, the latest complete month, and the year to date. Each card is written to be pasted into a pitch or a story, and each ends with a link that opens the live tracker filtered to the exact rows behind the number, so an editor can check the claim in one click.</p>
  <p class="alt-muted"><b>Generated <?php echo esc_html($alt_ps['generated']); ?>.</b> Figures refresh hourly; the wording stays stable. When a period rolls over, it moves to the archive below, so a number you already quoted stays reachable.</p>

  <?php foreach ($alt_ps['sets'] as $alt_set) : if (empty($alt_set['items'])) continue; ?>
  <h3 id="alt-ps-<?php echo esc_attr($alt_set['id']); ?>" class="alt-sb-grouptitle"><?php echo esc_html($alt_set['title']); ?> <small class="alt-muted">(<?php echo esc_html($alt_set['sub']); ?>)</small></h3>
  <div class="alt-soundbites">
    <?php foreach ($alt_set['items'] as $alt_it) : ?>
    <figure class="alt-soundbite alt-press-statement">
      <span class="alt-sb-label"><?php echo esc_html($alt_it['label']); ?></span>
      <blockquote class="alt-sb-text"><?php echo esc_html($alt_it['text']); ?></blockquote>
      <figcaption class="alt-sb-actions">
        <button type="button" class="alt-btn alt-btn-sm alt-sb-copy">Copy statement</button>
        <a class="alt-sb-link" href="<?php echo $alt_it['link']; ?>" target="_blank" rel="noopener">&#128202; <?php echo esc_html($alt_it['linklabel']); ?> &rarr;</a>
      </figcaption>
    </figure>
    <?php endforeach; ?>
  </div>
  <?php endforeach; ?>

  <?php if (!empty($alt_ps['archive'])) : ?>
  <details class="alt-methodology" id="alt-ps-archive">
    <summary>Statement archive (earlier months and years)</summary>
    <div class="alt-method-body">
      <p>Every period keeps its own preset view, so a figure you quoted last quarter stays reachable and checkable.</p>
      <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table">
        <thead><tr><th>Period</th><th>Documented job cuts</th><th>AI, employer's own words</th><th>Preset view</th></tr></thead>
        <tbody>
        <?php foreach ($alt_ps['archive'] as $alt_a) : ?>
          <tr>
            <th><?php echo esc_html($alt_a['label']); ?></th>
            <td><?php echo number_format($alt_a['v']); ?></td>
            <td><?php echo number_format($alt_a['ai']); ?></td>
            <td><a href="<?php echo $alt_a['link']; ?>" target="_blank" rel="noopener">Open this period &rarr;</a></td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table></div>
    </div>
  </details>
  <?php endif; ?>

  <?php if ($alt_sb_groups) : ?>
  <h2 id="alt-soundbites">Soundbite library</h2>
  <p>One-line versions of the same numbers, grouped by period and by region. Copy, cite, done. Attribute to "the AI Layoff Tracker by AskTheRecruiter.com." Each links to the chart or rows behind it.</p>
  <p class="alt-sb-disclaimer"><b>Two AI measures, always labeled.</b> <b>Verified</b> means the employer named AI in its own words, quote on file. The <b>broad measure</b> adds looser AI-linked cases (an AI pivot underway, press AI-framing) and is always larger. The two are never merged; pick the standard your story needs.</p>
    <?php foreach ($alt_sb_groups as $alt_g) : ?>
  <h3 id="<?php echo esc_attr($alt_g['id']); ?>" class="alt-sb-grouptitle"><?php echo esc_html($alt_g['title']); ?></h3>
  <div class="alt-soundbites">
      <?php foreach ($alt_g['items'] as $alt_sb) : ?>
    <figure class="alt-soundbite">
      <span class="alt-sb-label"><?php echo esc_html($alt_sb['label']); ?></span>
      <blockquote class="alt-sb-text"><?php echo esc_html($alt_sb['text']); ?></blockquote>
      <figcaption class="alt-sb-actions">
        <button type="button" class="alt-btn alt-btn-sm alt-sb-copy">Copy</button>
        <a class="alt-sb-link" href="<?php echo $alt_sb['link']; ?>" target="_blank" rel="noopener">&#128202; <?php echo esc_html($alt_sb['linklabel']); ?> &rarr;</a>
      </figcaption>
    </figure>
      <?php endforeach; ?>
  </div>
    <?php endforeach; ?>
  <p class="alt-muted">Figures are current live values and change as new sources are verified. Every number is reproducible from the public API.</p>
  <?php endif; ?>

  <h2 id="alt-evidence-ladder">What counts as an AI layoff</h2>
  <p>The hardest question about any AI layoff number is what counts as AI. We never publish one blended figure. Every entry records how directly the employer tied the cut to AI, so you can pick the standard your story needs and see exactly what falls in or out at each step.</p>
  <div class="alt-health-table-wrap"><table class="alt-sources-table">
    <thead><tr><th>Tier</th><th>What has to be true</th><th>Where it appears on the tracker</th><th><?php echo (int) $alt_ps['tiers']['year']; ?> jobs<br><small>verified tier</small></th><th>Preset view</th></tr></thead>
    <tbody>
      <tr>
        <td><b>Tier 1</b><br><small>AI named as the cause</small></td>
        <td>The employer states AI or automation is <b>the</b> reason for the cut, with the exact quote on file.</td>
        <td rowspan="2" class="alt-tier-map">Together these are the <b>&#34;AI cuts, verified (specific)&#34;</b> box on the tracker, and the AI figure we headline. Each also has an announced-stage counterpart in <b>&#34;AI cuts, announced&#34;</b>.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t1']); ?></b></td>
        <td rowspan="2"><a href="<?php echo esc_url(add_query_arg(array('years' => $alt_ps['tiers']['year'], 'ai' => '1'), home_url('/ai-layoff-tracker/'))); ?>" target="_blank" rel="noopener">Tiers 1 + 2 &rarr;</a><br><small class="alt-muted">One view: the employer's own words. The per-tier split is in the table.</small></td>
      </tr>
      <tr>
        <td><b>Tier 2</b><br><small>AI named among the causes</small></td>
        <td>The employer names AI as <b>a</b> contributing cause alongside others, again with the quote on file.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t2']); ?></b></td>
      </tr>
      <tr>
        <td><b>Tier 3</b><br><small>AI-linked, no direct statement</small></td>
        <td>No employer statement. An AI pivot is underway, or the press framed the cut that way. Reported separately and <b>never</b> merged into the tiers above.</td>
        <td>This tier is exactly what the <b>&#34;AI-linked, broad&#34;</b> box adds on top of the specific figure. It is the only reason that box is larger.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t3']); ?></b></td>
        <td><a href="<?php echo esc_url(add_query_arg(array('years' => $alt_ps['tiers']['year'], 'ai_broad' => '1'), home_url('/ai-layoff-tracker/'))); ?>" target="_blank" rel="noopener">Tiers 1 + 2 + 3 &rarr;</a></td>
      </tr>
    </tbody>
  </table></div>
  <p><b>These are not a second set of numbers.</b> The tiers are the same rows you already see on the tracker, sorted by how directly the employer tied the cut to AI, while verified and announced sort the same rows by whether the cut has happened yet. The two axes reconcile exactly: Tier 1 plus Tier 2 equals the tracker's verified AI box to the job, and Tier 3 is precisely the gap between the specific figure and the broad one. Nothing is double counted and nothing is invented for this table.</p>
  <p class="alt-muted">Counts are <b>verified-tier</b> jobs (announced-stage plans excluded) for rows where the employer's stated causation is on record. Our headline AI figure is <b>Tiers 1 and 2 only</b>: the employer's own words. Investment in AI, a future automation projection, or AI used to select who goes does not qualify by itself. If you want the wider lens, cite Tier 3 explicitly and say so.</p>

  <h2 id="alt-monthly-release">Monthly release schedule</h2>
  <p>Each month's figures are final once that month has closed, and the one-page report for it lives at a permanent link. The release date is the <b>1st of the following month</b>. Nothing is embargoed and nothing is held back: the link is live the moment the month closes.</p>
  <div class="alt-health-table-wrap"><table class="alt-sortable alt-sources-table">
    <thead><tr><th>Period</th><th>Released</th><th>Documented job cuts</th><th>AI, employer's own words</th><th>One-page report</th></tr></thead>
    <tbody>
    <?php foreach (($alt_ps['releases'] ?? array()) as $alt_r) : ?>
      <tr>
        <th><?php echo esc_html($alt_r['label']); ?></th>
        <td><?php echo esc_html($alt_r['released']); ?></td>
        <td><?php echo number_format($alt_r['v']); ?></td>
        <td><?php echo number_format($alt_r['ai']); ?></td>
        <td><a href="<?php echo $alt_r['report']; ?>" target="_blank" rel="noopener">Open the <?php echo esc_html($alt_r['label']); ?> report &rarr;</a></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p class="alt-muted">Every report link is permanent, so a story that cites the March figure still resolves to the March figure a year later.</p>

  <h2 id="alt-key-stats">Yearly totals</h2>
  <p>Live figures from the same database the tracker serves. "AI-attributed" uses our strict standard: the company named AI as a primary or contributing cause, with a supporting quote on file. A separate broader measure is available in the <code>ai_broad_jobs</code> API field.</p>
  <?php $alt_lu = function_exists('alt_data_last_updated_label') ? alt_data_last_updated_label() : ''; ?>
  <?php if ($alt_lu) : ?><p class="alt-muted"><b>Data last updated:</b> <?php echo esc_html($alt_lu); ?>, the moment the underlying database last changed (a new filing/notice/report was added), not the time you loaded this page.</p><?php endif; ?>
  <div class="alt-health-table-wrap"><table class="alt-press-table">
    <thead><tr><th>Year</th><th class="num">Verified layoffs</th><th class="num">Job cuts recorded</th><th class="num">AI-attributed (strict)</th></tr></thead>
    <tbody>
    <?php foreach ($alt_press_years as $alt_yr) : ?>
      <tr><td><b><?php echo (int) $alt_yr['y']; ?></b></td><td class="num"><?php echo number_format((int) $alt_yr['entries']); ?></td><td class="num"><?php echo number_format((int) $alt_yr['jobs']); ?></td><td class="num"><?php echo number_format((int) $alt_yr['ai_jobs']); ?></td></tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p>Coverage depth varies by year: 2015 to 2023 is primarily official US WARN filings; from 2024 on, worldwide news, SEC filings and European Restructuring Monitor coverage deepen. Methodology and per-country sources are documented on the tracker itself.</p>

  <h2 id="alt-cite">How to cite us</h2>
  <p>The data is free for editorial, research, and educational use under <b>CC BY 4.0</b>. Attribute to asktherecruiter.com and link back where possible.</p>
  <p><b>Suggested attribution:</b> "According to the AI Layoff Tracker by AskTheRecruiter.com..."</p>
  <p><b>One-line description:</b> "The AI Layoff Tracker by AskTheRecruiter.com, a source-linked database of layoffs worldwide, flagging the ones companies blame on AI."</p>
  <ul>
    <li><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">Methodology</a>: how every number is built, counted, and corrected.</li>
    <li><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>">AI layoffs, in their own words</a>: every employer AI attribution, verbatim, with its source.</li>
    <li><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a>: the full list of collectors and what each one covers.</li>
  </ul>
  <h3 id="alt-dataset">Get the full dataset</h3>
  <p>Filtered or full CSV and JSON exports are on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">tracker page</a>. The public REST API serves the same data live: <code>GET /blog/wp-json/layoffs/v1/query</code> and <code>GET /blog/wp-json/layoffs/v1/aggregate</code>. Company pages with stable, linkable URLs live under <code>/company-layoffs/</code>, so a reporter can cite one company's full source-linked history at a permanent address.</p>

  <h2 id="alt-boilerplate">About the tracker</h2>
  <p><b>Boilerplate:</b> AskTheRecruiter is the open, evidence-based intelligence platform helping workers understand the changing job market and improve their chances of getting hired. Its <b>AI Layoff Tracker</b> is a continuously updated, source-linked database of verified job cuts worldwide, purpose-built to flag which layoffs companies themselves attribute to AI or automation, every figure clickable back to a primary document.</p>
  <p>Live editorial tracking began in January 2026. The database also carries historical records back to 2002 (Europe) and 2015 (US), built from official WARN filings, SEC disclosures and the EU's restructuring monitor, so year-over-year comparisons are possible.</p>

  <h3 id="alt-why-cite">Why it's worth citing</h3>
  <div class="alt-health-table-wrap"><table class="alt-sources-table alt-angles-table">
    <thead><tr><th>The angle</th><th>Why it's a story</th></tr></thead>
    <tbody>
      <tr><td><b>We break out the AI cuts</b></td><td>Most layoff trackers give you one lump-sum number and stop. We flag the cuts a company itself pinned on AI or automation, each with the employer's own quote on file, so "AI-attributed" becomes a figure a reporter can source instead of guess at.</td></tr>
      <tr><td><b>Every number is a receipt</b></td><td>Estimate-based trackers hand you a figure. We hand you the document behind it: an SEC filing, a WARN notice, or a named report. It's a floor you can prove, not a projection.</td></tr>
      <tr><td><b>We count each cut once, on the day it happens</b></td><td>Every layoff is dated by when it takes effect, not when its notice was filed, and de-duplicated so one event is never summed twice. That is why we land within about 10 percent of independent WARN trackers. A tracker reporting several times higher is usually adding a company-wide headcount onto every state filing, which counts the same people over and over.</td></tr>
      <tr><td><b>We show where AI is cutting</b></td><td>A live world map, the teams hit hardest, and AI's rising share month over month: the geographic and functional detail a press release can't give a reporter.</td></tr>
      <tr><td><b>We audit our own completeness</b></td><td>We keep a standing checklist of 51 of the most significant layoffs major outlets have covered and re-check our database against it every week. We currently carry every one of them. Any gap is a finding we chase and backfill, not a number we quietly round up to.</td></tr>
      <tr><td><b>Nothing is hidden</b></td><td>A public corrections log, open methodology, the full source list, and an API anyone can reproduce. When we catch an error, we publish it.</td></tr>
    </tbody>
  </table></div>

  <h3>Editorial independence</h3>
  <p>The tracker is a data product of AskTheRecruiter.com. Its numbers are produced by fixed, published rules: counts come only from linked primary documents, AI labels require the employer's own words, and no figure is adjusted for any commercial purpose. The full methodology, the per-country source list, the public corrections log and the collection code are open for inspection, and the dataset can be reproduced from the public API by anyone.</p>

  <h3 id="alt-brand">Brand assets</h3>
  <div class="alt-brand-kit">
    <span class="alt-brand-lockup">
      <span class="alt-brand-mark" aria-hidden="true">atr</span>
      <span class="alt-brand-word">Ask The Recruiter</span>
    </span>
    <ul class="alt-brand-colors">
      <li><span class="alt-swatch" style="background:#4f7257"></span> Primary green <code>#4F7257</code></li>
      <li><span class="alt-swatch" style="background:#d4a574"></span> Accent <code>#D4A574</code></li>
      <li><span class="alt-swatch" style="background:#16181d"></span> Ink <code>#16181D</code></li>
    </ul>
  </div>
  <p class="alt-muted">The wordmark and "atr" mark above may be used to credit the tracker in coverage. For high-resolution PNG or SVG logo files or a specific lockup, ask through the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> and we'll send them the same day.</p>

  <h2>Press contact</h2>
  <p>For data requests, custom cuts of the dataset, corrections, or comment, use the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>. Press and reporter requests get priority, and every correction to a published figure is logged publicly on the tracker.</p>

  <?php
  $alt_sub_a = wp_rand(2, 9); $alt_sub_b = wp_rand(2, 9);
  $alt_sub_tok = wp_generate_password(16, false, false);
  set_transient('alt_captcha_' . $alt_sub_tok, $alt_sub_a + $alt_sub_b, 30 * MINUTE_IN_SECONDS);
  ?>
  <section id="alt-press-signup" class="alt-press-signup">
    <h2>Get the monthly brief</h2>
    <p>One email a month when the numbers close: the documented job-cut total, the AI figure in the employer's own words, the biggest cuts, and the preset links to check every claim. Built for reporters on deadline. No spam, unsubscribe any time.</p>
    <?php if (isset($_GET['alt_sub'])) : ?>
      <p class="alt-sub-ok" role="status">You're on the list. The next brief lands the 1st of the month.</p>
    <?php else : ?>
    <form class="alt-sub-form" method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
      <input type="hidden" name="action" value="alt_press_subscribe">
      <input type="hidden" name="alt_captcha_token" value="<?php echo esc_attr($alt_sub_tok); ?>">
      <input type="text" name="alt_hp" class="alt-hp" tabindex="-1" autocomplete="off" aria-hidden="true">
      <input type="email" name="alt_sub_email" required placeholder="you@outlet.com" aria-label="Email">
      <input type="text" name="alt_sub_name" placeholder="Name (optional)" aria-label="Name">
      <input type="text" name="alt_sub_outlet" placeholder="Outlet (optional)" aria-label="Outlet">
      <label class="alt-sub-cap">What is <?php echo (int) $alt_sub_a; ?> + <?php echo (int) $alt_sub_b; ?>? <input type="number" name="alt_captcha" required inputmode="numeric"></label>
      <button type="submit" class="alt-btn">Subscribe</button>
      <?php if (isset($_GET['alt_sub_err'])) : ?><span class="alt-sub-err">Please check the email and the math question.</span><?php endif; ?>
    </form>
    <?php endif; ?>
  </section>
</main>
