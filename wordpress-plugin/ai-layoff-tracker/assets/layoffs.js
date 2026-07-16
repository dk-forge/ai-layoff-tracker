/**
 * AI Layoff Tracker — front-end (server-side).
 *
 * Everything is driven by three REST endpoints so the browser never loads the
 * whole dataset (it scales to 100K+ rows):
 *   query      paginated + filtered + sorted rows (DataTables server-side mode)
 *   aggregate  filtered totals, top-N, monthly series, reason breakdown, leaders
 *   facets     distinct industry/country/state + date range (dropdowns + period)
 *
 * Filters, the period selector, and chart clicks all set the same controls and
 * then re-fetch query + aggregate, so table, charts, and headline numbers move
 * together.
 */
(function ($) {
    'use strict';

    if (typeof window.altData === 'undefined') return;
    var API = window.altData.apiUrl; // ends with .../layoffs/v1/

    /* ------------------------------------------------------------------ */
    /* Palette + labels                                                    */
    /* ------------------------------------------------------------------ */

    var PALETTE = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834'];
    var SEQ_BLUE = '#2a78d6';
    var SEQ_BLUE_FILL = 'rgba(42, 120, 214, 0.18)';
    var INK = { primary: '#0b0b0b', secondary: '#52514e', muted: '#898781', grid: '#e1e0d9' };

    var REASON_LABELS = {
        ai_automation: 'AI / automation', possible_ai: 'Possible AI',
        revenue_decline: 'Revenue decline', restructuring: 'Restructuring',
        merger_acquisition: 'Merger / acquisition', offshoring: 'Offshoring',
        product_discontinuation: 'Product discontinued', cost_reduction: 'Cost reduction',
        macroeconomic: 'Macroeconomic'
    };
    var VERIF_LABELS = { gold: 'SEC filing', warn: 'WARN notice', silver: 'Press release', bronze: 'News' };
    var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // A WARN link is either the EXACT notice (states like VT publish per-notice
    // pages) or the state's official WARN list page (the notice is a row in
    // it). Label the difference honestly instead of implying precision.
    function warnLinkIsExact(row) {
        if (row.source_type !== 'warn') return true;
        var url = String(row.source_url || '');
        // Per-notice URLs carry a record id / document path; landing pages don't.
        return /\/\d+\/?$|\.pdf($|\?)|record|lookups\/\d/i.test(url);
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
    function safeUrl(url) {
        url = String(url == null ? '' : url).trim();
        return /^https?:\/\//i.test(url) ? url : '';
    }
    function setText(id, text) { var el = document.getElementById(id); if (el) el.textContent = text; }
    function setStatus(id, text, isError) {
        var el = document.getElementById(id);
        if (!el) return;
        if (text === null) { el.style.display = 'none'; return; }
        el.style.display = ''; el.textContent = text;
        el.classList.toggle('alt-status-error', !!isError);
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
    function apiGet(path, params) {
        var url = API + path;
        var q = qs(params);
        if (q) url += (url.indexOf('?') > -1 ? '&' : '?') + q;
        return fetch(url, { credentials: 'same-origin' }).then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        });
    }

    /* Chart registry --------------------------------------------------- */

    var CHARTS = {};
    function mountChart(canvasId, config) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return null;
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
            tooltip: { backgroundColor: '#0b0b0b', titleColor: '#fff', bodyColor: '#e1e0d9', padding: 10, displayColors: false }
        },
        scales: {
            x: { grid: { display: false }, ticks: { color: INK.muted, maxRotation: 0, autoSkip: true } },
            y: { beginAtZero: true, grid: { color: INK.grid }, ticks: { color: INK.muted, callback: function (v) { return fmt(v); } } }
        }
    };
    function cloneOptions() {
        var o = JSON.parse(JSON.stringify(baseChartOptions));
        o.scales.y.ticks.callback = function (v) { return fmt(v); };
        return o;
    }

    /* ------------------------------------------------------------------ */
    /* Filter controls                                                     */
    /* ------------------------------------------------------------------ */

    var FILTER_STORAGE_KEY = 'altTrackerFilters:v2';
    var FILTER_IDS = ['alt-search', 'alt-f-from', 'alt-f-to', 'alt-f-years', 'alt-f-quarters',
        'alt-f-months', 'alt-f-industry', 'alt-f-country', 'alt-f-state', 'alt-f-reasons',
        'alt-f-verification', 'alt-f-company', 'alt-f-keyword', 'alt-f-minjobs', 'alt-f-ai', 'alt-f-announced'];

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
            window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(s));
        } catch (e) { /* private mode */ }
    }
    function restoreFilters() {
        try {
            var raw = window.localStorage.getItem(FILTER_STORAGE_KEY);
            if (!raw) return;
            var s = JSON.parse(raw);
            FILTER_IDS.forEach(function (id) { writeControl(id, s[id]); });
        } catch (e) { /* corrupt */ }
    }
    function clearFilters() {
        FILTER_IDS.forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) return;
            if (el.type === 'checkbox') el.checked = false;
            else if (el.multiple) Array.prototype.forEach.call(el.options, function (o) { o.selected = false; });
            else el.value = '';
        });
        try { window.localStorage.removeItem(FILTER_STORAGE_KEY); } catch (e) { /* noop */ }
    }

    // Current filter state → REST query params. Multi-selects send comma lists.
    function multiParam(id) {
        var v = readControl(id);
        if (Array.isArray(v)) return v.length ? v.join(',') : '';
        return v || '';
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
        if ((v = multiParam('alt-f-reasons'))) p.reasons = v;
        if ((v = multiParam('alt-f-verification'))) p.sources = v;
        if ((v = (readControl('alt-search') || '').trim())) p.q = v;
        if ((v = (readControl('alt-f-company') || '').trim())) p.company = v;
        if ((v = (readControl('alt-f-keyword') || '').trim())) p.keyword = v;
        var mj = parseInt(readControl('alt-f-minjobs'), 10);
        if (!isNaN(mj) && mj > 0) p.min_jobs = mj;
        if (readControl('alt-f-ai')) p.ai = '1';
        if (readControl('alt-f-announced')) p.stage = 'announced';
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
        var toggled = false;
        Array.prototype.forEach.call(el.options, function (o) {
            if (o.value === value) { o.selected = !o.selected; toggled = true; }
        });
        return toggled;
    }

    var TABLE = null;
    var DASH_PRESENT = false;
    var LAST_AGG = null;

    function refreshAll() {
        saveFilters();
        if (TABLE) TABLE.ajax.reload(null, true);
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
        var qsStr = qs(currentParams());
        [['alt-export-csv', window.altData.exportCsv, 'CSV'],
         ['alt-export-json', window.altData.exportJson, 'JSON']].forEach(function (p) {
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
        apiGet('aggregate', currentParams())
            .then(function (agg) {
                if (seq !== AGG_SEQ) return;
                LAST_AGG = agg;
                renderStats(agg.totals);
                renderCharts(agg);
            })
            .catch(function () { if (seq === AGG_SEQ) setStatus('alt-dashboard-status', 'Could not load chart data.', true); });
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
        { id: 'alt-f-verification', label: 'Source', kind: 'multi', map: VERIF_LABELS, color: 'gold' },
        { id: 'alt-f-ai', label: '', kind: 'bool', on: 'AI-attributed only', color: 'red' },
        { id: 'alt-f-announced', label: '', kind: 'bool', on: 'Announced only', color: 'gold' }
    ];

    function updateActiveFilterBar() {
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
        if (clr) clr.addEventListener('click', function () { clearFilters(); refreshAll(); });
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

    // Next scheduled data pull. Ingest runs at fixed UTC times (13:00 and
    // 22:00 = 9 AM & 6 PM ET); show the next one so "updated" always has a
    // forward-looking companion.
    function nextPullET() {
        var now = new Date(), cands = [];
        for (var d = 0; d <= 1; d++) {
            [13, 22].forEach(function (h) {
                var t = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + d, h, 0, 0));
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
        if (nextEl) { var np = nextPullET(); nextEl.textContent = np ? ('Next update ' + np) : ''; }
        if (!liveEl || !workEl) return;
        var phase = stats && stats.pipeline_phase;
        if (phase === 'refreshing' || phase === 'cleaning') {
            // Green "Live" greys out; the amber working pill blinks alongside it.
            liveEl.classList.add('alt-status-dim');
            var txt = document.getElementById('alt-work-text');
            var wt = document.getElementById('alt-work-time');
            if (txt) txt.textContent = (phase === 'cleaning')
                ? 'AI is checking & de-duplicating the data'
                : 'Refreshing data — pulling new filings, notices & news';
            if (wt && stats.pipeline_since) wt.textContent = '· ' + fmtET(stats.pipeline_since);
            workEl.hidden = false;
        } else {
            liveEl.classList.remove('alt-status-dim');
            workEl.hidden = true;
        }
    }

    function initStatsMeta() {
        if (!document.getElementById('alt-live-time') && !document.getElementById('alt-last-updated')) return;
        // /status is public + uncached, so the badge flips to refreshing/
        // cleaning within one poll instead of waiting on the 5-min stats cache.
        var poll = function () { apiGet('status', { _: Date.now() }).then(renderStatus).catch(function () {}); };
        poll();
        setInterval(poll, 60000);
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
        if (bare && years[0] === String(new Date().getFullYear())) return years[0] + ' YTD';
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

    function statScopeLabel() {
        var parts = [];
        // A region tab's country set reads as its region name ("Europe"),
        // not as "France +7" — the raw form confused readers.
        var countries = selectedList('alt-f-country');
        if (countries.length) {
            parts.push(regionNameFor(countries) ||
                (countries[0] + (countries.length > 1 ? ' +' + (countries.length - 1) + ' more' : '')));
        }
        [['alt-f-state', 'US: '], ['alt-f-industry', null]].forEach(function (p) {
            var v = selectedList(p[0]);
            if (v.length) parts.push((p[1] || '') + v[0] + (v.length > 1 ? ' +' + (v.length - 1) + ' more' : ''));
        });
        return parts.length ? ' · ' + parts.join(' · ') : '';
    }

    function plural(n, word) { return fmt(n) + ' ' + word + (n === 1 ? '' : 's'); }

    function renderStats(t) {
        if (!document.getElementById('alt-stats-bar') || !t) return;
        var period = statPeriodLabel();
        var scope = statScopeLabel();
        var annJ = t.announced_jobs || 0, annE = t.announced_entries || 0;
        setText('alt-stat-total', fmt(t.jobs - annJ));
        setText('alt-stat-total-entries', plural(t.entries - annE, 'layoff') + ' · ' + period + scope);
        setText('alt-stat-announced', fmt(annJ));
        setText('alt-stat-announced-sub', plural(annE, 'announcement') + ' · ' + period + scope);
        setText('alt-stat-ai', fmt(t.ai_jobs));
        setText('alt-stat-ai-entries', plural(t.ai_entries, 'layoff') + ' · ' + period + scope);
        setText('alt-stat-companies', fmt(t.companies));
        setText('alt-stat-industries', fmt(t.industries));
        setText('alt-stat-countries', fmt(t.countries));
        var sub = document.getElementById('alt-stat-companies-sub');
        if (sub) sub.textContent = t.states > 0 ? fmt(t.states) + ' US states' : '';

        // The earliest and latest layoff dates actually present in this view.
        var note = document.getElementById('alt-range-note');
        if (note) {
            note.textContent = (t.entries && t.min_date)
                ? 'earliest ' + fmtDate(t.min_date) + ' · latest ' + fmtDate(t.max_date)
                : 'no layoffs match the current filters';
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

    /* Custom checkbox-dropdowns over the hidden native multi-selects. The
       native select stays the single source of truth (readControl/writeControl,
       persistence, chips, quick views all keep working); the dropdown is pure
       presentation and dispatches 'change' on the select when toggled. */
    function initMultiDropdowns() {
        document.querySelectorAll('.alt-filter[data-dd]').forEach(function (cell) {
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
        renderLeaderboard(agg.leaders);
        var wired = !!document.getElementById('alt-f-industry');
        renderBarList('alt-bars-industries', agg.top_industries, wired ? 'alt-f-industry' : null, selectedList('alt-f-industry'));
        renderBarList('alt-bars-states', agg.top_states, wired ? 'alt-f-state' : null, selectedList('alt-f-state'));
        renderBarList('alt-bars-countries', agg.top_countries, wired ? 'alt-f-country' : null, selectedList('alt-f-country'));
    }

    function selectedList(id) {
        var v = readControl(id);
        return Array.isArray(v) ? v : (v ? [v] : []);
    }

    // "Where the cuts are" bars: name left, value right, a track whose blue
    // fill is scaled to the top bar, with an orange leading segment showing the
    // AI-attributed share. Rows are buttons that toggle the matching filter.
    function renderBarList(containerId, entries, filterId, activeValues) {
        var box = document.getElementById(containerId);
        if (!box) return;
        // Compact cards show a top-4 preview; expanded (or full-size dashboard
        // cards) show up to 12.
        var mini = box.closest('.alt-mini');
        var compact = mini && !mini.classList.contains('alt-expanded');
        var fullCount = (entries || []).length;
        var limit = compact ? 4 : 12;
        entries = (entries || []).slice(0, limit);
        if (!entries.length) {
            box.innerHTML = '<p class="alt-muted alt-empty">No data for the current filters.</p>';
            return;
        }
        var active = activeValues || [];
        var max = entries[0][1] || 1;
        entries.forEach(function (e) { if (e[1] > max) max = e[1]; });

        var html = '';
        entries.forEach(function (e) {
            var label = e[0], jobs = e[1], ai = e[2] || 0;
            var w = Math.max(2, Math.round(jobs / max * 100));
            var aiW = jobs > 0 ? (ai / jobs * w) : 0;
            var isActive = active.indexOf(label) !== -1;
            var dim = active.length && !isActive;
            html += '<button type="button" class="alt-barrow' + (isActive ? ' alt-barrow-on' : '') + (dim ? ' alt-barrow-dim' : '') + '"'
                + (filterId ? '' : ' disabled')
                + ' data-val="' + escapeHtml(label) + '" aria-pressed="' + (isActive ? 'true' : 'false') + '">'
                + '<span class="alt-barrow-top"><span class="alt-barrow-name">' + escapeHtml(label) + '</span>'
                + '<span class="alt-barrow-val">' + fmt(jobs) + '</span></span>'
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

        if (filterId) {
            box.querySelectorAll('.alt-barrow').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    // Multi-select: each click adds/removes that value, so bars
                    // compose (e.g. CA + WA + Technology).
                    toggleMultiFilter(filterId, btn.getAttribute('data-val'));
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

    function fillMonths(series) {
        if (!series || !series.length) return [];
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

        // Cap the ZERO-FILL at the current month, but never below real data:
        // WARN filings carry future effective dates that must stay visible.
        var now = new Date();
        var nowKey = now.getFullYear() + '-' + pad2(now.getMonth() + 1);
        var lastData = series[series.length - 1].month;
        var cap = lastData > nowKey ? lastData : nowKey;
        if (end > cap) end = cap;
        if (end < start) return series;

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

    function renderTrend(series) {
        if (!document.getElementById('alt-chart-weekly')) return;
        series = fillMonths(series);
        var range = document.getElementById('alt-trend-range');
        if (range) range.textContent = series.length
            ? monthLabel(series[0].month) + ' – ' + monthLabel(series[series.length - 1].month) : '';
        if (!series || !series.length) { clearChart('alt-chart-weekly'); return; }
        var options = cloneOptions();
        options.plugins.tooltip.callbacks = { label: function (ctx) { return 'Jobs cut: ' + fmt(ctx.parsed.y); } };
        mountChart('alt-chart-weekly', {
            type: 'line',
            data: {
                labels: series.map(function (s) { return monthLabel(s.month); }),
                datasets: [{ data: series.map(function (s) { return s.jobs; }), borderColor: SEQ_BLUE, backgroundColor: SEQ_BLUE_FILL, borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: true, tension: 0.3 }]
            },
            options: options
        });
    }

    function renderAiCumulative(series) {
        if (!document.getElementById('alt-chart-ai-cumulative')) return;
        series = fillMonths(series);
        var ai = (series || []).filter(function (s) { return s.ai_jobs > 0; });
        var range = document.getElementById('alt-cum-range');
        if (range) range.textContent = ai.length
            ? 'since ' + monthLabel(ai[0].month) : '';
        if (!ai.length) { clearChart('alt-chart-ai-cumulative'); return; }
        var running = 0;
        var cum = (series || []).map(function (s) { running += s.ai_jobs; return { month: s.month, v: running }; })
            .filter(function (x) { return x.v > 0; });
        var options = cloneOptions();
        options.plugins.tooltip.callbacks = { label: function (ctx) { return 'Cumulative AI-attributed: ' + fmt(ctx.parsed.y); } };
        mountChart('alt-chart-ai-cumulative', {
            type: 'line',
            data: {
                labels: cum.map(function (x) { return monthLabel(x.month); }),
                datasets: [{ data: cum.map(function (x) { return x.v; }), borderColor: PALETTE[5], backgroundColor: 'rgba(227, 73, 72, 0.15)', borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: true, tension: 0.25 }]
            },
            options: options
        });
    }

    function renderBar(canvasId, entries, filterId, activeValue, tipPrefix) {
        if (!document.getElementById(canvasId)) return;
        entries = entries || [];
        if (!entries.length) { clearChart(canvasId); return; }
        var colors = paletteFor(entries).map(function (base, i) {
            return (activeValue && entries[i][0] !== activeValue) ? '#d6d8de' : base;
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

    function renderReasons(entries, filterId, activeValues) {
        if (!document.getElementById('alt-chart-reasons')) return;
        entries = entries || [];
        if (!entries.length) { clearChart('alt-chart-reasons'); return; }
        var active = activeValues || [];
        var colors = entries.map(function (e, i) {
            var base = PALETTE[i % PALETTE.length];
            return (active.length && active.indexOf(e[0]) === -1) ? '#d6d8de' : base;
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
                datasets: [{ data: entries.map(function (e) { return e[1]; }), backgroundColor: colors, borderColor: '#fcfcfb', borderWidth: 2 }]
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
    /* Tracker table (server-side)                                         */
    /* ------------------------------------------------------------------ */

    function verificationBadge(level) {
        var safe = escapeHtml(level || 'bronze');
        return '<span class="alt-badge alt-badge-' + safe + '">' + escapeHtml(VERIF_LABELS[level] || 'News') + '</span>';
    }

    function initTracker() {
        var tableEl = document.getElementById('alt-table');
        if (!tableEl) return;
        if (typeof $.fn.DataTable === 'undefined') {
            setStatus('alt-table-status', 'The table library failed to load (CDN blocked?). Raw data: ' + API + 'query', true);
            return;
        }

        // column index -> server sort field (null = not sortable)
        var sortFields = ['layoff_date', 'company', 'job_count', 'industry', 'country', null, 'verification_level', null, null];

        var table = $(tableEl).DataTable({
            serverSide: true,
            processing: true,
            searching: false,
            order: [[0, 'desc']],
            pageLength: 25,
            lengthMenu: [10, 25, 50, 100],
            dom: 'lrtip',
            language: {
                processing: 'Loading…',
                emptyTable: 'No layoff entries match the current filters.',
                zeroRecords: 'No layoff entries match the current filters.'
            },
            ajax: function (dtData, callback) {
                var p = currentParams();
                p.per_page = dtData.length;
                p.page = Math.floor(dtData.start / dtData.length) + 1;
                var ord = dtData.order && dtData.order[0];
                if (ord && sortFields[ord.column]) { p.sort = sortFields[ord.column]; p.dir = ord.dir; }
                apiGet('query', p).then(function (res) {
                    callback({ draw: dtData.draw, recordsTotal: res.total, recordsFiltered: res.total, data: res.data });
                }).catch(function () {
                    setStatus('alt-table-status', 'Could not load layoff data.', true);
                    callback({ draw: dtData.draw, recordsTotal: 0, recordsFiltered: 0, data: [] });
                });
            },
            drawCallback: function () {
                var el = document.getElementById('alt-table-count');
                if (!el) return;
                var info = this.api().page.info();
                el.classList.toggle('alt-count-empty', !info.recordsDisplay);
                if (!info.recordsDisplay) { el.textContent = 'No layoffs match the current filters.'; return; }
                el.textContent = 'Showing ' + fmt(info.start + 1) + '–' + fmt(info.end) + ' of ' + fmt(info.recordsDisplay) + ' layoffs';
            },
            columns: [
                { data: 'layoff_date', render: function (d, t, row) {
                    if (t !== 'display') return d || '';
                    if (!d) return '<span class="alt-muted">unknown</span>';
                    // WARN filings are legally filed 60+ days ahead — flag cuts
                    // whose effective date hasn't arrived yet as planned, not
                    // done. Local calendar date, not UTC, so the tag doesn't
                    // flip early/late around midnight.
                    var n = new Date();
                    var today = n.getFullYear() + '-' + pad2(n.getMonth() + 1) + '-' + pad2(n.getDate());
                    var badges = (d > today ? ' <span class="alt-upcoming" title="Filed in advance. The effective date has not arrived yet.">upcoming</span>' : '');
                    if (row.announced) badges += ' <span class="alt-upcoming" title="Announcement of planned cuts, not yet executed or filed">announced</span>';
                    return escapeHtml(d) + badges;
                } },
                { data: 'company_name', render: function (d, t, row) {
                    if (t !== 'display') return d || '';
                    var h = '<strong>' + escapeHtml(d) + '</strong>';
                    if (row.ticker) h += ' <span class="alt-ticker">' + escapeHtml(row.ticker) + '</span>';
                    return h;
                } },
                { data: 'job_count', className: 'alt-num', render: function (d, t) { return t === 'display' ? fmt(d) : d; } },
                { data: 'industry', render: function (d, t) { return t === 'display' ? escapeHtml(d || '—') : (d || ''); } },
                { data: 'country', render: function (d, t, row) {
                    if (t !== 'display') return (d || '') + ' ' + (row.state || '');
                    var c = escapeHtml(d || '—');
                    if (row.state) c += ' <span class="alt-state">' + escapeHtml(row.state) + '</span>';
                    return c;
                } },
                { data: 'reason_tags', orderable: false, render: function (d, t) {
                    var tags = Array.isArray(d) ? d : [];
                    if (t !== 'display') return tags.join(' ');
                    return tags.map(function (x) { return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[x] || x) + '</span>'; }).join(' ');
                } },
                { data: 'verification_level', render: function (d, t) { return t === 'display' ? verificationBadge(d) : (d || ''); } },
                { data: 'ai_explicit', className: 'alt-center', render: function (d, t) {
                    if (t === 'display') return d ? '<span class="alt-ai-yes" title="Explicitly AI-attributed">AI</span>' : '';
                    return d ? 1 : 0;
                } },
                { data: 'source_url', orderable: false, render: function (d, t, row) {
                    if (t !== 'display') return row.source_name || '';
                    var url = safeUrl(d);
                    if (!url) return escapeHtml(row.source_name || '—');
                    var exact = warnLinkIsExact(row);
                    var title = exact ? 'Opens the primary source'
                        : 'Opens the state’s official WARN list. This notice is a row in it.';
                    var suffix = exact ? '' : ' <span class="alt-muted" title="' + title + '">(list)</span>';
                    return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow" title="' + escapeHtml(title) + '">' + escapeHtml(row.source_name || 'source') + '</a>' + suffix;
                } }
            ]
        });
        TABLE = table;
        setStatus('alt-table-status', null);

        var redraw = null;
        function onFilterChange() { clearTimeout(redraw); redraw = setTimeout(refreshAll, 250); }
        FILTER_IDS.forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', onFilterChange);
            if (el.type === 'text' || el.type === 'number') el.addEventListener('input', onFilterChange);
        });
        var reset = document.getElementById('alt-f-reset');
        if (reset) reset.addEventListener('click', function () { clearFilters(); refreshAll(); });

        // expand a row for the exact quote + source
        $(tableEl).on('click', 'tbody tr', function (e) {
            if (e.target && e.target.closest && e.target.closest('a')) return;
            var row = table.row(this);
            if (!row.data()) return;
            if (row.child.isShown()) { row.child.hide(); $(this).removeClass('alt-row-open'); }
            else { row.child(formatDetail(row.data())).show(); $(this).addClass('alt-row-open'); }
        });
    }

    function formatDetail(row) {
        var parts = [];
        if (row.ai_language) parts.push('<div class="alt-detail-block alt-detail-quote"><span class="alt-detail-h">Exact AI / automation quote</span><blockquote>“' + escapeHtml(row.ai_language) + '”</blockquote></div>');
        if (row.excerpt) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">From the source</span><p>' + escapeHtml(row.excerpt) + '</p></div>');
        if (row.roles) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Roles affected</span><p>' + escapeHtml(row.roles) + '</p></div>');
        var tags = (row.reason_tags || []).map(function (t) { return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[t] || t) + '</span>'; }).join(' ');
        if (tags) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Reasons cited</span><div>' + tags + '</div></div>');
        var url = safeUrl(row.source_url);
        var verif = row.verification_level ? ' · <span class="alt-badge alt-badge-' + escapeHtml(row.verification_level) + '">' + escapeHtml(VERIF_LABELS[row.verification_level] || 'News') + '</span>' : '';
        var linkText = warnLinkIsExact(row)
            ? 'View primary source (' + (row.source_name || 'source') + ') ↗'
            : 'View the state’s official WARN list (this notice is a row in it) ↗';
        var src = url ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">' + escapeHtml(linkText) + '</a>' : escapeHtml(row.source_name || '—');
        parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Source</span><div>' + src + verif + '</div></div>');
        return '<div class="alt-detail">' + (parts.join('') || 'No additional detail recorded.') + '</div>';
    }

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
            setText('alt-ai-hero-sub', 'across ' + fmt(aiRows.length) + ' events at ' + fmt(list.length) + ' companies');
            if (!aiRows.length) { setStatus('alt-ai-status', 'No explicitly AI-attributed layoffs recorded yet.'); return; }
            setStatus('alt-ai-status', chartsAvailable() ? null : 'Chart library failed to load (CDN blocked?). Charts unavailable.', !chartsAvailable());

            if (chartsAvailable()) {
                var byMonth = {};
                aiRows.forEach(function (r) { if (/^\d{4}-\d{2}-\d{2}$/.test(r.layoff_date)) { var m = r.layoff_date.slice(0, 7); byMonth[m] = (byMonth[m] || 0) + r.job_count; } });
                var keys = Object.keys(byMonth).sort();
                if (keys.length && document.getElementById('alt-chart-ai-monthly')) {
                    var options = cloneOptions();
                    options.plugins.tooltip.callbacks = { label: function (ctx) { return 'AI-attributed jobs: ' + fmt(ctx.parsed.y); } };
                    mountChart('alt-chart-ai-monthly', {
                        type: 'line',
                        data: { labels: keys.map(monthLabel), datasets: [{ data: keys.map(function (k) { return byMonth[k]; }), borderColor: SEQ_BLUE, backgroundColor: SEQ_BLUE_FILL, borderWidth: 2, pointRadius: 3, pointBackgroundColor: SEQ_BLUE, fill: true, tension: 0.25 }] },
                        options: options
                    });
                }
                var byInd = {};
                aiRows.forEach(function (r) { if (r.industry) byInd[r.industry] = (byInd[r.industry] || 0) + 1; });
                var indEntries = Object.keys(byInd).map(function (k) { return [k, byInd[k]]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 10);
                renderBar('alt-chart-ai-industries', indEntries, null, null, 'Events: ');
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
            if (!matches.length) { if (summary) summary.textContent = 'No recorded layoff events for this company yet.'; return; }
            var totalJobs = matches.reduce(function (s, r) { return s + r.job_count; }, 0);
            if (summary) summary.textContent = fmt(matches.length) + ' recorded events · ' + fmt(totalJobs) + ' total jobs cut';
            if (document.getElementById('alt-chart-company') && chartsAvailable()) {
                var options = cloneOptions();
                options.plugins.tooltip.callbacks = { label: function (ctx) { return 'Jobs: ' + fmt(ctx.parsed.y); } };
                mountChart('alt-chart-company', {
                    type: 'bar',
                    data: { labels: matches.map(function (r) { return r.layoff_date || 'unknown'; }), datasets: [{ data: matches.map(function (r) { return r.job_count; }), backgroundColor: matches.map(function (r) { return r.ai_explicit ? PALETTE[5] : SEQ_BLUE; }), borderRadius: 4, maxBarThickness: 40 }] },
                    options: options
                });
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

    // "Today July 15: so far in 2026, N layoffs with J people impacted..."
    function updateNarrative() {
        var el = document.getElementById('alt-narrative');
        if (!el) return;
        var tab = REGION_TABS[ACTIVE_TAB] || REGION_TABS.world;
        var now = new Date();
        var y = now.getFullYear();
        var base = tab.countries.length ? { country: tab.countries.join(',') } : {};
        var pThis = Object.assign({ years: String(y) }, base);
        var pPrev = Object.assign({ years: String(y - 1) }, base);
        Promise.all([apiGet('aggregate', pThis), apiGet('aggregate', pPrev)]).then(function (r) {
            var t = r[0].totals, p = r[1].totals;
            var today = MONTHS[now.getMonth()] + ' ' + now.getDate();
            var perDay = p.jobs ? Math.round(p.jobs / 365) : 0;
            var b = function (v) { return '<b>' + v + '</b>'; }; // every value is our own fmt()/config output
            // Plain human language: "layoff events affecting N workers", not
            // "layoffs with N people impacted" (readers mistook event counts
            // for people counts).
            var txt = 'Today, ' + b(today) + ': so far in ' + b(y) + ' we’ve verified ' + b(fmt(t.entries)) +
                ' layoff event' + (t.entries === 1 ? '' : 's') + ' ' + tab.label + ' affecting ' + b(fmt(t.jobs)) + ' workers';
            if (t.ai_jobs) txt += '. Companies explicitly blamed AI for ' + b(fmt(t.ai_jobs)) + ' of those job cuts';
            txt += '. In ' + b(y - 1) + ', ' + b(fmt(p.entries)) + ' verified event' + (p.entries === 1 ? '' : 's') +
                ' affected ' + b(fmt(p.jobs)) + ' workers' +
                (perDay ? ', an average of ' + b(fmt(perDay)) + ' people losing their jobs every day' : '') + '.';
            if (!t.entries && !p.entries && ACTIVE_TAB !== 'world') {
                txt += ' Coverage for this region is still filling in from the worldwide press index. Pick "All time" in the Years filter to see earlier verified events.';
            }
            el.innerHTML = txt;
        }).catch(function () { el.textContent = ''; });
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
        html += '<p><b>World</b> is the unfiltered total. It includes every entry, even ones whose country has no regional tab, plus the honest "Multiple countries" bucket for cuts that span several countries and which no single region can claim without double counting.</p>';
        el.innerHTML = html;
    }

    // The methodology's worked example quotes our own H1 figure — keep it
    // live from the API so it can never drift stale again (it had drifted
    // 83% behind after the nationwide WARN backfill; super test 2026-07-15).
    function updateWorkedExample() {
        var el = document.getElementById('alt-worked-ours');
        if (!el) return;
        apiGet('aggregate', { years: '2026', country: 'United States', stage: 'verified' }).then(function (r) {
            var h1 = 0;
            (r.series || []).forEach(function (m) {
                if (m.month >= '2026-01' && m.month <= '2026-06') h1 += m.jobs;
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

    var SORT_MAP = { newest: [0, 'desc'], oldest: [0, 'asc'], largest: [2, 'desc'], smallest: [2, 'asc'] };
    function setSort(val) {
        var sel = document.getElementById('alt-sort');
        if (sel && sel.value !== val) sel.value = val;
        if (TABLE && SORT_MAP[val]) TABLE.order(SORT_MAP[val]);
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

    function updateQuickViewStates() {
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

        // Per-chart downloads: canvas charts save as PNG (white background);
        // HTML bar lists save their current data as a small CSV.
        var BAR_AGG_KEY = {
            'alt-bars-industries': ['top_industries', 'by-industry'],
            'alt-bars-states': ['top_states', 'by-us-state'],
            'alt-bars-countries': ['top_countries', 'by-country']
        };
        Array.prototype.forEach.call(document.querySelectorAll('.alt-chart-dl'), function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                var t = btn.getAttribute('data-dl');
                var kind = btn.getAttribute('data-kind');
                if (kind === 'png') {
                    var ch = CHARTS[t];
                    if (!ch) return;
                    var src = ch.canvas;
                    var c = document.createElement('canvas');
                    c.width = src.width; c.height = src.height;
                    var ctx = c.getContext('2d');
                    ctx.fillStyle = '#ffffff';
                    ctx.fillRect(0, 0, c.width, c.height);
                    ctx.drawImage(src, 0, 0);
                    var a = document.createElement('a');
                    a.href = c.toDataURL('image/png');
                    a.download = 'ai-layoff-tracker-' + t.replace('alt-chart-', '') + '.png';
                    a.click();
                } else {
                    var meta = BAR_AGG_KEY[t];
                    var rows = (meta && LAST_AGG && LAST_AGG[meta[0]]) || [];
                    if (!rows.length) return;
                    var csv = 'label,jobs,ai_attributed_jobs\n' + rows.map(function (r) {
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

    $(function () {
        var citeDate = document.getElementById('alt-cite-date');
        if (citeDate) citeDate.textContent = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        var citeCopy = document.getElementById('alt-cite-copy');
        if (citeCopy) citeCopy.addEventListener('click', function () {
            var el = document.getElementById('alt-cite-text');
            if (el && navigator.clipboard) { navigator.clipboard.writeText(el.textContent.replace(/\s+/g, ' ').trim()); citeCopy.textContent = 'Copied ✓'; setTimeout(function () { citeCopy.textContent = 'Copy'; }, 1500); }
        });

        initStatsMeta();

        var needsData = document.getElementById('alt-table') || document.getElementById('alt-stats-bar')
            || document.querySelector('.alt-dashboard') || document.querySelector('.alt-ai-tracker')
            || document.querySelector('.alt-company-history');
        if (!needsData) return;

        if (chartsAvailable()) {
            Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
            Chart.defaults.color = INK.muted;
        }
        DASH_PRESENT = !!document.querySelector('.alt-dashboard');

        // Standalone AI / company pages don't use the shared filter surface.
        initAiTracker();
        initCompanyHistory();

        var hasFilterSurface = document.getElementById('alt-table') || document.getElementById('alt-stats-bar') || DASH_PRESENT;
        if (!hasFilterSurface) return;

        apiGet('facets', {}).then(function (facets) {
            fillSelect('alt-f-industry', facets.industries);
            fillSelect('alt-f-country', facets.countries);
            fillSelect('alt-f-state', facets.states);
            initYears(facets);

            // Restore saved filters, then default the PERIOD to the current
            // year whenever no period is actively selected — every page load
            // starts scoped to this year; "All time" is one click away.
            restoreFilters();
            var noPeriod = !(readControl('alt-f-years') || []).length
                && !(readControl('alt-f-quarters') || []).length
                && !(readControl('alt-f-months') || []).length
                && !readControl('alt-f-from') && !readControl('alt-f-to');
            if (noPeriod && document.getElementById('alt-f-years')) {
                writeControl('alt-f-years', [String(new Date().getFullYear())]);
            }

            initMultiDropdowns();
            initRangeControl();
            initTracker();            // builds the server-side table (reads restored filters)
            initChrome();             // search / sort / quick views / expanders
            initTabs();               // region tabs + narrative (respects saved filters)
            renderRegionDefs();       // on-page region → country documentation
            updateWorkedExample();    // live H1 figure in the methodology example
            updateActiveFilterBar();
            updateDropdownSummaries();
            updateRangeLabel();
            updateExportLinks();
            fetchAndRenderAggregate(); // charts + stats
        }).catch(function () {
            setStatus('alt-table-status', 'Could not load filters.', true);
            initMultiDropdowns();
            initRangeControl();
            initTracker();
            initChrome();
            fetchAndRenderAggregate();
        });
    });
})(jQuery);
