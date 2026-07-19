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

    // Okabe-Ito colorblind-safe palette, ordered so neighbors differ in
    // lightness as well as hue (yellow excluded: too weak on white for lines).
    var PALETTE = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9', '#000000', '#999999'];
    var ALT_RED = '#D55E00', ALT_AMBER = '#E69F00';
    var SEQ_BLUE = '#2a78d6';
    var SEQ_BLUE_FILL = 'rgba(42, 120, 214, 0.18)';
    var INK = { primary: '#0b0b0b', secondary: '#52514e', muted: '#898781', grid: '#e1e0d9' };

    var REASON_LABELS = {
        ai_automation: 'AI: company-stated (specific)', possible_ai: 'AI-linked (broad)',
        revenue_decline: 'Revenue decline', restructuring: 'Restructuring',
        merger_acquisition: 'Merger / acquisition', offshoring: 'Offshoring',
        product_discontinuation: 'Product discontinued', cost_reduction: 'Cost reduction',
        macroeconomic: 'Macroeconomic'
    };
    var VERIF_LABELS = { gold: 'SEC filing', warn: 'WARN notice', silver: 'Press release', bronze: 'News' };
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
    function apiGet(path, params) {
        var url = API + path;
        var q = qs(params);
        if (q) url += (url.indexOf('?') > -1 ? '&' : '?') + q;
        return fetch(url, { credentials: 'same-origin' }).then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.json();
        });
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
            sources: 'alt-f-verification', reasons: 'alt-f-reasons'
        };
        Object.keys(mappings).forEach(function (key) {
            if (query.has(key)) writeControl(mappings[key], query.get(key).split(',').filter(Boolean));
        });
        [['from', 'alt-f-from'], ['to', 'alt-f-to'], ['q', 'alt-search'], ['company', 'alt-f-company'],
         ['keyword', 'alt-f-keyword'], ['min_jobs', 'alt-f-minjobs']].forEach(function (pair) {
            if (query.has(pair[0])) writeControl(pair[1], query.get(pair[0]));
        });
        if (query.get('ai') === '1') writeControl('alt-f-ai', true);
        if (query.get('stage') === 'announced') writeControl('alt-f-announced', true);
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
        if (id === 'alt-f-country') LAST_MULTI_DIM = 'country';
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
        var np = nextPullET();
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
            // Up to four selections are named in full — "Australia +2 more"
            // hid exactly the cross-reference the picker exists for. Five or
            // more fall back to the compact form.
            // Every hand-picked country is named — hiding any behind
            // "+N more" defeats the cross-referencing the picker exists for.
            parts.push(regionNameFor(countries) || countries.join(' · '));
        }
        [['alt-f-state', 'US: '], ['alt-f-industry', null]].forEach(function (p) {
            var v = selectedList(p[0]);
            if (v.length) parts.push((p[1] || '') + (v.length <= 6 ? v.join(' · ')
                : v.slice(0, 5).join(' · ') + ' +' + (v.length - 5) + ' more'));
        });
        // Narrowing toggles change what every card MEANS — say so on the
        // cards themselves, or "Verified" silently becomes "verified AI".
        if (readControl('alt-f-ai')) parts.push('AI-attributed rows only');
        if (readControl('alt-f-announced')) parts.push('announced only');
        return parts.length ? ' · ' + parts.join(' · ') : '';
    }

    // Shows the retained Challenger AI benchmark under the Announced-AI card
    // ONLY when the view is scoped to the United States (their measure is
    // US-only, so showing it against a world view would mislead). Reads the
    // monthly-reconciliation record the server injects; updates itself when
    // the next official report is retained.
    function renderChallengerNote() {
        var note = document.getElementById('alt-stat-challenger-note');
        if (!note) return;
        var card = note.closest('[data-challenger]');
        var data;
        try { data = JSON.parse(card.getAttribute('data-challenger') || '{}'); } catch (e) { data = {}; }
        var countries = readControl('alt-f-country') || [];
        var usOnly = countries.length === 1 && countries[0] === 'United States';
        if (!usOnly || !data.ai_ytd) { note.style.display = 'none'; return; }
        // The cards above are the STRICT tier by job location, so quoting
        // Challenger's number alone reads as a huge gap when we actually
        // exceed them on their own counting basis (broad AI attribution,
        // counted by US employer). Fetch that basis and say both plainly.
        note.innerHTML = 'Challenger: <b>' + fmt(data.ai_ytd) + '</b> AI cuts YTD (through ' + monthLabel(data.ref_month) + ') · <a href="#alt-challenger-comparison">like-for-like comparison</a>';
        note.style.display = '';
        var y = new Date().getFullYear();
        apiGet('aggregate', { years: String(y), country: 'United States', country_basis: 'employer' }).then(function (a) {
            var broad = a && a.totals && a.totals.ai_broad_jobs;
            if (!broad) return;
            note.innerHTML = 'Challenger: <b>' + fmt(data.ai_ytd) + '</b> AI cuts YTD (through ' + monthLabel(data.ref_month) + ').<br>'
                + 'Counted their way (by US employer): we track <b>' + fmt(broad) + '</b> · <a href="#alt-challenger-comparison">like-for-like comparison</a>';
        }).catch(function () { /* keep the basic note */ });
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
        var whenAnnounced = period.replace(' YTD', '') + scope + ' · includes future-dated plans';
        setText('alt-stat-total', fmt(verifiedJ));
        setText('alt-stat-total-entries', when);
        setText('alt-stat-announced', fmt(annJ));
        setText('alt-stat-announced-sub', whenAnnounced);
        setText('alt-stat-all', fmt(t.jobs || 0));
        setText('alt-stat-all-sub', whenAnnounced);
        // AI-attributed is the VERIFIED subset; announced-AI is the ANNOUNCED
        // subset. Each card says which parent number it belongs to.
        var aiJ = (t.ai_verified_jobs != null) ? t.ai_verified_jobs : t.ai_jobs;
        setText('alt-stat-ai', fmt(aiJ));
        var pctTxt = function (num, den) {
            if (!(den > 0) || num == null) return null;
            var pv = 100 * num / den;
            return (pv >= 10 ? Math.round(pv) : pv.toFixed(1)) + '%';
        };
        setText('alt-stat-ai-sub', when);
        var shareV = pctTxt(aiJ, verifiedJ);
        setText('alt-stat-ai-share-line', shareV ? shareV + ' of verified cuts were blamed on AI by the employer' : '');
        // The broad card is the Challenger-style measure, and Challenger
        // counts by EMPLOYER: with a country filter active, refetch on the
        // employer basis so the headline number is the comparable one
        // (Oracle's 21K counts for the US even though its cuts span
        // countries). Location-basis fills first so the card never sits
        // empty; the employer figure replaces it when it arrives.
        setText('alt-stat-ai-broad', fmt(t.ai_broad_jobs || 0));
        setText('alt-stat-ai-broad-sub', when);
        var shareB = pctTxt(t.ai_broad_jobs, t.jobs);
        setText('alt-stat-ai-broad-share-line', shareB ? shareB + ' of all cuts in this view have an AI link' : '');
        // The anticipated card is FIXED-SCOPE: current year, US employers,
        // broad AI — the like-for-like total against the US benchmark. It
        // deliberately ignores the page filters (its description says so).
        var antSeq = (renderStats._antSeq = (renderStats._antSeq || 0) + 1);
        var yNow = new Date().getFullYear();
        apiGet('aggregate', { years: String(yNow), country: 'United States', country_basis: 'employer' }).then(function (a) {
            if (antSeq !== renderStats._antSeq) return;
            var tot = a && a.totals && a.totals.ai_broad_jobs;
            if (tot == null) return;
            setText('alt-stat-ai-anticipated', fmt(tot));
            setText('alt-stat-ai-anticipated-sub', yNow + ' YTD · US employers');
            var shareA = (a.totals && a.totals.jobs > 0) ? (100 * tot / a.totals.jobs) : null;
            setText('alt-stat-ai-anticipated-share-line',
                shareA != null ? (shareA >= 10 ? Math.round(shareA) : shareA.toFixed(1)) + '% of all US cuts this year have an AI link' : '');
        }).catch(function () { setText('alt-stat-ai-anticipated', '—'); });
        var aiAnnJ = (t.ai_announced_jobs != null)
            ? t.ai_announced_jobs
            : Math.max(0, (t.ai_jobs || 0) - aiJ);
        setText('alt-stat-ai-announced', fmt(aiAnnJ));
        setText('alt-stat-ai-announced-sub', whenAnnounced);

        setText('alt-stat-companies', fmt(t.companies));
        setText('alt-stat-industries', fmt(t.industries));
        setText('alt-stat-countries', fmt(t.countries));
        setText('alt-stat-states', t.states > 0 ? fmt(t.states) : '0');
        // Singular/plural so "1 countries" never renders
        setText('alt-stat-industries-label', t.industries === 1 ? 'industry' : 'industries');
        setText('alt-stat-countries-label', (t.countries === 1 ? 'country' : 'countries') + ' with layoffs');
        setText('alt-stat-states-label', t.states === 1 ? 'US state' : 'US states');

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
        // Largest single events: name, jobs, AI segment when explicitly
        // attributed. Tapping toggles the company text filter.
        var companyBox = document.getElementById('alt-f-company');
        var leaderEntries = (agg.leaders || []).map(function (l) {
            return [l.company_name, l.job_count, l.ai_explicit ? l.job_count : 0];
        });
        renderAiShare(agg.series);
        renderYoY(agg.series);
        // AI intensity: which industries' cuts are MOST AI-attributed (share
        // of that industry's jobs, min 1,000 jobs so tiny bases don't rank).
        var intensity = (agg.top_industries || [])
            .filter(function (e) { return e[1] >= 1000 && e[2] > 0; })
            .map(function (e) { return [e[0], Math.round(100 * e[2] / e[1]), Math.round(100 * e[2] / e[1])]; })
            .sort(function (a, b) { return b[1] - a[1]; })
            .slice(0, 8);
        renderBarList('alt-bars-ai-intensity', intensity, null, [], null, '%');
        renderBarList('alt-bars-sourcetypes', (agg.source_types || []).map(function (e) {
            return [SOURCE_TYPE_LABELS[e[0]] || e[0], e[1], e[2]];
        }), null, []);
        renderBarList('alt-bars-leaders', leaderEntries, null,
            companyBox && companyBox.value ? [companyBox.value] : [],
            companyBox ? function (val) { companyBox.value = (companyBox.value === val) ? '' : val; } : null);
        renderBarList('alt-bars-repeat', (agg.repeat_companies || []).map(function (e) { return [e[0], e[1], 0]; }), null,
            companyBox && companyBox.value ? [companyBox.value] : [],
            companyBox ? function (val) { companyBox.value = (companyBox.value === val) ? '' : val; } : null, ' rounds');
        var countryTitle = document.getElementById('alt-country-chart-title');
        if (countryTitle) {
            countryTitle.innerHTML = selectedList('alt-f-country').length
                ? 'By country <span class="alt-chart-sub">Other countries you could pivot to · tap to filter</span>'
                : 'By country <span class="alt-chart-sub"><span class="alt-ai-key"></span> AI share · tap to filter</span>';
        }
    }

    function selectedList(id) {
        var v = readControl(id);
        return Array.isArray(v) ? v : (v ? [v] : []);
    }

    // "Where the cuts are" bars: name left, value right, a track whose blue
    // fill is scaled to the top bar, with an orange leading segment showing the
    // AI-attributed share. Rows are buttons that toggle the matching filter.
    function renderBarList(containerId, entries, filterId, activeValues, onPick, suffix) {
        var box = document.getElementById(containerId);
        if (!box) return;
        // Compact cards show a top-4 preview; expanded (or full-size dashboard
        // cards) show up to 12.
        var mini = box.closest('.alt-mini');
        var compact = mini && !mini.classList.contains('alt-expanded');
        var fullCount = (entries || []).length;
        var limit = compact ? 4 : 24;
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
                + ((filterId || onPick) ? '' : ' disabled')
                + ' data-val="' + escapeHtml(label) + '" aria-pressed="' + (isActive ? 'true' : 'false') + '">'
                + '<span class="alt-barrow-top"><span class="alt-barrow-name">' + escapeHtml(label) + '</span>'
                + '<span class="alt-barrow-val">' + fmt(jobs) + (suffix || '') + '</span></span>'
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
                    if (onPick) { onPick(btn.getAttribute('data-val')); }
                    else { toggleMultiFilter(filterId, btn.getAttribute('data-val')); }
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

    // Jobs dated after the current month (announced plans, future WARN
    // effective dates). Charted months exclude them; callers surface a note.
    function futureDatedJobs(series) {
        var now = new Date();
        var nowKey = now.getFullYear() + '-' + pad2(now.getMonth() + 1);
        return (series || []).reduce(function (sum, s) {
            return s.month > nowKey ? sum + (s.jobs || 0) : sum;
        }, 0);
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
            return apiGet('aggregate', params).then(function (a) { return (a && a.series) || []; });
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
        var cmp = compareSelections();
        if (cmp) { renderCompareTrend(cmp); return; }
        var futureJobs = futureDatedJobs(series);
        series = fillMonths(series);
        var range = document.getElementById('alt-trend-range');
        if (range) range.textContent = (series.length
            ? monthLabel(series[0].month) + ' – ' + monthLabel(series[series.length - 1].month) : '')
            + (futureJobs > 0 ? ' · ' + fmt(futureJobs) + ' future-dated jobs in the table, not charted' : '');
        if (!series || !series.length) { clearChart('alt-chart-weekly'); return; }
        var options = cloneOptions();
        options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || 'Jobs cut') + ': ' + fmt(ctx.parsed.y); } };
        // Verified is the primary line (matches the main stat card); the
        // dashed announced line keeps plan-stage months (incl. future WARN
        // effective dates) visible without mixing the two numbers.
        var verified = series.map(function (s) { return (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
        var announced = series.map(function (s) { return s.announced_jobs || 0; });
        // A single-month filter yields one data point; with pointRadius 0 a
        // lone point renders as literally nothing and the chart looks stale.
        var dots = series.length <= 2 ? 4 : 0;
        var datasets = [{ label: 'Verified job cuts', data: verified, borderColor: SEQ_BLUE, backgroundColor: SEQ_BLUE_FILL, borderWidth: 2, pointRadius: dots, pointHitRadius: 12, fill: true, tension: 0.3 }];
        if (announced.some(function (v) { return v > 0; })) {
            // STACKED band: announced plans sit on top of verified, so the
            // top edge of the amber band reads as verified + announced —
            // matching the intuition that plans "add to" the total.
            datasets.push({ label: 'Announced plans, stacked on top of Verified', data: announced, borderColor: ALT_AMBER, backgroundColor: 'rgba(230, 159, 0, 0.22)', borderWidth: 1.5, pointRadius: dots, pointHitRadius: 12, fill: true, tension: 0.3 });
            options.scales.y.stacked = true;
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            options.plugins.tooltip.callbacks.footer = function (items) {
                var total = items.reduce(function (s, it) { return s + it.parsed.y; }, 0);
                return items.length > 1 ? 'Total incl. plans: ' + fmt(total) : '';
            };
        }
        mountChart('alt-chart-weekly', {
            type: 'line',
            data: { labels: series.map(function (s) { return monthLabel(s.month); }), datasets: datasets },
            options: options
        });
    }

    // Monthly AI share of verified cuts, as a percent line.
    // Year-over-year: this selection's verified line vs the same filters one
    // year earlier (dashed grey). Shown when exactly one year is in scope.
    var YOY_SEQ = 0;
    function renderYoY(series) {
        var box = document.getElementById('alt-chart-yoy');
        if (!box) return;
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
                return apiGet('aggregate', p).then(function (a) { return (a && a.series) || []; });
            })).then(function (lists) {
                if (seq !== YOY_SEQ) return;
                var datasets = picked.map(function (yr, i) {
                    var by = {};
                    lists[i].forEach(function (s) { by[s.month.slice(5)] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
                    return { label: String(yr),
                        data: mm.map(function (m) { return (parseInt(yr, 10) === nowYearNum && m > nowKey2) ? null : (by[m] || 0); }),
                        borderColor: PALETTE[i % PALETTE.length], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.3 };
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
            (series || []).forEach(function (s) { cur[s.month.slice(5)] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
            ((prev && prev.series) || []).forEach(function (s) { old[s.month.slice(5)] = (s.verified_jobs != null) ? s.verified_jobs : s.jobs; });
            var months = ['01','02','03','04','05','06','07','08','09','10','11','12'];
            var nowKey = pad2(new Date().getMonth() + 1);
            var labels = months.map(function (m) { return monthLabel(year + '-' + m).split(' ')[0]; });
            var curData = months.map(function (m) { return (year === new Date().getFullYear() && m > nowKey) ? null : (cur[m] || 0); });
            var oldData = months.map(function (m) { return old[m] || 0; });
            if (!curData.some(function (v) { return v > 0; }) && !oldData.some(function (v) { return v > 0; })) { clearChart('alt-chart-yoy'); return; }
            var options = cloneOptions();
            options.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            options.plugins.tooltip.callbacks = { label: function (ctx) { return (ctx.dataset.label || '') + ': ' + fmt(ctx.parsed.y); } };
            mountChart('alt-chart-yoy', { type: 'line', data: { labels: labels, datasets: [
                { label: String(year), data: curData, borderColor: SEQ_BLUE, backgroundColor: SEQ_BLUE_FILL, borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: true, tension: 0.3 },
                { label: String(year - 1), data: oldData, borderColor: '#9aa0ab', borderDash: [6, 4], borderWidth: 2, pointRadius: 0, pointHitRadius: 12, fill: false, tension: 0.3 }
            ] }, options: options });
        }).catch(function () { clearChart('alt-chart-yoy'); });
    }

    var CMP_SHARE_SEQ = 0;
    function renderCompareAiShare(cmp) {
        var seq = ++CMP_SHARE_SEQ;
        Promise.all(cmp.values.map(function (v) {
            var params = currentParams();
            params[cmp.dim === 'years' ? 'years' : 'country'] = v;
            return apiGet('aggregate', params).then(function (a) { return (a && a.series) || []; });
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
        var cmpShare = compareSelections();
        if (cmpShare) { renderCompareAiShare(cmpShare); return; }
        series = fillMonths(series);
        var pts = (series || []).map(function (s) {
            var v = (s.verified_jobs != null) ? s.verified_jobs : s.jobs;
            var ai = (s.ai_verified_jobs != null) ? s.ai_verified_jobs : (s.ai_jobs || 0);
            return { month: s.month, v: v > 0 ? Math.round(1000 * ai / v) / 10 : null };
        });
        if (!pts.some(function (p) { return p.v > 0; })) { clearChart('alt-chart-ai-share-trend'); return; }
        var options = cloneOptions();
        options.scales.y.ticks.callback = function (v) { return v + '%'; };
        options.plugins.tooltip.callbacks = { label: function (ctx) { return 'AI share: ' + ctx.parsed.y + '%'; } };
        mountChart('alt-chart-ai-share-trend', { type: 'line', data: {
            labels: pts.map(function (p) { return monthLabel(p.month); }),
            datasets: [{ data: pts.map(function (p) { return p.v; }), borderColor: ALT_RED, backgroundColor: 'rgba(213,94,0,0.1)', borderWidth: 2, pointRadius: pts.length <= 2 ? 4 : 0, pointHitRadius: 12, fill: true, tension: 0.25, spanGaps: true }]
        }, options: options });
    }

    var SOURCE_TYPE_LABELS = { warn: 'WARN notices', news: 'News reports', sec: 'SEC filings', '8K': 'SEC 8-K filings',
        erm: 'Eurofound ERM', press_release: 'Company releases', seed: 'Curated (sourced)' };

    var CMP_AI_SEQ = 0;
    function renderCompareAiCumulative(cmp) {
        var seq = ++CMP_AI_SEQ;
        Promise.all(cmp.values.map(function (v) {
            var params = currentParams();
            params[cmp.dim === 'years' ? 'years' : 'country'] = v;
            return apiGet('aggregate', params).then(function (a) { return (a && a.series) || []; });
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
        var datasets = [{ label: 'AI-attributed (verified)', data: cumV, borderColor: ALT_RED, backgroundColor: 'rgba(213, 94, 0, 0.15)', borderWidth: 2, pointRadius: dots, pointHitRadius: 12, fill: true, tension: 0.25 }];
        if (cumA[cumA.length - 1] > 0) {
            datasets.push({ label: 'Announced AI plans, stacked on top', data: cumA, borderColor: ALT_AMBER, backgroundColor: 'rgba(230, 159, 0, 0.22)', borderWidth: 1.5, pointRadius: dots, pointHitRadius: 12, fill: true, tension: 0.25 });
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

    // The server-rendered reconciliation table shows the STRICT comparator,
    // which reads as all-zeros until announcement-date enrichment completes.
    // Enrich it live: inject a broad US-employer column with real monthly
    // numbers, and say plainly what a strict zero means.
    function enhanceChallengerTable() {
        var table = document.querySelector('.alt-challenger-table table');
        if (!table) return;
        var head = table.querySelector('thead tr');
        var rows = table.querySelectorAll('tbody tr');
        if (!head || !rows.length) return;
        var firstMonth = (rows[rows.length - 1].cells[0] || {}).textContent || '';
        var yr = /^(\d{4})-/.test(firstMonth) ? firstMonth.slice(0, 4) : String(new Date().getFullYear());
        apiGet('aggregate', { years: yr, country: 'United States', country_basis: 'employer' }).then(function (a) {
            var by = {};
            ((a && a.series) || []).forEach(function (sr) { by[sr.month] = sr.ai_broad_jobs || 0; });
            var th = document.createElement('th');
            th.textContent = 'AskTheRecruiter AI broad, US employer (month)';
            head.insertBefore(th, head.cells[3]);
            Array.prototype.forEach.call(rows, function (tr) {
                var m = (tr.cells[0] || {}).textContent.trim();
                var td = document.createElement('td');
                var v = by[m];
                td.innerHTML = (v != null) ? '<b>' + fmt(v) + '</b>' : '—';
                tr.insertBefore(td, tr.cells[3]);
            });
            var note = document.createElement('p');
            note.className = 'alt-muted';
            note.textContent = 'A strict zero means no event has completed full announcement-date enrichment for that month yet, not zero AI cuts: the live broad column beside it carries the comparable monthly numbers.';
            table.parentNode.parentNode.insertBefore(note, table.parentNode);
        }).catch(function () { /* table stays as rendered */ });
    }

    function initChallengerReconciliationChart() {
        var ytdCanvas = document.getElementById('alt-chart-challenger-reconciliation');
        var monthlyCanvas = document.getElementById('alt-chart-challenger-monthly');
        var canvas = ytdCanvas || monthlyCanvas;
        if (!canvas || !chartsAvailable()) return;
        var points;
        try { points = JSON.parse(canvas.getAttribute('data-points') || '[]'); }
        catch (e) { return; }
        if (!Array.isArray(points) || points.length < 2) return;
        function options(step) {
            var result = cloneOptions();
            result.plugins.tooltip.callbacks = { label: function (ctx) {
                return (ctx.dataset.label || 'Jobs') + ': ' + fmt(ctx.parsed.y);
            } };
            result.plugins.legend = { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } };
            // Tall charts + fixed 10K/25K gridlines so the small strict lines
            // near zero stay readable against Challenger's six-figure scale.
            result.scales.y.ticks.stepSize = step;
            result.scales.y.ticks.maxTicksLimit = 24;
            result.scales.y.ticks.callback = function (value) { return value >= 1000 ? (value / 1000) + 'K' : value; };
            return result;
        }
        function pick(field) { return points.map(function (p) { return (p[field] === undefined || p[field] === null) ? null : p[field]; }); }
        function hasAny(field) { return points.some(function (p) { return p[field] !== null && p[field] !== undefined; }); }
        // Four labeled comparison series: Challenger vs AskTheRecruiter, for
        // all announced US cuts and for AI-attributed cuts. All-cuts lines
        // appear only once the reconciliation job has retained those fields.
        // Five distinct colors — solid = AI pair, dashed = all-cuts pair,
        // green = our observed AI (real holdings; not the strict comparator).
        var C = { chalAI: '#2a78d6', chalAll: '#8f98a8', usObs: '#1baf7a', usStrict: '#e34948', usAll: '#8b46c8', usBroad: '#0f9d9d', usEmp: '#d97b16' };
        function datasetsFor(suffix, observed, broad, employer) {
            var sets = [
                { label: 'Challenger — AI cuts', data: pick('challenger_' + suffix), borderColor: C.chalAI, borderWidth: 2.5, pointRadius: 3, fill: false, tension: 0.2 },
                // Employer basis = evidenced US domicile, falling back to US
                // job location only where no domicile is recorded — so a US-HQ
                // company's multi-country cut counts, the way Challenger
                // counts it, and a foreign-HQ company's US cut does not.
                { label: 'AskTheRecruiter — US-employer basis (Challenger-comparable)', data: employer, borderColor: C.usEmp, borderWidth: 2.5, pointRadius: 3, fill: false, tension: 0.2 },
                { label: 'AskTheRecruiter — AI-linked, broad (US job location)', data: broad, borderColor: C.usBroad, borderWidth: 2.5, pointRadius: 3, fill: false, tension: 0.2 },
                { label: 'AskTheRecruiter — AI observed (verified + announced)', data: observed, borderColor: C.usObs, borderWidth: 2.5, pointRadius: 3, fill: false, tension: 0.2 },
                { label: 'AskTheRecruiter — strict comparator', data: pick('tracker_' + suffix), borderColor: C.usStrict, borderWidth: 2, pointRadius: 3, fill: false, tension: 0.2 }
            ];
            if (hasAny('challenger_total_' + suffix)) {
                sets.push({ label: 'Challenger — all cuts', data: pick('challenger_total_' + suffix), borderColor: C.chalAll, borderDash: [6, 4], borderWidth: 2, pointRadius: 3, fill: false, tension: 0.2 });
            }
            if (hasAny('tracker_all_' + suffix)) {
                sets.push({ label: 'AskTheRecruiter — announced US cuts (strict)', data: pick('tracker_all_' + suffix), borderColor: C.usAll, borderDash: [6, 4], borderWidth: 2, pointRadius: 3, fill: false, tension: 0.2 });
            }
            return sets;
        }
        var labels = points.map(function (p) { return monthLabel(p.period); });
        var benchYear = (points[0] && points[0].period || '2026').slice(0, 4);
        function mountBoth(obsMonth, obsYtd, broadMonth, broadYtd, empMonth, empYtd) {
            if (monthlyCanvas && hasAny('challenger_month')) {
                mountChart('alt-chart-challenger-monthly', {
                    type: 'line',
                    data: { labels: labels, datasets: datasetsFor('month', obsMonth, broadMonth, empMonth) }, options: options(10000)
                });
            }
            if (ytdCanvas) {
                mountChart('alt-chart-challenger-reconciliation', {
                    type: 'line',
                    data: { labels: labels, datasets: datasetsFor('ytd', obsYtd, broadYtd, empYtd) }, options: options(25000)
                });
            }
        }
        // Our observed AI by month (verified + announced) comes from the live
        // aggregate so the comparison never reads as "we have nothing" when
        // only the STRICT lines sit near zero. The second aggregate is the
        // same scope on the employer basis (country_basis=employer): curated/
        // evidenced US domicile plus blank-domicile US-job-location fallback.
        // Each fetch degrades to null alone so one failure only drops its own
        // lines instead of blanking the whole comparison.
        Promise.all([
            apiGet('aggregate', { years: benchYear, country: 'United States' }).catch(function () { return null; }),
            apiGet('aggregate', { years: benchYear, country: 'United States', country_basis: 'employer' }).catch(function () { return null; })
        ]).then(function (results) {
            var agg = results[0], empAgg = results[1];
            var by = {}, byBroad = {}, byEmp = {};
            ((agg && agg.series) || []).forEach(function (srow) {
                by[srow.month] = (srow.ai_verified_jobs || 0) + (srow.ai_announced_jobs || 0);
                byBroad[srow.month] = (srow.ai_broad_jobs != null) ? srow.ai_broad_jobs : by[srow.month];
            });
            ((empAgg && empAgg.series) || []).forEach(function (srow) {
                byEmp[srow.month] = (srow.ai_broad_jobs != null) ? srow.ai_broad_jobs
                    : ((srow.ai_verified_jobs || 0) + (srow.ai_announced_jobs || 0));
            });
            var run = 0, runB = 0, runE = 0;
            var obsMonth = agg ? points.map(function (p) { return by[p.period] != null ? by[p.period] : null; }) : null;
            var obsYtd = agg ? points.map(function (p) { run += (by[p.period] || 0); return run; }) : null;
            var broadMonth = agg ? points.map(function (p) { return byBroad[p.period] != null ? byBroad[p.period] : null; }) : null;
            var broadYtd = agg ? points.map(function (p) { runB += (byBroad[p.period] || 0); return runB; }) : null;
            var empMonth = empAgg ? points.map(function (p) { return byEmp[p.period] != null ? byEmp[p.period] : null; }) : null;
            var empYtd = empAgg ? points.map(function (p) { runE += (byEmp[p.period] || 0); return runE; }) : null;
            mountBoth(obsMonth, obsYtd, broadMonth, broadYtd, empMonth, empYtd);
        });
    }

    /* Announced-to-verified conversion card ---------------------------- */

    // The /conversion endpoint answers "do announced cuts actually happen?":
    // per announcement month, the share of announced jobs with verified
    // same-company records inside the window, capped per announcement. Not
    // filter-wired (like the Challenger charts beside it): the question is
    // about the whole announced tier, and recent months need their maturity
    // labels regardless of the active view.
    var CONVERSION_DATA = null;
    function initConversionChart() {
        if (!document.getElementById('alt-chart-conversion') || !chartsAvailable()) return;
        apiGet('conversion', {}).then(function (data) {
            CONVERSION_DATA = data;
            renderConversionChart();
        }).catch(function () { /* card stays empty; no fabricated series */ });
    }
    function renderConversionChart() {
        var data = CONVERSION_DATA;
        if (!data || !document.getElementById('alt-chart-conversion') || !chartsAvailable()) return;
        var win = data.window_months || 6;
        // Future-dated plans (pending) cannot have converted yet; charting
        // them as 0% would read as broken promises. They stay in the CSV.
        var rows = (data.series || []).filter(function (p) { return p.status !== 'pending' && p.conversion_pct !== null; });
        if (rows.length < 2) return;
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
                { label: 'Window complete (' + win + ' months elapsed)', data: pickStatus('complete'), backgroundColor: '#0072B2', stack: 'conv' },
                { label: 'Still maturing (expected to rise)', data: pickStatus('maturing'), backgroundColor: '#E69F00', stack: 'conv' }
            ] },
            options: options
        });
        var note = document.getElementById('alt-conversion-note');
        if (note) {
            note.style.display = '';
            note.textContent = 'Counts verified filings and sourced reports from the same company after each announcement, capped at the announced size. Orange months are still maturing: those announcements have not had the full ' + win + ' months to show follow-through, so low bars there are expected to rise. This is company-level corroboration, not proof a specific plan was completed or dropped; unmatched jobs can still have happened through attrition or outside filing systems.';
        }
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
                    var badges = [];
                    if (d > today) badges.push('<span class="alt-upcoming" title="Filed in advance. The effective date has not arrived yet.">upcoming</span>');
                    if (row.announced) badges.push('<span class="alt-upcoming" title="Announcement of planned cuts, not yet executed or filed">announced</span>');
                    // Keep date-state labels as one compact unit.  Plain
                    // inline whitespace let DataTables wrap "announced" onto
                    // a detached second line on narrow screens.
                    return '<span class="alt-date-cell"><time datetime="' + escapeHtml(d) + '">' + escapeHtml(d) + '</time>'
                        + (badges.length ? '<span class="alt-date-badges">' + badges.join('') + '</span>' : '')
                        + '</span>';
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
        if (row.ai_causation) {
            var aiDetail = AI_CAUSATION_LABELS[row.ai_causation] || row.ai_causation;
            if (row.confidence != null && Number(row.confidence) > 0) aiDetail += ' · evidence confidence ' + fmt(row.confidence) + '/100';
            if (row.review_status) aiDetail += ' · ' + String(row.review_status).replace(/_/g, ' ');
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">AI attribution status</span><p>' + escapeHtml(aiDetail) + '</p></div>');
        }
        if (row.employer_country) parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Employer country</span><p>' + escapeHtml(row.employer_country) + '</p></div>');
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
                    data: { labels: matches.map(function (r) { return r.layoff_date || 'unknown'; }), datasets: [{ data: matches.map(function (r) { return r.job_count; }), backgroundColor: matches.map(function (r) { return r.ai_explicit ? ALT_RED : SEQ_BLUE; }), borderRadius: 4, maxBarThickness: 40 }] },
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
        var iso = function (d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); };
        var d7 = new Date(now.getTime() - 6 * 86400000), d14 = new Date(now.getTime() - 13 * 86400000), d8 = new Date(now.getTime() - 7 * 86400000);
        // Everything is stage=verified so the period totals AND each period's
        // largest-event pick share one basis (an announced 50K plan must not
        // headline a 9K verified week).
        var pYear = Object.assign({ years: String(y), stage: 'verified' }, base);
        var pMonth = Object.assign({ from: y + '-' + pad2(now.getMonth() + 1) + '-01', to: iso(now), stage: 'verified' }, base);
        var pWeek = Object.assign({ from: iso(d7), to: iso(now), stage: 'verified' }, base);
        var pWeekPrev = Object.assign({ from: iso(d14), to: iso(d8), stage: 'verified' }, base);
        var pToday = Object.assign({ from: iso(now), to: iso(now), stage: 'verified' }, base);
        Promise.all([apiGet('aggregate', pYear), apiGet('aggregate', pMonth), apiGet('aggregate', pWeek), apiGet('aggregate', pWeekPrev), apiGet('aggregate', pToday)]).then(function (r) {
            var t = r[0].totals, m = r[1].totals, w = r[2].totals, wp = r[3].totals, td = (r[4] || {}).totals || {};
            var yLead = (r[0].leaders || [])[0], mLead = (r[1].leaders || [])[0], wLead = (r[2].leaders || [])[0];
            var today = MONTHS[now.getMonth()] + ' ' + now.getDate();
            var tV = t.entries || 0, tJ = t.jobs || 0;
            var tAI = t.ai_jobs || 0; // stage=verified scope, so ai_jobs is verified AI
            // Current-year averages are per day ELAPSED (year-to-date), not /365.
            var startOfYear = new Date(y, 0, 1);
            var daysElapsed = Math.max(1, Math.round((now - startOfYear) / 86400000) + 1);
            var b = function (v) { return '<b>' + v + '</b>'; }; // every value is our own fmt() output
            // Companies and period figures are click-to-filter: the company
            // name sets the Company filter; a period's numbers set the date
            // range (or year), so the whole page re-scopes to what was clicked.
            var esc = function (v) { return String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;'); };
            var largest = function (ld) {
                return (ld && ld.job_count)
                    ? ' · largest: <a href="#" class="alt-nfilter" data-company="' + esc(ld.company_name) + '" title="Filter the page to this company">' + b(esc(ld.company_name)) + '</a> (' + fmt(ld.job_count) + ')'
                    : '';
            };
            var row = function (label, body, filterAttrs) {
                var open = filterAttrs ? '<a href="#" class="alt-nfilter" ' + filterAttrs + ' title="Filter the page to this period">' : '<span>';
                var close = filterAttrs ? '</a>' : '</span>';
                return '<div class="alt-nrow">' + open + '<span class="alt-nlabel">' + label + '</span>' + close + '<span>' + body + '</span></div>';
            };
            // "events affecting N workers", never "layoffs with N people"
            // (readers mistook event counts for people counts). Every number
            // is scoped to the active tab's countries.
            var wJ = w.jobs || 0, wE = w.entries || 0, wpJ = wp.jobs || 0;
            var weekDelta = '';
            if (wJ > 0 && wpJ > 0) {
                var delta = Math.round(100 * (wJ - wpJ) / wpJ);
                weekDelta = delta >= 0 ? ' · up ' + b(delta + '%') + ' vs the week before' : ' · down ' + b(Math.abs(delta) + '%') + ' vs the week before';
            }
            var rows = '';
            var tdJ = td.jobs || 0, tdE = td.entries || 0;
            if (tdJ > 0) {
                rows += row('Today', b(fmt(tdJ)) + ' workers · ' + b(fmt(tdE)) + ' verified event' + (tdE === 1 ? '' : 's') + largest(((r[4] || {}).leaders || [])[0]),
                    'data-from="' + iso(now) + '" data-to="' + iso(now) + '"');
            }
            rows += row('This week', wJ > 0
                ? b(fmt(wJ)) + ' workers · ' + b(fmt(wE)) + ' verified event' + (wE === 1 ? '' : 's') + largest(wLead) + weekDelta
                : 'no verified layoff events reported yet',
                'data-from="' + iso(d7) + '" data-to="' + iso(now) + '"');
            var mJ = m.jobs || 0, mE = m.entries || 0;
            rows += row('This month', mJ > 0
                ? b(fmt(mJ)) + ' workers · ' + b(fmt(mE)) + ' verified event' + (mE === 1 ? '' : 's') + largest(mLead)
                : 'no verified layoff events reported yet',
                'data-from="' + y + '-' + pad2(now.getMonth() + 1) + '-01" data-to="' + iso(now) + '"');
            rows += row(y + ' so far', tJ > 0
                ? b(fmt(tJ)) + ' workers · ' + b(fmt(tV)) + ' verified event' + (tV === 1 ? '' : 's') +
                  ' (about ' + fmt(Math.round(tJ / daysElapsed)) + ' workers a day)' +
                  (tAI ? ' · explicitly blamed on AI: ' + b(fmt(tAI)) : '') + largest(yLead)
                : 'no verified layoff events yet' + (ACTIVE_TAB !== 'world'
                    ? ' — coverage for this region is still filling in; pick "All time" in the Years filter for earlier events' : ''),
                'data-years="' + y + '"');
            // Post-sized rewrite for the copy button: X counts any URL as 23
            // characters, and the weekly detail degrades in steps (full → no
            // delta → no largest event) to stay under 280.
            var LINK = 'asktherecruiter.com/blog/ai-layoff-tracker/';
            var xLen = function (s2) { return s2.replace(LINK, 'xxxxxxxxxxxxxxxxxxxxxxx').length; };
            var lead = 'AI layoffs, ' + today + ': ' + fmt(tJ) + ' workers across ' + fmt(tV) + ' verified layoff event' + (tV === 1 ? '' : 's') +
                ' ' + tab.label + ' in ' + y + (tAI ? ' — ' + fmt(tAI) + ' cuts explicitly blamed on AI' : '') + '.';
            var tail = ' Live tracker (AskTheRecruiter.com): ' + LINK + ' #Layoffs #AI';
            var post = lead + tail;
            if (wJ > 0) {
                var wkBare = ' This week: ' + fmt(wJ) + ' workers across ' + fmt(wE) + ' event' + (wE === 1 ? '' : 's') + '.';
                var wkLead = (wLead && wLead.job_count)
                    ? wkBare.slice(0, -1) + ', largest at ' + wLead.company_name + ' (' + fmt(wLead.job_count) + ').'
                    : '';
                var wkFull = '';
                if (wkLead && wpJ > 0) {
                    var wd = Math.round(100 * (wJ - wpJ) / wpJ);
                    wkFull = wkLead.slice(0, -1) + (wd >= 0 ? ', up ' + wd : ', down ' + Math.abs(wd)) + '% on last week.';
                }
                [wkFull, wkLead, wkBare].some(function (wk) {
                    if (wk && xLen(lead + wk + tail) <= 278) { post = lead + wk + tail; return true; }
                    return false;
                });
            }
            el.innerHTML = '<div class="alt-narrative-head"><span>Today, ' + b(today) + ' · verified layoffs ' + tab.label + '</span>' +
                '<button type="button" class="alt-btn alt-btn-sm alt-narrative-copy" title="Copy a post-sized version of this summary (fits in one X/Twitter post)">Copy as post</button></div>' + rows;
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
            'alt-bars-countries': ['top_countries', 'by-country'],
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
                return ((LAST_AGG && LAST_AGG.top_industries) || [])
                    .filter(function (e) { return e[1] >= 1000 && e[2] > 0; })
                    .map(function (e) { return [e[0], Math.round(100 * e[2] / e[1]), Math.round(100 * e[2] / e[1])]; })
                    .sort(function (a, b) { return b[1] - a[1]; });
            }
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
                    var rows = BAR_ROWS_FN[t] ? BAR_ROWS_FN[t]() : ((meta && LAST_AGG && LAST_AGG[meta[0]]) || []);
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

    $(function () {
        var citeDate = document.getElementById('alt-cite-date');
        if (citeDate) citeDate.textContent = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        var citeCopy = document.getElementById('alt-cite-copy');
        if (citeCopy) citeCopy.addEventListener('click', function () {
            var el = document.getElementById('alt-cite-text');
            if (el && navigator.clipboard) { navigator.clipboard.writeText(el.textContent.replace(/\s+/g, ' ').trim()); citeCopy.textContent = 'Copied ✓'; setTimeout(function () { citeCopy.textContent = 'Copy'; }, 1500); }
        });

        initStatsMeta();
        renderSourceHealth();

        var needsData = document.getElementById('alt-table') || document.getElementById('alt-stats-bar')
            || document.querySelector('.alt-dashboard') || document.querySelector('.alt-ai-tracker')
            || document.querySelector('.alt-company-history');
        if (!needsData) return;

        if (chartsAvailable()) {
            Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
            Chart.defaults.color = INK.muted;
            initChallengerReconciliationChart();
            initConversionChart();
        }
        enhanceChallengerTable();
        DASH_PRESENT = !!document.querySelector('.alt-dashboard');

        // Standalone AI / company pages don't use the shared filter surface.
        initAiTracker();
        initCompanyHistory();
        initMethodologyAnchors();
        renderProvenance();

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
