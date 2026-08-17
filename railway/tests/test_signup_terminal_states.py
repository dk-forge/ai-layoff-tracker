"""WHAT A READER SEES AFTER ACTING, WHICH IS NOT THE FORM AGAIN.

THE DEFECT, 2026-08-16. The owner completed the double opt-in for real: form,
confirmation email through Brevo, link click, address confirmed. It worked, and
the page he landed on printed

    "Your subscription is confirmed. The next digest will include you."

and then rendered THE WHOLE EMPTY SIGNUP FORM directly underneath it, with a
blank email field and a Subscribe button. To someone who has just subscribed
that reads as "it did not work, do it again". The ones who believe it submit
again, which parks a new pending_prefs row and mails a second confirmation for
an address that is already confirmed, so the empty form manufactures exactly
the traffic it appears to be asking for.

WHAT THIS FILE HOLDS. Four states replace the form (check, confirmed, updated,
unsubscribed) and every other state keeps it, because every other state is
something the reader has to do again. Plus the contents of the confirmation:
which digests, at what frequency, when the first one lands, and two quiet ways
to change their mind.

THE MARKUP IS THE REAL RENDERER'S OUTPUT. Every other rendered test in this
repo slices the component out of its file and strips PHP, which cannot answer
a question about which BRANCH ran: stripping PHP leaves both branches or
neither. So the states come from tests/fixtures/digest_harness.php driving
alt_digest_subscribe_form() with a real $_GET, after a real signup and a real
confirm through the real handlers.

AND THE PANEL IS THEN MEASURED IN A BROWSER, on the blog fixture that carries
the live page's ancestor chain and all three database stylesheets, because a
panel that replaces a form inherits the form's obligations: 44px controls, no
sideways bleed, AA contrast, and fitting a phone screen.

No PHP or no Chrome: these SKIP loudly. Absence of a signal is not a pass.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402
import contrast_audit  # noqa: E402

import test_blog_reading_surface as blog  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
SUBSCRIBE = PLUGIN / "includes/subscribe.php"
DIGEST_API = PLUGIN / "includes/digest-api.php"
HARNESS = Path(__file__).resolve().parent / "fixtures/digest_harness.php"

WIDTHS = (375, 414, 768, 1280)
TAP_MIN = 44.0
GAP_MIN = 8.0
AA_NORMAL = 4.5
AA_LARGE = 3.0

# The states that must NOT show a Subscribe form, and why each one.
TERMINAL = {
    "check": "we have just emailed them; submitting again sends nothing new",
    "confirmed": "they are subscribed; this is the state the owner landed on",
    "updated": "same, with their changed choices applied",
    "unsubscribed": "everything has stopped; a Subscribe button invites undoing it",
}
# The states that must KEEP it, because each is something to do again.
KEEPS_FORM = ("default", "expired", "lists", "email")

# The address the harness signs up with. It must never appear in a URL, in the
# receipt, or anywhere in the rendered page.
HARNESS_EMAIL = "reader@example.com"


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


PHP = _php()


def harness():
    if not PHP:
        raise unittest.SkipTest(
            "no php binary, so the states could not be rendered by the code "
            "that ships them. UNKNOWN, not a pass.")
    proc = subprocess.run([PHP, str(HARNESS), str(SUBSCRIBE), str(DIGEST_API)],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout.strip().splitlines()[-1])


def body_of(html):
    """The MARKUP, with the component's self-carried <style> removed.

    Every class this file looks for is also named inside that stylesheet, so
    searching the whole string finds `alt-digest-panel` in a CSS selector on a
    page that renders no panel. The first cut of this file did exactly that and
    reported the form and the panel present together in every state.
    """
    end = html.find("</style>")
    return html[end + len("</style>"):] if end >= 0 else html


def visible_text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body_of(html))).strip()


def is_inline_in_sentence(row):
    """A word inside a paragraph, which 44px is the wrong answer for: it opens
    a 44px hole in the sentence. WCAG 2.5.5 and 2.5.8 both carry the exception.
    Same test test_signup_reaches_landing_pages.py applies, same two halves: an
    anchor AND laid out by the browser as an inline box."""
    return row["tag"] == "a" and row["display"] == "inline"


class TheFormIsNotShownToSomebodyWhoAlreadyActed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.o = harness()
        cls.r = cls.o["rendered"]

    def test_no_terminal_state_renders_a_subscribe_form(self):
        bad = []
        for state, why in sorted(TERMINAL.items()):
            html = body_of(self.r[state])
            for needle, what in (("<form", "a form"),
                                 ('type="submit"', "a Subscribe button"),
                                 ('type="email"', "an empty email field")):
                if needle in html:
                    bad.append("%s still renders %s (%s)" % (state, what, why))
        self.assertEqual(
            [], bad,
            "a reader who has already acted is being shown the form again. An "
            "empty Subscribe form under 'your subscription is confirmed' reads "
            "as 'it did not work, do it again', and the readers who believe it "
            "submit twice:\n  " + "\n  ".join(bad))

    def test_every_terminal_state_renders_a_panel_instead(self):
        """Not merely the absence of a form: something has to be there."""
        for state in sorted(TERMINAL):
            with self.subTest(state=state):
                self.assertIn(
                    "alt-digest-panel", body_of(self.r[state]),
                    "the %s state removed the form and put nothing in its "
                    "place, which is a blank space where a reader expected an "
                    "answer" % state)

    def test_every_other_state_still_carries_the_form(self):
        """The other half. Each of these is a thing to do again, and a state
        machine that swallows the form on an error is worse than the defect."""
        bad = []
        for state in KEEPS_FORM:
            html = body_of(self.r[state])
            if "<form" not in html or 'type="submit"' not in html:
                bad.append("%s renders no form" % state)
            if "alt-digest-panel" in html:
                bad.append("%s renders a terminal panel" % state)
        self.assertEqual(
            [], bad,
            "a state a reader has to retry from is missing its form:\n  "
            + "\n  ".join(bad))

    def test_a_used_confirm_link_does_not_read_as_a_failure(self):
        """A confirm token is cleared the moment it is spent, so the ordinary
        way to land here is clicking the same link twice, or clicking it after
        a mail scanner already followed it. That is success, described badly."""
        text = visible_text(self.r["expired"])
        self.assertIn(
            "already been used", text,
            "the stale-link state does not say the link was already used: %r"
            % text[:200])
        self.assertIn(
            "confirmed already", text,
            "the stale-link state does not offer the overwhelmingly likely "
            "explanation, which is that the reader is already subscribed: %r"
            % text[:200])
        status = re.search(r'<div class="alt-digest-status([^"]*)"',
                           body_of(self.r["expired"]))
        self.assertIsNotNone(status, "the stale-link state renders no status box")
        self.assertNotIn(
            "alt-digest-status-error", status.group(1),
            "the stale-link state is still painted as an error. It is the "
            "normal result of clicking a one-time link twice, and a red box "
            "tells a reader who is already subscribed that something broke.")


class TheConfirmationSaysWhatTheyActuallyGet(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.o = harness()
        cls.r = cls.o["rendered"]

    def test_it_names_the_digests_they_picked_and_only_those(self):
        text = visible_text(self.r["confirmed"])
        # The harness signs up for layoff + articles, not talent.
        self.assertIn("AI Layoff Tracker digest", text)
        self.assertIn("Occasional articles and product news", text)
        self.assertNotIn(
            "Talent Intelligence Tracker digest", text,
            "the confirmation lists a digest the reader did not tick. It must "
            "read back the stored row, not the menu: %r" % text[:300])

    def test_it_says_when_the_first_one_arrives(self):
        text = visible_text(self.r["confirmed"])
        self.assertIn(
            "Weekly digests go out on Monday mornings", text,
            "the confirmation sets no expectation about when anything "
            "arrives, which is the question a person has right after "
            "subscribing: %r" % text[:300])

    def test_it_offers_both_ways_to_change_their_mind(self):
        html = body_of(self.r["confirmed"])
        self.assertIn("Change your choices", html)
        self.assertIn(">Unsubscribe<", html)
        # Asserted as "a URL that carries a token and names the action",
        # not as one spelling of it. This pinned `alt_digest_unsub`, the
        # query-arg shape, until 2.20.76 moved the link off admin-post.php,
        # and a test that names one shape fails the day the shape improves
        # while proving nothing about whether the link works. What makes it a
        # control rather than a word is the href and the token in it.
        m = re.search(r'href="([^"]*)"[^>]*>Unsubscribe<', html)
        self.assertTrue(
            m, "the Unsubscribe text on the confirmation is not a link at "
               "all, so it is a word rather than a control")
        href = m.group(1)
        self.assertRegex(
            href, r"(unsubscribe|alt_digest_unsub)",
            "the Unsubscribe link points at %r, which does not name the "
            "unsubscribe action" % href)
        self.assertRegex(
            href, r"[a-f0-9]{64}",
            "the Unsubscribe link %r carries no token, so it cannot identify "
            "the row it is meant to stop" % href)

    def test_without_a_receipt_it_states_the_fact_and_invents_nothing(self):
        """Thirty minutes later, or on a hand-typed URL. It must not guess."""
        text = visible_text(self.r["confirmed_no_receipt"])
        self.assertIn("Your subscription is confirmed", text)
        for name in ("AI Layoff Tracker digest",
                     "Talent Intelligence Tracker digest",
                     "Occasional articles and product news"):
            self.assertNotIn(
                name, text,
                "with no receipt the panel still claims the reader is "
                "subscribed to %r. It knows nothing about their choices here "
                "and must say nothing about them." % name)
        self.assertNotIn(
            ">Unsubscribe<", body_of(self.r["confirmed_no_receipt"]),
            "the panel offers an unsubscribe link with no token behind it")


class TheReceiptNamesNobody(unittest.TestCase):
    """The confirmation page has to read preferences back without a session,
    and the address may never travel in a URL. This is the part of that which
    could go wrong quietly."""

    @classmethod
    def setUpClass(cls):
        cls.o = harness()

    def test_the_confirm_redirect_carries_a_receipt_and_not_an_address(self):
        url = self.o["confirm_redirect_url"]
        self.assertRegex(
            url, r"alt_r=[a-f0-9]{64}",
            "the confirm redirect carries no receipt token, so the page it "
            "lands on cannot say what the reader subscribed to: %r" % url)
        local = HARNESS_EMAIL.split("@")[0]
        for needle in (HARNESS_EMAIL, HARNESS_EMAIL.replace("@", "%40"), local):
            self.assertNotIn(
                needle, url,
                "the confirm redirect leaks %r into a URL. The address may "
                "never travel in one: it lands in browser history, in any "
                "referrer, and in every proxy log on the way. URL was: %r"
                % (needle, url))

    def test_the_receipt_holds_choices_and_nothing_that_names_a_person(self):
        store = self.o["confirm_receipt_store"]
        self.assertIsInstance(
            store, dict,
            "the confirm handler wrote no receipt transient, so the panel "
            "falls back to saying nothing about the reader's choices")
        self.assertEqual(
            sorted(store.keys()), ["freq", "lists", "unsub"],
            "the receipt holds %r. It may hold the list flags, the frequency "
            "and the row's unsubscribe token, and nothing else: no address, "
            "no row id, nothing that names a person." % (sorted(store.keys()),))
        blob = json.dumps(store)
        for needle in (HARNESS_EMAIL, HARNESS_EMAIL.split("@")[0]):
            self.assertNotIn(needle, blob,
                             "the receipt stores %r" % needle)
        self.assertEqual(sorted(store["lists"]), ["articles", "layoff"],
                         "the receipt does not match what was ticked: %r" % (store,))

    def test_the_rendered_confirmation_never_prints_the_address(self):
        o = harness()
        for state, html in o["rendered"].items():
            with self.subTest(state=state):
                self.assertNotIn(
                    HARNESS_EMAIL, body_of(html),
                    "the %s state prints the subscriber's address on a public "
                    "page. Nothing here needs it and a shoulder is enough to "
                    "read it." % state)


# --------------------------------------------------------------- rendered

PROBE = "(function () {" + contrast_audit._COLOR_JS + r"""
  var SEL = 'a[href], button, input:not([type="hidden"]), select, textarea,'
          + ' summary, [tabindex]:not([tabindex="-1"]), label:has(input)';
  var sec = document.querySelector('#alt-digest');
  if (!sec) return JSON.stringify({missing: true});
  var panel = sec.querySelector('.alt-digest-panel');
  var targets = [];
  Array.prototype.forEach.call(sec.querySelectorAll(SEL), function (el) {
    var cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    var r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.left + r.width <= 0) return;              // the honeypot, off screen
    var p = el.parentElement, nested = false;
    while (p && p !== sec) { if (p.matches(SEL)) nested = true; p = p.parentElement; }
    if (nested) return;
    targets.push({tag: el.tagName.toLowerCase(), display: cs.display,
                  text: (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40),
                  w: +r.width.toFixed(1), h: +r.height.toFixed(1),
                  x: +(r.left + scrollX).toFixed(1), y: +(r.top + scrollY).toFixed(1)});
  });
  var texts = [];
  var panelTexts = [];
  Array.prototype.forEach.call(sec.querySelectorAll('h2, p, li, a, div, summary'),
    function (el) {
      var own = '';
      Array.prototype.forEach.call(el.childNodes, function (n) {
        if (n.nodeType === 3) own += n.nodeValue;
      });
      if (!own.trim()) return;
      var cs = getComputedStyle(el);
      var back = backdrop(el);
      var ink = over(parse(cs.color), back.color);
      var row = {tag: el.tagName, color: rgbstr(ink), bg: rgbstr(back.color),
                 ratio: +ratio(ink, back.color).toFixed(2),
                 fs: parseFloat(cs.fontSize), fw: cs.fontWeight,
                 text: own.replace(/\s+/g, ' ').trim().slice(0, 46)};
      texts.push(row);
      // The panel's OWN lines. The section heading above it is a heading and
      // is sized by the article's scale on purpose (section 8b), so sweeping
      // the whole section for "nothing is at body size" would report it.
      if (panel && panel.contains(el)) panelTexts.push(row);
    });
  var r = sec.getBoundingClientRect();
  // The panel's own bottom edge. The <details> below it ships CLOSED and is
  // opened only for the tap sweep, so measuring the section's full height for
  // the fold would report an expanded privacy note nobody has opened.
  var pr = panel ? panel.getBoundingClientRect() : null;
  return JSON.stringify({
    vw: innerWidth, vh: innerHeight,
    overflow: +(document.documentElement.scrollWidth
                - document.documentElement.clientWidth).toFixed(1),
    section: {top: +(r.top + scrollY).toFixed(1), h: +r.height.toFixed(1),
              left: +r.left.toFixed(1), right: +r.right.toFixed(1)},
    panelBottom: pr ? +(pr.bottom + scrollY).toFixed(1) : null,
    targets: targets, texts: texts, panelTexts: panelTexts
  });
})()
"""


def page_with(html_block):
    """The blog fixture with this state's REAL markup where the_content puts
    it: the last child of the article."""
    page = blog.build_page(with_fix=True)
    idx = page.rfind('<h2 class="wp-block-heading"')
    assert idx >= 0, "the blog fixture changed shape"
    close = page.find("</div>", page.find("</p>", idx))
    assert close >= 0
    page = page[:close] + html_block + page[close:]
    return page.replace("</head>",
                        "<style>%s</style></head>" % contrast_audit.FREEZE_CSS)


def adjacent_pairs(rows):
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            dx = max(0.0, max(a["x"] - (b["x"] + b["w"]), b["x"] - (a["x"] + a["w"])))
            dy = max(0.0, max(a["y"] - (b["y"] + b["h"]), b["y"] - (a["y"] + a["h"])))
            if dx > 0 and dy > 0:
                continue
            out.append((dx + dy, a, b))
    return out


def describe(row):
    return "%s %r %.1fx%.1f at (%.0f,%.0f)" % (
        row["tag"], row["text"][:28], row["w"], row["h"], row["x"], row["y"])


class _RenderedStates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the terminal-state "
                "panels could not be measured. UNKNOWN, not a pass.")
        cls.states = harness()["rendered"]
        cls._cache = {}

    def rendered(self, state, width, height, open_details=False):
        key = (state, width, height, open_details)
        if key in self._cache:
            return self._cache[key]
        html = page_with(self.states[state])
        try:
            with Browser(width=width, height=height) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                if open_details:
                    # A closed <details> hides the privacy note's own link, and
                    # a reader who opens the disclosure has to be able to hit
                    # what is inside it. Only the tap sweep wants this.
                    page.eval_js(
                        "(function(){document.querySelectorAll('details')"
                        ".forEach(function(d){d.open=true;});return 1;})()")
                data = json.loads(page.eval_js(PROBE))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self.assertFalse(data.get("missing"),
                         "the %s state rendered nothing at %dpx" % (state, width))
        self._cache[key] = data
        return data


class EveryPanelControlIsStillAControl(_RenderedStates):
    """A panel that stands where a form stood inherits the form's bars."""

    STATES = ("check", "confirmed", "unsubscribed")

    def test_the_sweep_found_something_to_measure(self):
        for state in self.STATES:
            rows = self.rendered(state, 375, 812, open_details=True)["targets"]
            self.assertGreater(
                len(rows), 1,
                "only %d interactive target(s) in the %s panel, so this run "
                "measured almost nothing. UNKNOWN, not a pass."
                % (len(rows), state))

    def test_no_panel_control_is_under_44px(self):
        bad = []
        for state in self.STATES:
            for width in WIDTHS:
                d = self.rendered(state, width, 812 if width < 768 else 900,
                                  open_details=True)
                for r in d["targets"]:
                    if is_inline_in_sentence(r):
                        continue
                    if r["h"] < TAP_MIN - 0.05 or r["w"] < TAP_MIN - 0.05:
                        bad.append("%s at %dpx: %s" % (state, width, describe(r)))
        self.assertEqual(
            [], bad,
            "%d control(s) in a terminal panel below %.0fx%.0f (WCAG 2.5.5). "
            "These links are standalone actions, not words inside a sentence, "
            "so the 2.5.5 exception the intro's links use does not apply and "
            "they take the height in full:\n  %s"
            % (len(bad), TAP_MIN, TAP_MIN, "\n  ".join(bad)))

    def test_change_and_unsubscribe_are_not_a_mis_tap_apart(self):
        bad = []
        for width in WIDTHS:
            rows = [r for r in self.rendered(
                        "confirmed", width, 812 if width < 768 else 900,
                        open_details=True)["targets"]
                    if not is_inline_in_sentence(r)]
            for dist, a, b in adjacent_pairs(rows):
                if dist < GAP_MIN - 0.2:
                    bad.append("%dpx, %.1fpx apart: %s  |  %s"
                               % (width, dist, describe(a), describe(b)))
        self.assertEqual(
            [], bad,
            "two neighbouring controls in the confirmation panel are under "
            "%.0fpx apart. 'Change your choices' and 'Unsubscribe' are the "
            "worst pair on this site to take a wrong tap between:\n  %s"
            % (GAP_MIN, "\n  ".join(bad)))

    def test_no_panel_bleeds_sideways(self):
        bad = []
        for state in self.states:
            for width in WIDTHS:
                d = self.rendered(state, width, 812 if width < 768 else 900)
                if d["overflow"] > 0.5:
                    bad.append("%s at %dpx: document %.1fpx wider than the viewport"
                               % (state, width, d["overflow"]))
                s = d["section"]
                if s["left"] < -0.5 or s["right"] > d["vw"] + 0.5:
                    bad.append("%s at %dpx: block spans %.1f to %.1f in %dpx"
                               % (state, width, s["left"], s["right"], d["vw"]))
        self.assertEqual([], bad, "a signup state bleeds sideways:\n  "
                                  + "\n  ".join(bad))

    def test_every_panel_fits_one_phone_screen(self):
        """The repeated defect, applied to the new markup. A confirmation a
        reader has to scroll to finish reading is a confirmation they do not
        finish reading."""
        bad = []
        for state in self.STATES + ("updated",):
            d = self.rendered(state, 375, 812)
            self.assertIsNotNone(
                d["panelBottom"],
                "the %s state rendered no panel to measure" % state)
            reach = d["panelBottom"] - d["section"]["top"]
            if reach > 812:
                bad.append("%s: the confirmation ends %.1fpx down an 812px "
                           "screen" % (state, reach))
        self.assertEqual(
            [], bad,
            "a terminal state does not fit one phone screen even scrolled to "
            "its own top:\n  " + "\n  ".join(bad))


