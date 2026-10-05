/* Labour-market context charts ([alt_labour_context], includes/labour-context.php).
 *
 * Reads the public /reference/<source> documents and draws three Chart.js line
 * charts. Colours come from the same --alt-* custom properties layoffs.css
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

    function drawAll() { try { drawJolts(); drawCps(); drawOecd(); } catch (e) { } }

    function load(key, source, then) {
        fetch(api + source, { credentials: 'omit' })
            .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
            .then(function (d) { DOCS[key] = d; then(); })
            .catch(function () { if (status) status.textContent = 'Some official figures could not be loaded. Try again later.'; });
    }

    [['alt-lc-jolts-ind', drawJolts], ['alt-lc-cps-dim', drawCps], ['alt-lc-oecd-country', drawOecd],
     ['alt-lc-oecd-sex', drawOecd], ['alt-lc-oecd-age', drawOecd]].forEach(function (b) {
        var s = el(b[0]);
        if (s) s.addEventListener('change', b[1]);
    });
    if (el('alt-lc-jolts') || el('alt-lc-cps')) load('bls', 'bls_jolts_cps', function () { drawJolts(); drawCps(); });
    if (el('alt-lc-oecd')) load('oecd', 'oecd_unemployment', drawOecd);
    document.addEventListener('alt:themechange', drawAll);
})();
