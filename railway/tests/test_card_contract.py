"""THE RESULT CARD IS DEFINED ONCE, IN docs/card-contract.json, AND THIS PINS IT.

WHY THIS TEST EXISTS, stated plainly, because the reason is the whole design.

This tracker and its sibling, the Talent Intelligence Tracker, render the same
kind of fact: an employer, a place, a direction, an evidence tier, an amount, a
headline, a source. The owner screenshotted the sibling's list, liked it, and
asked for this one to match. By the time anybody looked, the sibling had already
changed its own labels, so neither side could say which design was current. The
mismatch was not the defect. THE INABILITY TO SAY WHICH ONE WAS CURRENT was the
defect, and shipping matching pixels once would have fixed nothing: they would
have drifted again in a fortnight, exactly as they had already drifted once.

So the card is defined ONCE, as data, in docs/card-contract.json, and that file
is byte-identical in both repositories. Not shared code: the two products have
different tables, different REST namespaces, different plugins and different
deploy paths, and coupling them through a library would buy a smaller problem at
the price of a much worse one. A shared CONTRACT, and a test on each side that
fails when its own markup stops matching it.

THREE THINGS HOLD IT TOGETHER, and each covers what the others cannot:

  1. This test, offline, on every push. It reads the contract and asserts that
     the markup this repo actually renders satisfies it. It cannot see the
     sibling.
  2. The digest below, and a second copy of it in docs/TECHLOG.md. Editing the
     contract without meaning to fails here; editing it deliberately means
     updating the digest, which is the moment you are told this is a two-repo
     change.
  3. .github/workflows/card-contract.yml, which fetches the sibling's copy of
     the contract and goes red while the two differ. That is the only one of
     the three that can see across the repo boundary, which is why it needs a
     network and lives in CI rather than here.

CHANGING THE CARD IS THEREFORE A FOUR-STEP JOB, and the point of the design is
that you cannot do three of them and ship: edit the contract, update the digest
here and in TECHLOG, change the markup, and copy the contract into the sibling.
Miss the last step and both repos go red until somebody finishes.
"""
import hashlib
import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
CONTRACT_PATH = os.path.join(ROOT, "docs", "card-contract.json")
TECHLOG_PATH = os.path.join(ROOT, "docs", "TECHLOG.md")
LAYOFFS_JS = os.path.join(
    ROOT, "wordpress-plugin", "ai-layoff-tracker", "assets", "layoffs.js"
)
LAYOFFS_CSS = os.path.join(
    ROOT, "wordpress-plugin", "ai-layoff-tracker", "assets", "layoffs.css"
)

# The contract as this repo last agreed to it. If this fails, the file changed:
# either you meant it (update this, update TECHLOG, and copy the file to the
# sibling) or you did not (revert).
CONTRACT_SHA256 = "5ce62ea8d11073b132af83696e222f0a2c4184fba646c5f0adcb9c06f7493af2"

PREFIX = "alt"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _strip_line_comments(src):
    """
    Prose about the card is not the card. Every assertion below that reads
    ORDER or asks whether a string is rendered runs on the code only, or a
    comment explaining why a badge was removed would count as the badge.
    """
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def _card_html_source(js):
    """The body of cardHtml(), which is the only place this repo builds a card."""
    start = js.index("function cardHtml(row, i) {")
    end = js.index("\n    function renderCards()", start)
    return _strip_line_comments(js[start:end])


def _card_template(js):
    """
    The return expression of cardHtml(): the concatenation that becomes the
    card. This, and not the order the local variables happen to be declared in,
    is the order a reader meets the card in.
    """
    card = _card_html_source(js)
    return card[card.index("return '<li class=\"alt-card\"") :]


# What each contract slot looks like INSIDE that return expression. Most are the
# class itself; a few are a local variable because the element is built a few
# lines above. If a rename makes one of these miss, the test says so and this map
# is the one place to fix it.
TEMPLATE_TOKEN = {
    "card": r'<li class="alt-card"',
    "card-rail": r'class="alt-card-rail"',
    "card-employer": r'class="alt-card-employer"',
    "card-industry": r"\bindustry\b",
    "card-where": r'class="alt-card-where"',
    "card-body": r'class="alt-card-body"',
    "card-badges": r'class="alt-card-badges"',
    "card-dir": r"\bdir\b",
    "card-ev": r"\bverificationBadge\(",
    "card-amt": r"\bjobs\b",
    "card-h": r"\bhead\b",
    "card-rt": r'class="alt-card-rt"',
    "card-foot": r'class="alt-card-foot"',
    "card-when": r'class="alt-card-when"',
    "card-src": r'class="alt-card-src"',
}


