/* Applause on a blog post. See includes/blog-claps.php for the whole argument.
 *
 * WHAT THIS FILE IS RESPONSIBLE FOR, and what it is explicitly not.
 *
 * It is responsible for turning taps into a small number of requests, for
 * keeping the visible count honest, and for saying the new total out loud to a
 * screen reader. It is NOT responsible for the limits: the server clamps the
 * per request amount and throttles per connection whatever this file sends. The
 * reader ceiling below lives in localStorage, which the reader owns, so it is a
 * courtesy that stops a held button and nothing more. That is stated on the
 * page rather than implied.
 *
 * WHY TAPS ARE BATCHED. A reader who taps twelve times should cost twelve
 * counts and one or two requests, not twelve. Taps accumulate for BATCH_MS and
 * go out together, capped at the per request ceiling the server will accept.
 * The count on screen moves on the tap, because a control that waits for a
 * round trip feels broken, and it is corrected to the server's number when the
 * response lands.
 *
 * THE BUTTON SHIPS DISABLED. The markup is rendered with the attribute set, so
 * a reader without JavaScript sees a real count and an inert control rather
 * than a live-looking one that does nothing. Enabling it is the first thing
 * this file does, and only when it has a fetch to make.
 */
(function () {
    'use strict';

    var BATCH_MS = 500;

    function ready(fn) {
        if (document.readyState !== 'loading') fn();
        else document.addEventListener('DOMContentLoaded', fn);
    }

    function setup(root) {
        var endpoint = window.ALT_CLAPS_ENDPOINT;
        if (!endpoint || typeof window.fetch !== 'function') return;

        var postId = parseInt(root.getAttribute('data-post'), 10);
        var readerMax = parseInt(root.getAttribute('data-max'), 10) || 50;
        var perRequest = parseInt(root.getAttribute('data-per-request'), 10) || 10;
        if (!postId) return;

        var btn = root.querySelector('[data-alt-clap-btn]');
        var numEl = root.querySelector('[data-alt-clap-num]');
        var wordEl = root.querySelector('[data-alt-clap-word]');
        var liveEl = root.querySelector('[data-alt-clap-live]');
        if (!btn || !numEl || !wordEl) return;

        var storeKey = 'alt-clap-' + postId;
        var given = 0;
        try {
            given = parseInt(window.localStorage.getItem(storeKey), 10) || 0;
        } catch (e) {
            // Private mode, or storage denied. The reader ceiling is then not
            // remembered across page loads, which is a smaller problem than a
            // control that throws on the first tap.
            given = 0;
        }

        var shown = parseInt((numEl.textContent || '0').replace(/[^0-9]/g, ''), 10) || 0;
        var pending = 0;
        var timer = null;

        // Grouped the same way PHP's number_format_i18n() renders it, so the
        // number does not lose its thousands separator the moment a reader taps.
        function pretty(total) {
            return total.toLocaleString();
        }

        function render(total) {
            shown = total;
            numEl.textContent = pretty(total);
            wordEl.textContent = total === 1 ? 'clap' : 'claps';
        }

        function announce(total) {
            if (!liveEl) return;
            liveEl.textContent = pretty(total) + ' ' + (total === 1 ? 'clap' : 'claps') + '.';
        }

        function remember() {
            try {
                window.localStorage.setItem(storeKey, String(given));
            } catch (e) { /* see above */ }
        }

        function exhausted() {
            if (given < readerMax) return false;
            btn.disabled = true;
            if (liveEl) {
                liveEl.textContent = 'That is the most one reader can add to this article.';
            }
            return true;
        }

        function send() {
            timer = null;
            var n = Math.min(pending, perRequest);
            if (n < 1) return;
            pending -= n;
            fetch(endpoint, {
                method: 'POST',
                credentials: 'omit',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: postId, n: n })
            }).then(function (r) {
                return r.ok ? r.json() : null;
            }).then(function (data) {
                // The server's number is the truth: another reader may have
                // applauded between this tap and this response, and the
                // throttle may have declined to count this one.
                if (data && typeof data.claps === 'number') {
                    render(data.claps);
                    announce(data.claps);
                }
                if (pending > 0 && !timer) timer = window.setTimeout(send, BATCH_MS);
            }).catch(function () {
                // Offline, or the host is down. Leave the optimistic number
                // alone rather than snapping it backwards under the reader's
                // finger; the next page load reads the real one.
            });
        }

        btn.addEventListener('click', function () {
            if (exhausted()) return;
            given += 1;
            pending += 1;
            remember();
            render(shown + 1);
            btn.setAttribute('data-alt-clap-pulse', '');
            window.setTimeout(function () { btn.removeAttribute('data-alt-clap-pulse'); }, 140);
            // Re-check AFTER counting, so the tap that reaches the ceiling is
            // itself counted and the button goes inert on the way out.
            exhausted();
            if (!timer) timer = window.setTimeout(send, BATCH_MS);
        });

        // A reader who leaves mid-batch should still be counted.
        window.addEventListener('pagehide', function () {
            if (pending < 1) return;
            var n = Math.min(pending, perRequest);
            pending = 0;
            if (navigator.sendBeacon) {
                navigator.sendBeacon(endpoint,
                    new Blob([JSON.stringify({ id: postId, n: n })],
                             { type: 'application/json' }));
            }
        });

        if (!exhausted()) btn.disabled = false;
    }

    ready(function () {
        var nodes = document.querySelectorAll('[data-alt-clap]');
        for (var i = 0; i < nodes.length; i++) setup(nodes[i]);
    });
}());
