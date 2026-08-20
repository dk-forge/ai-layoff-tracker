<?php
/** Main filterable tracker, rendered by [alt_tracker]. */
if (!defined('ABSPATH')) exit;

$alt_csv  = admin_url('admin-post.php?action=alt_export_csv');
$alt_json = admin_url('admin-post.php?action=alt_export_json');
$alt_api  = rest_url('layoffs/v1/query');
$alt_dl   = '<svg class="alt-dl-ico" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg>';

// NOTE: no Dataset block here — alt_seo_head() (wp_head, main plugin file)
// already emits the single, richer Dataset JSON-LD (incl. measurementTechnique
// + publisher merged from the block that used to live here). Two Dataset
// objects on one page made answer engines pick one at random (audit 2026-07-25).
?>
<?php
// Zero-round-trip first paint: inline the same three default-filter payloads
// (facets + aggregate + first query page) the front-end would otherwise fetch,
// computed by the REST endpoints' own callbacks (alt_tracker_bootstrap_payload,
// includes/db.php). Skipped for deep-linked filtered views — those must fetch
// live — and layoffs.js ALSO verifies each param set matches what it was about
// to request before using a piece, so a mismatch just falls back to fetching.
// JSON_HEX_TAG escapes < and >, so "</script>" can never appear in the blob.
// The guard must only trip AFTER a real emit. WordPress evaluates the_content
// more than once per request (SEO/meta-description and excerpt passes run it
// with output discarded, and some run during wp_head); a persistent flag set
// BEFORE emitting let one of those discarded passes claim the single emit and
// the visible body render then skipped. So: never run during the wp_head pass,
// and set the once-flag only once a payload is actually echoed.
// Emit unconditionally when the payload succeeds and no filter rides the URL.
// This theme renders the post content during wp_head (for SEO/JSON-LD) and that
// pass's output is what reaches the body, so any guard that suppressed the
// head-time pass (or a persistent once-flag set by an earlier discarded pass)
// killed the only emit that mattered. A duplicate emit, if the template ever
// renders twice into visible output, is harmless: layoffs.js reads the global
// once and the payloads are identical.
$alt_boot = null;
if (function_exists('alt_tracker_bootstrap_payload')) {
    $alt_boot_url_filters = array('years', 'quarters', 'months', 'industry', 'country', 'state',
        'sources', 'reasons', 'roles', 'from', 'to', 'q', 'company', 'keyword', 'min_jobs',
        'ai', 'ai_broad', 'stage', 'date_basis');
    $alt_boot = array_intersect($alt_boot_url_filters, array_keys($_GET))
        ? null : alt_tracker_bootstrap_payload();
    if ($alt_boot) {
        echo '<script>window.ALT_BOOTSTRAP = '
            . wp_json_encode($alt_boot, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT)
            . ';</script>' . "\n";
    }
}

// Server-rendered headline numbers, from the SAME cached bootstrap aggregate
// the front-end paints from (alt_api_cached path, zero additional queries).
// The whole pitch of this page is citability, and until 2.19.250 the stat
// tiles shipped as "…" until JS ran — crawlers and copy-pasting journalists
// got dots where the money quote should be. The arithmetic below mirrors
// renderStats() in layoffs.js exactly (verified = jobs - announced, strict AI
// total = verified AI + announced AI), and layoffs.js re-renders the same
// numbers on load, so the two can never disagree on a default view. A
// deep-linked filtered view has no bootstrap by design; it keeps the
// placeholder and JS fills it from the live, filtered aggregate.
$alt_sv = null;
$alt_t = ($alt_boot && isset($alt_boot['aggregate']['totals']) && is_array($alt_boot['aggregate']['totals']))
    ? $alt_boot['aggregate']['totals'] : null;
