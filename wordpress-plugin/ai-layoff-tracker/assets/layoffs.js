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
        macroeconomic: 'Macroeconomic', closure: 'Plant / site closure'
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
        'alt-f-months', 'alt-f-industry', 'alt-f-country', 'alt-f-state', 'alt-f-reasons', 'alt-f-roles',
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
            sources: 'alt-f-verification', reasons: 'alt-f-reasons', roles: 'alt-f-roles'
        };
        Object.keys(mappings).forEach(function (key) {
            if (query.has(key)) writeControl(mappings[key], query.get(key).split(',').filter(Boolean));
        });
        [['from', 'alt-f-from'], ['to', 'alt-f-to'], ['q', 'alt-search'], ['company', 'alt-f-company'],
         ['keyword', 'alt-f-keyword'], ['min_jobs', 'alt-f-minjobs']].forEach(function (pair) {
            if (query.has(pair[0])) writeControl(pair[1], query.get(pair[0]));
        });
        if (query.get('ai') === '1') writeControl('alt-f-ai', true);
        if (query.get('ai_broad') === '1') writeControl('alt-f-reasons', ['possible_ai']);
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
        // The two AI reason options must agree with the AI stat cards, which are
        // driven by the ai_explicit / ai_causation flag columns — NOT by
        // reason_tags. Translate them to the ai / ai_broad params so checking
        // "AI-linked (broad)" reproduces the broad card total exactly, instead of
        // the smaller reason-tagged subset. Broad supersedes specific (it
        // already includes every ai_explicit row). Non-AI reasons filter as before.
        var reasonsSel = (multiParam('alt-f-reasons') || '').split(',').filter(Boolean);
        if (reasonsSel.length) {
            var hasBroadAI = reasonsSel.indexOf('possible_ai') !== -1;
            var hasSpecificAI = reasonsSel.indexOf('ai_automation') !== -1;
            var restReasons = reasonsSel.filter(function (r) { return r !== 'possible_ai' && r !== 'ai_automation'; });
            if (hasBroadAI) p.ai_broad = '1';
            else if (hasSpecificAI) p.ai = '1';
            if (restReasons.length) p.reasons = restReasons.join(',');
        }
        if ((v = multiParam('alt-f-roles'))) p.roles = v;
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
        var aggParams = (window.altData && window.altData.embedParams) || currentParams();
        apiGet('aggregate', aggParams)
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
        { id: 'alt-f-roles', label: 'Role', kind: 'multi', map: ROLE_LABELS, color: 'teal' },
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
        // The broad card is the wider-lens AI measure. Location-basis fills
        // first so the card never sits empty.
        setText('alt-stat-ai-broad', fmt(t.ai_broad_jobs || 0));
        setText('alt-stat-ai-broad-sub', when);
        var shareB = pctTxt(t.ai_broad_jobs, t.jobs);
        setText('alt-stat-ai-broad-share-line', shareB ? shareB + ' of all cuts in this view have an AI link' : '');
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
        renderBarList('alt-bars-countries', (agg.top_countries || []).map(function (e) {
            return [e[0], e[1], e[2], countryFlag(e[0]) + e[0]];
        }), wired ? 'alt-f-country' : null, selectedList('alt-f-country'));
        AIMAP.data = agg; renderAiMap();
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
        var intensity = (agg.top_industries || [])
            .filter(function (e) { return e[1] >= 1000 && e[2] > 0; })
            .map(function (e) { return [e[0], Math.round(100 * e[2] / e[1]), Math.round(100 * e[2] / e[1])]; })
            .sort(function (a, b) { return b[1] - a[1]; })
            .slice(0, 8);
        renderBarList('alt-bars-ai-intensity', intensity, null, [], null, '%');
        // Roles most impacted: fixed-category jobs with the AI-attributed
        // share as the orange segment — the AI-vs-all comparison per team.
        // Coverage is partial by construction (only events whose sources name
        // the affected teams carry categories), so the subtitle states the
        // honest denominator instead of implying every event is categorized.
        renderBarList('alt-bars-roles', agg.top_roles, null, []);
        var rolesSub = document.getElementById('alt-roles-sub');
        var rolesCard = document.getElementById('alt-roles-card');
        if (rolesSub) {
            var rke = (agg.totals && agg.totals.roles_known_entries) || 0;
            // Small-sample guard: only a minority of sources name the teams cut,
            // so make the caveat unmissable when the base is thin — a reporter
            // must not read this as representative of the whole dataset.
            var small = rke < 100;
            if (rolesCard) rolesCard.classList.toggle('alt-small-sample', small);
            rolesSub.innerHTML = (small ? '<span class="alt-sample-warn">⚠ Small sample — illustrative only.</span> ' : '')
                + 'Each bar is total job cuts for that team; the <span class="alt-ai-key"></span> orange part'
                + ' and 🤖 number are the AI-linked share. Built from only the <b>' + fmt(rke)
                + ' of ' + fmt((agg.totals && agg.totals.entries) || 0) + '</b> records whose source named which teams were cut'
                + ' — a non-representative sample of where cuts land, <b>not</b> a breakdown of the total.';
        }
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
    // Country name -> ISO2 for emoji flags on the country list. Covers the
    // normalizer's vocabulary; unknown names simply render without a flag.
    var COUNTRY_ISO = { 'United States':'US','United Kingdom':'GB','Germany':'DE','France':'FR','Netherlands':'NL','India':'IN','Israel':'IL','Japan':'JP','Sweden':'SE','Canada':'CA','Australia':'AU','Brazil':'BR','China':'CN','Ireland':'IE','Singapore':'SG','Indonesia':'ID','Denmark':'DK','Finland':'FI','Norway':'NO','Poland':'PL','Spain':'ES','Italy':'IT','Austria':'AT','Belgium':'BE','Switzerland':'CH','Portugal':'PT','Czech Republic':'CZ','Czechia':'CZ','South Korea':'KR','Kenya':'KE','Nigeria':'NG','South Africa':'ZA','Egypt':'EG','Mexico':'MX','Argentina':'AR','Chile':'CL','Colombia':'CO','United Arab Emirates':'AE','Saudi Arabia':'SA','Turkey':'TR','Russia':'RU','Ukraine':'UA','New Zealand':'NZ','Philippines':'PH','Malaysia':'MY','Thailand':'TH','Vietnam':'VN','Taiwan':'TW','Hong Kong':'HK','Greece':'GR','Hungary':'HU','Romania':'RO','Bulgaria':'BG','Croatia':'HR','Slovakia':'SK','Slovenia':'SI','Estonia':'EE','Latvia':'LV','Lithuania':'LT','Luxembourg':'LU','Iceland':'IS','Serbia':'RS','Pakistan':'PK','Bangladesh':'BD','Sri Lanka':'LK','Nepal':'NP','Cambodia':'KH','Myanmar':'MM','Laos':'LA','Mongolia':'MN','Kazakhstan':'KZ','Qatar':'QA','Kuwait':'KW','Bahrain':'BH','Oman':'OM','Jordan':'JO','Lebanon':'LB','Iraq':'IQ','Iran':'IR','Morocco':'MA','Tunisia':'TN','Algeria':'DZ','Ghana':'GH','Ethiopia':'ET','Tanzania':'TZ','Uganda':'UG','Zambia':'ZM','Zimbabwe':'ZW','Botswana':'BW','Namibia':'NA','Mozambique':'MZ','Angola':'AO','Senegal':'SN','Ivory Coast':'CI','Cameroon':'CM','Peru':'PE','Ecuador':'EC','Uruguay':'UY','Paraguay':'PY','Bolivia':'BO','Venezuela':'VE','Costa Rica':'CR','Panama':'PA','Guatemala':'GT','Dominican Republic':'DO','Jamaica':'JM','Trinidad and Tobago':'TT','Cuba':'CU','Haiti':'HT' };
    function countryFlag(name) {
        if (name === 'Multiple countries') return '\uD83C\uDF10 ';
        var iso = COUNTRY_ISO[name];
        if (!iso) return '';
        var A = 0x1F1E6;
        return String.fromCodePoint(A + iso.charCodeAt(0) - 65, A + iso.charCodeAt(1) - 65) + ' ';
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
        var limit = 24;
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
            var label = e[0], jobs = e[1], ai = e[2] || 0, display = e[3] || e[0];
            var w = Math.max(2, Math.round(jobs / max * 100));
            var aiW = jobs > 0 ? (ai / jobs * w) : 0;
            var isActive = active.indexOf(label) !== -1;
            var dim = active.length && !isActive;
            // AI breakdown: expanded rows spell it out (total · AI n · x%);
            // compact rows keep the visual fill plus a hover tooltip, so the
            // small cards stay scannable and the detail is one expand away.
            var hasAi = !suffix && ai > 0 && ai <= jobs;
            var aiPct = hasAi ? Math.round(100 * ai / jobs) : 0;
            var valTxt = fmt(jobs) + (suffix || '');
            if (hasAi && !compact) valTxt += ' · \uD83E\uDD16 ' + fmt(ai) + ' (' + aiPct + '%)';
            var tip = hasAi ? (label + ': ' + fmt(jobs) + ' total · ' + fmt(ai) + ' AI-linked (' + aiPct + '%)') : '';
            html += '<button type="button" class="alt-barrow' + (isActive ? ' alt-barrow-on' : '') + (dim ? ' alt-barrow-dim' : '') + '"'
                + ((filterId || onPick) ? '' : ' disabled')
                + (tip ? ' title="' + escapeHtml(tip) + '"' : '')
                + ' data-val="' + escapeHtml(label) + '" aria-pressed="' + (isActive ? 'true' : 'false') + '">'
                + '<span class="alt-barrow-top"><span class="alt-barrow-name">' + escapeHtml(display) + '</span>'
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


    /* Announced-to-verified conversion card ---------------------------- */

    // The /conversion endpoint answers "do announced cuts actually happen?":
    // per announcement month, the share of announced jobs with verified
    // same-company records inside the window, capped per announcement. Not
    // filter-wired: the question is
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
        // AI slices wear the AI accent hues used site-wide (vermillion for
        // company-stated, orange for broad/possible); other reasons draw from
        // the non-AI hues so the donut speaks the same color language as the
        // cards and bar fills.
        var REASON_COLORS = { ai_automation: '#D55E00', possible_ai: '#E69F00' };
        var NEUTRAL_SEQ = ['#0072B2', '#009E73', '#CC79A7', '#56B4E9', '#000000', '#999999', '#7A6A52', '#4A5E7A'];
        var neutralIdx = 0;
        var colors = entries.map(function (e) {
            var base = REASON_COLORS[e[0]] || NEUTRAL_SEQ[(neutralIdx++) % NEUTRAL_SEQ.length];
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
                    if (row.source_type === 'warn') {
                        var wl = warnLinks(row);
                        if (!wl.primary) return escapeHtml(row.source_name || '—');
                        if (wl.exact) {
                            // Exact notice + distinct state list → both links; the
                            // list stays a compact secondary so the cell reads clean.
                            var suffix = wl.list
                                ? ' <a href="' + escapeHtml(wl.list) + '" target="_blank" rel="noopener nofollow" class="alt-muted" title="The state’s official WARN list this notice is filed in">(list)</a>'
                                : '';
                            return '<a href="' + escapeHtml(wl.primary) + '" target="_blank" rel="noopener nofollow" title="Opens this exact WARN notice">' + escapeHtml(row.source_name || 'source') + '</a>' + suffix;
                        }
                        return '<a href="' + escapeHtml(wl.primary) + '" target="_blank" rel="noopener nofollow" title="Opens the state’s official WARN list. This notice is a row in it.">' + escapeHtml(row.source_name || 'source') + '</a> <span class="alt-muted" title="The notice is a row in the state’s official WARN list">(list)</span>';
                    }
                    var url = safeUrl(d);
                    if (!url) return escapeHtml(row.source_name || '—');
                    return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow" title="Opens the primary source">' + escapeHtml(row.source_name || 'source') + '</a>';
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
        var verif = row.verification_level ? ' · <span class="alt-badge alt-badge-' + escapeHtml(row.verification_level) + '">' + escapeHtml(VERIF_LABELS[row.verification_level] || 'News') + '</span>' : '';
        var src;
        if (row.source_type === 'warn') {
            var wl = warnLinks(row);
            var warnText = wl.exact
                ? 'View this WARN notice (' + (row.source_name || 'source') + ') ↗'
                : 'View the state’s official WARN list (this notice is a row in it) ↗';
            src = wl.primary ? '<a href="' + escapeHtml(wl.primary) + '" target="_blank" rel="noopener nofollow">' + escapeHtml(warnText) + '</a>' : escapeHtml(row.source_name || '—');
            // Exact notice + a distinct state list → offer both: the specific
            // record and the official index it sits in.
            if (wl.list) {
                src += ' <span class="alt-src-sep">·</span> <a href="' + escapeHtml(wl.list) + '" target="_blank" rel="noopener nofollow">State WARN list ↗</a>';
            }
        } else {
            var url = safeUrl(row.source_url);
            src = url ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">' + escapeHtml('View primary source (' + (row.source_name || 'source') + ') ↗') + '</a>' : escapeHtml(row.source_name || '—');
        }
        parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Source</span><div>' + src + verif + '</div></div>');
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
    var AIMAP = { scope: 'world', data: null, outline: {}, loading: {}, transform: null, transformScope: null, retries: 0 };

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
        var rows = scope === 'us' ? (agg.map_states || agg.top_states || []) : (agg.map_countries || agg.top_countries || []);
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
    var MAP_BLUE = 'rgba(47,111,208,0.52)', MAP_BLUE_LINE = 'rgba(28,92,171,0.95)';
    var MAP_RED = 'rgba(208,67,26,0.85)', MAP_RED_LINE = 'rgba(150,38,10,0.95)';
    var MAP_LAND = '#eef1f5', MAP_LAND_LINE = '#d3d8e0';

    function prefersReducedMotion() {
        try { return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
        catch (e) { return false; }
    }
    function mapTipHtml(b) {
        var pct = Math.round((b.jobs ? b.ai / b.jobs : 0) * 100);
        return '<b>' + escapeHtml(b.label) + '</b><br>' + fmt(b.jobs) + ' job cuts'
            + ' &middot; ' + fmt(b.ai) + ' AI-linked (' + pct + '%)';
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
                ? fmt(mappedJobs) + ' job cuts mapped across ' + points.length + ' ' + place
                    + ' · ' + fmt(mappedAi) + ' AI-linked · ' + fmt(viewTotal) + ' total in this view'
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
            pts.forEach(function (p) { p.r = rOf(p.jobs); p.ra = rOf(p.ai); });

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
                .style('background', '#fff')
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

            // Tooltip (HTML overlay; transient, so left out of the PNG).
            var tip = d3.select(box).append('div').attr('class', 'alt-map-tip').style('display', 'none');

            function showTip(event, p) {
                var m = d3.pointer(event, box);
                tip.html(mapTipHtml(p)).style('display', 'block');
                var tw = tip.node().offsetWidth, th = tip.node().offsetHeight;
                var lx = Math.min(Math.max(6, m[0] + 14), w - tw - 6);
                var ly = Math.max(6, m[1] - th - 12);
                tip.style('left', lx + 'px').style('top', ly + 'px');
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
                    if (scope === 'us') writeControl('alt-f-state', [p.label]);
                    else writeControl('alt-f-country', [p.label]);
                    if (typeof refreshAll === 'function') refreshAll();
                });
            node.append('circle').attr('class', 'b-all')
                .attr('r', function (p) { return p.r; })
                .attr('fill', MAP_BLUE).attr('stroke', MAP_BLUE_LINE).attr('stroke-width', 0.8);
            node.filter(function (p) { return p.ra > 0; }).append('circle').attr('class', 'b-ai')
                .attr('r', function (p) { return p.ra; })
                .attr('fill', MAP_RED).attr('stroke', MAP_RED_LINE).attr('stroke-width', 0.8)
                .style('pointer-events', 'none');

            // Value labels for the largest few (de-cluttered: top 5).
            var labelPts = pts.slice().sort(function (a, b) { return b.jobs - a.jobs; }).slice(0, 5);
            var label = gOverlay.selectAll('text.alt-map-lab').data(labelPts).join('text')
                .attr('class', 'alt-map-lab')
                .attr('text-anchor', 'middle')
                .attr('font-size', 11).attr('font-weight', 700)
                .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif')
                .attr('fill', '#0b0b0b').attr('stroke', '#fff').attr('stroke-width', 3)
                .attr('paint-order', 'stroke').style('pointer-events', 'none')
                .text(function (p) { return fmt(p.jobs); });

            // In-SVG legend (captured by the PNG export).
            drawMapLegend(svg, w, h);

            // Zoom / pan (1x–8x). Base shapes ride the transform; bubbles and
            // labels are re-placed at constant screen size so clustered points
            // separate as you zoom instead of ballooning.
            function reposition(t) {
                gMap.attr('transform', t.toString());
                node.attr('transform', function (p) { var s = t.apply([p.x0, p.y0]); return 'translate(' + s[0] + ',' + s[1] + ')'; });
                label.attr('transform', function (p) { var s = t.apply([p.x0, p.y0]); return 'translate(' + s[0] + ',' + (s[1] - p.r - 5) + ')'; });
            }
            var zoom = d3.zoom().scaleExtent([1, 8])
                .on('zoom', function (event) {
                    AIMAP.transform = event.transform;
                    AIMAP.transformScope = scope;
                    reposition(event.transform);
                    svg.style('cursor', event.transform.k > 1 ? 'grab' : 'default');
                });
            svg.call(zoom);

            function zoomToFeature(feature) {
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

    function drawMapLegend(svg, w, h) {
        var g = svg.append('g').attr('class', 'alt-map-legend').attr('transform', 'translate(14,' + (h - 62) + ')');
        g.append('rect').attr('x', -8).attr('y', -14).attr('width', 176).attr('height', 66).attr('rx', 7)
            .attr('fill', 'rgba(255,255,255,0.9)').attr('stroke', MAP_LAND_LINE).attr('stroke-width', 1);
        var row = function (y, color, line, txt) {
            g.append('circle').attr('cx', 4).attr('cy', y).attr('r', 6).attr('fill', color).attr('stroke', line).attr('stroke-width', 1);
            g.append('text').attr('x', 18).attr('y', y + 4).attr('font-size', 11.5)
                .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif').attr('fill', '#4a4d55').text(txt);
        };
        row(2, MAP_BLUE, MAP_BLUE_LINE, 'All job cuts');
        row(22, MAP_RED, MAP_RED_LINE, 'AI-linked cuts');
        g.append('text').attr('x', -4).attr('y', 46).attr('font-size', 10.5)
            .attr('font-family', 'system-ui,-apple-system,"Segoe UI",sans-serif').attr('fill', '#898781')
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
            ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, c.width, c.height);
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
                renderBar('alt-chart-ai-industries', indEntries, null, null, 'Layoffs: ');
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
                rows += row('Today', b(fmt(tdJ)) + ' workers · ' + b(fmt(tdE)) + ' verified layoff' + (tdE === 1 ? '' : 's') + largest(((r[4] || {}).leaders || [])[0]),
                    'data-from="' + iso(now) + '" data-to="' + iso(now) + '"');
            }
            rows += row('This week', wJ > 0
                ? b(fmt(wJ)) + ' workers · ' + b(fmt(wE)) + ' verified layoff' + (wE === 1 ? '' : 's') + largest(wLead) + weekDelta
                : 'no verified job cuts reported yet',
                'data-from="' + iso(d7) + '" data-to="' + iso(now) + '"');
            var mJ = m.jobs || 0, mE = m.entries || 0;
            rows += row('This month', mJ > 0
                ? b(fmt(mJ)) + ' workers · ' + b(fmt(mE)) + ' verified layoff' + (mE === 1 ? '' : 's') + largest(mLead)
                : 'no verified job cuts reported yet',
                'data-from="' + y + '-' + pad2(now.getMonth() + 1) + '-01" data-to="' + iso(now) + '"');
            // Most-affected roles appear only when the sources behind at least
            // 20% of this scope's jobs name the teams cut — below that the
            // sample is too thin to headline.
            var rolesFrag = '';
            var yRoles = r[0].top_roles || [];
            if (tJ > 0 && ((t.roles_known_jobs || 0) / tJ) >= 0.2 && yRoles.length >= 2) {
                rolesFrag = ' · roles hit hardest (where stated): ' + b(esc(yRoles[0][0])) + ' and ' + b(esc(yRoles[1][0]));
            }
            rows += row(y + ' so far', tJ > 0
                ? b(fmt(tJ)) + ' workers · ' + b(fmt(tV)) + ' verified layoff' + (tV === 1 ? '' : 's') +
                  ' (about ' + fmt(Math.round(tJ / daysElapsed)) + ' workers a day)' +
                  (tAI ? ' · explicitly blamed on AI: ' + b(fmt(tAI)) : '') + rolesFrag + largest(yLead)
                : 'no verified job cuts yet' + (ACTIVE_TAB !== 'world'
                    ? ' · coverage for this region is still filling in; pick "All time" in the Years filter for earlier layoffs' : ''),
                'data-years="' + y + '"');
            // Post-sized rewrite for the copy button: X counts any URL as 23
            // characters, and the weekly detail degrades in steps (full → no
            // delta → no largest event) to stay under 280.
            var LINK = 'asktherecruiter.com/blog/ai-layoff-tracker/';
            var xLen = function (s2) { return s2.replace(LINK, 'xxxxxxxxxxxxxxxxxxxxxxx').length; };
            var lead = 'AI layoffs, ' + today + ': ' + fmt(tJ) + ' workers across ' + fmt(tV) + ' verified layoff' + (tV === 1 ? '' : 's') +
                ' ' + tab.label + ' in ' + y + (tAI ? ', ' + fmt(tAI) + ' explicitly blamed on AI' : '') + '.';
            var tail = ' Live tracker (AskTheRecruiter.com): ' + LINK + ' #Layoffs #AI';
            var post = lead + tail;
            if (wJ > 0) {
                var wkBare = ' This week: ' + fmt(wJ) + ' workers across ' + fmt(wE) + ' layoff' + (wE === 1 ? '' : 's') + '.';
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
    // Charts the frame-safe embed route (?alt_chart_embed) can render.
    var EMBED_OK = { 'alt-chart-weekly':1, 'alt-chart-ai-share-trend':1, 'alt-chart-ai-cumulative':1, 'alt-chart-yoy':1, 'alt-chart-reasons':1, 'alt-chart-aimap':1, 'alt-bars-industries':1, 'alt-bars-states':1, 'alt-bars-countries':1, 'alt-bars-roles':1 };
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
            sh.type = 'button'; sh.className = 'alt-chart-share'; sh.title = 'Copy a link to this filtered view';
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
                return h2c(card, { backgroundColor: '#ffffff', scale: 2, useCORS: true, logging: false });
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

    $(function () {
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
                copyText(q.textContent.replace(/[“”"]/g, '').trim(), function () {
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

        var needsData = document.getElementById('alt-table') || document.getElementById('alt-stats-bar')
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