class ThePanelIsOnTheComponentScaleNotTheArticleBody(_RenderedStates):
    """THE SAME CASCADE TRAP THE INTRO AND THE APPLAUSE NOTE BOTH FELL INTO.

    The panel declares 14px sans in its own <style>. On an article that rule is
    (0,1,0) and assets/blog-reading.css section 3 declares `.entry-content p`
    at (0,2,2) !important, so before section 8b named the panel the readout
    measured, on this fixture:

        .alt-digest-panel-lead    19.0 / 22.0px  Manrope
        .alt-digest-panel li      19.0 / 22.0px  VOLLKORN
        .alt-digest-panel p       19.0 / 22.0px  Manrope

    A confirmation set in the article's own body size and half of it in the
    article's serif does not read as an interface answering a reader, it reads
    as two more paragraphs of the piece they were reading.
    """

    # Component-scale, not article-scale. The intro this panel replaces is
    # 15px on this page, so anything at or under 16 is on the right side of the
    # line and 19 is the recorded defect.
    PANEL_PX_MAX = 16.0

    def test_no_line_of_the_panel_is_set_at_article_body_size(self):
        bad = []
        for state in ("check", "confirmed", "unsubscribed"):
            for width in WIDTHS:
                d = self.rendered(state, width, 812 if width < 768 else 900)
                for t in d["panelTexts"]:
                    if t["fs"] > self.PANEL_PX_MAX + 0.05:
                        bad.append("%s at %dpx: %s %r at %.1fpx"
                                   % (state, width, t["tag"], t["text"], t["fs"]))
        self.assertEqual(
            [], bad,
            "part of a terminal panel is set at the ARTICLE's body size rather "
            "than the component's. `.entry-content p` and `.entry-content li` "
            "are (0,2,2) !important in assets/blog-reading.css, so the panel's "
            "own (0,1,0) rules never applied:\n  " + "\n  ".join(bad))

    def test_the_readout_is_not_in_the_article_serif(self):
        """The `li` half specifically. Section 8b's older rule listed p, label,
        legend and summary and no list item, so the two digests a reader just
        subscribed to came out in Vollkorn between two lines of Manrope."""
        bad = []
        for width in (375, 1280):
            d = self.rendered("confirmed", width, 812 if width < 768 else 900)
            fams = json.loads(self._families(width))
            for sel, fam in fams.items():
                if fam and fam.split(",")[0].strip('"\' ') not in (
                        "Manrope", "ui-sans-serif", "system-ui"):
                    bad.append("%dpx: %s renders in %s" % (width, sel, fam.split(",")[0]))
        self.assertEqual(
            [], bad,
            "the confirmation readout is set in the article's serif:\n  "
            + "\n  ".join(bad))

    def _families(self, width):
        html = page_with(self.states["confirmed"])
        js = ("(function(){var o={};"
              "['.alt-digest-panel-lead','.alt-digest-panel li',"
              "'.alt-digest-panel p','.alt-digest-panel-actions a']"
              ".forEach(function(s){var e=document.querySelector(s);"
              "o[s]=e?getComputedStyle(e).fontFamily:null;});"
              "return JSON.stringify(o);})()")
        try:
            with Browser(width=width, height=900) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                return page.eval_js(js)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)


class EveryPanelMeetsAA(_RenderedStates):

    def test_every_line_of_every_state_meets_aa(self):
        bad = []
        for state in self.states:
            for width in (375, 1280):
                d = self.rendered(state, width, 812 if width < 768 else 900)
                self.assertTrue(d["texts"],
                                "the %s state rendered no text at all" % state)
                for t in d["texts"]:
                    need = (AA_LARGE if (t["fs"] >= 24 or
                                         (t["fs"] >= 18.66 and int(t["fw"]) >= 700))
                            else AA_NORMAL)
                    if t["ratio"] < need - 0.005:
                        bad.append("%s %dpx %s %r: %s on %s = %.2f:1, need %.1f"
                                   % (state, width, t["tag"], t["text"],
                                      t["color"], t["bg"], t["ratio"], need))
        self.assertEqual(
            [], bad,
            "a signup state fails WCAG 1.4.3 on an article:\n  "
            + "\n  ".join(bad))


if __name__ == "__main__":
    unittest.main()
