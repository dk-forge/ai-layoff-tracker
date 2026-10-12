/* AI exposure metro picker ([alt_ai_exposure], includes/ai-exposure.php).
   The page is server-rendered for the first metro; this only redraws the
   metro panel from data-ax-metros when the reader picks another one. */
(function () {
    function fmt(n) { return Number(n).toLocaleString('en-US'); }
    function init() {
        var card = document.querySelector('.alt-ax [data-ax="metro"]');
        if (!card) return;
        var data;
        try { data = JSON.parse(card.getAttribute('data-ax-metros') || '{}'); } catch (e) { return; }
        var sel = card.querySelector('#alt-ax-metro');
        var out = card.querySelector('.alt-ax-metro-out');
        if (!sel || !out) return;
        sel.addEventListener('change', function () {
            var m = data[sel.value];
            if (!m || !m.total) return;
            out.querySelector('.alt-ax-big').textContent = fmt(m.exposed);
            out.querySelector('.alt-ax-mt').textContent = m.title;
            out.querySelector('.alt-ax-share').textContent = Math.round(m.exposed / m.total * 100) + '%';
            out.querySelector('.alt-ax-tot').textContent = fmt(m.total);
            var ol = out.querySelector('.alt-ax-jobs');
            ol.textContent = '';
            (m.jobs || []).forEach(function (j) {
                var li = document.createElement('li');
                var a = document.createElement('span');
                a.textContent = j[0];
                var b = document.createElement('span');
                b.className = 'alt-ax-n';
                b.textContent = fmt(j[1]) + ' (' + j[2] + ' exposure)';
                li.appendChild(a);
                li.appendChild(document.createTextNode(' '));
                li.appendChild(b);
                ol.appendChild(li);
            });
        });
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
