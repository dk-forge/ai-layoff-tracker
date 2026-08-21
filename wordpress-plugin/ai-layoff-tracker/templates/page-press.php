<?php if (!defined('ABSPATH')) exit;
/*
  ONE "TODAY" FOR THE WHOLE PAGE, AND IT IS THE READER'S TODAY.

  This page published two of them. The year table below cut on MySQL
  CURDATE(), which this host answers in US Eastern; every other figure cut on
  PHP gmdate('Y-m-d'), which is UTC. Measured live on 2026-08-20 at 21:32 ET,
  the year-to-date block read 1,001,545 for 2026 and the year table read
  1,000,514 for the same year on the same basis, 1,031 apart, with an "as of
  Aug 21" dateline on an evening that was still Aug 20 in every US newsroom.

  Site-local wins, because the audience is American reporters and the dateline
  they will print is theirs. alt_site_today() is the one owner (api.php) and
  db.php reads it too, so the aggregate's to_date_* columns cut at the same
  instant this page does. Everything below derives from $alt_press_now: no
  second call to a clock, so no second answer.

  The clock TIME on the "Generated" stamp moved to the same zone for the same
  reason. It used to be labelled UTC beside an unlabelled UTC date, which is
  how a reader was expected to notice the two were the same zone.
*/
$alt_press_now   = function_exists('alt_site_now_ts') ? alt_site_now_ts() : (int) current_time('timestamp');
$alt_press_today = gmdate('Y-m-d', $alt_press_now);
$alt_press_year  = (int) gmdate('Y', $alt_press_now);
$alt_press_tz    = function_exists('alt_site_tz_abbr') ? alt_site_tz_abbr() : 'UTC';

/*
  WHICH ROWS MAY BE THE PAGE'S HEADLINE EXAMPLE, and why this is a gate rather
  than a correction to one row.

  "Largest single cut" picked the biggest job_count in the window and nothing
  else. On 2026-08-20 that put row 177321, "Automaker Giant", 50,000 jobs, at
  the top of both the statement cards and the soundbite library. That row is
  bronze, provisional, has no country and no employer country, and reaches us
  through a Google News redirect to a content farm that had ANONYMISED the
  employer. The name is the anonymisation. July's example, "Aeternum Health,
  Inc." at 20,000, is gold but equally unreviewed and reads synthetic too.

  A fact-checker's first click on a press page lands on the largest number.
  Editing one row would not have helped: the next content-farm headline with a
  big number would have taken the same slot the same day. So the SELECTION is
  gated, on the two columns that already record how much we trust a row.

  gold = an SEC filing. warn = a state WARN Act notice. silver = a corroborated
  named report. bronze, a single uncorroborated report, cannot carry this slot,
  and neither can any row still marked provisional in review whatever its tier.
  That is deliberately stricter than the totals, which keep every tier: a total
  is a floor built from everything we can trace, an EXAMPLE is a recommendation
  to go and quote one specific company.

  Stated on the page, not just here, in $alt_press_flagship_note below. The
  cards are omitted rather than relaxed when a short window holds no row that
  qualifies.

  Row 177321's own fate is a separate decision: changing a job count changes
  the dedup hash and needs /bulk-purge plus a re-import, and it moves published
  totals. This page simply stops recommending it.
*/
$alt_press_flagship_sql = "verification_level IN ('gold','warn','silver') AND review_status <> 'provisional'";
$alt_press_flagship_note = 'Largest-cut examples come only from entries backed by an SEC filing, a WARN notice or a corroborated report, and never from a row still marked provisional in review.';