class ContractFileIsPinned(unittest.TestCase):
    """The file itself, before anything that reads it."""

    def test_contract_parses_and_matches_its_digest(self):
        raw = open(CONTRACT_PATH, "rb").read()
        json.loads(raw)  # a contract that does not parse is not a contract
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            CONTRACT_SHA256,
            "docs/card-contract.json changed. This file is byte-identical in the "
            "sibling talent-intelligence-tracker repo and a change here is a "
            "change there: update CONTRACT_SHA256, update the digest recorded in "
            "docs/TECHLOG.md, and copy the file across. card-contract.yml goes "
            "red in BOTH repos until the two copies agree.",
        )

    def test_techlog_records_the_same_digest(self):
        """A spec doc that can disagree with the file it specifies is decoration."""
        self.assertIn(
            CONTRACT_SHA256,
            _read(TECHLOG_PATH),
            "docs/TECHLOG.md carries the canonical spec and must quote the "
            "digest of the contract it describes.",
        )

    def test_contract_names_this_product(self):
        contract = json.loads(_read(CONTRACT_PATH))
        prefixes = [p["prefix"] for p in contract["products"]]
        self.assertIn(PREFIX, prefixes)


class CardStructureMatchesTheContract(unittest.TestCase):
    """The markup this repo renders, read out of the renderer itself."""

    def setUp(self):
        self.contract = json.loads(_read(CONTRACT_PATH))
        self.js = _read(LAYOFFS_JS)
        self.card = _card_html_source(self.js)
        self.template = _card_template(self.js)

    def _at(self, suffix):
        m = re.search(TEMPLATE_TOKEN[suffix], self.template)
        self.assertIsNotNone(
            m,
            "the card template does not build %s. If this is a rename rather "
            "than a removal, update TEMPLATE_TOKEN." % suffix,
        )
        return m.start()

    def _required_suffixes(self):
        s = self.contract["structure"]
        out = [s["list"]["suffix"], s["card"]["suffix"]]
        out += s["card"]["children"]
        for region in ("rail", "body", "foot"):
            out += s[region]["required_children"]
        out += self.contract["badges"]["order"]
        out.append(self.contract["not_stated"]["class"])
        return out

    def test_every_required_class_is_rendered(self):
        for suffix in self._required_suffixes():
            cls = "%s-%s" % (PREFIX, suffix)
            self.assertIn(
                cls,
                self.js,
                "the shared card contract requires a %s element and this repo "
                "renders none" % cls,
            )

    def test_badges_are_rendered_in_the_contract_order(self):
        """Direction, then evidence, then the amount. Always, and in that order."""
        order = self.contract["badges"]["order"]
        at = [self._at(s) for s in order]
        self.assertEqual(
            at,
            sorted(at),
            "the badge row must render %s in that order (docs/card-contract.json "
            "-> badges.order). Product-specific badges follow them."
            % ", ".join(order),
        )

    def test_the_badge_row_places_them_before_this_products_own_badges(self):
        """The AI badge and the reason tags come AFTER the three shared ones."""
        row = re.search(
            r'<div class="alt-card-badges">\'\s*\n(.*?)\n\s*\+\s*\'</div>',
            self.template,
            re.S,
        )
        self.assertIsNotNone(row, "could not find the badge row in cardHtml()")
        body = row.group(1)
        for shared, own in (("dir", "aiBadge"), ("jobs", "tags")):
            self.assertLess(
                body.index(shared),
                body.index(own),
                "the shared badges lead the row; this product's own follow",
            )

    def test_each_region_renders_in_the_contract_reading_order(self):
        for region in ("rail", "body", "foot"):
            order = self.contract["structure"][region]["reading_order"]
            at = [self._at(s) for s in order]
            self.assertEqual(
                at,
                sorted(at),
                "the %s renders out of contract order; it must read %s"
                % (region, ", ".join(order)),
            )

    def test_the_amount_badge_is_absent_when_there_is_no_amount(self):
        """
        Not a pill reading "count not stated". The direction badge already says
        so, and two badges saying one thing is the duplicate the contract removed.
        """
        self.assertNotIn("Count not stated", _strip_line_comments(self.js))
        self.assertRegex(
            self.card,
            r"n > 0\s*\n\s*\?\s*'<span class=\"alt-card-amt",
            "the amount badge must be built only when there is an amount",
        )


