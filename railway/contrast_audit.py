#!/usr/bin/env python3
"""Read what the page RENDERS AS, in every theme, and fail on WCAG AA violations.

Why this exists, in one sentence: `reader_freshness.py` proves WHICH BYTES a
reader is served (the version, and since 2.20.33 the build stamp that ties the
body to them), and nothing proved what those bytes
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

It measures TWO things, because they fail independently. Text contrast (1.4.3)
answers "can I read the words". Control-boundary contrast (1.4.11) answers "can
I see that this is a control", and nothing measured it until the owner reported
that the filter bar "gets lost": every outline in that bar was one hairline of
--alt-border on a surface of the same family, 1.14:1 in light and 1.56:1 in
dark, with one segmented option at 1.00:1 because its border was transparent.
Perfectly readable text, invisible controls, and a green audit throughout.

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
/* Smooth scrolling is the same class of measurement lie as a colour
   transition. `scrollIntoView()` returns before a smooth scroll has finished,
   so a bounding rect read straight after it is the rect from BEFORE the
   scroll, and a synthetic click aimed at that rect lands somewhere else
   entirely. The first mobile walkthrough written against this file reported
   that the Filters toggle did not respond to a tap; the toggle was fine and
   the tap was 1500px above it. */
html, body, * { scroll-behavior: auto !important; }
"""

# WCAG 2.1 AA. Large text is >=24px, or >=18.66px when bold (>=700).
AA_NORMAL = 4.5
AA_LARGE = 3.0
# WCAG 2.1 AA 1.4.11 Non-text Contrast: the visual boundary of a user
# interface component needs 3:1 against the colours adjacent to it. Text
# contrast has been measured here since 2026-08-10; component boundaries were
# not, which is how a filter bar whose every control outline sits at 1.14:1 in
# light and 1.56:1 in dark passed every check in the repository.
AA_NONTEXT = 3.0

# WCAG 2.5.5 target size. The mobile sweep asserts this on filter controls at
# 375px, where a control is hit with a thumb and not a mouse.
TAP_MIN = 44.0

# The colour arithmetic, written once. Both probes below paste this in rather
# than carrying their own copy: two implementations of a contrast ratio is two
# numbers to reconcile the first time they disagree.
_COLOR_JS = r"""
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
"""