// Year-by-year stats straight from the fast table, cached an hour. The press
// page must never show a number the tracker itself cannot reproduce.
$alt_press_years = get_transient(alt_figure_cache_key('press_year_stats'));
if (!is_array($alt_press_years)) {
    global $wpdb;
    $alt_t = alt_db_table();
    $alt_press_years = $wpdb->get_results($wpdb->prepare(
        // superset_of=0, for the reason every other query on this page carries
        // it: a rollup row and its members are the same jobs twice. Without it
        // the 2026 row read 935,408 against the API's 922,720 for the same
        // window and the same measure, +12,688, on the page that exists to be
        // reproducible. The event count is likewise events, not "verified"
        // ones: it has always included the announced tier, so the column is
        // named for what it counts.
        "SELECT YEAR(layoff_date) y, COUNT(*) entries, COALESCE(SUM(job_count),0) jobs,
                COALESCE(SUM(CASE WHEN ai_explicit=1 THEN job_count END),0) ai_jobs
         FROM $alt_t WHERE superset_of=0 AND layoff_date >= '2015-01-01' AND layoff_date <= %s
         GROUP BY YEAR(layoff_date) ORDER BY y DESC", $alt_press_today), ARRAY_A) ?: array();
    set_transient(alt_figure_cache_key('press_year_stats'), $alt_press_years, HOUR_IN_SECONDS);
}

// Data-backed soundbite LIBRARY, grouped, live, source-reproducible sentences,
// one per chart/metric across two periods (this year to date + latest month)
// plus a per-region/country set. No em-dashes. Cached hourly; raw text stored
// (the template esc_html()s at render). Every link uses ONLY params the
// tracker front-end actually parses (restoreFiltersFromUrl in layoffs.js):
// years/months/from/to/industry/country/state/roles/company/ai/ai_broad.
$alt_sb_groups = get_transient(alt_figure_cache_key('press_sb_groups'));
if (!is_array($alt_sb_groups)) {
    global $wpdb; $alt_t = alt_db_table();
    $alt_tk = home_url('/ai-layoff-tracker/');
    $alt_y = $alt_press_year;
    $alt_ytd_from = sprintf('%04d-01-01', $alt_y); $alt_ytd_to = $alt_press_today;
    $alt_lm = strtotime(gmdate('Y-m-01', $alt_press_now) . ' -1 day');
    $alt_m_from = gmdate('Y-m-01', $alt_lm); $alt_m_to = gmdate('Y-m-t', $alt_lm);
    $alt_m_label = gmdate('F Y', $alt_lm);
    /*
      EVERY LINK OFF THIS PAGE NAMES THE BASIS ITS FIGURE WAS COUNTED ON, and it
      is done here rather than at the sixteen call sites for the reason this
      whole class of defect exists: a default copied by hand into sixteen places
      is a default that will next be updated in fifteen.

      Every statistic on this page is computed by the closures below on
      hardcoded `layoff_date BETWEEN` — the EFFECTIVE date. Since 2.20.4 the
      tracker page a reader lands on defaults to the FILING date, and a URL that
      says nothing gets that default (layoffs.js only overrides on an explicit
      date_basis). So "See the rows behind this number" was opening a view that
      recounted the number. 2.20.11 fixed three such links on this page (the two
      evidence-tier links further down, and the report/widget ones); these were
      the other sixteen, in the same file, under the same sentence.

      Measured live 2026-08-11, the year-to-date press headline:
        the sentence      479,037 verified jobs / 3,308 entries
        the link, before  480,685 / 3,450
      1,648 apart, which is the trap: two wrong things partly cancelling. Naming
      the basis ALONE would have moved the link to 514,111, a 35,074 gap and a
      visibly worse page. See the year-to-date window note below; both halves
      ship together or neither is a fix.

      Unconditional, not conditional on the args carrying a date window: on a
      windowless link the basis is a no-op, and a rule with an exception in it is
      the next thing to drift.
    */
    $alt_lk = function ($args) use ($alt_tk) {
        return esc_url(add_query_arg(array_merge(array('date_basis' => 'effective'), $args), $alt_tk));
    };
    $alt_stmap = alt_us_state_names();

    // Query helpers (columns are fixed literals, not user input).
    $alt_stats = function ($from, $to, $cty) use ($wpdb, $alt_t) {
        // v = verified job cuts; aiv = strict AI (employer's own words); aib = the
        // broad AI-linked measure (matches the ai_broad_jobs aggregate exactly:
        // ai_explicit OR ai_causation='ai_linked'). Both AI measures share the
        // verified-tier (announced=0) denominator so their percentages compare.
        // superset_of=0: without it the headline counted rollup rows AND their
        // members (+25,242 on the 2026 floor, audit 2026-07-28), contradicting
        // the API and the FAQ on the same site.
        $sql = "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                       COALESCE(SUM(CASE WHEN announced=1 THEN job_count END),0) a,
                       COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) aiv,
                       COALESCE(SUM(CASE WHEN (ai_explicit=1 OR ai_causation='ai_linked') AND announced=0 THEN job_count END),0) aib
                FROM $alt_t WHERE superset_of=0 AND layoff_date BETWEEN %s AND %s";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_top = function ($col, $from, $to, $cty) use ($wpdb, $alt_t) {
        // announced=0 + superset_of=0: these cards sit on the SAME page as the
        // verified headline, and without the filters the top-country card read
        // "United States 370,097" against a worldwide verified 368,220 — a
        // single country exceeding the world total (audit 2026-07-28). Announced
        // plans and rollup duplicates must never leak into a quotable card.
        $sql = "SELECT $col k, SUM(job_count) j FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND announced=0 AND superset_of=0 AND $col <> ''";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        $sql .= " GROUP BY $col ORDER BY j DESC LIMIT 1";
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_bigcut = function ($from, $to, $cty) use ($wpdb, $alt_t, $alt_press_flagship_sql) {
        // See the gate note at the top of this file: an EXAMPLE is a
        // recommendation, so it is held to a higher bar than a total.
        $sql = "SELECT company, job_count FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND announced=0 AND superset_of=0 AND job_count > 0 AND $alt_press_flagship_sql";
        $a = array($from, $to); if ($cty !== '') { $sql .= " AND country = %s"; $a[] = $cty; }
        $sql .= " ORDER BY job_count DESC, id DESC LIMIT 1";
        return $wpdb->get_row($wpdb->prepare($sql, $a));
    };
    $alt_toprole = function ($from, $to) use ($wpdb, $alt_t) {
        if (!function_exists('alt_role_categories')) return null;
        $best = null; $bj = 0; $bs = '';
        foreach (alt_role_categories() as $slug => $lab) {
            $j = (int) $wpdb->get_var($wpdb->prepare("SELECT COALESCE(SUM(job_count),0) FROM $alt_t WHERE layoff_date BETWEEN %s AND %s AND announced=0 AND superset_of=0 AND role_categories LIKE %s", $from, $to, '%,' . $slug . ',%'));
            if ($j > $bj) { $bj = $j; $best = $lab; $bs = $slug; }
        }
        return $best ? array('label' => $best, 'slug' => $bs, 'j' => $bj) : null;
    };

    // Build one period's chart soundbites (worldwide). Copy rule: one number,
    // one period, at most one context clause. The methodology caveat lives
    // ONCE at the top of the page, never inside the bites.
    $alt_period_items = function ($from, $to, $when, $periodarg, $reportlink) use ($alt_stats, $alt_top, $alt_bigcut, $alt_toprole, $alt_lk, $alt_stmap) {
        $items = array();
        $s = $alt_stats($from, $to, ''); $v = (int) ($s->v ?? 0); $ann = (int) ($s->a ?? 0); $aiv = (int) ($s->aiv ?? 0); $aib = (int) ($s->aib ?? 0);
        $pct = $v ? round(100 * $aiv / $v) : 0; $pctb = $v ? round(100 * $aib / $v) : 0;
        // The second tier, stated where the total is (owner decision
        // 2026-08-14): the announced-inclusive figure rides in the quotable
        // sentence itself, so a paste keeps both tiers. The tier sentence
        // lives once, in the disclaimer above the soundbite library.
        $tier = $ann > 0 ? ' Including announced cuts, ' . number_format($v + $ann) . '.' : '';
        if ($v) $items[] = array('label' => 'Headline', 'text' => 'The AI Layoff Tracker verified ' . number_format($v) . ' job cuts worldwide in ' . $when . '. Employers themselves blamed AI for ' . $pct . '% of them; counting every cut with any AI link, the share reaches ' . $pctb . '%.' . $tier, 'link' => $alt_lk($periodarg), 'linklabel' => 'See the rows behind this number');
        $ind = $alt_top('industry', $from, $to, '');
        if ($ind && $ind->k) $items[] = array('label' => 'Top industry', 'text' => $ind->k . ' was the hardest-hit industry in ' . $when . ', with ' . number_format((int) $ind->j) . ' recorded job cuts.', 'link' => $alt_lk(array_merge($periodarg, array('industry' => $ind->k))), 'linklabel' => 'See the ' . $ind->k . ' rows');
        $ctry = $alt_top('country', $from, $to, '');
        if ($ctry && $ctry->k) $items[] = array('label' => 'Top country', 'text' => $ctry->k . ' led the world in recorded job cuts in ' . $when . ', with ' . number_format((int) $ctry->j) . '.', 'link' => $alt_lk(array_merge($periodarg, array('country' => $ctry->k))), 'linklabel' => 'See the ' . $ctry->k . ' rows');
        $st = $alt_top('state', $from, $to, 'United States');
        if ($st && $st->k) $items[] = array('label' => 'Top US state', 'text' => (isset($alt_stmap[$st->k]) ? $alt_stmap[$st->k] : $st->k) . ' recorded the most US layoffs in ' . $when . ', with ' . number_format((int) $st->j) . '.', 'link' => $alt_lk(array_merge($periodarg, array('country' => 'United States', 'state' => $st->k))), 'linklabel' => 'See the ' . (isset($alt_stmap[$st->k]) ? $alt_stmap[$st->k] : $st->k) . ' rows');
        $r = $alt_toprole($from, $to);
        if ($r) $items[] = array('label' => 'Roles hit hardest', 'text' => $r['label'] . ' was the job function hit hardest in ' . $when . ', across ' . number_format($r['j']) . ' cuts where the source named the team affected.', 'link' => $alt_lk(array_merge($periodarg, array('roles' => $r['slug']))), 'linklabel' => 'See the ' . $r['label'] . ' rows');
        $big = $alt_bigcut($from, $to, '');
        if ($big && $big->company) $items[] = array('label' => 'Largest single cut', 'text' => 'The largest single layoff in ' . $when . ', among entries with strong evidence and no open review flag: ' . $big->company . ', at ' . number_format((int) $big->job_count) . ' jobs.', 'link' => $alt_lk(array_merge($periodarg, array('company' => $big->company))), 'linklabel' => 'See the ' . $big->company . ' entries');
        return $items;
    };

    $alt_sb_groups = array();
    /*
      "SO FAR" IS A WINDOW, AND THE LINK HAS TO CARRY THAT WINDOW.

      These figures are computed Jan 1 -> TODAY and labelled "<year> so far",
      but the link was `years=<year>`: the whole calendar year. Rows are dated by
      effective date and WARN notices are filed by law weeks ahead, so the
      calendar year legitimately holds cuts that have not happened, and the link
      under a "so far" sentence opened a wider view than the sentence described.
      alt_signal_board_periods() fixed exactly this for the board's YTD column
      (33,939 not-yet-effective jobs on 2026-08-04); the press page still had it.

      Measured 2026-08-11 on the matched effective basis: `years=2026` returns
      514,111 verified jobs against the sentence's 479,037. Naming the basis
      without narrowing the window would therefore have widened the gap from
      1,648 to 35,074 - the two defects were partly cancelling.
    */
    $ytd_items = $alt_period_items($alt_ytd_from, $alt_ytd_to, $alt_y . ' so far',
                                   array('from' => $alt_ytd_from, 'to' => $alt_ytd_to), '');
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
        $s = $alt_stats($alt_ytd_from, $alt_ytd_to, $p[1]); $v = (int) ($s->v ?? 0); $ann = (int) ($s->a ?? 0); $aiv = (int) ($s->aiv ?? 0); $aib = (int) ($s->aib ?? 0);
        $pct = $v ? round(100 * $aiv / $v) : 0; $pctb = $v ? round(100 * $aib / $v) : 0;
        $flag = alt_country_flag($p[1] === '' ? 'World' : $p[1]);
        // The announced-inclusive companion rides in the sentence, same as the
        // Headline soundbite above; the tier sentence lives once in the
        // disclaimer over the library.
        $tier = $ann > 0 ? ' Including announced cuts, ' . number_format($v + $ann) . '.' : '';
        // Same Jan 1 -> today window as the year-to-date block above (these come
        // from the same $alt_ytd_from/$alt_ytd_to pair), so the same from/to link.
        $geo_win = array('from' => $alt_ytd_from, 'to' => $alt_ytd_to);
        if ($v > 0) $geo_items[] = array('label' => ($flag ? $flag . ' ' : '') . $p[0], 'text' => $p[2] . number_format($v) . ' job cuts are on record for ' . $alt_y . '. Employers blamed AI for ' . $pct . '% of them; ' . $pctb . '% carry any AI link.' . $tier, 'link' => $alt_lk($p[1] === '' ? $geo_win : array_merge($geo_win, array('country' => $p[1]))), 'linklabel' => 'See the rows behind this number');
    }
    if ($geo_items) $alt_sb_groups[] = array('id' => 'sb-geo', 'title' => 'By region and country (' . $alt_y . ')', 'items' => $geo_items);

    set_transient(alt_figure_cache_key('press_sb_groups'), $alt_sb_groups, HOUR_IN_SECONDS);
}

// ---------------------------------------------------------------------------
// PRESS STATEMENTS ("Numbers you can use right now") + AI EVIDENCE LADDER DATA
//
// Soundbites are one sentence. Reporters also need a short paragraph they can
// paste into a pitch, with the filtered view already built so the claim can be
// checked in one click. Everything below is generated from live data, cached
// hourly, and every statement carries the preset link that reproduces it.
// ---------------------------------------------------------------------------
$alt_ps = get_transient(alt_figure_cache_key('press_statements'));
if (!is_array($alt_ps)) {
    global $wpdb; $alt_pt = alt_db_table();
    $alt_ptk = home_url('/ai-layoff-tracker/');
    // Same rule, same reason, second cache block: see the note on $alt_lk above.
    // Every $alt_pstats / $alt_ptopcol / $alt_pbig figure below is computed on
    // `layoff_date BETWEEN`, so every link off one of them says so.
    $alt_plk = function ($args) use ($alt_ptk) {
        return esc_url(add_query_arg(array_merge(array('date_basis' => 'effective'), $args), $alt_ptk));
    };
    $alt_pn = function ($v) { return number_format((int) $v); };

    // Evidence tiers. These are not new labels: they are the ai_causation values
    // already stored on every row, surfaced so a reporter can choose the
    // strictness their story needs instead of trusting one blended number.
    /*
      THE BOX THE TIERS ARE MEASURED AGAINST, READ RATHER THAN ASSUMED.

      This page asserted "Tier 1 plus Tier 2 equals the tracker's verified AI
      box, to the job". It did not. The tiers sum ai_causation IN
      ('primary_cause','contributing_cause'); every other AI figure on this
      site sums ai_explicit=1, and on 2026-08-20 about 700 jobs carried
      ai_explicit=1 with ai_causation='context_only'. Tiers 42,253, box
      42,953, and the page printed the box six times elsewhere.

      The tier SQL is NOT widened to swallow the remainder. Folding
      context-only rows into "Tier 2: the employer names AI as a contributing
      cause" would make the arithmetic close by making the Tier 2 label false,
      which is the same defect one layer down. Instead the box is read here and
      the residual is printed, so a reporter can reconcile the two definitions
      instead of trusting a claim of equality.
    */
    $alt_tiers = $wpdb->get_row(
        "SELECT COALESCE(SUM(CASE WHEN ai_causation='primary_cause' AND announced=0 THEN job_count END),0) t1,
                COALESCE(SUM(CASE WHEN ai_causation='contributing_cause' AND announced=0 THEN job_count END),0) t2,
                COALESCE(SUM(CASE WHEN ai_causation='ai_linked' AND announced=0 THEN job_count END),0) t3,
                COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) box
         FROM $alt_pt WHERE superset_of=0 AND YEAR(layoff_date) = " . $alt_press_year);

    // One period's figures.
    $alt_pstats = function ($from, $to) use ($wpdb, $alt_pt) {
        return $wpdb->get_row($wpdb->prepare(
            "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v,
                    COALESCE(SUM(CASE WHEN announced=1 THEN job_count END),0) a,
                    COALESCE(SUM(CASE WHEN ai_explicit=1 AND announced=0 THEN job_count END),0) ai,
                    COUNT(DISTINCT CASE WHEN announced=0 THEN company_key END) co
             FROM $alt_pt WHERE superset_of=0 AND layoff_date BETWEEN %s AND %s", $from, $to));
    };
    // THE SAME WINDOW, COUNTED THE WAY THE OTHER SURFACE COUNTS IT.
    //
    // Every figure on this page comes from $alt_pstats, which is
    // `layoff_date BETWEEN` — the EFFECTIVE basis, deliberately, and every
    // receipt link off this page says so. The tracker home page has counted by
    // the FILING basis since 2.20.4. This function is the ONLY thing here that
    // leaves this page's basis, and it exists for exactly one purpose: so the
    // period block below can name the home page's headline figure by READING
    // it rather than by remembering what it used to be. The basis expression
    // comes from alt_db_date_expr() in db.php, the one owner, because a
    // hand-typed date basis is the defect this release is about.
    $alt_pstats_filed = function ($from, $to) use ($wpdb, $alt_pt) {
        $col = function_exists('alt_db_date_expr') ? alt_db_date_expr('notice') : 'layoff_date';
        return $wpdb->get_row($wpdb->prepare(
            "SELECT COALESCE(SUM(CASE WHEN announced=0 THEN job_count END),0) v
             FROM $alt_pt WHERE superset_of=0 AND $col BETWEEN %s AND %s", $from, $to));
    };
    $alt_ptopcol = function ($col, $from, $to, $ai_only) use ($wpdb, $alt_pt) {
        $extra = $ai_only ? " AND ai_explicit=1" : "";
        return $wpdb->get_row($wpdb->prepare(
            "SELECT $col k, SUM(job_count) j FROM $alt_pt
             WHERE superset_of=0 AND layoff_date BETWEEN %s AND %s AND $col <> '' AND announced=0 $extra
             GROUP BY $col ORDER BY j DESC LIMIT 1", $from, $to));
    };
    $alt_pbig = function ($from, $to) use ($wpdb, $alt_pt, $alt_press_flagship_sql) {
        // Same gate as $alt_bigcut, same reason. See the note at the top.
        return $wpdb->get_row($wpdb->prepare(
            "SELECT company, job_count, country FROM $alt_pt
             WHERE superset_of=0 AND layoff_date BETWEEN %s AND %s AND announced=0 AND job_count > 0
               AND $alt_press_flagship_sql
             ORDER BY job_count DESC, id DESC LIMIT 1", $from, $to));
    };
    $alt_stn = alt_us_state_names();

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
        // The second tier, stated where the total is (owner decision
        // 2026-08-14): the announced-inclusive figure beside the verified
        // primary, labeled with the one shared sentence. The verified figure
        // still leads the statement and stays the quotable headline.
        $annclause = $a > 0
            ? sprintf(' Including announced cuts, the figure is %s. %s', $alt_pn($v + $a),
                      function_exists('alt_announced_tier_sentence') ? alt_announced_tier_sentence() : '')
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
                    '%s recorded more documented job cuts than any other US state for %s: %s jobs.%s Every row names the employer, the site and the effective date. The source is the state\'s own WARN notice or the company\'s SEC filing.',
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
                    'The largest single documented cut for %s: %s, at %s jobs. We draw this example only from entries with strong evidence and no open review flag. The entry links to the filing or named report that put the number on the record, so it can be checked at source before it is quoted.',
                    $label, $big->company, $alt_pn($big->job_count)),
                'link' => $alt_plk(array_merge($linkargs, array('company' => $big->company))),
                'linklabel' => 'See the ' . $big->company . ' entries');
        }
        return $out;
    };

    $alt_y2 = $alt_press_year;
    $alt_wk_from = gmdate('Y-m-d', $alt_press_now - 7 * DAY_IN_SECONDS);
    $alt_wk_to   = $alt_press_today;
    $alt_lmts    = strtotime(gmdate('Y-m-01', $alt_press_now) . ' -1 day');
    $alt_mo_from = gmdate('Y-m-01', $alt_lmts); $alt_mo_to = gmdate('Y-m-t', $alt_lmts);
    $alt_mo_lab  = gmdate('F Y', $alt_lmts);

    $alt_ps = array(
        // ONE DATE FORMAT ON THE PAGE BUILT FOR PEOPLE WHO COPY DATES.
        // This page used to print three conventions in one visit: "Aug 11,
        // 2026" in the period table, "11 August 2026" here and on the weekly
        // card, and "1 Aug 2026" down the release schedule. A journalist
        // copying a date off a press kit should not have to normalise it
        // first, and three renderings of one convention is the tell that
        // nobody owns the convention. M j, Y is the house format the rest of
        // the tracker already uses (alt_data_last_updated_label, the
        // methodology audit stamp), so it is the one that stays.
        'generated' => gmdate('M j, Y', $alt_press_now) . ', ' . gmdate('H:i', $alt_press_now) . ' ' . $alt_press_tz,
        'tiers'     => array(
            't1' => (int) ($alt_tiers->t1 ?? 0),
            't2' => (int) ($alt_tiers->t2 ?? 0),
            't3' => (int) ($alt_tiers->t3 ?? 0),
            'box' => (int) ($alt_tiers->box ?? 0),
            'year' => $alt_y2,
        ),
        'sets' => array(
            array('id' => 'weekly', 'title' => 'This week', 'sub' => 'rolling 7 days to ' . gmdate('M j, Y', $alt_press_now),
                  'items' => $alt_build($alt_wk_from, $alt_wk_to, 'the last seven days',
                                        array('from' => $alt_wk_from, 'to' => $alt_wk_to))),
            array('id' => 'monthly', 'title' => $alt_mo_lab, 'sub' => 'complete calendar month',
                  'items' => $alt_build($alt_mo_from, $alt_mo_to, $alt_mo_lab,
                                        array('from' => $alt_mo_from, 'to' => $alt_mo_to))),
            array('id' => 'yearly', 'title' => $alt_y2 . ' year to date', 'sub' => '1 January to today',
                  // from/to, not years=: this block is "1 January to today", and
                  // the calendar year is a wider window. See the note on
                  // $ytd_items above for the measurement.
                  'items' => $alt_build(sprintf('%04d-01-01', $alt_y2), $alt_press_today, $alt_y2 . ' so far',
                                        array('from' => sprintf('%04d-01-01', $alt_y2),
                                              'to' => $alt_press_today))),
        ),
    );

    // Rolling archive: every earlier month this year and each prior year, so a
    // statement stays reachable after its cadence rolls over.
    $alt_arch = array();
    for ($i = 2; $i <= 13; $i++) {
        $ts = strtotime(gmdate('Y-m-01', $alt_press_now) . " -$i month");
        $f = gmdate('Y-m-01', $ts); $t = gmdate('Y-m-t', $ts);
        $st = $alt_pstats($f, $t);
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_arch[] = array('label' => gmdate('F Y', $ts), 'v' => (int) $st->v, 'ai' => (int) $st->ai,
                            'link' => $alt_plk(array('from' => $f, 'to' => $t)),
                            'ai_link' => $alt_plk(array('from' => $f, 'to' => $t, 'ai' => 1)));
    }
    for ($yy = $alt_y2 - 1; $yy >= $alt_y2 - 6; $yy--) {
        $st = $alt_pstats(sprintf('%04d-01-01', $yy), sprintf('%04d-12-31', $yy));
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_arch[] = array('label' => 'Full year ' . $yy, 'v' => (int) $st->v, 'ai' => (int) $st->ai,
                            'link' => $alt_plk(array('years' => $yy)),
                            'ai_link' => $alt_plk(array('years' => $yy, 'ai' => 1)));
    }
    $alt_ps['archive'] = $alt_arch;
    // Monthly release index, computed here (inside the cache build) because
    // $alt_pstats only exists on a cache MISS. Referencing it from the render
    // path would fatal on every cached page load.
    $alt_rel = array();
    for ($i = 1; $i <= 12; $i++) {
        $ts = strtotime(gmdate('Y-m-01', $alt_press_now) . " -$i month");
        $f = gmdate('Y-m-01', $ts); $t = gmdate('Y-m-t', $ts);
        $st = $alt_pstats($f, $t);
        if ((int) ($st->v ?? 0) <= 0) continue;
        $alt_rel[] = array(
            'label'    => gmdate('F Y', $ts),
            'released' => gmdate('M j, Y', strtotime(gmdate('Y-m-01', $ts) . ' +1 month')),
            'v' => (int) $st->v, 'ai' => (int) $st->ai,
            'report'   => esc_url(add_query_arg(array('period' => gmdate('Y-m', $ts)),
                                                home_url('/ai-layoff-tracker/report/'))),
        );
    }
    $alt_ps['releases'] = $alt_rel;

    // THE TWO TOTALS THIS SITE PUBLISHES FOR ONE YEAR, and the arithmetic
    // between them, computed HERE from the same $alt_pstats used by every
    // statement above so the block cannot quote a figure this page did not
    // produce. Only the window differs: to-date ends today, calendar ends
    // 31 December. Every "so far" sentence on this page quotes to-date; the
    // tracker home page headlines the calendar figure. Until 2.19.266 the two
    // surfaces published 450,529 and 484,468 with nothing on either page
    // naming the other, which is a 33,939 gap for a reporter to discover on
    // their own after quoting one of them.
    $alt_cy = $alt_pstats(sprintf('%04d-01-01', $alt_y2), sprintf('%04d-12-31', $alt_y2));
    $alt_td = $alt_pstats(sprintf('%04d-01-01', $alt_y2), $alt_press_today);
    // AND THE SAME CALENDAR YEAR ON THE HOME PAGE'S BASIS, so the block below
    // can state the other surface's figure instead of claiming one of ours is
    // it. This is the read that replaces the sentence that went stale.
    $alt_fy = $alt_pstats_filed(sprintf('%04d-01-01', $alt_y2), sprintf('%04d-12-31', $alt_y2));
    $alt_ps['split'] = array(
        'year'     => $alt_y2,
        'as_of'    => gmdate('M j, Y', $alt_press_now),
        'to_date'  => (int) ($alt_td->v ?? 0),
        'calendar' => (int) ($alt_cy->v ?? 0),
        'later'    => max(0, (int) ($alt_cy->v ?? 0) - (int) ($alt_td->v ?? 0)),
        // The home page's headline, counted the home page's way. Named
        // 'home_*' rather than 'filed_*' because what makes it worth a query
        // is whose number it is, not which basis produced it.
        'home_calendar' => (int) ($alt_fy->v ?? 0),
        'home_basis'    => 'notice',
        'basis'         => 'effective',
    );
    set_transient(alt_figure_cache_key('press_statements'), $alt_ps, HOUR_IN_SECONDS);
}
?>
<main class="alt-wrap alt-press-page">
  <?php /* Dataset JSON-LD intentionally not emitted here: alt_seo_head() already
     emits the single Dataset block on tracker-family pages; a second one with a
     different url read as two conflicting datasets (audit 2026-07-28). */ ?>
  <p class="alt-eyebrow">AskTheRecruiter · press &amp; media kit</p>
  <h1>Press kit and soundbites</h1>
  <p class="alt-lead"><span class="alt-lead-text">AskTheRecruiter is the open intelligence platform helping workers understand the changing job market and improve their chances of getting hired. Live layoff numbers you can quote, each with a link to the exact rows behind it. Figures update automatically from the tracker's database and are reproducible from the public API.</span></p>
  <?php /* THE JUMP MENU IS THE SECOND THING ON THE PAGE, and it moved up here
           in 2.20.32 for the same reason the tracker grew a press button in
           the same release: the thing a reader came for was below the thing
           we wanted to say first.

           Measured live at 375x812 on 2026-08-13, before the move: the h1 sat
           273px down, this nav sat 943px down, and the first quotable
           statement 4,858px down a 26,289px page. So a journalist on a phone
           met the title, a lead, a four-clause methodology disclaimer and a
           row of four outbound links, and had to scroll past all of it before
           anything told them the soundbite library existed. The two "before
           you quote a number" sections below are worth what they cost and are
           NOT moving; this nav is how somebody skips them on purpose.

           The disclaimer did not move down the page and was not shortened. It
           now sits under the menu instead of over it, which is a swap of two
           adjacent blocks, and it is still the first prose a reader meets
           after the lead. */ ?>
  <nav class="alt-press-toc" aria-label="On this page">
    <span class="alt-toc-label">On this page</span>
    <a href="#alt-press-basis">Which basis</a>
    <a href="#alt-press-period">Which period</a>
    <a href="#alt-press-vs-survey">Versus the survey</a>
    <a href="#alt-press-statements">Numbers to use now</a>
    <a href="#alt-soundbites">Soundbites</a>
    <a href="#alt-evidence-ladder">What counts as AI</a>
    <a href="#alt-monthly-release">Monthly releases</a>
    <a href="#alt-key-stats">Yearly totals</a>
    <a href="#alt-cite">How to cite us</a>
    <a href="#alt-boilerplate">About</a>
    <a href="#alt-press-signup">Contact &amp; brief</a>
  </nav>

  <p class="alt-sb-disclaimer"><b>Every number on this page traces to an SEC filing, a state WARN notice, or a named news report. Nothing is estimated.</b> That makes our totals a documented floor, deliberately smaller than announcement surveys: surveys count intentions, including multi-year plans and cuts with no public paper trail. We count what can be verified, on the day each cut takes effect.</p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">How every number is built</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="<?php echo esc_url(home_url('/contact/')); ?>">Contact us</a></p>

  <h2 id="alt-press-basis">Before you quote a number: which basis</h2>
  <p>Our published US headline counts <b>jobs physically located in the US</b>. Most announcement surveys count <b>US-company announcements wherever the jobs land</b>. Those are different questions, so the totals differ by design. Both of ours are below, live, so you can quote the one that matches your comparison.</p>
  <?php if (function_exists('alt_basis_table_html')) echo alt_basis_table_html('United States'); ?>
  <p>If you are comparing us against an announcement survey, use the <b>employer basis</b> row. If you want the most conservative documented figure, use <b>job location</b>. Say which one you used and the number is reproducible from our public API.</p>

  <?php
  /* WHICH PERIOD. The companion to the basis block above, and it exists for the
     same reason: a reporter who reads two of our pages must be able to see why
     two of our numbers differ, on the page, without asking. Every figure below
     comes from $alt_pstats, the same helper behind every statement on this
     page, so the block is reproducible from the API by construction. */
  $alt_sp = isset($alt_ps['split']) && is_array($alt_ps['split']) ? $alt_ps['split'] : null;
  ?>
  <?php if ($alt_sp && $alt_sp['later'] > 0) : ?>
  <h2 id="alt-press-period">Before you quote a number: which period</h2>
  <p>We date every cut on this page by the day it <b>takes effect</b>, and WARN notices are filed weeks ahead by law. So <?php echo (int) $alt_sp['year']; ?> has two correct totals on that basis, and they are not in conflict. Quote the one that matches your sentence, and say which. The tracker home page counts on a <a href="#alt-press-which-date">different date basis again</a>, and that figure is named below too.</p>
  <div class="alt-health-table-wrap">
  <table class="alt-basis-table">
    <thead><tr><th>Counting period</th><th>Verified job cuts</th><th>What it counts, and where we publish it</th></tr></thead>
    <tbody>
      <tr><th>Taken effect, as of <?php echo esc_html($alt_sp['as_of']); ?> <span class="alt-muted">(the figure for a &ldquo;so far&rdquo; sentence)</span></th>
          <td><b><?php echo number_format($alt_sp['to_date']); ?></b></td>
          <td>Cuts whose effective date has arrived. Every statement on this page, the tracker's cite line and the FAQ quote this figure.</td></tr>
      <tr><th>Filed for effective dates later in <?php echo (int) $alt_sp['year']; ?></th>
          <td><b><?php echo number_format($alt_sp['later']); ?></b></td>
          <td>Notices already on file, each with a stated effective date still ahead. Documented, but they have not happened yet.</td></tr>
      <tr><th>Calendar year <?php echo (int) $alt_sp['year']; ?> <span class="alt-muted">(the two rows above, added)</span></th>
          <td><b><?php echo number_format($alt_sp['calendar']); ?></b></td>
          <td>The whole year on this page's basis: the two rows above added, so cuts that have happened plus notices on file for effective dates still ahead.</td></tr>
    </tbody>
  </table>
  </div>
  <p class="alt-press-split"><?php echo esc_html(function_exists('alt_period_split_sentence') ? alt_period_split_sentence($alt_sp['to_date'], $alt_sp['calendar'], $alt_sp['as_of'], (string) $alt_sp['year']) : ''); ?></p>
  <p class="alt-muted">Both figures come from the same query. Only the end date changes, so you can reproduce either one from the public API. For the first row, use <code>aggregate?from=<?php echo (int) $alt_sp['year']; ?>-01-01&amp;to=<?php echo esc_html($alt_press_today); ?></code>. For the third row, use <code>to=<?php echo (int) $alt_sp['year']; ?>-12-31</code>. Verified job cuts are <code>jobs</code> minus <code>announced_jobs</code>. Every date on this page is <?php echo esc_html($alt_press_tz); ?>, including the cut-off for today, so the whole page shares one dateline.</p>

  <?php /* WHICH DATE, the third block, and the one this page was missing.
           The two rows above reconcile two PERIODS on one basis. They do not
           reconcile this page against the tracker's own front page, which has
           counted by the FILING date since 2.20.4 while everything here counts
           by the EFFECTIVE date. Until 2.20.99 the calendar row claimed its
           own figure WAS the home page's headline; that was true when the
           sentence was written and wrong by 33,348 jobs by the time anyone
           checked. The figure is now read live, on the home page's basis, and
           printed. A journalist who lands here and then opens the tracker sees
           the number they are about to meet, before they meet it. */ ?>
  <h3 id="alt-press-which-date">Before you quote a number: which date</h3>
  <p class="alt-press-basis-cross"><?php echo esc_html(function_exists('alt_basis_cross_sentence') ? alt_basis_cross_sentence($alt_sp['home_calendar'], $alt_sp['calendar'], (string) $alt_sp['year']) : ''); ?></p>
  <p class="alt-muted">Filing date is when the notice was lodged; effective date is when the cut lands. The same records, sorted into years by two different dates, so the two totals are not a discrepancy and neither is a revision of the other. Reproduce the home page's figure with <code>aggregate?years=<?php echo (int) $alt_sp['year']; ?>&amp;date_basis=notice</code> and this page's with <code>date_basis=effective</code>. <a href="<?php echo esc_url(add_query_arg(array('years' => (int) $alt_sp['year'], 'date_basis' => 'notice'), home_url('/ai-layoff-tracker/'))); ?>">Open the tracker on the filing basis</a> &middot; <a href="<?php echo esc_url(add_query_arg(array('years' => (int) $alt_sp['year'], 'date_basis' => 'effective'), home_url('/ai-layoff-tracker/'))); ?>">on the effective basis</a>.</p>

  <?php
  /* THE STAMP. Same contract as window.ALT_BOOTSTRAP on the tracker page: the
     surface states the query behind its own figures, and
     railway/published_figures.py verifies every value in here against
     /aggregate and against the home page's live hero rather than believing any
     of it. A page that can define its way to green is not a page worth
     checking, so nothing below is taken on trust - it is only what tells the
     checker which question to ask.

     TWO CARRIERS, and the element is the one that matters. 2.20.99 shipped the
     script tag alone and it did not survive to a reader: something on this host
     rewrites an inline <script> into
     `<script defer src="data:text/javascript;base64,...">`, so the stamp was on
     the page, correct, and invisible to a checker reading for
     `window.ALT_PRESS_STAMP`. This is the same lesson the build stamp learned
     at 2.20.38, where an HTML comment was stripped outright: an element with an
     attribute is not droppable or rewritable that way. The script stays because
     it is the readable form in a view-source and because a page that carries
     the fact twice cannot lose it once. */
  $alt_stamp_json = wp_json_encode(array(
      'aggregate_params' => array('years' => (string) $alt_sp['year'], 'date_basis' => 'effective'),
      'to_date'          => (int) $alt_sp['to_date'],
      'calendar'         => (int) $alt_sp['calendar'],
      'home'             => array('date_basis' => 'notice',
                                  'calendar'   => (int) $alt_sp['home_calendar']),
  ));
  ?>
  <span class="alt-press-stamp" hidden data-alt-press-stamp="<?php echo esc_attr($alt_stamp_json); ?>"></span>
  <script>window.ALT_PRESS_STAMP=<?php echo $alt_stamp_json; ?>;</script>
  <?php endif; ?>

  <?php
  /*
    MONTH BY MONTH AGAINST THE NATIONAL ANNOUNCEMENT SURVEY (owner decision
    2026-08-14). Public, on this page rather than a page of its own, because
    this is the surface a journalist is routed to and the table completes the
    two "before you quote a number" blocks directly above it: basis, period,
    and now the comparison a reader arrives wanting to make.

    OUR SIDE IS RE-DERIVED LIVE ON EVERY CACHE BUILD, never pasted. The
    January 2026 correction moved our monthly figures the same morning this
    table shipped, which is exactly why a typed copy of our own side is
    banned here. THEIR side is hand-entered constants in
    data/survey-monthly.json with the date they were read, shared with
    railway/monthly_us_comparison.py so the repo holds ONE copy. A released
    month with no constant is flagged on the page (the awaiting note below)
    and by the script's STALE verdict; the due window is $alt_mc_due_days and
    must equal DUE_AFTER_DAYS in the script
    (test_stage_tier_and_survey_table pins both). No organization name
    appears anywhere: figures and dates only, per the standalone-brand rule.
  */
  $alt_mc = get_transient(alt_figure_cache_key('press_monthly_compare'));
  if (!is_array($alt_mc)) {
      global $wpdb; $alt_mct = alt_db_table();
      $alt_mc = array('rows' => array(), 'read_date' => '', 'stale_missing' => array(), 'sum' => null);
      $alt_mc_due_days = 40; // must equal DUE_AFTER_DAYS in railway/monthly_us_comparison.py
      $alt_mc_path = ALT_PLUGIN_DIR . 'data/survey-monthly.json';
      $alt_mc_j = is_readable($alt_mc_path) ? json_decode((string) file_get_contents($alt_mc_path), true) : null;
      if (is_array($alt_mc_j) && !empty($alt_mc_j['total']) && is_array($alt_mc_j['total'])) {
          $alt_mc['read_date'] = (string) ($alt_mc_j['read_date'] ?? '');
          $alt_mc_sum = array('eff' => 0, 'notice' => 0, 'survey' => 0);
          $alt_mc_months = array_keys($alt_mc_j['total']); sort($alt_mc_months);
          foreach ($alt_mc_months as $alt_mm) {
              if (!preg_match('/^\d{4}-\d{2}$/', $alt_mm)) continue;
              $alt_mfrom = $alt_mm . '-01';
              $alt_mto = gmdate('Y-m-t', strtotime($alt_mfrom));
              // Both tiers together and strict US job location, mirroring the
              // aggregate the API serves for the same window, so every cell is
              // reproducible from the public endpoint.
              $alt_mc_eff = (int) $wpdb->get_var($wpdb->prepare(
                  "SELECT COALESCE(SUM(job_count),0) FROM $alt_mct
                   WHERE superset_of=0 AND country='United States' AND layoff_date BETWEEN %s AND %s",
                  $alt_mfrom, $alt_mto));
              $alt_mc_not = (int) $wpdb->get_var($wpdb->prepare(
                  "SELECT COALESCE(SUM(job_count),0) FROM $alt_mct
                   WHERE superset_of=0 AND country='United States'
                     AND COALESCE(announcement_date, layoff_date) BETWEEN %s AND %s",
                  $alt_mfrom, $alt_mto));
              $alt_mc_sv = $alt_mc_j['total'][$alt_mm];
              $alt_mc_sv = is_numeric($alt_mc_sv) ? (int) $alt_mc_sv : null;
              $alt_mc_due = (time() - strtotime($alt_mto . ' 23:59:59 UTC')) > $alt_mc_due_days * DAY_IN_SECONDS;
              if ($alt_mc_sv !== null) {
                  $alt_mc_sum['eff'] += $alt_mc_eff; $alt_mc_sum['notice'] += $alt_mc_not; $alt_mc_sum['survey'] += $alt_mc_sv;
              } elseif ($alt_mc_due) {
                  $alt_mc['stale_missing'][] = gmdate('F Y', strtotime($alt_mfrom));
              }
              $alt_mc['rows'][] = array(
                  'label' => gmdate('F Y', strtotime($alt_mfrom)),
                  'eff' => $alt_mc_eff, 'notice' => $alt_mc_not,
                  'survey' => $alt_mc_sv, 'due' => $alt_mc_due,
              );
          }
          if ($alt_mc_sum['survey'] > 0) $alt_mc['sum'] = $alt_mc_sum;
      }
      set_transient(alt_figure_cache_key('press_monthly_compare'), $alt_mc, HOUR_IN_SECONDS);
  }
  $alt_mc_pct = function ($ours, $survey) {
      return $survey ? round(100 * $ours / $survey) . '%' : 'n/a';
  };
  ?>
  <?php if (!empty($alt_mc['rows'])) : ?>
  <h2 id="alt-press-vs-survey">Month by month against the national announcement survey</h2>
  <p>Two lenses on the same months, side by side. Our columns count jobs located in the US, verified and announced tiers together, recomputed live from the database. The survey column is the published national monthly total of announced cuts.</p>
  <p><b>Effective basis</b> dates each cut on the day it takes effect. <b>Notice basis</b> dates it on the day its notice or announcement entered the record. The survey books each announcement in the month it was made.</p>
  <div class="alt-health-table-wrap">
  <table class="alt-basis-table alt-press-table">
    <thead><tr><th>Month</th><th class="num">Ours, effective basis</th><th class="num">Ours, notice basis</th><th class="num">National survey, announcement basis</th><th class="num">Effective vs survey</th><th class="num">Notice vs survey</th></tr></thead>
    <tbody>
    <?php foreach ($alt_mc['rows'] as $alt_mr) : ?>
      <tr>
        <th><?php echo esc_html($alt_mr['label']); ?></th>
        <td class="num"><?php echo number_format($alt_mr['eff']); ?></td>
        <td class="num"><?php echo number_format($alt_mr['notice']); ?></td>
        <?php if ($alt_mr['survey'] !== null) : ?>
        <td class="num"><?php echo number_format($alt_mr['survey']); ?></td>
        <td class="num"><?php echo esc_html($alt_mc_pct($alt_mr['eff'], $alt_mr['survey'])); ?></td>
        <td class="num"><?php echo esc_html($alt_mc_pct($alt_mr['notice'], $alt_mr['survey'])); ?></td>
        <?php else : ?>
        <td class="num alt-muted"><?php echo $alt_mr['due'] ? 'awaiting entry here' : 'not published yet'; ?></td>
        <td class="num alt-muted">n/a</td>
        <td class="num alt-muted">n/a</td>
        <?php endif; ?>
      </tr>
    <?php endforeach; ?>
    <?php if (!empty($alt_mc['sum'])) : ?>
      <tr>
        <th>Published months, added</th>
        <td class="num"><b><?php echo number_format($alt_mc['sum']['eff']); ?></b></td>
        <td class="num"><b><?php echo number_format($alt_mc['sum']['notice']); ?></b></td>
        <td class="num"><b><?php echo number_format($alt_mc['sum']['survey']); ?></b></td>
        <td class="num"><b><?php echo esc_html($alt_mc_pct($alt_mc['sum']['eff'], $alt_mc['sum']['survey'])); ?></b></td>
        <td class="num"><b><?php echo esc_html($alt_mc_pct($alt_mc['sum']['notice'], $alt_mc['sum']['survey'])); ?></b></td>
      </tr>
    <?php endif; ?>
    </tbody>
  </table>
  </div>
  <p>The two columns of percentages are a comparison of lenses, not a score. The survey also counts federal reductions, voluntary buyout offers, employer estimates never filed anywhere, and unnamed small announcements. We count only cuts with a filing or a named public report behind them.</p>
  <p>A month above 100 percent is not an error. The two lenses date and admit cuts differently, so a notice filed in one month for a cut landing in another sits in different rows under each. The difference is the lens, not a shortfall in either count.</p>
  <?php if (!empty($alt_mc['stale_missing'])) : ?>
  <p class="alt-sb-disclaimer"><b>Awaiting an update:</b> the survey figure for <?php echo esc_html(implode(', ', $alt_mc['stale_missing'])); ?> is due and not yet entered here. Treat the added row as provisional until it is.</p>
  <?php endif; ?>
  <p class="alt-muted">Our columns read live from the same database as every other figure on this page, so this table re-derives itself as records arrive. The survey column is hand entered from the survey's published releases, read <?php echo esc_html($alt_mc['read_date']); ?>, and a released month missing here is flagged automatically rather than left to age. Reproduce our cells from the public API with <code>aggregate?country=United%20States&amp;from=&lt;month-start&gt;&amp;to=&lt;month-end&gt;</code>, adding <code>date_basis=notice</code> for the notice column.</p>
  <?php endif; ?>

  <h2 id="alt-press-statements">Numbers you can use right now</h2>
  <p>This week, the latest complete month, and the year to date. Each card is ready to paste into a pitch or a story. Each one ends with a link that opens the live tracker, filtered to the exact rows behind the number. An editor can check the claim in one click.</p>
  <p class="alt-muted"><b>Generated <?php echo esc_html($alt_ps['generated']); ?>.</b> Figures refresh hourly; the wording stays stable. When a period rolls over, it moves to the archive below, so a number you already quoted stays reachable. <?php echo esc_html($alt_press_flagship_note); ?></p>

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
            <td><?php if ($alt_a['ai'] > 0 && !empty($alt_a['ai_link'])) : ?><a href="<?php echo $alt_a['ai_link']; ?>" target="_blank" rel="noopener" title="Open this period filtered to cuts the employer attributed to AI"><?php echo number_format($alt_a['ai']); ?> &rarr;</a><?php else : ?><?php echo number_format($alt_a['ai']); ?><?php endif; ?></td>
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
  <p class="alt-sb-disclaimer"><b>Two AI measures, always labeled.</b> <b>Verified</b> means the employer named AI in its own words, quote on file. The <b>broad measure</b> adds looser AI-linked cases, such as an AI pivot underway or press AI-framing. It is never smaller than the verified measure.<?php if ((int) $alt_ps['tiers']['t3'] === 0) : ?> Right now the two are equal at the verified stage: every AI-linked case on record for <?php echo (int) $alt_ps['tiers']['year']; ?> sits in the announced stage. That is why the paired percentages below match.<?php endif; ?> The two are never merged. Pick the standard your story needs. <b>Two stages, always labeled too.</b> The verified figure leads every soundbite. <?php echo esc_html(function_exists('alt_announced_tier_sentence') ? alt_announced_tier_sentence() : ''); ?> A figure that says including announced adds that tier.</p>
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
  <p class="alt-muted">Figures are current live values and change as new sources are verified. Every number is reproducible from the public API. <?php echo esc_html($alt_press_flagship_note); ?></p>
  <?php endif; ?>

  <h2 id="alt-evidence-ladder">What counts as an AI layoff</h2>
  <p>The hardest question about any AI layoff number is what counts as AI. We never publish one blended figure. Every entry records how directly the employer tied the cut to AI. So you can pick the standard your story needs, and see exactly what falls in or out at each step.</p>
  <div class="alt-health-table-wrap"><table class="alt-sources-table">
    <thead><tr><th>Tier</th><th>What has to be true</th><th>Where it appears on the tracker</th><th><?php echo (int) $alt_ps['tiers']['year']; ?> jobs<br><small>verified tier</small></th><th>Preset view</th></tr></thead>
    <tbody>
      <tr>
        <td><b>Tier 1</b><br><small>AI named as the cause</small></td>
        <td>The employer states AI or automation is <b>the</b> reason for the cut, with the exact quote on file.</td>
        <td rowspan="2" class="alt-tier-map">Together these are the <b>&#34;AI cuts, verified (specific)&#34;</b> box on the tracker, and the AI figure we headline. Each also has an announced-stage counterpart in <b>&#34;AI cuts, announced&#34;</b>.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t1']); ?></b></td>
        <td rowspan="2"><a href="<?php echo esc_url(add_query_arg(array('years' => $alt_ps['tiers']['year'], 'ai' => '1', 'date_basis' => 'effective'), home_url('/ai-layoff-tracker/'))); ?>" target="_blank" rel="noopener">Tiers 1 + 2 &rarr;</a><br><small class="alt-muted">One view: the employer's own words. The per-tier split is in the table.</small></td>
      </tr>
      <tr>
        <td><b>Tier 2</b><br><small>AI named among the causes</small></td>
        <td>The employer names AI as <b>a</b> contributing cause alongside others, again with the quote on file.</td>
        <td><b><?php echo number_format($alt_ps['tiers']['t2']); ?></b></td>
      </tr>
      <tr>
        <td><b>Tier 3</b><br><small>AI-linked, no direct statement</small></td>
        <td>No employer statement. An AI pivot is underway, or the press framed the cut that way. Reported separately and <b>never</b> merged into the tiers above.</td>
        <td>This tier is what the <b>&#34;AI-linked, broad&#34;</b> box adds on top of the specific figure, and the only reason that box can be larger.<?php if ((int) $alt_ps['tiers']['t3'] === 0) : ?> For <?php echo (int) $alt_ps['tiers']['year']; ?> it is empty at the verified stage, so the two boxes match here. Every AI-linked case on record sits in the announced stage instead.<?php endif; ?></td>
        <td><b><?php echo number_format($alt_ps['tiers']['t3']); ?></b></td>
        <td><a href="<?php echo esc_url(add_query_arg(array('years' => $alt_ps['tiers']['year'], 'ai_broad' => '1', 'date_basis' => 'effective'), home_url('/ai-layoff-tracker/'))); ?>" target="_blank" rel="noopener">Tiers 1 + 2 + 3 &rarr;</a></td>
      </tr>
    </tbody>
  </table></div>
  <p><b>These are not a second set of numbers.</b> The tiers are the same rows you already see on the tracker, sorted by how directly the employer tied the cut to AI. Verified and announced sort those same rows a second way: by whether the cut has happened yet. <?php
    // 'box' arrived with 2.20.132 and the statement cache is keyed on
    // ALT_VERSION, so it is always present in practice. Guarded anyway: a
    // missing key must never let the page claim an equality it has not
    // measured, which is the defect being fixed three lines down.
    $alt_t12 = (int) $alt_ps['tiers']['t1'] + (int) $alt_ps['tiers']['t2'];
    $alt_box = (int) ($alt_ps['tiers']['box'] ?? 0);
    $alt_resid = $alt_box - $alt_t12;
    ?>
    <?php if ($alt_box > 0 && $alt_resid > 0) : ?>Tier 1 and Tier 2 add to <?php echo number_format($alt_t12); ?> of the tracker's verified AI box of <?php echo number_format($alt_box); ?>. The <?php echo number_format($alt_resid); ?>-job difference is rows where the employer named AI as context rather than as a stated cause. Those rows count in the box and in no tier here.<?php elseif ($alt_box > 0 && $alt_resid === 0) : ?>Tier 1 and Tier 2 add to <?php echo number_format($alt_t12); ?>, which is the tracker's verified AI box exactly.<?php else : ?>The tier columns count the stored cause on each row. The tracker's verified AI box counts every row where the employer named AI, so it is the wider of the two.<?php endif; ?> Tier 3 is reported on its own and is never folded into either figure above. Nothing is double counted and nothing is invented for this table.</p>
  <p class="alt-muted">Counts are <b>verified-tier</b> jobs (announced-stage plans excluded) for rows where the employer's stated reason is on record. The tier columns count the stored cause on each row; the tracker's AI box counts every row where the employer named AI, which is the wider of the two. Our headline AI figure is <b>Tiers 1 and 2 only</b>: the employer's own words. Investment in AI, a future automation projection, or AI used to pick who goes does not qualify by itself. If you want the wider lens, cite Tier 3 explicitly and say so.</p>

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
  <p>Live figures from the same database the tracker serves, cut at today, so the current year is a part year. <b>These columns count the verified and announced tiers together</b>, which is why the current-year row runs above the verified headline at the top of this page. "AI-attributed" uses our strict standard: the company named AI as a primary or contributing cause, with a supporting quote on file. A separate broader measure is available in the <code>ai_broad_jobs</code> API field.</p>
  <?php $alt_lu = function_exists('alt_data_last_updated_label') ? alt_data_last_updated_label() : ''; ?>
  <?php /* This page carries two freshness stamps a few hours apart, in two
       time zones, and until now neither said which one a citing journalist
       should use. They are different facts and both are needed, so the fix is
       to name them rather than to drop one: "Generated" is when this page's
       wording and figures were assembled (UTC, at the top of the page), and
       "Data last updated" is when the database behind them last changed, which
       is reported in the site's local zone because that is the zone the
       collectors are scheduled in. The accessed-date sentence says which one
       goes in a citation. */ ?>
  <?php if ($alt_lu) : ?><p class="alt-muted"><b>Data last updated:</b> <?php echo esc_html($alt_lu); ?>, the moment the underlying database last changed (a new filing/notice/report was added), not the time you loaded this page. <?php if (!empty($alt_ps['generated'])) : ?>That is a different stamp from <b>Generated <?php echo esc_html($alt_ps['generated']); ?></b> higher up the page, which is when these figures were assembled. <?php endif; ?> In a citation, use the date you accessed the tracker.</p><?php endif; ?>
  <div class="alt-health-table-wrap"><table class="alt-press-table">
    <thead><tr><th>Year</th><th class="num">Layoff entries recorded</th><th class="num">Job cuts recorded<br><small>verified and announced</small></th><th class="num">AI-attributed (strict)</th></tr></thead>
    <tbody>
    <?php foreach ($alt_press_years as $alt_yr) : ?>
      <tr><td><b><?php echo (int) $alt_yr['y']; ?></b></td><td class="num"><?php echo number_format((int) $alt_yr['entries']); ?></td><td class="num"><?php echo number_format((int) $alt_yr['jobs']); ?></td><td class="num"><?php echo number_format((int) $alt_yr['ai_jobs']); ?></td></tr>
    <?php endforeach; ?>
    </tbody>
  </table></div>
  <p>Coverage depth varies by year: 2015 to 2023 is primarily official US WARN filings; from 2024 on, worldwide news, SEC filings and European Restructuring Monitor coverage deepen. Methodology and per-country sources are documented on the tracker itself.</p>

  <h2 id="alt-cite">How to cite us</h2>
  <p>The data is free for editorial, research, and educational use under <b>CC BY 4.0</b>. Attribute to asktherecruiter.com and link back where possible.</p>
  <p><b>The accurate phrasing:</b> <em>"According to AskTheRecruiter's AI Layoff Tracker, N job cuts are documented for [period]."</em> Our totals are a verifiable floor, not a census. They cover what we can trace to a filing or a named report under a published methodology. Saying "there were exactly N layoffs" overstates what any tracker can know. Saying "documented counts" is precise, defensible, and survives fact-checking. Every number on this page links to the rows behind it, and the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>#m-audit">tracker audits its own published rows monthly</a> against their sources.</p>
  <p><b>Suggested attribution:</b> "According to the AI Layoff Tracker by AskTheRecruiter.com..."</p>
  <p><b>One-line description:</b> "The AI Layoff Tracker by AskTheRecruiter.com, a source-linked database of layoffs worldwide, flagging the ones companies blame on AI."</p>
  <ul>
    <li><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">Methodology</a>: how every number is built, counted, and corrected.</li>
    <li><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>"><?php echo esc_html(alt_page_link_label('page-ai-quotes.php', 'AI layoffs, in the employer\'s own words')); ?></a>: every employer AI attribution, verbatim, with its source.</li>
    <li><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a>: the full list of collectors and what each one covers.</li>
  </ul>
  <h3 id="alt-dataset">Get the full dataset</h3>
  <p>Filtered or full CSV and JSON exports are on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">tracker page</a>. The public REST API serves the same data live: <code>GET /blog/wp-json/layoffs/v1/query</code> and <code>GET /blog/wp-json/layoffs/v1/aggregate</code>. Company pages with stable, linkable URLs live under <code>/company-layoffs/</code>, so a reporter can cite one company's full source-linked history at a permanent address.</p>

  <h2 id="alt-boilerplate">About the tracker</h2>
  <p><b>Boilerplate:</b> AskTheRecruiter is the open, evidence-based intelligence platform helping workers understand the changing job market and improve their chances of getting hired. Its <b>AI Layoff Tracker</b> is a continuously updated, source-linked database of verified job cuts worldwide, purpose-built to flag which layoffs companies themselves attribute to AI or automation, every figure clickable back to a primary document.</p>
  <p>Live editorial tracking began in January 2026. The database also carries historical records back to 2002 in Europe and 2015 in the US. Those older rows come from official WARN filings, SEC disclosures and the EU's restructuring monitor, so year-over-year comparisons are possible.</p>

  <h3 id="alt-why-cite">Why it's worth citing</h3>
  <div class="alt-health-table-wrap"><table class="alt-sources-table alt-angles-table">
    <thead><tr><th>The angle</th><th>Why it's a story</th></tr></thead>
    <tbody>
      <tr><td><b>We break out the AI cuts</b></td><td>Most layoff trackers give you one lump-sum number and stop. We flag the cuts a company itself pinned on AI or automation, each with the employer's own quote on file. That turns "AI-attributed" into a figure a reporter can source instead of guess at.</td></tr>
      <tr><td><b>Every number is a receipt</b></td><td>Estimate-based trackers hand you a figure. We hand you the document behind it: an SEC filing, a WARN notice, or a named report. It's a floor you can prove, not a projection.</td></tr>
      <tr><td><b>We count each cut once, on the day it happens</b></td><td>Every layoff is dated by when it takes effect, not when its notice was filed, and de-duplicated so one layoff is never summed twice. That is why we land within about 10 percent of independent WARN trackers. A tracker reporting several times higher is usually adding a company-wide headcount onto every state filing, which counts the same people over and over.</td></tr>
      <tr><td><b>We show where AI is cutting</b></td><td>A live world map, the teams hit hardest, and AI's rising share month over month: the geographic and functional detail a press release can't give a reporter.</td></tr>
      <tr><td><b>We audit our own completeness</b></td><td>We keep a standing checklist of 51 of the most significant layoffs major outlets have covered and re-check our database against it every week. We currently carry every one of them. Any gap is a finding we chase and backfill, not a number we quietly round up to.</td></tr>
      <tr><td><b>Nothing is hidden</b></td><td>A public corrections log, open methodology, the full source list, and an API anyone can reproduce. When we catch an error, we publish it.</td></tr>
    </tbody>
  </table></div>

  <h3>Editorial independence</h3>
  <p>The tracker is a data product of AskTheRecruiter.com. Fixed, published rules produce its numbers. Counts come only from linked primary documents, AI labels require the employer's own words, and we adjust no figure for any commercial purpose. The full methodology, the per-country source list, the public corrections log and the collection code are open for inspection. Anyone can reproduce the dataset from the public API.</p>

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
    <p>One email a month, sent when the numbers close. It carries the documented job-cut total, the AI figure in the employer's own words, the biggest cuts, and the preset links to check every claim. Built for reporters on deadline. No spam, unsubscribe any time.</p>
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