class LabelsMatchTheContract(unittest.TestCase):
    """The words. This is the part that drifted."""

    def setUp(self):
        self.contract = json.loads(_read(CONTRACT_PATH))
        self.js = _read(LAYOFFS_JS)

    def _js_direction_labels(self):
        block = re.search(r"var DIRECTION_LABEL = \{(.*?)\};", self.js, re.S)
        self.assertIsNotNone(block, "layoffs.js declares no DIRECTION_LABEL")
        return dict(
            re.findall(r"(\w+)\s*:\s*'([^']*)'", block.group(1))
        )

    def test_direction_labels_are_exactly_the_shared_four(self):
        self.assertEqual(
            self._js_direction_labels(),
            self.contract["direction_labels"],
            "DIRECTION_LABEL in layoffs.js must equal direction_labels in "
            "docs/card-contract.json exactly. These four strings are shared with "
            "the sibling talent tracker and changing one here changes it there.",
        )

    def test_the_directions_this_product_uses_are_declared(self):
        """
        Every row here is a cut, so two of the four never appear. They are absent
        by declaration, never renamed and never reused for something else.
        """
        declared = set(
            [p for p in self.contract["products"] if p["prefix"] == PREFIX][0][
                "directions_used"
            ]
        )
        used = set(re.findall(r"return Number\(row\.job_count.*", self.js))
        self.assertTrue(used, "cardDirection() is gone")
        self.assertEqual(declared, {"displacement", "neutral"})
        for key in declared:
            self.assertIn("'%s'" % key, self.js)

    def test_evidence_labels_are_the_ones_the_contract_records(self):
        block = re.search(r"var VERIF_LABELS = \{(.*?)\};", self.js, re.S)
        self.assertIsNotNone(block)
        found = dict(re.findall(r"(\w+)\s*:\s*'([^']*)'", block.group(1)))
        self.assertEqual(found, self.contract["evidence_labels"][PREFIX])

    def test_the_not_stated_strings_are_shared_verbatim(self):
        for key in ("location", "date"):
            text = self.contract["not_stated"][key]
            self.assertIn(text, self.js, "%r is a shared string" % text)

    def test_no_em_dash_in_any_contract_label(self):
        for group in (
            self.contract["direction_labels"],
            self.contract["evidence_labels"][PREFIX],
            self.contract["not_stated"],
        ):
            for key, text in group.items():
                if key in ("note", "class"):
                    continue
                self.assertNotIn("\u2014", text)
                self.assertNotIn("\u2013", text)


class AccessibilityDoesNotRegress(unittest.TestCase):
    """Two real defects, both fixed once, both cheap to reintroduce."""

    def setUp(self):
        self.js = _read(LAYOFFS_JS)
        self.card = _card_html_source(self.js)

    def test_the_expander_is_a_real_button_carrying_aria_expanded(self):
        """
        It was a click handler on a <tr>, which no keyboard could reach. It is a
        <button type=button aria-expanded> and it stays one.
        """
        self.assertRegex(
            self.card,
            r'<button type="button" class="alt-card-more" aria-expanded="false">',
            "the card's detail expander must be a real button with aria-expanded",
        )
        self.assertIn(
            "btn.setAttribute('aria-expanded'", self.js,
            "the handler must keep aria-expanded in step with the panel",
        )

    def test_no_aria_label_overrides_visible_card_text(self):
        """
        An aria-label on an element that already has text REPLACES that text for
        a screen reader. The sibling shipped longer, invisible, differently
        worded labels over its visible ones. Inside a card, an aria-label is only
        ever allowed on an element with no text of its own.
        """
        self.assertNotIn(
            "aria-label",
            self.card,
            "no element inside the card carries an aria-label today, and none "
            "should be added over visible text. If you need one on an icon-only "
            "control, allowlist it here with the reason.",
        )

    def test_the_source_link_opens_out_safely(self):
        js = self.js
        self.assertIn('rel="noopener nofollow"', js)
        self.assertIn('target="_blank"', js)


class MobileHasNothingToClip(unittest.TestCase):
    """
    375px, and NOT by comparing scrollWidth to innerWidth: that comparison passes
    on a clipped page, and this site ships an inline html,body{overflow-x:hidden}
    from its theme, which makes it meaningless here anyway. What is checkable
    offline is the cause rather than the symptom: nothing inside a card may pin a
    width the viewport cannot give it.
    """

    def test_no_card_rule_sets_a_min_width(self):
        css = _read(LAYOFFS_CSS)
        block = css[css.index(".alt-cards {") : css.index(".alt-pager {")]
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("/*") or stripped.startswith("*"):
                continue
            # A breakpoint is the opposite of the failure this guards: it is how
            # the rail becomes a column ABOVE 700px and stays stacked below it.
            if stripped.startswith("@media"):
                continue
            self.assertNotIn(
                "min-width:",
                line.replace("min-width: 0", "").replace("min-width:0", ""),
                "a card may not pin a width a 375px viewport cannot give it: %s"
                % line.strip(),
            )

    def test_long_values_wrap_rather_than_overflow(self):
        css = _read(LAYOFFS_CSS)
        for selector in (".alt-card-employer", ".alt-card-h", ".alt-card-src"):
            at = css.index(selector)
            self.assertIn(
                "overflow-wrap: anywhere",
                css[at : at + 400],
                "%s holds arbitrary-length values and must wrap" % selector,
            )


if __name__ == "__main__":
    unittest.main()
