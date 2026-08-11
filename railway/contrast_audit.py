#!/usr/bin/env python3
"""Read what the page RENDERS AS, in every theme, and fail on WCAG AA violations.

Why this exists, in one sentence: `reader_freshness.py` proves which VERSION of
the bytes a reader is served, and for months nothing proved what those bytes
LOOK LIKE — so a site-level rule in the WordPress database hard-coded
`color:#1a1a1a !important` onto `.entry-content h2`, beat every token the
plugin owns, and shipped ~173 elements between 1.06:1 and 1.28:1 to every
reader who uses dark mode. Every check in the repo read green throughout,
because every check read CSS or version strings, and the defect only exists
once the cascade resolves.

So this check refuses to read CSS. It loads the live URL in real Chrome, with a
browser User-Agent and NO cache buster (the bare key a reader actually holds),
switches `data-theme`, and asks the browser for the COMPUTED colour of every
visible text element, composited against its real background. That is the only
evidence that survives an override we do not control and cannot see from the
repo.

  python3 railway/contrast_audit.py                  # all surfaces, both themes
  python3 railway/contrast_audit.py --url <u>        # one page
  python3 railway/contrast_audit.py --json out.json  # machine-readable
  python3 railway/contrast_audit.py --table          # full before/after table

Exit codes follow the house rule that absence of a signal is not a pass:
  0 = every surface measured, every theme, no AA violation
  2 = measured, and something FAILS AA
  3 = could NOT measure (no Chrome, host unreachable) -> UNKNOWN, not clear
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp import Browser, CDPError, CDPUnavailable  # noqa: E402

SITE = os.environ.get('WP_SITE_URL', 'https://asktherecruiter.com/blog').rstrip('/')

# The public surfaces a reader can land on. Keep in step with the 4-surface
# ritual in CLAUDE.md; the tracker page is the one that regressed.
SURFACES = [
    ('tracker', SITE + '/ai-layoff-tracker/'),
    ('health', SITE + '/ai-layoff-tracker/ai-tracker-health/'),
    ('sources', SITE + '/ai-layoff-tracker/sources/'),
]

# Four reader-realistic combinations, not two. `data-theme` is the reader's
# explicit choice and `prefers-color-scheme` is their OS; the plugin's dark
# rules are written as `[data-theme=dark]` OR `:not([data-theme=light])` under
# the media query, so the two MISMATCHED combinations (dark OS + Light chosen,
# light OS + Dark chosen) exercise a different half of the stylesheet than
# either matched one. Auto is the default, so `attr=None` is what most readers
# actually get and is the combination that shipped the 1.06:1 page.
THEMES = (
    ('light', 'light', None),        # name, emulated OS scheme, data-theme
    ('dark', 'dark', None),
    ('light-chosen', 'dark', 'light'),
    ('dark-chosen', 'light', 'dark'),
)
THEME_NAMES = tuple(t[0] for t in THEMES)
VIEWPORTS = ((1280, 900), (375, 812))

# Colour transitions are the reason a naive sweep lies. `.alt-btn` carries
# `transition: background .15s`, so reading a computed background in the same
# task that flipped the theme returns the OLD colour: the first run of this
# script reported ten dark-on-dark "violations" per theme that were entirely
# its own measurement, and settling for 1.5s made every one of them vanish.
# A guard that invents failures gets muted as fast as one that misses them, so
# animation is switched off outright rather than waited out.
FREEZE_CSS = """
*, *::before, *::after {
  transition: none !important;
  animation: none !important;
  caret-color: transparent !important;
}
"""

# WCAG 2.1 AA. Large text is >=24px, or >=18.66px when bold (>=700).
AA_NORMAL = 4.5
AA_LARGE = 3.0

# Read the computed colour of every visible text-bearing element and composite
# it against the real background stack. Runs in the page; returns plain data.
PROBE_JS = r"""
(function () {
  function parse(c) {
    var m = /^rgba?\(([^)]+)\)$/.exec(c || '');
    if (!m) return null;
    var p = m[1].split(',').map(function (x) { return parseFloat(x); });
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }
  function over(fg, bg) {           // source-over composite
    var a = fg.a + bg.a * (1 - fg.a);
    if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
    return {
      r: (fg.r * fg.a + bg.r * bg.a * (1 - fg.a)) / a,
      g: (fg.g * fg.a + bg.g * bg.a * (1 - fg.a)) / a,
      b: (fg.b * fg.a + bg.b * bg.a * (1 - fg.a)) / a,
      a: a
    };
  }
  function lum(c) {
    function ch(v) {
      v = v / 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    }
    return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b);
  }
  function ratio(a, b) {
    var l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  function rgbstr(c) {
    return 'rgb(' + Math.round(c.r) + ',' + Math.round(c.g) + ',' + Math.round(c.b) + ')';
  }

  // Walk up for the first opaque backdrop, compositing translucent layers.
  // A background-image (gradient, photo) is not measurable from a single
  // colour, so we mark it and report it rather than guessing a pass.
  function backdrop(el) {
    var stack = [], node = el, painted = false;
    while (node && node.nodeType === 1) {
      var cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') painted = true;
      var bg = parse(cs.backgroundColor);
      if (bg && bg.a > 0) {
        stack.push(bg);
        if (bg.a >= 0.999) break;
      }
      node = node.parentElement;
    }
    var out = { r: 255, g: 255, b: 255, a: 1 };
    for (var i = stack.length - 1; i >= 0; i--) out = over(stack[i], out);
    return { color: out, painted: painted };
  }

  function selectorOf(el) {
    var s = el.tagName.toLowerCase();
    if (el.id) return s + '#' + el.id;
    var cls = (el.getAttribute('class') || '').trim().split(/\s+/)
      .filter(Boolean).slice(0, 3);
    return cls.length ? s + '.' + cls.join('.') : s;
  }

  var out = [];
  var all = document.body ? document.body.querySelectorAll('*') : [];
  for (var i = 0; i < all.length; i++) {
    var el = all[i];
    // Only elements that own rendered text directly; a wrapper's colour is
    // irrelevant if every word inside it belongs to a child.
    var own = '';
    for (var j = 0; j < el.childNodes.length; j++) {
      var n = el.childNodes[j];
      if (n.nodeType === 3) own += n.nodeValue;
    }
    own = own.replace(/\s+/g, ' ').trim();
    if (!own) continue;

    var cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (parseFloat(cs.opacity) === 0) continue;
    var rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    // Screen-reader-only text is clipped out of the visual layer.
    if (rect.width <= 2 && rect.height <= 2) continue;
    if (cs.textIndent && parseFloat(cs.textIndent) < -900) continue;

    var fg = parse(cs.color);
    if (!fg || fg.a === 0) continue;
    var bd = backdrop(el);
    var eff = over(fg, bd.color);

    var size = parseFloat(cs.fontSize) || 16;
    var weight = parseInt(cs.fontWeight, 10) || 400;
    var large = size >= 24 || (size >= 18.66 && weight >= 700);

    out.push({
      sel: selectorOf(el),
      text: own.slice(0, 60),
      color: rgbstr(eff),
      bg: rgbstr(bd.color),
      size: size,
      weight: weight,
      large: large,
      painted: bd.painted,
      ratio: Math.round(ratio(eff, bd.color) * 100) / 100
    });
  }
  return out;
})()
"""


def _freeze(page):
    page.eval_js(
        "(function(){"
        "  var s = document.getElementById('alt-audit-freeze');"
        "  if (!s) { s = document.createElement('style');"
        "            s.id = 'alt-audit-freeze';"
        "            document.head.appendChild(s); }"
        "  s.textContent = %s; return true;"
        "})()" % json.dumps(FREEZE_CSS))


def _apply_theme(page, attr):
    """Set (or clear) the reader's explicit choice, exactly as the page's own
    head snippet does. Reading a stylesheet is not evidence; this makes the
    browser resolve the whole cascade for real, override and all."""
    if attr is None:
        page.eval_js(
            "(function(){ try { localStorage.removeItem('alt-theme'); } catch(e){}"
            "  document.documentElement.removeAttribute('data-theme');"
            "  return true; })()")
    else:
        page.eval_js(
            "(function(){ try { localStorage.setItem('alt-theme', %s); } catch(e){}"
            "  document.documentElement.setAttribute('data-theme', %s);"
            "  return true; })()" % (json.dumps(attr), json.dumps(attr)))
    got = page.eval_js("document.documentElement.getAttribute('data-theme')")
    if got != attr:
        raise CDPError('theme did not stick: asked %r, got %r' % (attr, got))
    return page.eval_js("getComputedStyle(document.body).backgroundColor")


def audit_page(page, url, os_scheme, attr):
    page.call('Emulation.setEmulatedMedia', {
        'features': [{'name': 'prefers-color-scheme', 'value': os_scheme}]})
    page.navigate(url)
    _freeze(page)
    body_bg = _apply_theme(page, attr)
    rows = page.eval_js(PROBE_JS)
    overflow = page.eval_js(
        "JSON.stringify({s: document.documentElement.scrollWidth,"
        " c: document.documentElement.clientWidth})")
    return rows, body_bg, json.loads(overflow)


def violations(rows):
    bad = []
    for r in rows:
        need = AA_LARGE if r['large'] else AA_NORMAL
        if r['ratio'] < need:
            r = dict(r)
            r['required'] = need
            bad.append(r)
    bad.sort(key=lambda r: r['ratio'])
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--url', action='append', help='audit only this URL (repeatable)')
    ap.add_argument('--theme', action='append', choices=THEME_NAMES,
                    help='audit only this theme (repeatable)')
    ap.add_argument('--width', type=int, action='append',
                    help='viewport width (repeatable); default 1280 and 375')
    ap.add_argument('--json', help='write the full measurement here')
    ap.add_argument('--table', action='store_true',
                    help='print every measured element, not just failures')
    ap.add_argument('--limit', type=int, default=25,
                    help='how many failures to print per surface (default 25)')
    args = ap.parse_args()

    surfaces = ([(u, u) for u in args.url] if args.url else SURFACES)
    themes = ([t for t in THEMES if t[0] in args.theme] if args.theme
              else list(THEMES))
    viewports = ([(w, 900 if w >= 768 else 812) for w in args.width]
                 if args.width else list(VIEWPORTS))

    report = {'surfaces': [], 'unknown': [], 'fail': 0}

    for width, height in viewports:
        try:
            with Browser(width=width, height=height) as page:
                for name, url in surfaces:
                    for theme, os_scheme, attr in themes:
                        label = '%s @%dpx %s' % (name, width, theme)
                        try:
                            rows, body_bg, ovf = audit_page(
                                page, url, os_scheme, attr)
                        except CDPError as exc:
                            report['unknown'].append('%s: %s' % (label, exc))
                            continue
                        bad = violations(rows)
                        report['fail'] += len(bad)
                        report['surfaces'].append({
                            'surface': name, 'url': url, 'theme': theme,
                            'width': width, 'body_bg': body_bg,
                            'measured': len(rows), 'violations': bad,
                            'scrollWidth': ovf['s'], 'clientWidth': ovf['c'],
                            'rows': rows if args.table or args.json else [],
                        })
        except CDPUnavailable as exc:
            report['unknown'].append('@%dpx: %s' % (width, exc))
        except Exception as exc:  # network/proxy block is UNKNOWN, not a pass
            report['unknown'].append('@%dpx: %s: %s' % (width, type(exc).__name__, exc))

    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(report, fh, indent=2)

    print('=' * 68)
    print('RENDERED CONTRAST AUDIT (WCAG AA: %.1f normal, %.1f large)'
          % (AA_NORMAL, AA_LARGE))
    print('=' * 68)

    for s in report['surfaces']:
        head = ('%-8s %-5s @%-5d bg=%-16s %4d text elements'
                % (s['surface'], s['theme'], s['width'], s['body_bg'], s['measured']))
        print('\n' + head)
        if s['scrollWidth'] > s['clientWidth']:
            print('    OVERFLOW: scrollWidth %d > clientWidth %d'
                  % (s['scrollWidth'], s['clientWidth']))
        if not s['measured']:
            print('    (nothing measured — treat as UNKNOWN)')
        if s['violations']:
            print('    FAIL %d element(s) below AA' % len(s['violations']))
            print('      %-38s %-16s %-16s %6s %6s'
                  % ('selector', 'color', 'background', 'ratio', 'need'))
            for v in s['violations'][:args.limit]:
                print('      %-38s %-16s %-16s %6.2f %6.1f%s'
                      % (v['sel'][:38], v['color'], v['bg'], v['ratio'],
                         v['required'], ' [bg-image]' if v['painted'] else ''))
            if len(s['violations']) > args.limit:
                print('      ... %d more' % (len(s['violations']) - args.limit))
        else:
            print('    PASS: every text element meets AA')
        if args.table:
            print('      --- all measured elements ---')
            for r in sorted(s['rows'], key=lambda r: r['ratio']):
                print('      %-38s %-16s %-16s %6.2f %s'
                      % (r['sel'][:38], r['color'], r['bg'], r['ratio'],
                         'large' if r['large'] else ''))

    if report['unknown']:
        print('\nUNKNOWN (could not measure — this is NOT a pass):')
        for u in report['unknown']:
            print('    ' + u)

    print()
    if report['unknown'] and not report['surfaces']:
        print('RESULT: UNKNOWN — nothing was measured.')
        return 3
    if report['fail']:
        print('RESULT: FAIL — %d contrast violation(s) are live for readers.'
              % report['fail'])
        return 2
    if report['unknown']:
        print('RESULT: UNKNOWN — some surfaces measured clean, others could '
              'not be measured at all.')
        return 3
    print('RESULT: PASS — every surface, every theme, meets WCAG AA.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
