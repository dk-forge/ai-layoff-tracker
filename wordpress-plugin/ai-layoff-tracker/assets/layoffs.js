/**
 * AI Layoff Tracker — front-end.
 * DataTables table + filters, Chart.js dashboards, AI displacement view.
 *
 * Data flow: PHP passes endpoint URLs via wp_localize_script (window.altData);
 * everything else is fetched live from the public REST API so charts update
 * automatically on every page load.
 */
(function ($) {
    'use strict';

    if (typeof window.altData === 'undefined') {
        return; // script enqueued without localized data — nothing to do
    }

    var API = window.altData.apiUrl; // ends with .../layoffs/v1/ (or ?rest_route= form)

    /* ------------------------------------------------------------------ */
    /* Palette (validated categorical set) + labels                        */
    /* ------------------------------------------------------------------ */

    var PALETTE = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834'];
    var SEQ_BLUE = '#2a78d6';
    var SEQ_BLUE_FILL = 'rgba(42, 120, 214, 0.18)';
    var INK = { primary: '#0b0b0b', secondary: '#52514e', muted: '#898781', grid: '#e1e0d9' };

    var REASON_LABELS = {
        ai_automation: 'AI / automation',
        possible_ai: 'Possible AI',
        revenue_decline: 'Revenue decline',
        restructuring: 'Restructuring',
        merger_acquisition: 'Merger / acquisition',
        offshoring: 'Offshoring',
        product_discontinuation: 'Product discontinued',
        cost_reduction: 'Cost reduction',
        macroeconomic: 'Macroeconomic'
    };

    var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    /* ------------------------------------------------------------------ */
    /* Helpers                                                             */
    /* ------------------------------------------------------------------ */

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function fmt(n) {
        return Number(n || 0).toLocaleString('en-US');
    }

    // Only render http(s) links — a manually edited source_url meta could
    // otherwise smuggle a javascript: URI past attribute escaping
    function safeUrl(url) {
        url = String(url == null ? '' : url).trim();
        return /^https?:\/\//i.test(url) ? url : '';
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function setStatus(id, text, isError) {
        var el = document.getElementById(id);
        if (!el) return;
        if (text === null) {
            el.style.display = 'none';
            return;
        }
        el.style.display = '';
        el.textContent = text;
        el.classList.toggle('alt-status-error', !!isError);
    }

    function isValidDate(s) {
        return typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s);
    }

    function monthKey(dateStr) {
        return dateStr.slice(0, 7); // YYYY-MM
    }

    function monthLabel(key) {
        var parts = key.split('-');
        return MONTHS[parseInt(parts[1], 10) - 1] + ' ' + parts[0];
    }

    function chartsAvailable() {
        return typeof window.Chart !== 'undefined';
    }

    /* Chart instance registry so charts can be re-rendered (destroyed + rebuilt)
       when cross-filters change — Chart.js throws if you reuse a live canvas. */
    var CHARTS = {};
    function mountChart(canvasId, config) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        if (CHARTS[canvasId]) { CHARTS[canvasId].destroy(); delete CHARTS[canvasId]; }
        CHARTS[canvasId] = new Chart(canvas, config);
        return CHARTS[canvasId];
    }

    /* Shared state for cross-filtering: chart click ⇄ table ⇄ other charts. */
    var ALL_ROWS = [];
    var TABLE = null;
    var DASH_PRESENT = false;

    var baseChartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: '#0b0b0b',
                titleColor: '#ffffff',
                bodyColor: '#e1e0d9',
                padding: 10,
                displayColors: false
            }
        },
        scales: {
            x: { grid: { display: false }, ticks: { color: INK.muted, maxRotation: 0, autoSkip: true } },
            y: {
                beginAtZero: true,
                grid: { color: INK.grid },
                ticks: {
                    color: INK.muted,
                    callback: function (v) { return fmt(v); }
                }
            }
        }
    };

    function cloneOptions() {
        // JSON round-trip drops functions — re-attach the tick formatter
        var options = JSON.parse(JSON.stringify(baseChartOptions));
        options.scales.y.ticks.callback = function (v) { return fmt(v); };
        return options;
    }

    function jobsTooltip(prefix) {
        return {
            callbacks: {
                label: function (ctx) {
                    var v = ctx.parsed.y !== undefined && ctx.parsed.y !== null ? ctx.parsed.y : ctx.parsed.x;
                    if (ctx.parsed && typeof ctx.parsed === 'number') v = ctx.parsed;
                    return (prefix || 'Jobs: ') + fmt(v);
                }
            }
        };
    }

    /* ------------------------------------------------------------------ */
    /* Data fetching (one shared request per page)                         */
    /* ------------------------------------------------------------------ */

    var dataPromise = null;

    function fetchAll() {
        if (!dataPromise) {
            dataPromise = fetch(API + 'all', { credentials: 'same-origin' })
                .then(function (resp) {
                    if (!resp.ok) throw new Error('API responded with HTTP ' + resp.status);
                    return resp.json();
                })
                .then(function (payload) {
                    if (!payload || !Array.isArray(payload.data)) {
                        throw new Error('Unexpected API response shape');
                    }
                    return payload.data;
                });
        }
        return dataPromise;
    }

    /* ------------------------------------------------------------------ */
    /* Aggregation                                                         */
    /* ------------------------------------------------------------------ */

    function aggregate(rows, keyFn, valueFn) {
        var out = {};
        rows.forEach(function (row) {
            var key = keyFn(row);
            if (key === null) return;
            out[key] = (out[key] || 0) + valueFn(row);
        });
        return out;
    }

    function topEntries(obj, n) {
        return Object.keys(obj)
            .map(function (k) { return [k, obj[k]]; })
            .sort(function (a, b) { return b[1] - a[1]; })
            .slice(0, n);
    }

    // Give each bar its own color so category charts read as a spectrum,
    // not a wall of one blue.
    function paletteFor(entries) {
        return entries.map(function (_, i) { return PALETTE[i % PALETTE.length]; });
    }

    /* ------------------------------------------------------------------ */
    /* Stats bar                                                           */
    /* ------------------------------------------------------------------ */

    // "Updated" timestamp is global (not filter-dependent), so fetch it once and
    // show it with the time + Eastern time zone.
    function initStatsMeta() {
        if (!document.getElementById('alt-last-updated')) return;
        fetch(API + 'stats', { credentials: 'same-origin' })
            .then(function (resp) { return resp.ok ? resp.json() : null; })
            .then(function (stats) {
                if (!stats || !stats.last_updated) return;
                var lu = new Date(stats.last_updated);
                if (isNaN(lu.getTime())) return;
                var when = lu.toLocaleString('en-US', {
                    timeZone: 'America/New_York',
                    month: 'short', day: 'numeric', year: 'numeric',
                    hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
                });
                setText('alt-last-updated', 'Updated ' + when);
            })
            .catch(function () { /* leave blank */ });
    }

    function computeStats(rows) {
        var jobs = 0, aiJobs = 0, aiEntries = 0, comp = {}, ind = {}, ctry = {};
        rows.forEach(function (r) {
            jobs += r.job_count || 0;
            if (r.ai_explicit) { aiJobs += r.job_count || 0; aiEntries += 1; }
            if (r.company_name) comp[String(r.company_name).toLowerCase()] = 1;
            if (r.industry) ind[r.industry] = 1;
            if (r.country) ctry[r.country] = 1;
        });
        return {
            jobs: jobs, entries: rows.length, aiJobs: aiJobs, aiEntries: aiEntries,
            companies: Object.keys(comp).length,
            industries: Object.keys(ind).length,
            countries: Object.keys(ctry).length
        };
    }

    // Headline numbers reflect the active filters / selected period.
    function renderStats() {
        if (!document.getElementById('alt-stats-bar')) return;
        var rows = ALL_ROWS.filter(function (r) { return rowPassesFilters(r); });
        var s = computeStats(rows);
        var period = currentPeriodLabel();
        setText('alt-stat-total', fmt(s.jobs));
        setText('alt-stat-total-entries', fmt(s.entries) + ' events · ' + period);
        setText('alt-stat-ai', fmt(s.aiJobs));
        setText('alt-stat-ai-entries', fmt(s.aiEntries) + ' events');
        setText('alt-stat-companies', fmt(s.companies));
        setText('alt-stat-industries', fmt(s.industries));
        setText('alt-stat-countries', fmt(s.countries));
    }

    /* ---- Period selector (All time / year / quarter / month) ---- */
    // Drives the same From/To date filter the dropdowns use, so table, charts,
    // and headline numbers all move together.

    var PERIOD_YEAR = '';

    function daysInMonth(y, m) { return new Date(y, m, 0).getDate(); } // m is 1-12
    function pad2(n) { return (n < 10 ? '0' : '') + n; }

    function currentPeriodLabel() {
        var from = readControl('alt-f-from');
        var to = readControl('alt-f-to');
        if (!from && !to) return 'all time';
        var q = readControl('alt-period-quarter');
        var mo = readControl('alt-period-month');
        if (PERIOD_YEAR && mo) return MONTHS[parseInt(mo, 10) - 1] + ' ' + PERIOD_YEAR;
        if (PERIOD_YEAR && q) return 'Q' + q + ' ' + PERIOD_YEAR;
        if (PERIOD_YEAR && from === PERIOD_YEAR + '-01-01') return PERIOD_YEAR;
        return (from || '…') + ' to ' + (to || 'now');
    }

    function applyPeriod() {
        var year = PERIOD_YEAR;
        var q = readControl('alt-period-quarter');
        var mo = readControl('alt-period-month');
        var refine = document.getElementById('alt-period-quarter');
        // Quarter + Month only make sense within a chosen year.
        if (refine) refine.disabled = !year;
        var moEl = document.getElementById('alt-period-month');
        if (moEl) moEl.disabled = !year;

        var from = '', to = '';
        if (year) {
            var y = parseInt(year, 10);
            if (mo) {
                var m = parseInt(mo, 10);
                from = year + '-' + pad2(m) + '-01';
                to = year + '-' + pad2(m) + '-' + pad2(daysInMonth(y, m));
            } else if (q) {
                var qn = parseInt(q, 10);
                var startM = (qn - 1) * 3 + 1;
                var endM = startM + 2;
                from = year + '-' + pad2(startM) + '-01';
                to = year + '-' + pad2(endM) + '-' + pad2(daysInMonth(y, endM));
            } else {
                from = year + '-01-01';
                to = year + '-12-31';
            }
        }
        writeControl('alt-f-from', from);
        writeControl('alt-f-to', to);
        saveFilters();
        refreshAll();
    }

    function updatePeriodActiveState() {
        var host = document.getElementById('alt-period-years');
        if (!host) return;
        Array.prototype.forEach.call(host.querySelectorAll('.alt-period-btn'), function (b) {
            b.classList.toggle('alt-period-on', b.getAttribute('data-year') === PERIOD_YEAR);
        });
    }

    var periodBuilt = false;
    function initPeriodSelector() {
        var wrap = document.getElementById('alt-period');
        var host = document.getElementById('alt-period-years');
        if (!wrap || !host || periodBuilt) return;
        // Needs the From/To filter inputs to write to (the tracker page).
        if (!document.getElementById('alt-f-from')) return;
        periodBuilt = true;
        wrap.style.display = '';

        var years = {};
        ALL_ROWS.forEach(function (r) {
            if (isValidDate(r.layoff_date)) years[r.layoff_date.slice(0, 4)] = 1;
        });
        var list = Object.keys(years).sort().reverse();

        // Reconstruct current selection from restored From/To.
        var from = readControl('alt-f-from');
        PERIOD_YEAR = (from && /^\d{4}-01-01$/.test(from)) ? from.slice(0, 4)
            : (from ? from.slice(0, 4) : '');
        if (from && list.indexOf(PERIOD_YEAR) === -1) PERIOD_YEAR = '';

        var html = '<button type="button" class="alt-period-btn" data-year="">All time</button>';
        list.forEach(function (y) {
            html += '<button type="button" class="alt-period-btn" data-year="' + y + '">' + y + '</button>';
        });
        host.innerHTML = html;

        Array.prototype.forEach.call(host.querySelectorAll('.alt-period-btn'), function (btn) {
            btn.addEventListener('click', function () {
                PERIOD_YEAR = btn.getAttribute('data-year');
                if (!PERIOD_YEAR) {
                    writeControl('alt-period-quarter', '');
                    writeControl('alt-period-month', '');
                }
                applyPeriod();
                updatePeriodActiveState();
            });
        });

        var qSel = document.getElementById('alt-period-quarter');
        var mSel = document.getElementById('alt-period-month');
        if (qSel) qSel.addEventListener('change', function () { writeControl('alt-period-month', ''); applyPeriod(); });
        if (mSel) mSel.addEventListener('change', function () { writeControl('alt-period-quarter', ''); applyPeriod(); });

        qSel && (qSel.disabled = !PERIOD_YEAR);
        mSel && (mSel.disabled = !PERIOD_YEAR);
        updatePeriodActiveState();
    }

    /* ------------------------------------------------------------------ */
    /* Tracker table + filters                                             */
    /* ------------------------------------------------------------------ */

    var FILTER_STORAGE_KEY = 'altTrackerFilters:v1';
    var FILTER_IDS = ['alt-f-from', 'alt-f-to', 'alt-f-industry', 'alt-f-country',
        'alt-f-reasons', 'alt-f-verification', 'alt-f-company', 'alt-f-keyword',
        'alt-f-minjobs', 'alt-f-ai'];

    function readControl(id) {
        var el = document.getElementById(id);
        if (!el) return null;
        if (el.type === 'checkbox') return el.checked;
        if (el.multiple) {
            return Array.prototype.slice.call(el.selectedOptions).map(function (o) { return o.value; });
        }
        return el.value;
    }

    function writeControl(id, value) {
        var el = document.getElementById(id);
        if (!el || value == null) return;
        if (el.type === 'checkbox') { el.checked = !!value; return; }
        if (el.multiple && Array.isArray(value)) {
            Array.prototype.forEach.call(el.options, function (o) {
                o.selected = value.indexOf(o.value) !== -1;
            });
            return;
        }
        el.value = value;
    }

    function saveFilters() {
        try {
            var state = {};
            FILTER_IDS.forEach(function (id) { state[id] = readControl(id); });
            window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(state));
        } catch (e) { /* storage unavailable (private mode) — filters just won't persist */ }
    }

    function restoreFilters() {
        try {
            var raw = window.localStorage.getItem(FILTER_STORAGE_KEY);
            if (!raw) return;
            var state = JSON.parse(raw);
            FILTER_IDS.forEach(function (id) { writeControl(id, state[id]); });
        } catch (e) { /* corrupted state — ignore */ }
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

    // `except` lets a category chart render without filtering on its own
    // dimension (so a "slicer" bar chart still shows all categories while the
    // table and other charts narrow). Pass 'industry' | 'country' | 'reasons'.
    function rowPassesFilters(row, except) {
        if (except !== 'date') {
            var from = readControl('alt-f-from');
            var to = readControl('alt-f-to');
            if ((from || to) && !isValidDate(row.layoff_date)) return false;
            if (from && row.layoff_date < from) return false;
            if (to && row.layoff_date > to) return false;
        }

        if (except !== 'industry') {
            var industry = readControl('alt-f-industry');
            if (industry && row.industry !== industry) return false;
        }

        if (except !== 'country') {
            var country = readControl('alt-f-country');
            if (country && row.country !== country) return false;
        }

        if (except !== 'reasons') {
            var reasons = readControl('alt-f-reasons') || [];
            if (reasons.length) {
                var tags = row.reason_tags || [];
                var hit = reasons.some(function (r) { return tags.indexOf(r) !== -1; });
                if (!hit) return false;
            }
        }

        var levels = readControl('alt-f-verification') || [];
        if (levels.length && levels.indexOf(row.verification_level) === -1) return false;

        if (readControl('alt-f-ai') && !row.ai_explicit) return false;

        var company = (readControl('alt-f-company') || '').trim().toLowerCase();
        if (company && String(row.company_name).toLowerCase().indexOf(company) === -1) return false;

        var keyword = (readControl('alt-f-keyword') || '').trim().toLowerCase();
        if (keyword && String(row.excerpt).toLowerCase().indexOf(keyword) === -1) return false;

        var minJobs = parseInt(readControl('alt-f-minjobs'), 10);
        if (!isNaN(minJobs) && minJobs > 0 && row.job_count < minJobs) return false;

        return true;
    }

    /* ---- Cross-filter plumbing: chart clicks drive the same controls the
       dropdowns use, then redraw the table + re-render every chart. ---- */

    // Toggle a single-value <select> (industry / country). Clicking the active
    // value again clears it. Returns false if the control isn't on this page.
    function toggleSingleFilter(id, value) {
        var el = document.getElementById(id);
        if (!el) return false;
        el.value = (el.value === value) ? '' : value;
        return true;
    }

    // Toggle one option in a multi-select (reason tags).
    function toggleMultiFilter(id, value) {
        var el = document.getElementById(id);
        if (!el) return false;
        var toggled = false;
        Array.prototype.forEach.call(el.options, function (o) {
            if (o.value === value) { o.selected = !o.selected; toggled = true; }
        });
        return toggled;
    }

    function refreshAll() {
        if (TABLE) TABLE.draw();
        renderDashboard();
        renderStats();
        updateActiveFilterBar();
    }

    // Chip bar above the charts so clicking a chart shows *why* the data changed.
    var ACTIVE_FILTER_DEFS = [
        { id: 'alt-f-industry', label: 'Industry', kind: 'single' },
        { id: 'alt-f-country', label: 'Country', kind: 'single' },
        { id: 'alt-f-reasons', label: 'Reason', kind: 'multi', map: REASON_LABELS },
        { id: 'alt-f-verification', label: 'Source', kind: 'multi', map: { gold: 'SEC filing', silver: 'Press release', bronze: 'News' } },
        { id: 'alt-f-ai', label: '', kind: 'bool', on: 'AI-attributed only' }
    ];

    function updateActiveFilterBar() {
        var bar = document.getElementById('alt-active-filters');
        if (!bar) return;
        var chips = [];
        ACTIVE_FILTER_DEFS.forEach(function (def) {
            var val = readControl(def.id);
            if (def.kind === 'bool') {
                if (val) chips.push({ id: def.id, text: def.on, value: true, kind: 'bool' });
            } else if (def.kind === 'multi') {
                (val || []).forEach(function (v) {
                    chips.push({ id: def.id, text: def.label + ': ' + ((def.map && def.map[v]) || v), value: v, kind: 'multi' });
                });
            } else if (val) {
                chips.push({ id: def.id, text: def.label + ': ' + val, value: val, kind: 'single' });
            }
        });

        if (!chips.length) { bar.innerHTML = ''; bar.style.display = 'none'; return; }
        bar.style.display = '';
        var html = '<span class="alt-af-label">Filtering:</span>';
        chips.forEach(function (c, i) {
            html += '<button type="button" class="alt-af-chip" data-i="' + i + '">'
                + escapeHtml(c.text) + ' <span aria-hidden="true">✕</span></button>';
        });
        html += '<button type="button" class="alt-af-clear" id="alt-af-clear">Clear all</button>';
        bar.innerHTML = html;

        bar.querySelectorAll('.alt-af-chip').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var c = chips[parseInt(btn.getAttribute('data-i'), 10)];
                if (c.kind === 'bool') { var el = document.getElementById(c.id); if (el) el.checked = false; }
                else if (c.kind === 'multi') { toggleMultiFilter(c.id, c.value); }
                else { toggleSingleFilter(c.id, ''); }
                saveFilters();
                refreshAll();
            });
        });
        var clearBtn = document.getElementById('alt-af-clear');
        if (clearBtn) clearBtn.addEventListener('click', function () {
            clearFilters();
            if (TABLE) TABLE.search('');
            refreshAll();
        });
    }

    function populateFilterOptions(rows) {
        var industries = {};
        var countries = {};
        rows.forEach(function (row) {
            if (row.industry) industries[row.industry] = true;
            if (row.country) countries[row.country] = true;
        });

        function fill(id, values) {
            var el = document.getElementById(id);
            if (!el) return;
            Object.keys(values).sort().forEach(function (v) {
                var opt = document.createElement('option');
                opt.value = v;
                opt.textContent = v;
                el.appendChild(opt);
            });
        }
        fill('alt-f-industry', industries);
        fill('alt-f-country', countries);
    }

    var VERIF_LABELS = { gold: 'SEC filing', silver: 'Press release', bronze: 'News' };
    function verificationBadge(level) {
        var safe = escapeHtml(level || 'bronze');
        var label = VERIF_LABELS[level] || 'News';
        return '<span class="alt-badge alt-badge-' + safe + '">' + escapeHtml(label) + '</span>';
    }

    function initTracker(rows) {
        var tableEl = document.getElementById('alt-table');
        if (!tableEl) return;

        if (typeof $.fn.DataTable === 'undefined') {
            setStatus('alt-table-status', 'The table library failed to load (CDN blocked?). Raw data: ' + API + 'all', true);
            return;
        }

        populateFilterOptions(rows);
        restoreFilters();

        // Register the custom filter BEFORE init so the first draw honors
        // restored filter state. Scope it to our table node.
        $.fn.dataTable.ext.search.push(function (settings, searchData, index, rowData) {
            if (settings.nTable !== tableEl) return true;
            return rowPassesFilters(rowData);
        });

        var table = $(tableEl).DataTable({
            data: rows,
            stateSave: true,       // persists paging / sort / built-in search
            stateDuration: 0,      // localStorage, no expiry
            order: [[0, 'desc']],
            pageLength: 25,
            lengthMenu: [10, 25, 50, 100],
            language: {
                emptyTable: 'No layoff entries match the current filters.',
                zeroRecords: 'No layoff entries match the current filters.'
            },
            drawCallback: function () {
                var el = document.getElementById('alt-table-count');
                if (!el) return;
                var info = this.api().page.info();
                if (!info.recordsDisplay) { el.textContent = 'No entries match the current filters.'; return; }
                var base = 'Showing ' + fmt(info.start + 1) + '–' + fmt(info.end) + ' of ' + fmt(info.recordsDisplay) + ' entries';
                el.textContent = (info.recordsDisplay !== info.recordsTotal)
                    ? base + ' (filtered from ' + fmt(info.recordsTotal) + ' total)'
                    : base;
            },
            columns: [
                {
                    data: 'layoff_date',
                    render: function (data, type) {
                        if (type === 'display') return data ? escapeHtml(data) : '<span class="alt-muted">unknown</span>';
                        return data || '';
                    }
                },
                {
                    data: 'company_name',
                    render: function (data, type, row) {
                        if (type !== 'display') return data || '';
                        var html = '<strong>' + escapeHtml(data) + '</strong>';
                        if (row.ticker) html += ' <span class="alt-ticker">' + escapeHtml(row.ticker) + '</span>';
                        return html;
                    }
                },
                {
                    data: 'job_count',
                    className: 'alt-num',
                    render: function (data, type) {
                        return type === 'display' ? fmt(data) : data;
                    }
                },
                {
                    data: 'industry',
                    render: function (data, type) {
                        return type === 'display' ? escapeHtml(data || '—') : (data || '');
                    }
                },
                {
                    data: 'country',
                    render: function (data, type) {
                        return type === 'display' ? escapeHtml(data || '—') : (data || '');
                    }
                },
                {
                    data: 'reason_tags',
                    orderable: false,
                    render: function (data, type) {
                        var tags = Array.isArray(data) ? data : [];
                        if (type !== 'display') return tags.join(' ');
                        return tags.map(function (t) {
                            return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[t] || t) + '</span>';
                        }).join(' ');
                    }
                },
                {
                    data: 'verification_level',
                    render: function (data, type) {
                        return type === 'display' ? verificationBadge(data) : (data || '');
                    }
                },
                {
                    data: 'ai_explicit',
                    className: 'alt-center',
                    render: function (data, type) {
                        if (type === 'display') return data ? '<span class="alt-ai-yes" title="Explicitly AI-attributed">AI</span>' : '';
                        return data ? 1 : 0;
                    }
                },
                {
                    data: 'source_url',
                    orderable: false,
                    render: function (data, type, row) {
                        if (type !== 'display') return row.source_name || '';
                        var url = safeUrl(data);
                        if (!url) return escapeHtml(row.source_name || '—');
                        return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">'
                            + escapeHtml(row.source_name || 'source') + '</a>';
                    }
                }
            ]
        });

        TABLE = table;
        setStatus('alt-table-status', null);

        var redrawTimer = null;
        function onFilterChange() {
            saveFilters();
            clearTimeout(redrawTimer);
            redrawTimer = setTimeout(refreshAll, 150);
        }

        FILTER_IDS.forEach(function (id) {
            var el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', onFilterChange);
            if (el.type === 'text' || el.type === 'number') {
                el.addEventListener('input', onFilterChange);
            }
        });

        var reset = document.getElementById('alt-f-reset');
        if (reset) {
            reset.addEventListener('click', function () {
                clearFilters();
                table.search('');
                refreshAll();
            });
        }

        // Click/tap a row to reveal the exact quote, roles, and source link
        $(tableEl).on('click', 'tbody tr', function (e) {
            if (e.target && e.target.closest && e.target.closest('a')) return; // let real links work
            var row = table.row(this);
            if (!row.data()) return; // the "no entries" message row
            if (row.child.isShown()) {
                row.child.hide();
                $(this).removeClass('alt-row-open');
            } else {
                row.child(formatDetail(row.data())).show();
                $(this).addClass('alt-row-open');
            }
        });

        // Filters were restored from storage — apply them to the first view
        table.draw();
        updateActiveFilterBar();
    }

    function formatDetail(row) {
        var parts = [];
        if (row.ai_language) {
            parts.push('<div class="alt-detail-block alt-detail-quote"><span class="alt-detail-h">Exact AI / automation quote</span>'
                + '<blockquote>“' + escapeHtml(row.ai_language) + '”</blockquote></div>');
        }
        if (row.excerpt) {
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">From the source</span>'
                + '<p>' + escapeHtml(row.excerpt) + '</p></div>');
        }
        if (row.roles) {
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Roles affected</span>'
                + '<p>' + escapeHtml(row.roles) + '</p></div>');
        }
        var tags = (row.reason_tags || []).map(function (t) {
            return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[t] || t) + '</span>';
        }).join(' ');
        if (tags) {
            parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Reasons cited</span><div>' + tags + '</div></div>');
        }
        var url = safeUrl(row.source_url);
        var verif = row.verification_level
            ? ' · <span class="alt-badge alt-badge-' + escapeHtml(row.verification_level) + '">' + escapeHtml(VERIF_LABELS[row.verification_level] || 'News') + '</span>'
            : '';
        var src = url
            ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">View primary source (' + escapeHtml(row.source_name || 'source') + ') ↗</a>'
            : escapeHtml(row.source_name || '—');
        parts.push('<div class="alt-detail-block"><span class="alt-detail-h">Source</span><div>' + src + verif + '</div></div>');
        return '<div class="alt-detail">' + (parts.join('') || 'No additional detail recorded.') + '</div>';
    }

    /* ------------------------------------------------------------------ */
    /* Dashboard charts                                                    */
    /* ------------------------------------------------------------------ */

    function buildWeeklyChart(rows) {
        var canvas = document.getElementById('alt-chart-weekly');
        if (!canvas) return;

        var WEEK = 7 * 86400000;
        var now = new Date();
        var day = (now.getUTCDay() + 6) % 7; // days since Monday
        var thisMonday = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - day);

        var labels = [], keys = [], sums = {};
        for (var i = 51; i >= 0; i--) {
            var start = thisMonday - i * WEEK;
            keys.push(start);
            var d = new Date(start);
            labels.push(MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate());
            sums[start] = 0;
        }

        rows.forEach(function (row) {
            if (!isValidDate(row.layoff_date)) return;
            var t = Date.parse(row.layoff_date + 'T00:00:00Z');
            if (isNaN(t)) return;
            var offset = Math.floor((t - (thisMonday - 51 * WEEK)) / WEEK);
            if (offset < 0 || offset > 51) return;
            var key = thisMonday - (51 - offset) * WEEK;
            sums[key] += row.job_count;
        });

        var options = cloneOptions();
        options.plugins.tooltip = $.extend(options.plugins.tooltip, jobsTooltip('Jobs cut: '));
        mountChart('alt-chart-weekly', {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: keys.map(function (k) { return sums[k]; }),
                    borderColor: SEQ_BLUE,
                    backgroundColor: SEQ_BLUE_FILL,
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHitRadius: 12,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: options
        });
    }

    function buildBarChart(canvasId, entries, colors, horizontal, tooltipPrefix, onClick, activeValue) {
        if (!entries.length) {
            if (CHARTS[canvasId]) { CHARTS[canvasId].destroy(); delete CHARTS[canvasId]; }
            return;
        }
        // Dim the other bars when a value in this dimension is selected.
        var bg = entries.map(function (e, i) {
            var base = Array.isArray(colors) ? colors[i % colors.length] : colors;
            return (activeValue && e[0] !== activeValue) ? '#d6d8de' : base;
        });
        var options = cloneOptions();
        if (horizontal) {
            options.indexAxis = 'y';
            options.scales = {
                x: {
                    beginAtZero: true,
                    grid: { color: INK.grid },
                    ticks: { color: INK.muted, callback: function (v) { return fmt(v); } }
                },
                y: { grid: { display: false }, ticks: { color: INK.secondary, autoSkip: false } }
            };
        }
        options.plugins.tooltip = $.extend(options.plugins.tooltip, {
            callbacks: {
                label: function (ctx) {
                    var v = horizontal ? ctx.parsed.x : ctx.parsed.y;
                    return (tooltipPrefix || 'Jobs: ') + fmt(v);
                }
            }
        });
        if (onClick) {
            options.onClick = function (evt, els) {
                if (els && els.length) onClick(entries[els[0].index][0]);
            };
            options.onHover = function (evt, els) {
                if (evt.native) evt.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
            };
        }
        mountChart(canvasId, {
            type: 'bar',
            data: {
                labels: entries.map(function (e) { return e[0]; }),
                datasets: [{
                    data: entries.map(function (e) { return e[1]; }),
                    backgroundColor: bg,
                    borderRadius: 4,
                    maxBarThickness: 26
                }]
            },
            options: options
        });
    }

    function buildReasonsDonut(rows, onClick, activeValues) {
        if (!document.getElementById('alt-chart-reasons')) return;

        var sums = {};
        rows.forEach(function (row) {
            (row.reason_tags || []).forEach(function (tag) {
                sums[tag] = (sums[tag] || 0) + row.job_count;
            });
        });
        var entries = topEntries(sums, 9);
        if (!entries.length) {
            if (CHARTS['alt-chart-reasons']) { CHARTS['alt-chart-reasons'].destroy(); delete CHARTS['alt-chart-reasons']; }
            return;
        }

        var active = activeValues || [];
        var bg = entries.map(function (e, i) {
            var base = PALETTE[i % PALETTE.length];
            return (active.length && active.indexOf(e[0]) === -1) ? '#d6d8de' : base;
        });

        var options = {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '62%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: INK.secondary, boxWidth: 12, boxHeight: 12 }
                },
                tooltip: {
                    callbacks: {
                        label: function (ctx) { return ctx.label + ': ' + fmt(ctx.parsed) + ' jobs'; }
                    }
                }
            }
        };
        if (onClick) {
            options.onClick = function (evt, els) {
                if (els && els.length) onClick(entries[els[0].index][0]);
            };
            options.onHover = function (evt, els) {
                if (evt.native) evt.native.target.style.cursor = (els && els.length) ? 'pointer' : 'default';
            };
        }

        mountChart('alt-chart-reasons', {
            type: 'doughnut',
            data: {
                labels: entries.map(function (e) { return REASON_LABELS[e[0]] || e[0]; }),
                datasets: [{
                    data: entries.map(function (e) { return e[1]; }),
                    backgroundColor: bg,
                    borderColor: '#fcfcfb',
                    borderWidth: 2
                }]
            },
            options: options
        });
    }

    function buildAiCumulativeChart(rows, canvasId) {
        if (!document.getElementById(canvasId)) return;

        var aiRows = rows.filter(function (r) { return r.ai_explicit && isValidDate(r.layoff_date); });
        if (!aiRows.length) {
            if (CHARTS[canvasId]) { CHARTS[canvasId].destroy(); delete CHARTS[canvasId]; }
            return;
        }

        var byMonth = aggregate(aiRows,
            function (r) { return monthKey(r.layoff_date); },
            function (r) { return r.job_count; });
        var keys = Object.keys(byMonth).sort();

        var running = 0;
        var cumulative = keys.map(function (k) { running += byMonth[k]; return running; });

        var options = cloneOptions();
        options.plugins.tooltip = $.extend(options.plugins.tooltip, jobsTooltip('Cumulative AI-attributed: '));
        mountChart(canvasId, {
            type: 'line',
            data: {
                labels: keys.map(monthLabel),
                datasets: [{
                    data: cumulative,
                    borderColor: PALETTE[5],
                    backgroundColor: 'rgba(227, 73, 72, 0.15)',
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHitRadius: 12,
                    fill: true,
                    tension: 0.25
                }]
            },
            options: options
        });
    }

    function buildLeaderboard(rows) {
        var box = document.getElementById('alt-leaderboard');
        if (!box) return;

        var top = rows.slice().sort(function (a, b) { return b.job_count - a.job_count; }).slice(0, 10);
        if (!top.length) {
            box.innerHTML = '<p class="alt-muted alt-empty">No data yet.</p>';
            return;
        }

        var html = '<table class="alt-plain-table"><thead><tr><th>#</th><th>Company</th><th class="alt-num">Jobs</th><th>Date</th></tr></thead><tbody>';
        top.forEach(function (row, i) {
            html += '<tr>'
                + '<td class="alt-muted">' + (i + 1) + '</td>'
                + '<td>' + escapeHtml(row.company_name)
                + (row.ai_explicit ? ' <span class="alt-ai-yes" title="Explicitly AI-attributed">AI</span>' : '')
                + '</td>'
                + '<td class="alt-num">' + fmt(row.job_count) + '</td>'
                + '<td>' + escapeHtml(row.layoff_date || '—') + '</td>'
                + '</tr>';
        });
        box.innerHTML = html + '</tbody></table>';
    }

    function initDashboard() {
        if (!document.querySelector('.alt-dashboard')) return;
        DASH_PRESENT = true;
        if (!chartsAvailable()) {
            setStatus('alt-dashboard-status', 'Chart library failed to load (CDN blocked?).', true);
            return;
        }
        setStatus('alt-dashboard-status', ALL_ROWS.length ? null : 'No entries yet. The pipeline hasn’t posted data.');
        renderDashboard();
    }

    // Rebuilds every chart from ALL_ROWS honoring the active filters. Trend
    // charts + leaderboard use the fully-filtered set; each category "slicer"
    // ignores its own dimension and highlights the current selection, so
    // clicking one chart narrows the table and the *other* charts.
    function renderDashboard() {
        if (!DASH_PRESENT || !chartsAvailable()) return;

        // Only wire chart clicks where the filter controls live (the tracker page).
        var wired = !!document.getElementById('alt-f-industry');

        var full = ALL_ROWS.filter(function (r) { return rowPassesFilters(r); });
        buildWeeklyChart(full);
        buildAiCumulativeChart(full, 'alt-chart-ai-cumulative');
        buildLeaderboard(full);

        // Category "slicers": skip blank values (no giant "Unknown" bar) and
        // ignore this dimension's own filter so all categories stay visible.
        var forInd = ALL_ROWS.filter(function (r) { return rowPassesFilters(r, 'industry'); });
        var indEntries = topEntries(aggregate(forInd,
            function (r) { return r.industry || null; },
            function (r) { return r.job_count; }), 10);
        buildBarChart('alt-chart-industries', indEntries, paletteFor(indEntries), true, 'Jobs: ',
            wired ? function (v) { if (toggleSingleFilter('alt-f-industry', v)) { saveFilters(); refreshAll(); } } : null,
            readControl('alt-f-industry'));

        var forCtry = ALL_ROWS.filter(function (r) { return rowPassesFilters(r, 'country'); });
        var ctryEntries = topEntries(aggregate(forCtry,
            function (r) { return r.country || null; },
            function (r) { return r.job_count; }), 10);
        buildBarChart('alt-chart-countries', ctryEntries, paletteFor(ctryEntries), true, 'Jobs: ',
            wired ? function (v) { if (toggleSingleFilter('alt-f-country', v)) { saveFilters(); refreshAll(); } } : null,
            readControl('alt-f-country'));

        var forReasons = ALL_ROWS.filter(function (r) { return rowPassesFilters(r, 'reasons'); });
        buildReasonsDonut(forReasons,
            wired ? function (v) { if (toggleMultiFilter('alt-f-reasons', v)) { saveFilters(); refreshAll(); } } : null,
            readControl('alt-f-reasons'));
    }

    /* ------------------------------------------------------------------ */
    /* AI displacement view                                                */
    /* ------------------------------------------------------------------ */

    function initAiTracker(rows) {
        if (!document.querySelector('.alt-ai-tracker')) return;

        var aiRows = rows.filter(function (r) { return r.ai_explicit; });

        var totalJobs = aiRows.reduce(function (sum, r) { return sum + r.job_count; }, 0);
        var companies = {};
        aiRows.forEach(function (r) {
            var key = String(r.company_name).toLowerCase();
            if (!companies[key]) companies[key] = { name: r.company_name, jobs: 0, events: 0 };
            companies[key].jobs += r.job_count;
            companies[key].events += 1;
        });
        var companyList = Object.keys(companies).map(function (k) { return companies[k]; })
            .sort(function (a, b) { return b.jobs - a.jobs; });

        setText('alt-ai-hero-jobs', fmt(totalJobs));
        setText('alt-ai-hero-sub', 'across ' + fmt(aiRows.length) + ' events at ' + fmt(companyList.length) + ' companies');

        if (!aiRows.length) {
            setStatus('alt-ai-status', 'No explicitly AI-attributed layoffs recorded yet.');
            return;
        }
        if (chartsAvailable()) {
            setStatus('alt-ai-status', null);
        } else {
            setStatus('alt-ai-status', 'Chart library failed to load (CDN blocked?). Charts unavailable.', true);
        }

        if (chartsAvailable()) {
            // Monthly AI-attributed jobs (acceleration)
            var canvas = document.getElementById('alt-chart-ai-monthly');
            if (canvas) {
                var dated = aiRows.filter(function (r) { return isValidDate(r.layoff_date); });
                var byMonth = aggregate(dated,
                    function (r) { return monthKey(r.layoff_date); },
                    function (r) { return r.job_count; });
                var keys = Object.keys(byMonth).sort();
                if (keys.length) {
                    var options = cloneOptions();
                    options.plugins.tooltip = $.extend(options.plugins.tooltip, jobsTooltip('AI-attributed jobs: '));
                    new Chart(canvas, {
                        type: 'line',
                        data: {
                            labels: keys.map(monthLabel),
                            datasets: [{
                                data: keys.map(function (k) { return byMonth[k]; }),
                                borderColor: SEQ_BLUE,
                                backgroundColor: SEQ_BLUE_FILL,
                                borderWidth: 2,
                                pointRadius: 3,
                                pointBackgroundColor: SEQ_BLUE,
                                fill: true,
                                tension: 0.25
                            }]
                        },
                        options: options
                    });
                } else {
                    canvas.parentNode.innerHTML = '<p class="alt-muted alt-empty">No dated AI-attributed entries yet.</p>';
                }
            }

            // Industries citing AI most frequently (event counts)
            var byIndustry = aggregate(aiRows,
                function (r) { return r.industry || null; },
                function () { return 1; });
            var aiIndEntries = topEntries(byIndustry, 10);
            buildBarChart('alt-chart-ai-industries', aiIndEntries, paletteFor(aiIndEntries), true, 'Events: ');
        }

        initQuoteWall(aiRows);

        var chips = document.getElementById('alt-ai-companies');
        if (chips) {
            chips.innerHTML = companyList.map(function (c) {
                return '<span class="alt-chip"><strong>' + escapeHtml(c.name) + '</strong> '
                    + fmt(c.jobs) + ' jobs</span>';
            }).join('');
        }
    }

    function initQuoteWall(aiRows) {
        var textEl = document.getElementById('alt-quote-text');
        var citeEl = document.getElementById('alt-quote-cite');
        if (!textEl || !citeEl) return;

        var quotes = aiRows.filter(function (r) {
            return r.ai_language && String(r.ai_language).trim() !== '';
        });
        if (!quotes.length) {
            textEl.textContent = 'No AI language captured yet.';
            return;
        }

        var index = 0;
        function show(i) {
            var q = quotes[i];
            textEl.textContent = '“' + q.ai_language + '”';
            citeEl.textContent = q.company_name + ' · ' + (q.source_name || '') +
                (q.layoff_date ? ' · ' + q.layoff_date : '');
        }
        show(0);

        if (quotes.length > 1) {
            var wall = document.getElementById('alt-quote-wall');
            setInterval(function () {
                index = (index + 1) % quotes.length;
                if (wall) {
                    wall.classList.add('alt-quote-fading');
                    setTimeout(function () {
                        show(index);
                        wall.classList.remove('alt-quote-fading');
                    }, 300);
                } else {
                    show(index);
                }
            }, 8000);
        }
    }

    /* ------------------------------------------------------------------ */
    /* Per-company history                                                 */
    /* ------------------------------------------------------------------ */

    function initCompanyHistory(rows) {
        var wrap = document.querySelector('.alt-company-history');
        if (!wrap) return;

        var target = (wrap.getAttribute('data-company') || '').toLowerCase();
        var matches = rows.filter(function (r) {
            return String(r.company_name).toLowerCase().indexOf(target) !== -1;
        }).sort(function (a, b) { return strcmpAsc(a.layoff_date, b.layoff_date); });

        function strcmpAsc(a, b) { return a < b ? -1 : (a > b ? 1 : 0); }

        var summary = document.getElementById('alt-company-summary');
        if (!matches.length) {
            if (summary) summary.textContent = 'No recorded layoff events for this company yet.';
            return;
        }

        var totalJobs = matches.reduce(function (sum, r) { return sum + r.job_count; }, 0);
        if (summary) {
            summary.textContent = fmt(matches.length) + ' recorded events · ' + fmt(totalJobs) + ' total jobs cut';
        }

        var canvas = document.getElementById('alt-chart-company');
        if (canvas && chartsAvailable()) {
            var options = cloneOptions();
            options.plugins.tooltip = $.extend(options.plugins.tooltip, jobsTooltip());
            new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: matches.map(function (r) { return r.layoff_date || 'unknown'; }),
                    datasets: [{
                        data: matches.map(function (r) { return r.job_count; }),
                        backgroundColor: matches.map(function (r) { return r.ai_explicit ? PALETTE[5] : SEQ_BLUE; }),
                        borderRadius: 4,
                        maxBarThickness: 40
                    }]
                },
                options: options
            });
        }

        var tbody = document.querySelector('#alt-company-table tbody');
        if (tbody) {
            tbody.innerHTML = matches.slice().reverse().map(function (row) {
                var tags = (row.reason_tags || []).map(function (t) {
                    return '<span class="alt-tag">' + escapeHtml(REASON_LABELS[t] || t) + '</span>';
                }).join(' ');
                var url = safeUrl(row.source_url);
                var source = url
                    ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener nofollow">' + escapeHtml(row.source_name || 'source') + '</a>'
                    : escapeHtml(row.source_name || '—');
                return '<tr>'
                    + '<td>' + escapeHtml(row.layoff_date || '—') + '</td>'
                    + '<td class="alt-num">' + fmt(row.job_count) + '</td>'
                    + '<td>' + tags + '</td>'
                    + '<td>' + verificationBadge(row.verification_level) + '</td>'
                    + '<td>' + source + '</td>'
                    + '</tr>';
            }).join('');
        }
    }

    /* ------------------------------------------------------------------ */
    /* Boot                                                                */
    /* ------------------------------------------------------------------ */

    $(function () {
        // "Cite this tracker": fill the accessed date + wire the copy button
        var citeDate = document.getElementById('alt-cite-date');
        if (citeDate) {
            citeDate.textContent = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        }
        var citeCopy = document.getElementById('alt-cite-copy');
        if (citeCopy) {
            citeCopy.addEventListener('click', function () {
                var el = document.getElementById('alt-cite-text');
                if (el && navigator.clipboard) {
                    navigator.clipboard.writeText(el.textContent.replace(/\s+/g, ' ').trim());
                    citeCopy.textContent = 'Copied ✓';
                    setTimeout(function () { citeCopy.textContent = 'Copy'; }, 1500);
                }
            });
        }

        initStatsMeta();

        var needsData = document.getElementById('alt-table')
            || document.getElementById('alt-stats-bar')
            || document.querySelector('.alt-dashboard')
            || document.querySelector('.alt-ai-tracker')
            || document.querySelector('.alt-company-history');
        if (!needsData) return;

        if (chartsAvailable()) {
            Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
            Chart.defaults.color = INK.muted;
        }

        fetchAll()
            .then(function (rows) {
                ALL_ROWS = rows;
                initTracker(rows);
                initPeriodSelector();
                initDashboard();
                renderStats();
                initAiTracker(rows);
                initCompanyHistory(rows);
            })
            .catch(function (err) {
                var message = 'Could not load layoff data (' + err.message + ').';
                setStatus('alt-table-status', message, true);
                setStatus('alt-dashboard-status', message, true);
                setStatus('alt-ai-status', message, true);
                var summary = document.getElementById('alt-company-summary');
                if (summary) summary.textContent = message;
            });
    });
})(jQuery);
