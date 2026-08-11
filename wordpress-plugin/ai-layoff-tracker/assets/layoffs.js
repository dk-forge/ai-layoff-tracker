/**
 * AI Layoff Tracker — front-end (server-side).
 *
 * Everything is driven by three REST endpoints so the browser never loads the
 * whole dataset (it scales to 100K+ rows):
 *   query      one page of filtered rows, ordered and paged by the SERVER
 *   aggregate  filtered totals, top-N, monthly series, reason breakdown, leaders
 *   facets     distinct industry/country/state + date range (dropdowns + period)
 *
 * Filters, the period selector, and chart clicks all set the same controls and
 * then re-fetch query + aggregate, so the results list, charts, and headline
 * numbers move together.
 *
 * The results list is cards, not a table, and it holds exactly one page of
 * them at a time. No third-party table library is involved: /query already
 * does the ORDER BY and the LIMIT/OFFSET, so sorting orders all 63,000 events
 * and the browser never renders more than one page of cards.
 *
 * First paint: the tracker template inlines the default-filter responses for
 * all three endpoints as window.ALT_BOOTSTRAP (computed server-side by the
 * same endpoint callbacks), so an unfiltered first load renders with zero
 * REST round-trips; see takeBoot() below. Filter changes always fetch live.
 */
(function () {
    'use strict';

    if (typeof window.altData === 'undefined') return;
    var API = window.altData.apiUrl; // ends with .../layoffs/v1/

    /* ------------------------------------------------------------------ */
    /* Palette + labels                                                    */
    /* ------------------------------------------------------------------ */

    // THE CHARTS READ THEIR COLOURS FROM THE STYLESHEET.
    //
    // A canvas does not inherit CSS, so every colour Chart.js and d3 paint
    // with used to be a literal sitting right here. That is the exact thing
    // that leaves a chart light-on-light when the page goes dark. These
    // values are now read from the same custom properties layoffs.css
    // defines, at draw time, through tok() below.
    //
    // The vars stay `var` and stay module-scoped because ~40 call sites read
    // them; readTheme() reassigns them, and every renderer is called again
    // afterwards. Nothing caches a colour past a repaint: mountChart()
    // destroys and rebuilds the chart, and cloneOptions() deep-clones
    // baseChartOptions at call time, so the fresh values are picked up.
    var CSS_ROOT = null;
    function tok(name, fallback) {
        if (!CSS_ROOT) {
            CSS_ROOT = window.getComputedStyle(document.documentElement);
        }
        var v = CSS_ROOT.getPropertyValue('--alt-' + name);
        v = v ? v.trim() : '';
        return v || fallback;
    }

    // Okabe-Ito colorblind-safe palette, ordered so neighbors differ in
    // lightness as well as hue (yellow excluded: too weak on white for lines).
    // The four that carry meaning on this page (verified, AI-attributed,
    // announced, accent) are themed; the rest are hues that read on either
    // ground and stay fixed so series identity survives a theme switch.
    var PALETTE = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9', '#000000', '#999999'];
    var ALT_RED, ALT_AMBER, SEQ_BLUE, SEQ_BLUE_FILL, INK, CHART_DIM, TIP;
    var MAP_BLUE, MAP_BLUE_LINE, MAP_RED, MAP_RED_LINE, MAP_LAND, MAP_LAND_LINE;
    var MAP_HATCH, MAP_HATCH_LINE, MAP_LABEL, MAP_LABEL_HALO, MAP_PLATE;

    function readTheme() {
        CSS_ROOT = null;                       // drop the stale computed style
        ALT_RED = tok('ai', '#D55E00');
        ALT_AMBER = tok('announced', '#E69F00');
        SEQ_BLUE = tok('blue', '#2a78d6');
        SEQ_BLUE_FILL = 'rgba(' + tok('heat-rgb', '42, 120, 214') + ', 0.18)';
        CHART_DIM = tok('chart-dim', '#d6d8de');
        INK = {
            primary: tok('chart-ink', '#0b0b0b'),
            secondary: tok('chart-ink-2', '#52514e'),
            muted: tok('chart-muted', '#898781'),
            grid: tok('chart-grid', '#e1e0d9')
        };
        TIP = {
            bg: tok('chart-tip-bg', '#0b0b0b'),
            title: tok('chart-tip-ink', '#fff'),
            body: tok('chart-tip-body', '#e1e0d9')
        };
        PALETTE[0] = tok('verified', '#0072B2');
        PALETTE[1] = tok('ai', '#D55E00');
        PALETTE[4] = tok('announced', '#E69F00');
        MAP_BLUE = tok('map-blue', 'rgba(47, 111, 208, 0.52)');
        MAP_BLUE_LINE = tok('map-blue-line', 'rgba(28, 92, 171, 0.95)');
        MAP_RED = tok('map-red', 'rgba(208, 67, 26, 0.85)');
        MAP_RED_LINE = tok('map-red-line', 'rgba(150, 38, 10, 0.95)');
        MAP_LAND = tok('map-land', '#eef1f5');
        MAP_LAND_LINE = tok('map-land-line', '#d3d8e0');
        MAP_HATCH = tok('map-hatch', '#eceef3');
        MAP_HATCH_LINE = tok('map-hatch-line', '#b6bac6');
        MAP_LABEL = tok('map-label', '#0b0b0b');
        MAP_LABEL_HALO = tok('map-label-halo', '#fff');
        MAP_PLATE = tok('chart-plate', '#fff');
        if (window.Chart) {
            // Global, and NOT part of the options clone, so it has to be
            // re-applied on every repaint rather than only at boot.
            window.Chart.defaults.color = INK.muted;
            window.Chart.defaults.borderColor = INK.grid;
        }
    }
    readTheme();

    // Unemployment-claims backdrop (BLS/DOL via /claims). Macro CONTEXT only —
    // rendered on its OWN right-side axis, never summed with layoff counts.
    var CLAIMS_DATA = null;

    var REASON_LABELS = {
        /*
          THESE ARE REASON TAGS, AND THEY USED TO WEAR THE TILES' NAMES.

          "AI: company-stated (specific)" and "AI-linked (broad)" are the
          labels on the two AI stat tiles, which are counted from the
          ai_explicit / ai_causation flag columns. These two are reason TAGS,
          counted from reason_tags, and they are different quantities: on
          2026-08-04 the tag read 10,415 where the tile read 124,793. One name
          over two numbers on one page is not a labelling nicety, it is a
          reader adding up figures that were never the same measure.
        */
        ai_automation: 'Reason tag: AI or automation', possible_ai: 'Reason tag: AI press-linked',
        revenue_decline: 'Revenue decline', restructuring: 'Restructuring',
        merger_acquisition: 'Merger / acquisition', offshoring: 'Offshoring',
        product_discontinuation: 'Product discontinued', cost_reduction: 'Cost reduction',
        macroeconomic: 'Macroeconomic', closure: 'Plant / site closure',
        bankruptcy: 'Bankruptcy / insolvency', federal_workforce: 'Government / public sector'
    };
    var VERIF_LABELS = { gold: 'SEC filing', warn: 'WARN notice', silver: 'Press release', bronze: 'News' };
    // Mirrors alt_role_categories() (api.php); used by the Roles filter chip.
    var ROLE_LABELS = {
        engineering: 'Engineering & IT', product_design: 'Product & design',
        customer_support: 'Customer support & success', sales_marketing: 'Sales & marketing',
        hr_recruiting: 'HR & recruiting', operations_warehouse: 'Operations & warehouse',
        content_trust_safety: 'Content & trust and safety', finance_admin: 'Finance & admin',
        manufacturing: 'Manufacturing & production', retail_staff: 'Retail staff'
    };
    // /aggregate returns top_roles keyed by LABEL (db.php builds it from
    // alt_role_categories()), but the Roles filter sends slugs — so a tap on a
    // role bar has to translate back. Derived, never hand-kept in step.
    var ROLE_SLUG_BY_LABEL = {};
    Object.keys(ROLE_LABELS).forEach(function (k) { ROLE_SLUG_BY_LABEL[ROLE_LABELS[k]] = k; });
    // Declared here (not next to the chart that draws them) because the
    // active-filter chip table below needs them at definition time.
    var SOURCE_TYPE_LABELS = { warn: 'WARN notices', news: 'News reports', sec: 'SEC filings', '8K': 'SEC 8-K filings',
        erm: 'Eurofound ERM', press_release: 'Company releases', federal_rif: 'US federal RIFs (OPM)', seed: 'Curated (sourced)' };
    // The `sources` param deliberately accepts BOTH vocabularies (verification
    // tier from the dropdown, source_type from the "By data source" chart —
    // db.php matches either column), so the chip label map has to cover both.
    var SOURCE_FILTER_LABELS = {};
    Object.keys(VERIF_LABELS).forEach(function (k) { SOURCE_FILTER_LABELS[k] = VERIF_LABELS[k]; });
    Object.keys(SOURCE_TYPE_LABELS).forEach(function (k) {
        if (!SOURCE_FILTER_LABELS[k]) SOURCE_FILTER_LABELS[k] = SOURCE_TYPE_LABELS[k];
    });
    var AI_CAUSATION_LABELS = {
        primary_cause: 'AI primary cause', contributing_cause: 'AI contributing cause',
        selection_or_operations: 'AI used in selection / operations', context_only: 'AI context only',
        explicitly_denied: 'AI explicitly denied', unknown: 'AI classification pending'
    };
    var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // A WARN link is either the EXACT notice (states like VT publish per-notice
    // pages) or the state's official WARN list page (the notice is a row in
    // it). Label the difference honestly instead of implying precision.
    function warnLinkIsExact(row) {
        if (row.source_type !== 'warn') return true;
        var url = String(row.source_url || '');
        // Per-notice URLs carry a record id / document path; landing pages don't.
        // Note .pdf may sit INSIDE a query string (WA fortress serves the notice
        // as DownloadFile.aspx?file=<guid>.pdf&download=1), so match .pdf before
        // & as well as ? / end, plus the file-download shapes states actually use.
        return /\/\d+\/?$|\.pdf($|[?&])|downloadfile|[?&]file=|record|lookups\/\d/i.test(url);
    }
    // The row's official state WARN list page (derived fresh from its state).
    function warnListUrl(row) {
        if (row.source_type !== 'warn') return '';
        return safeUrl(row.source_list_url);
    }
    // Resolve a WARN row to what actually renders:
    //   exact notice  -> primary = the notice, secondary = the state list
    //   list-only      -> one link, preferring the FRESH derived list over a
    //                     possibly-stale stored source_url (WA moved its DB page).
    // This also means a stored source_url that has since gone stale self-heals
    // on the list-only path without needing a re-import.
    function warnLinks(row) {
        var stored = safeUrl(row.source_url);
        var list = warnListUrl(row);
        if (warnLinkIsExact(row)) {
            return { primary: stored, list: (list && list !== stored) ? list : '', exact: true };
        }
        return { primary: list || stored, list: '', exact: false };
    }

    /* ------------------------------------------------------------------ */
    /* Helpers                                                             */
    /* ------------------------------------------------------------------ */

    function escapeHtml(v) {
        return String(v == null ? '' : v)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    function fmt(n) { return Number(n || 0).toLocaleString('en-US'); }
    // Axis-label form. "2,000,000" is seven characters and on a card ~190px
    // wide two of those columns leave almost nothing for the plot. Used only
    // where a value is a scale marker, never where it is a figure being quoted:
    // tooltips, stats and captions keep the exact number.
    // The default numeric y-axis formatter, named so mountChart() can
    // recognise it and swap it for the compact form in a narrow card. A
    // chart that set its own callback (the percent axes) is left alone.
    function fmtAxis(v) { return fmt(v); }
    // Is this canvas in a card too narrow for full-length axis labels?
    // A clientWidth of 0 means the element is not laid out yet (a card inside a
    // closed <details>, a first paint before layout) and is NOT a narrow card;
    // reading it as one would ship abbreviated labels to a desktop. It falls
    // back to the viewport, which is what the stylesheet's own one-column
    // breakpoint keys on.
    function narrowChartBox(canvas) {
        var w = (canvas && canvas.parentNode) ? canvas.parentNode.clientWidth : 0;
        if (w > 0) return w < 420;
        return window.innerWidth > 0 && window.innerWidth <= 560;
    }
    function fmtCompact(n) {
        var v = Number(n || 0);
        if (v >= 1000000) return (Math.round(v / 100000) / 10) + 'M';
        if (v >= 1000) return (Math.round(v / 100) / 10) + 'k';
        return fmt(Math.round(v));
    }
    function safeUrl(url) {
        url = String(url == null ? '' : url).trim();
        return /^https?:\/\//i.test(url) ? url : '';
    }
    // Permanent receipt for California WARN rows. CA's per-row source_url is the
    // ROLLING recent-processed xlsx, which drops a notice within weeks (verified:
    // Meta's 2026-07-22 filings, processed in May, are gone from it). But CA also
    // publishes a PERMANENT cumulative PDF per fiscal year that DOES list the
    // notice (Meta is on page 19 of the FY2025-26 report), keyed by NOTICE date
    // (July 1 to June 30). This maps a notice date to that permanent PDF so a CA
    // row links to a document that actually contains it. The current fiscal year
    // has no PDF until it closes (~mid the following year), so recent notices
    // fall back to the live file. Filenames are irregular, hence an explicit map.
    var CA_WARN_FY_PDF = {
        2019: 'warn-report-for-7-1-2019-to-6-30-2020.pdf',
        2020: 'warn-report-for-7-1-2020-to-06-30-2021.pdf',
        2021: 'warn-report-for-7-1-2021-to-06-30-2022.pdf',
        2022: 'warn-report-for-7-1-2022-to-06-30-2023.pdf',
        2023: 'warn-report-for-7-1-2023-to-06-30-2024.pdf',
        2024: 'warn-report-for-7-1-2024-to-06-30-2025.pdf',
        2025: 'warn-report-for-7-1-25-to-6-30-26.pdf'
    };
    function caWarnPdfUrl(dateStr) {
        var m = /^(\d{4})-(\d{2})/.exec(String(dateStr || ''));
        if (!m) return '';
        var y = parseInt(m[1], 10), mo = parseInt(m[2], 10);
        var fy = mo >= 7 ? y : y - 1;   // CA fiscal year starts July 1
        return CA_WARN_FY_PDF[fy]
            ? 'https://edd.ca.gov/siteassets/files/jobs_and_training/warn/' + CA_WARN_FY_PDF[fy]
            : '';
    }
    // Permanent Internet Archive (Wayback) snapshot of the row's source, when
    // the backfill has captured one. The API attaches `archived_url` only for a
    // resolved snapshot, so this returns '' (no link) whenever an archive is
    // still pending or unavailable — never a broken or guessed link. The second
    // link sits alongside the official source on every row that has one.
    function archivedUrl(row) { return safeUrl(row && row.archived_url); }
    function hasSourceUrl(row) { return row && typeof row.source_url === 'string' && row.source_url.indexOf('http') === 0; }
    // Last-checked date (YYYY-MM-DD) for the transparency disclaimer.
    function archiveCheckedDate(row) {
        var c = row && row.archive_checked_at ? String(row.archive_checked_at) : '';
        return c ? c.slice(0, 10) : '';
    }
    // Mirror of the server's archive re-check cadence (db.php
    // ALT_ARCHIVE_RETRY_HOURS / ALT_ARCHIVE_RECHECK_DAYS / ALT_ARCHIVE_DAILY_RUN_UTC,
    // themselves pinned to the archive-backfill cron). One promise, two
    // renderers; railway/tests/test_archive_promise.py asserts these constants
    // stay equal to the PHP ones.
    var ARCHIVE_RETRY_HOURS = 72, ARCHIVE_RECHECK_DAYS = 7, ARCHIVE_RUN_UTC = [5, 25];
    // The REAL date (UTC, YYYY-MM-DD) of the next automatic archive attempt for
    // this row's source, derived from its recorded state + the cron schedule —
    // never a typed promise. Queued rows are picked up by the next daily run;
    // 'pending' retries after the spacing window; 'unavailable' re-checks weekly.
    function archiveNextCheckDate(row) {
        var status = row && row.archive_status ? String(row.archive_status) : 'queued';
        var raw = row && row.archive_checked_at ? String(row.archive_checked_at) : '';
        var checked = raw ? Date.parse(raw.replace(' ', 'T') + 'Z') : NaN;
        var eligible = Date.now();
        if (!isNaN(checked)) {
            if (status === 'pending') eligible = checked + ARCHIVE_RETRY_HOURS * 3600000;
            else if (status === 'unavailable') eligible = checked + ARCHIVE_RECHECK_DAYS * 86400000;
        }
        if (eligible < Date.now()) eligible = Date.now();
        var d = new Date(eligible);
        var run = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), ARCHIVE_RUN_UTC[0], ARCHIVE_RUN_UTC[1], 0);
        if (run < eligible) run += 86400000;
        return new Date(run).toISOString().slice(0, 10);
    }
    // Every row with a source URL shows EITHER a permanent Wayback link OR a
    // truthful, dated "archive pending" disclaimer — never a silent gap. The
    // backfill re-checks the Internet Archive weekly and adds the link the moment
    // a snapshot exists, so the disclaimer is honest about state, not a dead end.
    function archivePendingTitle(row) {
        var d = archiveCheckedDate(row);
        return 'No permanent Internet Archive (Wayback) copy exists yet. We re-check '
            + 'automatically every week and add the archived copy the moment the '
            + 'Internet Archive captures this source. Next check by ' + archiveNextCheckDate(row) + '.'
            + (d ? ' Last checked ' + d + '.' : '');
    }
    // The archived copy on a result card: always a SECOND link, never instead
    // of the publisher's own. Wording, separator and tone match the sibling
    // talent tracker (`archived`, after a middot, in the quieter ink) so the
    // two products say the same thing the same way. What is ours and not the
    // sibling's is the pending state: a row whose source has not been captured
    // yet says so and says when it was last checked, rather than showing
    // nothing and leaving a reader to guess whether we simply did not bother.
    function archivedCellLink(row) {
        var a = archivedUrl(row);
        if (a) return '<span class="alt-archived"> · <a href="' + escapeHtml(a) + '" target="_blank" rel="noopener nofollow" class="alt-muted" title="A copy saved by the Internet Archive, for when the publisher’s own page has moved or gone">archived</a></span>';
        if (hasSourceUrl(row)) return '<span class="alt-archived"> · <span class="alt-muted" title="' + escapeHtml(archivePendingTitle(row)) + '">archive pending</span></span>';
        return '';
    }
    // archivedDetailLink removed 2026-07-28: superseded by archiveCell (F28).
    // v2.19.208 — the row-detail Source block is now separate labelled rows
    // (primary source / source list / archived copy) instead of one dot-joined
    // run-on line, so a reader sees at a glance which link is which.
    function srcRow(label, valueHtml) {
        return '<div class="alt-src-row"><span class="alt-src-label">' + escapeHtml(label)
            + '</span><span class="alt-src-val">' + valueHtml + '</span></div>';
    }
    // Archived-copy cell: the permanent Wayback link, or an HONEST pending note.
    // Pending is truthful — the backfill re-checks 'pending' URLs on every run
    // (and 'unavailable' ones weekly, forever), so it really does get captured.
    function archiveCell(row) {
        var a = archivedUrl(row);
        if (a) return '<a href="' + escapeHtml(a) + '" target="_blank" rel="noopener nofollow" title="Permanent Internet Archive (Wayback Machine) snapshot, in case the official source moves or is taken down">Wayback Machine snapshot ↗</a>';
        if (hasSourceUrl(row)) {
            var d = archiveCheckedDate(row);
            return '<span class="alt-muted">No archive snapshot yet. We re-check weekly; next check by '
                + escapeHtml(archiveNextCheckDate(row)) + '.'
                + (d ? ' Last checked ' + escapeHtml(d) + '.' : '') + '</span>';
        }
        // WARN rows without an article URL still show the official state list
        // link as their source, so a bare "No web source" directly under a
        // working link read as false (F29). Name the real situation instead.
        return '<span class="alt-muted">Source is the official state register (linked above); no separate article URL to archive.</span>';
    }
    function setText(id, text) { var el = document.getElementById(id); if (el) el.textContent = text; }
    function setStatus(id, text, isError) {
        var el = document.getElementById(id);
        if (!el) return;
        if (text === null) { el.style.display = 'none'; return; }
        el.style.display = ''; el.textContent = text;
        el.classList.toggle('alt-status-error', !!isError);
    }

    /* Loading / loaded / failed --------------------------------------------
       THREE STATES, AND THE THIRD ONE IS THE POINT. The owner reported the
       page looking frozen while a filter change was in flight: the old
       behaviour left the previous numbers on screen, fully styled, looking
       final, for as long as the host took to answer. So every async surface
       now says out loud that it is working.

       The rule this file has hit repeatedly is that a mechanism which looks
       alive while doing nothing is worse than one that visibly stops. An
       indicator that spins forever is exactly that defect, so busyTrack()
       carries its own deadline: when the promise has neither resolved nor
       rejected by LOAD_TIMEOUT_MS the region lands in the FAILED state with a
       retry, and the fetch behind it is aborted rather than left running.

       Accessibility is wired two ways on purpose, because the two answer
       different questions. aria-busy on the region tells a screen reader that
       what it can see is stale. The overlay is role="status", so its text is
       announced politely on entry and again when it changes to the failure
       copy. Neither is decorative, and neither depends on the spinner, which
       prefers-reduced-motion removes (see .alt-load-spin in layoffs.css).

       Layout does not move. The overlay is absolutely positioned inside the
       region, so it takes no flow space, and busyBegin freezes the region's
       current height as a min-height for the duration, so a region that was
       empty on first paint does not jump when its rows arrive. */
    var LOAD_TIMEOUT_MS = 20000;
    var LOAD_MIN_H = 132;      // floor for a region that is empty on first paint
    var BUSY = {};             // region id -> { token, el, overlay, timer, ctrl }
    var BUSY_TOKEN = 0;

    function busyOverlay(el) {
        var node = document.createElement('div');
        node.className = 'alt-load';
        node.setAttribute('role', 'status');
        node.innerHTML = '<span class="alt-load-spin" aria-hidden="true"></span>'
            + '<span class="alt-load-msg"></span>'
            + '<button type="button" class="alt-load-retry" hidden>Try again</button>';
        el.appendChild(node);
        return node;
    }

    // Begin. Idempotent per region: a second call while busy re-uses the
    // overlay (and its reserved height) rather than stacking two of them.
    function busyBegin(id, label) {
        var el = document.getElementById(id);
        if (!el) return null;
        var st = BUSY[id];
        if (!st || !st.overlay || !st.overlay.parentNode) {
            el.classList.add('alt-load-host');
            var reserved = Math.max(el.offsetHeight || 0, LOAD_MIN_H);
            el.style.minHeight = reserved + 'px';
            st = BUSY[id] = { el: el, overlay: busyOverlay(el), timer: null, ctrl: null };
        }
        st.token = ++BUSY_TOKEN;
        el.setAttribute('aria-busy', 'true');
        st.overlay.classList.remove('alt-load-failed');
        st.overlay.querySelector('.alt-load-msg').textContent = label || 'Loading';
        st.overlay.querySelector('.alt-load-retry').hidden = true;
        return st;
    }

    function busyClear(id) {
        var st = BUSY[id];
        if (!st) return;
        if (st.timer) clearTimeout(st.timer);
        if (st.overlay && st.overlay.parentNode) st.overlay.parentNode.removeChild(st.overlay);
        st.el.classList.remove('alt-load-host');
        st.el.setAttribute('aria-busy', 'false');
        // Release the reserved height only after the browser has painted the
        // content that replaced it, so the region never collapses and reflows.
        var el = st.el;
        (window.requestAnimationFrame || setTimeout)(function () { el.style.minHeight = ''; });
        delete BUSY[id];
    }

    // Failed. The region stops claiming to be working (aria-busy false), the
    // copy says so, and the retry button is the way out. No timer survives.
    function busyFail(id, message, retry) {
        var st = BUSY[id];
        if (!st) st = busyBegin(id, message);
        if (!st) return;
        if (st.timer) { clearTimeout(st.timer); st.timer = null; }
        // Retire the token. A response that arrives after we gave up belongs to
        // a request the region no longer holds, and it must not clear an error
        // the reader is currently looking at (or paint data behind their back).
        st.token = ++BUSY_TOKEN;
        st.el.setAttribute('aria-busy', 'false');
        st.overlay.classList.add('alt-load-failed');
        st.overlay.querySelector('.alt-load-msg').textContent = message;
        var btn = st.overlay.querySelector('.alt-load-retry');
        btn.hidden = !retry;
        btn.onclick = retry ? function () { busyClear(id); retry(); } : null;
    }

    // Wrap one in-flight promise in the three states. `make` receives an
    // AbortSignal so the deadline can stop the request it gave up on.
    //
    // `companions` are regions painted by the SAME call, given as [id, label]
    // pairs. They have to be here rather than managed by the caller, because a
    // caller can only move them from the promise's own then/catch, and a
    // promise that never settles never runs either. That is exactly what the
    // deadline exists for, and it is not hypothetical: the first shipped
    // version drove the chart grid from the aggregate call's catch, and a
    // stalled fetch left the tiles correctly in the failed state with the chart
    // grid spinning underneath them forever. Measured on the live 2.20.8 page.
    // One deadline now moves every region it started.
    function busyTrack(id, label, make, retry, companions) {
        companions = companions || [];
        var st = busyBegin(id, label);
        if (!st) return make(null);
        companions.forEach(function (c) { busyBegin(c[0], c[1]); });
        var token = st.token;
        var ctrl = null;
        try { ctrl = new AbortController(); } catch (e) { ctrl = null; }
        st.ctrl = ctrl;
        var live = function () { return BUSY[id] && BUSY[id].token === token; };
        var all = function (fn) { fn(id); companions.forEach(function (c) { fn(c[0]); }); };
        st.timer = setTimeout(function () {
            if (!live()) return;
            if (ctrl) { try { ctrl.abort(); } catch (e) { /* already settled */ } }
            all(function (r) { busyFail(r, 'This is taking longer than usual.', retry); });
        }, LOAD_TIMEOUT_MS);
        return make(ctrl ? ctrl.signal : null).then(function (value) {
            if (live()) all(busyClear);
            return value;
        }, function (err) {
            if (live()) all(function (r) { busyFail(r, 'We could not load this data.', retry); });
            throw err;
        });
    }

    // The concise result-summary links point to native disclosure panels.
    // Open the destination before the browser scrolls to it so keyboard,
    // mouse and direct fragment-link visitors all reach readable content.
    function revealMethodologyHash() {
        var id = window.location.hash ? decodeURIComponent(window.location.hash.slice(1)) : '';
        if (!id) return;
        var target = document.getElementById(id);
        if (target && target.tagName === 'DETAILS') target.open = true;
    }
    function initMethodologyAnchors() {
        document.querySelectorAll('.alt-method-link').forEach(function (link) {
            link.addEventListener('click', function () {
                var id = (link.getAttribute('href') || '').replace(/^#/, '');
                var target = id ? document.getElementById(id) : null;
                if (target && target.tagName === 'DETAILS') target.open = true;
            });
        });
        revealMethodologyHash();
        window.addEventListener('hashchange', revealMethodologyHash);
    }
    function monthLabel(key) {
        var p = key.split('-');
        return MONTHS[parseInt(p[1], 10) - 1] + ' ' + p[0];
    }
    function chartsAvailable() { return typeof window.Chart !== 'undefined'; }
    function paletteFor(entries) { return entries.map(function (_, i) { return PALETTE[i % PALETTE.length]; }); }

    /* API access ------------------------------------------------------- */

    function qs(obj) {
        return Object.keys(obj || {}).map(function (k) {
            return encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]);
        }).join('&');
    }
    // `signal` is optional and comes from busyTrack's deadline: an abandoned
    // request is cancelled rather than left in flight behind an error state.
    function apiGet(path, params, signal) {
        var url = API + path;
        var q = qs(params);
        if (q) url += (url.indexOf('?') > -1 ? '&' : '?') + q;
        var opts = { credentials: 'same-origin' };
        if (signal) opts.signal = signal;
        return fetch(url, opts).then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        });
    }

    // Server-inlined first-load payloads (window.ALT_BOOTSTRAP, emitted by
    // page-tracker.php from the same PHP callbacks the REST endpoints run).
    // Each REST round-trip costs ~1.2s of WordPress boot on this host, so the
    // default first paint uses these instead of fetching. Every piece is used
    // AT MOST ONCE, and only when the request the page was about to make
    // matches the params the server computed it for — deep links, saved
    // session filters and year rollover all mismatch and fall back to a
    // normal fetch, so the bootstrap can never show numbers the API wouldn't.
    var BOOT = window.ALT_BOOTSTRAP || null;
    function bootParamsMatch(want, have) {
        var kw = Object.keys(want || {}), kh = Object.keys(have || {});
        if (kw.length !== kh.length) return false;
        return kw.every(function (k) {
            return Object.prototype.hasOwnProperty.call(have, k) && String(want[k]) === String(have[k]);
        });
    }
    function takeBoot(kind, params) {
        if (!BOOT || !BOOT[kind]) return null;
        if (!bootParamsMatch(params || {}, BOOT[kind + '_params'] || {})) return null;
        var data = BOOT[kind];
        BOOT[kind] = null; // one shot: everything after first load fetches live
        return data;
    }

    function renderSourceHealth() {
        var box = document.getElementById('alt-source-health');
        var note = document.getElementById('alt-source-health-note');
        if (!box || !note) return;
        apiGet('source-health', {}).then(function (health) {
            var names = Object.keys(health || {}).sort();
            box.textContent = '';
            if (!names.length) {
                note.textContent = 'No collector status has been received yet. This is a setup state, not evidence of zero layoffs.';
                return;
            }
            note.textContent = 'Latest autonomous collector attempts.';
            var table = document.createElement('table');
            var head = document.createElement('thead');
            head.innerHTML = '<tr><th>Source</th><th>Status</th><th>Documents</th><th>Checked</th></tr>';
            table.appendChild(head);
            var body = document.createElement('tbody');
            names.forEach(function (name) {
                var item = health[name] || {};
                var tr = document.createElement('tr');
                var label = item.status === 'ok' ? 'Healthy' : (item.status === 'running' ? 'Running' : 'Degraded');
                [name, label, fmt(item.entries), item.checked_at ? new Date(item.checked_at).toLocaleString() : '—'].forEach(function (value) {
                    var td = document.createElement('td'); td.textContent = value; tr.appendChild(td);
                });
                tr.className = item.status === 'ok' ? 'alt-source-ok' : (item.status === 'running' ? 'alt-source-running' : 'alt-source-degraded');
                body.appendChild(tr);
            });
            table.appendChild(body); box.appendChild(table);
        }).catch(function () {
            note.textContent = 'Live source status is temporarily unavailable; the dataset itself remains available through the tracker and API.';
        });
    }

    // This is deliberately a small live pointer to the existing public
    // quality endpoint, rather than a locally cached or inferred timestamp.
    function renderProvenance() {
        var el = document.getElementById('alt-provenance-quality');
        if (!el) return;
        apiGet('quality-status', {}).then(function (status) {
            var revision = Number(status && status.dataset_revision);
            var checked = status && status.generated_at ? new Date(status.generated_at) : null;
            var revisionText = Number.isFinite(revision) && revision > 0
                ? 'Dataset revision ' + fmt(revision)
                : 'Dataset revision unavailable';
            var checkedText = checked && !isNaN(checked.getTime())
                ? 'status checked ' + checked.toLocaleString()
                : 'status check time unavailable';
            el.textContent = revisionText + ' · ' + checkedText;
        }).catch(function () {
            el.textContent = 'Live dataset status temporarily unavailable';
        });
    }

    /* Chart registry --------------------------------------------------- */

    var CHARTS = {};
    function mountChart(canvasId, config) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        // Expanded cards re-render through here (the expand toggle calls
        // renderCharts), so scale type up for readability at full width:
        // Chart.js grows the canvas but keeps fonts fixed otherwise.
        if (canvas.closest && canvas.closest('.alt-expanded')) {
            var o = config.options = config.options || {};
            var scales = o.scales || {};
            [scales.x, scales.y].forEach(function (ax) {
                if (ax && ax.ticks) ax.ticks.font = { size: 15 };
            });
            o.plugins = o.plugins || {};
            o.plugins.legend = o.plugins.legend || {};
            o.plugins.legend.labels = Object.assign({}, o.plugins.legend.labels,
                { font: { size: 14 }, boxWidth: 16 });
            if (o.plugins.tooltip) {
                o.plugins.tooltip.titleFont = { size: 15 };
                o.plugins.tooltip.bodyFont = { size: 14 };
            }
        }
        // NUMERIC Y LABELS GO COMPACT IN A NARROW CARD, and this is a
        // correctness fix rather than a taste one. Chart.js caps how much of a
        // small canvas an axis may claim, and a label wider than the cap is
        // simply DRAWN PAST THE CANVAS EDGE rather than shrunk or wrapped. At
        // 375px this page's cards are ~177px wide, the cap works out at ~44px,
        // and "200,000" needs ~47px, so the trend card's left axis rendered as
        // "0,000" and "0,000" with the leading digits gone. Nothing errors and
        // nothing overflows a DOM box, so only looking at it finds it.
        // Only the default formatter is swapped; a chart that set its own
        // callback (the percent axes) keeps it, and the expanded card is wide
        // enough that the swap never applies there.
        var narrowBox = narrowChartBox(canvas);
        if (narrowBox && config.options && config.options.scales) {
            ['y', 'y1'].forEach(function (id) {
                var ax = config.options.scales[id];
                if (ax && ax.ticks && ax.ticks.callback === fmtAxis) ax.ticks.callback = fmtCompact;
            });
        }
        // Time-axis labels: compact cards show exactly three anchors —
        // earliest, middle, latest — so the span reads at a glance and the
        // latest month is always present; the expanded view shows every
        // label, rotated vertical. Line charts only (bar lists need all
        // their category names).
        var xlabels = (config.data && config.data.labels) || [];
        if (config.type === 'line' && xlabels.length > 8) {
            var xo = config.options = config.options || {};
            xo.scales = xo.scales || {};
            xo.scales.x = xo.scales.x || {};
            var tx = xo.scales.x.ticks = Object.assign({}, xo.scales.x.ticks);
            if (canvas.closest && canvas.closest('.alt-expanded')) {
                tx.autoSkip = xlabels.length > 40;
                tx.maxTicksLimit = 40;
                tx.minRotation = 60;
                tx.maxRotation = 90;
                delete tx.callback;
            } else {
                tx.autoSkip = false;
                tx.maxRotation = 0;
                var lastIdx = xlabels.length - 1, midIdx = Math.floor(lastIdx / 2);
                tx.callback = function (val, idx) {
                    return (idx === 0 || idx === lastIdx || idx === midIdx) ? xlabels[idx] : '';
                };
            }
        }
        if (CHARTS[canvasId]) { CHARTS[canvasId].destroy(); delete CHARTS[canvasId]; }
        CHARTS[canvasId] = new Chart(canvas, config);
        return CHARTS[canvasId];
    }
    function clearChart(canvasId) {
        if (CHARTS[canvasId]) { CHARTS[canvasId].destroy(); delete CHARTS[canvasId]; }
    }

    var baseChartOptions = {
        responsive: true, maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: { backgroundColor: TIP.bg, titleColor: TIP.title, bodyColor: TIP.body, padding: 10, displayColors: false }
        },
        scales: {
            x: { grid: { display: false }, ticks: { color: INK.muted, maxRotation: 0, autoSkip: true } },
            y: { beginAtZero: true, grid: { color: INK.grid }, ticks: { color: INK.muted, callback: function (v) { return fmt(v); } } }
        }
    };
    function cloneOptions() {
        var o = JSON.parse(JSON.stringify(baseChartOptions));
        o.scales.y.ticks.callback = fmtAxis;
        return o;
    }

    /* ------------------------------------------------------------------ */
    /* Filter controls                                                     */
    /* ------------------------------------------------------------------ */

    var FILTER_STORAGE_KEY = 'altTrackerFilters:v2';
    var FILTER_IDS = ['alt-search', 'alt-f-from', 'alt-f-to', 'alt-f-years', 'alt-f-quarters',
        'alt-f-months', 'alt-f-industry', 'alt-f-country', 'alt-f-state', 'alt-f-reasons', 'alt-f-roles',
        'alt-f-verification', 'alt-f-company', 'alt-f-keyword', 'alt-f-minjobs', 'alt-f-ai', 'alt-f-ai-broad', 'alt-f-announced'];

    function readControl(id) {
        var el = document.getElementById(id);
        if (!el) return null;
        if (el.type === 'checkbox') return el.checked;
        if (el.multiple) return Array.prototype.slice.call(el.selectedOptions).map(function (o) { return o.value; });
        return el.value;
    }
    function writeControl(id, value) {
        var el = document.getElementById(id);
        if (!el || value == null) return;
        if (el.type === 'checkbox') { el.checked = !!value; return; }
        if (el.multiple && Array.isArray(value)) {
            Array.prototype.forEach.call(el.options, function (o) { o.selected = value.indexOf(o.value) !== -1; });
            return;
        }
        el.value = value;
    }
    function saveFilters() {
        try {
            var s = {}; FILTER_IDS.forEach(function (id) { s[id] = readControl(id); });
            window.sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(s));
        } catch (e) { /* private mode */ }
    }
    function restoreFilters() {
        try {
            var raw = window.sessionStorage.getItem(FILTER_STORAGE_KEY);
            if (!raw) return;
            var s = JSON.parse(raw);
            FILTER_IDS.forEach(function (id) { writeControl(id, s[id]); });
        } catch (e) { /* corrupt */ }
    }
    // Shared links and widgets can open the full tracker with the exact
    // public filter scope. URL parameters intentionally win over a visitor's
    // locally saved exploratory filters.
    function restoreFiltersFromUrl() {
        var query = new URLSearchParams(window.location.search);
        var mappings = {
            years: 'alt-f-years', quarters: 'alt-f-quarters', months: 'alt-f-months',
            industry: 'alt-f-industry', country: 'alt-f-country', state: 'alt-f-state',
            sources: 'alt-f-verification', reasons: 'alt-f-reasons', roles: 'alt-f-roles'
        };
        // Label lookups for values a shared link may carry that the dropdown has
        // no option for — a source_type from the "By data source" chart, or a
        // country that only ever appears as an employer HQ. writeControl matches
        // on existing options, so without this the filter would silently vanish
        // for the recipient and the link would not mean what the sender saw.
        var URL_VALUE_LABELS = { sources: SOURCE_FILTER_LABELS, reasons: REASON_LABELS, roles: ROLE_LABELS };
        Object.keys(mappings).forEach(function (key) {
            if (!query.has(key)) return;
            var vals = query.get(key).split(',').filter(Boolean);
            var labels = URL_VALUE_LABELS[key];
            vals.forEach(function (v) { ensureOption(mappings[key], v, (labels && labels[v]) || v); });
            writeControl(mappings[key], vals);
        });
        [['from', 'alt-f-from'], ['to', 'alt-f-to'], ['q', 'alt-search'], ['company', 'alt-f-company'],
         ['keyword', 'alt-f-keyword'], ['min_jobs', 'alt-f-minjobs']].forEach(function (pair) {
            if (query.has(pair[0])) writeControl(pair[1], query.get(pair[0]));
        });
        if (query.get('ai') === '1') writeControl('alt-f-ai', true);
        // ai_broad has its OWN control now. It used to be written into the
        // Reasons multi-select as `possible_ai`, which made an inbound broad
        // link look like a reason-tag selection and, worse, made every
        // reason-tag selection of that slice silently become a broad-AI
        // filter. The two are different columns and different totals.
        if (query.get('ai_broad') === '1') writeControl('alt-f-ai-broad', true);
        if (query.get('stage') === 'announced') writeControl('alt-f-announced', true);
        // date_basis was WRITE-only: every share URL carried it, nothing read it
        // back, so a "notice date" link silently reverted the recipient to the
        // effective-date basis while looking like it carried the setting — and
        // the two bases produce different numbers.
        //
        // BOTH values are read now, not just the non-default one. When the
        // default was 'effective' a link saying date_basis=effective was
        // indistinguishable from a link saying nothing, so reading only
        // 'notice' happened to work. The default is 'notice' now, and a link
        // that explicitly asks for the effective basis has to be honoured or
        // every effective-basis share silently becomes a filed-basis view.
        var urlBasis = query.get('date_basis');
        if (urlBasis === 'notice' || urlBasis === 'effective') setDateBasis(urlBasis);
    }
    function clearFilters() {
        FILTER_IDS.forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) return;
            if (el.type === 'checkbox') el.checked = false;
            else if (el.multiple) Array.prototype.forEach.call(el.options, function (o) { o.selected = false; });
            else el.value = '';
        });
        try { window.sessionStorage.removeItem(FILTER_STORAGE_KEY); } catch (e) { /* noop */ }
    }

    // Current filter state → REST query params. Multi-selects send comma lists.
    function multiParam(id) {
        var v = readControl(id);
        if (Array.isArray(v)) return v.length ? v.join(',') : '';
        return v || '';
    }

    /*
      THE DATE BASIS, AND WHY THE DEFAULT IS THE FILING DATE.

      'notice' counts each cut on the day it was filed or announced
      (COALESCE(announcement_date, layoff_date) server-side, so no row is ever
      dropped for lacking a filing date). 'effective' counts it on the day the
      jobs end.

      The default was 'effective' and is now 'notice'. The reason is not that
      one basis is more true: it is that the filing basis is the one every
      other published layoff figure is counted on, so a reader arriving with a
      number in their head can reconcile ours against it in one step. On the
      filing basis, US July 2026 reads within about one percent of the
      independent national estimate for the same month. On the effective basis
      the same month reads roughly double, and a correct number that needs a
      paragraph before it can be compared gets read as a wrong one.

      The effective basis is NOT demoted out of existence. It answers a real
      and different question, when the jobs actually ended, it is one click
      away in the toolbar, and every figure on the page recomputes on it.

      Anything that renders a total reads BASIS_COPY rather than writing the
      words itself, so a total and its basis label cannot drift apart.
    */
    var DATE_BASIS = 'notice';
    var BASIS_COPY = {
        notice: {
            // Goes straight into the hero label after the geography and period.
            headline: 'counted by filing date',
            // The (i) body on the Verified job cuts tile. Names ONE basis. It
            // used to name both ("Filed or reported, counted on the day each
            // cut takes effect"), which was wrong on whichever basis was live.
            tile: 'Counted on the day each cut was filed or announced. This is the basis layoffs are reported on elsewhere, so this figure compares directly. Every row behind it links to its source.',
            // The switch itself, so the active option states the question it
            // answers rather than only naming a date.
            toggleTitle: 'Counts each layoff on the day its notice was filed or the cut was announced. This is the basis layoffs are reported on elsewhere, so our figure compares directly. This is the default.'
        },
        effective: {
            headline: 'counted by effective date',
            tile: 'Counted on the day the jobs actually end. This answers when the work stopped, rather than when it was reported. Every row behind it links to its source.',
            toggleTitle: 'Counts each layoff on the day the cut takes effect, the day the jobs actually end. A different question from the filing basis, and equally real.'
        }
    };
    function basisCopy() { return BASIS_COPY[DATE_BASIS] || BASIS_COPY.notice; }

    // One writer for the basis state: the closure variable, the segmented
    // switch's visual and aria state, and every caption that names the basis.
    // Three callers (URL restore, the toggle click, init) used to do parts of
    // this by hand, which is how a caption ends up naming a basis that is not
    // the one being counted.
    function setDateBasis(basis) {
        DATE_BASIS = (basis === 'effective') ? 'effective' : 'notice';
        document.querySelectorAll('.alt-datebasis-opt').forEach(function (x) {
            var on = (x.getAttribute('data-basis') === 'notice' ? 'notice' : 'effective') === DATE_BASIS;
            x.classList.toggle('alt-datebasis-on', on);
            x.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
        renderBasisCopy();
    }

    // Every caption that names the basis, rewritten from BASIS_COPY. Called on
    // every basis change and on every stats render, so a caption can never
    // survive a toggle while describing the other basis.
    function renderBasisCopy() {
        var c = basisCopy();
        setText('alt-hero-total-basis', c.headline);
        setText('alt-stat-total-basis', c.headline);
        setText('alt-citeline-basis', c.headline);
        var tileBody = document.getElementById('alt-stat-total-i-body');
        if (tileBody) tileBody.textContent = c.tile;
        document.querySelectorAll('.alt-datebasis-opt').forEach(function (x) {
            var key = x.getAttribute('data-basis') === 'notice' ? 'notice' : 'effective';
            x.setAttribute('title', BASIS_COPY[key].toggleTitle);
        });
    }
    function currentParams() {
        var p = {};
        var v;
        if ((v = readControl('alt-f-from'))) p.from = v;
        if ((v = readControl('alt-f-to'))) p.to = v;
        if ((v = multiParam('alt-f-years'))) p.years = v;
        if ((v = multiParam('alt-f-quarters'))) p.quarters = v;
        if ((v = multiParam('alt-f-months'))) p.months = v;
        if ((v = multiParam('alt-f-industry'))) p.industry = v;
        if ((v = multiParam('alt-f-country'))) p.country = v;
        if ((v = multiParam('alt-f-state'))) p.state = v;
        /*
          A REASON FILTER FILTERS BY REASON TAG. All of them, including the two
          AI ones.

          This used to translate `possible_ai` to ai_broad=1 and `ai_automation`
          to ai=1, so that picking a reason reproduced the AI stat cards
          exactly. It made the destination match the card and left the thing
          you clicked lying about where it went: the doughnut drew the
          possible_ai slice at 10,415 and tapping it returned 124,793, a
          twelvefold jump with nothing on screen explaining it. The broad
          measure now has its own control (alt-f-ai-broad), which is a
          removable chip like every other filter, so both quantities stay
          reachable and neither borrows the other's number.
        */
        if ((v = multiParam('alt-f-reasons'))) p.reasons = v;
        if ((v = multiParam('alt-f-roles'))) p.roles = v;
        if ((v = multiParam('alt-f-verification'))) p.sources = v;
        if ((v = (readControl('alt-search') || '').trim())) p.q = v;
        if ((v = (readControl('alt-f-company') || '').trim())) p.company = v;
        if ((v = (readControl('alt-f-keyword') || '').trim())) p.keyword = v;
        var mj = parseInt(readControl('alt-f-minjobs'), 10);
        if (!isNaN(mj) && mj > 0) p.min_jobs = mj;
        if (readControl('alt-f-ai')) p.ai = '1';
        if (readControl('alt-f-ai-broad')) p.ai_broad = '1';
        if (readControl('alt-f-announced')) p.stage = 'announced';
        // ALWAYS explicit, on both bases. This param feeds the API request AND
        // (through syncUrlFromFilters) the address bar, so writing it only for
        // the non-default value made a shared URL mean "whatever the default is
        // on the day you open it". The default has now changed once; a link
        // shared before this line was added would have silently changed basis.
        // Written last so the querystring reads scope-then-basis.
        p.date_basis = (DATE_BASIS === 'effective') ? 'effective' : 'notice';
        return p;
    }

    /* Cross-filter helpers --------------------------------------------- */

    function toggleSingleFilter(id, value) {
        var el = document.getElementById(id);
        if (!el) return false;
        el.value = (el.value === value) ? '' : value;
        return true;
    }
    function toggleMultiFilter(id, value) {
        var el = document.getElementById(id);
        if (!el) return false;
        if (id === 'alt-f-country') LAST_MULTI_DIM = 'country';
        var toggled = false;
        Array.prototype.forEach.call(el.options, function (o) {
            if (o.value === value) { o.selected = !o.selected; toggled = true; }
        });
        return toggled;
    }

    // A chart can legitimately show a value the matching dropdown has no option
    // for: /facets lists the location vocabularies only, and the "By data
    // source" chart speaks source_type (news/erm/press_release) while the
    // dropdown lists verification tiers. Both are accepted by the same `sources`
    // param server-side, so add the option rather than letting a tap silently
    // do nothing — the control then SHOWS the chart-applied filter, which is the
    // whole point of tap-to-filter (you can see why the page narrowed, and undo
    // it from the dropdown or the chip).
    function ensureOption(id, value, text) {
        var el = document.getElementById(id);
        if (!el || value === '' || value == null) return null;
        var has = Array.prototype.some.call(el.options, function (o) { return o.value === value; });
        if (!has) {
            var opt = document.createElement('option');
            opt.value = value;
            opt.textContent = text || value;
            el.appendChild(opt);
        }
        return el;
    }

    // Tapping a month on a time-series chart scopes the page to that month,
    // through the SAME Years/Months controls the dropdowns write — so the
    // dropdowns, the chips, the exports and the address bar all show it, and
    // the keyboard route to the identical state is those dropdowns. Tapping the
    // month that is already scoped drops the month and leaves the year, i.e. it
    // zooms back out one step rather than to all time (the year has its own
    // chip if you want that too). Quarters are left alone: the chart can only
    // ever draw months the current quarter filter already admits.
    function pickMonth(monthKey) {
        if (!monthKey || !/^\d{4}-\d{2}$/.test(monthKey)) return;
        var y = monthKey.slice(0, 4);
        var m = String(parseInt(monthKey.slice(5, 7), 10));
        var years = selectedList('alt-f-years');
        var months = selectedList('alt-f-months');
        var alreadyOn = years.length === 1 && years[0] === y && months.length === 1 && months[0] === m;
        if (alreadyOn) {
            writeControl('alt-f-months', []);
            return;
        }
        ensureOption('alt-f-years', y, y);
        writeControl('alt-f-years', [y]);
        writeControl('alt-f-months', [m]);
    }

    // Put the current view in the address bar so it can simply be copied.
    // Same querystring the per-card share buttons already build (currentParams),
    // and restoreFiltersFromUrl() reads it back on load, so a chart tap survives
    // being pasted to someone else. replaceState, not pushState: a history entry
    // per keystroke in the search box would bury the back button. The default
    // view (this year, nothing else) keeps a clean, param-free URL.
    // The querystring the DEFAULT view produces, so the default view keeps a
    // clean, param-free URL. currentParams() now always writes date_basis, so
    // the baseline has to carry it too or every unfiltered page load would
    // rewrite the address bar with a querystring that changes nothing.
    // qs() preserves insertion order and date_basis is written last.
    var URL_BASELINE = 'years=' + new Date().getFullYear() + '&date_basis=notice';
    function syncUrlFromFilters() {
        if (window.altData && window.altData.embedParams) return; // embed iframe: not a shareable view
        try {
            var q = qs(currentParams());
            history.replaceState(null, '',
                window.location.pathname + ((q && q !== URL_BASELINE) ? '?' + q : '') + window.location.hash);
        } catch (e) { /* a URL we cannot write is not worth failing the render for */ }
    }

    var DASH_PRESENT = false;
    var LAST_AGG = null;

    // Announced-vs-executed reconciliation, loaded once and keyed by a loose
    // company name so a row's detail panel can show the link between a company's
    // announcement (news/SEC) and its on-the-ground WARN executions.
    var RECON_MAP = {};
    function reconKey(name) {
        return String(name || '').toLowerCase()
            .replace(/\b(inc|corp|co|ltd|plc|llc|lp|group|holdings|the|sa|se|ag|nv|americas?|us|usa)\b/g, '')
            .replace(/[^a-z0-9]+/g, '').trim();
    }
    function loadReconciliation() {
        apiGet('reconciliation', {}).then(function (r) {
            (r && r.rows || []).forEach(function (row) {
                var k = reconKey(row.company);
                if (k) RECON_MAP[k] = row;
            });
        }).catch(function () { /* reconciliation is enrichment; never block the table */ });
    }

    function refreshAll() {
        saveFilters();
        syncUrlFromFilters();
        // Any filter change is a new result set, so it starts at page one.
        // Paging itself calls loadRows() directly and keeps its page.
        PAGE = 1;
        loadRows();
        fetchAndRenderAggregate();
        updateActiveFilterBar();
        updateQuickViewStates();
        updateDropdownSummaries();
        updateRangeLabel();
        updateExportLinks();
    }

    // The CSV/JSON buttons download exactly what's on screen: the current
    // filters ride along as query params and the label says which it is.
    function updateExportLinks() {
        if (!window.altData) return;
        // Export matches the on-screen table (inclusive country basis), so a
        // downloaded "United States" CSV includes US-HQ global cuts too.
        var ep = currentParams();
        if (ep.country) ep.country_basis = 'any';
        var qsStr = qs(ep);
        // The -top pair is the first-screen cite line's copy of the same
        // affordance; both must honor the live filters or a journalist's
        // download would not match the number beside it.
        [['alt-export-csv', window.altData.exportCsv, 'CSV'],
         ['alt-export-json', window.altData.exportJson, 'JSON'],
         ['alt-export-csv-top', window.altData.exportCsv, 'CSV'],
         ['alt-export-json-top', window.altData.exportJson, 'JSON']].forEach(function (p) {
            var a = document.getElementById(p[0]);
            if (!a) return;
            a.href = p[1] + (qsStr ? '&' + qsStr : '');
            var lbl = document.getElementById(p[0] + '-label');
            if (lbl) lbl.textContent = p[2] + (qsStr ? ' · filtered' : ' · all');
        });
    }

    var AGG_SEQ = 0;
    function fetchAndRenderAggregate() {
        if (!document.getElementById('alt-stats-bar') && !DASH_PRESENT) return;
        var seq = ++AGG_SEQ; // drop stale responses that resolve out of order
        var aggParams = (window.altData && window.altData.embedParams) || currentParams();
        var boot = takeBoot('aggregate', aggParams);
        if (boot) { LAST_AGG = boot; renderStats(boot.totals); renderCharts(boot); return; }
        // The tiles and the chart grid are two regions because they are two
        // places a reader looks; both are stale until this one call answers.
        // The grid rides along as a companion so that ONE deadline moves both.
        // Driving it from the catch below was the bug: a fetch that neither
        // resolves nor rejects never reaches a catch, so the tiles reported the
        // timeout honestly while the grid spun under them forever.
        busyTrack('alt-stats-bar', 'Loading the totals', function (signal) {
            return apiGet('aggregate', aggParams, signal);
        }, fetchAndRenderAggregate, [['alt-minigrid', 'Loading the charts']])
            .then(function (agg) {
                if (seq !== AGG_SEQ) return;
                LAST_AGG = agg;
                renderStats(agg.totals);
                renderCharts(agg);
            })
            .catch(function () {
                if (seq === AGG_SEQ) setStatus('alt-dashboard-status', 'Could not load chart data.', true);
            });
    }

    /* Active-filter chip bar ------------------------------------------- */

    var MONTH_MAP = {};
    MONTHS.forEach(function (m, i) { MONTH_MAP[String(i + 1)] = m; });
    var QUARTER_MAP = { '1': 'Q1', '2': 'Q2', '3': 'Q3', '4': 'Q4' };

    // Each dimension gets its own chip color so stacked cross-filters read at
    // a glance (year chips blue, industry green, country orange, ...).
    var ACTIVE_FILTER_DEFS = [
        { id: 'alt-search', label: 'Search', kind: 'single', color: 'ink' },
        { id: 'alt-f-years', label: 'Year', kind: 'multi', color: 'blue' },
        { id: 'alt-f-quarters', label: 'Quarter', kind: 'multi', map: QUARTER_MAP, color: 'teal' },
        { id: 'alt-f-months', label: 'Month', kind: 'multi', map: MONTH_MAP, color: 'violet' },
        { id: 'alt-f-industry', label: 'Industry', kind: 'multi', color: 'green' },
        { id: 'alt-f-country', label: 'Country', kind: 'multi', color: 'orange' },
        { id: 'alt-f-state', label: 'State', kind: 'multi', color: 'pink' },
        { id: 'alt-f-reasons', label: 'Reason', kind: 'multi', map: REASON_LABELS, color: 'slate' },
        { id: 'alt-f-roles', label: 'Role', kind: 'multi', map: ROLE_LABELS, color: 'teal' },
        { id: 'alt-f-verification', label: 'Source', kind: 'multi', map: SOURCE_FILTER_LABELS, color: 'gold' },
        // Company is what the "Largest single job cuts" and "Repeat layoffs"
        // charts write, so it needs a chip like every other chart-applied
        // filter — otherwise a tap narrowed the page with no visible ✕ to undo.
        { id: 'alt-f-company', label: 'Company', kind: 'single', color: 'blue' },
        { id: 'alt-f-ai', label: '', kind: 'bool', on: 'AI-attributed only', color: 'red' },
        // The broad AI measure is a filter of its own now, not a reason tag
        // wearing the tile's name. Chip so it is visible and removable.
        { id: 'alt-f-ai-broad', label: '', kind: 'bool', on: 'AI-linked, broad only', color: 'gold' },
        { id: 'alt-f-announced', label: '', kind: 'bool', on: 'Announced only', color: 'gold' }
    ];

    /* ------------------------------------------------------------------ */
    /* The Filters panel                                                   */
    /* ------------------------------------------------------------------ */

    /*
      ELEVEN DROPDOWNS BEHIND ONE BUTTON, and the button says how many are on.

      Only the controls that live INSIDE the panel are counted. Search, the
      region tabs, the date range, the date basis and sort stay outside it, so
      counting them would make "Filters (3)" point at a panel holding none of
      them. The values are read with readControl(), the same reader the chips
      use, so the count and the chips cannot disagree.
    */
    var PANEL_FILTER_IDS = ['alt-f-years', 'alt-f-quarters', 'alt-f-months',
        'alt-f-industry', 'alt-f-country', 'alt-f-state', 'alt-f-reasons',
        'alt-f-verification', 'alt-f-roles', 'alt-f-company', 'alt-f-keyword',
        'alt-f-minjobs'];

    function panelFilterCount() {
        var n = 0;
        PANEL_FILTER_IDS.forEach(function (id) {
            if (!document.getElementById(id)) return;
            var v = readControl(id);
            if (Array.isArray(v)) n += v.length;
            else if (v !== '' && v != null && v !== false) n += 1;
        });
        return n;
    }

    function updateFilterPanelCount() {
        var out = document.getElementById('alt-filters-count');
        if (!out) return;
        var n = panelFilterCount();
        out.textContent = n ? ' (' + n + ')' : '';
        var btn = document.getElementById('alt-filters-toggle');
        if (btn) btn.classList.toggle('alt-filterbar-toggle-on', n > 0);
    }

    function setFilterPanelOpen(open) {
        var body = document.getElementById('alt-filterbar-body');
        var btn = document.getElementById('alt-filters-toggle');
        if (!body || !btn) return;
        body.hidden = !open;
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    /*
      PROGRESSIVE ENHANCEMENT, in this order and not the other one.

      The panel ships OPEN and the toggle ships `hidden`, so a reader with no JS
      keeps all eleven controls exactly as before. This runs after
      restoreFilters()/restoreFiltersFromUrl(), so a deep-linked or remembered
      view that already has one of these filters set leaves the panel OPEN: the
      control that shaped the page is never the one we hide.
    */
    function initFilterPanel() {
        var body = document.getElementById('alt-filterbar-body');
        var btn = document.getElementById('alt-filters-toggle');
        if (!body || !btn) return;
        btn.hidden = false;
        // A years pill is set for everyone on first load (the page opens scoped
        // to this year), so it is not evidence the reader chose anything.
        var chosen = PANEL_FILTER_IDS.some(function (id) {
            if (id === 'alt-f-years') return false;
            if (!document.getElementById(id)) return false;
            var v = readControl(id);
            return Array.isArray(v) ? v.length > 0 : (v !== '' && v != null && v !== false);
        });
        setFilterPanelOpen(chosen);
        btn.addEventListener('click', function () {
            setFilterPanelOpen(btn.getAttribute('aria-expanded') !== 'true');
        });
        updateFilterPanelCount();
    }

    function updateActiveFilterBar() {
        updateFilterPanelCount();
        var bar = document.getElementById('alt-active-filters');
        if (!bar) return;
        var chips = [];
        ACTIVE_FILTER_DEFS.forEach(function (def) {
            var val = readControl(def.id);
            if (def.kind === 'bool') { if (val) chips.push({ id: def.id, text: def.on, value: true, kind: 'bool', color: def.color }); }
            else if (def.kind === 'multi') {
                // A "multi" control may actually be a single select on some pages.
                var vals = Array.isArray(val) ? val : (val ? [val] : []);
                var kind = Array.isArray(val) ? 'multi' : 'single';
                // A region tab's whole country set collapses to ONE chip
                // ("Region: Europe") — 31 per-country chips helped no one.
                if (def.id === 'alt-f-country' && vals.length > 1) {
                    var region = regionNameFor(vals);
                    if (region) { chips.push({ id: def.id, text: 'Region: ' + region, kind: 'region', color: def.color }); return; }
                }
                vals.forEach(function (v) {
                    chips.push({ id: def.id, text: def.label + ': ' + ((def.map && def.map[v]) || v), value: v, kind: kind, color: def.color });
                });
            } else if (val) { chips.push({ id: def.id, text: def.label + ': ' + val, value: val, kind: 'single', color: def.color }); }
        });
        if (!chips.length) { bar.innerHTML = ''; bar.style.display = 'none'; return; }
        bar.style.display = '';
        var html = '<span class="alt-af-label">Filtering:</span>';
        chips.forEach(function (c, i) {
            html += '<button type="button" class="alt-af-chip alt-af-' + (c.color || 'blue') + '" data-i="' + i + '">' + escapeHtml(c.text) + ' <span aria-hidden="true">✕</span></button>';
        });
        html += '<button type="button" class="alt-af-clear" id="alt-af-clear">Clear all</button>';
        bar.innerHTML = html;
        bar.querySelectorAll('.alt-af-chip').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var c = chips[parseInt(btn.getAttribute('data-i'), 10)];
                if (c.kind === 'bool') { var el = document.getElementById(c.id); if (el) el.checked = false; }
                else if (c.kind === 'region') writeControl(c.id, []); // ✕ on a region chip = back to world
                else if (c.kind === 'multi') toggleMultiFilter(c.id, c.value);
                else toggleSingleFilter(c.id, '');
                refreshAll();
            });
        });
        var clr = document.getElementById('alt-af-clear');
        if (clr) clr.addEventListener('click', function () { clearFilters(); writeControl('alt-f-years', [String(new Date().getFullYear())]); updateDropdownSummaries(); refreshAll(); });
    }

    /* ------------------------------------------------------------------ */
    /* Stats bar                                                           */
    /* ------------------------------------------------------------------ */

    // Always render in Eastern Time (the site's standard) with a live dynamic
    // date, e.g. "Jul 16, 9:32 AM EDT".
    function fmtET(iso) {
        var d = new Date(iso);
        if (isNaN(d.getTime())) return '';
        return d.toLocaleString('en-US', {
            timeZone: 'America/New_York', month: 'short', day: 'numeric',
            hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
        });
    }

    // Next scheduled data pull, so "updated" always has a forward-looking
    // companion. The hours come from altData.ingest, which the server reads
    // from data/ingest-schedule.json — generated from the REAL Railway cron
    // (railway/railway.toml) and drift-guarded by test_ingest_schedule.py.
    // Never typed here: without a schedule we show nothing rather than guess.
    function nextPullET() {
        var ing = window.altData && window.altData.ingest;
        var hours = ing && ing.utc_hours;
        if (!hours || !hours.length) return '';
        var minute = ing.utc_minute || 0;
        var now = new Date(), cands = [];
        for (var d = 0; d <= 1; d++) {
            hours.forEach(function (h) {
                var t = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + d, h, minute, 0));
                if (t > now) cands.push(t);
            });
        }
        cands.sort(function (a, b) { return a - b; });
        return cands.length ? fmtET(cands[0].toISOString()) : '';
    }

    function renderStatus(stats) {
        var liveEl = document.getElementById('alt-status-live');
        var workEl = document.getElementById('alt-status-working');
        var timeEl = document.getElementById('alt-live-time') || document.getElementById('alt-last-updated');
        if (timeEl && stats && stats.last_updated) {
            var when = fmtET(stats.last_updated);
            if (when) timeEl.textContent = (timeEl.id === 'alt-live-time') ? when : ('Updated ' + when);
        }
        var nextEl = document.getElementById('alt-next-pull');
        var np = nextPullET();
        // The first-screen cite line's dateline: server-rendered in UTC for
        // no-JS readers, refreshed here to a live Eastern-time reading.
        var topNext = document.getElementById('alt-next-top');
        if (topNext && np) topNext.textContent = 'Next update ' + np;
        if (!liveEl || !workEl) return;
        var phase = stats && stats.pipeline_phase;
        var roo = document.getElementById('alt-roo');
        var wrap = document.getElementById('alt-roo-wrap');
        if (phase === 'refreshing' || phase === 'cleaning') {
            // Roo wakes up (lights on) and the amber pill lights up beside him;
            // the "Live · updated" pill greys out until he's finished.
            var txt = document.getElementById('alt-work-text');
            if (txt) txt.textContent = (phase === 'cleaning')
                ? 'Roo is checking & de-duplicating the data'
                : 'Roo is pulling in new filings, notices & news';
            workEl.hidden = false;
            liveEl.classList.add('alt-status-dim');   // greyed while Roo works
            // SVG className is a read-only object — must use setAttribute.
            if (roo) roo.setAttribute('class', 'alt-roo ' + (phase === 'cleaning' ? 'roo-working-hard' : 'roo-working'));
            if (wrap) wrap.className = 'alt-roo-wrap is-working';
            if (nextEl) nextEl.textContent = np ? ('Next update ' + np) : '';
        } else {
            // All caught up: Roo falls asleep (greyscale + zzz), "Live" lights up.
            workEl.hidden = true;
            liveEl.classList.remove('alt-status-dim');
            if (roo) roo.setAttribute('class', 'alt-roo roo-sleeping');
            if (wrap) wrap.className = 'alt-roo-wrap is-sleeping';
            var lastTxt = (stats && stats.last_updated) ? fmtET(stats.last_updated) : '';
            if (nextEl) nextEl.textContent =
                (lastTxt ? ('Roo pulled the latest data ' + lastTxt + ', resting until ' + (np || 'the next run')) 
                         : (np ? ('Roo’s resting until the next update, ' + np) : ''));
        }
    }

    function initStatsMeta() {
        if (!document.getElementById('alt-live-time') && !document.getElementById('alt-last-updated')) return;
        // /status is public + uncached, so the badge flips to refreshing/
        // cleaning within one poll instead of waiting on the 5-min stats cache.
        var poll = function () { apiGet('status', { _: Date.now() }).then(renderStatus).catch(function () {}); };
        poll();
        // Every poll is an uncached origin hit; 3 min is plenty for a status
        // badge and cuts recurring load (the pipeline phase changes rarely).
        setInterval(poll, 180000);
    }

    function fmtDate(iso) {
        if (!iso || !/^\d{4}-\d{2}-\d{2}/.test(iso)) return '';
        var p = iso.split('-');
        return MONTHS[parseInt(p[1], 10) - 1] + ' ' + parseInt(p[2], 10) + ', ' + p[0];
    }

    // "in 2026" is technically right but slow to parse — when the selection is
    // exactly the current year, say "2026 YTD" instead.
    function statPeriodLabel() {
        var years = readControl('alt-f-years') || [];
        var bare = years.length === 1
            && !(readControl('alt-f-quarters') || []).length
            && !(readControl('alt-f-months') || []).length
            && !readControl('alt-f-from') && !readControl('alt-f-to');
        // NOT "<year> YTD". A year filter is the whole calendar year, and
        // because rows are dated by EFFECTIVE date it legitimately holds
        // notices filed for dates still ahead. The hero's as-of line splits
        // the window into what has taken effect and what has not; the stamp
        // just names the window. (Defect: the stamp said YTD over the whole
        // year while the page's own FAQ schema published the to-date figure.)
        if (bare && years[0] === String(new Date().getFullYear())) return years[0];
        var period = currentPeriodLabel();
        return period === 'all time' ? 'all time' : period.replace(/^in /, '');
    }

    // The scope suffix makes an active place/industry filter impossible to
    // miss right where the numbers are ("· United States"), so nobody reads a
    // filtered total as the global one.
    // A region tab can only select the subset of its countries that exist in
    // the dropdown (facets only list countries WITH data) — so every
    // "selection == tab" comparison must use that same intersection.
    function tabSelectableCountries(k) {
        var sel = document.getElementById('alt-f-country');
        var avail = {};
        if (sel) Array.prototype.forEach.call(sel.options, function (o) { avail[o.value] = 1; });
        return (REGION_TABS[k] ? REGION_TABS[k].countries : []).filter(function (c) { return avail[c]; });
    }
    function regionNameFor(selection) {
        var sel = selection.slice().sort().join('|'), named = '';
        Object.keys(REGION_TABS).forEach(function (k) {
            var t = REGION_TABS[k];
            if (!t.countries.length) return;
            if (tabSelectableCountries(k).sort().join('|') === sel) {
                named = t.label.replace(/^in (the )?/, '');
                named = named.charAt(0).toUpperCase() + named.slice(1);
            }
        });
        return named;
    }

    // The PLACE half of the scope, on its own, because the hero label needs a
    // geography and "worldwide · announced only" is not one. Splitting it here
    // keeps a single definition: statScopeLabel() below is these parts followed
    // by the rest, in the order it has always emitted them.
    function statPlaceParts() {
        var parts = [];
        // A region tab's country set reads as its region name ("Europe"),
        // not as "France +7" — the raw form confused readers.
        var countries = selectedList('alt-f-country');
        if (countries.length) {
            // Up to four selections are named in full — "Australia +2 more"
            // hid exactly the cross-reference the picker exists for. Five or
            // more fall back to the compact form.
            // Every hand-picked country is named — hiding any behind
            // "+N more" defeats the cross-referencing the picker exists for.
            parts.push(regionNameFor(countries) || countries.join(' · '));
        }
        var st = selectedList('alt-f-state');
        if (st.length) parts.push('US: ' + (st.length <= 6 ? st.join(' · ')
            : st.slice(0, 5).join(' · ') + ' +' + (st.length - 5) + ' more'));
        return parts;
    }

    // Everything else the scope stamp carries: industry, and the narrowing
    // toggles. Not geography, so the hero label never absorbs it.
    function statNarrowParts() {
        var parts = [];
        var v = selectedList('alt-f-industry');
        if (v.length) parts.push(v.length <= 6 ? v.join(' · ')
            : v.slice(0, 5).join(' · ') + ' +' + (v.length - 5) + ' more');
        // Narrowing toggles change what every card MEANS — say so on the
        // cards themselves, or "Verified" silently becomes "verified AI".
        if (readControl('alt-f-ai')) parts.push('AI-attributed rows only');
        if (readControl('alt-f-ai-broad')) parts.push('AI-linked broad rows only');
        if (readControl('alt-f-announced')) parts.push('announced only');
        return parts;
    }

    function statScopeLabel() {
        var parts = statPlaceParts().concat(statNarrowParts());
        return parts.length ? ' · ' + parts.join(' · ') : '';
    }

    /*
      THE HERO'S BASIS, IN THE LABEL ITSELF.

      The hero is the figure a journalist compares against a national estimate
      inside ten seconds, and it read "verified job cuts, 2026": no geography,
      and a bare year that does not say whether the window is what has happened
      or what is on file. Those are two numbers 33,939 apart on 2026-08-04.

      Geography falls back to "worldwide" rather than to nothing, because an
      unfiltered total IS a worldwide total and leaving it unsaid is what made
      the figure look like a US claim next to a US survey.

      Period says "calendar year" and deliberately not "YTD", because rows are
      dated by effective date, so the window holds notices filed for dates ahead.
      The as-of line under the hero splits the two and sums back to this figure.
    */
    function heroGeoLabel() {
        var places = statPlaceParts();
        return places.length ? places.join(' · ') : 'worldwide';
    }

    function heroPeriodLabel() {
        var period = statPeriodLabel();
        if (/^\d{4}$/.test(period)) period = 'calendar year ' + period;
        return period + statNarrowParts().map(function (p) { return ' · ' + p; }).join('');
    }

    // The as-of date the server counted to, in the page's own date style.
    // Read from the response rather than from the browser clock: the two can
    // differ by a day across timezones, and the sentence names a figure the
    // server produced.
    function asOfLabel(t) {
        var iso = (t && t.as_of) || '';
        var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
        if (!m) return 'today';
        return MONTHS[parseInt(m[2], 10) - 1] + ' ' + parseInt(m[3], 10) + ', ' + m[1];
    }

    /*
      THE SAME SENTENCE alt_period_split_sentence() BUILDS IN db.php, character
      for character. Two totals are correct for one year (what has taken effect,
      and the whole window including notices filed for effective dates still
      ahead), and on 2026-08-04 the home page headlined one while the press page
      quoted the other with nothing tying them together. The reconciliation is
      now one sentence, printed on both surfaces, so it cannot drift on one of
      them. test_headline_total_agreement.py runs BOTH implementations on the
      same inputs and fails on any difference, including whitespace.
    */
    function periodSplitSentence(toDate, calendar, asOf, period) {
        toDate = Math.max(0, toDate | 0);
        calendar = Math.max(0, calendar | 0);
        var later = Math.max(0, calendar - toDate);
        if (later <= 0) return '';
        return fmt(toDate) + ' have taken effect as of ' + asOf
            + '. The other ' + fmt(later)
            + ' are on notices already filed for effective dates later in ' + period
            + '. Together they make the ' + fmt(calendar) + ' total for ' + period + '.';
    }

    // The compressed twin of alt_period_split_short() in db.php, character for
    // character. This is the version the first screen carries: two parts, the
    // whole, and the period, in one line. See the PHP docblock for why it is
    // compressed rather than removed, and why it is not behind a disclosure.
    function periodSplitShort(toDate, calendar, period) {
        toDate = Math.max(0, toDate | 0);
        calendar = Math.max(0, calendar | 0);
        var later = Math.max(0, calendar - toDate);
        if (later <= 0) return '';
        return fmt(toDate) + ' have taken effect. The other ' + fmt(later)
            + ' are filed for effective dates later in ' + period
            + '. Together, ' + fmt(calendar) + '.';
    }

    function renderStats(t) {
        if (!document.getElementById('alt-stats-bar') || !t) return;
        var period = statPeriodLabel();
        var scope = statScopeLabel();
        var annJ = t.announced_jobs || 0;
        var verifiedJ = t.jobs - annJ;
        var when = period + scope;
        // Announced plans carry future dates inside the selected period, so
        // "YTD" would wrongly imply they already happened. Plans can also
        // change or be cancelled before execution — dates are the company's
        // stated schedule, not a promise.
        var whenAnnounced = period + scope + ' · includes future-dated plans';
        setText('alt-stat-total', fmt(verifiedJ));
        setText('alt-stat-total-entries', when);
        // The basis, on every surface that publishes a total, rewritten from
        // the one BASIS_COPY table. Called here as well as from setDateBasis()
        // so a filter change that re-renders the tiles cannot leave a stale
        // basis word behind, and so the server-rendered first paint is
        // corrected the moment JS runs.
        renderBasisCopy();
        setText('alt-hero-total-geo', heroGeoLabel());
        // The hero figure is the SAME number as the Verified tile, written from
        // the same variable in the same pass, so a filter change can never
        // leave the page publishing two different headline totals.
        setText('alt-hero-total', fmt(verifiedJ));
        setText('alt-hero-total-period', heroPeriodLabel());
        /*
          THE HERO'S RECONCILING LINE, and the citeline that quotes it.

          verifiedToDate + later = verifiedJ, so a reader can add up what is on
          screen and land on the headline. `to_date_jobs` is absent only in the
          seconds between an FTP deploy landing this file and db.php; the line
          hides rather than printing a subtraction it cannot make.
        */
        var haveToDate = (t.to_date_jobs != null && t.to_date_announced_jobs != null);
        var verifiedToDate = haveToDate ? (t.to_date_jobs - t.to_date_announced_jobs) : null;
        var asOfEl = document.getElementById('alt-hero-asof');
        if (asOfEl) {
            // The COMPRESSED reconciliation. The full sentence still exists and
            // still runs (periodSplitSentence, above) on the press page, where a
            // reader is deliberately looking up how to cite a figure.
            var split = haveToDate
                ? periodSplitShort(verifiedToDate, verifiedJ, period) : '';
            asOfEl.textContent = split;
            // The sentence now sits inside a labelled wrapper ("In this
            // figure: ..."), so an empty split has to hide the LABEL too or
            // the hero prints a colon with nothing after it.
            var asOfWrap = document.getElementById('alt-hero-asof-wrap');
            if (asOfWrap) asOfWrap.hidden = (split === '');
            else asOfEl.hidden = (split === '');
        }
        /*
          THE CITE LINE SAYS WHAT ITS NUMBER IS, and it is not the headline.

          It read "N verified job cuts recorded for 2026 so far". Three totals
          on this page can be live at once and all three read as the same
          claim: the hero (the whole selected window), the at-a-glance board's
          YTD column (its own fixed period, region tabs only) and this line
          (the part of the selected window that has already taken effect). In
          one live view they were 484,427, 335,637 and 24,754, with nothing on
          screen saying which question each answered. A screenshot of the
          smallest one, captioned as ours, is a story.

          So this line now states its geography and its period from the SAME
          labels the hero uses, and says plainly that its number is the part
          that has already taken effect. The basis word comes from
          renderBasisCopy(), which reads the one BASIS_COPY table.
        */
        if (verifiedToDate != null) setText('alt-citeline-total', fmt(verifiedToDate));
        setText('alt-citeline-geo', heroGeoLabel());
        setText('alt-citeline-period', heroPeriodLabel());
        setText('alt-stat-announced', fmt(annJ));
        setText('alt-stat-announced-sub', whenAnnounced);
        setText('alt-stat-all', fmt(t.jobs || 0));
        setText('alt-stat-all-sub', whenAnnounced);
        // AI-attributed is the VERIFIED subset; announced-AI is the ANNOUNCED
        // subset. Each card says which parent number it belongs to.
        var aiJ = (t.ai_verified_jobs != null) ? t.ai_verified_jobs : t.ai_jobs;
        setText('alt-stat-ai', fmt(aiJ));
        setText('alt-hero-ai', fmt(aiJ));
        var pctTxt = function (num, den) {
            if (!(den > 0) || num == null) return null;
            var pv = 100 * num / den;
            return (pv >= 10 ? Math.round(pv) : pv.toFixed(1)) + '%';
        };
        setText('alt-stat-ai-sub', when);
        // A share is only meaningful against a denominator that still contains
        // non-AI rows. Once the view is filtered to AI-attributed rows the
        // denominator IS the numerator, so this read "100% of verified cuts
        // were blamed on AI by the employer", which is circular and, screenshot
        // out of context, plainly false. Say what the filter did instead.
        var _cp = (typeof currentParams === 'function') ? currentParams() : {};
        var aiFiltered = !!(readControl('alt-f-ai')
            || _cp.ai === '1' || _cp.ai_broad === '1' || _cp.ai_primary === '1');
        var shareV = aiFiltered ? null : pctTxt(aiJ, verifiedJ);
        setText('alt-stat-ai-share-line', aiFiltered
            ? 'Share not shown: this view is filtered to AI-attributed rows, so it would compare the number with itself.'
            // "blamed on AI by the employer" was a verdict. The rubric is that
            // the EMPLOYER named AI, in words we hold; we report the stated
            // reason and do not assert the cause on anyone's behalf.
            : (shareV ? shareV + ' of verified cuts name AI as a reason, in the employer\'s words' : ''));
        // The broad card is the wider-lens AI measure. Location-basis fills
        // first so the card never sits empty.
        setText('alt-stat-ai-broad', fmt(t.ai_broad_jobs || 0));
        setText('alt-stat-ai-broad-sub', when);
        // Same trap: filtered to strict-AI rows, the broad measure cannot
        // exceed them, so the card silently equalled the specific total while
        // its caption promised it would be larger.
        var shareB = aiFiltered ? null : pctTxt(t.ai_broad_jobs, t.jobs);
        setText('alt-stat-ai-broad-share-line', aiFiltered
            ? 'Equals the specific total in this filtered view: the broad lens can only widen an UNfiltered set. Clear the AI filter to see it.'
            : (shareB ? shareB + ' of all cuts in this view have an AI link' : ''));
        var aiAnnJ = (t.ai_announced_jobs != null)
            ? t.ai_announced_jobs
            : Math.max(0, (t.ai_jobs || 0) - aiJ);
        setText('alt-stat-ai-announced', fmt(aiAnnJ));
        setText('alt-stat-ai-announced-sub', whenAnnounced);
        // Strict AI total = verified + announced (these DO add up; the broad
        // card is a separate, looser measure and deliberately does not).
        var aiTotal = aiJ + aiAnnJ;
        setText('alt-stat-ai-total', fmt(aiTotal));
        setText('alt-stat-ai-total-sub', fmt(aiJ) + ' verified + ' + fmt(aiAnnJ) + ' announced');

        setText('alt-stat-companies', fmt(t.companies));
        setText('alt-stat-industries', fmt(t.industries));
        setText('alt-stat-countries', fmt(t.countries));
        setText('alt-stat-states', t.states > 0 ? fmt(t.states) : '0');
        // Singular/plural so "1 countries" never renders
        setText('alt-stat-industries-label', t.industries === 1 ? 'industry' : 'industries');
        setText('alt-stat-countries-label', (t.countries === 1 ? 'country' : 'countries') + ' with reported layoffs');
        setText('alt-stat-states-label', t.states === 1 ? 'US state' : 'US states');

        // Only surface an explicit empty-state; the raw earliest/latest range
        // reads as noise (a year filter trivially spans Jan 1–Dec 31).
        var note = document.getElementById('alt-range-note');
        if (note) {
            note.textContent = (t.entries && t.min_date) ? '' : 'no layoffs match the current filters';
        }
    }

    /* ------------------------------------------------------------------ */
    /* Period selections + multi-select dropdowns                          */
    /* ------------------------------------------------------------------ */

    function daysInMonth(y, m) { return new Date(y, m, 0).getDate(); }
    function pad2(n) { return (n < 10 ? '0' : '') + n; }

    // Human summary of the selected period, e.g. "in 2026", "in Q1 2024 & 2026".
    function currentPeriodLabel() {
        var years = readControl('alt-f-years') || [];
        var quarters = readControl('alt-f-quarters') || [];
        var months = readControl('alt-f-months') || [];
        var from = readControl('alt-f-from'); var to = readControl('alt-f-to');
        var parts = [];
        if (months.length) parts.push(months.map(function (m) { return MONTHS[parseInt(m, 10) - 1]; }).join(' & '));
        if (quarters.length) parts.push(quarters.map(function (q) { return 'Q' + q; }).join(' & '));
        if (years.length) parts.push(years.slice().sort().join(' & '));
        if (from || to) parts.push((from ? fmtDate(from) : '…') + ' – ' + (to ? fmtDate(to) : 'now'));
        return parts.length ? 'in ' + parts.join(' ') : 'all time';
    }

    // Fill the Years select from the data range, newest first, capped at the
    // current year (no future years even if a filing is future-dated).
    function initYears(facets) {
        var sel = document.getElementById('alt-f-years');
        if (!sel) return;
        var nowY = new Date().getFullYear();
        var minY = facets.min_date ? parseInt(facets.min_date.slice(0, 4), 10) : 2019;
        var maxY = facets.max_date ? Math.min(parseInt(facets.max_date.slice(0, 4), 10), nowY) : nowY;
        for (var y = maxY; y >= minY; y--) {
            var opt = document.createElement('option');
            opt.value = String(y); opt.textContent = String(y);
            sel.appendChild(opt);
        }
    }

    /* Toggle pills over a hidden native multi-select, for any facet marked
       `data-pills` in the template. As of 2.19.251 the template marks NONE:
       the owner reversed the Sources/Roles pill strips on 2026-08-02 (they ate
       half the filter bar), so both are compact checkbox dropdowns again. The
       renderer stays because it is small, generic and template-driven — adding
       `data-pills` to a cell re-enables it with no JS change.

       This deliberately hangs off the SAME two hooks the checkbox dropdown uses,
       and adds none of its own: `cell._altDdRender` (which
       updateDropdownSummaries already calls after every refreshAll, every URL
       restore, every chart tap and every reset) and a 'change' listener on the
       select. So the select stays the single source of truth and the whole
       existing state machine — querystring, chips bar, exports, quick views,
       click-to-filter, sessionStorage — keeps reading and writing it untouched.
       Toggling goes through toggleMultiFilter, the same helper a chart bar uses,
       rather than a second copy of the same three lines.

       With JavaScript off the native select simply remains, exactly as before. */
    function initPillGroup(cell) {
        var select = cell.querySelector('select[multiple]');
        if (!select || cell.querySelector('.alt-pillgroup')) return;
        // Presentation-hidden, not removed: it is still the state, and it is
        // still the control a no-JS reader gets.
        select.style.display = 'none';
        select.tabIndex = -1;
        select.setAttribute('aria-hidden', 'true');

        var group = document.createElement('div');
        group.className = 'alt-pillgroup';
        group.setAttribute('role', 'group');
        // The <label for> now points at a hidden control, so the group needs the
        // label named at it directly or the pills are an unlabelled cluster.
        var lbl = cell.querySelector('label');
        if (lbl && lbl.id) group.setAttribute('aria-labelledby', lbl.id);
        cell.appendChild(group);

        function render() {
            group.innerHTML = Array.prototype.map.call(select.options, function (o) {
                if (!o.value) return '';
                return '<button type="button" class="alt-pill' + (o.selected ? ' alt-pill-on' : '')
                    + '" data-value="' + escapeHtml(o.value) + '"'
                    + ' aria-pressed="' + (o.selected ? 'true' : 'false') + '">'
                    + escapeHtml(o.textContent) + '</button>';
            }).join('');
        }
        group.addEventListener('click', function (e) {
            var btn = e.target && e.target.closest ? e.target.closest('button[data-value]') : null;
            if (!btn) return;
            if (!toggleMultiFilter(select.id, btn.getAttribute('data-value'))) return;
            select.dispatchEvent(new Event('change', { bubbles: false }));
        });
        select.addEventListener('change', render);
        cell._altDdRender = render;
        render();
    }

    /* Custom checkbox-dropdowns over the hidden native multi-selects. The
       native select stays the single source of truth (readControl/writeControl,
       persistence, chips, quick views all keep working); the dropdown is pure
       presentation and dispatches 'change' on the select when toggled. */
    function initMultiDropdowns() {
        document.querySelectorAll('.alt-filter[data-dd]').forEach(function (cell) {
            if (cell.hasAttribute('data-pills')) { initPillGroup(cell); return; }
            var select = cell.querySelector('select[multiple]');
            if (!select || cell.querySelector('.alt-dd')) return;
            select.style.display = 'none';

            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'alt-dd';
            btn.setAttribute('aria-haspopup', 'listbox');
            var pop = document.createElement('div');
            pop.className = 'alt-dd-pop';
            pop.hidden = true;
            cell.appendChild(btn);
            cell.appendChild(pop);

            function summary() {
                var picked = Array.prototype.filter.call(select.options, function (o) { return o.selected; });
                if (!picked.length) return cell.getAttribute('data-empty') || 'All';
                if (picked.length === 1) return picked[0].textContent;
                return picked[0].textContent + ' +' + (picked.length - 1);
            }
            function render() {
                btn.innerHTML = '<span class="alt-dd-txt">' + escapeHtml(summary()) + '</span>'
                    + '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
                btn.classList.toggle('alt-dd-on', select.selectedOptions.length > 0);
                pop.innerHTML = '';
                Array.prototype.forEach.call(select.options, function (o) {
                    var row = document.createElement('label');
                    row.className = 'alt-dd-row';
                    var cb = document.createElement('input');
                    cb.type = 'checkbox';
                    cb.checked = o.selected;
                    cb.addEventListener('change', function () {
                        o.selected = cb.checked;
                        select.dispatchEvent(new Event('change', { bubbles: false }));
                    });
                    row.appendChild(cb);
                    row.appendChild(document.createTextNode(' ' + o.textContent));
                    pop.appendChild(row);
                });
            }
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var willOpen = pop.hidden;
                closeAllDropdowns();
                if (willOpen) { render(); pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); }
            });
            pop.addEventListener('click', function (e) { e.stopPropagation(); });
            select.addEventListener('change', render);
            cell._altDdRender = render;
            render();
        });

        document.addEventListener('click', closeAllDropdowns);
    }
    function closeAllDropdowns() {
        document.querySelectorAll('.alt-dd-pop, .alt-range-pop').forEach(function (p) { p.hidden = true; });
        document.querySelectorAll('.alt-dd, .alt-range-btn').forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    }
    function updateDropdownSummaries() {
        document.querySelectorAll('.alt-filter[data-dd]').forEach(function (cell) {
            if (cell._altDdRender) cell._altDdRender();
        });
    }

    /* Clickable date-range control (replaces the From/To calendars in the bar) */
    function updateRangeLabel() {
        var label = document.getElementById('alt-range-label');
        if (!label) return;
        var from = readControl('alt-f-from'); var to = readControl('alt-f-to');
        if (from || to) {
            label.textContent = (from ? fmtDate(from) : 'Start') + ' – ' + (to ? fmtDate(to) : 'now');
            return;
        }
        var years = (readControl('alt-f-years') || []).slice().sort();
        if (years.length) {
            var a = years[0], b = years[years.length - 1];
            label.textContent = 'Jan 1' + (a === b ? '' : ', ' + a) + ' – Dec 31, ' + b;
            return;
        }
        label.textContent = 'All time';
    }

    function initRangeControl() {
        var btn = document.getElementById('alt-range-btn');
        var pop = document.getElementById('alt-range-pop');
        if (!btn || !pop) return;
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var willOpen = pop.hidden;
            closeAllDropdowns();
            pop.hidden = !willOpen;
            btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        });
        pop.addEventListener('click', function (e) { e.stopPropagation(); });
        document.addEventListener('click', function () { pop.hidden = true; });
        var clr = document.getElementById('alt-range-clear');
        if (clr) clr.addEventListener('click', function () {
            writeControl('alt-f-from', ''); writeControl('alt-f-to', '');
            refreshAll();
        });
    }

    /* ------------------------------------------------------------------ */
    /* Charts (from /aggregate)                                            */
    /* ------------------------------------------------------------------ */

    function renderCharts(agg) {
        if (!DASH_PRESENT) return;
        setStatus('alt-dashboard-status', agg.totals.entries ? null : 'No entries match the current filters.');
        if (chartsAvailable()) {
            renderTrend(agg.series);
            renderAiCumulative(agg.series);
            renderReasons(agg.reasons, document.getElementById('alt-f-reasons') ? 'alt-f-reasons' : null, readControl('alt-f-reasons'));
        }
        // Outside the Chart.js guard on purpose: the trajectory strip is plain
        // SVG, so it still draws on a browser where the chart library failed.
        renderTrendTrajectory();
        renderLeaderboard(agg.leaders);
        var wired = !!document.getElementById('alt-f-industry');
        // Every bar list below is drawn on the VERIFIED basis so it is the same
        // quantity as the headline tile, and every one carries the sentence
        // saying so. See verifiedBasis() for the defect this closes.
        var barTotals = agg.totals || null;
        var industryRows = verifiedBasis(agg.top_industries);
        var stateRows = verifiedBasis(agg.top_states);
        // THE FLAG IS A COLUMN, NOT A PREFIX ON THE NAME.
        //
        // It used to be concatenated into the display string, so a country
        // COUNTRY_ISO had never met drew no flag and started its name a flag's
        // width left of every other row - which does not read as a missing
        // flag, it reads as a broken left edge halfway down a ranked list, on
        // the one line the eye tracks. Adding the missing countries fixed the
        // rows we draw TODAY and left the layout exactly as brittle for the
        // next country the data reaches, and the data reaches new countries on
        // its own. So the icon moved into slot 4 and renderBarList reserves
        // that column's width for every row of the card, flag or no flag.
        // Slot 4 is free: verifiedBasis emits four fields, and it is the last
        // thing every bar list passes through.
        var countryRows = verifiedBasis(agg.top_countries).map(function (e) {
            return [e[0], e[1], e[2], e[3] || e[0], countryFlag(e[0])];
        });
        renderBarList('alt-bars-industries', industryRows, wired ? 'alt-f-industry' : null, selectedList('alt-f-industry'));
        renderBarList('alt-bars-states', stateRows, wired ? 'alt-f-state' : null, selectedList('alt-f-state'));
        renderBarList('alt-bars-countries', countryRows, wired ? 'alt-f-country' : null, selectedList('alt-f-country'));
        setBarBasisNote('alt-bars-industries-basis',
            barBasisNote(barTotals, industryRows, 'industry', selectedList('alt-f-industry').length > 0));
        // The state card is scoped to the United States (see barBasisNote):
        // its bars can only ever cover US cuts, so it reconciles against the
        // US verified total, not the worldwide one.
        var usVerified = countryVerifiedTotal(agg, 'United States');
        var worldVerified = ((barTotals && barTotals.jobs) || 0) - ((barTotals && barTotals.announced_jobs) || 0);
        var stateScope = {
            // 0 makes barBasisNote stop after the basis sentence: with no
            // United States row in this view there is no honest denominator,
            // and the worldwide one is the defect this scope exists to close.
            headline: (usVerified == null) ? 0 : usVerified,
            of: 'verified US cuts',
            outside: (usVerified != null && worldVerified > usVerified)
                ? 'The ' + fmt(worldVerified - usVerified) + ' verified cuts outside the United States are not in these bars and are not counted below.'
                : ''
        };
        setBarBasisNote('alt-bars-states-basis',
            barBasisNote(barTotals, stateRows, 'US state', selectedList('alt-f-state').length > 0, stateScope));
        setBarBasisNote('alt-bars-countries-basis',
            barBasisNote(barTotals, countryRows, 'country', selectedList('alt-f-country').length > 0));
        AIMAP.data = agg;
        // Defer the map's heavy work (fetching the ~756KB world atlas + the d3
        // geo render) until the card nears the viewport. The data is stored
        // above so the map is always current when it does draw; only the draw
        // waits. This is the single biggest initial-load win on mobile.
        if (AIMAP.revealed) renderAiMap(); else observeMapReveal();
        // Largest single events: name, jobs, AI segment when explicitly
        // attributed. Tapping toggles the company text filter.
        var companyBox = document.getElementById('alt-f-company');
        // entry[0] stays the bare company name (the tap-to-filter key); entry[3]
        // is the display label with the event's location appended, so multiple
        // filings by one company read as the distinct places they are.
        var leaderEntries = (agg.leaders || []).map(function (l) {
            var display = l.company_name + (l.location ? ' · ' + l.location : '');
            return [l.company_name, l.job_count, l.ai_explicit ? l.job_count : 0, display];
        });
        renderAiShare(agg.series);
        renderYoY(agg.series);
        // AI intensity: which industries' cuts are MOST AI-attributed (share
        // of that industry's jobs, min 1,000 jobs so tiny bases don't rank).
        // Numerator AND denominator are the verified pair, so this share is
        // the same one the AI tile states against the headline tile. Mixing an
        // all-jobs denominator with a verified numerator would understate it.
        var intensity = industryRows
            .filter(function (e) { return e[1] >= 1000 && e[2] > 0; })
            .map(function (e) { return [e[0], Math.round(100 * e[2] / e[1]), Math.round(100 * e[2] / e[1])]; })
            .sort(function (a, b) { return b[1] - a[1]; })
            .slice(0, 8);
        // Same industry vocabulary as the "By industry" card, so a tap goes
        // through the identical Industries control.
        renderBarList('alt-bars-ai-intensity', intensity, wired ? 'alt-f-industry' : null,
            selectedList('alt-f-industry'), null, '%');
        /*
          THIS CARD IS HONESTLY SPARSE, AND IT NOW SAYS SO.

          In a typical filtered view it draws ONE row, Technology, and leaves a
          large empty area that reads as broken. It is not broken. The 1,000-cut
          floor is there so a share is computed on a base that can carry one: a
          50 percent AI rate over 4 cuts is exactly the number this project
          refuses to publish. Lowering the floor to fill the card, or padding it
          with more rows, would trade the card's correctness for its looks.

          So the emptiness gets a label instead of a fix: how many industries
          are in this view, and how many cleared the bar. When NONE clear it the
          card says that in words rather than rendering nothing at all, which is
          the state that most reads as a broken card. Written as visible prose
          into the card, and the guard test measures its RENDERED text length
          rather than reading this source.
        */
        var intensityNote = document.getElementById('alt-bars-ai-intensity-note');
        if (intensityNote) {
            var considered = industryRows.length;
            var cleared = intensity.length;
            var txt;
            if (!considered) {
                txt = 'No industry is recorded in this view, so there is no rate to show.';
            } else if (!cleared) {
                txt = 'None of the ' + fmt(considered) + ' industr' + (considered === 1 ? 'y' : 'ies')
                    + ' in this view has both 1,000 or more verified cuts and any cut the employer attributed to AI, so there is no rate to show. The floor is there so a share is never computed on a base too small to carry one.';
            } else {
                txt = fmt(cleared) + ' of the ' + fmt(considered) + ' industr'
                    + (considered === 1 ? 'y' : 'ies') + ' in this view '
                    + (cleared === 1 ? 'has' : 'have') + ' 1,000 or more verified cuts and at least one cut the employer attributed to AI, so '
                    + (cleared === 1 ? 'one bar is' : fmt(cleared) + ' bars are') + ' shown. The floor is there so a share is never computed on a base too small to carry one.';
            }
            intensityNote.textContent = txt;
            intensityNote.hidden = false;
        }
        // Roles most impacted: fixed-category jobs with the AI-attributed
        // share as the orange segment — the AI-vs-all comparison per team.
        // Coverage is partial by construction (only events whose sources name
        // the affected teams carry categories), so the subtitle states the
        // honest denominator instead of implying every event is categorized.
        // /aggregate keys these by label; the filter takes slugs. Carry the slug
        // as the row's value and the label as its display text, so the tap
        // writes the Roles control exactly as picking it from the dropdown does.
        // A label with no slug (vocabulary drift) stays a plain, non-filtering row.
        var rolesWired = !!document.getElementById('alt-f-roles');
        var roleRows = verifiedBasis((agg.top_roles || []).map(function (e) {
            return [ROLE_SLUG_BY_LABEL[e[0]] || e[0], e[1], e[2], e[0], e[4], e[5]];
        }));
        renderBarList('alt-bars-roles', roleRows, rolesWired ? 'alt-f-roles' : null, selectedList('alt-f-roles'));
        var rolesSub = document.getElementById('alt-roles-sub');
        var rolesCard = document.getElementById('alt-roles-card');
        if (rolesSub) {
            var rke = (agg.totals && agg.totals.roles_known_entries) || 0;
            // Small-sample guard: only a minority of sources name the teams cut,
            // so make the caveat unmissable when the base is thin — a reporter
            // must not read this as representative of the whole dataset.
            var small = rke < 100;
            if (rolesCard) rolesCard.classList.toggle('alt-small-sample', small);
            rolesSub.innerHTML = (small ? '<span class="alt-sample-warn">⚠ Small sample, illustrative only.</span> ' : '')
                + 'Each bar is verified job cuts for that team, the same basis as the Verified job cuts tile; the <span class="alt-ai-key"></span> orange part'
                + ' and 🤖 number are the AI-attributed share. Built from only the <b>' + fmt(rke)
                + ' of ' + fmt((agg.totals && agg.totals.entries) || 0) + '</b> records whose source named which teams were cut'
                + '; a non-representative sample of where cuts land, <b>not</b> a breakdown of the total. Tap a role to filter the page.';
        }
        // Keep the raw source_type as the row value (the `sources` param accepts
        // it directly alongside the verification tiers — db.php matches either
        // column) and show the friendly label. The Sources dropdown only gains
        // the option when a bar is actually tapped (renderBarList's handler), so
        // the control stays short until someone uses it and then shows exactly
        // what they picked.
        var srcWired = !!document.getElementById('alt-f-verification');
        var sourceRows = verifiedBasis((agg.source_types || []).map(function (e) {
            return [e[0], e[1], e[2], SOURCE_TYPE_LABELS[e[0]] || e[0], e[4], e[5]];
        }));
        renderBarList('alt-bars-sourcetypes', sourceRows, srcWired ? 'alt-f-verification' : null, selectedList('alt-f-verification'));
        setBarBasisNote('alt-bars-sourcetypes-basis',
            barBasisNote(barTotals, sourceRows, 'data source', selectedList('alt-f-verification').length > 0));
        renderBarList('alt-bars-leaders', leaderEntries, null,
            companyBox && companyBox.value ? [companyBox.value] : [],
            companyBox ? function (val) { companyBox.value = (companyBox.value === val) ? '' : val; } : null);
        renderBarList('alt-bars-repeat', (agg.repeat_companies || []).map(function (e) { return [e[0], e[1], 0]; }), null,
            companyBox && companyBox.value ? [companyBox.value] : [],
            companyBox ? function (val) { companyBox.value = (companyBox.value === val) ? '' : val; } : null, ' rounds');
        // The card's title is rewritten here on every render, so this string
        // and the one page-tracker.php ships have to be the same words. They
        // were not: the template said "Layoffs by country" and this said "By
        // country", so the card renamed itself a beat after load and ended up
        // reading as a bare fragment beside its own neighbour, "Layoffs by US
        // state" - the same component, the same basis, the same subtitle
        // pattern, two grammars, side by side. The template's wording wins,
        // because it is the one that also survives with JavaScript off.
        var countryTitle = document.getElementById('alt-country-chart-title');
        if (countryTitle) {
            countryTitle.innerHTML = selectedList('alt-f-country').length
                ? 'Layoffs by country <span class="alt-chart-sub">Other countries you could pivot to · tap to filter</span>'
                : 'Layoffs by country <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span>';
        }
    }

    function selectedList(id) {
        var v = readControl(id);
        return Array.isArray(v) ? v : (v ? [v] : []);
    }

    // "Where the cuts are" bars: name left, value right, a track whose blue
    // fill is scaled to the top bar, with an orange leading segment showing the
    // AI-attributed share. Rows are buttons that toggle the matching filter.
    // Country name -> ISO2 for emoji flags on the country list. Covers the
    // normalizer's vocabulary; unknown names simply render without a flag.
    //
    // A GAP HERE IS VISIBLE, NOT SILENT. "renders without a flag" is not a
    // graceful degradation in a ranked list: every name is laid out from the
    // same x, so a row with no flag starts a flag's width to the left of the
    // twenty above it and breaks the one edge the eye tracks down the list.
    // On 2026-08-10 five live countries were in that state - Türkiye, Bosnia
    // and Herzegovina, Cyprus, Isle of Man and Malta - two of them mid-list.
    //
    // Two of those five were not spelling gaps but VOCABULARY drift: the map
    // carried 'Turkey' while the data has since moved to the endonym Türkiye,
    // and 'United Arab Emirates' while alt_normalize_country() canonicalises
    // that country to the string "UAE" (api.php). Both spellings are kept, so
    // a re-spelled row cannot lose its flag again. test_facet_pages.py holds
    // the list of names the country card is known to draw.
    var COUNTRY_ISO = { 'United States':'US','United Kingdom':'GB','Germany':'DE','France':'FR','Netherlands':'NL','India':'IN','Israel':'IL','Japan':'JP','Sweden':'SE','Canada':'CA','Australia':'AU','Brazil':'BR','China':'CN','Ireland':'IE','Singapore':'SG','Indonesia':'ID','Denmark':'DK','Finland':'FI','Norway':'NO','Poland':'PL','Spain':'ES','Italy':'IT','Austria':'AT','Belgium':'BE','Switzerland':'CH','Portugal':'PT','Czech Republic':'CZ','Czechia':'CZ','South Korea':'KR','Kenya':'KE','Nigeria':'NG','South Africa':'ZA','Egypt':'EG','Mexico':'MX','Argentina':'AR','Chile':'CL','Colombia':'CO','United Arab Emirates':'AE','Saudi Arabia':'SA','Turkey':'TR','Russia':'RU','Ukraine':'UA','New Zealand':'NZ','Philippines':'PH','Malaysia':'MY','Thailand':'TH','Vietnam':'VN','Taiwan':'TW','Hong Kong':'HK','Greece':'GR','Hungary':'HU','Romania':'RO','Bulgaria':'BG','Croatia':'HR','Slovakia':'SK','Slovenia':'SI','Estonia':'EE','Latvia':'LV','Lithuania':'LT','Luxembourg':'LU','Iceland':'IS','Serbia':'RS','Pakistan':'PK','Bangladesh':'BD','Sri Lanka':'LK','Nepal':'NP','Cambodia':'KH','Myanmar':'MM','Laos':'LA','Mongolia':'MN','Kazakhstan':'KZ','Qatar':'QA','Kuwait':'KW','Bahrain':'BH','Oman':'OM','Jordan':'JO','Lebanon':'LB','Iraq':'IQ','Iran':'IR','Morocco':'MA','Tunisia':'TN','Algeria':'DZ','Ghana':'GH','Ethiopia':'ET','Tanzania':'TZ','Uganda':'UG','Zambia':'ZM','Zimbabwe':'ZW','Botswana':'BW','Namibia':'NA','Mozambique':'MZ','Angola':'AO','Senegal':'SN','Ivory Coast':'CI','Cameroon':'CM','Peru':'PE','Ecuador':'EC','Uruguay':'UY','Paraguay':'PY','Bolivia':'BO','Venezuela':'VE','Costa Rica':'CR','Panama':'PA','Guatemala':'GT','Dominican Republic':'DO','Jamaica':'JM','Trinidad and Tobago':'TT','Cuba':'CU','Haiti':'HT','Türkiye':'TR','Bosnia and Herzegovina':'BA','Cyprus':'CY','Malta':'MT','Isle of Man':'IM','UAE':'AE','Antigua and Barbuda':'AG','Saint Kitts and Nevis':'KN','Saint Vincent and the Grenadines':'VC','Sao Tome and Principe':'ST','Turks and Caicos Islands':'TC' };
    function countryFlag(name) {
        // No trailing space: the gap is the reserved column's width now, so a
        // space here would double it on the rows that happen to have a flag.
        if (name === 'Multiple countries') return '\uD83C\uDF10';
        var iso = COUNTRY_ISO[name];
        if (!iso) return '';
        var A = 0x1F1E6;
        return String.fromCodePoint(A + iso.charCodeAt(0) - 65, A + iso.charCodeAt(1) - 65);
    }

    /* THE BARS AND THE HEADLINE MUST BE THE SAME QUANTITY -------------- */
    /*
      The bar cards used to draw entry[1], which is verified PLUS announced,
      immediately beside a headline tile counting verified only. On 2026-08-04
      the visible country bars summed to about 757,000 against a published
      headline of 444,871: roughly 70% over, with nothing on the card saying
      the two were different quantities. A reader adding up what they could see
      could not land on the number the page publishes, and was not told why.

      /aggregate now carries a verified pair at [4]/[5] (see the $topN note in
      db.php for why they are there and not at [1]/[2]). This switches the
      dashboard's bars onto it, drops rows that are entirely announced, and
      re-sorts, because the server orders by the all-jobs total for the sake of
      the facet pages and the appendix CSV that read the same block.

      THE CARDS ALSO SAY SO. Matching the basis is necessary and not
      sufficient: these lists are a top-N of a longer tail, so the bars still
      will not sum to the headline exactly. barBasisNote() states the basis and
      names the remainder, so the gap that is left is an explained one.
    */
    // How many rows a bar card draws. Shared with barBasisNote() below: the
    // sentence says how many of the dimension are shown, so it has to be the
    // same number the renderer stops at.
    var BARLIST_LIMIT = 24;

    function verifiedBasis(entries) {
        return (entries || []).map(function (e) {
            // Absent only during the seconds-long window where an FTP deploy
            // has landed this file but not yet db.php. Falling back to [1] is
            // the pre-fix rendering, which self-heals on the next response;
            // drawing zeros would empty the card instead.
            var v = (e[4] != null) ? e[4] : e[1];
            var a = (e[5] != null) ? e[5] : e[2];
            return [e[0], v, a, e[3]];
        }).filter(function (e) {
            return e[1] > 0;
        }).sort(function (x, y) {
            return y[1] - x[1];
        });
    }

    /*
      THE SENTENCE THAT MAKES THE CARD RECONCILABLE.

      Matching the basis was necessary and not sufficient. Even on one basis
      the bars do not sum to the headline, for reasons a reader cannot see:
      records with no value in that dimension are not on the chart at all
      (in the 2026 view, 27,964 verified cuts sit on records with no country
      recorded), and the card draws at most BARLIST_LIMIT rows.

      So rather than hand-waving at the gap, this states it: how much the bars
      cover, of what, and where the rest is. Every figure is computed from the
      same totals the tiles render, so the sentence cannot drift from them, and
      the drawn total is summed from the drawn rows rather than fetched, so it
      cannot disagree with the bars above it either.

      THE ONE CASE WHERE THE ARITHMETIC DOES NOT HOLD, and is not claimed: each
      bar list deliberately ignores its OWN dimension's filter, so you can pick
      a different country while looking at the country card. With that filter
      on, the bars are a wider population than the headline and no sum relates
      them. The note says that instead of printing a subtraction that is false.

      AND THE ONE CASE WHERE THE DENOMINATOR IS NOT THE HEADLINE. Industry,
      country and data source are global dimensions: every counted row can
      carry one, so the worldwide verified total is the right denominator and
      the remainder really is "records with no value here". US STATE is not
      like that. Its universe is the United States, so measuring the state
      bars against the worldwide total charged every non-US cut to a US
      data-quality gap: on 2026-08-04 the card printed 193,896 missing when
      the honest figure was about 89,848, and on the default all-time view it
      printed 2,383,032 against roughly 1,285,383. The caller passes a scope
      for that card, and the sentence names it.
    */
    function barBasisNote(totals, rows, noun, dimensionFiltered, scope) {
        if (!totals || !rows) return '';
        var txt = 'Bars are verified job cuts, the same basis as the Verified job cuts tile.';
        var ann = totals.announced_jobs || 0;
        if (ann > 0) {
            txt += ' The ' + fmt(ann) + ' announced job cuts in this view are a separate tier and are not in these bars.';
        }
        if (dimensionFiltered) {
            return txt + ' This list keeps showing every ' + noun + ' while a ' + noun
                + ' filter is on, so you can switch; its bars cover a wider set than the total above and are not meant to sum to it.';
        }
        var shown = rows.slice(0, BARLIST_LIMIT);
        // A scoped card reconciles against ITS OWN universe, and says which.
        // Scope shape: { headline: n, of: 'verified US cuts', outside: '...' }.
        // A scope whose headline could not be established (no United States row
        // in this view) drops the coverage sentence rather than reconciling
        // against a denominator that is not the card's population.
        var headline = scope ? (scope.headline || 0) : ((totals.jobs || 0) - ann);
        var ofPhrase = scope ? scope.of : 'verified cuts';
        if (scope && scope.outside) txt += ' ' + scope.outside;
        if (headline <= 0 || !shown.length) return txt;
        var drawn = shown.reduce(function (sum, e) { return sum + (e[1] || 0); }, 0);
        txt += ' These ' + fmt(shown.length) + ' bars cover ' + fmt(drawn) + ' of the '
            + fmt(headline) + ' ' + ofPhrase;
        var rest = headline - drawn;
        if (rest > 0) {
            txt += '; the remaining ' + fmt(rest) + ' sit on records with no ' + noun + ' recorded';
            if (rows.length > shown.length) {
                txt += ', or outside the largest ' + fmt(shown.length) + ' shown';
            }
            txt += '.';
        } else {
            txt += '.';
        }
        return txt;
    }

    // The reasons card's own sentence. It cannot use barBasisNote(): that one
    // reconciles a top-N against a total, and these slices are overlapping tags
    // that no total contains. It says exactly that instead of printing a
    // subtraction that would be false.
    function reasonsBasisNote() {
        var txt = 'Slices are verified job cuts, the same basis as the Verified job cuts tile.';
        txt += ' Reason tags overlap, so they are not a breakdown of the total.'
            + ' One event can carry several tags, and an event whose source states no reason carries none.'
            + ' The slices are not meant to sum to the headline.';
        txt += ' These tags are read from the stored source text and are a different measure from the AI tiles,'
            + ' which are counted from the AI attribution flags. Tapping a slice filters the page to that tag.';
        return txt;
    }

    // The verified total for one country in this view, from the same
    // top_countries block the country card draws. Null when the view has no
    // row for it, which is the signal to print no coverage sentence at all.
    function countryVerifiedTotal(agg, name) {
        var rows = (agg && agg.top_countries) || [];
        for (var i = 0; i < rows.length; i++) {
            if (rows[i][0] === name) {
                return (rows[i][4] != null) ? rows[i][4] : rows[i][1];
            }
        }
        return null;
    }

    function setBarBasisNote(elId, txt) {
        var el = document.getElementById(elId);
        if (!el) return;
        el.textContent = txt || '';
        el.hidden = !txt;
    }

    function renderBarList(containerId, entries, filterId, activeValues, onPick, suffix) {
        var box = document.getElementById(containerId);
        if (!box) return;
        // Compact cards show a top-4 preview; expanded (or full-size dashboard
        // cards) show up to 12.
        var mini = box.closest('.alt-mini');
        var compact = mini && !mini.classList.contains('alt-expanded');
        var fullCount = (entries || []).length;
        // Compact cards render all rows too (up to 24) and scroll inside a
        // short box (CSS: .alt-mini .alt-barlist), so every item is reachable
        // without expanding — expanding just gives it more room.
        var limit = BARLIST_LIMIT;
        entries = (entries || []).slice(0, limit);
        if (!entries.length) {
            box.innerHTML = '<p class="alt-muted alt-empty">No data for the current filters.</p>';
            return;
        }
        var active = activeValues || [];
        // If ANY row of this card carries an icon (slot 4), every row of it
        // gets the icon column, empty or not. Emitting the span only where
        // there is something to put in it would be the same defect in a new
        // place: the rows without one would still start their name further
        // left than the rows with one.
        var iconCol = entries.some(function (e) { return e[4]; });
        var max = entries[0][1] || 1;
        entries.forEach(function (e) { if (e[1] > max) max = e[1]; });

        var html = '';
        entries.forEach(function (e) {
            var label = e[0], jobs = e[1], ai = e[2] || 0, display = e[3] || e[0];
            var w = Math.max(2, Math.round(jobs / max * 100));
            var aiW = jobs > 0 ? (ai / jobs * w) : 0;
            var isActive = active.indexOf(label) !== -1;
            var dim = active.length && !isActive;
            // AI breakdown: expanded rows spell it out (total · AI n · x%);
            // compact rows keep the visual fill plus a hover tooltip, so the
            // small cards stay scannable and the detail is one expand away.
            // aiKnown: this card counts jobs and the AI figure is a real subset
            // of them. hasAi narrows that to rows where the subset is not
            // empty, which is what earns the orange segment.
            var aiKnown = !suffix && ai <= jobs;
            var hasAi = aiKnown && ai > 0;
            var aiPct = hasAi ? Math.round(100 * ai / jobs) : 0;
            var valTxt = fmt(jobs) + (suffix || '');
            if (hasAi && !compact) valTxt += ' · \uD83E\uDD16 ' + fmt(ai) + ' (' + aiPct + '%)';
            /*
              THE TOOLTIP SAYS THE NAME THAT WAS HOVERED, AND IT DOES NOT COME
              AND GO DOWN THE LIST.

              Two defects in one line, both measured on the live page on
              2026-08-10.

              (1) It opened with `label`, which is the row's FILTER VALUE and
              not its name. On every card but one those are the same string. On
              "Roles most impacted" the value is the slug, so hovering "Sales &
              marketing" answered "sales_marketing: 26,089 total": an internal
              identifier, and not the name the reader pointed at. `display` is
              the string on screen, so it is the string the tooltip must open
              with. Every other tooltip on the page already leads with the
              human name ("United States: 369,821 total").

              (2) It was suppressed outright when the AI figure was zero, so on
              the country list it appeared on four rows of 22 with no rule a
              reader could infer from outside: Bangladesh, the third largest
              bar, had none, while Australia at a fifth its size did. Hovering
              down the list the control flickered on and off and read as
              broken. A zero is a fact about the row, so it is said in words.
              No number moves: a row with no AI-attributed cuts still draws no
              orange segment and still reports the same total.

              The `ai > jobs` case is data we do not trust, so it claims
              neither: no tooltip rather than a share we would have to qualify.
              Cards drawn with a `suffix` are not counting jobs at all (rounds,
              percent) and carry no tooltip, exactly as before.
            */
            var tip = '';
            if (aiKnown) {
                tip = display + ': ' + fmt(jobs) + ' total · '
                    + (hasAi ? fmt(ai) + ' AI-attributed (' + aiPct + '%)' : 'none attributed to AI');
            }
            html += '<button type="button" class="alt-barrow' + (isActive ? ' alt-barrow-on' : '') + (dim ? ' alt-barrow-dim' : '') + '"'
                + ((filterId || onPick) ? '' : ' disabled')
                + (tip ? ' title="' + escapeHtml(tip) + '"' : '')
                + ' data-val="' + escapeHtml(label) + '" data-label="' + escapeHtml(display) + '"'
                + ' aria-pressed="' + (isActive ? 'true' : 'false') + '">'
                + '<span class="alt-barrow-top"><span class="alt-barrow-name">'
                + (iconCol ? '<span class="alt-barrow-icon" aria-hidden="true">' + escapeHtml(e[4] || '') + '</span>' : '')
                + escapeHtml(display) + '</span>'
                + '<span class="alt-barrow-val">' + valTxt + '</span></span>'
                + '<span class="alt-bartrack">'
                + (aiW > 0.4 ? '<span class="alt-barfill-ai" style="width:' + aiW.toFixed(1) + '%"></span>' : '')
                + '<span class="alt-barfill" style="left:' + aiW.toFixed(1) + '%;width:' + Math.max(0, w - aiW).toFixed(1) + '%"></span>'
                + '</span></button>';
        });
        // Compact preview showing only part of the list: offer the rest.
        if (compact && fullCount > limit) {
            html += '<button type="button" class="alt-bar-more">Show all ' + fullCount + ' →</button>';
        }
        box.innerHTML = html;

        if (filterId || onPick) {
            box.querySelectorAll('.alt-barrow').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    // Multi-select: each click adds/removes that value, so bars
                    // compose (e.g. CA + WA + Technology). onPick overrides for
                    // non-multi targets (e.g. the company text filter).
                    var val = btn.getAttribute('data-val');
                    if (onPick) { onPick(val); }
                    else {
                        // A chart can show a value /facets never listed (an
                        // employer-HQ-only country, a source_type). Give the
                        // dropdown the option first so the toggle lands AND the
                        // control visibly reflects it.
                        ensureOption(filterId, val, btn.getAttribute('data-label') || val);
                        toggleMultiFilter(filterId, val);
                    }
                    refreshAll();
                });
            });
        }
        var more = box.querySelector('.alt-bar-more');
        if (more && mini) {
            more.addEventListener('click', function () {
                mini.classList.add('alt-expanded');
                var xp = mini.querySelector('.alt-expand');
                if (xp) { xp.setAttribute('aria-label', 'Collapse chart'); xp.title = 'Collapse'; }
                if (LAST_AGG) renderCharts(LAST_AGG);
            });
        }
    }

    // The API only returns months that have events; fill the gaps with zeros
    // so e.g. a January with no cuts shows as 0 instead of vanishing. The
    // window honors the whole period selection (From/To, years, quarters,
    // months) and only fills months the filters actually include — a month
    // excluded by the filter must not render as a misleading zero. Capped at
    // the current month so future months don't show as fake zeros.
    function periodAllowsMonth(y, m) {
        var years = readControl('alt-f-years') || [];
        var quarters = readControl('alt-f-quarters') || [];
        var months = readControl('alt-f-months') || [];
        if (years.length && years.indexOf(String(y)) === -1) return false;
        if (quarters.length && quarters.indexOf(String(Math.floor((m - 1) / 3) + 1)) === -1) return false;
        if (months.length && months.indexOf(String(m)) === -1) return false;
        return true;
    }

    /*
      THE IN-PROGRESS MONTH, CUT AT TODAY.

      /aggregate attaches a `to_date` block to a month bucket whenever some of
      its rows are dated later than today, which in practice is the current
      month and nothing else. This swaps those values in, so every chart plots
      what has actually taken effect.

      WHY THIS IS NOT COSMETIC. A month bucket is a bucket of EFFECTIVE dates,
      and WARN notices are filed with effective dates weeks ahead by law. On
      2026-08-04 the August bucket held 35,362 verified cuts of which 21,776
      had taken effect. The chart drew 35,362 under a caption reading "4 of 31
      days so far", while the This-month card on the same screen published
      21,776. Labelling the point partial and dashing it, which is what
      2.19.263 did, described the smaller number and drew the larger one, so
      the caption made the mismatch harder to spot rather than easier.

      The remainder is not discarded: futureDatedJobs() counts it and the
      chart note names it.
    */
    function toDateMonths(series) {
        return (series || []).map(function (s) {
            if (!s || !s.to_date) return s;
            var out = {};
            Object.keys(s).forEach(function (k) { out[k] = s[k]; });
            Object.keys(s.to_date).forEach(function (k) {
                if (k !== 'as_of') out[k] = s.to_date[k];
            });
            // Kept so a caller can still name the part that has not happened.
            out.full = s;
            return out;
        });
    }

    // Jobs in the charted data that have not taken effect yet: whole months
    // after this one (announced plans, future WARN effective dates), PLUS the
    // rest of the month the clock is inside. That second part used to be
    // missing, so the card printed "N future-dated jobs are not charted" while
    // 13,586 future-dated jobs sat inside the final plotted point.
    function futureDatedJobs(series) {
        var now = new Date();
        var nowKey = now.getFullYear() + '-' + pad2(now.getMonth() + 1);
        return (series || []).reduce(function (sum, s) {
            if (s.month > nowKey) return sum + (s.jobs || 0);
            if (s.to_date) return sum + Math.max(0, (s.jobs || 0) - (s.to_date.jobs || 0));
            return sum;
        }, 0);
    }

    /* THE MONTH THE CLOCK IS STILL INSIDE ------------------------------ */
    /*
      WHY THIS EXISTS. fillMonths() caps the charted window at the CURRENT
      month, which stops future months rendering as fake zeros. It does not
      stop the current month itself rendering as a FINISHED one, and that is
      the more expensive mistake, because the reader cannot see it.

      On 4 August 2026 the bucket for August held 16,546 verified cuts: four
      days of a month whose completed neighbours averaged about 58,000. Drawn
      as an ordinary point on an ordinary line, that is a plunge of roughly
      70%, and three charts published it at once. The trend line dived. The
      AI-share line, dividing an AI numerator that was still zero by those
      four days, terminated at exactly 0.0%. The year-over-year line crossed
      under last year in the final month. Every one of those said the reverse
      of what the data says: four days at that rate is ABOVE the run rate,
      not a collapse.

      WHAT WE DO NOT DO. We do not extrapolate the partial month to a
      full-month figure, and we do not annualise it. A projection is a number
      no source states, and this tracker publishes only numbers its sources
      state. The partial figure is shown as exactly what it is.

      THE TREATMENT IS THE SAME ON ALL THREE CHARTS, on purpose: one rule a
      reader learns once. The in-progress month is
        (a) LABELLED as partial, on the axis where the labels are per-month
            and in the legend where they are not (the year-over-year chart
            shares one "Aug" label between two years, so suffixing the axis
            there would libel last year's completed August), and
        (b) DRAWN DASHED, the same dash this page already uses for "not the
            verified floor", with a visible marker on the point, and
        (c) NAMED under the chart in a sentence that gives the elapsed days.

      Styling alone was not judged enough. A dashed final segment is legible
      to someone studying the chart and invisible to someone screenshotting
      it, so the words carry the meaning and the dash reinforces it.
    */
    function nowMonthKey() {
        var now = new Date();
        return now.getFullYear() + '-' + pad2(now.getMonth() + 1);
    }

    // Where the in-progress month sits in a list of month keys, or null if the
    // charted window does not reach it (a filtered past year, say).
    // `rows` are the CLAMPED series rows (post toDateMonths), so the note can
    // state the number actually plotted and the number held back, instead of
    // describing elapsed days over a value that is not elapsed days.
    function partialMonthAt(monthKeys, rows) {
        var key = nowMonthKey();
        var idx = (monthKeys || []).indexOf(key);
        if (idx === -1) return null;
        var now = new Date();
        var info = {
            key: key, index: idx,
            days: now.getDate(),
            of: daysInMonth(now.getFullYear(), now.getMonth() + 1),
            charted: null, later: null
        };
        (rows || []).forEach(function (s) {
            if (!s || s.month !== key) return;
            info.charted = (s.verified_jobs != null) ? s.verified_jobs : (s.jobs || 0);
            if (s.full) {
                var fullV = (s.full.verified_jobs != null) ? s.full.verified_jobs : (s.full.jobs || 0);
                info.later = Math.max(0, fullV - info.charted);
            } else {
                info.later = 0;
            }
        });
        return info;
    }

    function partialLabel(info) {
        return monthLabel(info.key) + ' (partial)';
    }

    /*
      The sentence under the chart. States the elapsed days and refuses the
      comparison, rather than making one.

      WHY IT TAKES A MODE. The treatment of the in-progress month is the same
      on all three charts, and for a while so was the sentence: 435 bytes,
      byte-identical, printed three times inside about 950px of scroll. That
      did not read as three captions. It read as a template that had fired
      three times, and the third copy of a paragraph is where a reader stops
      reading the paragraph at all - including the sentence naming the 11,083
      cuts that are filed but not yet in effect, which is the part they most
      need.

      The fix is not a shorter duplicate. The three charts plot three
      different quantities, so each note now describes the point it sits
      under, and the repetition was the symptom of them not doing that:

        'jobs'  (Jobs cut per month) - the full account. This is the chart
                whose y-axis IS the job count, so it is the one that can say
                what the point counts and what is still to come. Unchanged,
                to the byte.
        'year'  (This year vs last year) - the same quantity split by year.
                Names what the final point counts, and drops the filed-later
                clause: the comparison it invites is with last year's finished
                August, not with the rest of this one.
        'share' (AI share of verified cuts) - a percentage. Quoting a job
                count under a percent line was always a category error; what
                a reader needs is the size of the base the share is computed
                on, and that it is not a projection.

      Default is 'jobs', so a one-argument call is the old behaviour exactly.
    */
    function partialNoteText(info, mode) {
        var opened = monthLabel(info.key) + ' is still in progress: ' + info.days + ' of '
            + info.of + ' days so far.';
        if (mode === 'share') {
            var base = (info.charted != null)
                ? ' The share for this month is computed on the ' + fmt(info.charted)
                    + ' verified job cuts whose effective date has arrived, not on a whole month.'
                : '';
            return opened + base + ' The point is dashed for that reason, and it is not a projection'
                + ' of the full month.';
        }
        if (mode === 'year') {
            var counts = (info.charted != null)
                ? ' The final point for this year counts the ' + fmt(info.charted)
                    + ' verified job cuts whose effective date has arrived.'
                : '';
            return opened + counts + ' It is dashed because a part month is not comparable with the'
                + ' completed month beside it, and it is not a projection of the full month.';
        }
        var txt = opened;
        if (info.charted != null) {
            txt += ' This point counts the ' + fmt(info.charted)
                + ' verified job cuts whose effective date has arrived.';
        }
        if (info.later) {
            txt += ' A further ' + fmt(info.later) + ' are on notices already filed for effective dates later in '
                + monthLabel(info.key).split(' ')[0]
                + '; those are in the table and the totals, and join this point as their dates pass.';
        }
        return txt + ' The point is dashed because a part month is not comparable with the completed'
            + ' months beside it, and it is not a projection of the full month.';
    }

    function setPartialNote(elId, info, mode) {
        var el = document.getElementById(elId);
        if (!el) return;
        el.textContent = info ? partialNoteText(info, mode) : '';
        el.hidden = !info;
    }

    // Dash the segment that ENDS on the partial point and put a marker on it.
    // Chart.js 4 scriptable options; `undefined` from a segment callback falls
    // back to the dataset's own borderDash, so a line that is already dashed
    // (the announced-plans series) keeps its dash everywhere else.
    function markPartialPoint(ds, idx) {
        var basePoint = ds.pointRadius;
        ds.segment = ds.segment || {};
        ds.segment.borderDash = function (ctx) {
            return ctx.p1DataIndex === idx ? [3, 3] : undefined;
        };
        ds.pointRadius = function (ctx) {
            return ctx.dataIndex === idx ? 4 : (typeof basePoint === 'number' ? basePoint : 0);
        };
        ds.pointBackgroundColor = function (ctx) {
            return ctx.dataIndex === idx ? tok('surface', '#fff') : ds.borderColor;
        };
        ds.pointBorderColor = ds.borderColor;
        ds.pointBorderWidth = function (ctx) { return ctx.dataIndex === idx ? 2 : 0; };
        return ds;
    }

    function fillMonths(series) {
        if (!series || !series.length) return [];
        // Cut the in-progress month at today before anything plots it. Every
        // chart that reaches the current month goes through here.
        series = toDateMonths(series);
        var map = {};
        series.forEach(function (s) { map[s.month] = s; });

        var from = readControl('alt-f-from');
        var to = readControl('alt-f-to');
        var years = (readControl('alt-f-years') || []).slice().sort();
        var start, end;
        if (from && /^\d{4}-\d{2}/.test(from)) start = from.slice(0, 7);
        else if (years.length) start = years[0] + '-01';
        else start = series[0].month;
        if (to && /^\d{4}-\d{2}/.test(to)) end = to.slice(0, 7);
        else if (years.length) end = years[years.length - 1] + '-12';
        else end = series[series.length - 1].month;

        // Hard-cap the chart at the CURRENT month (owner decision 2026-07-18):
        // months that haven't happened yet made the trend read as a year of
        // collapse. Future-dated notices stay in the stats and table; the
        // renderers surface an "excludes future-dated" note when any exist.
        // The cap advances automatically as months roll over.
        var now = new Date();
        var nowKey = now.getFullYear() + '-' + pad2(now.getMonth() + 1);
        if (end > nowKey) end = nowKey;
        if (end < start) return series.filter(function (s) { return s.month <= nowKey; });

        var out = [];
        var y = parseInt(start.slice(0, 4), 10), m = parseInt(start.slice(5, 7), 10);
        var ey = parseInt(end.slice(0, 4), 10), em = parseInt(end.slice(5, 7), 10);
        var guard = 0;
        while ((y < ey || (y === ey && m <= em)) && guard++ < 600) {
            if (periodAllowsMonth(y, m)) {
                var k = y + '-' + pad2(m);
                out.push(map[k] || { month: k, jobs: 0, ai_jobs: 0 });
            }
            m++; if (m > 12) { m = 1; y++; }
        }
        return out.length ? out : series;
    }

    // When compared series differ by orders of magnitude (Australia 6,200 vs
    // Austria 40), the small ones flatten into the axis on a linear scale.
    // Switch to log when the spread exceeds ~25x; zeros become gaps (log has
    // no zero), tooltips stay exact.
    // Legend labels carry each compared series' total ("Canada (1,842)",
    // "Austria (0)") so flat-at-zero lines are identifiable without hovering.
    function labelWithTotals(datasets) {
        datasets.forEach(function (d) {
            var tot = d.data.reduce(function (a, v) { return a + (v || 0); }, 0);
            d.label = d.label + ' (' + fmt(tot) + ')';
        });
    }

    function labelWithFinal(datasets) {
        datasets.forEach(function (d) {
            var fin = 0;
            d.data.forEach(function (v) { if (v != null) fin = v; });
            d.label = d.label + ' (' + fmt(fin) + ')';
        });
    }

    function applyLogIfSpread(datasets, options) {
        var maxes = datasets.map(function (d) {
            return d.data.reduce(function (m, v) { return (v != null && v > m) ? v : m; }, 0);
        }).filter(function (v) { return v > 0; });
        if (maxes.length < 2) return false;
        var hi = Math.max.apply(null, maxes), lo = Math.min.apply(null, maxes);
        if (!(lo > 0) || hi / lo <= 25) return false;
        options.scales.y.type = 'logarithmic';
        datasets.forEach(function (d) {
            d.data = d.data.map(function (v) { return v === 0 ? null : v; });
            d.spanGaps = true;
        });
        return true;
    }

    var CMP_SEQ = 0;
    // Which compare dimension the visitor touched last. Without this, a
    // leftover multi-country selection silently swallowed every year pick
    // (the trend chart kept "comparing Germany · United States" no matter
    // which years were chosen).
    var LAST_MULTI_DIM = null;
    function compareSelections() {
        var years = (readControl('alt-f-years') || []).slice().sort().slice(0, 8);
        var countries = (readControl('alt-f-country') || []).slice(0, 8);
        var yearsOk = years.length >= 2, countriesOk = countries.length >= 2;
        if (yearsOk && countriesOk) {
            return LAST_MULTI_DIM === 'years' ? { dim: 'years', values: years } : { dim: 'country', values: countries };
        }
        if (countriesOk) return { dim: 'country', values: countries };
        if (yearsOk) return { dim: 'years', values: years };
        return null;
    }

    // When several years or countries are selected, the trend chart breaks
    // each one out as its own colored line instead of one merged blob, so
    // selections can be cross-referenced directly.
    function renderCompareTrend(cmp) {
        var seq = ++CMP_SEQ;
        Promise.all(cmp.values.map(function (v) {
            var params = currentParams();
            params[cmp.dim === 'years' ? 'years' : 'country'] = v;
            return apiGet('aggregate', params).then(function (a) { return toDateMonths((a && a.series) || []); });
        })).then(function (lists) {
            if (seq !== CMP_SEQ) return;
            var labels, datasets;
            if (cmp.dim === 'years') {
                var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                labels = monthNames;
                datasets = cmp.values.map(function (y, i) {
                    var by = {};
                    lists[i].forEach(function (s) { by[parseInt(s.month.slice(5), 10)] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
                    return { label: String(y), data: monthNames.map(function (_, m) { return by[m + 1] || 0; }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.3 };
                });
            } else {
                var monthSet = {};
                lists.forEach(function (l) { l.forEach(function (s) { monthSet[s.month] = 1; }); });
                var months = Object.keys(monthSet).sort();
                var nowKey = new Date().getFullYear() + '-' + pad2(new Date().getMonth() + 1);
                months = months.filter(function (m) { return m <= nowKey; });
                labels = months.map(monthLabel);
                datasets = cmp.values.map(function (c, i) {
                    var by = {};
                    lists[i].forEach(function (s) { by[s.month] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
                    return { label: c, data: months.map(function (m) { return by[m] || 0; }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: months.length <= 2 ? 4 : 0, pointHitRadius: 12, fill: false, tension: 0.3 };
                });
            }
            var range = document.getElementById('alt-trend-range');
            var options = cloneOptions();
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || '') + ': ' + fmt(ctx.parsed.y); } };
            var logOn = applyLogIfSpread(datasets, options);
            labelWithTotals(datasets);
            if (range) range.textContent = 'comparing ' + cmp.values.join(' · ') + ' · verified cuts' + (logOn ? ' · log scale so small series stay visible' : '');
            mountChart('alt-chart-weekly', { type: 'line', data: { labels: labels, datasets: datasets }, options: options });
        }).catch(function () { /* combined view already rendered as fallback */ });
    }

    function renderTrend(series) {
        if (!document.getElementById('alt-chart-weekly')) return;
        // Clear first so a note never survives a re-render into a view it is
        // not true of (a past-year filter, or the compare mode below).
        setPartialNote('alt-trend-partial', null);
        var cmp = compareSelections();
        if (cmp) { renderCompareTrend(cmp); return; }
        var futureJobs = futureDatedJobs(series);
        series = fillMonths(series);
        var range = document.getElementById('alt-trend-range');
        if (range) range.textContent = (series.length
            ? monthLabel(series[0].month) + ' – ' + monthLabel(series[series.length - 1].month) : '');
        // The future-dated caveat lives inside the card's (i) disclosure when
        // the template provides one, so the visible caption stays two plain
        // sentences; without that span it stays on the range line as before.
        var futureEl = document.getElementById('alt-trend-future');
        var futureTxt = futureJobs > 0 ? fmt(futureJobs) + ' future-dated jobs (announced plans and filed notices whose effective date has not arrived) are in the table and totals, but not charted.' : '';
        if (futureEl) futureEl.textContent = futureTxt;
        else if (range && futureJobs > 0) range.textContent += ' · ' + fmt(futureJobs) + ' future-dated jobs in the table, not charted';
        if (!series || !series.length) { clearChart('alt-chart-weekly'); return; }
        // A Chart.js legend does not wrap or truncate: it draws its labels
        // centred and lets them run off the canvas. At 375px this card's plot
        // is ~177px, and "Announced plans (not yet in the verified floor)"
        // rendered as "ounced plans (not yet in the verifie". Shorter labels
        // only where that happens; the full wording stays everywhere else,
        // because the distinction it draws is the point of the second line.
        // The note under the chart carries the long form at every width.
        var narrow = narrowChartBox(document.getElementById('alt-chart-weekly'));
        var options = cloneOptions();
        options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || 'Jobs cut') + ': ' + fmt(ctx.parsed.y); } };
        // Tap a month to scope the whole page to it (same Years/Months controls
        // the dropdowns write; tap again to clear). Canvas has no focusable
        // parts, so the keyboard route to this exact state is the Years +
        // Months dropdowns above, which is what this writes.
        options.onClick = function (evt, els) {
            if (els && els.length && series[els[0].index]) { pickMonth(series[els[0].index].month); refreshAll(); }
        };
        options.onHover = function (evt, els) {
            if (evt.native) evt.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
        };
        // Verified is the primary line (matches the main stat card); the
        // dashed announced line keeps plan-stage months (incl. future WARN
        // effective dates) visible without mixing the two numbers.
        var verified = series.map(function (s) { return (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
        var announced = series.map(function (s) { return s.announced_jobs || 0; });
        // A single-month filter yields one data point; with pointRadius 0 a
        // lone point renders as literally nothing and the chart looks stale.
        var dots = series.length <= 2 ? 4 : 0;
        // The in-progress month, if the charted window reaches it.
        var partial = partialMonthAt(series.map(function (s) { return s.month; }), series);
        setPartialNote('alt-trend-partial', partial);
        var datasets = [{ label: 'Verified job cuts', data: verified, borderColor: SEQ_BLUE, backgroundColor: SEQ_BLUE_FILL, borderWidth: 2, pointRadius: dots, pointHitRadius: 12, fill: true, tension: 0.3 }];
        if (announced.some(function (v) { return v > 0; })) {
            // UN-stacked: the blue filled area is the verified floor (the number
            // we stand behind); announced plans are a separate DASHED line, not
            // piled on top — they are forward-looking signal that hasn't landed
            // in the floor yet. Keeping them apart avoids reading the amber edge
            // as part of the verified count.
            datasets.push({ label: narrow ? 'Announced plans' : 'Announced plans (not yet in the verified floor)', data: announced, borderColor: ALT_AMBER, backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 4], pointRadius: dots, pointHitRadius: 12, fill: false, tension: 0.3 });
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
        }
        // Optional macro-context overlay: jobless claims as muted bars on a
        // SEPARATE right axis (different unit AND ~15x scale — never blended
        // with the layoff line). Toggle-gated (ON by default), drawn behind.
        var claimsTog = document.getElementById('alt-claims-toggle');
        if (claimsTog && claimsTog.checked && CLAIMS_DATA) {
            var cl = claimsAligned(series.map(function (s) { return s.month; }));
            if (cl) {
                datasets.push({
                    type: 'bar', label: narrow ? cl.label : cl.label + ' (context)', data: cl.data, yAxisID: 'y1',
                    backgroundColor: 'rgba(' + tok('claims-rgb', '130,130,130') + ',0.13)', borderColor: 'rgba(' + tok('claims-rgb', '130,130,130') + ',0.20)',
                    borderWidth: 0, order: 99, barPercentage: 0.9, categoryPercentage: 0.96
                });
                // NARROW CARDS DROP THE AXIS TITLE AND SHORTEN THE CLAIMS
                // TICKS. At 375px this card is about 190px wide, and there the
                // rotated title landed ON TOP of its own tick labels with its
                // first words clipped off the edge, while "2,000,000" is the
                // widest string on the card at seven characters. Between them
                // they were taking more of the card than the plot. The legend
                // under the chart already names the series and the note under
                // it explains the right axis, so nothing is lost by dropping a
                // label that was unreadable anyway.
                options.scales.y1 = {
                    position: 'right', beginAtZero: true, grid: { display: false },
                    ticks: { color: INK.muted, callback: fmtAxis },
                    title: { display: !narrow, text: 'jobless claims per month', color: INK.muted, font: { size: 10 } }
                };
                options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            }
        }
        // Mark the partial month on every LINE series (the claims overlay is a
        // bar on its own axis and is left alone), and suffix its axis label.
        if (partial) {
            datasets.forEach(function (ds) { if (ds.type !== 'bar') markPartialPoint(ds, partial.index); });
        }
        mountChart('alt-chart-weekly', {
            type: 'line',
            data: {
                labels: series.map(function (s) {
                    return (partial && s.month === partial.key) ? partialLabel(partial) : monthLabel(s.month);
                }),
                datasets: datasets
            },
            options: options
        });
    }

    /* The whole-record trajectory strip -------------------------------- */
    /*
      WHY THIS EXISTS. The page opens filtered to the current calendar year, so
      the chart above opens with the months of that year and nothing else: five
      points in May, eight on 1 August, one on 1 January (which is why the
      renderer above has to switch point markers back on below three points, or
      the card renders as an empty box). The table under it holds 307 months.
      A reader's first sight of the trend was therefore a handful of columns
      with a curve laid over them, and with the jobless-claims bars behind it,
      it read as a bar chart rather than a trajectory.

      The chart above is NOT changed to draw all 307 months. It is the filtered
      view, it says so, tapping a month scopes the page, and drawing months the
      filter excludes would put the chart at odds with the filter chips. So the
      shape over time is drawn beside it, and the filtered window is shaded on
      it, which is the question the reader actually has: where does the slice I
      am looking at sit on the whole record.

      THE TECHNIQUE IS THE SIBLING TALENT TRACKER'S, not a new one. Its trend
      card had the same problem for the same reason (a chart in a card narrower
      than its own axis labels) and the answer was to take the TEXT out of the
      drawing: the axis values and the two dates are HTML beside the SVG, so
      they stay CSS pixels in a 200px card, in an expanded card and on a phone,
      while the SVG holds geometry only. Grid and lines carry
      vector-effect="non-scaling-stroke" so a 2px line is 2px at any width, and
      the endpoint dots are a SECOND svg with no viewBox, so their radius is a
      real pixel rather than an ellipse stretched by preserveAspectRatio.

      NOTHING IS INTERPOLATED. A month with no matching row is a break in the
      path, never a zero and never a line drawn straight across it: we do not
      hold a figure for it, and joining the two months either side would draw a
      slope nothing measured. The count of those months is printed under the
      strip so a broken line reads as missing data rather than as a rendering
      fault.

      NO LEGEND. The two colours are the two the Chart.js legend directly above
      already names; a second key would be the same words twice.
    */
    var TJ = { revealed: false, observing: false, key: null, series: null, seq: 0 };
    var TJ_PERIOD_PARAMS = ['from', 'to', 'years', 'quarters', 'months'];

    function periodFiltered(params) {
        return TJ_PERIOD_PARAMS.some(function (k) {
            return params[k] != null && params[k] !== '';
        });
    }
    function withoutPeriod(params) {
        var out = {};
        Object.keys(params).forEach(function (k) {
            if (TJ_PERIOD_PARAMS.indexOf(k) === -1) out[k] = params[k];
        });
        return out;
    }
    function tjMonthSeq(startKey, endKey) {
        var out = [];
        var y = parseInt(startKey.slice(0, 4), 10), m = parseInt(startKey.slice(5, 7), 10);
        var ey = parseInt(endKey.slice(0, 4), 10), em = parseInt(endKey.slice(5, 7), 10);
        var guard = 0;
        while ((y < ey || (y === ey && m <= em)) && guard++ < 2400) {
            out.push(y + '-' + pad2(m));
            m++; if (m > 12) { m = 1; y++; }
        }
        return out;
    }
    // Zero-based, topped at a round number two steps up: 0 / 100k / 200k reads
    // instantly where 0 / 93k / 186k does not. Two steps rather than the
    // sibling's four because this strip is ~80px tall and five labels in that
    // column collide.
    function tjNiceMax(raw) {
        var max = Math.max(1, raw);
        var q = max / 2;
        var mag = Math.pow(10, Math.floor(Math.log(q) / Math.LN10));
        var mults = [1, 2, 2.5, 5, 10];
        for (var i = 0; i < mults.length; i++) {
            if (q <= mag * mults[i] + 1e-9) { q = mag * mults[i]; break; }
        }
        return 2 * q;
    }

    function observeTrajectoryReveal() {
        if (TJ.observing || TJ.revealed) return;
        var card = document.querySelector('.alt-trend-card');
        if (!card || !('IntersectionObserver' in window)) { TJ.revealed = true; renderTrendTrajectory(); return; }
        TJ.observing = true;
        var io = new IntersectionObserver(function (entries) {
            if (entries.some(function (e) { return e.isIntersecting; })) {
                io.disconnect();
                TJ.observing = false;
                TJ.revealed = true;
                renderTrendTrajectory();
            }
        }, { rootMargin: '1200px 0px' });
        io.observe(card);
    }

    /*
      COST. The whole-record series is a SECOND /aggregate call, and it asks for
      `include=series` only: one grouped monthly SUM plus the totals row the
      endpoint will not let a caller drop, against the ~31 statements the
      default aggregate runs. It is also fetched only once the card is near the
      viewport (the card sits ~9,600px down), so a visitor who never scrolls to
      the trend pays nothing, and the first paint is untouched. When no period
      filter is set the chart above IS the whole record, so the strip hides
      itself and makes no request at all. A failure hides the strip; a trend
      that could not be drawn must not become a trend drawn wrong.
    */
    function renderTrendTrajectory() {
        var box = document.getElementById('alt-trend-full');
        if (!box) return;
        var params = currentParams();
        if (!periodFiltered(params)) { box.hidden = true; return; }
        if (!TJ.revealed) { observeTrajectoryReveal(); return; }
        var rest = withoutPeriod(params);
        var key = qs(rest);
        if (TJ.key === key && TJ.series) { drawTrajectory(box, TJ.series); return; }
        var seq = ++TJ.seq;
        rest.include = 'series';
        apiGet('aggregate', rest).then(function (a) {
            if (seq !== TJ.seq) return;
            TJ.key = key;
            TJ.series = toDateMonths((a && a.series) || []);
            drawTrajectory(box, TJ.series);
        }).catch(function () { box.hidden = true; });
    }

    function drawTrajectory(box, full) {
        var nowKey = new Date().getFullYear() + '-' + pad2(new Date().getMonth() + 1);
        var rows = (full || []).filter(function (s) { return s.month && s.month <= nowKey; });
        if (rows.length < 2) { box.hidden = true; return; }
        var by = {};
        rows.forEach(function (s) { by[s.month] = s; });
        var keys = tjMonthSeq(rows[0].month, rows[rows.length - 1].month);
        if (keys.length < 2) { box.hidden = true; return; }

        var verified = function (s) { return (s.verified_jobs != null) ? s.verified_jobs : (s.jobs || 0); };
        var announced = function (s) { return s.announced_jobs || 0; };
        var peak = 0, peakRow = null, hasAnnounced = false;
        rows.forEach(function (s) {
            if (verified(s) > peak) { peak = verified(s); peakRow = s; }
            peak = Math.max(peak, announced(s));
            if (announced(s) > 0) hasAnnounced = true;
        });
        var max = tjNiceMax(peak);

        var W = 300, H = 90, padT = 3, padB = 3;
        var plotH = H - padT - padB;
        var n = keys.length;
        var x = function (i) { return Math.round(W * i / (n - 1)); };
        var y = function (v) { return Math.round(padT + plotH - (plotH * Math.min(v, max) / max)); };

        // Contiguous runs only. A run of one month is drawn as a zero-length
        // line so the round cap renders it as a dot: an isolated month must be
        // visible, and a bare moveto draws nothing at all.
        function pathFor(pick) {
            var segs = [], cur = null;
            keys.forEach(function (k, i) {
                var row = by[k];
                if (!row) { cur = null; return; }
                var pt = x(i) + ' ' + y(pick(row));
                if (!cur) { cur = [pt]; segs.push(cur); } else cur.push(pt);
            });
            return segs.map(function (s) {
                return 'M' + s[0] + (s.length === 1 ? ' L' + s[0] : ' L' + s.slice(1).join(' L'));
            }).join(' ');
        }

        // The months the chart above is currently drawing, marked on the whole
        // record. Runs, not one span: a Quarter or Month filter selects months
        // that are not next to each other, and a single band across them would
        // shade months the page has excluded.
        var scoped = {};
        ((LAST_AGG && LAST_AGG.series) || []).forEach(function (s) {
            if (s.month && s.month <= nowKey) scoped[s.month] = 1;
        });
        var half = W / (n - 1) / 2;
        var bands = [], run = null;
        keys.forEach(function (k, i) {
            if (scoped[k]) { if (run) run[1] = i; else run = [i, i]; }
            else if (run) { bands.push(run); run = null; }
        });
        if (run) bands.push(run);
        // A one-month scope is one 296th of the span, which is under a pixel of
        // the drawn width and therefore no marker at all. The floor is 4 user
        // units (about 2.5 CSS px in the narrow card) so the marker is visible;
        // it is a pointer to a position, and the exact window is named in the
        // filter chips and the chart heading above it.
        var bandSvg = bands.map(function (b) {
            var x0 = Math.max(0, x(b[0]) - half), x1 = Math.min(W, x(b[1]) + half);
            var wide = Math.max(4, x1 - x0);
            return '<rect class="alt-tj-band" x="' + Math.min(x0, W - wide).toFixed(1)
                + '" y="0" width="' + wide.toFixed(1) + '" height="' + H + '"/>';
        }).join('');

        var gaps = keys.filter(function (k) { return !by[k]; }).length;
        var firstRow = by[keys[0]], lastRow = by[keys[n - 1]];
        var startLabel = monthLabel(keys[0]), endLabel = monthLabel(keys[n - 1]);
        var describe = 'Verified job cuts by month, ' + startLabel + ' to ' + endLabel + '. '
            + (firstRow ? fmt(verified(firstRow)) + ' in ' + startLabel + '. ' : '')
            + (lastRow ? fmt(verified(lastRow)) + ' in ' + endLabel + '. ' : '')
            + (gaps ? gaps + ' of these ' + n + ' months have no recorded event and are not drawn.' : '');

        var lines = '<path d="' + pathFor(verified) + '" class="alt-tj-line" stroke="' + SEQ_BLUE
            + '" vector-effect="non-scaling-stroke"/>';
        var dots = '<circle cx="100%" cy="' + (lastRow ? (100 * y(verified(lastRow)) / H).toFixed(1) : '50')
            + '%" r="3" fill="' + SEQ_BLUE + '"/>';
        if (hasAnnounced) {
            lines += '<path d="' + pathFor(announced) + '" class="alt-tj-line alt-tj-line-dash" stroke="'
                + ALT_AMBER + '" vector-effect="non-scaling-stroke"/>';
            if (lastRow) {
                dots += '<circle cx="100%" cy="' + (100 * y(announced(lastRow)) / H).toFixed(1)
                    + '%" r="3" fill="' + ALT_AMBER + '"/>';
            }
        }

        var grid = '';
        for (var g = 0; g <= 2; g++) {
            var gy = y(max * g / 2);
            grid += '<line x1="0" x2="' + W + '" y1="' + gy + '" y2="' + gy
                + '" class="alt-tj-grid" vector-effect="non-scaling-stroke"/>';
        }

        box.innerHTML =
            // The band is only mentioned when there is one to see. The charted
            // window can fall entirely on months this view holds nothing for,
            // and pointing at a marker that is not drawn is worse than silence.
            '<div class="alt-tj-h">The whole record <span>every month we hold under these filters'
            + (bands.length ? '. The shaded band is the period charted above.' : '.') + '</span></div>'
            + '<div class="alt-tj-plot">'
            + '<div class="alt-tj-ys" aria-hidden="true"><span>' + escapeHtml(fmtCompact(max))
            + '</span><span>' + escapeHtml(fmtCompact(max / 2)) + '</span><span>0</span></div>'
            + '<div class="alt-tj-box">'
            + '<svg class="alt-tj-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none"'
            + ' role="img" aria-label="' + escapeHtml(describe) + '">'
            + bandSvg + grid + lines + '</svg>'
            + '<svg class="alt-tj-dots" aria-hidden="true" focusable="false">' + dots + '</svg>'
            + '</div></div>'
            + '<p class="alt-tj-xs" aria-hidden="true"><span>' + escapeHtml(startLabel)
            + '</span><span>' + escapeHtml(endLabel) + '</span></p>'
            + '<p class="alt-tj-note">' + escapeHtml(
                (gaps
                    ? gaps + ' of these ' + fmt(n) + ' months have no event we can source, so the line breaks '
                        + 'there rather than being drawn as zero. '
                    : 'Every one of these ' + fmt(n) + ' months has at least one sourced event. ')
                /*
                  THE AXIS IS ZERO-BASED AND THE PEAK IS NAMED, which is one
                  decision rather than two. Over the full record one month
                  (Mar 2020, 709,906) is about seventy times the median, so a
                  true zero-based axis leaves two decades reading as a low
                  band under one tower. That IS the shape of this dataset and
                  rescaling to hide it would be the lie; what a reader cannot
                  do is tell whether a flat-looking stretch is a quiet market
                  or a broken chart. Naming the tallest month answers that in
                  words, at no cost to the drawing.
                */
                + (peakRow ? 'Tallest month: ' + monthLabel(peakRow.month) + ', at '
                    + fmt(verified(peakRow)) + ' verified cuts, against a scale that starts at zero.' : ''))
            + '</p>';
        box.hidden = false;
    }

    // Align the claims series to the chart's months; national by default, or the
    // selected US state's claims when exactly one US state is filtered.
    function claimsAligned(monthKeys) {
        if (!CLAIMS_DATA || !CLAIMS_DATA.national) return null;
        var stSel = readControl('alt-f-state'), st = null;
        if (Array.isArray(stSel) && stSel.length === 1) st = stSel[0];
        else if (typeof stSel === 'string' && stSel) st = stSel;
        var src, label;
        if (st && CLAIMS_DATA.states && CLAIMS_DATA.states[st] && CLAIMS_DATA.states[st].length) {
            src = CLAIMS_DATA.states[st]; label = st + ' initial jobless claims';
        } else {
            src = CLAIMS_DATA.national.initial || []; label = 'US initial jobless claims';
        }
        var map = {};
        src.forEach(function (p) { map[p.month] = p.value; });
        var data = monthKeys.map(function (m) { return map[m] != null ? map[m] : null; });
        return data.some(function (v) { return v != null; }) ? { data: data, label: label } : null;
    }

    // "Jobless claims by US state": official DOL initial claims, latest month,
    // every state, ranked. Deliberately GREY (not the layoff blue/orange) and
    // deliberately NOT wired to the filters — it is a different universe shown
    // for context, so it must never look like a filterable layoff chart.
    function renderClaimsStates() {
        var box = document.getElementById('alt-bars-claims-states');
        var card = document.getElementById('alt-claims-states-card');
        if (!box || !card || !CLAIMS_DATA || !CLAIMS_DATA.states) return;
        var rows = [];
        Object.keys(CLAIMS_DATA.states).forEach(function (st) {
            var series = CLAIMS_DATA.states[st] || [];
            if (!series.length) return;
            var last = series[series.length - 1];
            if (last && last.value != null) rows.push({ st: st, month: last.month, value: last.value });
        });
        if (!rows.length) return;
        rows.sort(function (a, b) { return b.value - a.value; });
        var max = rows[0].value || 1;
        var latest = rows.reduce(function (m, r) { return r.month > m ? r.month : m; }, '');
        var monthEl = document.getElementById('alt-claims-states-month');
        if (monthEl && latest) monthEl.textContent = monthLabel(latest);
        box.innerHTML = rows.map(function (r) {
            var pct = Math.max(1, Math.round(100 * r.value / max));
            // States publish on slightly different lags; when a state's latest
            // point is older than the headline month, say so on the value
            // instead of silently ranking a May figure in a June list.
            var lag = (r.month && latest && r.month < latest) ? ' <small>(' + escapeHtml(monthLabel(r.month)) + ')</small>' : '';
            return '<div class="alt-barrow" role="listitem">'
                + '<div class="alt-barrow-top"><span class="alt-barrow-name">' + escapeHtml(r.st) + '</span>'
                + '<span class="alt-barrow-val">' + fmt(r.value) + lag + '</span></div>'
                + '<div class="alt-bartrack"><div style="width:' + pct + '%;height:100%;border-radius:inherit;background:#9aa0ab"></div></div>'
                + '</div>';
        }).join('');
        card.hidden = false;
    }

    // Fetch the claims backdrop once, reveal the toggle, redraw the trend on flip.
    // Fail-soft: no claims data => toggle stays hidden and nothing changes.
    function initClaimsOverlay() {
        var tog = document.getElementById('alt-claims-toggle');
        if (!tog) return;
        apiGet('claims', {}).then(function (d) {
            if (!d || !d.national || !((d.national.initial || []).length)) return;
            CLAIMS_DATA = d;
            var wrap = document.getElementById('alt-claims-toggle-wrap');
            if (wrap) wrap.hidden = false;
            var note = document.getElementById('alt-claims-note');
            function syncNote() { if (note) note.hidden = !tog.checked; }
            syncNote();
            tog.addEventListener('change', function () { syncNote(); if (LAST_AGG) renderTrend(LAST_AGG.series); });
            // The toggle defaults ON, but the first trend render ran before the
            // claims data loaded — redraw now so the overlay appears without a click.
            if (tog.checked && LAST_AGG) renderTrend(LAST_AGG.series);
            renderClaimsStates();
        }).catch(function () {});
    }

    // Monthly AI share of verified cuts, as a percent line.
    // Year-over-year: this selection's verified line vs the same filters one
    // year earlier (dashed grey). Shown when exactly one year is in scope.
    var YOY_SEQ = 0;
    function renderYoY(series) {
        var box = document.getElementById('alt-chart-yoy');
        if (!box) return;
        setPartialNote('alt-yoy-partial', null);
        var years = readControl('alt-f-years') || [];
        var seq = ++YOY_SEQ;
        var nowYearNum = new Date().getFullYear();
        if (years.length >= 2) {
            var picked = years.slice().sort().slice(0, 8);
            var nowKey2 = pad2(new Date().getMonth() + 1);
            var mm = ['01','02','03','04','05','06','07','08','09','10','11','12'];
            Promise.all(picked.map(function (yr) {
                var p = currentParams();
                p.years = String(yr);
                return apiGet('aggregate', p).then(function (a) { return toDateMonths((a && a.series) || []); });
            })).then(function (lists) {
                if (seq !== YOY_SEQ) return;
                // This chart's x-axis is bare month names shared by every year,
                // so "(partial)" cannot go there: it would label last year's
                // completed August as partial too. It goes on the legend entry
                // for the current year, which is the only series it is true of.
                var yoyPartial = partialMonthAt([nowYearNum + '-' + nowKey2],
                    lists[picked.indexOf(String(nowYearNum))] || []);
                setPartialNote('alt-yoy-partial', picked.indexOf(String(nowYearNum)) === -1 ? null : yoyPartial, 'year');
                var datasets = picked.map(function (yr, i) {
                    var by = {};
                    lists[i].forEach(function (s) { by[s.month.slice(5)] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
                    var isNow = parseInt(yr, 10) === nowYearNum;
                    var ds = { label: String(yr) + (isNow && yoyPartial ? ' (' + MONTHS[parseInt(nowKey2, 10) - 1] + ' partial)' : ''),
                        data: mm.map(function (m) { return (isNow && m > nowKey2) ? null : (by[m] || 0); }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.3 };
                    if (isNow && yoyPartial) markPartialPoint(ds, parseInt(nowKey2, 10) - 1);
                    return ds;
                });
                if (!datasets.some(function (d) { return d.data.some(function (v) { return v > 0; }); })) { clearChart('alt-chart-yoy'); return; }
                var options = cloneOptions();
                options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
                options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || '') + ': ' + fmt(ctx.parsed.y); } };
                applyLogIfSpread(datasets, options);
                labelWithTotals(datasets);
                mountChart('alt-chart-yoy', { type: 'line', data: {
                    labels: mm.map(function (m) { return monthLabel('2000-' + m).split(' ')[0]; }), datasets: datasets
                }, options: options });
            }).catch(function () { clearChart('alt-chart-yoy'); });
            return;
        }
        var year = years.length === 1 ? parseInt(years[0], 10) : nowYearNum;
        var params = currentParams();
        params.years = String(year - 1);
        apiGet('aggregate', params).then(function (prev) {
            if (seq !== YOY_SEQ) return;
            var cur = {}, old = {};
            toDateMonths(series || []).forEach(function (s) { cur[s.month.slice(5)] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
            toDateMonths((prev && prev.series) || []).forEach(function (s) { old[s.month.slice(5)] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
            var months = ['01','02','03','04','05','06','07','08','09','10','11','12'];
            var nowKey = pad2(new Date().getMonth() + 1);
            var labels = months.map(function (m) { return monthLabel(year + '-' + m).split(' ')[0]; });
            var curData = months.map(function (m) { return (year === new Date().getFullYear() && m > nowKey) ? null : (cur[m] || 0); });
            var oldData = months.map(function (m) { return old[m] || 0; });
            if (!curData.some(function (v) { return v > 0; }) && !oldData.some(function (v) { return v > 0; })) { clearChart('alt-chart-yoy'); return; }
            var options = cloneOptions();
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || '') + ': ' + fmt(ctx.parsed.y); } };
            // Only the current year has an unfinished month, and only when the
            // chart is actually showing the current year. Without this the
            // final point dropped the line under last year's completed one.
            var yoyPartial1 = (year === new Date().getFullYear())
                ? partialMonthAt([year + '-' + nowKey], toDateMonths(series || [])) : null;
            setPartialNote('alt-yoy-partial', yoyPartial1, 'year');
            var curDs = { label: String(year) + (yoyPartial1 ? ' (' + MONTHS[parseInt(nowKey, 10) - 1] + ' partial)' : ''), data: curData, borderColor: SEQ_BLUE, backgroundColor: SEQ_BLUE_FILL, borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: true, tension: 0.3 };
            if (yoyPartial1) markPartialPoint(curDs, parseInt(nowKey, 10) - 1);
            mountChart('alt-chart-yoy', { type: 'line', data: { labels: labels, datasets: [
                curDs,
                { label: String(year - 1), data: oldData, borderColor: CHART_DIM, borderDash: [6, 4], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.3 }
            ] }, options: options });
        }).catch(function () { clearChart('alt-chart-yoy'); });
    }

    var CMP_SHARE_SEQ = 0;
    function renderCompareAiShare(cmp) {
        var seq = ++CMP_SHARE_SEQ;
        Promise.all(cmp.values.map(function (v) {
            var params = currentParams();
            params[cmp.dim === 'years' ? 'years' : 'country'] = v;
            return apiGet('aggregate', params).then(function (a) { return toDateMonths((a && a.series) || []); });
        })).then(function (lists) {
            if (seq !== CMP_SHARE_SEQ) return;
            var share = function (srow) {
                var v = (srow.verified_jobs != null) ? srow.verified_jobs : srow.jobs;
                var ai = (srow.ai_verified_jobs != null) ? srow.ai_verified_jobs : (srow.ai_jobs || 0);
                return v > 0 ? Math.round(1000 * ai / v) / 10 : null;
            };
            var labels, datasets;
            var nowYearNum = new Date().getFullYear();
            var nowKey = pad2(new Date().getMonth() + 1);
            if (cmp.dim === 'years') {
                var mm = ['01','02','03','04','05','06','07','08','09','10','11','12'];
                labels = mm.map(function (mo) { return monthLabel('2000-' + mo).split(' ')[0]; });
                datasets = cmp.values.map(function (yr, i) {
                    var by = {};
                    lists[i].forEach(function (srow) { by[srow.month.slice(5)] = share(srow); });
                    return { label: String(yr),
                        data: mm.map(function (mo) { return (parseInt(yr, 10) === nowYearNum && mo > nowKey) ? null : (by[mo] != null ? by[mo] : null); }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.25, spanGaps: true };
                });
            } else {
                var monthSet = {};
                lists.forEach(function (l) { l.forEach(function (srow) { monthSet[srow.month] = 1; }); });
                var months = Object.keys(monthSet).sort().filter(function (mo) { return mo <= nowYearNum + '-' + nowKey; });
                labels = months.map(monthLabel);
                datasets = cmp.values.map(function (c, i) {
                    var by = {};
                    lists[i].forEach(function (srow) { by[srow.month] = share(srow); });
                    return { label: c, data: months.map(function (mo) { return by[mo] != null ? by[mo] : null; }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.25, spanGaps: true };
                });
            }
            if (!datasets.some(function (d) { return d.data.some(function (v) { return v > 0; }); })) { clearChart('alt-chart-ai-share-trend'); return; }
            var options = cloneOptions();
            options.scales.y.ticks.callback = function (v) { return v + '%'; };
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || '') + ': ' + ctx.parsed.y + '%'; } };
            mountChart('alt-chart-ai-share-trend', { type: 'line', data: { labels: labels, datasets: datasets }, options: options });
        }).catch(function () { /* merged view already rendered as fallback */ });
    }

    function renderAiShare(series) {
        if (!document.getElementById('alt-chart-ai-share-trend')) return;
        setPartialNote('alt-ai-share-partial', null);
        var cmpShare = compareSelections();
        if (cmpShare) { renderCompareAiShare(cmpShare); return; }
        series = fillMonths(series);
        var pts = (series || []).map(function (s) {
            var v = (s.verified_jobs != null) ? s.verified_jobs : s.jobs;
            var ai = (s.ai_verified_jobs != null) ? s.ai_verified_jobs : (s.ai_jobs || 0);
            return { month: s.month, v: v > 0 ? Math.round(1000 * ai / v) / 10 : null };
        });
        if (!pts.some(function (p) { return p.v > 0; })) { clearChart('alt-chart-ai-share-trend'); return; }
        // Same partial-month rule as the trend chart. This card is where the
        // artefact was worst: a month a few days old has a full denominator of
        // days-so-far and an AI numerator that usually has not landed yet, so
        // the line terminated at exactly 0.0% and read as attribution
        // collapsing rather than as a month that has barely started.
        var sharePartial = partialMonthAt(pts.map(function (p) { return p.month; }), series);
        setPartialNote('alt-ai-share-partial', sharePartial, 'share');
        var options = cloneOptions();
        options.scales.y.ticks.callback = function (v) { return v + '%'; };
        options.plugins.tooltip.callbacks = { label: function (ctx) { return 'AI share: ' + ctx.parsed.y + '%'; } };
        options.onClick = function (evt, els) {
            if (els && els.length && pts[els[0].index]) { pickMonth(pts[els[0].index].month); refreshAll(); }
        };
        options.onHover = function (evt, els) {
            if (evt.native) evt.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
        };
        var shareDs = { data: pts.map(function (p) { return p.v; }), borderColor: ALT_RED, backgroundColor: 'rgba(' + tok('ai-rgb', '213,94,0') + ',0.1)', borderWidth: 2, pointRadius: pts.length <= 2 ? 4 : 0, pointHitRadius: 12, fill: true, tension: 0.25, spanGaps: true };
        if (sharePartial) markPartialPoint(shareDs, sharePartial.index);
        mountChart('alt-chart-ai-share-trend', { type: 'line', data: {
            labels: pts.map(function (p) {
                return (sharePartial && p.month === sharePartial.key) ? partialLabel(sharePartial) : monthLabel(p.month);
            }),
            datasets: [shareDs]
        }, options: options });
    }

    var CMP_AI_SEQ = 0;
    function renderCompareAiCumulative(cmp) {
        var seq = ++CMP_AI_SEQ;
        Promise.all(cmp.values.map(function (v) {
            var params = currentParams();
            params[cmp.dim === 'years' ? 'years' : 'country'] = v;
            return apiGet('aggregate', params).then(function (a) { return toDateMonths((a && a.series) || []); });
        })).then(function (lists) {
            if (seq !== CMP_AI_SEQ) return;
            var aiVal = function (s) { return (s.ai_verified_jobs != null) ? s.ai_verified_jobs : (s.ai_jobs || 0); };
            var labels, datasets;
            var nowYearNum = new Date().getFullYear();
            var nowKey = pad2(new Date().getMonth() + 1);
            if (cmp.dim === 'years') {
                var mm = ['01','02','03','04','05','06','07','08','09','10','11','12'];
                labels = mm.map(function (m) { return monthLabel('2000-' + m).split(' ')[0]; });
                datasets = cmp.values.map(function (yr, i) {
                    var by = {};
                    lists[i].forEach(function (s) { by[s.month.slice(5)] = aiVal(s); });
                    var run = 0;
                    return { label: String(yr),
                        data: mm.map(function (m) { if (parseInt(yr, 10) === nowYearNum && m > nowKey) return null; run += by[m] || 0; return run; }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.25 };
                });
            } else {
                var monthSet = {};
                lists.forEach(function (l) { l.forEach(function (s) { if (aiVal(s) > 0) monthSet[s.month] = 1; }); });
                var months = Object.keys(monthSet).sort().filter(function (m) { return m <= nowYearNum + '-' + nowKey; });
                labels = months.map(monthLabel);
                datasets = cmp.values.map(function (c, i) {
                    var by = {};
                    lists[i].forEach(function (s) { by[s.month] = aiVal(s); });
                    var run = 0;
                    return { label: c, data: months.map(function (m) { run += by[m] || 0; return run; }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: months.length <= 2 ? 4 : 0, pointHitRadius: 12, fill: false, tension: 0.25 };
                });
            }
            var any = datasets.some(function (d) { return d.data.some(function (v) { return v > 0; }); });
            var range = document.getElementById('alt-cum-range');
            if (!labels.length || !any) {
                if (range) range.textContent = 'no AI-attributed cuts in this comparison';
                clearChart('alt-chart-ai-cumulative');
                return;
            }
            var options = cloneOptions();
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || '') + ': ' + fmt(ctx.parsed.y); } };
            var logOn = applyLogIfSpread(datasets, options);
            labelWithFinal(datasets);
            if (range) range.textContent = 'comparing ' + cmp.values.join(' · ') + ' · cumulative verified AI cuts' + (logOn ? ' · log scale so small series stay visible' : '');
            mountChart('alt-chart-ai-cumulative', { type: 'line', data: { labels: labels, datasets: datasets }, options: options });
        }).catch(function () { /* merged view already rendered as fallback */ });
    }

    function renderAiCumulative(series) {
        if (!document.getElementById('alt-chart-ai-cumulative')) return;
        var cmpAi = compareSelections();
        if (cmpAi) { renderCompareAiCumulative(cmpAi); return; }
        series = fillMonths(series);
        var ai = (series || []).filter(function (s) { return s.ai_jobs > 0; });
        var range = document.getElementById('alt-cum-range');
        if (range) range.textContent = ai.length
            ? 'since ' + monthLabel(ai[0].month) : '';
        if (!ai.length) { clearChart('alt-chart-ai-cumulative'); return; }
        // Two labeled lines mirroring the stat cards: the verified subset and
        // the announced-plan subset accumulate separately, never summed.
        var start = null;
        (series || []).forEach(function (s, i) { if (start === null && s.ai_jobs > 0) start = i; });
        var charted = (series || []).slice(start === null ? 0 : start);
        var runV = 0, runA = 0;
        var cumV = charted.map(function (s) { runV += (s.ai_verified_jobs != null) ? s.ai_verified_jobs : s.ai_jobs; return runV; });
        var cumA = charted.map(function (s) { runA += s.ai_announced_jobs || 0; return runA; });
        var options = cloneOptions();
        options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || 'Cumulative AI-attributed') + ': ' + fmt(ctx.parsed.y); } };
        var dots = charted.length <= 2 ? 4 : 0;
        var datasets = [{ label: 'AI-attributed (verified)', data: cumV, borderColor: ALT_RED, backgroundColor: 'rgba(' + tok('ai-rgb', '213,94,0') + ', 0.15)', borderWidth: 2, pointRadius: dots, pointHitRadius: 12, fill: true, tension: 0.25 }];
        if (cumA[cumA.length - 1] > 0) {
            datasets.push({ label: 'Announced AI plans, stacked on top', data: cumA, borderColor: ALT_AMBER, backgroundColor: 'rgba(' + tok('announced-rgb', '230,159,0') + ', 0.22)', borderWidth: 1.5, pointRadius: dots, pointHitRadius: 12, fill: true, tension: 0.25 });
            options.scales.y.stacked = true;
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            options.plugins.tooltip.callbacks.footer = function (items) {
                var total = items.reduce(function (s, it) { return s + it.parsed.y; }, 0);
                return items.length > 1 ? 'Total AI incl. plans: ' + fmt(total) : '';
            };
        }
        mountChart('alt-chart-ai-cumulative', {
            type: 'line',
            data: { labels: charted.map(function (s) { return monthLabel(s.month); }), datasets: datasets },
            options: options
        });
    }


    /* Announced-to-verified conversion card ---------------------------- */

    // The /conversion endpoint answers "do announced cuts actually happen?":
    // per announcement month, the share of announced jobs with verified
    // same-company records inside the window, capped per announcement. Not
    // filter-wired: the question is
    // about the whole announced tier, and recent months need their maturity
    // labels regardless of the active view.
    var CONVERSION_DATA = null;
    var CONVERSION_REQUESTED = false;
    function fetchConversionChart() {
        if (CONVERSION_REQUESTED) return;
        CONVERSION_REQUESTED = true;
        apiGet('conversion', {}).then(function (data) {
            CONVERSION_DATA = data;
            renderConversionChart();
        }).catch(function () { /* card stays empty; no fabricated series */ });
    }
    function initConversionChart() {
        var canvas = document.getElementById('alt-chart-conversion');
        if (!canvas || !chartsAvailable()) return;
        // The card sits far below the fold, so fetching it with the first
        // paint made every visitor pay a full REST round-trip for a chart
        // most never scroll to. Load it when the card approaches the viewport
        // instead (generous margin, so it is drawn before it is visible);
        // toggling the card is a second trigger, and browsers without
        // IntersectionObserver keep the old load-immediately behavior.
        var card = document.getElementById('alt-conversion-card') || canvas;
        card.addEventListener('toggle', fetchConversionChart);
        if (typeof IntersectionObserver === 'undefined') { fetchConversionChart(); return; }
        var io = new IntersectionObserver(function (entries) {
            if (entries.some(function (e) { return e.isIntersecting; })) {
                io.disconnect();
                fetchConversionChart();
            }
        }, { rootMargin: '1200px 0px' });
        io.observe(card);
    }
    function renderConversionChart() {
        var data = CONVERSION_DATA;
        if (!data || !document.getElementById('alt-chart-conversion') || !chartsAvailable()) return;
        var win = data.window_months || 6;
        // Future-dated plans (pending) cannot have converted yet; charting
        // them as 0% would read as broken promises. They stay in the CSV.
        var allRows = (data.series || []).filter(function (p) { return p.status !== 'pending' && p.conversion_pct !== null; });
        if (allRows.length < 2) return;
        // Default to a RECENT window: 288 months since 2002 makes current months
        // invisible, and the current ones (still maturing) are what readers want.
        // A toggle exposes the longer history; the full series stays in the CSV.
        var convRange = 24;
        function rowsForRange() {
            return convRange > 0 ? allRows.slice(-convRange) : allRows;
        }
        var rows = rowsForRange();
        var labels = rows.map(function (p) { return monthLabel(p.month); });
        function pickStatus(status) {
            return rows.map(function (p) { return p.status === status ? p.conversion_pct : null; });
        }
        var options = cloneOptions();
        options.scales.y.max = 100;
        options.scales.y.ticks.callback = function (v) { return v + '%'; };
        options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
        options.plugins.tooltip.callbacks = {
            label: function (ctx) {
                var p = rows[ctx.dataIndex];
                if (!p) return '';
                var lines = [
                    p.conversion_pct + '% of announced jobs had verified records within ' + win + ' months',
                    'Announced: ' + fmt(p.announced_jobs) + ' jobs in ' + fmt(p.announced_entries) + ' plans',
                    'Matched: ' + fmt(p.matched_jobs) + ' verified jobs'
                ];
                if (p.status === 'maturing') lines.push('Still maturing: the ' + win + ' month window is not over yet');
                return lines;
            }
        };
        // Same-slot stacking: each month has exactly one non-null dataset, so
        // the two datasets render as one bar per month while the legend
        // explains the two colors.
        options.scales.x.stacked = true;
        options.scales.y.stacked = true;
        mountChart('alt-chart-conversion', {
            type: 'bar',
            data: { labels: labels, datasets: [
                { label: 'Window complete (' + win + ' months elapsed)', data: pickStatus('complete'), backgroundColor: tok('verified', '#0072B2'), stack: 'conv' },
                { label: 'Still maturing (expected to rise)', data: pickStatus('maturing'), backgroundColor: tok('announced', '#E69F00'), stack: 'conv' }
            ] },
            options: options
        });
        document.querySelectorAll('.alt-conv-btn').forEach(function (b) {
            if (b.__convBound) return; b.__convBound = true;
            b.addEventListener('click', function () {
                convRange = parseInt(b.getAttribute('data-range'), 10) || 0;
                document.querySelectorAll('.alt-conv-btn').forEach(function (x) { x.classList.toggle('alt-conv-on', x === b); });
                rows = rowsForRange();
                labels = rows.map(function (p) { return monthLabel(p.month); });
                if (CHARTS['alt-chart-conversion']) {
                    var c = CHARTS['alt-chart-conversion'];
                    c.data.labels = labels;
                    c.data.datasets[0].data = pickStatus('complete');
                    c.data.datasets[1].data = pickStatus('maturing');
                    c.update();
                }
            });
        });
        var note = document.getElementById('alt-conversion-note');
        if (note) {
            note.style.display = '';
            note.textContent = 'Counts verified filings and sourced reports from the same company after each announcement, capped at the announced size. Orange months are still maturing. Those announcements have not had the full ' + win + ' months to show follow-through, so expect low bars there to rise. This is company-level corroboration, not proof a specific plan was completed or dropped. Unmatched jobs can still have happened through attrition or outside filing systems.';
        }
    }

    function renderBar(canvasId, entries, filterId, activeValue, tipPrefix) {
        if (!document.getElementById(canvasId)) return;
        entries = entries || [];
        if (!entries.length) { clearChart(canvasId); return; }
        var colors = paletteFor(entries).map(function (base, i) {
            return (activeValue && entries[i][0] !== activeValue) ? CHART_DIM : base;
        });
        var options = cloneOptions();
        options.indexAxis = 'y';
        options.scales = {
            x: { beginAtZero: true, grid: { color: INK.grid }, ticks: { color: INK.muted, callback: function (v) { return fmt(v); } } },
            y: { grid: { display: false }, ticks: { color: INK.secondary, autoSkip: false } }
        };
        options.plugins.tooltip.callbacks = { label: function (ctx) { return (tipPrefix || 'Jobs: ') + fmt(ctx.parsed.x); } };
        if (filterId) {
            options.onClick = function (evt, els) { if (els && els.length) { toggleSingleFilter(filterId, entries[els[0].index][0]); refreshAll(); } };
            options.onHover = function (evt, els) { if (evt.native) evt.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default'; };
        }
        mountChart(canvasId, {
            type: 'bar',
            data: {
                labels: entries.map(function (e) { return e[0]; }),
                datasets: [{ data: entries.map(function (e) { return e[1]; }), backgroundColor: colors, borderRadius: 4, maxBarThickness: 26 }]
            },
            options: options
        });
    }

    /*
      THE DOUGHNUT THAT WAS NOT A WHOLE, on a basis that was not the headline's.

      Two defects, both live until 2.19.265. It drew index [1] (verified PLUS
      announced) beside a headline counting verified only, and it was the one
      chart in the grid with no basis note. And a doughnut asserts a partition:
      these tags do not partition anything, because one event can carry several
      and most events carry none. On 2026-08-04 the slices summed to 660,320
      against a published 444,871.

      So it draws the verified pair now, like every other card, and the note
      says in plain words that the slices are not parts of a total.
    */
    function renderReasons(entries, filterId, activeValues) {
        if (!document.getElementById('alt-chart-reasons')) return;
        entries = verifiedBasis(entries || []);
        if (!entries.length) { clearChart('alt-chart-reasons'); setBarBasisNote('alt-chart-reasons-basis', ''); return; }
        setBarBasisNote('alt-chart-reasons-basis', reasonsBasisNote());
        var active = activeValues || [];
        // AI slices wear the AI accent hues used site-wide (vermillion for
        // company-stated, orange for broad/possible); other reasons draw from
        // the non-AI hues so the donut speaks the same color language as the
        // cards and bar fills.
        var REASON_COLORS = { ai_automation: ALT_RED, possible_ai: ALT_AMBER };
        var NEUTRAL_SEQ = [tok('verified', '#0072B2'), '#009E73', '#CC79A7', '#56B4E9', tok('chart-ink', '#000000'), '#999999', '#7A6A52', '#4A5E7A'];
        var neutralIdx = 0;
        var colors = entries.map(function (e) {
            var base = REASON_COLORS[e[0]] || NEUTRAL_SEQ[(neutralIdx++) % NEUTRAL_SEQ.length];
            return (active.length && active.indexOf(e[0]) === -1) ? CHART_DIM : base;
        });
        var options = {
            responsive: true, maintainAspectRatio: false, cutout: '62%',
            plugins: {
                // Bottom legend: items flow in rows, each label stays on one
                // line instead of truncating against the donut.
                legend: {
                    position: 'bottom', align: 'start',
                    labels: { color: INK.secondary, boxWidth: 9, boxHeight: 9, padding: 7, font: { size: 10.5 } }
                },
                tooltip: { callbacks: { label: function (ctx) { return ctx.label + ': ' + fmt(ctx.parsed) + ' jobs'; } } }
            }
        };
        if (filterId) {
            options.onClick = function (evt, els) { if (els && els.length) { toggleMultiFilter(filterId, entries[els[0].index][0]); refreshAll(); } };
            options.onHover = function (evt, els) { if (evt.native) evt.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default'; };
        }
        mountChart('alt-chart-reasons', {
            type: 'doughnut',
            data: {
                labels: entries.map(function (e) { return REASON_LABELS[e[0]] || e[0]; }),
                datasets: [{ data: entries.map(function (e) { return e[1]; }), backgroundColor: colors, borderColor: tok('surface', '#fcfcfb'), borderWidth: 2 }]
            },
            options: options
        });
    }

    function renderLeaderboard(leaders) {
        var box = document.getElementById('alt-leaderboard');
        if (!box) return;
        leaders = leaders || [];
        if (!leaders.length) { box.innerHTML = '<p class="alt-muted alt-empty">No data yet.</p>'; return; }
        var html = '<table class="alt-plain-table"><thead><tr><th>#</th><th>Company</th><th class="alt-num">Jobs</th><th>Date</th></tr></thead><tbody>';
        leaders.forEach(function (row, i) {
            var loc = row.state ? ' <span class="alt-state">' + escapeHtml(row.state) + '</span>' : '';
            html += '<tr><td class="alt-muted">' + (i + 1) + '</td><td>' + escapeHtml(row.company_name) + loc
                + (row.ai_explicit ? ' <span class="alt-ai-yes" title="Explicitly AI-attributed">AI</span>' : '')
                + '</td><td class="alt-num">' + fmt(row.job_count) + '</td><td>' + escapeHtml(row.layoff_date || '—') + '</td></tr>';
        });
        box.innerHTML = html + '</tbody></table>';
    }

    /* ------------------------------------------------------------------ */
    /* Results: a list of cards, fetched and paged SERVER-side              */
    /* ------------------------------------------------------------------ */
    /* This replaced a DataTables table in 2.19.226. DataTables was already
       running in serverSide mode, so it was never sorting or paging in the
       browser — /query did the ORDER BY and the LIMIT/OFFSET (db.php
       alt_api_query_compute) and DataTables only drew the chrome. What it did
       cost was a render-blocking stylesheet and 29KB of script from cdnjs, and
       a nine-column table that had to scroll sideways on a phone.

       The card is the sibling talent tracker's results card, so a reader
       moving between the two products meets one component: employer eyebrow,
       a badge row, the fact, our plain-English read of it, then the date and
       the source. The one thing this product adds is the job count as a
       prominent badge, which is the number a reader scans for and the thing a
       table genuinely did better than a card. */

    // `extra` carries the shared card contract's evidence class when this badge
    // is rendered inside a card (docs/card-contract.json, badges.card-ev). The
    // badge itself is unchanged everywhere else it appears.
    function verificationBadge(level, extra) {
        var safe = escapeHtml(level || 'bronze');
        return '<span class="' + (extra ? extra + ' ' : '') + 'alt-badge alt-badge-' + safe + '">'
            + escapeHtml(VERIF_LABELS[level] || 'News') + '</span>';
    }

    // The sort control is now the only sort UI. It always ordered the whole
    // filtered set, not the loaded page: these two params go to /query, which
    // has its own $sortable allowlist (layoff_date, job_count, company,
    // country, state, industry).
    var SORT_PARAMS = {
        newest:   ['layoff_date', 'desc'],
        oldest:   ['layoff_date', 'asc'],
        largest:  ['job_count', 'desc'],
        smallest: ['job_count', 'asc']
    };
    var PER_PAGE_CHOICES = [10, 25, 50, 100];

    var PAGE = 1, PER_PAGE = 25, TOTAL = 0, ROWS = [], QUERY_SEQ = 0;

    // Local calendar date, not UTC, so "upcoming" doesn't flip early or late
    // around midnight for a reader west of Greenwich.
    function todayLocal() {
        var n = new Date();
        return n.getFullYear() + '-' + pad2(n.getMonth() + 1) + '-' + pad2(n.getDate());
    }
    // The date the record carries, in the sibling's format (30 Jul 2026).
    // Split by hand rather than through Date(), which reads a bare YYYY-MM-DD
    // as UTC midnight and can show the previous day.
    function cardWhen(d) {
        var p = String(d || '').slice(0, 10).split('-');
        if (p.length !== 3) return '';
        return String(+p[2]) + ' ' + (MONTHS[+p[1] - 1] || '') + ' ' + p[0];
    }

    // The shared card vocabulary. MIRRORS direction_labels IN
    // docs/card-contract.json AND MUST STAY IDENTICAL TO IT, byte for byte, and
    // to the sibling talent tracker's DIRECTION_LABEL. Pinned by
    // railway/tests/test_card_contract.py; a change here that is not a change
    // there fails the build in both repos.
    //
    // Two of the four never appear on this product: everything it holds is a
    // cut, so there is no adding and no pay change. They are absent, never
    // renamed and never quietly reused for something else. The keys are ours
    // and are derived, not stored: this tracker has no signal_direction column.
    var DIRECTION_LABEL = {
        hiring: 'Adding Roles',
        displacement: 'Cutting Roles',
        comp_shift: 'Pay Change',
        neutral: 'Headcount Not Stated'
    };
    // A record that names a headcount is a cut we can size. One that does not is
    // the sibling's `neutral` bucket exactly: the source says nothing about
    // headcount. Saying that in the direction badge is why the card no longer
    // carries a second badge reading "Count not stated" beside it.
    function cardDirection(row) {
        return Number(row.job_count || 0) > 0 ? 'displacement' : 'neutral';
    }

    // Where the jobs were. The rail says so plainly, and says so out loud when
    // the record does not carry a place, rather than leaving the line blank.
    function cardWhere(row) {
        var bits = [];
        if (row.state) bits.push(String(row.state));
        if (row.country) bits.push(String(row.country));
        if (!bits.length) return '<span class="alt-card-nowhere">Location not stated</span>';
        return escapeHtml(bits.join(', '));
    }

    // The fact, in one line. A WARN notice filed for a future effective date,
    // and anything on the announced tier, has not happened yet: saying "cut"
    // of either would be the tracker asserting something it cannot.
    function cardHeadline(row) {
        var co = row.company_name ? String(row.company_name) : 'This employer';
        var n = Number(row.job_count || 0);
        var planned = !!row.announced || (row.layoff_date && row.layoff_date > todayLocal());
        var what = n > 0 ? (fmt(n) + ' job' + (n === 1 ? '' : 's')) : 'jobs';
        return co + (planned ? ' plans to cut ' : ' cut ') + what;
    }

    // Our plain-English read of the record, kept visually separate from the
    // fact above it (same convention as the sibling's read-through). The
    // stored excerpt is the most specific thing we have; the tier sentences
    // are the honest fallback when a row carries none.
    var VERIF_MEANING = {
        gold: 'Disclosed in an SEC filing, so the figure is the company’s own.',
        warn: 'Filed with the state as a legal WARN notice, so the size, date and location are on the public record. A WARN notice records the cut, not its cause.',
        silver: 'Announced by the company in its own release.',
        bronze: 'Reported by a named news source.'
    };
    function cardMeaning(row) {
        if (row.excerpt) return String(row.excerpt);
        return VERIF_MEANING[row.verification_level] || '';
    }

    // Publisher link first, archived copy second and never instead. The
    // publisher's own URL is the citation; the Internet Archive snapshot is
    // what keeps the evidence reachable when that URL moves or goes. Wording
    // matches the sibling so the two products read alike.
    function cardSourceLinks(row) {
        var arch = archivedCellLink(row);
        var name = escapeHtml(row.source_name || 'source');
        if (row.source_type === 'warn') {
            var wl = warnLinks(row);
            if (!wl.primary) return escapeHtml(row.source_name || 'Source not recorded');
            if (wl.exact) {
                var suffix = wl.list
                    ? ' <a href="' + escapeHtml(wl.list) + '" target="_blank" rel="noopener nofollow" class="alt-muted" title="The state’s official WARN list this notice is filed in">(list)</a>'
                    : '';
                return '<a href="' + escapeHtml(wl.primary) + '" target="_blank" rel="noopener nofollow" title="Opens this exact WARN notice">' + name + ' ↗</a>' + suffix + arch;
            }
            return '<a href="' + escapeHtml(wl.primary) + '" target="_blank" rel="noopener nofollow" title="Opens the state’s official WARN list, where this notice was filed. Many states publish a rolling file, so an older notice may have moved to the state’s annual archive. We captured the details shown here from the notice when it was filed.">' + name + ' ↗</a> <span class="alt-muted" title="The state’s official WARN list this notice was filed in">(list)</span>' + arch;
        }
        var url = safeUrl(row.source_url);
        if (!url) return escapeHtml(row.source_name || 'Source not recorded');
        return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow" title="Opens the primary source">' + name + ' ↗</a>' + arch;
    }

    function cardHtml(row, i) {
        var d = row.layoff_date || '';
        var when = cardWhen(d);
        var flags = '';
        if (d && d > todayLocal()) flags += '<span class="alt-upcoming" title="Filed in advance. The effective date has not arrived yet.">upcoming</span>';
        if (row.announced) flags += '<span class="alt-upcoming" title="Announcement of planned cuts, not yet executed or filed">announced</span>';

        // The stated / not-stated pair, which is the distinction this whole
        // tracker rests on. Never colour alone: each carries its words.
        var aiBadge = row.ai_explicit
            ? '<span class="alt-tag alt-tag-ai" title="The employer named AI or automation as a cause, in words we can quote">AI-attributed</span>'
            : '<span class="alt-tag alt-tag-quiet" title="No cause attributed to AI in this record">Cause not stated</span>';

        var tags = (Array.isArray(row.reason_tags) ? row.reason_tags : []).map(function (x) {
            return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[x] || x) + '</span>';
        }).join('');

        // Badge one of the shared contract: which way headcount moved, in the
        // words both trackers use.
        var dirKey = cardDirection(row);
        var dir = '<span class="alt-card-dir alt-card-dir-' + dirKey + '">'
            + escapeHtml(DIRECTION_LABEL[dirKey]) + '</span>';

        var n = Number(row.job_count || 0);
        // Badge three: the amount, and ONLY when there is one. When there is
        // not, the direction badge above has already said so and a second badge
        // repeating it was the duplicate the shared contract removed.
        // Real text, never a CSS ::after: a generated unit is not a dependable
        // thing for a screen reader to read, and a bare "1,200" says nothing.
        var jobs = n > 0
            ? '<span class="alt-card-amt alt-card-jobs">' + fmt(n) + '<span class="alt-card-jobs-unit"> jobs</span></span>'
            : '';

        // Blue only ever means clickable. The headline links to the entry's own
        // page when it has one (those permalinks were previously rendered
        // nowhere at all), and is plain ink when it does not.
        var perma = safeUrl(row.permalink);
        var head = perma
            ? '<a class="alt-card-h" href="' + escapeHtml(perma) + '">' + escapeHtml(cardHeadline(row)) + '</a>'
            : '<span class="alt-card-h alt-card-h-plain">' + escapeHtml(cardHeadline(row)) + '</span>';

        var meaning = cardMeaning(row);
        var industry = row.industry
            ? '<span class="alt-card-industry">' + escapeHtml(row.industry) + '</span>'
            : '';
        var ticker = row.ticker ? ' <span class="alt-ticker">' + escapeHtml(row.ticker) + '</span>' : '';

        return '<li class="alt-card" data-i="' + i + '">'
            + '<div class="alt-card-rail">'
            +   '<span class="alt-card-employer">' + escapeHtml(row.company_name || 'Employer not named') + ticker + '</span>'
            +   industry
            +   '<span class="alt-card-where">' + cardWhere(row) + '</span>'
            + '</div>'
            + '<div class="alt-card-body">'
            // Contract order: direction, evidence, amount. This product's own
            // badges (AI attribution, reason tags) follow them. See
            // docs/card-contract.json -> badges.order.
            +   '<div class="alt-card-badges">'
            +     dir + verificationBadge(row.verification_level, 'alt-card-ev') + jobs + aiBadge + tags
            +   '</div>'
            +   head
            +   (meaning ? '<p class="alt-card-rt">' + escapeHtml(meaning) + '</p>' : '')
            +   '<div class="alt-card-foot">'
            +     (when ? '<time class="alt-card-when" datetime="' + escapeHtml(d) + '">' + escapeHtml(when) + '</time>'
                        : '<span class="alt-card-when alt-card-nowhere">Date not stated</span>')
            +     flags
            +     '<span class="alt-card-src">' + cardSourceLinks(row) + '</span>'
            +     '<button type="button" class="alt-card-more" aria-expanded="false">Details</button>'
            +   '</div>'
            +   '<div class="alt-card-detail" hidden></div>'
            + '</div>'
            + '</li>';
    }

    function renderCards() {
        var list = document.getElementById('alt-cards');
        if (!list) return;
        list.setAttribute('aria-busy', 'false');
        if (!ROWS.length) {
            list.innerHTML = '<li class="alt-cards-empty">'
                + '<p class="alt-cards-empty-h">No layoffs match the current filters</p>'
                + '<p class="alt-cards-empty-p">We would rather show you nothing than guess.</p>'
                + '<button type="button" class="alt-cards-empty-clear">Reset all filters</button>'
                + '</li>';
            return;
        }
        list.innerHTML = ROWS.map(cardHtml).join('');
    }

    // Numbered pages, windowed so 2,547 pages do not print 2,547 buttons.
    function pageWindow(cur, last) {
        var out = [], i;
        var lo = Math.max(2, cur - 1), hi = Math.min(last - 1, cur + 1);
        out.push(1);
        if (lo > 2) out.push('gap');
        for (i = lo; i <= hi; i++) out.push(i);
        if (hi < last - 1) out.push('gap');
        if (last > 1) out.push(last);
        return out;
    }

    function renderPager() {
        var nav = document.getElementById('alt-pager');
        if (!nav) return;
        var last = Math.max(1, Math.ceil(TOTAL / PER_PAGE));
        if (!TOTAL) { nav.hidden = true; nav.innerHTML = ''; return; }
        nav.hidden = false;
        var html = '<button type="button" class="alt-page-btn alt-page-nav" data-page="' + (PAGE - 1) + '"'
            + (PAGE <= 1 ? ' disabled' : '') + '>Previous</button>';
        html += '<span class="alt-page-nums">';
        pageWindow(PAGE, last).forEach(function (p) {
            if (p === 'gap') { html += '<span class="alt-page-gap" aria-hidden="true">…</span>'; return; }
            html += '<button type="button" class="alt-page-btn' + (p === PAGE ? ' alt-page-on' : '') + '" data-page="' + p + '"'
                + (p === PAGE ? ' aria-current="page"' : '')
                + ' aria-label="Page ' + p + ' of ' + last + '">' + fmt(p) + '</button>';
        });
        html += '</span>';
        html += '<button type="button" class="alt-page-btn alt-page-nav" data-page="' + (PAGE + 1) + '"'
            + (PAGE >= last ? ' disabled' : '') + '>Next</button>';
        html += '<label class="alt-page-size"><span>Per page</span><select id="alt-per-page">'
            + PER_PAGE_CHOICES.map(function (n) {
                return '<option value="' + n + '"' + (n === PER_PAGE ? ' selected' : '') + '>' + n + '</option>';
            }).join('')
            + '</select></label>';
        nav.innerHTML = html;
    }

    function renderCount() {
        var el = document.getElementById('alt-table-count');
        if (!el) return;
        el.classList.toggle('alt-count-empty', !TOTAL);
        if (!TOTAL) { el.textContent = 'No layoffs match the current filters.'; return; }
        var start = (PAGE - 1) * PER_PAGE + 1;
        var end = Math.min(TOTAL, PAGE * PER_PAGE);
        el.textContent = 'Showing ' + fmt(start) + '–' + fmt(end) + ' of ' + fmt(TOTAL) + ' layoffs';
    }

    // The params the results list asks for. Kept in one place so the bootstrap
    // match, the fetch and the export links can never drift apart.
    function queryParams() {
        var p = currentParams();
        // The list uses the inclusive country basis so a US-HQ company's global
        // cut (labeled "Multiple countries") surfaces under a US filter. The
        // headline stats (/aggregate, currentParams) stay on the strict
        // job-location basis, so the US total isn't inflated.
        if (p.country) p.country_basis = 'any';
        var s = SORT_PARAMS[currentSort()] || SORT_PARAMS.newest;
        p.per_page = String(PER_PAGE);
        p.page = String(PAGE);
        p.sort = s[0];
        p.dir = s[1];
        return p;
    }

    function loadRows() {
        var list = document.getElementById('alt-cards');
        if (!list) return;
        var p = queryParams();

        // Zero-fetch first paint, unchanged: the server inlined this exact
        // response as window.ALT_BOOTSTRAP, and it is used only when the
        // request we were about to make matches it key for key.
        var boot = takeBoot('query', p);
        if (boot) {
            TOTAL = boot.total; ROWS = boot.data || [];
            renderCards(); renderPager(); renderCount();
            setStatus('alt-table-status', null);
            return;
        }

        var seq = ++QUERY_SEQ;   // drop responses that resolve out of order
        busyTrack('alt-cards', 'Loading the records', function (signal) {
            return apiGet('query', p, signal);
        }, loadRows).then(function (res) {
            if (seq !== QUERY_SEQ) return;
            TOTAL = res.total; ROWS = res.data || [];
            renderCards(); renderPager(); renderCount();
            setStatus('alt-table-status', null);
        }).catch(function () {
            if (seq !== QUERY_SEQ) return;
            setStatus('alt-table-status', 'Could not load layoff data.', true);
        });
    }

    function gotoPage(p) {
        var last = Math.max(1, Math.ceil(TOTAL / PER_PAGE));
        p = Math.min(last, Math.max(1, p));
        if (p === PAGE) return;
        PAGE = p;
        loadRows();
        var row = document.getElementById('alt-count-row');
        if (row && row.scrollIntoView) row.scrollIntoView({ block: 'start' });
    }

    function initTracker() {
        var list = document.getElementById('alt-cards');
        if (!list) return;

        PAGE = 1;
        loadRows();

        // One delegated handler for the whole list. Expanding is a real
        // <button> with aria-expanded, so the detail is reachable by keyboard;
        // clicking the card body anywhere else still toggles it for a mouse,
        // which is what the table rows used to do and the only thing they did.
        list.addEventListener('click', function (e) {
            var clear = e.target.closest && e.target.closest('.alt-cards-empty-clear');
            if (clear) {
                clearFilters();
                writeControl('alt-f-years', [String(new Date().getFullYear())]);
                updateDropdownSummaries();
                refreshAll();
                return;
            }
            var card = e.target.closest && e.target.closest('.alt-card');
            if (!card) return;
            if (e.target.closest('a')) return;                     // let links be links
            var btn = card.querySelector('.alt-card-more');
            var panel = card.querySelector('.alt-card-detail');
            if (!btn || !panel) return;
            // A click on any other control inside the card is that control's.
            if (e.target.closest('button') && e.target.closest('button') !== btn) return;
            var open = btn.getAttribute('aria-expanded') === 'true';
            if (!open && !panel.innerHTML) {
                var row = ROWS[Number(card.getAttribute('data-i'))];
                if (row) panel.innerHTML = formatDetail(row);
            }
            btn.setAttribute('aria-expanded', open ? 'false' : 'true');
            btn.textContent = open ? 'Details' : 'Hide details';
            panel.hidden = open;
            card.classList.toggle('alt-card-open', !open);
        });

        var nav = document.getElementById('alt-pager');
        if (nav) {
            nav.addEventListener('click', function (e) {
                var b = e.target.closest && e.target.closest('.alt-page-btn');
                if (!b || b.disabled) return;
                gotoPage(Number(b.getAttribute('data-page')));
            });
            nav.addEventListener('change', function (e) {
                if (!e.target || e.target.id !== 'alt-per-page') return;
                PER_PAGE = Number(e.target.value) || 25;
                PAGE = 1;
                loadRows();
            });
        }

        setStatus('alt-table-status', null);

        var redraw = null;
        function onFilterChange(e) {
            var id = e && e.target && e.target.id;
            if (id === 'alt-f-years') LAST_MULTI_DIM = 'years';
            else if (id === 'alt-f-country') LAST_MULTI_DIM = 'country';
            clearTimeout(redraw); redraw = setTimeout(refreshAll, 250);
        }
        FILTER_IDS.forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', onFilterChange);
            if (el.type === 'text' || el.type === 'number') el.addEventListener('input', onFilterChange);
        });
        var reset = document.getElementById('alt-f-reset');
        if (reset) reset.addEventListener('click', function () { clearFilters(); writeControl('alt-f-years', [String(new Date().getFullYear())]); updateDropdownSummaries(); refreshAll(); });

        // Company typeahead: as the user types (2+ chars), fetch matching
        // employer names from /companies?q= and fill the <datalist>, so the
        // Company box is a search-as-you-type instead of guess-the-exact-name.
        // Debounced; the actual table filter still fires via onFilterChange.
        var coBox = document.getElementById('alt-f-company');
        var coList = document.getElementById('alt-company-suggest');
        if (coBox && coList) {
            var coTimer, coLast = '';
            coBox.addEventListener('input', function () {
                var q = coBox.value.trim();
                if (q.length < 2 || q === coLast) return;
                coLast = q;
                clearTimeout(coTimer);
                coTimer = setTimeout(function () {
                    apiGet('companies', { q: q, limit: 12 }).then(function (res) {
                        var names = (res && res.companies) || [];
                        coList.innerHTML = names.map(function (n) {
                            return '<option value="' + escapeHtml(n) + '"></option>';
                        }).join('');
                    }).catch(function () { /* suggestions are best-effort */ });
                }, 220);
            });
        }

        // Date-basis toggle: recount the whole page by filing vs effective date.
        // setDateBasis() owns the closure state, the visual and aria state of
        // the switch, and every caption that names the basis, so the caption
        // and the number it sits under cannot disagree after a click.
        document.querySelectorAll('.alt-datebasis-opt').forEach(function (b) {
            b.addEventListener('click', function () {
                var basis = b.getAttribute('data-basis') === 'notice' ? 'notice' : 'effective';
                if (basis === DATE_BASIS) return;
                setDateBasis(basis);
                refreshAll();
            });
        });

    }

    function formatDetail(row) {
        var parts = [];
        if (row.source_type === 'warn' && !row.ai_explicit) {
            // A WARN notice is a legal headcount filing: it records the layoff's
            // size, date and location, never its cause. Saying "AI classification
            // pending" implies a verdict is coming; there is nothing in the filing
            // to classify. Where the SAME cut was reported with a company-stated
            // reason, that reason lives on the separate news / SEC entry.
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">AI attribution status</span><p>Not stated in this filing. A WARN notice records a layoff’s size, date and location, not its cause. When the same cut is reported with a company-stated reason, that appears as a separate news or SEC entry for this employer.</p></div>');
        } else if (row.ai_causation) {
            var aiDetail = AI_CAUSATION_LABELS[row.ai_causation] || row.ai_causation;
            if (row.confidence != null && Number(row.confidence) > 0) aiDetail += ' · evidence confidence ' + fmt(row.confidence) + '/100';
            if (row.review_status) aiDetail += ' · ' + String(row.review_status).replace(/_/g, ' ');
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">AI attribution status</span><p>' + escapeHtml(aiDetail) + '</p></div>');
        }
        if (row.employer_country) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Employer country</span><p>' + escapeHtml(row.employer_country) + '</p></div>');
        // Announced-vs-executed: if this employer has both an announcement and
        // WARN executions on file, show the link so the two rows read as one story.
        var rc = RECON_MAP[reconKey(row.company_name)];
        if (rc && rc.announced_jobs && rc.executed_warn_jobs) {
            var lag = (rc.lag_days != null) ? (rc.lag_days + ' day' + (rc.lag_days === 1 ? '' : 's') + ' after the announcement') : '';
            var isWarn = row.source_type === 'warn';
            var lead = isWarn
                ? 'This WARN filing is part of a larger announced cut.'
                : 'This announcement has begun showing up in official WARN filings.';
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Announced vs executed</span><p>' +
                escapeHtml(lead) + ' <b>' + fmt(rc.announced_jobs) + '</b> announced' +
                (rc.announced_date ? ' (' + escapeHtml(rc.announced_date) + ')' : '') +
                '; <b>' + fmt(rc.executed_warn_jobs) + '</b> confirmed so far in US WARN filings' +
                (lag ? ', first ' + escapeHtml(lag) : '') +
                '. <span class="alt-muted">WARN is US-only and captures large single-site filings, so this is a floor, not a completion rate.</span></p></div>');
        }
        if (row.ai_language) parts.push('<div class="alt-detail-block alt-detail-quote"><span class="alt-detail-h">Exact AI / automation quote</span><blockquote>“' + escapeHtml(row.ai_language) + '”</blockquote></div>');
        if (row.excerpt) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">From the source</span><p>' + escapeHtml(row.excerpt) + '</p></div>');
        if (row.roles) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Roles affected</span><p>' + escapeHtml(row.roles) + '</p></div>');
        var tags = (row.reason_tags || []).map(function (t) { return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[t] || t) + '</span>'; }).join(' ');
        if (tags) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Reasons cited</span><div>' + tags + '</div></div>');
        var verifBadge = row.verification_level ? '<span class="alt-badge alt-badge-' + escapeHtml(row.verification_level) + '">' + escapeHtml(VERIF_LABELS[row.verification_level] || 'News') + '</span>' : '';
        var srcRows = [];
        var rollingNote = '';
        if (row.source_type === 'warn') {
            var wl = warnLinks(row);
            var warnText = wl.exact
                ? 'View this WARN notice (' + (row.source_name || 'source') + ') ↗'
                : 'View the state’s official WARN list (where this notice was filed) ↗';
            srcRows.push(srcRow('Primary source', wl.primary
                ? '<a href="' + escapeHtml(wl.primary) + '" target="_blank" rel="noopener nofollow">' + escapeHtml(warnText) + '</a>'
                : escapeHtml(row.source_name || '—')));
            // Exact notice + a distinct state list → offer both: the specific
            // record and the official index it sits in.
            if (wl.list) {
                srcRows.push(srcRow('State WARN list', '<a href="' + escapeHtml(wl.list) + '" target="_blank" rel="noopener nofollow">State WARN list ↗</a>'));
            }
            // California: link the PERMANENT fiscal-year PDF that actually lists
            // this notice (by notice/received date), not the rolling xlsx that
            // has dropped it. Uses announcement_date (the received date CA files
            // under) when present, else the effective date.
            if (row.state === 'CA') {
                var caPdf = caWarnPdfUrl(row.announcement_date || row.layoff_date);
                if (caPdf) {
                    srcRows.push(srcRow('Permanent report', '<a href="' + escapeHtml(caPdf) + '" target="_blank" rel="noopener nofollow" title="California’s permanent cumulative WARN report for the fiscal year this notice was filed in. This notice is listed in it.">Official CA WARN report (PDF) ↗</a>'));
                }
            }
            // Rolling-file honesty: many states publish one continuously updated
            // file, so an older notice may no longer appear in today's version.
            if (!wl.exact) {
                rollingNote = '<div class="alt-muted alt-warn-rolling">States update their WARN lists continuously, so an older notice may have rolled into the state’s annual archive. Where a permanent report exists (linked above), this notice is listed in it. The size, date and location shown here are the details we captured from the notice when it was filed.</div>';
            }
        } else {
            var url = safeUrl(row.source_url);
            srcRows.push(srcRow('Primary source', url
                ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">' + escapeHtml('View primary source (' + (row.source_name || 'source') + ') ↗') + '</a>'
                : escapeHtml(row.source_name || '—')));
        }
        // Every row now carries an explicit Archived-copy row: the permanent
        // Wayback link, or the honest "waiting to be crawled" note. Never a gap.
        srcRows.push(srcRow('Archived copy', archiveCell(row)));
        if (verifBadge) srcRows.push(srcRow('Verification', verifBadge));
        parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Source</span><div class="alt-src-list">' + srcRows.join('') + rollingNote + '</div></div>');
        // Corroboration: when this event was recorded from more than one source
        // (e.g. an official WARN filing AND the news article that reported it,
        // or two independent outlets), surface those other links too — the
        // primary link above is only one of them.
        var extra = (row.additional_sources || []).filter(function (s) { return s && safeUrl(s.source_url); });
        if (extra.length) {
            var links = extra.map(function (s) {
                var lbl = SOURCE_TYPE_LABELS[s.source_type] || s.source_type || 'source';
                return '<a href="' + escapeHtml(safeUrl(s.source_url)) + '" target="_blank" rel="noopener nofollow">' +
                    escapeHtml(s.source_name || 'source') + '</a> <span class="alt-muted">(' + escapeHtml(lbl) + ')</span>';
            }).join('<br>');
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Other sources for this layoff</span><div>' + links + '</div></div>');
        }
        return '<div class="alt-detail">' + (parts.join('') || 'No additional detail recorded.') + '</div>';
    }

    /* ------------------------------------------------------------------ */
    /* The map of AI job loss — d3 proportional-symbol map (d3 + topojson)  */
    /* ------------------------------------------------------------------ */

    // Centroids [lon, lat] for placing bubbles. Countries keyed by the exact
    // label the aggregate returns; US states by 2-letter code. Only the places
    // that actually appear in the data need an entry — anything missing is just
    // skipped (with a console note), never an error.
    var COUNTRY_CENTROIDS = {
        'United States': [-98, 39], 'India': [79, 22], 'United Kingdom': [-1.5, 53], 'Germany': [10, 51],
        'Canada': [-106, 56], 'Australia': [134, -25], 'France': [2, 47], 'China': [104, 35],
        'Japan': [138, 37], 'Singapore': [103.8, 1.35], 'Netherlands': [5.7, 52], 'Sweden': [18, 62],
        'Switzerland': [8, 47], 'Ireland': [-8, 53], 'Spain': [-4, 40], 'Italy': [12.5, 42],
        'Brazil': [-52, -10], 'Mexico': [-102, 23], 'Israel': [35, 31], 'Poland': [19, 52],
        'Norway': [9, 61], 'Denmark': [10, 56], 'Finland': [26, 64], 'Belgium': [4.5, 50.6],
        'Austria': [14, 47.5], 'South Korea': [128, 36], 'Nigeria': [8, 10], 'South Africa': [24, -29],
        'United Arab Emirates': [54, 24], 'Saudi Arabia': [45, 24], 'Indonesia': [113, -0.8],
        'Philippines': [122, 12], 'Malaysia': [102, 4], 'Thailand': [101, 15], 'Vietnam': [106, 16],
        'Turkey': [35, 39], 'Portugal': [-8, 39.5], 'New Zealand': [172, -41], 'Argentina': [-64, -34],
        'Egypt': [30, 27], 'Kenya': [38, 0], 'Pakistan': [70, 30], 'Bangladesh': [90, 24],
        'Russia': [90, 61], 'Ukraine': [32, 49], 'Greece': [22, 39], 'Romania': [25, 46],
        'Czechia': [15.5, 49.8], 'Hungary': [19, 47], 'Colombia': [-73, 4], 'Chile': [-71, -30],
        'Taiwan': [121, 23.7], 'Hong Kong': [114.1, 22.3]
    };
    var US_STATE_CENTROIDS = {
        AL:[-86.8,32.8],AK:[-152,64],AZ:[-111.7,34.2],AR:[-92.4,34.8],CA:[-119.4,37.2],CO:[-105.5,39],
        CT:[-72.7,41.6],DE:[-75.5,39],DC:[-77,38.9],FL:[-81.6,28.6],GA:[-83.4,32.6],HI:[-157,20.3],
        ID:[-114.5,44.2],IL:[-89.2,40],IN:[-86.3,39.9],IA:[-93.5,42],KS:[-98.3,38.5],KY:[-84.9,37.5],
        LA:[-92,31],ME:[-69.2,45.4],MD:[-76.6,39],MA:[-71.8,42.2],MI:[-84.6,44.3],MN:[-94.3,46.3],
        MS:[-89.7,32.7],MO:[-92.5,38.4],MT:[-109.6,47],NE:[-99.8,41.5],NV:[-116.6,39.3],NH:[-71.6,43.7],
        NJ:[-74.5,40.1],NM:[-106,34.4],NY:[-75.5,42.9],NC:[-79.4,35.6],ND:[-100.3,47.5],OH:[-82.8,40.3],
        OK:[-97.5,35.6],OR:[-120.6,44],PA:[-77.6,40.9],RI:[-71.5,41.7],SC:[-80.9,33.9],SD:[-100.2,44.4],
        TN:[-86.4,35.8],TX:[-99.3,31.5],UT:[-111.7,39.3],VT:[-72.7,44],VA:[-78.8,37.5],WA:[-120.5,47.4],
        WV:[-80.6,38.6],WI:[-89.9,44.6],WY:[-107.5,43]
    };
    var TOPO_URL = {
        world: 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json',
        us: 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json'
    };
    var AIMAP = { scope: 'world', data: null, outline: {}, loading: {}, transform: null, transformScope: null, retries: 0, revealed: false };
    // Draw the map only once its card scrolls near the viewport, so the initial
    // page load doesn't pay for the world atlas + geo render up front. Falls
    // back to drawing immediately if IntersectionObserver or the card is absent.
    // d3 + topojson (~95KB gzip) power ONLY the map, which lazy-renders below
    // the fold — so the libraries lazy-load with it instead of shipping to
    // every visitor (perf audit 2026-07-25: they were 30% of the eager JS and
    // defeated the atlas lazy-load). renderAiMap() already polls d3Ready() for
    // up to 6s, which absorbs the CDN fetch time.
    var MAP_LIBS = ['https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js',
                    'https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js'];
    function loadMapLibs() {
        if (loadMapLibs._done) return;
        loadMapLibs._done = true;
        MAP_LIBS.forEach(function (src) {
            var el = document.createElement('script');
            el.src = src; el.async = true;
            document.head.appendChild(el);
        });
    }
    function observeMapReveal() {
        if (AIMAP._observing) return;
        var card = document.getElementById('alt-map-card');
        if (!card || !('IntersectionObserver' in window)) { AIMAP.revealed = true; loadMapLibs(); renderAiMap(); return; }
        AIMAP._observing = true;
        var io = new IntersectionObserver(function (entries) {
            for (var i = 0; i < entries.length; i++) {
                if (entries[i].isIntersecting) {
                    io.disconnect();
                    AIMAP._observing = false;
                    AIMAP.revealed = true;
                    loadMapLibs();
                    renderAiMap();
                    return;
                }
            }
        }, { rootMargin: '600px' });
        io.observe(card);
    }

    // d3 v7 (window.d3) + topojson-client (window.topojson) power the map now.
    // Both are plain UMD globals loaded just before this file (tracker + embed).
    function d3Ready() { return typeof window.d3 !== 'undefined' && typeof window.topojson !== 'undefined'; }

    function loadTopo(scope) {
        if (AIMAP.outline[scope]) return Promise.resolve(AIMAP.outline[scope]);
        if (AIMAP.loading[scope]) return AIMAP.loading[scope];
        AIMAP.loading[scope] = fetch(TOPO_URL[scope]).then(function (r) { return r.json(); }).then(function (topo) {
            var obj = scope === 'us' ? topo.objects.states : topo.objects.countries;
            var feats = window.topojson.feature(topo, obj).features;
            AIMAP.outline[scope] = feats;
            return feats;
        });
        return AIMAP.loading[scope];
    }

    function aiMapPoints(scope, agg) {
        // Same verified basis as the bar cards and the headline tile: a bubble
        // sized on verified-plus-announced next to a page publishing verified
        // is the same defect in a rounder shape.
        var rows = verifiedBasis(scope === 'us' ? (agg.map_states || agg.top_states || []) : (agg.map_countries || agg.top_countries || []));
        var lut = scope === 'us' ? US_STATE_CENTROIDS : COUNTRY_CENTROIDS;
        var out = [];
        rows.forEach(function (e) {
            var label = e[0], jobs = e[1] || 0, ai = e[2] || 0;
            if (jobs <= 0) return;
            var c = lut[label];
            if (!c) return;                            // no centroid (e.g. "Multiple countries") — skip
            out.push({ lon: c[0], lat: c[1], label: label, jobs: jobs, ai: ai });
        });
        return out;
    }

    // Two clear layers: BLUE = all job cuts, RED = AI-linked cuts sitting inside.
    // Both hues, the land plate and the label halo are declared and assigned
    // up in readTheme(), from --alt-map-*. They used to be re-assigned here,
    // which ran AFTER readTheme() at load and silently put the light values
    // back, so the map was the one surface that stayed light in dark mode.

    function prefersReducedMotion() {
        try { return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
        catch (e) { return false; }
    }
    function mapTipHtml(b) {
        var pct = Math.round((b.jobs ? b.ai / b.jobs : 0) * 100);
        return '<b>' + escapeHtml(b.label) + '</b><br>' + fmt(b.jobs) + ' job cuts'
            + ' &middot; ' + fmt(b.ai) + ' AI-attributed (' + pct + '%)';
    }

    // NYT-style proportional-symbol map on an SVG: gray base geography, a blue
    // "all cuts" bubble with the red "AI-linked" bubble nested inside, smooth
    // d3.zoom pan/zoom, hover tooltip, click-to-filter, value labels on the
    // biggest few, an in-SVG legend, and a reset affordance. Rebuilt on every
    // filter change; the zoom transform is preserved within a scope.
    function renderAiMap() {
        var box = document.getElementById('alt-chart-aimap');
        var note = document.getElementById('alt-map-note');
        if (!box || !AIMAP.data) return;
        if (!d3Ready()) {
            if (note) { note.style.display = ''; note.textContent = 'Map library still loading…'; }
            if ((AIMAP.retries = (AIMAP.retries || 0) + 1) <= 20) setTimeout(renderAiMap, 300);
            return;
        }
        AIMAP.retries = 0;
        var d3 = window.d3;
        var scope = AIMAP.scope;
        var points = aiMapPoints(scope, AIMAP.data);

        // Caption (unchanged behavior): mapped jobs / AI / view total.
        var total = document.getElementById('alt-map-total');
        if (total) {
            var mappedJobs = 0, mappedAi = 0;
            points.forEach(function (b) { mappedJobs += b.jobs; mappedAi += b.ai; });
            var viewTotal = (AIMAP.data.totals && AIMAP.data.totals.jobs) || 0;
            var place = scope === 'us' ? 'US states' : 'countries';
            total.textContent = points.length
                ? fmt(mappedJobs) + ' job cuts plotted (those with a named location, across ' + points.length + ' ' + place + ')'
                    + ' · ' + fmt(mappedAi) + ' AI-attributed · ' + fmt(viewTotal) + ' total in this view · ' + statPeriodLabel()
                : '';
        }

        loadTopo(scope).then(function (outline) {
            if (!points.length) {
                box.innerHTML = '';
                if (note) { note.style.display = ''; note.textContent = 'No cuts with a known location in this view yet.'; }
                return;
            }
            if (note) note.style.display = 'none';

            var rect = box.getBoundingClientRect();
            var w = Math.max(320, Math.round(rect.width || box.clientWidth || 640));
            var h = Math.max(240, Math.round(rect.height || box.clientHeight || 360));

            var proj = (scope === 'us' ? d3.geoAlbersUsa() : d3.geoNaturalEarth1())
                .fitSize([w, h], { type: 'FeatureCollection', features: outline });
            var path = d3.geoPath(proj);

            // Project centroids once; drop any the projection can't place
            // (geoAlbersUsa returns null outside the US inset).
            var pts = [];
            points.forEach(function (p) {
                var xy = proj([p.lon, p.lat]);
                if (!xy) return;
                p.x0 = xy[0]; p.y0 = xy[1];
                pts.push(p);
            });
            if (!pts.length) {
                box.innerHTML = '';
                if (note) { note.style.display = ''; note.textContent = 'No cuts with a known location in this view yet.'; }
                return;
            }
            // Draw big→small so small bubbles land on top and stay clickable.
            pts.sort(function (a, b) { return b.jobs - a.jobs; });

            var maxJobs = d3.max(pts, function (p) { return p.jobs; }) || 1;
            var maxR = scope === 'us' ? 30 : 38;
            var rScale = d3.scaleSqrt().domain([0, maxJobs]).range([0, maxR]);
            var rOf = function (v) { return v > 0 ? Math.max(2.2, rScale(v)) : 0; };
            // AI dots get a HIGHER visibility floor: with an all-time view the AI
            // share is ~1% of the total, so a strictly proportional radius shrinks
            // to ~2px inside a 30px+ blue bubble and reads as "no AI on the map".
            // 4px keeps tiny-but-real AI presence findable; the tooltip carries
            // the exact number, so the floor never misstates a value.
            var rAi = function (v) { return v > 0 ? Math.max(4, rScale(v)) : 0; };
            // The AI dot's 4px visibility floor must never exceed its own blue
            // bubble: for small totals rScale(jobs) < 4, and an uncapped floor
            // drew red OVER blue — the legend's "sits inside" became a lie
            // (audit 2026-07-25). Cap at the parent radius.
            pts.forEach(function (p) { p.r = rOf(p.jobs); p.ra = Math.min(p.r, rAi(p.ai)); });

            box.innerHTML = '';
            box.style.position = 'relative';

            var svg = d3.select(box).append('svg')
                .attr('class', 'alt-map-svg')
                .attr('viewBox', '0 0 ' + w + ' ' + h)
                .attr('preserveAspectRatio', 'xMidYMid meet')
                .attr('width', '100%').attr('height', '100%')
                .attr('role', 'img')
                .attr('aria-label', 'Map of job cuts by ' + (scope === 'us' ? 'US state' : 'country'))
                .style('display', 'block')
                .style('touch-action', 'none')
                .style('background', MAP_PLATE)
                .style('cursor', 'grab');

            var gMap = svg.append('g').attr('class', 'alt-map-geo');   // zoomed: base shapes
            var gOverlay = svg.append('g').attr('class', 'alt-map-pts'); // screen-space: bubbles + labels

            // Base geography — click a shape to zoom toward it.
            gMap.selectAll('path').data(outline).join('path')
                .attr('d', path)
                .attr('fill', MAP_LAND)
                .attr('stroke', MAP_LAND_LINE)
                .attr('stroke-width', 0.5)
                .attr('vector-effect', 'non-scaling-stroke')
                .style('cursor', 'pointer')
                .on('click', function (event, d) { zoomToFeature(d); });

            // Tooltip (HTML overlay; transient, so left out of the PNG). The
            // no-register panel reuses this element but can be "pinned" (made
            // interactive) on click so its BLS link is reachable.
            var tip = d3.select(box).append('div').attr('class', 'alt-map-tip').style('display', 'none');
            var hatchPinned = false;

            function placeTip(event) {
                var m = d3.pointer(event, box);
                var tw = tip.node().offsetWidth, th = tip.node().offsetHeight;
                var lx = Math.min(Math.max(6, m[0] + 14), w - tw - 6);
                var ly = Math.max(6, m[1] - th - 12);
                tip.style('left', lx + 'px').style('top', ly + 'px');
            }
            function hideTip() { hatchPinned = false; tip.style('display', 'none').style('pointer-events', 'none'); }
            function showTip(event, p) {
                hatchPinned = false;
                tip.html(mapTipHtml(p)).style('display', 'block').style('pointer-events', 'none');
                placeTip(event);
            }

            // US-only fallback: states with NO usable public WARN register get
            // a hatched fill (clearly a different kind of thing from the layoff
            // bubbles) and are labeled with the official BLS unemployment rate —
            // a SEPARATE metric, never a layoff count. Guarded: the embed route
            // may not ship altData.noRegister, in which case the layer is skipped.
            var noReg = (scope === 'us' && window.altData && window.altData.noRegister) ? window.altData.noRegister : null;
            var stateLabor = (window.altData && window.altData.stateLabor) || {};
            var hasHatch = false, hatchLabelPts = [];
            if (noReg) {
                var FIPS2CODE = { '05': 'AR', '56': 'WY', '33': 'NH', '29': 'MO', '15': 'HI', '40': 'OK' };
                var STATE_NAMES = { AR: 'Arkansas', WY: 'Wyoming', NH: 'New Hampshire', MO: 'Missouri', HI: 'Hawaii', OK: 'Oklahoma' };
                var fmtRate = function (r) { return (typeof r === 'number' && isFinite(r)) ? r.toFixed(1) : null; };
                var blsUrl = safeUrl(window.altData.blsUrl) || 'https://www.bls.gov/lau/';
                var panelHtml = function (code) {
                    var reason = String(noReg[code] || '').trim();
                    var lab = stateLabor[code] || {};
                    var rate = fmtRate(lab.rate);
                    var s = '<b>' + escapeHtml(STATE_NAMES[code] || code) + ':</b> no public layoff register.';
                    if (reason) s += ' ' + escapeHtml(reason);
                    if (rate != null) s += ' Unemployment rate (BLS' + (lab.period ? ', ' + escapeHtml(lab.period) : '') + '): ' + rate + '%.';
                    s += ' <a href="' + escapeHtml(blsUrl) + '" target="_top" rel="noopener">View at BLS ↗</a>';
                    return s;
                };

                // Cross-hatch <pattern> (userSpaceOnUse so it renders identically
                // in the rasterized PNG). Light gray, unmistakably not a bubble.
                var defs = svg.append('defs');
                var pat = defs.append('pattern').attr('id', 'alt-hatch')
                    .attr('patternUnits', 'userSpaceOnUse').attr('width', 6).attr('height', 6)
                    .attr('patternTransform', 'rotate(45)');
                pat.append('rect').attr('width', 6).attr('height', 6).attr('fill', MAP_HATCH);
                pat.append('line').attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 6)
                    .attr('stroke', MAP_HATCH_LINE).attr('stroke-width', 1.5);

                var hatchFeatures = outline.filter(function (f) {
                    var code = FIPS2CODE[String(f.id)];
                    return code && noReg[code];
                });
                hasHatch = hatchFeatures.length > 0;

                gMap.selectAll('path.alt-hatch-state').data(hatchFeatures).join('path')
                    .attr('class', 'alt-hatch-state')
                    .attr('d', path)
                    .attr('fill', 'url(#alt-hatch)')
                    .attr('stroke', MAP_HATCH_LINE).attr('stroke-width', 0.7)
                    .attr('vector-effect', 'non-scaling-stroke')
                    .style('cursor', 'pointer')
                    .on('mouseenter', function (event, f) {
                        if (hatchPinned) return;
                        tip.html(panelHtml(FIPS2CODE[String(f.id)])).style('display', 'block').style('pointer-events', 'none');
                        placeTip(event);
                    })
                    .on('mousemove', function (event) { if (!hatchPinned) placeTip(event); })
                    .on('mouseleave', function () { if (!hatchPinned) hideTip(); })
                    .on('click', function (event, f) {
                        event.stopPropagation();
                        hatchPinned = true;
                        tip.html(panelHtml(FIPS2CODE[String(f.id)])).style('display', 'block').style('pointer-events', 'auto');
                        placeTip(event);
                    });

                // Centered "AR 4.2%" labels, kept constant screen-size in the
                // overlay (re-placed with the zoom transform, like value labels).
                hatchFeatures.forEach(function (f) {
                    var c = path.centroid(f);
                    if (!c || !isFinite(c[0])) return;
                    var code = FIPS2CODE[String(f.id)];
                    var rate = fmtRate((stateLabor[code] || {}).rate);
                    hatchLabelPts.push({ x0: c[0], y0: c[1], text: code + (rate != null ? ' ' + rate + '%' : '') });
                });
            }

            // Bubble groups: blue (all cuts) with red (AI-linked) nested inside.
            var node = gOverlay.selectAll('g.alt-bub').data(pts).join('g')
                .attr('class', 'alt-bub')
                .style('cursor', 'pointer')
                .on('mouseenter', function (event, p) {
                    d3.select(this).raise().select('.b-all').attr('stroke-width', 1.6);
                    showTip(event, p);
                })
                .on('mousemove', function (event, p) { showTip(event, p); })
                .on('mouseleave', function () {
                    d3.select(this).select('.b-all').attr('stroke-width', 0.8);
                    tip.style('display', 'none');
                })
                .on('click', function (event, p) {
                    event.stopPropagation();
                    // Toggle, not overwrite: tapping the lit bubble again takes
                    // the filter off, matching every bar row on the page. Routed
                    // through toggleMultiFilter so the country path is the same
                    // one the dropdown uses (and so keeps country_basis=any for
                    // the table while the headline stats stay job-location).
                    var id = scope === 'us' ? 'alt-f-state' : 'alt-f-country';
                    ensureOption(id, p.label, p.label);
                    toggleMultiFilter(id, p.label);
                    if (typeof refreshAll === 'function') refreshAll();
                });
            node.append('circle').attr('class', 'b-all')
                .attr('r', function (p) { return p.r; })
                .attr('fill', MAP_BLUE).attr('stroke', MAP_BLUE_LINE).attr('stroke-width', 0.8);
            node.filter(function (p) { return p.ra > 0; }).append('circle').attr('class', 'b-ai')
                .attr('r', function (p) { return p.ra; })
                .attr('fill', MAP_RED).attr('stroke', MAP_RED_LINE).attr('stroke-width', 0.8)
                .style('pointer-events', 'none');

            // Place-NAME labels (not raw counts): the biggest few places are
            // always named, and as you zoom in the names of smaller places appear
            // once they separate enough not to collide. The exact figure stays in
            // the hover tooltip; the name answers "which place is this" at a glance.
            var byJobs = pts.slice().sort(function (a, b) { return b.jobs - a.jobs; });
            var BASE_LABELS = scope === 'us' ? 7 : 6;
            var label = gOverlay.selectAll('text.alt-map-lab').data(byJobs, function (p) { return p.label; }).join('text')
                .attr('class', 'alt-map-lab')
                .attr('text-anchor', 'middle')
                .attr('font-size', 11).attr('font-weight', 700)
                .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif')
                .attr('fill', MAP_LABEL).attr('stroke', MAP_LABEL_HALO).attr('stroke-width', 3)
                .attr('paint-order', 'stroke').style('pointer-events', 'none')
                .text(function (p) { return p.label; });

            // Choose which names to show for a zoom transform t: always the
            // headline set, plus any in-view place once zoomed in, minus anything
            // that would overlap a name already placed (biggest place wins the spot).
            function placeLabels(t) {
                var k = t.k || 1, placed = [];
                byJobs.forEach(function (p, i) {
                    var s = t.apply([p.x0, p.y0]);
                    p._lx = s[0]; p._ly = s[1] - p.r - 5;
                    var inView = s[0] > 6 && s[0] < w - 6 && s[1] > 10 && s[1] < h - 6;
                    var show = inView && ((i < BASE_LABELS) || k > 1.6);
                    if (show) {
                        for (var j = 0; j < placed.length; j++) {
                            if (Math.abs(placed[j][0] - p._lx) < 48 && Math.abs(placed[j][1] - p._ly) < 14) { show = false; break; }
                        }
                    }
                    p._show = show;
                    if (show) placed.push([p._lx, p._ly]);
                });
                label.attr('transform', function (p) { return 'translate(' + p._lx + ',' + p._ly + ')'; })
                    .style('display', function (p) { return p._show ? null : 'none'; });
            }

            // "AR 4.2%" labels on the hatched no-register states.
            var hatchLabel = gOverlay.selectAll('text.alt-hatch-lab').data(hatchLabelPts).join('text')
                .attr('class', 'alt-hatch-lab')
                .attr('text-anchor', 'middle')
                .attr('font-size', 10.5).attr('font-weight', 700)
                .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif')
                .attr('fill', INK.secondary).attr('stroke', MAP_LABEL_HALO).attr('stroke-width', 2.6)
                .attr('paint-order', 'stroke').style('pointer-events', 'none')
                .text(function (p) { return p.text; });

            // In-SVG legend (captured by the PNG export).
            drawMapLegend(svg, w, h, hasHatch);

            // Zoom / pan (1x–8x). Base shapes ride the transform; bubbles and
            // labels are re-placed at constant screen size so clustered points
            // separate as you zoom instead of ballooning.
            function reposition(t) {
                gMap.attr('transform', t.toString());
                node.attr('transform', function (p) { var s = t.apply([p.x0, p.y0]); return 'translate(' + s[0] + ',' + s[1] + ')'; });
                placeLabels(t);
                hatchLabel.attr('transform', function (p) { var s = t.apply([p.x0, p.y0]); return 'translate(' + s[0] + ',' + s[1] + ')'; });
            }
            var zoom = d3.zoom().scaleExtent([1, 8])
                .on('zoom', function (event) {
                    AIMAP.transform = event.transform;
                    AIMAP.transformScope = scope;
                    reposition(event.transform);
                    svg.style('cursor', event.transform.k > 1 ? 'grab' : 'default');
                });
            svg.call(zoom);

            // Visible +/- zoom control (scroll-wheel, drag-pan and click-a-shape
            // still work; the buttons make zoom discoverable and touch-friendly).
            function zoomByFactor(f) {
                svg.transition().duration(prefersReducedMotion() ? 0 : 250).call(zoom.scaleBy, f);
            }
            var zc = d3.select(box).append('div').attr('class', 'alt-map-zoom');
            zc.append('button').attr('type', 'button').attr('class', 'alt-map-zbtn')
                .attr('aria-label', 'Zoom in').attr('title', 'Zoom in').text('+')
                .on('click', function (event) { event.stopPropagation(); zoomByFactor(1.6); });
            zc.append('button').attr('type', 'button').attr('class', 'alt-map-zbtn')
                .attr('aria-label', 'Zoom out').attr('title', 'Zoom out').text('−')
                .on('click', function (event) { event.stopPropagation(); zoomByFactor(1 / 1.6); });

            function zoomToFeature(feature) {
                hideTip();                         // dismiss any pinned no-register panel
                var b;
                try { b = path.bounds(feature); } catch (e) { return; }
                if (!b || !isFinite(b[0][0])) return;
                var dx = b[1][0] - b[0][0], dy = b[1][1] - b[0][1];
                var cx = (b[0][0] + b[1][0]) / 2, cy = (b[0][1] + b[1][1]) / 2;
                var k = Math.max(1, Math.min(8, 0.82 / Math.max(dx / w, dy / h || 1e-6)));
                var t = d3.zoomIdentity.translate(w / 2 - k * cx, h / 2 - k * cy).scale(k);
                svg.transition().duration(prefersReducedMotion() ? 0 : 600).call(zoom.transform, t);
            }
            AIMAP.resetZoom = function () {
                svg.transition().duration(prefersReducedMotion() ? 0 : 450).call(zoom.transform, d3.zoomIdentity);
            };

            // "Reset view" affordance (HTML overlay).
            var reset = d3.select(box).append('button')
                .attr('type', 'button').attr('class', 'alt-map-reset').attr('title', 'Reset view')
                .html('Reset view')
                .on('click', function (event) { event.stopPropagation(); AIMAP.resetZoom(); });
            reset.node().style.display = 'none';

            // Restore the prior transform within a scope; otherwise start fresh.
            var t0 = (AIMAP.transform && AIMAP.transformScope === scope) ? AIMAP.transform : d3.zoomIdentity;
            svg.call(zoom.transform, t0);
            var syncReset = function () { reset.node().style.display = (AIMAP.transform && AIMAP.transform.k > 1.001) ? 'block' : 'none'; };
            zoom.on('zoom.reset', function () { syncReset(); });
            syncReset();
        }).catch(function () {
            if (note) { note.style.display = ''; note.textContent = 'Map data could not be loaded.'; }
        });
    }

    function drawMapLegend(svg, w, h, hasHatch) {
        // Extra row (+20px taller box) when the US no-register layer is present.
        var boxH = hasHatch ? 86 : 66;
        var g = svg.append('g').attr('class', 'alt-map-legend').attr('transform', 'translate(14,' + (h - boxH + 4) + ')');
        g.append('rect').attr('x', -8).attr('y', -14).attr('width', hasHatch ? 236 : 176).attr('height', boxH).attr('rx', 7)
            .attr('fill', tok('sticky-bg', 'rgba(255,255,255,0.9)')).attr('stroke', MAP_LAND_LINE).attr('stroke-width', 1);
        var row = function (y, color, line, txt) {
            g.append('circle').attr('cx', 4).attr('cy', y).attr('r', 6).attr('fill', color).attr('stroke', line).attr('stroke-width', 1);
            g.append('text').attr('x', 18).attr('y', y + 4).attr('font-size', 11.5)
                .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif').attr('fill', INK.secondary).text(txt);
        };
        row(2, MAP_BLUE, MAP_BLUE_LINE, 'All job cuts');
        row(22, MAP_RED, MAP_RED_LINE, 'AI-attributed cuts');
        var sizeY = 46;
        if (hasHatch) {
            // Small hatched swatch matching the state pattern.
            g.append('rect').attr('x', -2).attr('y', 36).attr('width', 12).attr('height', 12).attr('rx', 2)
                .attr('fill', 'url(#alt-hatch)').attr('stroke', MAP_HATCH_LINE).attr('stroke-width', 0.8);
            g.append('text').attr('x', 18).attr('y', 46).attr('font-size', 11)
                .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif').attr('fill', INK.secondary)
                .text('No layoff register (BLS unemployment shown)');
            sizeY = 68;
        }
        g.append('text').attr('x', -4).attr('y', sizeY).attr('font-size', 10.5)
            .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif').attr('fill', INK.muted)
            .text('Circle size = number of jobs');
    }

    // Serialize the live map SVG to a PNG. Interactive HTML overlays (tooltip,
    // reset button) are deliberately excluded; the legend lives inside the SVG
    // and so is captured.
    function exportMapPng() {
        var box = document.getElementById('alt-chart-aimap');
        var svg = box && box.querySelector('svg.alt-map-svg');
        if (!svg) return;
        var vb = (svg.getAttribute('viewBox') || '0 0 640 360').split(/\s+/);
        var w = parseFloat(vb[2]) || 640, h = parseFloat(vb[3]) || 360;
        var scale = 2;
        var clone = svg.cloneNode(true);
        clone.setAttribute('width', w);
        clone.setAttribute('height', h);
        clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        var xml = new XMLSerializer().serializeToString(clone);
        var url = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(xml);
        var img = new Image();
        img.onload = function () {
            var c = document.createElement('canvas');
            c.width = Math.round(w * scale); c.height = Math.round(h * scale);
            var ctx = c.getContext('2d');
            ctx.fillStyle = MAP_PLATE; ctx.fillRect(0, 0, c.width, c.height);
            ctx.drawImage(img, 0, 0, c.width, c.height);
            var a = document.createElement('a');
            try { a.href = c.toDataURL('image/png'); } catch (e) { return; }
            a.download = 'ai-layoff-tracker-map.png';
            a.click();
        };
        img.onerror = function () { /* offline / blocked — silently no-op */ };
        img.src = url;
    }

    function initAiMap() {
        document.querySelectorAll('.alt-map-scope').forEach(function (btn) {
            btn.addEventListener('click', function () {
                if (btn.classList.contains('alt-map-scope-on')) return;
                document.querySelectorAll('.alt-map-scope').forEach(function (b) { b.classList.remove('alt-map-scope-on'); });
                btn.classList.add('alt-map-scope-on');
                AIMAP.scope = btn.getAttribute('data-scope');
                AIMAP.transform = null;              // switching scope resets the view
                renderAiMap();
            });
        });
        // Re-fit the SVG to the card when it resizes (expand toggle, window).
        if (window.ResizeObserver && !AIMAP._ro) {
            var box = document.getElementById('alt-chart-aimap');
            if (box) {
                var tmr = null;
                AIMAP._ro = new ResizeObserver(function () {
                    clearTimeout(tmr);
                    tmr = setTimeout(function () { if (AIMAP.data) renderAiMap(); }, 180);
                });
                AIMAP._ro.observe(box);
            }
        }
    }

    /* ------------------------------------------------------------------ */
    /* Repaint on theme change                                             */
    /* ------------------------------------------------------------------ */

    // A stylesheet repaints itself. A canvas does not, and neither does an
    // SVG built as a string with fill= attributes baked in. So when the theme
    // changes we re-read the tokens and drive every draw path again.
    //
    // The event is dispatched by the inline head snippet (see alt_theme_boot
    // in ai-layoff-tracker.php), which owns the toggle and the persistence.
    // This file only listens, so the health page - which loads health.js and
    // not this file - still gets a working toggle with no charts to repaint.
    function repaintForTheme() {
        readTheme();
        // renderCharts covers trend, AI cumulative, the reasons doughnut, the
        // trajectory strip, the bar lists, AI share, the leaderboard, and it
        // re-seeds AIMAP.data and calls renderAiMap. mountChart destroys and
        // rebuilds each canvas, and renderAiMap clears its box and rebuilds
        // the SVG while preserving AIMAP.transform, so the visitor keeps
        // their pan and zoom across a theme switch.
        try { if (LAST_AGG) renderCharts(LAST_AGG); } catch (e) { }
        // Separate state, not reached by renderCharts.
        try { if (CONVERSION_DATA) renderConversionChart(); } catch (e) { }
        // The two single-purpose pages mount their chart inline from a fetch
        // callback; each stores its last rows so a repaint costs no request.
        try { if (AI_TRACKER_CHART) AI_TRACKER_CHART(); } catch (e) { }
        try { if (COMPANY_CHART) COMPANY_CHART(); } catch (e) { }
    }
    var AI_TRACKER_CHART = null, COMPANY_CHART = null;
    document.addEventListener('alt:themechange', repaintForTheme);

    /* ------------------------------------------------------------------ */
    /* AI displacement view + company history (bounded result sets)        */
    /* ------------------------------------------------------------------ */

    function initAiTracker() {
        var wrap = document.querySelector('.alt-ai-tracker');
        if (!wrap) return;
        apiGet('query', { ai: '1', per_page: 500, sort: 'job_count', dir: 'desc' }).then(function (res) {
            var aiRows = res.data || [];
            var totalJobs = aiRows.reduce(function (s, r) { return s + r.job_count; }, 0);
            var companies = {};
            aiRows.forEach(function (r) {
                var k = String(r.company_name).toLowerCase();
                if (!companies[k]) companies[k] = { name: r.company_name, jobs: 0 };
                companies[k].jobs += r.job_count;
            });
            var list = Object.keys(companies).map(function (k) { return companies[k]; }).sort(function (a, b) { return b.jobs - a.jobs; });
            setText('alt-ai-hero-jobs', fmt(totalJobs));
            setText('alt-ai-hero-sub', 'across ' + fmt(aiRows.length) + ' layoffs at ' + fmt(list.length) + ' companies');
            if (!aiRows.length) { setStatus('alt-ai-status', 'No explicitly AI-attributed layoffs recorded yet.'); return; }
            setStatus('alt-ai-status', chartsAvailable() ? null : 'Chart library failed to load (CDN blocked?). Charts unavailable.', !chartsAvailable());

            if (chartsAvailable()) {
                var byMonth = {};
                aiRows.forEach(function (r) { if (/^\d{4}-\d{2}-\d{2}$/.test(r.layoff_date)) { var m = r.layoff_date.slice(0, 7); byMonth[m] = (byMonth[m] || 0) + r.job_count; } });
                var keys = Object.keys(byMonth).sort();
                var byInd = {};
                aiRows.forEach(function (r) { if (r.industry) byInd[r.industry] = (byInd[r.industry] || 0) + 1; });
                var indEntries = Object.keys(byInd).map(function (k) { return [k, byInd[k]]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 10);
                // Named and stored, so a theme change repaints these two from
                // the rows already in hand instead of re-issuing the query.
                AI_TRACKER_CHART = function () {
                    if (keys.length && document.getElementById('alt-chart-ai-monthly')) {
                        var options = cloneOptions();
                        options.plugins.tooltip.callbacks = { label: function (ctx) { return 'AI-attributed jobs: ' + fmt(ctx.parsed.y); } };
                        mountChart('alt-chart-ai-monthly', {
                            type: 'line',
                            data: { labels: keys.map(monthLabel), datasets: [{ data: keys.map(function (k) { return byMonth[k]; }), borderColor: SEQ_BLUE, backgroundColor: SEQ_BLUE_FILL, borderWidth: 2, pointRadius: 3, pointBackgroundColor: SEQ_BLUE, fill: true, tension: 0.25 }] },
                            options: options
                        });
                    }
                    renderBar('alt-chart-ai-industries', indEntries, null, null, 'Layoffs: ');
                };
                AI_TRACKER_CHART();
            }
            initQuoteWall(aiRows);
            var chips = document.getElementById('alt-ai-companies');
            if (chips) chips.innerHTML = list.map(function (c) { return '<span class="alt-chip"><strong>' + escapeHtml(c.name) + '</strong> ' + fmt(c.jobs) + ' jobs</span>'; }).join('');
        }).catch(function () { setStatus('alt-ai-status', 'Could not load AI layoff data.', true); });
    }

    function initQuoteWall(aiRows) {
        var textEl = document.getElementById('alt-quote-text');
        var citeEl = document.getElementById('alt-quote-cite');
        if (!textEl || !citeEl) return;
        var quotes = aiRows.filter(function (r) { return r.ai_language && String(r.ai_language).trim() !== ''; });
        if (!quotes.length) { textEl.textContent = 'No AI language captured yet.'; return; }
        var index = 0;
        function show(i) {
            var q = quotes[i];
            textEl.textContent = '“' + q.ai_language + '”';
            citeEl.textContent = q.company_name + ' · ' + (q.source_name || '') + (q.layoff_date ? ' · ' + q.layoff_date : '');
        }
        show(0);
        if (quotes.length > 1) {
            var wall = document.getElementById('alt-quote-wall');
            setInterval(function () {
                index = (index + 1) % quotes.length;
                if (wall) { wall.classList.add('alt-quote-fading'); setTimeout(function () { show(index); wall.classList.remove('alt-quote-fading'); }, 300); }
                else show(index);
            }, 8000);
        }
    }

    function initCompanyHistory() {
        var wrap = document.querySelector('.alt-company-history');
        if (!wrap) return;
        var target = (wrap.getAttribute('data-company') || '').trim();
        apiGet('query', { company: target, per_page: 200, sort: 'layoff_date', dir: 'asc' }).then(function (res) {
            var matches = res.data || [];
            var summary = document.getElementById('alt-company-summary');
            if (!matches.length) { if (summary) summary.textContent = 'No recorded layoff rounds for this company yet.'; return; }
            var totalJobs = matches.reduce(function (s, r) { return s + r.job_count; }, 0);
            if (summary) summary.textContent = fmt(matches.length) + ' recorded rounds · ' + fmt(totalJobs) + ' total jobs cut';
            if (document.getElementById('alt-chart-company') && chartsAvailable()) {
                // Stored for the same reason as the AI tracker chart above: a
                // theme repaint must not cost another /query.
                COMPANY_CHART = function () {
                    var options = cloneOptions();
                    options.plugins.tooltip.callbacks = { label: function (ctx) { return 'Jobs: ' + fmt(ctx.parsed.y); } };
                    mountChart('alt-chart-company', {
                        type: 'bar',
                        data: { labels: matches.map(function (r) { return r.layoff_date || 'unknown'; }), datasets: [{ data: matches.map(function (r) { return r.job_count; }), backgroundColor: matches.map(function (r) { return r.ai_explicit ? ALT_RED : SEQ_BLUE; }), borderRadius: 4, maxBarThickness: 40 }] },
                        options: options
                    });
                };
                COMPANY_CHART();
            }
            var tbody = document.querySelector('#alt-company-table tbody');
            if (tbody) tbody.innerHTML = matches.slice().reverse().map(function (row) {
                var tags = (row.reason_tags || []).map(function (t) { return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[t] || t) + '</span>'; }).join(' ');
                var url = safeUrl(row.source_url);
                var source = url ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">' + escapeHtml(row.source_name || 'source') + '</a>' : escapeHtml(row.source_name || '—');
                return '<tr><td>' + escapeHtml(row.layoff_date || '—') + '</td><td class="alt-num">' + fmt(row.job_count) + '</td><td>' + tags + '</td><td>' + verificationBadge(row.verification_level) + '</td><td>' + source + '</td></tr>';
            }).join('');
        }).catch(function () { var s = document.getElementById('alt-company-summary'); if (s) s.textContent = 'Could not load company data.'; });
    }

    /* ------------------------------------------------------------------ */
    /* Region tabs + auto-updating narrative                               */
    /* ------------------------------------------------------------------ */

    // World = no country filter (the aggregate of EVERYTHING, including rows
    // whose region has no tab). Region lists are generous — the dropdown only
    // holds countries with data, and tabSelectableCountries() intersects, so
    // a listed country with no rows yet costs nothing and lights up the day
    // its first entry lands.
    var REGION_TABS = {
        world:  { label: 'worldwide', countries: [] },
        usa:    { label: 'in the United States', countries: ['United States'] },
        canada: { label: 'in Canada', countries: ['Canada'] },
        latam:  { label: 'in Latin America', countries: ['Mexico', 'Brazil', 'Argentina', 'Chile', 'Colombia', 'Peru', 'Uruguay', 'Paraguay', 'Bolivia', 'Ecuador', 'Venezuela', 'Costa Rica', 'Panama', 'Guatemala', 'Honduras', 'El Salvador', 'Nicaragua', 'Belize', 'Dominican Republic', 'Cuba', 'Jamaica', 'Haiti', 'Trinidad and Tobago', 'Guyana', 'Suriname'] },
        // Russia + Greenland ride with Europe (Moscow-centric coverage and
        // the Danish realm respectively); Turkey sits in the Middle East.
        europe: { label: 'in Europe', countries: ['United Kingdom', 'Ireland', 'France', 'Germany', 'Spain', 'Portugal', 'Italy', 'Netherlands', 'Belgium', 'Luxembourg', 'Switzerland', 'Austria', 'Sweden', 'Norway', 'Denmark', 'Finland', 'Iceland', 'Greenland', 'Poland', 'Czech Republic', 'Slovakia', 'Hungary', 'Romania', 'Bulgaria', 'Greece', 'Croatia', 'Slovenia', 'Serbia', 'Bosnia and Herzegovina', 'Albania', 'North Macedonia', 'Montenegro', 'Kosovo', 'Ukraine', 'Belarus', 'Moldova', 'Russia', 'Estonia', 'Latvia', 'Lithuania', 'Cyprus', 'Malta', 'Georgia', 'Armenia', 'Azerbaijan'] },
        uk:     { label: 'in the United Kingdom', countries: ['United Kingdom'] },
        mideast:{ label: 'in the Middle East', countries: ['Israel', 'UAE', 'Saudi Arabia', 'Qatar', 'Kuwait', 'Bahrain', 'Oman', 'Turkey', 'Jordan', 'Lebanon', 'Iraq', 'Iran', 'Syria', 'Yemen'] },
        africa: { label: 'in Africa', countries: ['South Africa', 'Nigeria', 'Kenya', 'Egypt', 'Morocco', 'Ghana', 'Ethiopia', 'Tanzania', 'Uganda', 'Tunisia', 'Algeria', 'Libya', 'Sudan', 'Zimbabwe', 'Zambia', 'Senegal', 'Ivory Coast', 'Cameroon', 'Angola', 'Mozambique', 'Democratic Republic of the Congo', 'Botswana', 'Namibia', 'Rwanda', 'Mauritius', 'Madagascar'] },
        asia:   { label: 'in Asia', countries: ['China', 'India', 'Japan', 'South Korea', 'Taiwan', 'Hong Kong', 'Singapore', 'Malaysia', 'Indonesia', 'Thailand', 'Vietnam', 'Philippines', 'Cambodia', 'Bangladesh', 'Pakistan', 'Sri Lanka', 'Nepal', 'Myanmar', 'Laos', 'Brunei', 'Mongolia', 'Kazakhstan', 'Uzbekistan', 'Kyrgyzstan', 'Turkmenistan', 'Tajikistan', 'Afghanistan', 'Bhutan', 'Maldives'] },
        aus:    { label: 'in Australia & Oceania', countries: ['Australia', 'New Zealand', 'Fiji', 'Papua New Guinea'] }
    };
    var ACTIVE_TAB = 'world';

    function applyTab(key, skipHash) {
        var tab = REGION_TABS[key];
        if (!tab) return;
        ACTIVE_TAB = key;
        // The tab drives the Countries filter. The dropdown only lists
        // countries WITH data, so a region whose countries all lack rows
        // would select nothing — and an empty selection means "world",
        // silently showing global rows under an "Africa" tab. Inject the
        // missing options so the filter genuinely scopes (to 0 rows if the
        // region is empty; the API filters by value, not by vocabulary).
        var sel = document.getElementById('alt-f-country');
        if (sel) {
            var have = {};
            Array.prototype.forEach.call(sel.options, function (o) { have[o.value] = 1; });
            tab.countries.forEach(function (c) {
                if (!have[c]) sel.appendChild(new Option(c, c));
            });
        }
        writeControl('alt-f-country', tab.countries.slice());
        if (key !== 'usa' && key !== 'world') writeControl('alt-f-state', []);
        document.querySelectorAll('.alt-tab').forEach(function (b) {
            b.classList.toggle('alt-tab-on', b.getAttribute('data-tab') === key);
        });
        // The US-states chart only makes sense on World/USA views
        var statesCard = document.getElementById('alt-bars-states');
        if (statesCard) {
            var card = statesCard.closest('.alt-mini') || statesCard.closest('.alt-chart-card');
            if (card) card.style.display = (key === 'usa' || key === 'world') ? '' : 'none';
        }
        if (!skipHash) { try { history.replaceState(null, '', '#' + key); } catch (e) { /* noop */ } }
        refreshAll();
        updateNarrative();
    }

    // THE SIGNAL BOARD (evolves the narrative strip; same container, same
    // aggregate plumbing, same click-to-filter machinery, Copy as post kept).
    // Rows: Workers / Verified layoffs / Explicitly AI-attributed / Largest
    // event. Columns: Today / This week / This month / YTD. Heat is scaled
    // WITHIN each row; every numeric cell filters the page through the
    // existing filter+URL machinery, and Largest-event cells open the entry
    // permalink instead (falling back to the company filter when the row has
    // no permalink page).
    function updateNarrative() {
        var el = document.getElementById('alt-narrative');
        if (!el) return;
        var tab = REGION_TABS[ACTIVE_TAB] || REGION_TABS.world;
        var now = new Date();
        var y = now.getFullYear();
        var base = tab.countries.length ? { country: tab.countries.join(',') } : {};
        var iso = function (d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); };
        var d7 = new Date(now.getTime() - 6 * 86400000);
        // Everything is stage=verified so the period totals AND each period's
        // largest-event pick share one basis (an announced 50K plan must not
        // headline a 9K verified week). include=leaders keeps each call to the
        // totals block plus one leaders query — the same cache keys the
        // server-rendered board warmed (alt_signal_board_periods in db.php).
        var P = {
            today: Object.assign({ from: iso(now), to: iso(now), stage: 'verified', include: 'leaders' }, base),
            week:  Object.assign({ from: iso(d7), to: iso(now), stage: 'verified', include: 'leaders' }, base),
            month: Object.assign({ from: y + '-' + pad2(now.getMonth() + 1) + '-01', to: iso(now), stage: 'verified', include: 'leaders' }, base),
            // Byte-identical to alt_signal_board_periods()['ytd'] in db.php.
            // A real to-date window, not the whole calendar year: see there.
            ytd:   Object.assign({ from: y + '-01-01', to: iso(now), stage: 'verified', include: 'leaders' }, base)
        };
        var KEYS = ['today', 'week', 'month', 'ytd'];
        // Server-inlined board: consumed at most once, and only when every
        // period's params match what this repaint was about to request (the
        // takeBoot rule — a site-timezone date rolling past the browser's
        // simply mismatches and falls back to a live fetch).
        var boot = null;
        if (BOOT && BOOT.board && KEYS.every(function (k) {
            return BOOT.board[k] && bootParamsMatch(P[k], BOOT.board[k].params || {});
        })) {
            boot = BOOT.board;
            BOOT.board = null;
        }
        var ready = boot
            ? Promise.resolve(KEYS.map(function (k) {
                return { totals: boot[k].totals || {}, leaders: boot[k].leader ? [boot[k].leader] : [] };
            }))
            : busyTrack('alt-narrative', 'Loading the at a glance board', function (signal) {
                return Promise.all(KEYS.map(function (k) { return apiGet('aggregate', P[k], signal); }));
            }, updateNarrative);
        ready.then(function (r) {
            var D = {};
            KEYS.forEach(function (k, i) {
                D[k] = { t: (r[i] || {}).totals || {}, l: ((r[i] || {}).leaders || [])[0] || null };
            });
            var today = MONTHS[now.getMonth()] + ' ' + now.getDate();
            var b = function (v) { return '<b>' + v + '</b>'; };
            var cols = { today: 'Today', week: 'This week', month: 'This month', ytd: y + ' YTD' };
            var meta = {};
            KEYS.forEach(function (k) {
                var p = P[k];
                meta[k] = p.years
                    ? { href: '?years=' + p.years, data: ' data-years="' + p.years + '"' }
                    : { href: '?from=' + p.from + '&amp;to=' + p.to, data: ' data-from="' + p.from + '" data-to="' + p.to + '"' };
            });
            // "Today and this month identical" (the 1st of the month) survives
            // as equal-column styling, never as duplicate columns.
            var eq = (D.today.t.jobs || 0) > 0
                && (D.today.t.jobs || 0) === (D.month.t.jobs || -1)
                && (D.today.t.entries || 0) === (D.month.t.entries || -1)
                && ((D.today.l || {}).company_name || '') === ((D.month.l || {}).company_name || '');
            var eqCls = function (k) { return eq && (k === 'today' || k === 'month') ? ' alt-sb-eq' : ''; };
            var eqTitle = ' title="Today and this month are identical so far"';
            var heat = function (v, max) {
                return (v > 0 && max > 0) ? ' style="background:rgba(' + tok('heat-rgb', '42,120,214') + ',' + (0.08 + 0.26 * v / max).toFixed(3) + ')"' : '';
            };
            var head = '<div class="alt-sb-row alt-sb-headrow" role="row"><span class="alt-sb-label" role="columnheader"><span class="screen-reader-text">Measure</span></span>'
                + KEYS.map(function (k) { return '<span class="alt-sb-col" role="columnheader">' + cols[k] + '</span>'; }).join('') + '</div>';
            var numRow = function (cls, label, key) {
                var max = 0;
                KEYS.forEach(function (k) { var v = D[k].t[key] || 0; if (v > max) max = v; });
                return '<div class="alt-sb-row ' + cls + '" role="row"><span class="alt-sb-label" role="rowheader">' + label + '</span>'
                    + KEYS.map(function (k) {
                        var v = D[k].t[key] || 0;
                        var e = eqCls(k), et = e ? eqTitle : '';
                        return v > 0
                            ? '<a class="alt-sb-cell alt-nfilter' + e + '" role="cell" href="' + meta[k].href + '"' + meta[k].data + et + heat(v, max) + '><b>' + fmt(v) + '</b></a>'
                            : '<span class="alt-sb-cell alt-sb-zero' + e + '" role="cell"' + et + '>0</span>';
                    }).join('') + '</div>';
            };
            var lmax = 0;
            KEYS.forEach(function (k) { var v = (D[k].l || {}).job_count || 0; if (v > lmax) lmax = v; });
            // One event legitimately leads several columns (this week sits
            // inside this month), which is correct and reads like a bug. The
            // first column carrying a leader keeps it plain; every later column
            // showing the same employer is marked "same event". Server parity:
            // the identical rule runs in page-tracker.php.
            var lseen = {};
            var lRow = '<div class="alt-sb-row alt-sb-r-largest" role="row"><span class="alt-sb-label" role="rowheader">Largest event</span>'
                + KEYS.map(function (k) {
                    var ld = D[k].l, v = (ld || {}).job_count || 0, e = eqCls(k);
                    if (!(v > 0)) return '<span class="alt-sb-cell alt-sb-zero' + e + '" role="cell">none</span>';
                    var name = String(ld.company_name);
                    var rep = Object.prototype.hasOwnProperty.call(lseen, name) ? ' alt-sb-ev-repeat' : '';
                    lseen[name] = true;
                    var body = '<b>' + escapeHtml(name) + '</b><span>' + fmt(v) + '</span>'
                        + (rep ? '<i class="alt-sb-again">same event</i>' : '');
                    return ld.permalink
                        ? '<a class="alt-sb-cell alt-sb-ev' + e + rep + '" role="cell" href="' + escapeHtml(ld.permalink) + '" title="Open this event&#39;s record page"' + heat(v, lmax) + '>' + body + '</a>'
                        : '<a class="alt-sb-cell alt-sb-ev alt-nfilter' + e + rep + '" role="cell" href="#" data-company="' + escapeHtml(name) + '" title="Filter the page to this company"' + heat(v, lmax) + '>' + body + '</a>';
                }).join('') + '</div>';
            // The footnote was one sentence doing four jobs, so a reader after
            // any one of them read all four. One clause per line, each with the
            // thing it explains. The "less ... more" heat legend is gone: it
            // rendered as stray words beside the columns and was never a control.
            /*
              THIS BOARD IS A THIRD TOTAL, AND IT SAYS SO.

              Its columns are fixed periods and it follows the region tabs
              only, by design. It also counts on the EFFECTIVE date and always
              has, which was harmless while the headline did too and is not
              harmless now that the headline defaults to the filing basis. Two
              correct totals sitting inches apart on different bases, with
              neither saying so, is the defect this whole change exists to
              remove. So the first line names the basis and, when the headline
              is on the other one, says in plain words that the two answer
              different questions and are not meant to match.
            */
            var foot = '<ul class="alt-sb-foot">'
                + '<li>' + (DATE_BASIS === 'effective'
                    ? 'Every row counts verified events on the day each cut takes effect, the same basis as the headline figure above.'
                    : 'Every row counts verified events on the day each cut takes effect. The headline figure above counts by filing date, so the two answer different questions and are not meant to match.')
                + '</li>'
                + '<li>The AI row counts cuts where the employer named AI, in words we hold.</li>'
                + '<li>Columns overlap, so they do not add up: this week sits inside this month, and one event can lead both.</li>'
                + '<li>Tap any number to filter the page to that period. This board follows the region tabs above; the date and dropdown filters below do not change it.</li>'
                + '</ul>';
            // Post-sized rewrite for the copy button: X counts any URL as 23
            // characters, and the weekly detail degrades in steps (with
            // largest event → bare) to stay under 280.
            var tJ = D.ytd.t.jobs || 0, tV = D.ytd.t.entries || 0, tAI = D.ytd.t.ai_jobs || 0;
            var wJ = D.week.t.jobs || 0, wE = D.week.t.entries || 0, wLead = D.week.l;
            var largestLoc = function (ld) {
                var c = ld && ld.country ? String(ld.country) : '';
                var s = ld && ld.state ? String(ld.state).toUpperCase() : '';
                if (c === 'United States') return s ? s + ', US' : 'US';
                return c;
            };
            var LINK = 'asktherecruiter.com/blog/ai-layoff-tracker/';
            var xLen = function (s2) { return s2.replace(LINK, 'xxxxxxxxxxxxxxxxxxxxxxx').length; };
            var lead = 'AI layoffs, ' + today + ': ' + fmt(tJ) + ' workers across ' + fmt(tV) + ' verified layoff' + (tV === 1 ? '' : 's') +
                ' ' + tab.label + ' in ' + y + (tAI ? ', ' + fmt(tAI) + ' where the employer named AI' : '') + '.';
            var tail = ' Live tracker (AskTheRecruiter.com): ' + LINK + ' #Layoffs #AI';
            var post = lead + tail;
            if (wJ > 0) {
                var wkBare = ' This week: ' + fmt(wJ) + ' workers across ' + fmt(wE) + ' layoff' + (wE === 1 ? '' : 's') + '.';
                var wkLoc = largestLoc(wLead);
                var wkLead = (wLead && wLead.job_count)
                    ? wkBare.slice(0, -1) + ', largest at ' + wLead.company_name + ' (' + fmt(wLead.job_count) + (wkLoc ? ' · ' + wkLoc : '') + ').'
                    : '';
                [wkLead, wkBare].some(function (wk) {
                    if (wk && xLen(lead + wk + tail) <= 278) { post = lead + wk + tail; return true; }
                    return false;
                });
            }
            // "At a glance" is the <summary> of the disclosure this board lives
            // in now, so repeating it inside the panel said it twice.
            el.innerHTML = '<div class="alt-narrative-head"><span>Verified layoffs ' + tab.label + ' · ' + b(today) + '</span>' +
                '<button type="button" class="alt-btn alt-btn-sm alt-narrative-copy" title="Copy a post-sized version of this summary (fits in one X/Twitter post)">Copy as post</button></div>' +
                '<div class="alt-sb" role="table" aria-label="Verified layoffs by period">' + head +
                numRow('alt-sb-r-workers', 'Workers', 'jobs') +
                numRow('alt-sb-r-events', 'Verified layoffs', 'entries') +
                numRow('alt-sb-r-ai', 'Explicitly AI-attributed', 'ai_jobs') +
                lRow + '</div>' + foot;
            var copyBtn = el.querySelector('.alt-narrative-copy');
            if (copyBtn) copyBtn.addEventListener('click', function () {
                if (navigator.clipboard) navigator.clipboard.writeText(post).then(function () { copyBtn.textContent = 'Copied!'; setTimeout(function () { copyBtn.textContent = 'Copy as post'; }, 1500); });
            });
            // onclick (not addEventListener): updateNarrative re-runs on every
            // tab switch and must not stack duplicate handlers.
            el.onclick = function (e) {
                var a = e.target && e.target.closest ? e.target.closest('.alt-nfilter') : null;
                if (!a) return;
                e.preventDefault();
                if (a.getAttribute('data-company')) writeControl('alt-f-company', a.getAttribute('data-company'));
                if (a.getAttribute('data-from')) {
                    writeControl('alt-f-from', a.getAttribute('data-from'));
                    writeControl('alt-f-to', a.getAttribute('data-to'));
                    writeControl('alt-f-years', []);
                }
                if (a.getAttribute('data-years')) {
                    writeControl('alt-f-years', [a.getAttribute('data-years')]);
                    writeControl('alt-f-from', '');
                    writeControl('alt-f-to', '');
                }
                updateRangeLabel();
                updateDropdownSummaries();
                refreshAll();
            };
        // A failure used to blank the board, which is indistinguishable from a
        // board with nothing to report. It now keeps the failed state busyTrack
        // put there, with its retry, and only supplies one when the throw came
        // from the render above (busyTrack having already cleared its own).
        }).catch(function () {
            if (!BUSY['alt-narrative']) busyFail('alt-narrative', 'We could not load this data.', updateNarrative);
        });
    }

    // Hero plumbing: "Search the record" scrolls to and focuses the search
    // box (the button still works as a plain #alt-search anchor without JS),
    // and any in-page anchor whose target sits inside a closed <details>
    // (e.g. the coverage ribbon's "How complete, measured") opens the chain
    // of ancestors so the landing is visible, not swallowed.
    function initHeroActions() {
        var heroSearch = document.getElementById('alt-hero-search');
        if (heroSearch) heroSearch.addEventListener('click', function (e) {
            var s = document.getElementById('alt-search');
            if (!s) return;
            e.preventDefault();
            s.scrollIntoView({ behavior: 'smooth', block: 'center' });
            s.focus({ preventScroll: true });
        });
        var openDetailsForHash = function () {
            var id = (location.hash || '').slice(1);
            var t = id ? document.getElementById(id) : null;
            if (!t || !t.closest) return;
            for (var d = t.closest('details'); d; d = d.parentElement ? d.parentElement.closest('details') : null) {
                d.open = true;
            }
        };
        window.addEventListener('hashchange', openDetailsForHash);
        openDetailsForHash();
    }

    // "Which countries are in which tab?" — rendered from REGION_TABS itself
    // so the on-page documentation can never drift from the actual behavior.
    function renderRegionDefs() {
        var el = document.getElementById('alt-region-defs');
        if (!el) return;
        var names = { usa: 'USA', canada: 'Canada', latam: 'Latin America', europe: 'Europe',
            uk: 'UK', mideast: 'Middle East', africa: 'Africa', asia: 'Asia', aus: 'Australia' };
        var html = '';
        Object.keys(names).forEach(function (k) {
            html += '<p><b>' + names[k] + ':</b> ' + REGION_TABS[k].countries.join(', ') + '</p>';
        });
        html += '<p><b>World</b> is the unfiltered total. It includes every entry, even ones whose country has no regional tab. It also includes the honest "Multiple countries" bucket, for cuts that span several countries. No single region can claim those without double counting.</p>';
        el.innerHTML = html;
    }

    // The methodology's worked example quotes our own H1 figure — keep it
    // live from the API so it can never drift stale again (it had drifted
    // 83% behind after the nationwide WARN backfill; super test 2026-07-15).
    function updateWorkedExample() {
        var el = document.getElementById('alt-worked-ours');
        if (!el) return;
        // Window derives from the clock: current year's H1 once July starts,
        // else last year's H1 — so the label and figure can never go stale.
        var now = new Date();
        var exYear = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
        apiGet('aggregate', { years: String(exYear), country: 'United States', stage: 'verified' }).then(function (r) {
            var h1 = 0;
            (r.series || []).forEach(function (m) {
                if (m.month >= exYear + '-01' && m.month <= exYear + '-06') h1 += m.jobs;
            });
            if (h1 > 0) el.textContent = 'about ' + fmt(Math.round(h1 / 1000) * 1000);
        }).catch(function () { /* keep the server-rendered fallback text */ });
    }

    // Light the tab matching the current country selection WITHOUT overwriting
    // filters (used at boot so saved selections survive page loads).
    function syncTabVisual() {
        var sel = selectedList('alt-f-country').slice().sort().join('|');
        ACTIVE_TAB = 'world';
        Object.keys(REGION_TABS).forEach(function (k) {
            // Compare against the SELECTABLE subset (countries with data) —
            // the raw config list can never all be selected.
            if (k !== 'world' && sel && tabSelectableCountries(k).sort().join('|') === sel) ACTIVE_TAB = k;
        });
        document.querySelectorAll('.alt-tab').forEach(function (b) {
            b.classList.toggle('alt-tab-on', b.getAttribute('data-tab') === ACTIVE_TAB);
        });
    }

    function initTabs() {
        var bar = document.getElementById('alt-tabs');
        if (!bar) return;
        bar.querySelectorAll('.alt-tab').forEach(function (btn) {
            btn.addEventListener('click', function () { applyTab(btn.getAttribute('data-tab')); });
        });
        var fromHash = (location.hash || '').replace('#', '');
        if (REGION_TABS[fromHash]) {
            applyTab(fromHash, true);   // explicit deep link wins
        } else {
            syncTabVisual();            // respect restored filters
            updateNarrative();
        }
    }

    /* ------------------------------------------------------------------ */
    /* Toolbar chrome: search, sort, Filters panel, quick views            */
    /* ------------------------------------------------------------------ */

    // Writing the control IS applying the sort: queryParams() reads it through
    // currentSort() on every fetch, and the caller follows with refreshAll().
    // It used to also have to tell DataTables the column index to order by,
    // which meant the sort options were coupled to the table's column order.
    function setSort(val) {
        var sel = document.getElementById('alt-sort');
        if (sel && SORT_PARAMS[val] && sel.value !== val) sel.value = val;
    }
    function currentSort() { var s = document.getElementById('alt-sort'); return s ? s.value : 'newest'; }

    var QUICK_VIEWS = {
        ai: {
            apply: function () { var el = document.getElementById('alt-f-ai'); if (el) el.checked = true; },
            clear: function () { var el = document.getElementById('alt-f-ai'); if (el) el.checked = false; },
            active: function () { return !!readControl('alt-f-ai'); }
        },
        month: {
            apply: function () {
                var now = new Date();
                writeControl('alt-f-years', [String(now.getFullYear())]);
                writeControl('alt-f-months', [String(now.getMonth() + 1)]);
                writeControl('alt-f-quarters', []);
            },
            clear: function () { writeControl('alt-f-months', []); },
            active: function () {
                var now = new Date();
                var ys = readControl('alt-f-years') || [], ms = readControl('alt-f-months') || [];
                return ms.length === 1 && ms[0] === String(now.getMonth() + 1)
                    && ys.length === 1 && ys[0] === String(now.getFullYear());
            }
        },
        largest: {
            apply: function () { setSort('largest'); },
            clear: function () { setSort('newest'); },
            active: function () { return currentSort() === 'largest'; }
        },
        sec: {
            apply: function () {
                var el = document.getElementById('alt-f-verification');
                if (el) { if (el.multiple) writeControl('alt-f-verification', ['gold']); else el.value = 'gold'; }
            },
            clear: function () {
                var el = document.getElementById('alt-f-verification');
                if (el) { if (el.multiple) writeControl('alt-f-verification', []); else el.value = ''; }
            },
            active: function () {
                var v = readControl('alt-f-verification');
                if (Array.isArray(v)) return v.length === 1 && v[0] === 'gold';
                return v === 'gold';
            }
        },
        announced: {
            apply: function () { var el = document.getElementById('alt-f-announced'); if (el) el.checked = true; },
            clear: function () { var el = document.getElementById('alt-f-announced'); if (el) el.checked = false; },
            active: function () { return !!readControl('alt-f-announced'); }
        },
        tech: {
            apply: function () { writeControl('alt-f-industry', ['Technology']); },
            clear: function () { writeControl('alt-f-industry', []); },
            active: function () {
                var v = readControl('alt-f-industry');
                var arr = Array.isArray(v) ? v : (v ? [v] : []);
                return arr.length === 1 && arr[0] === 'Technology';
            }
        }
    };

    /*
      QUICK DATE RANGES. Each returns the [from, to] it names, or null for "no
      date bound at all", and each is checked for active state by recomputing
      its own range and comparing, so the marked pill is the one that actually
      matches what the page is showing rather than the one that was last
      clicked. A hand-typed range in the popover that happens to equal a preset
      therefore lights that preset, which is correct: the page IS showing it.

      isoDay() is the browser's local day, matching every other date the front
      end computes (the board's periods, the trend buckets). The server counts
      in site time; the two differ by at most a day at the boundary, and the
      Date Range popover has always had the same property.
    */
    function isoDay(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
    function daysAgo(n) { return new Date(Date.now() - n * 86400000); }
    var DATE_PRESETS = {
        today: function () { var t = isoDay(new Date()); return [t, t]; },
        d7:    function () { return [isoDay(daysAgo(6)), isoDay(new Date())]; },
        d30:   function () { return [isoDay(daysAgo(29)), isoDay(new Date())]; },
        // "Last quarter" as the trailing 90 days, not the previous calendar
        // quarter. The Quarters dropdown already offers calendar quarters, and
        // two controls whose labels both say "quarter" and mean different
        // windows is how a reader stops trusting either.
        d90:   function () { return [isoDay(daysAgo(89)), isoDay(new Date())]; },
        ytd:   function () { return [new Date().getFullYear() + '-01-01', isoDay(new Date())]; },
        all:   function () { return null; }
    };

    // Presets write the same from/to controls the Date Range popover writes, so
    // there is one date range on this page and not two. The year, quarter and
    // month dropdowns are cleared because alt_db_where ANDs them with the
    // range: "Last 7 days" left standing beside years=2026 is an intersection,
    // and beside years=2024 it is an empty one.
    function applyDatePreset(key) {
        var r = (DATE_PRESETS[key] || DATE_PRESETS.all)();
        writeControl('alt-f-years', []);
        writeControl('alt-f-quarters', []);
        writeControl('alt-f-months', []);
        writeControl('alt-f-from', r ? r[0] : '');
        writeControl('alt-f-to', r ? r[1] : '');
    }

    function datePresetActive(key) {
        var from = readControl('alt-f-from') || '';
        var to = readControl('alt-f-to') || '';
        var years = readControl('alt-f-years') || [];
        var quarters = readControl('alt-f-quarters') || [];
        var months = readControl('alt-f-months') || [];
        // Any period dropdown in play means the view is not the bare range this
        // pill names, so nothing is marked rather than something being marked
        // that would not reproduce the numbers on screen.
        if (years.length || quarters.length || months.length) return false;
        var r = (DATE_PRESETS[key] || DATE_PRESETS.all)();
        if (!r) return from === '' && to === '';
        return from === r[0] && to === r[1];
    }

    function updateDatePresetStates() {
        document.querySelectorAll('.alt-dp').forEach(function (btn) {
            var on = datePresetActive(btn.getAttribute('data-dp'));
            btn.classList.toggle('alt-dp-on', on);
            btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        });
    }

    function updateQuickViewStates() {
        updateDatePresetStates();
        Array.prototype.forEach.call(document.querySelectorAll('.alt-qv'), function (btn) {
            var qv = QUICK_VIEWS[btn.getAttribute('data-qv')];
            btn.classList.toggle('alt-qv-on', !!(qv && qv.active()));
        });
    }

    function initChrome() {
        var search = document.getElementById('alt-search');
        var searchTimer = null;
        if (search) search.addEventListener('input', function () {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(refreshAll, 300);
        });

        var sort = document.getElementById('alt-sort');
        if (sort) sort.addEventListener('change', function () { setSort(sort.value); refreshAll(); });

        Array.prototype.forEach.call(document.querySelectorAll('.alt-qv'), function (btn) {
            btn.addEventListener('click', function () {
                var qv = QUICK_VIEWS[btn.getAttribute('data-qv')];
                if (!qv) return;
                if (qv.active()) qv.clear(); else qv.apply();
                refreshAll();
            });
        });

        // Quick date ranges. Not a toggle: tapping the active one again would
        // have to mean "all time", and a pill that silently becomes a different
        // pill on a second tap is how a reader loses the thread of what is
        // filtered. "All time" is its own control in the row.
        Array.prototype.forEach.call(document.querySelectorAll('.alt-dp'), function (btn) {
            btn.addEventListener('click', function () {
                applyDatePreset(btn.getAttribute('data-dp'));
                refreshAll();
            });
        });

        // Per-chart downloads: canvas charts save as PNG (white background);
        // HTML bar lists save their current data as a small CSV.
        var BAR_AGG_KEY = {
            'alt-bars-industries': ['top_industries', 'by-industry'],
            'alt-bars-states': ['top_states', 'by-us-state'],
            'alt-bars-countries': ['top_countries', 'by-country'],
            'alt-bars-roles': ['top_roles', 'by-role'],
            'alt-bars-sourcetypes': ['source_types', 'by-data-source']
        };
        // Computed lists export exactly what the card shows for the current
        // filters (LAST_AGG is the filtered aggregate).
        var BAR_ROWS_FN = {
            'alt-bars-leaders': function () {
                return ((LAST_AGG && LAST_AGG.leaders) || []).map(function (l) {
                    return [l.company_name, l.job_count, l.ai_explicit ? l.job_count : 0];
                });
            },
            'alt-bars-repeat': function () {
                return ((LAST_AGG && LAST_AGG.repeat_companies) || []).map(function (e) {
                    return [e[0], e[1], e[2]];
                });
            },
            'alt-bars-ai-intensity': function () {
                // Verified numerator over verified denominator, matching the
                // card (see renderCharts).
                return verifiedBasis((LAST_AGG && LAST_AGG.top_industries) || [])
                    .filter(function (e) { return e[1] >= 1000 && e[2] > 0; })
                    .map(function (e) { return [e[0], Math.round(100 * e[2] / e[1]), Math.round(100 * e[2] / e[1])]; })
                    .sort(function (a, b) { return b[1] - a[1]; });
            }
        };
        // The three computed cards above are not job counts, so they must not
        // inherit the job-count header.
        var BAR_CSV_HEADER = {
            'alt-bars-leaders': 'label,jobs,ai_attributed_jobs',
            'alt-bars-repeat': 'label,rounds,ai_attributed_rounds',
            'alt-bars-ai-intensity': 'label,ai_share_pct_of_verified,ai_share_pct_of_verified'
        };
        Array.prototype.forEach.call(document.querySelectorAll('.alt-chart-dl'), function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var t = btn.getAttribute('data-dl');
                var kind = btn.getAttribute('data-kind');
                if (kind === 'png' && t === 'alt-chart-aimap') {
                    // The map is now an SVG (not a Chart.js canvas), so rasterize
                    // it: serialize → data-URL → draw onto an offscreen canvas
                    // over a white ground → PNG. Self-contained (inline styles,
                    // no external images) so toDataURL stays untainted.
                    exportMapPng();
                } else if (kind === 'png') {
                    var ch = CHARTS[t];
                    if (!ch) return;
                    var src = ch.canvas;
                    var c = document.createElement('canvas');
                    // Reserve a strip under the chart for the credit. Exported
                    // charts get screenshotted into stories and posts, and an
                    // unbranded PNG travels with no way back to the source, so
                    // the attribution has to be baked into the pixels.
                    var strip = Math.max(22, Math.round(src.height * 0.07));
                    c.width = src.width; c.height = src.height + strip;
                    var ctx = c.getContext('2d');
                    ctx.fillStyle = tok('surface', '#ffffff');
                    ctx.fillRect(0, 0, c.width, c.height);
                    ctx.drawImage(src, 0, 0);
                    ctx.fillStyle = tok('tint', '#eef3ee');
                    ctx.fillRect(0, src.height, c.width, strip);
                    var fs = Math.max(11, Math.round(strip * 0.5));
                    ctx.font = '600 ' + fs + 'px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
                    ctx.textBaseline = 'middle';
                    ctx.fillStyle = tok('accent', '#4f7257');
                    ctx.fillText('AI Layoff Tracker  ·  asktherecruiter.com',
                                 10, src.height + strip / 2);
                    ctx.font = Math.max(10, fs - 2) + 'px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
                    ctx.fillStyle = tok('muted', '#5e6675');
                    var stamp = 'Source-linked data · ' + new Date().toISOString().slice(0, 10);
                    ctx.textAlign = 'right';
                    ctx.fillText(stamp, c.width - 10, src.height + strip / 2);
                    ctx.textAlign = 'left';
                    var a = document.createElement('a');
                    a.href = c.toDataURL('image/png');
                    a.download = 'ai-layoff-tracker-' + t.replace('alt-chart-', '') + '.png';
                    a.click();
                } else if (t === 'alt-chart-conversion') {
                    // Conversion CSV keeps its own columns (percentages,
                    // maturity status) and includes the future-dated pending
                    // months the chart deliberately leaves out.
                    var crows = ((CONVERSION_DATA && CONVERSION_DATA.series) || []);
                    if (!crows.length) return;
                    var cwin = CONVERSION_DATA.window_months || 6;
                    var ccsv = 'announcement_month,announced_jobs,announced_entries,matched_verified_jobs,matched_entries,conversion_pct,window_months,status\n'
                        + crows.map(function (p) {
                            return [p.month, p.announced_jobs, p.announced_entries, p.matched_jobs, p.matched_entries,
                                (p.conversion_pct === null ? '' : p.conversion_pct), cwin, p.status].join(',');
                        }).join('\n');
                    var cblob = new Blob([ccsv], { type: 'text/csv' });
                    var ca = document.createElement('a');
                    ca.href = URL.createObjectURL(cblob);
                    ca.download = 'ai-layoff-tracker-announced-to-verified-conversion.csv';
                    ca.click();
                    URL.revokeObjectURL(ca.href);
                } else {
                    var meta = BAR_AGG_KEY[t];
                    // Through verifiedBasis() so the file holds the numbers the
                    // card drew. Downloading a CSV whose column disagreed with
                    // the bar above the button is how a wrong figure escapes
                    // the page and turns up in someone else's chart.
                    var rows = BAR_ROWS_FN[t] ? BAR_ROWS_FN[t]()
                        : verifiedBasis((meta && LAST_AGG && LAST_AGG[meta[0]]) || []);
                    if (!rows.length) return;
                    var csv = (BAR_CSV_HEADER[t] || 'label,verified_jobs,ai_attributed_verified_jobs') + '\n' + rows.map(function (r) {
                        return '"' + String(r[0]).replace(/"/g, '""') + '",' + r[1] + ',' + (r[2] || 0);
                    }).join('\n');
                    var blob = new Blob([csv], { type: 'text/csv' });
                    var a2 = document.createElement('a');
                    a2.href = URL.createObjectURL(blob);
                    a2.download = 'ai-layoff-tracker-' + (meta ? meta[1] : t) + '.csv';
                    a2.click();
                    URL.revokeObjectURL(a2.href);
                }
            });
        });

        // Mini-chart expand: toggle the card to full width/height, then
        // re-render so bar lists show more rows and canvases re-measure.
        Array.prototype.forEach.call(document.querySelectorAll('.alt-mini .alt-expand'), function (btn) {
            btn.addEventListener('click', function () {
                var card = btn.closest('.alt-mini');
                if (!card) return;
                var on = card.classList.toggle('alt-expanded');
                btn.setAttribute('aria-label', on ? 'Collapse chart' : 'Expand chart');
                btn.title = on ? 'Collapse' : 'Expand';
                if (LAST_AGG) renderCharts(LAST_AGG);
                renderConversionChart(); // standalone card; re-measures on toggle
            });
        });

        updateQuickViewStates();
    }

    /* ------------------------------------------------------------------ */
    /* Boot                                                                */
    /* ------------------------------------------------------------------ */

    function fillSelect(id, values) {
        var el = document.getElementById(id);
        if (!el) return;
        (values || []).forEach(function (v) {
            var opt = document.createElement('option');
            opt.value = v; opt.textContent = v;
            el.appendChild(opt);
        });
    }

    // ---- Share per chart: copy a deep link that reproduces the current
    // filter state, scrolled to the chart. (Embed lives on a dedicated
    // frame-safe route — the tracker page itself is never framed, per the
    // anti-clickjacking rule in ai-layoff-tracker.php.)
    function copyText(txt, cb) {
        var ok = function () { if (cb) cb(); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(txt).then(ok, function () { fallbackCopy(txt); ok(); });
        } else { fallbackCopy(txt); ok(); }
    }
    function fallbackCopy(txt) {
        var ta = document.createElement('textarea'); ta.value = txt;
        ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta);
        ta.focus(); ta.select(); try { document.execCommand('copy'); } catch (e) {} ta.remove();
    }
    function shareBase() { return window.location.origin + window.location.pathname; }
    function chartIdFor(btns) {
        var dl = btns.querySelector('.alt-chart-dl[data-dl]');
        return dl ? dl.getAttribute('data-dl') : null;
    }
    function flashBtn(btn) {
        var title = btn.getAttribute('title');
        btn.classList.add('alt-copied'); btn.setAttribute('title', 'Link copied ✓');
        setTimeout(function () { btn.classList.remove('alt-copied'); btn.setAttribute('title', title); }, 1600);
    }
    var SHARE_SVG = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>';
    var EMBED_SVG = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 8l-4 4 4 4M16 8l4 4-4 4"/></svg>';
    /*
      Charts the frame-safe embed route (?alt_chart_embed) can render.

      THIS LIST IS WHAT DECIDES HOW MANY ICONS A CARD SHOWS. Share, CSV and
      expand are on every chart card; embed is added only for an id in here.
      So an omission is not invisible - it prints a three-icon toolbar next to
      two four-icon ones at the same y, and the reader is left to guess which
      card is missing a control and why. On 2026-08-10 the "Who is cutting,
      and why" band read 3, 3, 3, 3 while the band above it read 4, 4.

      The four bar cards added here draw from the same /aggregate payload
      through the same renderBarList as the three already listed, so the embed
      route renders them with no new data path. Their basis sentences travel
      with them: page-chart-embed.php now ships the note element each one
      writes into, which the earlier bar embeds were quietly dropping.

      ONE CARD IS STILL DELIBERATELY ABSENT: alt-bars-claims-states. It is
      official DOL jobless-claims data, drawn grey, labelled "context only,
      not our counts", and fetched from /claims rather than /aggregate. An
      embed of it would travel to another site under this tracker's frame with
      a number this tracker did not collect, which is exactly the confusion the
      grey and the label exist to prevent. Its toolbar is short on purpose.
    */
    var EMBED_OK = { 'alt-chart-weekly':1, 'alt-chart-ai-share-trend':1, 'alt-chart-ai-cumulative':1, 'alt-chart-yoy':1, 'alt-chart-reasons':1, 'alt-chart-aimap':1, 'alt-bars-industries':1, 'alt-bars-states':1, 'alt-bars-countries':1, 'alt-bars-roles':1, 'alt-bars-sourcetypes':1, 'alt-bars-leaders':1, 'alt-bars-repeat':1, 'alt-bars-ai-intensity':1 };
    function embedSnippet(id) {
        var f = qs(currentParams());
        var src = shareBase() + '?alt_chart_embed=1&chart=' + encodeURIComponent(id) + (f ? '&' + f : '');
        var h = id === 'alt-chart-aimap' ? 470 : 360;
        return '<iframe src="' + src + '" width="100%" height="' + h + '" style="border:1px solid #e5e7eb;border-radius:12px;max-width:640px" title="AI Layoff Tracker" loading="lazy"></iframe>';
    }
    function closeEmbedPops(except) { document.querySelectorAll('.alt-embed-pop').forEach(function (p) { if (p !== except) p.remove(); }); }
    function openEmbedPop(btns, id) {
        var existing = btns.querySelector('.alt-embed-pop');
        closeEmbedPops(existing);
        if (existing) { existing.remove(); return; }
        var pop = document.createElement('div'); pop.className = 'alt-embed-pop';
        pop.innerHTML = '<h4>Embed this chart</h4><textarea readonly></textarea>' +
            '<button type="button" class="alt-btn alt-btn-sm alt-embed-copy">Copy embed code</button>' +
            '<p class="alt-embed-hint">Reflects the filters active right now.</p>';
        var ta = pop.querySelector('textarea'); ta.value = embedSnippet(id);
        pop.addEventListener('click', function (e) { e.stopPropagation(); });
        pop.querySelector('.alt-embed-copy').addEventListener('click', function () {
            ta.focus(); ta.select();
            copyText(ta.value, function () { var b = pop.querySelector('.alt-embed-copy'); b.textContent = 'Copied ✓'; setTimeout(function () { b.textContent = 'Copy embed code'; }, 1500); });
        });
        btns.appendChild(pop);
    }
    function initShareEmbed() {
        document.querySelectorAll('.alt-chart-card').forEach(function (card) {
            var btns = card.querySelector('.alt-chart-btns');
            if (!btns) return;
            var id = chartIdFor(btns);
            if (!id) return;
            if (!card.id) card.id = 'card-' + id;
            var sh = document.createElement('button');
            sh.type = 'button'; sh.className = 'alt-chart-share'; sh.title = 'Copy a link to this filtered view (live data: numbers update as new sources are verified)';
            sh.setAttribute('aria-label', 'Share this view'); sh.innerHTML = SHARE_SVG;
            btns.insertBefore(sh, btns.firstChild);
            sh.addEventListener('click', function (e) {
                e.stopPropagation();
                var url = shareBase() + '?' + qs(currentParams()) + '#' + card.id;
                if (navigator.share) { navigator.share({ title: 'AI Layoff Tracker', url: url }).then(function () { flashBtn(sh); }, function () { copyText(url, function () { flashBtn(sh); }); }); }
                else copyText(url, function () { flashBtn(sh); });
            });
            if (EMBED_OK[id]) {
                var em = document.createElement('button');
                em.type = 'button'; em.className = 'alt-chart-embed'; em.title = 'Get an embed code';
                em.setAttribute('aria-label', 'Embed this chart'); em.innerHTML = EMBED_SVG;
                btns.insertBefore(em, sh.nextSibling);
                em.addEventListener('click', function (e) { e.stopPropagation(); openEmbedPop(btns, id); });
            }
        });
        document.addEventListener('click', function () { closeEmbedPops(null); });
        // Card ids are assigned above (after render), so the browser's initial
        // anchor jump missed them — honor a #card-… hash from a shared link.
        // Charts render async and shift layout, so retry as it settles and bail
        // the moment the recipient takes over scrolling.
        if (window.location.hash && /^#card-/.test(window.location.hash)) {
            var target = document.getElementById(window.location.hash.slice(1));
            if (target) {
                var userScrolled = false;
                var yield_ = function () { userScrolled = true; };
                window.addEventListener('wheel', yield_, { passive: true, once: true });
                window.addEventListener('touchmove', yield_, { passive: true, once: true });
                [450, 1600, 3200].forEach(function (ms) {
                    setTimeout(function () { if (!userScrolled) target.scrollIntoView({ behavior: ms > 600 ? 'smooth' : 'auto', block: 'start' }); }, ms);
                });
            }
        }
    }

    // Report one-pager exports: Print→PDF (zero-dep) + PNG (lazy html2canvas,
    // loaded only on click so the report page stays light).
    var _h2cPromise = null;
    function loadHtml2Canvas() {
        if (window.html2canvas) return Promise.resolve(window.html2canvas);
        if (_h2cPromise) return _h2cPromise;
        _h2cPromise = new Promise(function (resolve, reject) {
            var s = document.createElement('script');
            s.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
            s.onload = function () { window.html2canvas ? resolve(window.html2canvas) : reject(new Error('h2c missing')); };
            s.onerror = function () { reject(new Error('h2c load failed')); };
            document.head.appendChild(s);
        });
        return _h2cPromise;
    }
    function initReportExports() {
        var card = document.getElementById('alt-report-card');
        if (!card) return;
        var printBtn = document.querySelector('.alt-report-print');
        if (printBtn) printBtn.addEventListener('click', function () { window.print(); });
        var pngBtn = document.querySelector('.alt-report-png');
        if (pngBtn) pngBtn.addEventListener('click', function () {
            if (pngBtn.disabled) return;
            pngBtn.disabled = true; var orig = pngBtn.textContent; pngBtn.textContent = 'Rendering…';
            loadHtml2Canvas().then(function (h2c) {
                return h2c(card, { backgroundColor: tok('surface', '#ffffff'), scale: 2, useCORS: true, logging: false });
            }).then(function (canvas) {
                var a = document.createElement('a');
                a.href = canvas.toDataURL('image/png');
                a.download = 'asktherecruiter-report-' + (card.getAttribute('data-slug') || 'card') + '.png';
                document.body.appendChild(a); a.click(); a.remove();
                pngBtn.textContent = 'Saved ✓'; setTimeout(function () { pngBtn.textContent = orig; pngBtn.disabled = false; }, 1600);
            }).catch(function () {
                pngBtn.textContent = 'Use PDF instead'; setTimeout(function () { pngBtn.textContent = orig; pngBtn.disabled = false; }, 2200);
            });
        });
    }

    // Was jQuery's $(fn). The script is deferred, so DOMContentLoaded may
    // already have fired by the time it runs; check readyState rather than
    // waiting for an event that has been and gone.
    function onReady(fn) {
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
        else fn();
    }

    onReady(function () {
        // Embed mode: a single frame-safe chart driven by URL filter params
        // (window.altData.embedParams). Render only the one chart present and
        // skip the whole filter/table/tabs surface.
        if (window.altData && window.altData.embed) {
            if (chartsAvailable()) {
                Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
                Chart.defaults.color = INK.muted;
            }
            DASH_PRESENT = true;
            if (document.getElementById('alt-chart-aimap')) initAiMap();
            fetchAndRenderAggregate();
            return;
        }
        initReportExports();
        document.querySelectorAll('.alt-sb-copy').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var fig = btn.closest('.alt-soundbite');
                var q = fig && fig.querySelector('.alt-sb-text');
                if (!q) return;
                // Paste the VERIFICATION URL with the text. A statement lands
                // in an editor's inbox stripped of its markup, so a link that
                // only exists as an <a> beneath it does not travel; the editor
                // then has a claim with no way to check it. Source line too, so
                // the pitch is self-contained.
                var body = q.textContent.replace(/[“”"]/g, '').trim();
                var vlink = fig.querySelector('.alt-sb-link');
                if (vlink && vlink.href) body += '\n\nCheck this figure (filters pre-applied): ' + vlink.href;
                body += '\nSource: AI Layoff Tracker, asktherecruiter.com/blog/ai-layoff-tracker/press/';
                copyText(body, function () {
                    var o = btn.textContent; btn.textContent = 'Copied ✓';
                    setTimeout(function () { btn.textContent = o; }, 1500);
                });
            });
        });
        var citeDate = document.getElementById('alt-cite-date');
        if (citeDate) citeDate.textContent = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        var citeCopy = document.getElementById('alt-cite-copy');
        if (citeCopy) citeCopy.addEventListener('click', function () {
            var el = document.getElementById('alt-cite-text');
            if (el && navigator.clipboard) { navigator.clipboard.writeText(el.textContent.replace(/\s+/g, ' ').trim()); citeCopy.textContent = 'Copied ✓'; setTimeout(function () { citeCopy.textContent = 'Copy'; }, 1500); }
        });

        initStatsMeta();
        renderSourceHealth();

        var needsData = document.getElementById('alt-cards') || document.getElementById('alt-stats-bar')
            || document.querySelector('.alt-dashboard') || document.querySelector('.alt-ai-tracker')
            || document.querySelector('.alt-company-history');
        if (!needsData) return;

        if (chartsAvailable()) {
            Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
            Chart.defaults.color = INK.muted;
            initConversionChart();
        }
        DASH_PRESENT = !!document.querySelector('.alt-dashboard');
        if (DASH_PRESENT) initShareEmbed();

        // Standalone AI / company pages don't use the shared filter surface.
        initAiTracker();
        initCompanyHistory();
        if (document.getElementById('alt-chart-aimap')) initAiMap();
        initMethodologyAnchors();
        renderProvenance();

        var hasFilterSurface = document.getElementById('alt-cards') || document.getElementById('alt-stats-bar') || DASH_PRESENT;
        if (!hasFilterSurface) return;

        // The whole filter surface waits on facets, so the server-inlined copy
        // (when present and unfiltered) removes the one fetch that gated
        // everything else; the aggregate and first query page below then also
        // resolve from the bootstrap, making the default first paint zero-fetch.
        var bootFacets = takeBoot('facets', {});
        // The whole filter surface waits on this one call, so the dropdowns
        // carry the busy state for it. Retrying re-runs the same boot, which
        // is why the retry here is a reload rather than a second init pass:
        // initTracker/initChrome below are one-shot wiring.
        var facetsReady = bootFacets
            ? Promise.resolve(bootFacets)
            : busyTrack('alt-filterbar-body', 'Loading the filters', function (signal) {
                return apiGet('facets', {}, signal);
            }, function () { window.location.reload(); });
        facetsReady.then(function (facets) {
            fillSelect('alt-f-industry', facets.industries);
            fillSelect('alt-f-country', facets.countries);
            fillSelect('alt-f-state', facets.states);
            initYears(facets);

            // Restore saved filters, then default the PERIOD to the current
            // year whenever no period is actively selected — every page load
            // starts scoped to this year; "All time" is one click away.
            restoreFilters();
            restoreFiltersFromUrl();
            var noPeriod = !(readControl('alt-f-years') || []).length
                && !(readControl('alt-f-quarters') || []).length
                && !(readControl('alt-f-months') || []).length
                && !readControl('alt-f-from') && !readControl('alt-f-to');
            if (noPeriod && document.getElementById('alt-f-years')) {
                writeControl('alt-f-years', [String(new Date().getFullYear())]);
            }

            initMultiDropdowns();
            initRangeControl();
            initFilterPanel();        // eleven dropdowns behind one "Filters (n)" button
            initTracker();            // builds the server-side table (reads restored filters)
            initChrome();             // search / sort / quick views / expanders
            initTabs();               // region tabs + signal board (respects saved filters)
            initHeroActions();        // hero "Search the record" focus + anchors inside <details>
            renderRegionDefs();       // on-page region → country documentation
            updateWorkedExample();    // live H1 figure in the methodology example
            updateActiveFilterBar();
            updateDropdownSummaries();
            updateRangeLabel();
            updateExportLinks();
            fetchAndRenderAggregate(); // charts + stats
            loadReconciliation();      // announced-vs-executed links for row detail
            initClaimsOverlay();       // jobless-claims backdrop toggle (macro context)
        }).catch(function () {
            setStatus('alt-table-status', 'Could not load filters.', true);
            initMultiDropdowns();
            initRangeControl();
            initTracker();
            initChrome();
            fetchAndRenderAggregate();
        });
    });
})();
