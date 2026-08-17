"""The signup form is a guest on other people's pages, so its colours are a
CONTRACT, and this pins it.

WHY THIS FILE EXISTS. Every colour in `alt_digest_subscribe_form()` is written
as `var(--alt-NAME, <light literal>)`: read the host page's site token, and fall
back to a light literal if the host does not declare it. That is the right
shape. It means the form takes on whatever palette the surrounding page uses,
and a page that answers nothing still gets a readable light form instead of an
unstyled one.

The half that is not self-enforcing is the word HOST. A surface that is DARK and
does not declare these names gets the light literals on a dark ground, and the
result is unreadable rather than merely plain.

That is not hypothetical. On 2026-08-15, 2.20.60 put this form on the pages
readers land on. One of them was the sibling product's dashboard, which is dark
capable and loads `dashboard.css`, where no `--alt-` name had ever existed. All
thirteen site tokens fell through to light literals on a #14161b ground and the
sibling's scheduled contrast audit went red the next morning: seven labels, two
legends and one summary at **1.02:1**, reported across two themes and two
viewports. Neither repository was wrong when read on its own. The form's comment
reasoned "the surfaces that have a dark mode all load layoffs.css", which was
true the day it was written. The defect lived only where the two plugins met,
which is exactly why every check on either side stayed green.

WHAT THIS TEST CAN AND CANNOT DO. It cannot see the sibling repository, so it
cannot prove that `dashboard.css` still answers. What it CAN do is make the
contract impossible to widen silently: the set of site tokens this form depends
on is pinned below, so adding a fourteenth is a loud, deliberate change that
names the other repository in its failure message. A token added here without a
matching declaration over there is precisely how 1.02:1 happened, and it would
otherwise be invisible until a scheduled audit caught it a day later.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FORM = REPO / "wordpress-plugin/ai-layoff-tracker/includes/subscribe.php"
LAYOFFS_CSS = REPO / "wordpress-plugin/ai-layoff-tracker/assets/layoffs.css"

# The site tokens the form reads from its host. Thirteen, as of 2.20.60.
#
# Adding to this set is a CROSS-REPOSITORY change. Every dark-capable surface
# that renders this form has to declare the new name too, and one of those
# surfaces lives in talent-intelligence-tracker (dashboard.css, which points
# each of these at its own theme-aware --tit-* token). Update both, or the new
# colour is a light literal on a dark ground.
PINNED_SITE_TOKENS = {
    "--alt-blue",
    "--alt-blue-dark",
    "--alt-border",
    "--alt-control-border",
    "--alt-crit",
    "--alt-crit-border",
    "--alt-ink",
    "--alt-ok-bg",
    "--alt-ok-ink",
    "--alt-on-accent",
    "--alt-red-tint",
    "--alt-surface",
    "--alt-tint-border",
}


def _form_source():
    return FORM.read_text(encoding="utf-8")


def _tokens_read(src):
    """Every --alt-* name the form resolves through var()."""
    return set(re.findall(r"var\(\s*(--alt-[a-z0-9-]+)", src))


def _tokens_declared(src):
    """Every --alt-* name the source declares for itself."""
    return set(re.findall(r"^\s*(--alt-[a-z0-9-]+)\s*:", src, re.M))


def site_tokens_required():
    """What the form needs its HOST to answer.

    Read minus self-declared. The `--alt-dg-*` component tokens are declared in
    the form's own style block, so they answer themselves and are not part of
    the contract.
    """
    src = _form_source()
    return _tokens_read(src) - _tokens_declared(src)


class TheFormStatesWhatItNeedsFromItsHost(unittest.TestCase):

    def test_the_contract_has_not_widened_without_the_sibling_being_told(self):
        actual = site_tokens_required()
        added = sorted(actual - PINNED_SITE_TOKENS)
        removed = sorted(PINNED_SITE_TOKENS - actual)
        self.assertEqual(
            actual,
            PINNED_SITE_TOKENS,
            "the signup form's host-token contract changed.\n"
            f"  newly required: {added}\n"
            f"  no longer required: {removed}\n"
            "Every dark-capable surface rendering this form must declare the "
            "names it reads. One of those surfaces is NOT in this repository: "
            "talent-intelligence-tracker's dashboard.css maps each of these to "
            "its own theme-aware --tit-* token. A name added here and not there "
            "resolves to the light literal on a dark ground, which is how seven "
            "labels reached 1.02:1 on 2026-08-16. Update dashboard.css in the "
            "sibling repo, then update PINNED_SITE_TOKENS here.",
        )

    def test_this_repo_answers_its_own_contract(self):
        css = LAYOFFS_CSS.read_text(encoding="utf-8")
        missing = sorted(
            t for t in site_tokens_required()
            if re.search(r"^\s*" + re.escape(t) + r"\s*:", css, re.M) is None
        )
        self.assertEqual(
            [], missing,
            "layoffs.css does not declare every site token the signup form "
            f"reads: {missing}. Tracker surfaces load this stylesheet, so a "
            "missing name here means the form falls back to a light literal on "
            "our own pages, in whichever theme the reader chose.",
        )

    def test_the_fallbacks_are_still_there(self):
        """A var() with no fallback is worse than the defect it replaced.

        Without a fallback an unanswered token resolves to the UNSET value: no
        border on the box, no fill on the button, a stock grey browser button,
        and an email field at 1.6:1. The fallback is what keeps an unanswered
        surface merely plain instead of broken.
        """
        src = _form_source()
        # SITE tokens only. The --alt-dg-* component tokens are read without a
        # fallback on purpose: they are declared a few lines above in this same
        # block, so they always resolve. A fallback on those would be a second
        # copy of a literal that already exists, which is how two copies of one
        # colour drift apart.
        required = site_tokens_required()
        naked = sorted(
            t for t in re.findall(r"var\(\s*(--alt-[a-z0-9-]+)\s*\)", src)
            if t in required
        )
        self.assertEqual(
            [], sorted(set(naked)),
            f"these HOST tokens are read with no fallback literal: {sorted(set(naked))}. "
            "Every site token this form reads must carry the site's own light "
            "literal as its second argument, so a surface that declares "
            "nothing still renders a readable form rather than an unstyled one.",
        )


if __name__ == "__main__":
    unittest.main()
