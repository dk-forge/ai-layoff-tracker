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
    var FILTER_IDS = ['alt-f-from', 'alt-f-to', 'alt-f-industry', 'alt-f-country',
        'alt-f-state', 'alt-f-reasons', 'alt-f-verification', 'alt-f-company',
        'alt-f-keyword', 'alt-f-minjobs', 'alt-f-ai'];

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

    // Current filter state → REST query params.
    function currentParams() {
        var p = {};
        var v;
        if ((v = readControl('alt-f-from'))) p.from = v;
        if ((v = readControl('alt-f-to'))) p.to = v;
        if ((v = readControl('alt-f-industry'))) p.industry = v;
        if ((v = readControl('alt-f-country'))) p.country = v;
        if ((v = readControl('alt-f-state'))) p.state = v;
        var reasons = readControl('alt-f-reasons') || [];
        if (reasons.length) p.reasons = reasons.join(',');
        var sources = readControl('alt-f-verification') || [];
        if (sources.length) p.sources = sources.join(',');
        if ((v = (readControl('alt-f-company') || '').trim())) p.company = v;
        if ((v = (readControl('alt-f-keyword') || '').trim())) p.keyword = v;
        var mj = parseInt(readControl('alt-f-minjobs'), 10);
        if (!isNaN(mj) && mj > 0) p.min_jobs = mj;
        if (readControl('alt-f-ai')) p.ai = '1';
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

    function refreshAll() {
        saveFilters();
        if (TABLE) TABLE.ajax.reload(null, true);
        fetchAndRenderAggregate();
        updateActiveFilterBar();
    }

    function fetchAndRenderAggregate() {
        if (!document.getElementById('alt-stats-bar') && !DASH_PRESENT) return;
        apiGet('aggregate', currentParams())
            .then(function (agg) { renderStats(agg.totals); renderCharts(agg); })
            .catch(function () { setStatus('alt-dashboard-status', 'Could not load chart data.', true); });
    }

    /* Active-filter chip bar ------------------------------------------- */

    var ACTIVE_FILTER_DEFS = [
        { id: 'alt-f-industry', label: 'Industry', kind: 'single' },
        { id: 'alt-f-country', label: 'Country', kind: 'single' },
        { id: 'alt-f-state', label: 'State', kind: 'single' },
        { id: 'alt-f-reasons', label: 'Reason', kind: 'multi', map: REASON_LABELS },
        { id: 'alt-f-verification', label: 'Source', kind: 'multi', map: VERIF_LABELS },
        { id: 'alt-f-ai', label: '', kind: 'bool', on: 'AI-attributed only' }
    ];

    function updateActiveFilterBar() {
        var bar = document.getElementById('alt-active-filters');
        if (!bar) return;
        var chips = [];
        ACTIVE_FILTER_DEFS.forEach(function (def) {
            var val = readControl(def.id);
            if (def.kind === 'bool') { if (val) chips.push({ id: def.id, text: def.on, value: true, kind: 'bool' }); }
            else if (def.kind === 'multi') {
                (val || []).forEach(function (v) {
                    chips.push({ id: def.id, text: def.label + ': ' + ((def.map && def.map[v]) || v), value: v, kind: 'multi' });
                });
            } else if (val) { chips.push({ id: def.id, text: def.label + ': ' + val, value: val, kind: 'single' }); }
        });
        if (!chips.length) { bar.innerHTML = ''; bar.style.display = 'none'; return; }
        bar.style.display = '';
        var html = '<span class="alt-af-label">Filtering:</span>';
        chips.forEach(function (c, i) {
            html += '<button type="button" class="alt-af-chip" data-i="' + i + '">' + escapeHtml(c.text) + ' <span aria-hidden="true">✕</span></button>';
        });
        html += '<button type="button" class="alt-af-clear" id="alt-af-clear">Clear all</button>';
        bar.innerHTML = html;
        bar.querySelectorAll('.alt-af-chip').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var c = chips[parseInt(btn.getAttribute('data-i'), 10)];
                if (c.kind === 'bool') { var el = document.getElementById(c.id); if (el) el.checked = false; }
                else if (c.kind === 'multi') toggleMultiFilter(c.id, c.value);
                else toggleSingleFilter(c.id, '');
                refreshAll();
            });
        });
        var clr = document.getElementById('alt-af-clear');
        if (clr) clr.addEventListener('click', function () { clearFilters(); PERIOD_YEAR = ''; updatePeriodActiveState(); refreshAll(); });
    }

    /* ------------------------------------------------------------------ */
    /* Stats bar                                                           */
    /* ------------------------------------------------------------------ */

    function initStatsMeta() {
        if (!document.getElementById('alt-last-updated')) return;
        apiGet('stats', {}).then(function (stats) {
            if (!stats || !stats.last_updated) return;
            var lu = new Date(stats.last_updated);
            if (isNaN(lu.getTime())) return;
            setText('alt-last-updated', 'Updated ' + lu.toLocaleString('en-US', {
                timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric',
                hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
            }));
        }).catch(function () { /* leave blank */ });
    }

    function renderStats(t) {
        if (!document.getElementById('alt-stats-bar') || !t) return;
        setText('alt-stat-total', fmt(t.jobs));
        setText('alt-stat-total-entries', fmt(t.entries) + ' events · ' + currentPeriodLabel());
        setText('alt-stat-ai', fmt(t.ai_jobs));
        setText('alt-stat-ai-entries', fmt(t.ai_entries) + ' events');
        setText('alt-stat-companies', fmt(t.companies));
        setText('alt-stat-industries', fmt(t.industries));
        setText('alt-stat-countries', fmt(t.countries));
        var sub = document.getElementById('alt-stat-companies-sub');
        if (sub) sub.textContent = fmt(t.states) + ' US states';
    }

    /* ------------------------------------------------------------------ */
    /* Period selector                                                     */
    /* ------------------------------------------------------------------ */

    var PERIOD_YEAR = '';
    function daysInMonth(y, m) { return new Date(y, m, 0).getDate(); }
    function pad2(n) { return (n < 10 ? '0' : '') + n; }

    function currentPeriodLabel() {
        var from = readControl('alt-f-from'); var to = readControl('alt-f-to');
        if (!from && !to) return 'all time';
        var q = readControl('alt-period-quarter'); var mo = readControl('alt-period-month');
        if (PERIOD_YEAR && mo) return MONTHS[parseInt(mo, 10) - 1] + ' ' + PERIOD_YEAR;
        if (PERIOD_YEAR && q) return 'Q' + q + ' ' + PERIOD_YEAR;
        if (PERIOD_YEAR && from === PERIOD_YEAR + '-01-01') return PERIOD_YEAR;
        return (from || '…') + ' to ' + (to || 'now');
    }

    function applyPeriod() {
        var year = PERIOD_YEAR;
        var q = readControl('alt-period-quarter'); var mo = readControl('alt-period-month');
        var qEl = document.getElementById('alt-period-quarter'); if (qEl) qEl.disabled = !year;
        var mEl = document.getElementById('alt-period-month'); if (mEl) mEl.disabled = !year;
        var from = '', to = '';
        if (year) {
            var y = parseInt(year, 10);
            if (mo) { var m = parseInt(mo, 10); from = year + '-' + pad2(m) + '-01'; to = year + '-' + pad2(m) + '-' + pad2(daysInMonth(y, m)); }
            else if (q) { var qn = parseInt(q, 10); var sm = (qn - 1) * 3 + 1, em = sm + 2; from = year + '-' + pad2(sm) + '-01'; to = year + '-' + pad2(em) + '-' + pad2(daysInMonth(y, em)); }
            else { from = year + '-01-01'; to = year + '-12-31'; }
        }
        writeControl('alt-f-from', from); writeControl('alt-f-to', to);
        refreshAll();
    }

    function updatePeriodActiveState() {
        var host = document.getElementById('alt-period-years');
        if (!host) return;
        Array.prototype.forEach.call(host.querySelectorAll('.alt-period-btn'), function (b) {
            b.classList.toggle('alt-period-on', b.getAttribute('data-year') === PERIOD_YEAR);
        });
    }

    function initPeriodSelector(facets) {
        var wrap = document.getElementById('alt-period');
        var host = document.getElementById('alt-period-years');
        if (!wrap || !host || !document.getElementById('alt-f-from')) return;
        wrap.style.display = '';

        var minY = facets.min_date ? parseInt(facets.min_date.slice(0, 4), 10) : 2019;
        var maxY = facets.max_date ? parseInt(facets.max_date.slice(0, 4), 10) : (new Date()).getUTCFullYear();
        var years = [];
        for (var y = maxY; y >= minY; y--) years.push(String(y));

        var from = readControl('alt-f-from');
        PERIOD_YEAR = (from && /^\d{4}/.test(from) && years.indexOf(from.slice(0, 4)) !== -1) ? from.slice(0, 4) : '';

        var html = '<button type="button" class="alt-period-btn" data-year="">All time</button>';
        years.forEach(function (yr) { html += '<button type="button" class="alt-period-btn" data-year="' + yr + '">' + yr + '</button>'; });
        host.innerHTML = html;
        Array.prototype.forEach.call(host.querySelectorAll('.alt-period-btn'), function (btn) {
            btn.addEventListener('click', function () {
                PERIOD_YEAR = btn.getAttribute('data-year');
                if (!PERIOD_YEAR) { writeControl('alt-period-quarter', ''); writeControl('alt-period-month', ''); }
                applyPeriod(); updatePeriodActiveState();
            });
        });
        var qSel = document.getElementById('alt-period-quarter');
        var mSel = document.getElementById('alt-period-month');
        if (qSel) { qSel.addEventListener('change', function () { writeControl('alt-period-month', ''); applyPeriod(); }); qSel.disabled = !PERIOD_YEAR; }
        if (mSel) { mSel.addEventListener('change', function () { writeControl('alt-period-quarter', ''); applyPeriod(); }); mSel.disabled = !PERIOD_YEAR; }
        updatePeriodActiveState();
    }

    /* ------------------------------------------------------------------ */
    /* Charts (from /aggregate)                                            */
    /* ------------------------------------------------------------------ */

    function renderCharts(agg) {
        if (!DASH_PRESENT || !chartsAvailable()) return;
        setStatus('alt-dashboard-status', agg.totals.entries ? null : 'No entries match the current filters.');
        renderTrend(agg.series);
        renderAiCumulative(agg.series);
        renderLeaderboard(agg.leaders);
        var wired = !!document.getElementById('alt-f-industry');
        renderBar('alt-chart-industries', agg.top_industries, wired ? 'alt-f-industry' : null, readControl('alt-f-industry'), 'Jobs: ');
        renderBar('alt-chart-states', agg.top_states, wired ? 'alt-f-state' : null, readControl('alt-f-state'), 'Jobs: ');
        renderBar('alt-chart-countries', agg.top_countries, wired ? 'alt-f-country' : null, readControl('alt-f-country'), 'Jobs: ');
        renderReasons(agg.reasons, wired ? 'alt-f-reasons' : null, readControl('alt-f-reasons'));
    }

    function renderTrend(series) {
        if (!document.getElementById('alt-chart-weekly')) return;
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
        var ai = (series || []).filter(function (s) { return s.ai_jobs > 0; });
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
                legend: { position: 'right', labels: { color: INK.secondary, boxWidth: 12, boxHeight: 12 } },
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
                if (!info.recordsDisplay) { el.textContent = 'No entries match the current filters.'; return; }
                el.textContent = 'Showing ' + fmt(info.start + 1) + '–' + fmt(info.end) + ' of ' + fmt(info.recordsDisplay) + ' entries';
            },
            columns: [
                { data: 'layoff_date', render: function (d, t) { return t === 'display' ? (d ? escapeHtml(d) : '<span class="alt-muted">unknown</span>') : (d || ''); } },
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
                    return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">' + escapeHtml(row.source_name || 'source') + '</a>';
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
        if (reset) reset.addEventListener('click', function () { clearFilters(); PERIOD_YEAR = ''; updatePeriodActiveState(); refreshAll(); });

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
        var src = url ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">View primary source (' + escapeHtml(row.source_name || 'source') + ') ↗</a>' : escapeHtml(row.source_name || '—');
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
            restoreFilters();
            initPeriodSelector(facets);
            initTracker();            // builds the server-side table (reads restored filters)
            updateActiveFilterBar();
            fetchAndRenderAggregate(); // charts + stats
        }).catch(function () {
            setStatus('alt-table-status', 'Could not load filters.', true);
            initTracker();
            fetchAndRenderAggregate();
        });
    });
})(jQuery);
