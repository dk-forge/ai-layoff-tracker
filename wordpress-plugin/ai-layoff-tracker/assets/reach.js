/*
  Reach (includes/reach.php): GA4 funnel events and share buttons.

  EVENTS. Five, fixed, sent through the site's existing Google tag
  (window.gtag) and nowhere else. send() keeps only an allow-list of short,
  non-personal parameters, and drops any value that looks like an email
  address, so a future caller cannot leak one by accident. No gtag on the page
  (blocked, consent off) means nothing is sent and nothing breaks.

  SHARE. Native Web Share where the browser has it, else copy link, LinkedIn
  and X intent links. Built from the page URL and title only; no third-party
  script is loaded.

  Tests: railway/tests/test_reach.py runs this file in node.
*/
var AltReach = (function () {
    var EVENTS = ['digest_signup', 'follow', 'embed_copy', 'cite_copy', 'resume_prompt_click'];
    var KEYS = ['surface', 'kind', 'chart', 'page_type', 'campaign', 'method'];

    function clean(params) {
        var out = {};
        params = params || {};
        KEYS.forEach(function (k) {
            var v = params[k];
            if (typeof v !== 'string' || v === '' || v.length > 64 || v.indexOf('@') !== -1) return;
            out[k] = v;
        });
        return out;
    }

    function send(name, params) {
        if (EVENTS.indexOf(name) === -1) return false;
        if (typeof gtag !== 'function') return false;
        try { gtag('event', name, clean(params)); } catch (e) { return false; }
        return true;
    }

    function shareLinks(url, title) {
        var u = encodeURIComponent(url);
        return {
            linkedin: 'https://www.linkedin.com/sharing/share-offsite/?url=' + u,
            x: 'https://x.com/intent/post?url=' + u + '&text=' + encodeURIComponent(title || '')
        };
    }

    function resumeCampaign(href) {
        var m = /[?&]utm_source=ai-layoff-tracker(?:&|$)/.test(href || '') && /[?&]utm_campaign=([a-z0-9_-]+)/i.exec(href);
        return m ? m[1] : null;
    }

    return { EVENTS: EVENTS, clean: clean, send: send, shareLinks: shareLinks, resumeCampaign: resumeCampaign };
})();

(function () {
    if (typeof document === 'undefined') return;
    var d = document;
    var pageType = d.querySelector('.alt-facet-page') ? 'facet'
        : d.querySelector('.alt-company-directory') ? 'company'
        : d.getElementById('alt-cite-box') ? 'tracker' : 'other';

    function closest(el, sel) { return el && el.closest ? el.closest(sel) : null; }

    d.addEventListener('submit', function (e) {
        var f = e.target;
        if (closest(f, 'form.alt-digest-form')) {
            AltReach.send('digest_signup', { surface: f.getAttribute('data-alt-context') || '', page_type: pageType });
        } else if (closest(f, '.alt-follow form')) {
            var k = f.querySelector('input[name="alt_follow_kind"]');
            AltReach.send('follow', { kind: k ? k.value : '', page_type: pageType });
        }
    }, true);

    d.addEventListener('click', function (e) {
        var t = e.target;
        if (closest(t, '.alt-embed-copy, #alt-widget-copy')) {
            AltReach.send('embed_copy', { surface: closest(t, '#alt-widget-copy') ? 'widget' : 'chart', page_type: pageType });
            return;
        }
        if (closest(t, '#alt-cite-copy, #alt-cite')) {
            AltReach.send('cite_copy', { page_type: pageType });
            return;
        }
        var a = closest(t, 'a[href]');
        if (a) {
            var c = AltReach.resumeCampaign(a.href);
            if (c) AltReach.send('resume_prompt_click', { campaign: c, page_type: pageType });
        }
    }, true);

    function initShare(box) {
        var url = box.getAttribute('data-alt-share-url') || (location.origin + location.pathname);
        var title = box.getAttribute('data-alt-share-title') || d.title;
        var links = AltReach.shareLinks(url, title);
        var native = box.querySelector('[data-alt-share-kind="native"]');
        var status = box.querySelector('[data-alt-share-status]');
        if (native && navigator.share) {
            native.hidden = false;
            native.addEventListener('click', function () {
                navigator.share({ title: title, url: url }).catch(function () {});
            });
        }
        var li = box.querySelector('[data-alt-share-kind="linkedin"]');
        var x = box.querySelector('[data-alt-share-kind="x"]');
        if (li) li.href = links.linkedin;
        if (x) x.href = links.x;
        var copy = box.querySelector('[data-alt-share-kind="copy"]');
        if (copy) copy.addEventListener('click', function () {
            var done = function () { if (status) status.textContent = 'Link copied'; };
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url).then(done, function () { if (status) status.textContent = url; });
            } else if (status) { status.textContent = url; }
        });
    }

    function boot() { d.querySelectorAll('[data-alt-share]').forEach(initShare); }
    d.readyState === 'loading' ? d.addEventListener('DOMContentLoaded', boot) : boot();
})();
