"""DEAD SPACE INSIDE A CARD, MEASURED ON THE RENDERED PAGE.

WHY THIS EXISTS, and why it is not a list of card names.

The owner reported the same defect three times about three different cards:
"Largest single job cuts" has a band of empty white under its last row, then
"Repeat layoffs" and "Browse the record: top places", then a soundbite card on
the press page. Each report was true, each was fixable on its own, and fixing
them one at a time guarantees a fourth report. His actual ask was the rule:
"ensure all get formatted automatically all the time".

So this measures a PROPERTY OF EVERY CARD rather than of the cards anybody has
noticed. It renders a surface in real Chrome at a real width and, for each
card, finds the LARGEST SINGLE VERTICAL GAP inside it: between the bottom of
one laid-out child and the top of the next, and between the last child and the
card's content-box bottom. That one number catches both shapes of the defect
with no special cases:

  * a list clamped below what its card can show leaves the gap AFTER the last
    child (the tracker's bar-list cards, where the grid row stretched the card
    but a fixed `max-height` stopped the list from growing into it);
  * a card whose footer is pinned to the bottom leaves the gap in the MIDDLE
    (the press page's soundbite grid, where a short quote is stretched to the
    height of the longest quote in its row).

A metric that only looked below the last child would have scored the soundbite
card as perfect while half of it was blank.

WHAT IS NOT A DEFECT. Ordinary spacing between children is a gap too, so the
threshold has to sit above the largest deliberate margin on these surfaces
(~24px) and below the smallest gap anybody would call a band. GAP_LIMIT is
64px, which is more than two rows of deliberate spacing and less than one
bar-list row plus its label. A card that genuinely has less to say than its
row-mates is not padded with invented rows to satisfy this: it is allowed to
stop stretching, which closes the gap by making the card shorter rather than by
making the content longer.

WHAT IT CANNOT DO. It cannot check a page it was not pointed at. SURFACES is
the one thing here that a new PAGE has to be added to; a new CARD on a page
already listed is covered the day it ships, which is the whole point. Without
Chrome, or without the network, it raises rather than returning an empty pass:
absence of a signal is not a pass (CLAUDE.md).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cdp import Browser, CDPUnavailable  # noqa: E402

SITE = os.environ.get('WP_SITE_URL', 'https://asktherecruiter.com/blog').rstrip('/')

# The card components. One selector list for every surface: a new card built
# from an existing component is measured without editing this file.
CARD_SELECTOR = '.alt-chart-card, .alt-soundbite'

# Surfaces that render those components. This is the only registry a NEW PAGE
# has to join.
SURFACES = (
    ('tracker', '/ai-layoff-tracker/'),
    ('press', '/ai-layoff-tracker/press/'),
)

# Widths: the phone, where the grid collapses to one column and nothing
# stretches, and the desktop, where a grid row is as tall as its tallest card
# and every shorter card in that row is the one at risk.
WIDTHS = ((375, 812), (1280, 900))

# Above this many pixels, a gap inside a card is a band rather than spacing.
GAP_LIMIT = 64.0

MEASURE_JS = r"""
(function (selector) {
  var out = [];
  document.querySelectorAll(selector).forEach(function (card) {
    var cs = getComputedStyle(card);
    if (cs.display === 'none' || !card.getClientRects().length) return;
    var cr = card.getBoundingClientRect();
    var top = cr.top + parseFloat(cs.paddingTop) + parseFloat(cs.borderTopWidth);
    var bottom = cr.bottom - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth);

    // Laid-out, in-flow children only. A hidden note or an absolutely
    // positioned badge is not what holds the card open.
    var boxes = [];
    Array.prototype.forEach.call(card.children, function (kid) {
      var ks = getComputedStyle(kid);
      if (ks.display === 'none' || ks.position === 'absolute' || ks.position === 'fixed') return;
      if (kid.hidden) return;
      var kr = kid.getBoundingClientRect();
      if (kr.height <= 0) return;
      boxes.push({ top: kr.top, bottom: kr.bottom, tag: kid.className || kid.tagName });
    });
    if (!boxes.length) return;
    boxes.sort(function (a, b) { return a.top - b.top; });

    // Largest single vertical gap: before the first child, between any two
    // consecutive children, and after the last one.
    var worst = boxes[0].top - top, where = 'above first child';
    var reach = boxes[0].bottom;
    for (var i = 1; i < boxes.length; i++) {
      var g = boxes[i].top - reach;
      if (g > worst) { worst = g; where = 'before .' + String(boxes[i].tag).split(' ')[0]; }
      if (boxes[i].bottom > reach) reach = boxes[i].bottom;
    }
    var tail = bottom - reach;
    if (tail > worst) { worst = tail; where = 'below last child'; }

    // The card's own name, read from what it RENDERS, not from markup.
    var h = card.querySelector('.alt-chart-h, .alt-sb-label');
    var title = h ? h.textContent.replace(/\s+/g, ' ').trim().slice(0, 46) : '(untitled)';

    // A scrollable region inside the card is the elastic part: if one is
    // present and still has content out of view while the card has a band,
    // the card is clamped rather than empty.
    var elastic = null;
    var scroller = card.querySelector('.alt-barlist');
    if (scroller) {
      elastic = {
        height: +scroller.getBoundingClientRect().height.toFixed(1),
        content: +scroller.scrollHeight.toFixed(1),
        rows: scroller.querySelectorAll('.alt-barrow').length,
        clipped: scroller.scrollHeight > scroller.clientHeight + 1
      };
    }

    out.push({
      title: title,
      height: +cr.height.toFixed(1),
      gap: +worst.toFixed(1),
      where: where,
      elastic: elastic
    });
  });
  return JSON.stringify({ pageHeight: document.documentElement.scrollHeight, cards: out });
})(%s)
"""


def measure(url, width, height, settle=8.0):
    """Every card on one surface at one width. Raises if Chrome is unusable."""
    with Browser(width=width, height=height) as browser:
        browser.navigate(url, settle=settle)
        raw = browser.eval_js(MEASURE_JS % json.dumps(CARD_SELECTOR))
    return json.loads(raw)


def sweep(site=SITE, surfaces=SURFACES, widths=WIDTHS):
    """[(surface, width, result)] across every surface and width."""
    results = []
    for name, path in surfaces:
        for width, height in widths:
            results.append((name, width, measure(site + path, width, height)))
    return results


def offenders(results, limit=GAP_LIMIT):
    """Flat list of the cards whose worst gap is over the limit."""
    bad = []
    for name, width, res in results:
        for card in res['cards']:
            if card['gap'] > limit:
                bad.append((name, width, card))
    return bad


def _main():
    try:
        results = sweep()
    except CDPUnavailable as exc:
        print('UNKNOWN: no usable Chrome, nothing was measured (%s)' % exc)
        return 3
    for name, width, res in results:
        print('==== %s @ %dpx ====  page height %spx' % (name, width, res['pageHeight']))
        print('%-48s %8s %8s  %s' % ('card', 'height', 'gap', 'where'))
        for card in sorted(res['cards'], key=lambda c: -c['gap']):
            flag = '  <-- BAND' if card['gap'] > GAP_LIMIT else ''
            extra = ''
            if card['elastic']:
                extra = '  [list %.0f/%.0f, %d rows%s]' % (
                    card['elastic']['height'], card['elastic']['content'],
                    card['elastic']['rows'], ', clipped' if card['elastic']['clipped'] else '')
            print('%-48s %8.1f %8.1f  %s%s%s'
                  % (card['title'], card['height'], card['gap'], card['where'], extra, flag))
        print()
    bad = offenders(results)
    print('%d card(s) over the %.0fpx band limit' % (len(bad), GAP_LIMIT))
    return 2 if bad else 0


if __name__ == '__main__':
    raise SystemExit(_main())