# Read the computed colour of every visible text-bearing element and composite
# it against the real background stack. Runs in the page; returns plain data.
PROBE_JS = "(function () {" + _COLOR_JS + r"""
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

# ---------------------------------------------------------------------------
# THE FILTER BAR'S CONTROLS, AND WHETHER YOU CAN SEE WHERE THEY ARE.
#
# The text probe above answers "can I read the words". It says nothing about
# "can I tell this is a control at all", and those are different failures with
# different causes. The owner's report was "it gets lost": every boundary in
# this filter bar was one hairline of --alt-border or --alt-grid on a surface
# of the same family, which measures 1.14:1 in light and 1.56:1 in dark, and
# one segmented option carried `border: 1px solid transparent` on a tinted
# track, which is 1.00:1 - no boundary at all, just text sitting on a panel.
#
# Every entry here is a control a reader operates in order to change what the
# page shows. The list is deliberately explicit rather than "everything that
# looks like a button": a guard that discovers its own scope silently stops
# covering a control the day its class name changes, and this bar has been
# rebuilt three times.
# ---------------------------------------------------------------------------
FILTER_CONTROLS = (
    ('date preset',      '#alt-datepresets .alt-dp'),
    ('date range button', '.alt-range-btn'),
    ('date from/to',     '#alt-range-pop input[type="date"]'),
    ('date basis option', '.alt-datebasis-opt'),
    ('search box',       '#alt-search'),
    ('sort select',      '#alt-sort'),
    ('quick view',       '.alt-quickviews .alt-qv'),
    ('filters toggle',   '#alt-filters-toggle'),
    ('filter dropdown',  '#alt-filterbar-body .alt-dd'),
    ('filter text input', '#alt-filterbar-body input[type="text"]'),
    ('filter number input', '#alt-filterbar-body input[type="number"]'),
    ('reset button',     '#alt-f-reset'),
)

# TAP TARGETS THAT ARE NOT BOUNDED CONTROLS.
#
# A row inside an open dropdown is something a thumb has to hit, and the first
# mobile walkthrough measured those rows at 31px. It is NOT a bounded control:
# the thing WCAG 1.4.11 is about there is the checkbox, which the browser draws
# itself, and demanding a 3:1 box around every row of a list would be asking
# for a border nobody wants and no guideline requires. So these are measured
# for target size and not for a boundary, and the two lists are kept apart so
# that distinction is visible rather than buried in an exception.
FILTER_TAP_TARGETS = (
    ('dropdown option', '.alt-dd-pop .alt-dd-row'),
)

# Measure the perimeter of each control.
#
# THE RULE, stated so it can be argued with. Walking outward across a control's
# edge a reader crosses at most three colours: the page behind it, the border
# line, and the fill. The edge is perceivable when SOME adjacent pair along
# that walk differs by 3:1, so the test is
#     max(ratio(border, outside), ratio(border, fill)) >= 3
# when a border line actually paints, and
#     ratio(fill, outside) >= 3
# when it does not (zero width, `none`, or a fully transparent colour).
#
# Both halves matter and neither alone is right. Dropping the second half
# passes a control whose border is transparent, which is the exact defect on
# the inactive segment of the date-basis switch. Dropping ratio(border, fill)
# fails a filled active pill whose border matches its own fill, which is
# visible precisely because the fill contrasts with the page.
#
# Translucent layers are composited, not swept: `backdrop()` walks up
# compositing every partially transparent background it meets until it reaches
# an opaque one, and the border colour is composited over the outside colour
# before either ratio is taken. Naively reading `backgroundColor` and calling
# rgba(0,0,0,0) "white" is how the first version of this file reported a clean
# bar on a page that had none.
CONTROLS_JS = "(function () {" + _COLOR_JS + r"""
  var GROUPS = __GROUPS__;
  var out = [];
  for (var gi = 0; gi < GROUPS.length; gi++) {
    var kind = GROUPS[gi][0], sel = GROUPS[gi][1], tapOnly = GROUPS[gi][2];
    var found;
    try { found = document.querySelectorAll(sel); } catch (e) { found = []; }
    for (var i = 0; i < found.length; i++) {
      var el = found[i];
      var cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') continue;
      var rect = el.getBoundingClientRect();
      if (rect.width < 1 || rect.height < 1) continue;

      var outside = backdrop(el.parentElement || document.body).color;
      var own = parse(cs.backgroundColor) || { r: 0, g: 0, b: 0, a: 0 };
      var fill = over(own, outside);

      // The weakest of the four sides is the one that decides whether the
      // shape reads, so take the minimum rather than an average.
      var sides = ['Top', 'Right', 'Bottom', 'Left'];
      var best = null, line = null, painted = false, widths = [];
      for (var s = 0; s < sides.length; s++) {
        var w = parseFloat(cs['border' + sides[s] + 'Width']) || 0;
        var st = cs['border' + sides[s] + 'Style'];
        var bc = parse(cs['border' + sides[s] + 'Color']);
        widths.push(w);
        var r;
        if (w <= 0 || st === 'none' || st === 'hidden' || !bc || bc.a === 0) {
          r = ratio(fill, outside);          // no line: the fill is the edge
        } else {
          painted = true;
          var lc = over(bc, outside);
          r = Math.max(ratio(lc, outside), ratio(lc, fill));
          if (line === null) line = lc;
        }
        if (best === null || r < best) best = r;
      }

      out.push({
        kind: kind,
        tapOnly: !!tapOnly,
        sel: selectorOf(el),
        text: (el.textContent || el.value || el.placeholder || '')
                .replace(/\s+/g, ' ').trim().slice(0, 40),
        outside: rgbstr(outside),
        fill: rgbstr(fill),
        line: line ? rgbstr(line) : '(none)',
        bordered: painted,
        borderWidths: widths,
        radius: cs.borderTopLeftRadius,
        fontSize: parseFloat(cs.fontSize) || 0,
        w: Math.round(rect.width * 10) / 10,
        h: Math.round(rect.height * 10) / 10,
        ratio: Math.round(best * 100) / 100
      });
    }
  }
  return out;
})()
"""


def controls_js():
    """The control probe with the selector table baked in.

    Kept as a function so the selector list has ONE definition (the tuple
    above) and the tests can assert against that tuple rather than against a
    second copy embedded in a string.
    """
    groups = [[k, s, False] for k, s in FILTER_CONTROLS]
    groups += [[k, s, True] for k, s in FILTER_TAP_TARGETS]
    return CONTROLS_JS.replace('__GROUPS__', json.dumps(groups))


def control_violations(rows, tap_min=None):
    """Controls whose perimeter is below 3:1, or below the tap floor.

    `tap_min` is opt-in because 44px is a mobile assertion: the same control at
    a desk is operated with a pointer. Passing it at 1280 would fail the page
    for a defect that is not there.
    """
    bad = []
    for r in rows:
        why = []
        if not r.get('tapOnly') and r['ratio'] < AA_NONTEXT:
            why.append('boundary %.2f:1 (need %.1f)' % (r['ratio'], AA_NONTEXT))
        if tap_min and (r['w'] < tap_min or r['h'] < tap_min):
            why.append('target %.0fx%.0f (need %.0f)' % (r['w'], r['h'], tap_min))
        if why:
            r = dict(r)
            r['why'] = '; '.join(why)
            bad.append(r)
    bad.sort(key=lambda r: r['ratio'])
    return bad


# Controls that live behind a disclosure are still controls. The filter panel
# remembers a reader's collapse choice and the date popover opens on click, so
# a sweep that measured only what happens to be expanded would report a clean
# bar by measuring three controls out of twenty-five. This forces every one of
# them into the layout before the probe runs, and it is a MEASUREMENT-ONLY
# mutation: nothing here changes a filter value, and the page is reloaded for
# the next theme anyway.
REVEAL_JS = r"""
(function () {
  // The toggle itself ships `hidden` and is unhidden by layoffs.js, so a
  // fixture with no script has to be told, and the live page is unaffected.
  var ids = ['alt-filterbar-body', 'alt-range-pop', 'alt-filters-toggle'];
  var n = 0;
  for (var i = 0; i < ids.length; i++) {
    var el = document.getElementById(ids[i]);
    if (el && el.hidden) { el.hidden = false; n++; }
  }
  // Every dropdown's option list, which is where the 31px rows were hiding.
  document.querySelectorAll('.alt-dd-pop[hidden]').forEach(function (p) {
    p.hidden = false; n++;
  });
  return n;
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
    # ORDER MATTERS AND IT IS NOT OBVIOUS. Freeze first, theme second, read
    # third. `.alt-btn` and every control in the bar carry a background
    # transition, so a computed background read in the same task that flipped
    # `data-theme` returns the colour it is transitioning FROM. The first run
    # of this script invented ten dark-on-dark violations per theme that way.
    _freeze(page)
    body_bg = _apply_theme(page, attr)
    rows = page.eval_js(PROBE_JS)
    page.eval_js(REVEAL_JS)
    controls = page.eval_js(controls_js())
    overflow = page.eval_js(
        "JSON.stringify({s: document.documentElement.scrollWidth,"
        " c: document.documentElement.clientWidth})")
    return rows, controls, body_bg, json.loads(overflow)


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
                            rows, ctls, body_bg, ovf = audit_page(
                                page, url, os_scheme, attr)
                        except CDPError as exc:
                            report['unknown'].append('%s: %s' % (label, exc))
                            continue
                        bad = violations(rows)
                        cbad = control_violations(
                            ctls, TAP_MIN if width < 768 else None)
                        # A tracker page that yields zero controls has not been
                        # checked, and an unchecked filter bar is UNKNOWN. This
                        # is the failure mode where a class rename quietly
                        # empties the sweep and every run turns green.
                        if name == 'tracker' and not ctls:
                            report['unknown'].append(
                                '%s: the filter bar matched 0 controls, so its '
                                'boundaries were not measured' % label)
                        report['fail'] += len(bad) + len(cbad)
                        report['surfaces'].append({
                            'surface': name, 'url': url, 'theme': theme,
                            'width': width, 'body_bg': body_bg,
                            'measured': len(rows), 'violations': bad,
                            'controls_measured': len(ctls),
                            'control_violations': cbad,
                            'scrollWidth': ovf['s'], 'clientWidth': ovf['c'],
                            'rows': rows if args.table or args.json else [],
                            'controls': ctls if args.table or args.json else [],
                        })
        except CDPUnavailable as exc:
            report['unknown'].append('@%dpx: %s' % (width, exc))
        except Exception as exc:  # network/proxy block is UNKNOWN, not a pass
            report['unknown'].append('@%dpx: %s: %s' % (width, type(exc).__name__, exc))

    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(report, fh, indent=2)

    print('=' * 68)
    print('RENDERED CONTRAST AUDIT (WCAG AA: %.1f normal text, %.1f large '
          'text, %.1f control boundaries)' % (AA_NORMAL, AA_LARGE, AA_NONTEXT))
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

        # The filter bar is only on the tracker page; elsewhere this measures
        # nothing, and "nothing measured" is reported rather than passed.
        if s.get('controls_measured'):
            if s['control_violations']:
                print('    FAIL %d filter control(s): boundary below %.1f:1%s'
                      % (len(s['control_violations']), AA_NONTEXT,
                         ' or target below %.0fpx' % TAP_MIN
                         if s['width'] < 768 else ''))
                print('      %-22s %-26s %-16s %-16s %6s  %s'
                      % ('control', 'selector', 'line', 'outside', 'ratio', 'why'))
                for v in s['control_violations'][:args.limit]:
                    print('      %-22s %-26s %-16s %-16s %6.2f  %s'
                          % (v['kind'][:22], v['sel'][:26], v['line'],
                             v['outside'], v['ratio'], v['why']))
                if len(s['control_violations']) > args.limit:
                    print('      ... %d more'
                          % (len(s['control_violations']) - args.limit))
            else:
                print('    PASS: all %d filter controls have a visible boundary'
                      % s['controls_measured'])
        elif s['surface'] == 'tracker':
            print('    (no filter controls matched — treat as UNKNOWN, the '
                  'bar did not render or the selectors moved)')

        if args.table:
            print('      --- all measured elements ---')
            for r in sorted(s['rows'], key=lambda r: r['ratio']):
                print('      %-38s %-16s %-16s %6.2f %s'
                      % (r['sel'][:38], r['color'], r['bg'], r['ratio'],
                         'large' if r['large'] else ''))
            print('      --- all measured controls ---')
            for r in sorted(s['controls'], key=lambda r: r['ratio']):
                print('      %-20s %-26s line=%-16s out=%-16s %6.2f  '
                      '%6.1fx%-5.1f r=%-6s fs=%.1f'
                      % (r['kind'][:20], r['sel'][:26], r['line'], r['outside'],
                         r['ratio'], r['w'], r['h'], r['radius'], r['fontSize']))

    if report['unknown']:
        print('\nUNKNOWN (could not measure — this is NOT a pass):')
        for u in report['unknown']:
            print('    ' + u)

    print()
    if report['unknown'] and not report['surfaces']:
        print('RESULT: UNKNOWN — nothing was measured.')
        return 3
    if report['fail']:
        print('RESULT: FAIL — %d contrast violation(s) are live for readers '
              '(text and/or control boundaries).' % report['fail'])
        return 2
    if report['unknown']:
        print('RESULT: UNKNOWN — some surfaces measured clean, others could '
              'not be measured at all.')
        return 3
    print('RESULT: PASS — every surface, every theme, meets WCAG AA.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