if ($alt_t) {
    $alt_jobs = (int) ($alt_t['jobs'] ?? 0);
    $alt_annj = (int) ($alt_t['announced_jobs'] ?? 0);
    $alt_aiv  = isset($alt_t['ai_verified_jobs']) ? (int) $alt_t['ai_verified_jobs'] : (int) ($alt_t['ai_jobs'] ?? 0);
    $alt_aia  = isset($alt_t['ai_announced_jobs']) ? (int) $alt_t['ai_announced_jobs']
        : max(0, (int) ($alt_t['ai_jobs'] ?? 0) - $alt_aiv);
    $alt_sv = array(
        'total'        => max(0, $alt_jobs - $alt_annj),
        'announced'    => $alt_annj,
        'all'          => $alt_jobs,
        'ai'           => $alt_aiv,
        'ai-announced' => $alt_aia,
        'ai-total'     => $alt_aiv + $alt_aia,
        'ai-broad'     => (int) ($alt_t['ai_broad_jobs'] ?? 0),
        // The same window, cut at today (see the to_date_* note in db.php).
        // 'total' counts the whole filtered window, which for a calendar-year
        // filter includes notices already filed for effective dates later in
        // the year; 'to-date' is the one a "so far" sentence may quote.
        'to-date'      => max(0, (int) ($alt_t['to_date_jobs'] ?? 0) - (int) ($alt_t['to_date_announced_jobs'] ?? 0)),
        'later'        => max(0, (int) ($alt_t['jobs'] ?? 0) - (int) ($alt_t['announced_jobs'] ?? 0)
                                 - ((int) ($alt_t['to_date_jobs'] ?? 0) - (int) ($alt_t['to_date_announced_jobs'] ?? 0))),
        'companies'    => (int) ($alt_t['companies'] ?? 0),
        'industries'   => (int) ($alt_t['industries'] ?? 0),
        'countries'    => (int) ($alt_t['countries'] ?? 0),
        'states'       => (int) ($alt_t['states'] ?? 0),
    );
}
$alt_stat = function ($k) use ($alt_sv) {
    return $alt_sv === null ? '…' : number_format($alt_sv[$k]);
};
// The bootstrap scope is always the current year (see
// alt_tracker_bootstrap_payload), so the period stamps are knowable here too.
/*
  THE PERIOD STAMP SAYS WHAT THE WINDOW IS, not what we wish it were.

  This stamp read "<year> YTD" over a figure scoped to the whole calendar
  year. Rows are dated by EFFECTIVE date and WARN notices are filed with
  effective dates weeks ahead by law, so on 2026-08-04 that figure was
  33,939 ahead of "to date" while the FAQPage JSON-LD on the same page
  published the to-date number. One document, two totals, one wording.
  The stamp now names the calendar year, and the reconciling line below the
  hero prints the to-date figure and the remainder, which sum to it.
*/
$alt_period     = $alt_sv === null ? '' : current_time('Y');
$alt_period_ann = $alt_sv === null ? '' : current_time('Y') . ' · includes future-dated plans';
// The hero's own stamp spells the window out rather than printing a bare year,
// and names the geography, because the hero is the figure that gets compared
// against an outside estimate. The tile stamps above stay compact: they sit in a
// grid where the hero has already established both.
$alt_hero_period = $alt_sv === null ? '' : 'calendar year ' . current_time('Y');
$alt_hero_geo    = 'worldwide';
/*
  THE DEFAULT BASIS, IN ONE PLACE ON THE SERVER.

  It is the FILING basis, matching the DATE_BASIS default in layoffs.js and the
  date_basis the bootstrap payload is computed on. These three have to agree or
  the first paint publishes a figure counted one way under a label naming the
  other, which is the exact defect this change removes rather than one to
  introduce. The wording is byte-identical to BASIS_COPY.notice.headline in
  layoffs.js and pinned by railway/tests/test_date_basis_default.py.
*/
$alt_hero_basis  = 'counted by filing date';
?>
<div class="alt-wrap alt-tracker-wrap alt-dashboard">

    <?php
    // Next collection time, derived from the real cron (alt_next_ingest_utc
    // reads data/ingest-schedule.json, generated from railway/railway.toml —
    // never typed). Shown in the freshness panel; layoffs.js refreshes it to
    // a live Eastern-time reading via #alt-next-top.
    $alt_next_ts = function_exists('alt_next_ingest_utc') ? alt_next_ingest_utc() : null;
    ?>
    <?php
    /*
      EDITORIAL HERO, and the ONE question the first screen answers.

      2026-08-04, the owner reading the live page: "still very messy, lots of
      text, lots of confusion on what to do first and how to start." Above the
      first row of data the page carried three headline paragraphs, a status
      panel, a coverage ribbon, an export row, a 4x4 board with a four-clause
      footnote, four more link groups, ten region chips, fifteen dropdowns and
      five tiles each with its own paragraph. It answered every question a
      reader might have at once, so it answered none of them first.

      The hero now holds exactly four things: the figure, what it counts, one
      trust line stated as a benefit, and the two routes out. Everything the
      hero used to carry is still on the page, further down, in the
      alt-datastrip section (freshness, coverage ribbon, cite/export row, the
      report and press links). Nothing was deleted except the duplicated trust
      claims and the "New here? Start with:" block, whose existence was the
      bug: a page that needs a start-here list has failed to be self-evident.
    */
    ?>
    <header class="alt-hero">
        <div class="alt-hero-main">
            <?php /* THE FIGURE THE PAGE EXISTS TO PUBLISH, at the top of the first
                     screen and larger than anything else on it.
                     Before 2.19.263 the page's own NAME was the biggest thing on
                     it at 46px, the thesis was 31px, and the number itself was
                     20px in the right-hand panel below an illustration, tied for
                     smallest with "countries". Eight tiles then followed at an
                     identical 28px, so nothing among them led either. A reader
                     arriving from a search result met the title of the page
                     before the finding of the page.
                     Kept in step live by renderStats() (alt-hero-total), from the
                     same totals the Verified tile uses, so the two can never
                     disagree. */ ?>
            <?php if ($alt_sv !== null) : ?>
            <p class="alt-hero-figure">
                <span class="alt-hero-figure-value" id="alt-hero-total"><?php echo esc_html($alt_stat('total')); ?></span>
                <?php /* THE LABEL STATES UNIT, GEOGRAPHY AND PERIOD, in that order,
                         because the first thing a reader does with this figure is
                         compare it against a national estimate they arrived with.
                         It read "verified job cuts, 2026" and named neither where
                         nor over what window. A correct number whose basis is
                         unstated is read as a contradiction of whatever it is being
                         compared to, at the same cost as a wrong one.
                         NOT "2026 YTD". The window is dated by EFFECTIVE date, so it
                         legitimately holds notices already filed for dates still
                         ahead; "calendar year" says that and "YTD" would deny it.
                         The as-of line directly below splits the two.
                         Both spans are kept in step live by renderStats(), which
                         swaps in the active filter's geography and period. */ ?>
                <?php /* THE BASIS IS PART OF THE LABEL, not a footnote. The
                         default basis changed to the filing date so that this
                         figure can be reconciled against the independent
                         national estimate a reader arrives with, and a figure
                         that does not say which of the two questions it answers
                         invites exactly the "why is yours wrong" the change was
                         made to end. Written by renderBasisCopy() in layoffs.js
                         from the one BASIS_COPY table, so the word here and the
                         number above it cannot drift. */ ?>
                <span class="alt-hero-figure-label">verified job cuts <span id="alt-hero-total-geo"><?php echo esc_html($alt_hero_geo); ?></span>, <span id="alt-hero-total-period"><?php echo esc_html($alt_hero_period); ?></span>, <span id="alt-hero-total-basis"><?php echo esc_html($alt_hero_basis); ?></span></span>
                <?php /* THE AI LINE, written to the rubric it reports and no wider.
                         It read "blamed on AI by the employer". "Blamed" is a verdict,
                         and this tracker does not return one: the record is that the
                         EMPLOYER named AI, in words we hold and can quote. The
                         methodology page words it the same way ("employer names
                         AI/automation, quote on file"), so the two surfaces now agree
                         and neither asserts causation on the employer's behalf. */ ?>
                <span class="alt-hero-figure-sub"><b id="alt-hero-ai"><?php echo esc_html($alt_stat('ai')); ?></b> of those are cuts where the employer named AI as a reason.</span>
                <?php /* THE SECOND TIER, STATED WHERE THE TOTAL IS (owner
                         decision 2026-08-14). The verified figure above stays
                         primary; this companion states the announced-inclusive
                         total beside it so a reader comparing us against an
                         announcement estimate meets both tiers on the first
                         screen instead of discovering the announced tile
                         later. Same stage split the tiles below carry, same
                         basis as the headline, and the sentence is
                         alt_announced_tier_sentence(), rendered verbatim here,
                         on the press page and on the report page. Kept in step
                         live by renderStats(), which also hides the wrapper
                         when the view holds no announced rows, because the
                         same number twice under two labels is noise. */ ?>
                <span class="alt-hero-figure-incl" id="alt-hero-incl-wrap"<?php echo ($alt_sv !== null && $alt_sv['announced'] > 0) ? '' : ' hidden'; ?>><b id="alt-hero-incl"><?php echo esc_html($alt_stat('all')); ?></b> including announced cuts. <?php echo esc_html(function_exists('alt_announced_tier_sentence') ? alt_announced_tier_sentence() : ''); ?></span>
            </p>
            <?php endif; ?>
            <?php /* ONE trust line, and it is the benefit, not the refusal. It read
                     "Every layoff here is verified. That is the whole point." followed
                     by "We do not estimate...". The first argues with somebody the
                     reader has never met; the second leads with what we refuse to do.
                     Both state one fact, so the page states it once, as what the
                     reader gets. The two duplicate claims that stood beside it (the
                     hero trust paragraph and the freshness panel's "No figure appears
                     unless its source states it") are gone, not moved. */ ?>
            <p class="alt-hero-thesis" role="heading" aria-level="2">Every entry links to the filing, notice or report it came from.</p>
            <?php /* THE THIRD ROUTE, AND THE ONE THE PRIMARY READER NEEDS.
                     Journalists are this product's audience and the press kit
                     is the page written for them, yet until 2.20.32 the only
                     route to it was a text link inside .alt-lead-links, which
                     sits in the data strip BELOW the whole page. Measured on
                     the live page, bare URL, 2026-08-13: that link's top edge
                     was 13,252px down at 1280px and 31,707px down at 375px, on
                     a 44,128px document. The owner failed to find it twice in
                     one day, and he knew it existed. Renaming it (2.20.27, from
                     "Press & media" to the destination's own heading) fixed
                     what it SAID without fixing where it was.

                     It is a button here and not a fourth text link because the
                     two things a reader does on this page are already buttons,
                     and a link among links is what the press route already was.

                     THE LABEL IS THE DESTINATION'S OWN H1, "Press kit and
                     soundbites", carried in front of a "For press" tag that
                     answers the owner's actual question ("are you press, click
                     here") without inventing a fifth name for that page. The
                     tag is a label, not a shout: 11px, the brand green, and no
                     exclamation anywhere near it. This page's credibility with
                     the reader it is aimed at costs more than the click.

                     PLACED HERE BECAUSE IT COSTS THE FIRST SCREEN NOTHING IT
                     DOES NOT HAVE TO. It sits BELOW the hero figure, so the
                     figure does not move at any width; at 1280px the three
                     buttons share one flex row and nothing below moves either.
                     At 375px there is 24.4px of slack on that row and no label
                     fits in it, so the button wraps and everything below the
                     hero drops by exactly one 44px target plus the 8px gap.
                     That is the floor, not a choice: 44px is the tap minimum
                     this page already holds. Do not "save" those 52px by
                     shrinking it under 44, and do not save them by moving it
                     back down the page, which is the defect. */ ?>
            <p class="alt-hero-actions">
                <a class="alt-btn alt-btn-primary" id="alt-hero-search" href="#alt-search">Search the record</a>
                <a class="alt-btn" href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">How we count</a>
                <a class="alt-btn alt-btn-press" id="alt-hero-press" href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>"><span class="alt-btn-tag">For press</span> Press kit and soundbites</a>
                <?php /* THE FOURTH ROUTE, AND THE PRESS DEFECT REPEATING ON A
                         SECOND SURFACE. The digest signup has been live,
                         working and reachable only by scrolling to the end of
                         the page. Measured live, bare URL, browser UA, no
                         cache buster, 2026-08-14 at ver=2.20.50:

                             viewport     signup top   document
                             1280 x 900   17,731px     18,849px
                              375 x 812   40,744px     42,483px

                         Nineteen screens and fifty. The press kit at least
                         had a text link aimed at it from the data strip; this
                         had no route of any kind above it.

                         THE LABEL IS THE SIGNUP'S OWN H2, "Email digest",
                         behind a "Weekly or daily" tag that answers the first
                         question anybody asks of a signup, in the same words
                         the form's own radio buttons use. Not "Subscribe to
                         our newsletter": nobody wants a newsletter, and the
                         thing on offer is a digest.

                         IT IS A SAME-PAGE JUMP, SO SHIPPING THE BUTTON IS
                         HALF OF IT. The press page's own jump menu ended
                         847px down an 812px screen and was called fixed. The
                         landing is asserted in
                         test_digest_route_is_findable.py: after the hash is
                         followed, the heading, the email field and the submit
                         button are all on screen at 375 and at 1280. The
                         signup's intro paragraph was shedding that budget to
                         a theme override and now holds its own size, which is
                         where the room came from.

                         COST TO THE FIRST SCREEN, measured rather than
                         claimed: 0px at 1280 (the four buttons still share
                         one flex row, ending at x=907 of 1110) and 52.0px at
                         375 and at 414, which is one 44px target plus the 8px
                         gap. That is the floor, not a choice: 44px is the tap
                         minimum this page already holds, and it is the same
                         52px the press button pays. Do not "save" it by
                         shrinking the button under 44, and do not save it by
                         moving the route back down the page, which is the
                         defect. It sits BELOW the hero figure, so the
                         number this page exists to publish does not move at
                         any width. */ ?>
                <a class="alt-btn alt-btn-digest" id="alt-hero-digest" href="#alt-digest"><span class="alt-btn-tag">Weekly or daily</span> Email digest</a>
            </p>
            <?php /* THE RECONCILING LINE, DEMOTED BUT NOT HIDDEN. to-date + later =
                     the hero figure, so a reader can add up what is on screen, and
                     the press page prints the identical sentence for the same year
                     (alt_period_split_sentence owns the wording, and
                     test_headline_total_agreement.py runs both implementations on
                     the same inputs). It used to be the THIRD thing a human read:
                     three numbers and an equation delivered before anyone had a
                     reason to care. It is now a labelled note after the two routes.
                     It is NOT behind a disclosure. This codebase has shipped three
                     separate caveats that computed to display:none or 0x0 and were
                     never read by anyone, and a reconciliation a journalist cannot
                     see does not reconcile anything. Kept in step live by
                     renderStats(), which hides the WRAPPER (label and all) in a
                     past-year view where there is nothing left to split. */ ?>
            <?php /* COMPRESSED, NOT REMOVED, AND STILL VISIBLE PROSE. The full
                     40-word sentence stays on the press page, where somebody is
                     deliberately looking up how to cite a figure. Here it is one
                     line carrying the two parts, the whole and the period, with
                     the fuller explanation a click away in "Why our numbers
                     differ". Under the filing-basis default this line is worth
                     MORE than it was: it is the arithmetic that lets a
                     journalist quote either figure correctly. */ ?>
            <?php $alt_split = ($alt_sv !== null && function_exists('alt_period_split_short'))
                ? alt_period_split_short($alt_sv['to-date'], $alt_sv['total'], $alt_period)
                : ''; ?>
            <p class="alt-hero-figure-asof" id="alt-hero-asof-wrap"<?php echo $alt_split === '' ? ' hidden' : ''; ?>><b class="alt-hero-asof-label">In this figure:</b> <span id="alt-hero-asof"><?php echo esc_html($alt_split); ?></span> <a class="alt-hero-asof-more" href="#alt-basis-explainer">Why two figures</a></p>
        </div>
    </header>
    <?php
    // THE SIGNAL BOARD, server-rendered (the "colored narratives"). Same
    // container and same data plumbing as the strip it evolves: numbers come
    // from window.ALT_BOOTSTRAP's board block (the cached aggregate handler,
    // stage=verified per period), layoffs.js repaints the identical board on
    // load and on every tab switch, and every numeric cell click-filters the
    // page through the existing .alt-nfilter machinery. The hrefs are real
    // filter URLs so the cells also work before (or without) JS, like the
    // tiles.
    $alt_board = ($alt_boot && !empty($alt_boot['board']) && is_array($alt_boot['board'])) ? $alt_boot['board'] : null;
    $alt_board_html = '';
    // Both guarded, for the reason in CLAUDE.md: an FTPS deploy races mid
    // upload, so this template can be live for a few seconds against the
    // PREVIOUS db.php. A missing label helper must cost the server-rendered
    // board (layoffs.js repaints it a moment later), never a fatal.
    $alt_board_periods = (function_exists('alt_signal_board_periods')
                          && function_exists('alt_signal_board_labels'))
        ? alt_signal_board_periods() : array();
    if ($alt_board && count($alt_board) === count($alt_board_periods) && $alt_board_periods) {
        // COMPUTED, NEVER WRITTEN DOWN, and computed from the same windows the
        // cells were counted over. A literal month name in this template is
        // right today and wrong on the first of next month with nothing on the
        // page or in CI able to notice. See alt_signal_board_labels() in db.php
        // for why the completed periods name themselves instead of saying
        // "last month" (the date presets below already use that phrase for a
        // ROLLING window, and one phrase meaning two things on one page is the
        // ambiguity the entries rename removed).
        $alt_cols = alt_signal_board_labels($alt_board_periods);
        // "Today and this month identical" survives as equal-column styling,
        // never as duplicate columns: both cells carry one linking class.
        $alt_tt = $alt_board['today']['totals']; $alt_mt = $alt_board['month']['totals'];
        $alt_tl = $alt_board['today']['leader']; $alt_ml = $alt_board['month']['leader'];
        $alt_sb_eq = ((int) ($alt_tt['jobs'] ?? 0)) > 0
            && (int) ($alt_tt['jobs'] ?? 0) === (int) ($alt_mt['jobs'] ?? -1)
            && (int) ($alt_tt['entries'] ?? 0) === (int) ($alt_mt['entries'] ?? -1)
            && (string) ($alt_tl['company_name'] ?? '') === (string) ($alt_ml['company_name'] ?? '');
        // EVERY CELL LINK NAMES THE BASIS THE CELL WAS COUNTED ON, for the same
        // reason the report page's receipt links do (page-report.php, 2.20.11).
        // The board's period queries now send date_basis=notice, the page's own
        // default, so a cell links into a view that recounts the period exactly
        // the way the cell counted it. The link is a receipt or it is nothing.
        //
        // Read off the board's own params rather than hardcoded. That was
        // written as a fallback when the board named no basis, and it is the
        // reason this survived the basis moving underneath it without a single
        // edit here: a value read is a value that stays true. The params must
        // stay byte-identical to P in layoffs.js (bootParamsMatch/takeBoot) or
        // the inlined board is rejected and repainted with six live fetches.
        //
        // No new bootstrap suppression: date_basis sits in $alt_boot_url_filters
        // above, but so do from/to AND years, so every href here already
        // suppressed the inline payload before this param joined it.
        $alt_sb_meta = array();
        foreach ($alt_cols as $alt_ck => $alt_cl) {
            $alt_bp = $alt_board[$alt_ck]['params'];
            $alt_sb_basis = isset($alt_bp['date_basis']) ? (string) $alt_bp['date_basis'] : 'effective';
            $alt_sb_meta[$alt_ck] = isset($alt_bp['years'])
                ? array('href' => '?years=' . rawurlencode($alt_bp['years']) . '&amp;date_basis=' . rawurlencode($alt_sb_basis),
                        'data' => ' data-years="' . esc_attr($alt_bp['years']) . '" data-date-basis="' . esc_attr($alt_sb_basis) . '"')
                : array('href' => '?from=' . rawurlencode($alt_bp['from']) . '&amp;to=' . rawurlencode($alt_bp['to']) . '&amp;date_basis=' . rawurlencode($alt_sb_basis),
                        'data' => ' data-from="' . esc_attr($alt_bp['from']) . '" data-to="' . esc_attr($alt_bp['to']) . '" data-date-basis="' . esc_attr($alt_sb_basis) . '"');
        }
        $alt_sb_head = '<div class="alt-sb-row alt-sb-headrow" role="row"><span class="alt-sb-label" role="columnheader"><span class="screen-reader-text">Measure</span></span>';
        foreach ($alt_cols as $alt_ck => $alt_cl) {
            $alt_sb_head .= '<span class="alt-sb-col" role="columnheader">' . esc_html($alt_cl) . '</span>';
        }
        $alt_sb_head .= '</div>';
        $alt_sb_numrow = function ($cls, $label, $key) use ($alt_board, $alt_cols, $alt_sb_meta, $alt_sb_eq) {
            $vals = array(); $max = 0;
            foreach ($alt_cols as $ck => $cl) {
                $v = (int) ($alt_board[$ck]['totals'][$key] ?? 0);
                $vals[$ck] = $v; if ($v > $max) $max = $v;
            }
            $h = '<div class="alt-sb-row ' . $cls . '" role="row"><span class="alt-sb-label" role="rowheader">' . $label . '</span>';
            foreach ($alt_cols as $ck => $cl) {
                $v = $vals[$ck];
                $eq = $alt_sb_eq && ($ck === 'today' || $ck === 'month') ? ' alt-sb-eq' : '';
                $eqt = $eq ? ' title="Today and this month are identical so far"' : '';
                $heat = ($v > 0 && $max > 0) ? ' style="background:rgba(var(--alt-heat-rgb),' . number_format(0.08 + 0.26 * $v / $max, 3, '.', '') . ')"' : '';
                $h .= $v > 0
                    ? '<a class="alt-sb-cell alt-nfilter' . $eq . '" role="cell" href="' . $alt_sb_meta[$ck]['href'] . '"' . $alt_sb_meta[$ck]['data'] . $eqt . $heat . '><b>' . esc_html(number_format($v)) . '</b></a>'
                    : '<span class="alt-sb-cell alt-sb-zero' . $eq . '" role="cell"' . $eqt . '>0</span>';
            }
            return $h . '</div>';
        };
        $alt_board_html .= '<div class="alt-sb" role="table" aria-label="Verified layoffs by period">' . $alt_sb_head;
        $alt_board_html .= $alt_sb_numrow('alt-sb-r-workers', 'Workers', 'jobs');
        $alt_board_html .= $alt_sb_numrow('alt-sb-r-events', 'Verified layoffs', 'entries');
        // THE TWO AI ROWS, AND WHY THE SECOND LABEL CARRIES A CLAUSE. The
        // strict measure is the tightest of the four AI figures we hold, and
        // read alone it invites "is that really all?". The broad lens is the
        // honest wider answer and was invisible on this board. Two AI rows
        // adjacent is also exactly where a reader adds them, and CLAUDE.md
        // forbids blending or summing the AI measures, so the second label
        // states the containment on the row itself rather than leaving it
        // entirely to the footnote. Checked live before it was written: on
        // 2026-08-13 an ai=1 slice reports ai_broad_jobs equal to its own jobs
        // (42,253) and an ai_broad=1 slice reports ai_jobs 42,253 inside
        // 53,253, so strict is a genuine subset. The ANNOUNCED tier is
        // deliberately not a third AI row: announced-versus-verified is what
        // the Workers and Verified layoffs rows already carry.
        $alt_board_html .= $alt_sb_numrow('alt-sb-r-ai', 'Explicitly AI-attributed', 'ai_jobs');
        $alt_board_html .= $alt_sb_numrow('alt-sb-r-aibroad', 'AI-linked, broad lens (includes the above)', 'ai_broad_jobs');
        // Largest event: links to the entry's permalink (the citable unit),
        // falling back to the company click-filter when no permalink exists.
        $alt_lmax = 0; $alt_lvals = array();
        foreach ($alt_cols as $alt_ck => $alt_cl) {
            $alt_ld = $alt_board[$alt_ck]['leader'];
            $alt_lvals[$alt_ck] = $alt_ld && !empty($alt_ld['job_count']) ? (int) $alt_ld['job_count'] : 0;
            if ($alt_lvals[$alt_ck] > $alt_lmax) $alt_lmax = $alt_lvals[$alt_ck];
        }
        // THE SAME EVENT CAN LEAD MORE THAN ONE COLUMN, and it usually does:
        // this week sits inside this month, so one big cut leads both. That is
        // arithmetically right and it reads as a bug ("why is Dird Group
        // printed twice?"). The repeat is now MARKED rather than removed: the
        // first column to carry a leader keeps it plain, and every later column
        // showing the same employer says "same event" under the number. Nothing
        // about the underlying values changes.
        $alt_lseen = array();
        $alt_board_html .= '<div class="alt-sb-row alt-sb-r-largest" role="row"><span class="alt-sb-label" role="rowheader">Largest entry</span>';
        foreach ($alt_cols as $alt_ck => $alt_cl) {
            $alt_ld = $alt_board[$alt_ck]['leader'];
            $alt_lv = $alt_lvals[$alt_ck];
            $eq = $alt_sb_eq && ($alt_ck === 'today' || $alt_ck === 'month') ? ' alt-sb-eq' : '';
            $heat = ($alt_lv > 0 && $alt_lmax > 0) ? ' style="background:rgba(var(--alt-heat-rgb),' . number_format(0.08 + 0.26 * $alt_lv / $alt_lmax, 3, '.', '') . ')"' : '';
            if ($alt_lv > 0) {
                $alt_lname = (string) $alt_ld['company_name'];
                $alt_lrep = isset($alt_lseen[$alt_lname]) ? ' alt-sb-ev-repeat' : '';
                $alt_lseen[$alt_lname] = true;
                $alt_lbody = '<b>' . esc_html($alt_lname) . '</b><span>' . esc_html(number_format($alt_lv)) . '</span>'
                    . ($alt_lrep ? '<i class="alt-sb-again">same entry</i>' : '');
                $alt_board_html .= !empty($alt_ld['permalink'])
                    ? '<a class="alt-sb-cell alt-sb-ev' . $eq . $alt_lrep . '" role="cell" href="' . esc_url($alt_ld['permalink']) . '" title="Open this entry&#39;s record page"' . $heat . '>' . $alt_lbody . '</a>'
                    : '<a class="alt-sb-cell alt-sb-ev alt-nfilter' . $eq . $alt_lrep . '" role="cell" href="#" data-company="' . esc_attr($alt_lname) . '" title="Filter the page to this company"' . $heat . '>' . $alt_lbody . '</a>';
            } else {
                $alt_board_html .= '<span class="alt-sb-cell alt-sb-zero' . $eq . '" role="cell">none</span>';
            }
        }
        $alt_board_html .= '</div></div>';
        // THE FOOTNOTE, SPLIT. It was one sentence doing four jobs (what a row
        // counts, where the AI row's words come from, why the columns do not
        // add up, what a tap does), so a reader looking for any one of them
        // read all four. One clause per line now, each sitting with the thing
        // it explains. The "less ▪▪▪ more" heat legend is gone: it rendered as
        // stray words beside the columns and it was never a control.
        $alt_board_html .= '<ul class="alt-sb-foot">'
            // The server render is the DEFAULT view and the board now counts
            // on the page's default basis, so this is the "they agree"
            // wording. layoffs.js swaps it for the "different questions"
            // wording the moment a reader toggles the page to the effective
            // basis, which moves the headline and not the board. See the
            // comment on boardBasisNote() in layoffs.js.
            // The class is how renderBasisCopy() finds this line again: a
            // reader who switches the basis after load gets this one sentence
            // rewritten in place, with no board refetch. See there.
            . '<li class="alt-sb-foot-basis">Every row counts verified entries by filing date, the same basis as the headline figure above.</li>'
            . '<li>Explicitly AI-attributed counts cuts where the employer named AI, in words we hold. The broad lens contains every one of those cuts and adds looser links, so the smaller figure sits inside the larger one and the two are never added together.</li>'
            . '<li>Columns overlap, so they do not add up: this week sits inside this month, and a completed month can sit inside a completed quarter. One entry can lead more than one column.</li>'
            // "and counted the same way" is not decoration: the tap now carries
            // the board's basis into the page, so the filtered view reproduces
            // the number that was tapped instead of recounting it by filing
            // date. The copy says what the link does.
            . '<li>Tap any number to filter the page to that period, counted the same way this board counts it. This board follows the region tabs above; the date and dropdown filters below do not change it.</li>'
            . '</ul>';
        $alt_board_html = '<div class="alt-narrative-head"><span>Verified layoffs worldwide · <b>' . esc_html(date_i18n('M j')) . '</b></span>'
            . '<button type="button" class="alt-btn alt-btn-sm alt-narrative-copy" title="Copy a post-sized version of this summary (fits in one X/Twitter post)">Copy as post</button></div>'
            . $alt_board_html;
    }
    ?>
    <?php
    /*
      REGION CHIPS FIRST, THEN THE BOARD, THEN EVERYTHING ELSE.

      The filter-placement defect, stated exactly: the board is NOT narrowed by
      the date range, the quick views or the fifteen dropdowns (its own footnote
      says so), and all of them used to sit ABOVE it. Controls standing above
      content they do not control teach a reader the page is broken.

      The board IS narrowed by the region tabs — updateNarrative() scopes every
      period query to REGION_TABS[ACTIVE_TAB].countries. So the honest order is
      the one below: the tabs, which do control the board, sit above it; the
      date basis, sort, quick views and dropdown stack, which do not, sit below
      it. Nothing was made to "respond to the filters" that cannot: the four
      columns ARE fixed periods, and a date range over a Today column is not a
      narrower question, it is a different one.

      THE BOARD IS OPEN ON FIRST PAINT, and it used to be collapsed. The
      argument for the collapse was "roughly 300px of the first screen on a
      phone". Measured on the live page rather than estimated, that is not what
      it costs, because the board does not sit on the first screen at all: at
      375x812 its summary starts 999px down, already below the fold, and the
      hero and the headline figure sit above it at 282px and do not move by a
      pixel when it opens. What opening it actually costs is scroll depth to
      the controls below it: the date presets move from 1068 to 1782 and the
      stat tiles from 2798 to 3512 (714px) on a phone, and from 776 to 1154 and
      1354 to 1732 (378px) at 1280x900. Nothing above it moves at either width.

      Shipping it open in the SERVED markup, and not by script, is the same
      rule the filter panel landed on: the no-JS render has to agree with the
      one a reader gets, so the `open` attribute is here rather than in an
      onload handler. A reader who collapses it is remembered for the session
      only (sessionStorage, in initSignalBoard) because a collapse is a "not
      right now" and not a preference, and a deep link that names a region
      forces it open again: the region tabs are the one control that scopes
      this board, so the view that arrived by naming one is never the view we
      hide it from.
    */
    ?>
    <div class="alt-tabs" id="alt-tabs" role="tablist" aria-label="Region">
        <button type="button" class="alt-tab alt-tab-world" data-tab="world">🌐 World</button>
        <button type="button" class="alt-tab alt-tab-usa" data-tab="usa">🇺🇸 USA</button>
        <button type="button" class="alt-tab alt-tab-canada" data-tab="canada">🇨🇦 Canada</button>
        <button type="button" class="alt-tab alt-tab-latam" data-tab="latam">🌎 Latin America</button>
        <button type="button" class="alt-tab alt-tab-europe" data-tab="europe">🇪🇺 Europe</button>
        <button type="button" class="alt-tab alt-tab-uk" data-tab="uk">🇬🇧 UK</button>
        <button type="button" class="alt-tab alt-tab-mideast" data-tab="mideast">🌅 Middle East</button>
        <button type="button" class="alt-tab alt-tab-africa" data-tab="africa">🌍 Africa</button>
        <button type="button" class="alt-tab alt-tab-asia" data-tab="asia">🌏 Asia</button>
        <button type="button" class="alt-tab alt-tab-aus" data-tab="aus">🇦🇺 Australia</button>
    </div>

    <details class="alt-narrative-wrap" id="alt-narrative-wrap" open>
        <summary class="alt-narrative-summary">At a glance: today, this week, this month, the last completed month and quarter, and this year</summary>
        <div class="alt-narrative" id="alt-narrative"><?php echo $alt_board_html; // phpcs:ignore -- built above from escaped parts ?></div>
    </details>
    <?php /* THE DEFINITION LINE, AND IT IS OUTSIDE THE DISCLOSURE ON PURPOSE.

             The board's rows are Workers and Verified layoffs, and the owner
             could not tell from the page which of the two a number was. This
             says it, in the two shortest sentences that carry it, at the
             place a first-time reader meets the number.

             It sits AFTER </details>, not inside it, and that placement is
             deliberately independent of whether the board ships open. A
             CLOSED <details> still has a box and still carries textContent
             for text nobody can read; innerText on a subtree that is not
             rendered falls back to textContent too, so a caveat in there
             would pass every check in this repo and reach no reader. This
             codebase has already shipped three of those. The board's default
             has been both in one week, and this line must not follow it. It
             is also
             literal HTML rather than a string PHP builds, so the fixture in
             test_reader_copy_says_entries.py renders the real line rather
             than a copy of it, and the test reads its innerText off the
             rendered parent.

             "Entry" and not "event": one real-world layoff can produce a WARN
             notice, a news report and a filing, which is what the dedup and
             superset machinery reconciles. `entries` is also what the API
             field has always been called, so the code, the copy and the docs
             now give one name to one thing. */ ?>
    <p class="alt-board-def" id="alt-board-def">An entry is one layoff reported by one employer. Workers counts people.</p>
    <?php
    // The WARN coverage claim comes from alt_warn_states_phrase(), the one
    // helper that owns it. It used to be count(alt_state_warn_urls()) rendered
    // as "48 US states and DC" — but that map's 48 keys ALREADY include DC, so
    // the sentence counted DC twice and invented a 48th state.
    $alt_warn_phrase = function_exists('alt_warn_states_phrase') ? alt_warn_states_phrase() : 'covered US states';
    ?>
    <?php /* DELETED, not moved: "Filter below; every number, chart and row
             updates to match. Bookmark any view: the address bar always matches
             the filters." A caption explaining that filters filter is a patch
             over a control that is not self-evident. The controls below say
             what they do; the URL keeps matching them either way. */ ?>

    <div id="alt-dashboard-status" class="alt-status" role="status" style="display:none"></div>

    <?php
    /*
      QUICK DATE RANGES, BACK ON THE SURFACE.

      A date preset is a one-tap, high-intent control and it had no visible
      home: the only way to ask for "the last 30 days" was to open the Date
      Range popover and type two dates, or to open the Filters panel and
      assemble it from the year, quarter and month dropdowns. That is three
      interactions for the most common question anyone brings to a layoff
      tracker.

      WHY HERE AND NOT BESIDE THE REGION TABS. The tabs sit above the
      at-a-glance board because they DO scope it. Dates do not: the board's four
      columns are fixed periods, so a date range over a Today column is a
      different question rather than a narrower one. Putting a date control
      above the board would restore precisely the "controls standing above
      content they do not control" defect that ordering was built to fix. So
      these sit at the top of the block of controls that DOES scope everything
      below, immediately above the date range they are shorthand for.

      They write the same from/to controls the popover writes, so they compose
      with the date basis: "Last 30 days" on the filing basis means filed in the
      last 30 days, and on the effective basis it means taking effect in them.
      Each one clears the year, quarter and month dropdowns, because those AND
      with a range and would otherwise silently return an empty intersection.
      No dropdown was demoted to make room: this row is new chrome, one line
      tall, and it removes two panel-opens from the common path.
    */
    ?>
    <div class="alt-datepresets" id="alt-datepresets">
        <span class="alt-ctl-label" id="alt-dp-label">Date</span>
        <div class="alt-ctl-row" role="group" aria-labelledby="alt-dp-label">
        <button type="button" class="alt-dp" data-dp="today">Today</button>
        <button type="button" class="alt-dp" data-dp="d7">Last 7 days</button>
        <button type="button" class="alt-dp" data-dp="d30">Last 30 days</button>
        <button type="button" class="alt-dp" data-dp="d90">Last quarter</button>
        <button type="button" class="alt-dp" data-dp="ytd">Year to date</button>
        <button type="button" class="alt-dp" data-dp="all">All time</button>
        </div>
    </div>

    <div class="alt-toolbar2">
        <div class="alt-range-wrap">
            <button type="button" class="alt-range-btn" id="alt-range-btn" aria-expanded="false">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
                <span id="alt-range-label">Date Range</span>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
            </button>
            <span class="alt-range-note-data" id="alt-range-note"></span>
            <div class="alt-range-pop" id="alt-range-pop" hidden>
                <div class="alt-filter">
                    <label for="alt-f-from">From</label>
                    <input type="date" id="alt-f-from">
                </div>
                <div class="alt-filter">
                    <label for="alt-f-to">To</label>
                    <input type="date" id="alt-f-to">
                </div>
                <button type="button" class="alt-btn alt-btn-sm" id="alt-range-clear">Clear Dates</button>
            </div>
        </div>
        <?php /* THE DEFAULT IS "WHEN IT WAS FILED", AND IT IS LISTED FIRST.

                 Both facts matter. A segmented switch is read left to right, so
                 the option carrying alt-datebasis-on has to be the one a reader
                 meets first or the control teaches that the page is showing the
                 other one. The default moved because the filing basis is the
                 basis every other published layoff figure is counted on, so a
                 reader lands on a number dated the way the one in their head is
                 dated. On the effective basis the same month reads roughly
                 double and needs a paragraph before it can be compared at all.

                 THE BASIS IS NOT A CLAIM OF EQUIVALENCE, and a sentence here
                 used to make it one: it put US July 2026 inside a hand-written
                 percentage of the national estimate. That was measured once, on a
                 month still collecting WARN notices, and the figure underneath
                 it kept moving. Measured 2026-08-13, US verified, filing basis:
                 May is 47% below the national figure, June 21% below, July 19%
                 ABOVE, and Jan to Jul is 67% of it. Same basis, different
                 populations, because a survey also counts federal reductions,
                 buyouts and employer estimates that file nothing. Do not write
                 a percentage into this file again; it has no recomputing
                 behind it and it decays silently.

                 The effective basis is not demoted out of existence. It is one
                 click away, every figure on the page recomputes on it, and a
                 deep link that names it is honoured. The titles are rewritten
                 by renderBasisCopy() from BASIS_COPY so this markup and the JS
                 cannot drift; these are the same strings. */ ?>
        <div class="alt-datebasis-wrap">
            <span class="alt-ctl-label" id="alt-datebasis-label">Count Layoffs By</span>
            <span class="alt-datebasis-switch" role="group" aria-labelledby="alt-datebasis-label">
            <button type="button" class="alt-datebasis-opt alt-datebasis-on" data-basis="notice" aria-pressed="true"
                title="Counts each layoff on the day its notice was filed or the cut was announced. This is the basis layoffs are reported on elsewhere, so our figure can be read beside a national estimate for the same month rather than converted first. It is not the same measurement. This is the default.">When it was filed</button>
            <button type="button" class="alt-datebasis-opt" data-basis="effective" aria-pressed="false"
                title="Counts each layoff on the day the cut takes effect, the day the jobs actually end. A different question from the filing basis, and equally real.">When it takes effect</button>
            </span>
        </div>
        <div class="alt-search-wrap">
            <label class="alt-ctl-label" for="alt-search">Search</label>
            <svg class="alt-search-ico" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
            <input type="search" id="alt-search" placeholder="Search company, industry, keyword…" autocomplete="off">
        </div>
        <label class="alt-sort"><span class="alt-ctl-label">Sort</span>
            <select id="alt-sort">
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="largest">Largest Cuts</option>
                <option value="smallest">Smallest Cuts</option>
            </select>
        </label>
    </div>

    <div class="alt-quickviews">
        <span class="alt-ctl-label" id="alt-qv-label">Quick Views</span>
        <div class="alt-ctl-row" role="group" aria-labelledby="alt-qv-label">
        <button type="button" class="alt-qv" data-qv="month">This Month</button>
        <button type="button" class="alt-qv" data-qv="largest">Largest Cuts</button>
        <button type="button" class="alt-qv" data-qv="sec">SEC-verified</button>
        <button type="button" class="alt-qv" data-qv="announced">Announced Only</button>
        <button type="button" class="alt-qv" data-qv="tech">Tech Industry</button>
        </div>
    </div>

    <?php
    /*
      ELEVEN DROPDOWNS BEHIND ONE BUTTON.

      This grid is `repeat(auto-fit, minmax(160px, 1fr))`, which on a 375px
      phone is ONE column: eleven stacked controls, roughly 700px of chrome,
      between the headline figure and the first row of data. The region chips,
      search, date range, date basis and sort stay out here because they are the
      controls a reader actually reaches for; everything else is now inside.

      NO-JS FIRST. The panel ships OPEN and the toggle ships `hidden`. layoffs.js
      unhides the toggle and collapses the panel on init, and it leaves the panel
      OPEN when the URL arrived with one of these filters already set, so a
      deep-linked view never hides the control that shaped it. A reader without
      JS keeps every filter exactly as before.

      The count on the button is written by updateFilterPanelCount() from the
      same readControl() the chips use, so "Filters (2)" cannot disagree with the
      two chips sitting under it.
    */
    ?>
    <div class="alt-filterbar-toggle-row">
        <button type="button" class="alt-btn alt-filterbar-toggle" id="alt-filters-toggle"
                aria-expanded="true" aria-controls="alt-filterbar-body" hidden>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 5h18M6 12h12M10 19h4"/></svg>
            <span>Filters</span><span class="alt-filters-count" id="alt-filters-count"></span>
        </button>
    </div>
    <div class="alt-filterbar" id="alt-filterbar-body">
        <div class="alt-filterbar-row">
            <div class="alt-filter" data-dd="Years" data-empty="All years">
                <label for="alt-f-years">Years</label>
                <select id="alt-f-years" multiple></select>
            </div>
            <div class="alt-filter" data-dd="Quarters" data-empty="All quarters">
                <label for="alt-f-quarters">Quarters</label>
                <select id="alt-f-quarters" multiple>
                    <option value="1">Q1 (Jan to Mar)</option>
                    <option value="2">Q2 (Apr to Jun)</option>
                    <option value="3">Q3 (Jul to Sep)</option>
                    <option value="4">Q4 (Oct to Dec)</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Months" data-empty="All months">
                <label for="alt-f-months">Months</label>
                <select id="alt-f-months" multiple>
                    <option value="1">January</option><option value="2">February</option>
                    <option value="3">March</option><option value="4">April</option>
                    <option value="5">May</option><option value="6">June</option>
                    <option value="7">July</option><option value="8">August</option>
                    <option value="9">September</option><option value="10">October</option>
                    <option value="11">November</option><option value="12">December</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Industries" data-empty="All industries">
                <label for="alt-f-industry">Industries</label>
                <select id="alt-f-industry" multiple></select>
            </div>
            <div class="alt-filter" data-dd="Countries" data-empty="All countries">
                <label for="alt-f-country">Countries</label>
                <select id="alt-f-country" multiple></select>
            </div>
            <div class="alt-filter" data-dd="US states" data-empty="All states">
                <label for="alt-f-state">US States</label>
                <select id="alt-f-state" multiple></select>
            </div>
            <div class="alt-filter" data-dd="Reasons" data-empty="All reasons">
                <label for="alt-f-reasons">Reasons</label>
                <select id="alt-f-reasons" multiple>
                    <?php /* REASON TAGS, not the AI tiles. These are read from the
                             stored source text (reason_tags); the AI tiles are counted
                             from the AI attribution flags. They used to share a name and
                             publish different numbers on one page. */ ?>
                    <option value="ai_automation">Reason tag: AI or automation</option>
                    <option value="possible_ai">Reason tag: AI press-linked</option>
                    <option value="revenue_decline">Revenue decline</option>
                    <option value="restructuring">Restructuring</option>
                    <option value="merger_acquisition">Merger / acquisition</option>
                    <option value="offshoring">Offshoring</option>
                    <option value="product_discontinuation">Product discontinued</option>
                    <option value="cost_reduction">Cost reduction</option>
                    <option value="macroeconomic">Macroeconomic</option>
                    <option value="closure">Plant / site closure</option>
                    <option value="bankruptcy">Bankruptcy / insolvency</option>
                    <option value="federal_workforce">Government / public sector</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Sources" data-empty="All sources">
                <label id="alt-lbl-verification" for="alt-f-verification">Sources</label>
                <select id="alt-f-verification" multiple>
                    <option value="gold">SEC filing (8-K/6-K)</option>
                    <option value="warn">WARN notice</option>
                    <option value="silver">Press release</option>
                    <option value="bronze">News</option>
                </select>
            </div>
            <div class="alt-filter" data-dd="Roles" data-empty="All roles">
                <label id="alt-lbl-roles" for="alt-f-roles">Roles Most Impacted</label>
                <select id="alt-f-roles" multiple>
                    <?php foreach (alt_role_categories() as $alt_rk => $alt_rlabel) : ?>
                    <option value="<?php echo esc_attr($alt_rk); ?>"><?php echo esc_html($alt_rlabel); ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="alt-filter">
                <label for="alt-f-company">Company</label>
                <input type="text" id="alt-f-company" placeholder="Type to search, e.g. Amazon" list="alt-company-suggest" autocomplete="off">
                <datalist id="alt-company-suggest"></datalist>
            </div>
            <div class="alt-filter">
                <label for="alt-f-keyword">Keyword in Excerpt</label>
                <input type="text" id="alt-f-keyword" placeholder="Search excerpts">
            </div>
            <div class="alt-filter">
                <label for="alt-f-minjobs">Minimum Job Count</label>
                <input type="number" id="alt-f-minjobs" min="0" step="1" placeholder="0">
            </div>
        </div>
        <?php /* Sources and Roles were pill strips for a while (visibility of
                 the evidence-tier facet); the owner reversed that on 2026-08-02
                 because the strips ate half the filter bar. They are compact
                 checkbox multi-select dropdowns again, inside the grid with
                 the other eleven controls, same element IDs so URL state,
                 chips, chart taps and Reset all behave unchanged. */ ?>
        <div class="alt-filterbar-reset">
            <button type="button" id="alt-f-reset" class="alt-btn alt-btn-reset">Reset All Filters</button>
        </div>
        <!-- Hidden state holders: quick-view pills are the visible controls -->
        <input type="checkbox" id="alt-f-ai" hidden>
        <?php /* The broad AI measure used to ride in the Reasons multi-select as
                 `possible_ai`, so tapping that doughnut slice returned a set about
                 twelve times the size it drew. It is its own filter now, with its
                 own removable chip. */ ?>
        <input type="checkbox" id="alt-f-ai-broad" hidden>
        <input type="checkbox" id="alt-f-announced" hidden>
    </div>

    <!-- Active-filter summary. Sits directly under the filter controls and
         sticks to the top as you scroll down past them (so what's filtered
         stays visible through the whole page), then re-docks here on the way
         back up. Empty (display:none) when no filters are set. -->
    <div id="alt-active-filters" class="alt-active-filters alt-active-filters--sticky" style="display:none"></div>

    <section class="alt-results-summary" aria-labelledby="alt-results-summary-title">
        <div class="screen-reader-text" id="alt-results-summary-title" role="heading" aria-level="2">Results summary</div>
        <?php
        // The tiles left in this row can all be added or compared safely; the
        // broad AI measure (deliberately NOT addable) renders in its own strip
        // below, so a reader can no longer sum across a row that mixes
        // measures. Captions state the fact; the arithmetic caveat lives in a
        // per-tile (i) disclosure instead of a paragraph on the tile face.
        ?>
        <?php
        /*
          EACH TILE SHOWS A NUMBER AND A LABEL. Its explanation is an (i) the
          reader opens, not a paragraph they have to read past.

          Five tiles times two or three lines of standing prose was roughly 90
          words of definition between the headline figure and the first row of
          data, and a reader who already knows what "verified" means had no way
          to skip it.

          The mechanism is <details class="alt-stat-i">, ALREADY used by the
          trend chart on this page, so there is one disclosure pattern here and
          not two. It is a real <details>: keyboard reachable, focus-visible
          styled, and the body is a plain child that is displayed when [open].
          Three separate caveats in this codebase have computed to display:none
          or 0x0 and were never read by anybody, so the guard test opens each
          one and measures RENDERED TEXT LENGTH rather than reading markup.
        */
        // $id is optional and exists for ONE case: the lead tile's body names
        // the active date basis, so layoffs.js has to be able to rewrite it
        // when the toggle changes. Every other body is a fixed definition and
        // carries no id.
        $alt_tile_i = function ($label, $body, $id = '') {
            return '<details class="alt-stat-i alt-stat-i-tile"><summary aria-label="' . esc_attr($label) . '">i</summary>'
                . '<span class="alt-stat-i-body"' . ($id !== '' ? ' id="' . esc_attr($id) . '"' : '') . '>' . $body . '</span></details>';
        };
        ?>
        <div class="alt-stats-bar" id="alt-stats-bar">
            <div class="alt-stat-card alt-stat-card-lead alt-fam-verified">
                <span class="alt-stat-value" id="alt-stat-total"><?php echo esc_html($alt_stat('total')); ?></span>
                <?php /* ONE BASIS PER SENTENCE. This read "Filed or reported,
                         counted on the day each cut takes effect", which names
                         BOTH bases in one breath and is therefore wrong on
                         whichever one is live. The body is now written by
                         renderBasisCopy() in layoffs.js from BASIS_COPY, so it
                         names the active basis and only that one, and it
                         changes when the toggle changes. The server prints the
                         default (filing) wording, byte-identical to
                         BASIS_COPY.notice.tile. */ ?>
                <span class="alt-stat-label">Verified job cuts <?php echo $alt_tile_i('What counts as verified', 'Counted on the day each cut was filed or announced. This is the basis layoffs are reported on elsewhere, so this figure can be set beside a national estimate for the same month. It is not the same measurement: we count only cuts with a public filing or named report behind them. Every row behind it links to its source.', 'alt-stat-total-i-body'); // phpcs:ignore ?></span>
                <span class="alt-stat-sub" id="alt-stat-total-entries"><?php echo esc_html($alt_period); ?></span>
                <span class="alt-stat-sub alt-stat-detail" id="alt-stat-total-basis"><?php echo esc_html($alt_hero_basis); ?></span>
            </div>
            <div class="alt-stat-card alt-fam-announced">
                <span class="alt-stat-value" id="alt-stat-announced"><?php echo esc_html($alt_stat('announced')); ?></span>
                <span class="alt-stat-label">Announced job cuts (planned) <?php echo $alt_tile_i('What announced means', 'Company plans at announcement stage, not yet in Verified.'); // phpcs:ignore ?></span>
                <span class="alt-stat-sub" id="alt-stat-announced-sub"><?php echo esc_html($alt_period_ann); ?></span>
            </div>
            <div class="alt-stat-card">
                <span class="alt-stat-value-row"><span class="alt-stat-value" id="alt-stat-companies"><?php echo esc_html($alt_stat('companies')); ?></span><span class="alt-stat-label">Companies <?php echo $alt_tile_i('What this tile covers', 'Coverage in this view: how many distinct employers, industries, countries and US states the current filters return.'); // phpcs:ignore ?></span></span>
                <span class="alt-stat-line"><b id="alt-stat-industries"><?php echo esc_html($alt_stat('industries')); ?></b> <span id="alt-stat-industries-label">industries</span></span>
                <span class="alt-stat-line"><b id="alt-stat-countries"><?php echo esc_html($alt_stat('countries')); ?></b> <span id="alt-stat-countries-label">countries with reported layoffs</span></span>
                <span class="alt-stat-line"><b id="alt-stat-states"><?php echo esc_html($alt_stat('states')); ?></b> <span id="alt-stat-states-label">US states</span></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-verified">
                <span class="alt-stat-value" id="alt-stat-ai"><?php echo esc_html($alt_stat('ai')); ?></span>
                <span class="alt-stat-label">🤖 AI cuts, verified (specific) <?php echo $alt_tile_i('How the AI tag is assigned', 'Verified-tier cuts where the employer named AI, in words we hold and can quote. We report the stated reason. We do not decide the cause. Examples: "AI now handles this work" or "replaced by AI."'); // phpcs:ignore ?></span>
                <span class="alt-stat-sub" id="alt-stat-ai-sub"><?php echo esc_html($alt_period); ?></span>
                <span class="alt-stat-sub" id="alt-stat-ai-share-line"></span>
            </div>
            <div class="alt-stat-card alt-stat-card-ai alt-fam-announced">
                <span class="alt-stat-value" id="alt-stat-ai-announced"><?php echo esc_html($alt_stat('ai-announced')); ?></span>
                <span class="alt-stat-label">🤖 AI cuts, announced (planned) <?php echo $alt_tile_i('How the AI tag is assigned here', 'Announced-tier plans that name AI, like "cutting roles as we adopt AI."'); // phpcs:ignore ?></span>
                <span class="alt-stat-sub" id="alt-stat-ai-announced-sub"><?php echo esc_html($alt_period_ann); ?></span>
            </div>
        </div>
        <?php
        // DERIVED TOTALS, AND THE SENTENCE THAT STOPS A DOUBLE COUNT.
        //
        // These three sat behind a <details> for a while, on the argument that
        // a caveat is a poor use of the first screen. The owner questioned
        // that and he is right to: "Each of these is built from the tiles above
        // rather than counted separately, so adding one of them to those tiles
        // would count the same cuts twice" is precisely the sentence that stops
        // a journalist publishing a number twice its true size, and it was
        // sitting behind a click that most readers never make.
        //
        // This is the same correction .alt-why-lower already carries a few
        // hundred lines down: that paragraph was a <details> too, and for as
        // long as it was, it measured 0px wide on a rendered page and nobody
        // outside this repository had ever read it. A <section> has no open
        // state that can default shut and no toggle a later edit can leave
        // closed.
        //
        // The heading, every number, every per-tile explanation and every
        // element ID are unchanged, so renderStats() keeps writing all three.
        // The change is which of them a reader can see without asking.
        ?>
        <section class="alt-stats-derived" aria-labelledby="alt-stats-derived-h">
            <h3 class="alt-stats-derived-h" id="alt-stats-derived-h">Derived totals, and why they do not add up with the tiles above</h3>
            <div class="alt-stats-derived-body">
                <p class="alt-stats-derived-note">Each of these is built from the tiles above rather than counted separately, so adding one of them to those tiles would count the same cuts twice.</p>
                <div class="alt-broad-strip">
                    <div class="alt-stat-card alt-fam-all">
                        <span class="alt-stat-value" id="alt-stat-all"><?php echo esc_html($alt_stat('all')); ?></span>
                        <span class="alt-stat-label">Verified + announced job cuts</span>
                        <div class="alt-stat-desc">Both tiers together. One cut can appear in both stages (an announced plan often becomes a verified filing later), so this is not a count of distinct people.</div>
                        <span class="alt-stat-sub" id="alt-stat-all-sub"><?php echo esc_html($alt_period_ann); ?></span>
                    </div>
                    <div class="alt-stat-card alt-stat-card-ai alt-fam-total">
                        <span class="alt-stat-value" id="alt-stat-ai-total"><?php echo esc_html($alt_stat('ai-total')); ?></span>
                        <span class="alt-stat-label">🤖 AI cuts, total (specific)</span>
                        <span class="alt-stat-desc">The two AI tiles above, summed: cuts the employer or plan explicitly named AI for.</span>
                        <span class="alt-stat-sub" id="alt-stat-ai-total-sub"><?php echo $alt_sv === null ? '' : esc_html($alt_stat('ai') . ' verified + ' . $alt_stat('ai-announced') . ' announced'); ?></span>
                    </div>
                    <div class="alt-stat-card alt-stat-card-ai alt-stat-card-broad">
                        <span class="alt-stat-value" id="alt-stat-ai-broad"><?php echo esc_html($alt_stat('ai-broad')); ?></span>
                        <span class="alt-stat-label">🤖 AI-linked, broad (wider lens)</span>
                        <div class="alt-stat-desc">A separate, looser measure. Counts press framing like "amid AI push" as well as employer statements, so it is wider than the strict AI figure by design and never sums with it.</div>
                        <span class="alt-stat-sub" id="alt-stat-ai-broad-sub"><?php echo esc_html($alt_period); ?></span>
                        <span class="alt-stat-sub" id="alt-stat-ai-broad-share-line"></span>
                    </div>
                </div>
            </div>
        </section>
        <?php /* DELETED: the "New here? Start with:" box and its three links
                 ("What these numbers mean", "Where do we get this data?", "How we
                 catch & fix errors"). A page that needs a start-here list has
                 failed to be self-evident, and those three joined "How we count",
                 "Why this is verified" and "See the full methodology" as SIX
                 entry points to one subject. There is one now: "How we count",
                 in the hero, next to the number it explains. Every destination
                 those links pointed at is still on this page, in the methodology
                 section, and the full methodology page links on to each. */ ?>
        <?php /* THE ONLY ROUTE BETWEEN THE TWO PRODUCTS, and it was a sentence
                 with an inline link in 13px body grey. Somebody who wants the
                 hiring side has to notice a phrase in a paragraph they have no
                 other reason to read. The sentence stays, because it is the
                 context that makes the destination make sense, and the link is
                 now a control: a real button-shaped target with its own
                 accessible name, a visible focus ring, and colours from the
                 theme tokens so it holds contrast in light and dark alike.
                 Nothing here is hardcoded; --alt-accent and --alt-on-accent are
                 the same pair the primary hero action uses. */ ?>
        <p class="alt-crosslink">Looking for who is hiring instead? Hiring signals are tracked separately.
            <a class="alt-btn alt-btn-sm alt-crosslink-btn" href="<?php echo esc_url(home_url('/talent-intelligence-tracker/')); ?>" aria-label="Open the Talent Intelligence Tracker, our hiring signals tracker">Talent Intelligence Tracker</a></p>
    </section>

    <?php /* NOT A <details>. This is the paragraph that makes our figure
             defensible when a reader compares it against an independent
             national estimate, and for as long as it was a collapsed
             disclosure it was measured at 0px wide on a rendered page: nobody
             who did not click it had ever read it. A caveat nobody sees is not
             a caveat. It is a <section> now, so there is no open state that can
             default shut and no toggle for a later edit to leave closed. */ ?>
    <section class="alt-why-lower" aria-labelledby="alt-why-lower-h">
        <h2 class="alt-why-summary" id="alt-why-lower-h">Why our number is lower, and why it&rsquo;s the one to cite</h2>
        <div class="alt-why-body">
        <p class="alt-why-lead">Announcement surveys count what companies <em>say</em>. We count what you can <em>prove</em>. Every figure on this page clicks through to a legal filing or a named report. So our total is a <strong>documented floor</strong>: smaller than the headline estimates by design, and verifiable by design.</p>
        <div class="alt-why-grid">
            <div class="alt-why-item"><b>They book multi-year plans on day one.</b> A &ldquo;20,000 over two years&rdquo; announcement lands in their total instantly. We add each cut as its WARN notice or SEC filing actually appears.</div>
            <div class="alt-why-item"><b>They fold in receiptless separations.</b> Buyouts, attrition, and federal-workforce reductions that name no company and file nothing. Hundreds of thousands of jobs with no document to link. We don&rsquo;t claim what we can&rsquo;t source.</div>
            <div class="alt-why-item"><b>We don&rsquo;t pad to match a bigger headline.</b> A number a journalist can verify is worth more than a bigger one they can&rsquo;t. Nothing here is estimated into existence.</div>
            <div class="alt-why-item"><b>On AI, the thing this tracker exists for.</b> Every flagged cut carries the employer&rsquo;s own words naming AI. Those words are quotable and clickable, and we hold them to a standard the estimates don&rsquo;t apply to themselves.</div>
        </div>
        <?php /* The double-pass and dedup detail lives on the methodology page,
                 where the fact-checker who needs it will look; 70 words about
                 the pipeline were standing between the reader and the data. */ ?>
        <?php /* One methodology link out of this section, not two. It ended with
                 "How we check ourselves →" and then "See the full methodology →"
                 pointing at two different destinations for the same question. */ ?>
        <p class="alt-why-quality">Every figure links to a primary source, and every correction and merge is disclosed in the <a href="#alt-corrections">open log</a>. Nothing is quietly edited. <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">How we count &rarr;</a></p>
        </div>
    </section>

    <?php $alt_expand = '<button type="button" class="alt-expand" aria-label="Expand chart" title="Expand"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg></button>'; ?>
    <?php /* id, not just a class: layoffs.js marks this whole grid busy while
             the one /aggregate call every chart in it depends on is in
             flight (busyTrack in assets/layoffs.js). */ ?>
    <div class="alt-minigrid" id="alt-minigrid">
        <div class="alt-grid-h"><h2>Where the cuts are</h2><p>Geography first: the map plots every cut with a named place, then the state and country rankings below it.</p></div>
        <div class="alt-mini alt-chart-card alt-map-card" id="alt-map-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">The map of job cuts <span class="alt-chart-sub"><b style="color:var(--alt-blue)">blue</b> = all job cuts &middot; <b style="color:var(--alt-ai)">red</b> = AI-attributed cuts, the employer's own words (sits inside; small red dots are kept visible even when the share is tiny) &middot; circle size = number of jobs &middot; tap a bubble to filter, tap the map to zoom &middot; hover for exact numbers, expand &#10530; for a bigger view &middot; only cuts with a named country or state are plotted; the rest are counted in the totals but not on the map</span></div>
                <span class="alt-chart-btns">
                    <span class="alt-map-toggle">
                        <button type="button" class="alt-map-scope alt-map-scope-on" data-scope="world">World</button>
                        <button type="button" class="alt-map-scope" data-scope="us">US states</button>
                    </span>
                    <button type="button" class="alt-chart-dl" data-dl="alt-chart-aimap" data-kind="png" aria-label="Download map as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?>
                </span>
            </div>
            <div class="alt-chart-box alt-map-box"><div id="alt-chart-aimap" aria-label="AI-attributed layoffs by geography"></div></div>
            <p class="alt-map-total alt-muted" id="alt-map-total"></p>
            <p class="alt-map-empty alt-muted" id="alt-map-note" style="display:none"></p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Layoffs by US state <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter · our documented cuts, not jobless claims</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-states" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-states"></div>
            <?php /* BASIS LINE. Written by layoffs.js (setBarBasisNote) from the same
                     totals the tiles render, so it cannot drift from them. The bars are
                     verified job cuts; before 2.19.263 they were verified PLUS announced
                     beside a verified-only headline, about 70% over, unexplained. */ ?>
            <p class="alt-chart-note alt-chart-note-basis" id="alt-bars-states-basis" hidden></p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h" id="alt-country-chart-title">Layoffs by country <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-countries" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-countries"></div>
            <?php /* BASIS LINE. Written by layoffs.js (setBarBasisNote) from the same
                     totals the tiles render, so it cannot drift from them. The bars are
                     verified job cuts; before 2.19.263 they were verified PLUS announced
                     beside a verified-only headline, about 70% over, unexplained. */ ?>
            <p class="alt-chart-note alt-chart-note-basis" id="alt-bars-countries-basis" hidden></p>
        </div>
        <div class="alt-mini alt-chart-card" id="alt-claims-states-card" hidden>
            <div class="alt-chart-head">
                <div class="alt-chart-h">Jobless claims by US state <span class="alt-chart-sub">official government data (DOL), <span id="alt-claims-states-month">latest month</span> · context only, not our counts</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-claims-states" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-claims-states"></div>
            <?php /* Collapsed by default: as an always-open paragraph this note made the
                     card roughly twice the height of its two siblings in the same row,
                     leaving a large blank gap under them. The disclosure keeps the full
                     caveat on the page (it matters - this is a different universe from
                     our counts) without paying for it in layout. */ ?>
            <details class="alt-chart-more"><summary>What this measures</summary>
            <p>Official DOL jobless claims, for scale. A much larger universe than our documented cuts; never added to our totals. Counts everyone who filed for unemployment benefits that month, all states, all causes. Not affected by the filters above. Refreshes weekly.</p></details>
        </div>
        <div class="alt-grid-h"><h2>How it is trending</h2><p>The same filtered data over time: monthly totals with jobless-claims context, this year against last, and how often employers name AI.</p></div>
        <div class="alt-mini alt-chart-card alt-trend-card">
            <div class="alt-chart-head">
                <?php /* Two plain sentences visible (what a bar IS, what a tap
                         does); every mechanic (future-dated rows, overlay
                         axis, the whole-record strip) lives behind the (i). */ ?>
                <div class="alt-chart-h">Jobs cut per month <span class="alt-chart-sub">Verified job cuts we can document, dated to the month each cut takes effect. Tap a month to filter the whole page to it; tap again to clear. · <span id="alt-trend-range"></span> <details class="alt-stat-i"><summary aria-label="How this chart is built">i</summary><span class="alt-stat-i-body">The solid line is verified cuts; the dashed line is announced plans, never mixed into the verified line. <span id="alt-trend-future"></span> The small strip under the chart shows the whole record and where the charted window sits. The optional grey overlay is official US jobless claims on its own right-hand axis, for scale only.</span></details></span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-weekly" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <label class="alt-claims-toggle" id="alt-claims-toggle-wrap" hidden><input type="checkbox" id="alt-claims-toggle" checked> <span>Overlay US jobless claims (BLS/DOL), background context</span></label>
            <div class="alt-chart-box"><canvas id="alt-chart-weekly"></canvas></div>
            <?php /* The whole-record trajectory. Filled by layoffs.js (drawTrajectory)
                     and hidden until it has real months to draw, so a failed or
                     skipped fetch leaves no empty frame behind. It is deliberately
                     inside this card rather than a card of its own: it answers
                     "where does the charted window sit on the record", which is a
                     question about the chart above it. */ ?>
            <div class="alt-tj" id="alt-trend-full" hidden></div>
            <?php /* PARTIAL-PERIOD NOTE. Filled by layoffs.js (setPartialNote) whenever
                     the charted window reaches the month the clock is still inside.
                     It is a visible paragraph, not a line inside the (i) disclosure:
                     a partial point drawn like a finished one publishes the reverse
                     of the trend, and a caveat nobody opens does not undo that. */ ?>
            <p class="alt-chart-note alt-chart-note-partial" id="alt-trend-partial" hidden></p>
            <p class="alt-chart-note" id="alt-claims-note" hidden>Grey bars show everyone who filed for US unemployment benefits that month, for scale. They are context and are never added to our counts.</p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">This year vs last year <span class="alt-chart-sub">verified cuts · select 2+ years to compare more</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-yoy" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-yoy"></canvas></div>
            <p class="alt-chart-note alt-chart-note-partial" id="alt-yoy-partial" hidden></p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">AI share of verified cuts, monthly <span class="alt-chart-sub">how attribution is trending · tap a month to scope the page, again to clear</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-ai-share-trend" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-share-trend"></canvas></div>
            <p class="alt-chart-note alt-chart-note-partial" id="alt-ai-share-partial" hidden></p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Cumulative AI-attributed cuts <span class="alt-chart-sub" id="alt-cum-range"></span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-ai-cumulative" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-ai-cumulative"></canvas></div>
        </div>
        <div class="alt-grid-h"><h2>Who is cutting, and why</h2><p>Industries, stated reasons, the biggest single layoffs and repeat cutters, plus which data source each figure came from.</p></div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">By industry <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-industries" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-barlist" id="alt-bars-industries"></div>
            <?php /* BASIS LINE. Written by layoffs.js (setBarBasisNote) from the same
                     totals the tiles render, so it cannot drift from them. The bars are
                     verified job cuts; before 2.19.263 they were verified PLUS announced
                     beside a verified-only headline, about 70% over, unexplained. */ ?>
            <p class="alt-chart-note alt-chart-note-basis" id="alt-bars-industries-basis" hidden></p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head">
                <div class="alt-chart-h">Reasons cited <span class="alt-chart-sub">tap to filter</span></div>
                <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-reasons" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-reasons"></canvas></div>
            <?php /* BASIS LINE. This was the one chart in the grid without one, and
                     it was also the one drawing a different basis from the headline.
                     Written by layoffs.js (reasonsBasisNote). */ ?>
            <p class="alt-chart-note alt-chart-note-basis" id="alt-chart-reasons-basis" hidden></p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">Largest single job cuts <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-leaders" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-leaders"></div>
        </div>
        <?php /* alt-chart-card was missing here and on no other card in this grid,
                 so "Repeat layoffs" rendered with no border, no card background and
                 no share/embed controls while its two row-mates had all three. */ ?>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">Repeat layoffs <span class="alt-chart-sub">companies with 2+ rounds in this period · tap to filter</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-repeat" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-repeat"></div>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">By data source <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-sourcetypes" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-sourcetypes"></div>
            <?php /* BASIS LINE. Written by layoffs.js (setBarBasisNote) from the same
                     totals the tiles render, so it cannot drift from them. The bars are
                     verified job cuts; before 2.19.263 they were verified PLUS announced
                     beside a verified-only headline, about 70% over, unexplained. */ ?>
            <p class="alt-chart-note alt-chart-note-basis" id="alt-bars-sourcetypes-basis" hidden></p>
        </div>
        <div class="alt-mini alt-chart-card">
            <div class="alt-chart-head"><div class="alt-chart-h">AI intensity by industry <span class="alt-chart-sub">share of each industry's cuts the employer attributed to AI · tap to filter · industries under 1,000 cuts excluded</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-ai-intensity" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-ai-intensity"></div>
            <?php /* THE SPARSENESS, LABELLED. This card legitimately draws one
                     bar in most views because of its 1,000-cut floor, and an
                     unexplained single row beside a full-height neighbour reads
                     as a broken card. Written by layoffs.js from the counts it
                     just used, so it cannot claim a number the bars contradict.
                     Not hidden and not inside a disclosure. */ ?>
            <p class="alt-chart-note alt-chart-note-basis" id="alt-bars-ai-intensity-note" hidden></p>
            <p class="alt-chart-note">Each share is the employer's own words, not our inference. <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>">See the verbatim quotes and their sources →</a></p>
        </div>
        <div class="alt-mini alt-chart-card" id="alt-roles-card">
            <div class="alt-chart-head"><div class="alt-chart-h">Roles most impacted <span class="alt-chart-sub" id="alt-roles-sub">Each bar is total job cuts for that team; the <span class="alt-ai-key"></span> orange part and 🤖 number are the AI-attributed share. From only the reports that named which teams were cut.</span></div><span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-bars-roles" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><?php echo $alt_expand; ?></span></div>
            <div class="alt-barlist" id="alt-bars-roles"></div>
        </div>
        <?php
        // In-grid entry point to the record permalink pages, filling the empty
        // slot beside Roles. Server-rendered from alt_facet_index() — the same
        // memoised 6-hour transient the Browse section reads, ZERO extra
        // queries — and covering the whole record, so it is labeled as
        // filter-exempt exactly like the jobless-claims card (the only honest
        // label: making it filter-scoped would put three grouped COUNTs on
        // every filter tap, the cost the opt-in facet_counts block exists to
        // avoid). Rows are links (a permanent per-place page is the better
        // destination than a filter here, same call as the talent strip's
        // company links); the live filterable versions of these dimensions are
        // the two geography cards above.
        $alt_places = array();
        if (function_exists('alt_facet_index')) {
            foreach (alt_facet_index() as $alt_pf) {
                if ($alt_pf['dim'] === 'country' || $alt_pf['dim'] === 'state') $alt_places[] = $alt_pf;
            }
            usort($alt_places, function ($x, $y) { return (int) $y['events'] - (int) $x['events']; });
            $alt_places = array_slice($alt_places, 0, 12);
        }
        if ($alt_places) : $alt_pmax = max(1, (int) $alt_places[0]['events']); ?>
        <div class="alt-mini alt-chart-card" id="alt-places-card">
            <div class="alt-chart-head"><div class="alt-chart-h">Browse the record: top places <span class="alt-chart-sub">source-linked entries over the whole record · each row opens that place's permanent record page · whole record, not affected by the filters above</span></div></div>
            <div class="alt-barlist alt-barlist-static">
                <?php foreach ($alt_places as $alt_pf) : $alt_pw = max(2, (int) round(100 * (int) $alt_pf['events'] / $alt_pmax)); ?>
                <a class="alt-barrow alt-barrow-link" href="<?php echo esc_url($alt_pf['url']); ?>">
                    <span class="alt-barrow-top"><span class="alt-barrow-name"><?php echo esc_html($alt_pf['display']); ?><?php echo $alt_pf['dim'] === 'state' ? ' (US state)' : ''; ?></span><span class="alt-barrow-val"><?php echo esc_html(number_format((int) $alt_pf['events'])); ?> entries</span></span>
                    <span class="alt-bartrack"><span class="alt-barfill" style="width:<?php echo (int) $alt_pw; ?>%"></span></span>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
        <?php endif; ?>
    </div>

    <div class="alt-count-row" id="alt-count-row">
        <div class="alt-count-left">
            <span id="alt-table-count" class="alt-count-strong">Loading…</span>
        </div>
        <div class="alt-toolbar-actions">
            <a class="alt-btn alt-btn-sm" id="alt-export-csv" href="<?php echo esc_url($alt_csv); ?>"><?php echo $alt_dl; ?> <span id="alt-export-csv-label">CSV</span></a>
            <a class="alt-btn alt-btn-sm" id="alt-export-json" href="<?php echo esc_url($alt_json); ?>"><?php echo $alt_dl; ?> <span id="alt-export-json-label">JSON</span></a>
        </div>
    </div>

    <div id="alt-table-status" class="alt-status" role="status" style="display:none"></div>

    <?php /* The results are a list of cards, not a table, and they are the same
             card the sibling talent tracker renders so a reader moving between
             the two products meets one component rather than two.

             It is an <ol> because the order is the content: "newest first" and
             "largest cuts" are the two things the sort control says out loud,
             and an unordered list would tell a screen reader the opposite.

             Rows are fetched and paged SERVER-side (25 at a time, `/query`
             already does ORDER BY + LIMIT/OFFSET), so the card being taller
             than a table row costs nothing at 63,000 events: the browser never
             holds more than one page of them. */ ?>
    <ol class="alt-cards" id="alt-cards" aria-busy="true"></ol>

    <nav class="alt-pager" id="alt-pager" aria-label="Result pages" hidden></nav>

    <?php
    /*
      THE DATA STRIP: everything that used to crowd the first screen, kept
      whole, sitting after the data instead of in front of it.

      Nothing here is new and nothing here was cut. The freshness panel (Roo's
      status header and the next collection time), the coverage ribbon, the
      cite-and-export row and the report/press/embed links all rendered above
      the headline figure; a reader met four link groups and a status panel
      before they met a layoff. They answer "how current is this and how do I
      take it away", which is a question you ask AFTER you have looked at the
      data, so they now sit where that question gets asked.

      The element IDs are unchanged (#alt-next-top, #alt-citeline-total,
      #alt-export-csv-top and the rest), so renderStatus(), renderStats() and
      the export-href plumbing in layoffs.js keep writing all of them.
    */
    $alt_cov = alt_coverage_counts();
    $alt_cov_first = !empty($alt_cov['first']) ? date_i18n('M Y', strtotime($alt_cov['first'])) : '';
    ?>
    <section class="alt-datastrip" aria-label="How current this is, and how to cite it">
        <aside class="alt-fresh" aria-label="Freshness">
            <?php echo function_exists('alt_render_status_header') ? alt_render_status_header() : ''; ?>
            <?php if ($alt_next_ts) : ?>
            <span class="alt-fresh-next" id="alt-next-top">Next update <?php echo esc_html(gmdate('M j, H:i', $alt_next_ts)); ?> UTC</span>
            <?php endif; ?>
            <?php if ($alt_sv !== null) : ?>
            <?php /* The headline total and the AI figure live in the hero and are
                     deliberately NOT repeated here: the same number twice, once at
                     72px and once at 20px, invites the reader to wonder which of
                     the two is the real one. */ ?>
            <?php
            /* YEAR AND ALL-TIME PAIRS (owner request 2026-08-14, matching the
               talent tracker's glance strip). The year figures come from the
               same bootstrap aggregate as the tiles; the all-time figures are
               one cached COUNT query. The headline jobs total is still NOT
               repeated here, for the reason above: entries, companies and
               countries are the record's shape, not a second headline. */
            $alt_at = get_transient(alt_figure_cache_key('fresh_alltime'));
            if (!is_array($alt_at)) {
                global $wpdb; $alt_att = alt_db_table();
                $alt_at = $wpdb->get_row(
                    "SELECT COUNT(*) e, COUNT(DISTINCT company_key) co,
                            COUNT(DISTINCT NULLIF(country,'')) c
                     FROM $alt_att WHERE superset_of=0", ARRAY_A) ?: array();
                set_transient(alt_figure_cache_key('fresh_alltime'), $alt_at, HOUR_IN_SECONDS);
            }
            $alt_yr_label = current_time('Y');
            ?>
            <div class="alt-fresh-stats">
                <span class="alt-fresh-stat"><b><?php echo esc_html($alt_stat('companies')); ?></b><i>companies · <?php echo esc_html($alt_yr_label); ?></i></span>
                <span class="alt-fresh-stat"><b><?php echo number_format((int) ($alt_at['co'] ?? 0)); ?></b><i>companies · all time</i></span>
                <span class="alt-fresh-stat"><b><?php echo esc_html($alt_stat('countries')); ?></b><i>countries · <?php echo esc_html($alt_yr_label); ?></i></span>
                <span class="alt-fresh-stat"><b><?php echo number_format((int) ($alt_at['c'] ?? 0)); ?></b><i>countries · all time</i></span>
                <span class="alt-fresh-stat"><b><?php echo number_format((int) ($alt_at['e'] ?? 0)); ?></b><i>entries · all time</i></span>
            </div>
            <?php endif; ?>
        </aside>
        <p class="alt-ribbon">
            <span class="alt-ribbon-scope">Covering <?php echo $alt_cov_first ? '<b>' . esc_html($alt_cov_first) . '</b> to ' : ''; ?><b><?php echo esc_html(date_i18n('M j, Y')); ?></b> · <b><?php echo (int) $alt_cov['countries']; ?></b> countries · <b><?php echo (int) $alt_cov['us_states']; ?></b> US states<?php echo !empty($alt_cov['dc']) ? ' + DC' : ''; ?></span>
            <span class="alt-ribbon-links"><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Sources</a> · <a href="#alt-recall-measured">How complete, measured</a> · <a href="#alt-corrections">Corrections</a> · <a href="<?php echo esc_url(home_url('/talent-intelligence-tracker/')); ?>">Hiring is tracked separately</a></span>
        </p>
        <p class="alt-citeline">
            <?php if ($alt_sv !== null) : ?>
            <?php /* "so far, as of <today>" is a TO-DATE claim, so it quotes the
                     to-date figure. It used to quote the whole-window total, which
                     disagreed with the FAQPage JSON-LD this same page emits from
                     alt_live_numbers() (that query has always clamped at today).

                     THAT SENTENCE IS NO LONGER TRUE OF THE BASIS, and saying so
                     is the point of this paragraph. Both figures clamp at today,
                     but since 2.20.4 this line's ROWS are selected on the filing
                     basis and alt_live_numbers()' rows are selected on the
                     effective one, so the two are the same question over two
                     different windows. Measured live on 2026-08-12: 445,869 here
                     against 479,410 in the JSON-LD, 33,541 apart. 2.20.12 chose
                     to keep them apart and label them rather than converge them
                     (reasons in alt_live_numbers()), so this line names its basis
                     below and the FAQ answer names the other one. Do not restore
                     a comment claiming these two agree.

                     IT NOW SAYS WHICH OF THE PAGE'S TOTALS IT IS. "N verified job
                     cuts recorded for 2026 so far" named no geography, no basis,
                     and a period that reads like the hero's. Three live totals on
                     this page answered three different questions under wording
                     that made them look like one claim, and this was the smallest
                     of the three: 24,754 beside a hero of 484,427. A screenshot of
                     this line, captioned as our figure, was a story we handed out.
                     The geography, period and basis spans are written by
                     renderStats() from the SAME labels the hero uses. */ ?>
            <span class="alt-citeline-stat"><b id="alt-citeline-total"><?php echo esc_html($alt_stat('to-date')); ?></b> verified job cuts <span id="alt-citeline-geo"><?php echo esc_html($alt_hero_geo); ?></span> have already taken effect, as of <?php echo esc_html(date_i18n('M j, Y')); ?>. This view covers <span id="alt-citeline-period"><?php echo esc_html($alt_hero_period); ?></span>, <span id="alt-citeline-basis"><?php echo esc_html($alt_hero_basis); ?></span>.</span>
            <?php endif; ?>
            <span class="alt-citeline-links"><a href="#alt-cite-box">Cite this tracker</a> · <a id="alt-export-csv-top" href="<?php echo esc_url($alt_csv); ?>"><span id="alt-export-csv-top-label">CSV</span></a> · <a id="alt-export-json-top" href="<?php echo esc_url($alt_json); ?>"><span id="alt-export-json-top-label">JSON</span></a> · <a href="<?php echo esc_url($alt_api); ?>">API</a></span>
        </p>
        <?php /* THE PRESS LINK IS NO LONGER ONE OF THESE, and that is the whole
                 of the demotion: it was promoted to a button in the hero
                 (2.20.32) and this row is 31,707px down a 44,128px page at
                 375px. Offering the same destination twice under the same name,
                 once where it is seen and once where it is not, teaches nobody
                 anything and makes the second one look like a different page.
                 The other three are untouched and still here: each is somebody's
                 route to something and none of them has a route above it. */ ?>
        <p class="alt-lead"><span class="alt-lead-links"><a class="alt-report-star" href="<?php echo esc_url(home_url('/ai-layoff-tracker/report/')); ?>">★ Monthly report (1-pager)</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>"><?php echo esc_html(alt_page_link_label('page-ai-quotes.php', 'AI layoffs, in the employer\'s own words')); ?></a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/publisher-tools/')); ?>">Embed this tracker</a></span></p>
        <?php include ALT_PLUGIN_DIR . 'templates/partials/scan-scope.php'; ?>
    </section>

    <section class="alt-methodology alt-faq" itemscope>
        <div class="alt-detail-h" role="heading" aria-level="2" style="font-size:19px;margin:0 0 10px">Frequently asked questions</div>
        <?php foreach (alt_faq_items() as $qa) : ?>
        <details class="alt-faq-item">
            <summary><?php echo esc_html($qa[0]); ?></summary>
            <div class="alt-method-body"><p><?php echo esc_html($qa[1]); ?><?php
                if (isset($qa[2]) && is_array($qa[2])) {
                    echo ' <a href="' . esc_url(home_url('/' . ltrim($qa[2][0], '/'))) . '">' . wp_kses($qa[2][1], array()) . '</a>';
                } ?></p></div>
        </details>
        <?php endforeach; ?>
    <details class="alt-methodology" id="alt-metric-definitions" open>
        <summary>Methodology &amp; sources (for journalists &amp; researchers)</summary>
        <div class="alt-method-body">
            <p><b>The short version.</b> <b>Verified job cuts</b> are cuts with a filing or named source behind them; the main figure. By default we count each on the day it was filed or announced, the basis used elsewhere. The &ldquo;Count layoffs by&rdquo; control recounts the page on the effective date instead. <b>AI-attributed</b> is the subset where the employer named AI in words we can quote. <b>Announced</b> is a separate, labeled tier of announcement-stage plans, never mixed into the verified total. Nothing is estimated; every number links to a legal filing or named report, and country/US-state filters describe where the jobs were, not an employer's headquarters.</p>
            <p><b>How the AI tag works.</b> Only a primary or contributing cause counts, and each one needs an exact supporting quote. Investment in AI, future projections, or AI used to pick who goes do not qualify. A separate broader measure is labeled and never merged in.</p>
            <p class="alt-method-cta"><a class="alt-method-fulllink" href="<?php echo esc_url(home_url('/ai-layoff-tracker/methodology/')); ?>">Read the full methodology and sources &rarr;</a> &middot; extraction, dedup, coverage limits, why our totals differ, and API access, all in detail.</p>
        </div>
    </details>
    <details class="alt-methodology" id="alt-data-sources">
        <summary>Where do we get this data? Every source, by country</summary>
        <div class="alt-method-body">
            <p>We collect official government filings and notices directly: SEC EDGAR, including Item 2.05 exit-cost filings, and WARN notices from <?php echo esc_html($alt_warn_phrase); ?>. For the EU we read Eurofound ERM. It is the EU agency's own restructuring database, but its national correspondents compile it from media reports. The filings employers make to labour authorities stay confidential. We also monitor press-release wires and reviewed company investor-relations feeds. And <?php echo number_format((int) $alt_scan_outlets); ?> reviewed news outlets across <?php echo number_format((int) $alt_scan_countries); ?> countries surface coverage through GDELT's 65-language index and Google News. We work from an allowlist and never crawl those outlets directly. Every published entry links to its source. A handful of US states publish no usable WARN register: Arkansas, Wyoming, New Hampshire, Missouri, Hawaii and Oklahoma. For those states we also show the official monthly unemployment rate from the US Bureau of Labor Statistics, sourced and dated. It is a clearly separate context metric, and we never mix it into the layoff counts. <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">See the full source directory</a>.</p>
            <?php
            // Rendered from the committed weekly measurement (data/recall-measurement.json,
            // written by recall_precision.py), never typed: when capture improves the page
            // follows. If the file is missing or malformed the paragraph is OMITTED —
            // an absent measurement is honest, a stale typed number is not.
            $alt_rm = function_exists('alt_recall_measurement') ? alt_recall_measurement() : null;
            if ($alt_rm) : ?>
            <p class="alt-muted" id="alt-recall-measured"><b>How complete is that, measured?</b> We
            enumerated every SEC 8-K filed between 1 July 2025 and 30 June 2026
            that qualified for this test. A filing qualified if its structured
            filing header carries Item 2.05 and it states an absolute number of
            affected employees. Then we checked how many appear
            here. <b><?php echo (int) $alt_rm['matched']; ?> of <?php echo (int) $alt_rm['reference']; ?></b>,
            or <?php echo (int) $alt_rm['pct']; ?>% (95% confidence interval
            <?php echo (int) $alt_rm['lo_pct']; ?>% to <?php echo (int) $alt_rm['hi_pct']; ?>%).
            So this is a floor and not a census, and it is why the page does not
            claim to hold every filing.<?php if (isset($alt_rm['precision_ok'])) : ?> Where a count is published, it is
            accurate: <?php echo (int) $alt_rm['precision_ok']; ?> of <?php echo (int) $alt_rm['precision_checked']; ?> checked figures appear verbatim in the cited
            source.<?php endif; ?> That measurement covers one source family over one year. It
            says nothing about private employers, non-US layoffs, or the WARN and
            news routes, which we count separately. We re-measure it weekly
            against the same frozen filing list, so this paragraph updates as
            capture improves.</p>
            <?php endif; ?>
            <?php /* The full 700-outlet directory used to render here, between
                     the charts and the FAQ/cite block — ballast for every
                     audience on this page (the one reader in a hundred who
                     wants the list gets it, still generated from the
                     collector's own allowlist, on the Sources page). */ ?>
            <p><b>The full outlet directory</b>, every country and every reviewed outlet we scan with each country's official register, lives on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data Sources page</a>, generated straight from the collector's own allowlist.</p>
        </div>
    </details>
    <details class="alt-methodology alt-conversion-card" id="alt-conversion-card" open>
        <summary>Do announced cuts actually happen?</summary>
        <div class="alt-method-body">
            <p class="alt-muted" style="margin-top:0">Share of each month's announced job cuts that show verified records (filings or sourced reports) from the same company within 6 months. Matches are capped per announcement, so a month can never exceed 100%.</p>
            <div class="alt-conv-range" role="group" aria-label="Time range">
              <button type="button" class="alt-conv-btn alt-conv-on" data-range="24">Last 2 years</button>
              <button type="button" class="alt-conv-btn" data-range="60">Last 5 years</button>
              <button type="button" class="alt-conv-btn" data-range="0">All time</button>
            </div>
            <div class="alt-chart-box"><canvas id="alt-chart-conversion" aria-label="Announced-to-verified conversion by announcement month"></canvas></div>
            <span class="alt-chart-btns"><button type="button" class="alt-chart-dl" data-dl="alt-chart-conversion" data-kind="png" aria-label="Download chart as image" title="Download PNG"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button><button type="button" class="alt-chart-dl" data-dl="alt-chart-conversion" data-kind="csv" aria-label="Download data as CSV" title="Download CSV"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg></button></span>
            <p class="alt-muted" id="alt-conversion-note" style="display:none"></p>
        </div>
    </details>
    <details class="alt-methodology">
        <summary>Which countries are in which region tab?</summary>
        <div class="alt-method-body" id="alt-region-defs">
            <p>The region tabs are views over the worldwide data. The full country list for each tab loads here.</p>
        </div>
    </details>

    <?php /* OPEN BY DEFAULT, and it stays a <details> only so a reader who has
             read it once can fold it away. It is the long-form answer to the
             question a reporter arrives with, and it was measured at 4px wide
             on a rendered page because it defaulted shut. The short version
             above it is not collapsible at all. */ ?>
    <details class="alt-methodology" open>
        <summary>Why our numbers differ from other trackers</summary>
        <div class="alt-method-body">
            <p><b>Every tracker measures a different thing, so the numbers should differ.</b> We count <em>verified entries</em>: cuts with a filing or named-outlet source behind them, each one clickable. The big announcement trackers count <em>corporate intentions</em>. Neither is wrong; they answer different questions. Our total sits below the headline announcement estimates, and the gap is fully explainable, here is exactly why, and why we treat it as a feature, not a shortfall.</p>

            <p><b>1 &middot; They book multi-year plans on day one; we count cuts as they happen.</b> When a company announces "20,000 cuts over two years," the announcement trackers record all 20,000 that day. We add each cut as its WARN notice or SEC filing actually appears. Over a year that is a large, permanent gap, their figure is a forecast, ours is an execution ledger.</p>

            <p><b>2 &middot; They include separations that name no employer.</b> Announcement totals fold in voluntary buyouts, deferred resignations, and attrition programs, including large federal-workforce reductions that file no WARN notice and name no company. In 2025 that was roughly <b>250,000 to 300,000 jobs</b> of the announcement total alone. There is no document or named source to link, so we do not claim it.</p>

            <p><b>3 &middot; They count cuts no outlet ever named.</b> Announcement surveys aggregate press mentions and estimates we cannot reproduce. We only publish what traces to a source, so an unsourced cut never enters our total.</p>

            <?php /* PARAGRAPH 4 IS THE MONTH-TO-MONTH RECONCILIATION, and it is
                     the one a reader arrives holding: our figure for a month
                     against the US national survey's figure for the same month,
                     two different totals, and the assumption that one of us is
                     wrong.

                     THE DEFAULT MOVED, AND THIS PARAGRAPH MOVED WITH IT. It
                     used to argue FOR the effective date as the default ("that
                     is what a worker lives through"), which contradicted the
                     control the moment the default became the filing date. The
                     effective-date reasoning is not deleted; it is the second
                     half, stated as the real question it answers, one click
                     away. What this revision adds is the comparison itself: say
                     what the survey is counting, say what we are counting, name
                     BOTH toggle options in the exact words printed on the
                     buttons, and say what stands behind our rows. A reader who
                     is told only that "you can recount on either basis" has been
                     told a control exists somewhere.

                     STANDING RULE: the survey's publisher is never named, here
                     or anywhere in this repo. "The US national survey" is the
                     approved framing, and railway/published_figures.py checks
                     that this explainer is present and open on the live page.

                     Anchored so the hero's "Why two figures" link lands here. */ ?>
            <p id="alt-basis-explainer"><b>4 &middot; We count each cut on the day it was filed, and you can recount it on the day it takes effect.</b> Layoffs are reported nearly everywhere on the filing date. The US national survey counts announcements made during a month. Our default counts each cut on the day its notice was filed or the cut was announced, which is the same question. So the figure at the top of this page is dated the way a national estimate for the same month is dated. The two are worth setting side by side. They are not the same measurement. We count only cuts with a filing or a named report behind them. A national survey also counts federal job cuts, buyout offers and employer estimates that never produce a public document. So in any given month our total can land above or below theirs. The effective date answers a different and equally real question: when the jobs actually ended. That is what a worker lives through, and what a labour-market reader often wants. Neither basis is the true one. <b>When it was filed</b> is the default, and the one that lines up with the survey. Set &ldquo;Count Layoffs By&rdquo; to <b>When it takes effect</b> and every figure, chart and table here is recounted on it. The gap between the two is not noise. A notice filed in May for a July closing sits in May on the default and in July on the other. In any given month the two totals can differ widely. The line under the headline figure shows how they split. On either basis, every row we count has a filing or a named report behind it.</p>
            <p><b>The bottom line, stated plainly.</b> Our verified figure is a <em>documented floor</em>. It is smaller than the estimates, but every single number clicks through to a legal filing or a named report. We deliberately do <b>not</b> pad it to match a headline estimate. A number a journalist can verify is worth more than a bigger one they cannot. That holds on the measure this tracker exists for too, <b>layoffs companies attribute to AI</b>. Compared like for like against an announcement survey's AI figure, ours is <em>much smaller</em>, and we would rather say so than pick the widest slice we have. A survey codes a reason from what an employer reports to it. We require the employer's own words, with the source behind them. So what we offer there is not a bigger number. It is that every attribution can be read back to the sentence the employer actually said.</p>

            <p><b>Where we lead, and where we don't, stated honestly.</b> Because our figure is built from receipts, it is not always smaller. Measured like-for-like against the public trackers by category:</p>
            <ul class="alt-method-list">
                <li><b>Against WARN-only aggregators</b> (the legally-filed US floor), we come out <em>higher</em>. We import the same WARN notices, then add SEC filings and named-news reports on top. Our US verified total clears the WARN floor rather than stopping at it.</li>
                <li><b>Against tech-event trackers</b>, our worldwide technology job-cut total is <em>at or above</em> the largest of them by volume. We carry fewer tiny private-startup events, but more total tech job losses. We catch the big filed cuts they sometimes miss.</li>
                <li><b>On AI attribution</b>, we run <em>lower</em> than an announcement survey's AI figure, and that is the one place readers most expect us to claim otherwise. A survey codes a reason from what an employer reports to it privately. We require a quote we can show you. So we only ever hold the subset that was said in public. Our broader AI-linked tier is wider than our strict one, and neither is a claim to have found more AI-driven cuts than a survey counted.</li>
                <li><b>Against announcement surveys' all-industry total</b>, we run <em>lower</em>, on purpose: the gap is receiptless cuts (federal-workforce reductions, buyouts, attrition, and small closings that file nothing). We do not claim what we cannot source.</li>
                <li><b>On coverage no one else offers</b>, we are the only one of these measuring the <em>global, all-industry, source-linked</em> universe. Everyone else is US-only, tech-only, or a survey.</li>
            </ul>

            <p><b>Where each kind of tracker fits:</b></p>
            <ul class="alt-method-list">
                <li><b>Announcement surveys</b>, monthly totals of <em>announced</em> US cuts from press reports and company statements, including estimates and multi-year plans. Typically published as press releases; no per-layoff public database.</li>
                <li><b>Editorial newsroom trackers</b>, selected major announcements with newsroom verification. No downloadable dataset; selective by design.</li>
                <li><b>Sector trackers</b>, technology-focused trackers built from announcements and crowdsourced reports. Their scope matches our <em>Technology</em> filter, not our all-industry total.</li>
                <li><b>Official statistics</b>, <a href="https://www.bls.gov/jlt/" target="_blank" rel="noopener">US BLS JOLTS</a>, <a href="https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/redundancies" target="_blank" rel="noopener">UK ONS</a>, <a href="https://ec.europa.eu/eurostat" target="_blank" rel="noopener">Eurostat</a> count <em>all</em> separations economy-wide (millions/month) with no company detail. A different universe entirely.</li>
                <li><b>This tracker</b>, verified entries in the headline, announcement-stage figures in a separate labeled tier, corrections logged openly, data and code public. When our number differs, the difference is definitional, and both definitions are stated here so either can be cited correctly.</li>
            </ul>
        </div>
    </details>

    <details class="alt-methodology">
        <summary>Known gaps &amp; why the country count changes</summary>
        <div class="alt-method-body">
            <p>The full directory of every pipeline, the SEC, all state WARN registries with live links, Eurofound ERM, and the news index, lives on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data Sources page</a>. The disclosures below cover what is <em>not</em> yet included.</p>
            <p><b>Why the country count grows over time.</b> The number of countries is not a setting we can raise; it reflects where large, press-covered layoffs have actually happened in our window. GDELT already searches every country on earth in 65+ languages, so a country appears the moment a credible outlet there covers a qualifying layoff. As layoffs occur and as we add more trusted local outlets, the count rises on its own. This is honest by design: we show the countries where verifiable layoffs exist, not a padded list.</p>
            <p><b>Known gaps, stated plainly.</b> We do not yet operate direct connectors for Canada SEDAR+, UK RNS, ASX, TDnet/EDINET, NSE/BSE, HKEXnews, SGXNet, SENS, DART or TASE. We maintain them as official-source research candidates. We will name one as live only after a stable public interface, tests and source-health monitoring exist for it. A few countries also publish official per-company redundancy records we do not ingest yet, including Belgium's FPS Employment collective-dismissal reports, Italy's weekly CIGS decree lists, and Sweden's varsel statistics. Most countries, including Germany and Mexico, treat employer identity in redundancy filings as confidential, so press coverage through GDELT in local languages is the primary source there. Layoffs too small for any press coverage, any WARN threshold, or the ERM threshold of 100 jobs will not appear in any tracker, including this one.</p>
        </div>
    </details>

    <details class="alt-methodology" id="alt-corrections" open>
        <summary>Data notes &amp; corrections log</summary>
        <div class="alt-method-body">
            <p class="alt-corrections-framing">Corrections are dated and described here, newest first, and corrected rows carry <code>edited: true</code> in the API. Nothing is quietly edited. Each entry has its own anchor link, so a correction can be cited by URL.</p>
            <?php
            // Provenance is computed from the entries' own recorded text
            // (alt_corrections_provenance): an entry with no explicit origin
            // marker is reported as unrecorded, never assigned one.
            $alt_prov = function_exists('alt_corrections_provenance') ? alt_corrections_provenance() : null;
            if (is_array($alt_prov) && (int) $alt_prov['entries'] > 0) : ?>
            <p class="alt-corrections-provenance">Origin, computed from the log entries themselves.
            Of the <?php echo number_format((int) $alt_prov['entries']); ?> machine-written entries below,
            <?php echo number_format((int) $alt_prov['internal']); ?> name an internal audit or automated
            check as the trigger. Another <?php echo number_format((int) $alt_prov['external']); ?> name an external
            report. The remaining <?php echo number_format((int) $alt_prov['unrecorded']); ?> do not record an origin,
            so they are counted as unrecorded, not assigned one.</p>
            <?php endif; ?>
            <p>For reproducible monitoring, the machine-readable <a href="<?php echo esc_url(rest_url('layoffs/v1/quality-status')); ?>">quality status endpoint</a> reports dataset revision, recent corrections, collector health, retained-source integrity and the status of each coverage workstream. Pending work is shown as pending, not silently treated as coverage.</p>
            <ul class="alt-corrections-scroll">
                <?php
                // The log renders from the actual audit trail: every /edit and
                // /trash appends to alt_corrections_log, so nothing can be
                // corrected without being disclosed. Newest first.
                //
                // Per-entry anchors (Keep a Changelog: entries should be
                // linkable; a journalist citing a correction needs a URL to
                // the entry, not to the page). Numbered on the APPEND-ordered
                // array, so an entry's anchor never shifts when later
                // corrections land on the same date.
                $alt_corr = get_option('alt_corrections_log');
                $alt_corr = is_array($alt_corr) ? $alt_corr : array();
                $alt_log_seq = array();
                $alt_log_items = array();
                foreach ($alt_corr as $c) {
                    $alt_ld = preg_replace('/[^0-9-]/', '', (string) ($c['date'] ?? ''));
                    if ($alt_ld === '') $alt_ld = 'undated';
                    $alt_log_seq[$alt_ld] = isset($alt_log_seq[$alt_ld]) ? $alt_log_seq[$alt_ld] + 1 : 1;
                    $c['anchor'] = 'log-' . $alt_ld . '-' . $alt_log_seq[$alt_ld];
                    $alt_log_items[] = $c;
                }
                foreach (array_reverse($alt_log_items) as $c) : ?>
                <li id="<?php echo esc_attr($c['anchor']); ?>"><b><?php echo esc_html($c['date']); ?>: <?php echo (int) $c['count']; ?> entr<?php echo ((int) $c['count'] === 1) ? 'y' : 'ies'; ?> <?php echo esc_html($c['action']); ?><?php echo $c['detail'] ? ' (' . esc_html($c['detail']) . ')' : ''; ?>.</b> <?php echo esc_html($c['reason']); ?> <a class="alt-log-anchor" href="#<?php echo esc_attr($c['anchor']); ?>" aria-label="Link to this correction">#</a></li>
                <?php endforeach; ?>
                <li id="log-2026-07-15-s1"><b>2026-07-15: Florida test rows removed, 87,600 jobs.</b> Florida's official WARN export contains internal test entries, which are fictitious notices sharing one WARN number and using non-existent zip codes. Eight such rows were removed, the largest a fake 78,788-worker "AT&amp;T" notice that briefly ranked as our biggest entry. Our importer now skips test-named rows, and each removed row is permanently blocked from re-import. <a class="alt-log-anchor" href="#log-2026-07-15-s1" aria-label="Link to this correction">#</a></li>
                <li id="log-2026-07-15-s2"><b>2026-07-15: Country assigned to 88 news and SEC entries.</b> These rows had no country recorded, which hid them from the regional views and country charts, though they were always in the worldwide totals. Each was resolved from its own source article. The largest were Oracle (30,000, spanning the US, India, Canada, Mexico and Uruguay, so "Multiple countries") and BBC (2,000, United Kingdom). <a class="alt-log-anchor" href="#log-2026-07-15-s2" aria-label="Link to this correction">#</a></li>
                <li id="log-2026-07-15-s3"><b>2026-07-15: Ideal US Talent Systems RI corrected from 9,891 to 2.</b> The Rhode Island notice states the company-wide figure, but only 2 RI employees are affected. The per-state filings for DC, GA, IL and VA are already separate entries. Counting the company-wide total under RI double-counted the layoff. <a class="alt-log-anchor" href="#log-2026-07-15-s3" aria-label="Link to this correction">#</a></li>
                <li id="log-2026-07-15-s4"><b>2026-07-15: Ten non-layoffs removed.</b> These were SEC-filing extraction mistakes. Some were severance dollar figures and job-cut percentages misread as headcounts. Some were WARN Act boilerplate clauses from acquisition agreements. Three were duplicate rows of one Meta story carrying wrong dates. <a class="alt-log-anchor" href="#log-2026-07-15-s4" aria-label="Link to this correction">#</a></li>
            </ul>
            <p>Spotted something off? Every entry links to its primary source so you can check us. Send corrections through the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a> and they get priority.</p>
        </div>
    </details>
    </section>

    <div class="alt-cite-box" id="alt-cite-box">
        <span class="alt-detail-h">Cite this tracker</span>
        <?php // The access date is SERVER-RENDERED. It used to be JavaScript-only,
              // so every crawler and every answer engine read "Accessed ." -- a
              // citation with no date, on the one product whose selling point is
              // traceability. The URL was missing outright. layoffs.js still
              // overwrites the date with the reader's own, which is more accurate
              // for a human and no longer load-bearing for anyone else. ?>
        <code id="alt-cite-text">AI Layoff Tracker, AskTheRecruiter.com. Accessed <span id="alt-cite-date"><?php echo esc_html(wp_date('M j, Y')); ?></span>. <?php echo esc_html(home_url('/ai-layoff-tracker/')); ?> Data from SEC EDGAR 8-K filings, US state WARN notices, and credible news outlets. Licensed CC BY 4.0.</code>
        <button type="button" class="alt-btn alt-btn-sm" id="alt-cite-copy">Copy</button>
    </div>

    <?php
    // The facet mesh had no on-site entry point. 103 indexable country, state
    // and industry pages shipped at 2.19.243 reachable only from a company page
    // or the sitemap, which is most of an internal-linking structure missing
    // the part that makes it one: links from the page that has the authority.
    //
    // alt_facet_index() already returns ONLY what clears
    // alt_facet_indexable_floor(), so this cannot link a noindex page, and it
    // reads alt_facet_counts() -- one memoised 6-hour transient keyed on
    // alt_data_ver, not a query per value. The counts shown are therefore the
    // same numbers the destination prints, including the strict job-location
    // basis the country pages use and explain.
    $alt_browse = function_exists('alt_facet_index') ? alt_facet_index() : array();
    if ($alt_browse) :
        $alt_browse_groups = array();
        foreach ($alt_browse as $alt_f) { $alt_browse_groups[$alt_f['dim']][] = $alt_f; }
        $alt_browse_labels = array(
            'country'  => 'By country',
            'state'    => 'By US state',
            'industry' => 'By industry',
        );
    ?>
    <section class="alt-browse" aria-labelledby="alt-browse-title">
        <h2 id="alt-browse-title" class="alt-browse-title">Browse the record</h2>
        <p class="alt-browse-intro">Every page below lists the source-linked entries behind its own figure. Counts are entries, not jobs.</p>
        <?php foreach ($alt_browse_labels as $alt_dim => $alt_label) :
            if (empty($alt_browse_groups[$alt_dim])) continue; ?>
            <div class="alt-browse-group">
                <h3 class="alt-browse-heading"><?php echo esc_html($alt_label); ?></h3>
                <ul class="alt-browse-list">
                <?php foreach ($alt_browse_groups[$alt_dim] as $alt_f) : ?>
                    <li><a href="<?php echo esc_url($alt_f['url']); ?>"><?php
                        echo esc_html($alt_f['display']); ?><span class="alt-browse-n"><?php
                        echo esc_html(number_format((int) $alt_f['events'])); ?></span></a></li>
                <?php endforeach; ?>
                </ul>
            </div>
        <?php endforeach; ?>
        <?php
        // THE SAME GAP THIS SECTION WAS BUILT TO CLOSE, one dimension over.
        // 2.19.243 shipped 103 facet pages reachable only from a sitemap and
        // the note above fixed it. Measured on the live site 2026-08-19, the
        // employer set had the identical defect and never got the identical
        // fix: of the 7,500 indexable company pages, 5,961 were linked from no
        // page on this site, and this page linked to none of them at all.
        //
        // A-Z rather than a list of employers: 7,500 will not render, and any
        // shortlist would be an editorial pick of whose page gets the link.
        // The letters are the whole set, evenly, in 27 links. Counts are the
        // real per-letter counts, from the same transient the index renders.
        $alt_emp_counts = function_exists('alt_company_index_counts') ? alt_company_index_counts() : array();
        if (array_sum($alt_emp_counts) > 0) : ?>
            <div class="alt-browse-group">
                <h3 class="alt-browse-heading">By employer</h3>
                <ul class="alt-browse-list alt-browse-letters">
                <?php foreach (alt_company_index_buckets() as $alt_b) :
                    $alt_bn = (int) ($alt_emp_counts[$alt_b] ?? 0);
                    if ($alt_bn === 0) continue; ?>
                    <li><a href="<?php echo esc_url(alt_company_index_url($alt_b)); ?>"><?php
                        echo esc_html($alt_b === '0-9' ? '0-9' : strtoupper($alt_b)); ?><span class="alt-browse-n"><?php
                        echo esc_html(number_format($alt_bn)); ?></span></a></li>
                <?php endforeach; ?>
                </ul>
                <p class="alt-browse-note"><a href="<?php echo esc_url(alt_company_index_url()); ?>">All
                <?php echo esc_html(number_format(array_sum($alt_emp_counts))); ?> employers, A to Z</a></p>
            </div>
        <?php endif; ?>
    </section>
    <?php endif; ?>

    <div class="alt-journalist">
        <div class="alt-journalist-text">
            <strong>Built for journalists &amp; researchers</strong>
            <p>Free to use with attribution to <strong>asktherecruiter.com</strong>. Every figure links to a primary source. Query the full dataset live through our API, and reach the editors at <a href="<?php echo esc_url(home_url('/contact/')); ?>">our contact page</a>, where corrections get priority.</p>
        </div>
        <code class="alt-journalist-api"><?php echo esc_html('GET ' . wp_make_link_relative($alt_api)); ?></code>
    </div>

    <?php // Shared digest signup (one subscriber list for both trackers; see includes/subscribe.php).
    if (function_exists('alt_digest_subscribe_form')) echo alt_digest_subscribe_form('layoff'); ?>

    <footer class="alt-provenance" aria-label="Tracker provenance">
        <span>Tracker release <b>v<?php echo esc_html(ALT_VERSION); ?></b></span>
        <span id="alt-provenance-quality" aria-live="polite">Dataset status loading…</span>
        <a class="alt-method-link" href="#alt-metric-definitions">Methodology</a>
        <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit and soundbites</a>
    </footer>
</div>
