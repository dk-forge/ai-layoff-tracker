/*
 * Roo, the floating feedback widget, on every /blog page (owner ruling
 * 2026-10-21; asktherecruiter-sandbox docs/DECISIONS.md "Roo feedback on every
 * surface"). Posts to the SAME pipeline as the app (/api/feedback/site, same
 * origin) with product=blog and the page path. Config comes from the
 * data-alt-roo attribute on #alt-roo-feedback, never an inline object
 * (Autoptimize). No dependencies.
 */
(function (root) {
  'use strict';

  /* VISIBILITY RULE: a mirror of asktherecruiter-sandbox
   * frontend/shared/roo/rooVisibility.ts (and fasthire lib/rooVisibility.ts).
   * Same constants, same FNV-1a hash, same golden buckets in the tests. */
  var UNTIL = '2027-02-01T00:00:00Z';
  var PERCENT = 50;
  var KEY = 'atr_roo_vid';

  function bucket(id) {
    var h = 0x811c9dc5;
    for (var i = 0; i < id.length; i++) {
      h ^= id.charCodeAt(i);
      h = Math.imul(h, 0x01000193) >>> 0;
    }
    return h % 100;
  }

  function show(id, nowMs) {
    if (nowMs < Date.parse(UNTIL)) return true;
    if (!id) return false;
    return bucket(id) < PERCENT;
  }

  function visitorId() {
    try {
      var s = root.localStorage;
      var v = s.getItem(KEY);
      if (v) return v;
      v = (root.crypto && root.crypto.randomUUID) ? root.crypto.randomUUID()
        : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12);
      s.setItem(KEY, v);
      return v;
    } catch (e) {
      return null;
    }
  }

  root.AltRooRule = { UNTIL: UNTIL, PERCENT: PERCENT, KEY: KEY, bucket: bucket, show: show };

  var doc = root.document;
  if (!doc) return;

  var ROO_SVG = '<svg aria-hidden="true" focusable="false" width="28" height="30" viewBox="0 0 140 150">'
    + '<line x1="70" y1="14" x2="70" y2="26" stroke="#3F5E46" stroke-width="3" stroke-linecap="round"/>'
    + '<circle cx="70" cy="10" r="5" fill="#D4A574"/>'
    + '<rect x="26" y="24" width="88" height="40" rx="20" fill="#fff" stroke="#3F5E46" stroke-width="3.5"/>'
    + '<circle cx="51" cy="44" r="12" fill="#E6EDE6" stroke="#3F5E46" stroke-width="2.5"/>'
    + '<circle cx="53.5" cy="44" r="5.5" fill="#3F5E46"/>'
    + '<circle cx="89" cy="44" r="12" fill="#E6EDE6" stroke="#3F5E46" stroke-width="2.5"/>'
    + '<circle cx="86.5" cy="44" r="5.5" fill="#3F5E46"/>'
    + '<path d="M 59 57 Q 70 61 81 57" fill="none" stroke="#3F5E46" stroke-width="2.5" stroke-linecap="round"/>'
    + '<rect x="64" y="64" width="12" height="8" fill="#3F5E46" rx="2"/>'
    + '<rect x="18" y="82" width="14" height="28" rx="7" fill="#fff" stroke="#3F5E46" stroke-width="3"/>'
    + '<rect x="108" y="82" width="14" height="28" rx="7" fill="#fff" stroke="#3F5E46" stroke-width="3"/>'
    + '<rect x="36" y="72" width="68" height="46" rx="10" fill="#fff" stroke="#3F5E46" stroke-width="3.5"/>'
    + '<rect x="48" y="80" width="44" height="30" rx="5" fill="#E6EDE6" stroke="#3F5E46" stroke-width="2"/>'
    + '<rect x="30" y="122" width="80" height="14" rx="7" fill="#E6EDE6" stroke="#3F5E46" stroke-width="2.5"/>'
    + '</svg>';

  var MESSAGES = {
    403: 'The security check did not pass. Please try again.',
    422: 'Please check your email address and try again.',
    429: 'Thanks, we have plenty from you for now. Please try again later.'
  };

  function el(tag, attrs, text) {
    var n = doc.createElement(tag);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, attrs[k]);
    if (text) n.textContent = text;
    return n;
  }

  function readConfig(host) {
    try {
      var c = JSON.parse(host.getAttribute('data-alt-roo') || '{}');
      if (typeof c.endpoint === 'string' && c.endpoint.charAt(0) === '/') return c;
    } catch (e) { /* fall through */ }
    return null;
  }

  var turnstileLoading = false;
  function loadTurnstile(cb) {
    if (root.turnstile) return cb();
    if (!turnstileLoading) {
      turnstileLoading = true;
      var s = el('script', { src: 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit', async: '' });
      doc.head.appendChild(s);
    }
    var tries = 0;
    var t = setInterval(function () {
      if (root.turnstile || ++tries > 50) { clearInterval(t); if (root.turnstile) cb(); }
    }, 200);
  }

  function boot() {
    var host = doc.getElementById('alt-roo-feedback');
    if (!host) return;
    var cfg = readConfig(host);
    if (!cfg) return;
    if (!show(visitorId(), Date.now())) return;

    var trigger = el('button', {
      type: 'button', 'class': 'alt-roo-btn', 'data-testid': 'alt-roo-button', 'aria-expanded': 'false'
    });
    trigger.setAttribute('aria-label', 'Give us feedback');
    trigger.setAttribute('aria-haspopup', 'dialog');
    trigger.innerHTML = ROO_SVG + '<span class="alt-roo-btn-text">Feedback</span>';
    host.appendChild(trigger);

    var dialog = null;

    function close() {
      if (!dialog) return;
      dialog.parentNode.removeChild(dialog);
      dialog = null;
      trigger.setAttribute('aria-expanded', 'false');
      doc.removeEventListener('keydown', onKey);
      trigger.focus();
    }

    function onKey(e) {
      if (!dialog) return;
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Tab') return;
      var items = dialog.querySelectorAll('button, input, textarea, iframe');
      if (!items.length) return;
      var first = items[0], last = items[items.length - 1];
      if (e.shiftKey && doc.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && doc.activeElement === last) { e.preventDefault(); first.focus(); }
    }

    function open() {
      if (dialog) return;
      var titleId = 'alt-roo-title';
      dialog = el('div', { 'class': 'alt-roo-dialog', 'data-testid': 'alt-roo-dialog' });
      dialog.setAttribute('role', 'dialog');
      dialog.setAttribute('aria-modal', 'true');
      dialog.setAttribute('aria-labelledby', titleId);

      var form = el('form', { novalidate: '' });
      var head = el('div', { 'class': 'alt-roo-head' });
      head.appendChild(el('h2', { id: titleId, 'class': 'alt-roo-title' }, 'Tell us what you think'));
      var x = el('button', { type: 'button', 'class': 'alt-roo-close' }, '×');
      x.setAttribute('aria-label', 'Close');
      x.addEventListener('click', close);
      head.appendChild(x);
      form.appendChild(head);

      var stars = el('fieldset', { 'class': 'alt-roo-stars' });
      stars.appendChild(el('legend', { 'class': 'alt-roo-legend' }, 'How useful is this page?'));
      var rating = 0;
      for (var n = 1; n <= 5; n++) {
        (function (v) {
          var lab = el('label', { 'class': 'alt-roo-star' });
          var r = el('input', { type: 'radio', name: 'alt-roo-rating', value: String(v), 'class': 'alt-roo-vh' });
          r.setAttribute('aria-label', v + ' out of 5 stars');
          var glyph = el('span', { 'aria-hidden': 'true' }, '☆');
          r.addEventListener('change', function () {
            rating = v;
            var gl = stars.querySelectorAll('.alt-roo-star span');
            for (var i = 0; i < gl.length; i++) gl[i].textContent = i < v ? '★' : '☆';
          });
          lab.appendChild(r); lab.appendChild(glyph);
          stars.appendChild(lab);
        })(n);
      }
      form.appendChild(stars);

      var tl = el('label', { 'class': 'alt-roo-label', 'for': 'alt-roo-text' }, 'Anything to add? (optional)');
      var ta = el('textarea', { id: 'alt-roo-text', maxlength: '2000', rows: '3', 'class': 'alt-roo-input' });
      var stl = el('label', { 'class': 'alt-roo-label', 'for': 'alt-roo-email' }, 'Email, if you would like a reply (optional)');
      var em = el('input', { id: 'alt-roo-email', type: 'email', maxlength: '254', autocomplete: 'email', 'class': 'alt-roo-input' });
      var hp = el('input', { type: 'text', name: 'website', tabindex: '-1', autocomplete: 'off', 'class': 'alt-roo-hp' });
      hp.setAttribute('aria-hidden', 'true');
      form.appendChild(tl); form.appendChild(ta); form.appendChild(stl); form.appendChild(em); form.appendChild(hp);

      var widget = el('div', { 'class': 'alt-roo-turnstile' });
      form.appendChild(widget);
      var token = '';
      if (cfg.siteKey) {
        loadTurnstile(function () {
          if (dialog && root.turnstile) root.turnstile.render(widget, { sitekey: cfg.siteKey, callback: function (t) { token = t; } });
        });
      }

      var status = el('p', { 'class': 'alt-roo-status', 'data-testid': 'alt-roo-status' });
      status.setAttribute('aria-live', 'polite');
      var send = el('button', { type: 'submit', 'class': 'alt-roo-send' }, 'Send');
      form.appendChild(status); form.appendChild(send);

      form.addEventListener('submit', function (e) {
        e.preventDefault();
        if (rating < 1) { status.textContent = 'Please choose a star rating.'; return; }
        send.disabled = true;
        status.textContent = 'Sending...';
        var body = {
          rating: rating,
          text: (ta.value || '').trim(),
          email: (em.value || '').trim() || null,
          page: (root.location.pathname || '').split(/[?#]/)[0].slice(0, 200),
          product: cfg.product || 'blog',
          website: hp.value || null,
          turnstile_token: token || null
        };
        fetch(cfg.endpoint, {
          method: 'POST', credentials: 'omit',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        }).then(function (r) {
          if (r.ok) {
            status.textContent = 'Thanks for the feedback. We read every message.';
            send.style.display = 'none';
            return;
          }
          status.textContent = MESSAGES[r.status] || 'Could not send just now. Please try again later.';
          send.disabled = false;
          if (root.turnstile) { try { root.turnstile.reset(widget); } catch (err) { /* ignore */ } token = ''; }
        }).catch(function () {
          status.textContent = 'Could not send just now. Please try again later.';
          send.disabled = false;
        });
      });

      dialog.appendChild(form);
      doc.body.appendChild(dialog);
      trigger.setAttribute('aria-expanded', 'true');
      doc.addEventListener('keydown', onKey);
      var firstStar = dialog.querySelector('input[type=radio]');
      if (firstStar) firstStar.focus();
    }

    trigger.addEventListener('click', open);
  }

  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', boot);
  else boot();
})(typeof window !== 'undefined' ? window : this);
