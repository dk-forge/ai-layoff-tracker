/* Labour-market context charts ([alt_labour_context], includes/labour-context.php).
 *
 * Reads the public /reference/<source> documents and draws the Chart.js
 * charts (JOLTS, CPS, OECD, FRED, QWI, and the early-warning timeline, whose
 * data the server embeds in data-ew). Colours come from the same --alt-* custom properties layoffs.css
 * defines (read at draw time), and every chart is rebuilt on alt:themechange,
 * so light and dark both work the way the dashboard charts do.
 *
 * Official aggregate statistics only: nothing here touches tracker counts.
 */
(function () {
    'use strict';
    var root = document.getElementById('labour-context');
    if (!root || typeof window.Chart === 'undefined') return;
    var api = root.getAttribute('data-api') || '';
    var status = root.querySelector('.alt-lc-status');
    var PALETTE = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9'];
    var DOCS = {}, CHARTS = {};

    function tok(name, fb) {
        var v = getComputedStyle(document.documentElement).getPropertyValue('--alt-' + name);
        return (v && v.trim()) || fb;
    }
    function el(id) { return document.getElementById(id); }

    function lineChart(id, labels, sets, unit) {
        var canvas = el(id);
        if (!canvas) return;
        var ink = tok('chart-ink-2', '#52514e'), grid = tok('chart-grid', '#e1e0d9');
        if (CHARTS[id]) CHARTS[id].destroy();
        CHARTS[id] = new window.Chart(canvas, {
            type: 'line',
            data: { labels: labels, datasets: sets.map(function (s, i) {
                var c = s.color || PALETTE[i % PALETTE.length];
                return { label: s.label, data: s.data, borderColor: c, backgroundColor: c,
                         borderWidth: s.dash ? 1.5 : 2, borderDash: s.dash ? [5, 4] : [],
                         pointRadius: 0, pointHitRadius: 6, spanGaps: true, tension: 0.2 };
            }) },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: true, position: 'bottom', labels: { color: ink, boxWidth: 12, usePointStyle: true } },
                    tooltip: { callbacks: { label: function (ctx) {
                        var v = ctx.parsed.y;
                        return ctx.dataset.label + ': ' + (v == null ? 'n/a' : v.toLocaleString() + unit);
                    } } }
                },
                scales: {
                    x: { ticks: { color: ink, maxTicksLimit: 6, maxRotation: 0 }, grid: { display: false } },
                    y: { ticks: { color: ink }, grid: { color: grid } }
                }
            }
        });
        var desc = sets.map(function (s) {
            var last = null;
            for (var i = s.data.length - 1; i >= 0; i--) { if (s.data[i] != null) { last = s.data[i]; break; } }
            return s.label + (last == null ? '' : ' latest ' + last.toLocaleString() + unit);
        }).join('; ');
        canvas.setAttribute('aria-label', desc);
        canvas.textContent = desc;
    }

    function align(seriesList) {
        var months = {};
        seriesList.forEach(function (pts) { (pts || []).forEach(function (p) { months[p[0]] = 1; }); });
        var labels = Object.keys(months).sort();
        return { labels: labels, data: seriesList.map(function (pts) {
            var m = {};
            (pts || []).forEach(function (p) { m[p[0]] = p[1]; });
            return labels.map(function (l) { return l in m ? m[l] : null; });
        }) };
    }

    function series(doc, ds, test) {
        var out = [], all = (doc.datasets || {})[ds] || {};
        Object.keys(all).forEach(function (sid) { if (test(all[sid])) out.push(all[sid]); });
        return out;
    }

    function drawJolts() {
        var doc = DOCS.bls, sel = el('alt-lc-jolts-ind');
        if (!doc || !sel) return;
        var names = { layoffs_discharges: 'Layoffs and discharges', openings: 'Job openings', quits: 'Quits' };
        var order = ['layoffs_discharges', 'openings', 'quits'], picked = [];
        order.forEach(function (m) {
            var s = series(doc, 'jolts', function (x) { return x.dim === 'industry' && x.label === sel.value && x.measure === m; })[0];
            if (s) picked.push({ label: names[m], points: s.points });
        });
        var a = align(picked.map(function (p) { return p.points; }));
        lineChart('alt-lc-jolts', a.labels, picked.map(function (p, i) {
            return { label: p.label, data: a.data[i].map(function (v) { return v == null ? null : v * 1000; }) };
        }), '');
    }

    function drawCps() {
        var doc = DOCS.bls, sel = el('alt-lc-cps-dim');
        if (!doc || !sel) return;
        var groups = series(doc, 'cps', function (x) { return x.dim === sel.value; }).slice(0, 6);
        var total = series(doc, 'cps', function (x) { return x.dim === 'total'; })[0];
        var all = groups.slice();
        if (total) all.push(total);
        var a = align(all.map(function (s) { return s.points; }));
        lineChart('alt-lc-cps', a.labels, all.map(function (s, i) {
            var isTotal = total && s === total;
            return { label: isTotal ? 'Everyone 16 and over' : s.label, data: a.data[i],
                     dash: isTotal, color: isTotal ? tok('chart-muted', '#6e6c67') : null };
        }), '%');
    }

    function drawOecd() {
        var doc = DOCS.oecd, csel = el('alt-lc-oecd-country');
        if (!doc || !csel) return;
        var key = el('alt-lc-oecd-sex').value + '|' + el('alt-lc-oecd-age').value;
        var monthly = (doc.datasets || {}).monthly || {}, picked = [];
        Array.prototype.forEach.call(csel.options, function (o) {
            if (o.selected && picked.length < 6 && monthly[o.value] && monthly[o.value][key]) {
                picked.push({ label: o.textContent, points: monthly[o.value][key] });
            }
        });
        var a = align(picked.map(function (p) { return p.points; }));
        lineChart('alt-lc-oecd', a.labels, picked.map(function (p, i) { return { label: p.label, data: a.data[i] }; }), '%');
        if (status) status.textContent = picked.length ? '' : 'No published OECD figure for that combination.';
    }

    /* ---- FRED trend, Census QWI, early warning (2.20.227). Series colours
       are read from --alt-* tokens at draw time, so dark mode follows. ---- */
    var TOKS = ['blue', 'red', 'accent', 'ochre', 'chart-muted', 'gold'];
    function tc(i) { return tok(TOKS[i % TOKS.length], PALETTE[i % PALETTE.length]); }
    function chart(id, cfg, desc) {
        var canvas = el(id);
        if (!canvas) return;
        if (CHARTS[id]) CHARTS[id].destroy();
        CHARTS[id] = new window.Chart(canvas, cfg);
        canvas.setAttribute('aria-label', desc);
        canvas.textContent = desc;
    }
    function axes(ink, grid, horizontal) {
        var cat = { ticks: { color: ink, maxTicksLimit: 6, maxRotation: 0, autoSkip: !horizontal }, grid: { display: false } };
        var val = { ticks: { color: ink }, grid: { color: grid } };
        return horizontal ? { x: val, y: cat } : { x: cat, y: val };
    }
    function legend(ink) { return { display: true, position: 'bottom', labels: { color: ink, boxWidth: 12, usePointStyle: true } }; }
    function fmt(v) { return v == null ? 'n/a' : Number(v).toLocaleString(); }

    var FRED = {};
    function drawFred() {
        var sel = el('alt-lc-fred-series');
        if (!sel) return;
        var sid = sel.value, doc = FRED[sid];
        if (!doc) {
            fetch(api + 'fred_labour?series_id=' + encodeURIComponent(sid), { credentials: 'omit' })
                .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
                .then(function (d) { FRED[sid] = d; if (sel.value === sid) drawFred(); })
                .catch(function () { if (status) status.textContent = 'Some official figures could not be loaded. Try again later.'; });
            return;
        }
        var rows = ((doc.datasets || {}).observations || []).filter(function (r) { return r[0] === sid; });
        var meta = (doc.series || {})[sid] || {};
        var unit = meta.units === 'percent' ? '%' : '';
        var label = (meta.label || sid) + (meta.units && meta.units !== 'percent' && meta.units !== 'number' ? ' (' + meta.units + ')' : '');
        var ink = tok('chart-ink-2', '#52514e'), grid = tok('chart-grid', '#e1e0d9');
        var last = rows.length ? rows[rows.length - 1] : null;
        chart('alt-lc-fred', {
            type: 'line',
            data: { labels: rows.map(function (r) { return r[1]; }), datasets: [{
                label: label, data: rows.map(function (r) { return r[2]; }), borderColor: tc(0), backgroundColor: tc(0),
                borderWidth: 2, pointRadius: 0, pointHitRadius: 6, tension: 0.2 }] },
            options: { responsive: true, maintainAspectRatio: false, animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { legend: legend(ink), tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + fmt(c.parsed.y) + unit; } } } },
                scales: axes(ink, grid, false) }
        }, label + (last ? ', latest ' + fmt(last[2]) + unit + ' for ' + last[1] : ''));
    }

    var QWI = null, QWI_CACHE = {};
    function qwiData() {
        if (QWI) return QWI;
        var fig = root.querySelector('[data-lc="qwi"]');
        try { QWI = JSON.parse(fig ? fig.getAttribute('data-qwi') : '') || null; } catch (e) { QWI = null; }
        return QWI;
    }
    function qwiQuery(q, then) {
        if (QWI_CACHE[q]) { then(QWI_CACHE[q]); return; }
        fetch(api + 'census_qwi?' + q, { credentials: 'omit' })
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (d) { QWI_CACHE[q] = d; then(d); })
            .catch(function () { if (status) status.textContent = 'Some official figures could not be loaded. Try again later.'; });
    }
    function qwiLines(quarters, hires, seps, title) {
        var ink = tok('chart-ink-2', '#52514e'), grid = tok('chart-grid', '#e1e0d9');
        var n = quarters.length - 1;
        chart('alt-lc-qwi', {
            type: 'line',
            data: { labels: quarters, datasets: [
                { label: 'Stable hires', data: hires, borderColor: tc(0), backgroundColor: tc(0), borderWidth: 2, pointRadius: 3, tension: 0.2 },
                { label: 'Separations (all causes)', data: seps, borderColor: tc(1), backgroundColor: tc(1), borderWidth: 2, borderDash: [5, 4], pointRadius: 3, tension: 0.2 }
            ] },
            options: { responsive: true, maintainAspectRatio: false, animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { legend: legend(ink), tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + fmt(c.parsed.y); } } } },
                scales: axes(ink, grid, false) }
        }, title + (n >= 0 ? ': ' + quarters[n] + ' stable hires ' + fmt(hires[n]) + ', separations ' + fmt(seps[n]) : ''));
    }
    function drawQwi() {
        var d = qwiData(), ssel = el('alt-lc-qwi-state'), isel = el('alt-lc-qwi-ind'), split = el('alt-lc-qwi-split');
        if (!d || !ssel || !isel) return;
        var st = ssel.value, ind = isel.value, sp = split ? split.value : '';
        isel.disabled = !!sp;
        if (sp) { drawQwiSplit(d, st, sp); return; }
        if (!st) {
            var qs = Object.keys(d.national || {}).sort(), h = [], s = [];
            qs.forEach(function (q) {
                var row = d.national[q], th = 0, ts = 0;
                Object.keys(row).forEach(function (k) { if (!ind || k === ind) { th += row[k][0]; ts += row[k][1]; } });
                h.push(th); s.push(ts);
            });
            qwiLines(qs, h, s, 'All states');
            return;
        }
        qwiQuery('breakdown=by_sector&state=' + encodeURIComponent(st) + (ind ? '&industry=' + encodeURIComponent(ind) : ''), function (doc) {
            var by = {};
            ((doc.datasets || {}).by_sector || []).forEach(function (r) {
                if (!by[r[2]]) by[r[2]] = [0, 0];
                by[r[2]][0] += r[9] || 0; by[r[2]][1] += r[10] || 0;
            });
            var qs = Object.keys(by).sort();
            qwiLines(qs, qs.map(function (q) { return by[q][0]; }), qs.map(function (q) { return by[q][1]; }), ssel.options[ssel.selectedIndex].text);
        });
    }
    var QWI_COL = { sex: 4, agegrp: 5, education: 6, race: 7, ethnicity: 8 };
    var QWI_ALL = { sex: '0', agegrp: 'A00', education: 'E0', race: 'A0', ethnicity: 'A0' };
    function drawQwiSplit(d, st, sp) {
        var q = 'breakdown=' + sp + (d.latest ? '&quarter=' + encodeURIComponent(d.latest) : '') + (st ? '&state=' + encodeURIComponent(st) : '');
        qwiQuery(q, function (doc) {
            var col = QWI_COL[sp], names = (d.codes || {})[sp] || {}, by = {};
            ((doc.datasets || {})[sp] || []).forEach(function (r) {
                var g = r[col];
                if (g === QWI_ALL[sp]) return;
                if (!by[g]) by[g] = [0, 0];
                by[g][0] += r[9] || 0; by[g][1] += r[10] || 0;
            });
            var groups = Object.keys(by).sort();
            var ink = tok('chart-ink-2', '#52514e'), grid = tok('chart-grid', '#e1e0d9');
            var labels = groups.map(function (g) { return names[g] || g; });
            chart('alt-lc-qwi', {
                type: 'bar',
                data: { labels: labels, datasets: [
                    { label: 'Stable hires', data: groups.map(function (g) { return by[g][0]; }), backgroundColor: tc(0) },
                    { label: 'Separations (all causes)', data: groups.map(function (g) { return by[g][1]; }), backgroundColor: tc(1) }
                ] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
                    plugins: { legend: legend(ink), tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + fmt(c.parsed.x); } } } },
                    scales: axes(ink, grid, true) }
            }, (d.latest || '') + ' by group: ' + groups.map(function (g, i) {
                return labels[i] + ' hires ' + fmt(by[g][0]) + ', separations ' + fmt(by[g][1]);
            }).join('; '));
            if (status) status.textContent = groups.length ? '' : 'No published QWI figure for that combination.';
        });
    }

    var EW = null;
    function drawEw() {
        var box = el('early-warning'), sel = el('alt-ew-ind');
        if (!box || !sel) return;
        if (!EW) { try { EW = JSON.parse(box.getAttribute('data-ew')); } catch (e) { return; } }
        var ind = (EW.industries || {})[sel.value];
        if (!ind) return;
        var badge = box.querySelector('.alt-ew-badge'), why = box.querySelector('.alt-ew-why');
        if (badge) { badge.setAttribute('data-status', ind.status || ''); badge.textContent = ind.status ? ind.status_label : 'Not enough official data to judge'; }
        if (why) why.textContent = (ind.reasons || []).join('; ');
        var ink = tok('chart-ink-2', '#52514e'), grid = tok('chart-grid', '#e1e0d9'), oi = 0;
        var sets = ind.series.map(function (s) {
            var tracker = s.kind === 'tracker', c = tracker ? tok('chart-ink', '#0b0b0b') : tc([0, 2, 3][oi++ % 3]);
            return { label: s.name, data: s.index, raw: s.raw, borderColor: c, backgroundColor: c,
                     borderWidth: tracker ? 3 : 2, borderDash: tracker ? [] : (s.name.indexOf('QWI') === 0 ? [5, 4] : []),
                     pointRadius: s.name.indexOf('QWI') === 0 ? 3 : 0, pointHitRadius: 6, spanGaps: true, tension: 0.2 };
        });
        chart('alt-lc-ew', {
            type: 'line',
            data: { labels: EW.months, datasets: sets },
            options: { responsive: true, maintainAspectRatio: false, animation: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { legend: legend(ink), tooltip: { callbacks: { label: function (c) {
                    var raw = c.dataset.raw[c.dataIndex];
                    return c.dataset.label + ': ' + fmt(raw) + ' (index ' + fmt(c.parsed.y) + ')';
                } } } },
                scales: axes(ink, grid, false) }
        }, ind.label + ': ' + (ind.status ? ind.status_label : 'not enough official data') + '. ' + (ind.reasons || []).join('; '));
    }

    function drawAll() { try { drawJolts(); drawCps(); drawOecd(); drawFred(); drawQwi(); drawEw(); } catch (e) { } }

    function load(key, source, then) {
        fetch(api + source, { credentials: 'omit' })
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (d) { DOCS[key] = d; then(); })
            .catch(function () { if (status) status.textContent = 'Some official figures could not be loaded. Try again later.'; });
    }

    [['alt-lc-jolts-ind', drawJolts], ['alt-lc-cps-dim', drawCps], ['alt-lc-oecd-country', drawOecd],
     ['alt-lc-oecd-sex', drawOecd], ['alt-lc-oecd-age', drawOecd], ['alt-lc-fred-series', drawFred],
     ['alt-lc-qwi-state', drawQwi], ['alt-lc-qwi-ind', drawQwi], ['alt-lc-qwi-split', drawQwi],
     ['alt-ew-ind', drawEw]].forEach(function (b) {
        var s = el(b[0]);
        if (s) s.addEventListener('change', b[1]);
    });
    if (el('alt-lc-jolts') || el('alt-lc-cps')) load('bls', 'bls_jolts_cps', function () { drawJolts(); drawCps(); });
    if (el('alt-lc-oecd')) load('oecd', 'oecd_unemployment', drawOecd);
    try { drawFred(); drawQwi(); drawEw(); } catch (e) { }
    document.addEventListener('alt:themechange', drawAll);
})();
