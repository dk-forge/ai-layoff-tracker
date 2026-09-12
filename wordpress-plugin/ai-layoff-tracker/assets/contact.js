/*
 * The contact form's behaviour, as a FILE and not as an inline <script>.
 *
 * WHY THIS IS A FILE. The same code lived inline in the shortcode's output and
 * NEVER REACHED THE LIVE PAGE. Measured 2026-09-12 on asktherecruiter.com: the
 * rendered contact page carries the markup (`alt-tip-only`, `data-alt-hints`)
 * and not one line of the script, while other script tags on the same page
 * survive, so something in the stack strips executable script out of content
 * and has been doing it the whole time. Nothing reported it, because a
 * behaviour that never runs raises no error: the tip-only "Company that had
 * the layoff" field simply never appeared for anyone.
 *
 * It is enqueued the way every other script in this plugin is, which is the
 * shape that demonstrably survives (assets/blog-claps.js, assets/health.js).
 *
 * The endpoint arrives as window.ALT_CONTACT_CHALLENGE_URL, set by
 * wp_add_inline_script, exactly as blog-claps.js takes ALT_CLAPS_ENDPOINT.
 */
(function () {
    var topic = document.getElementById('alt-c-topic');
    if (!topic) return;
    var hints = {};
    try { hints = JSON.parse(topic.getAttribute('data-alt-hints') || '{}'); } catch (e) { hints = {}; }
    var hintEl = document.getElementById('alt-c-topic-hint');
    // 'app' is the one subject that is not about the tracker at all, so
    // the source-link row stops asking for a news report and asks for
    // the page that went wrong instead. Leaving the tracker wording up
    // is how a form tells someone they picked the wrong option.
    var sync = function () {
        var value = topic.value;
        var isTip = value === 'tip';
        var isApp = value === 'app';
        document.querySelectorAll('.alt-tip-only').forEach(function (el) { el.hidden = !isTip; });
        var show = function (sel, on) {
            var el = document.querySelector(sel);
            if (el) el.hidden = !on;
        };
        show('.alt-tip-note', isTip);
        show('.alt-app-note', isApp);
        show('.alt-nontip-note', !isTip && !isApp);
        var linkLabel = document.getElementById('alt-c-link-label');
        if (linkLabel) {
            linkLabel.textContent = isApp
                ? 'Link to the page (optional)'
                : 'Link to the source (news report, filing, or company post)';
        }
        if (hintEl && Object.prototype.hasOwnProperty.call(hints, value)) {
            hintEl.textContent = hints[value];
        }
    };
    topic.addEventListener('change', sync);
    sync();

    // THE CHALLENGE IS FETCHED, NOT TRUSTED FROM THE HTML.
    //
    // Everything below replaces values that were minted when this page
    // was RENDERED, which behind a shared cache can be hours or days
    // before anyone read it. The nonce, the timestamp and the
    // arithmetic token all expire; the page does not. Until this ran,
    // a visitor served a cached copy was told their message looked
    // like spam.
    //
    // Failure here is silent ON PURPOSE. If the route cannot be
    // reached, the printed values stay in place and the form behaves
    // exactly as it did before: on an uncached page they are valid,
    // and a visitor should never be shown an error about our caching.
    var form = document.querySelector('.alt-contact-form');
    if (!form || !window.fetch) return;
    var put = function (name, value) {
        var el = form.querySelector('[name="' + name + '"]');
        if (el) el.value = value;
    };
    fetch(window.ALT_CONTACT_CHALLENGE_URL, {
        credentials: 'same-origin',
        cache: 'no-store'
    }).then(function (r) {
        return r.ok ? r.json() : null;
    }).then(function (c) {
        if (!c || !c.token) return;
        put('alt_contact_nonce', c.nonce);
        put('alt_ts', c.ts);
        put('alt_token', c.token);
        var label = document.getElementById('alt-c-captcha-label');
        if (label && typeof c.a === 'number' && typeof c.b === 'number') {
            var tpl = label.getAttribute('data-alt-question') || '';
            label.textContent = tpl.replace('%A%', c.a).replace('%B%', c.b);
        }
        var answer = document.getElementById('alt-c-captcha');
        // The question just changed under them; an answer to the old
        // one would fail and read as their mistake.
        if (answer) answer.value = '';
    }).catch(function () { /* printed values stand */ });
})();
