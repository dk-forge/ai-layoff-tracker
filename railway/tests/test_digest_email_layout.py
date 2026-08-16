"""What the digest looks like when it reaches a person, and when it reaches
the person THEY forward it to.

WHY THIS FILE IS MOSTLY ABOUT FORWARDING.

Gmail, Outlook.com and most webmail strip `<head>` and every `<style>` block
when a message is forwarded or quoted. A design that lives in a stylesheet
looks right in the inbox and collapses the moment a reader passes it on, which
for a data digest read by recruiters and journalists is the single most likely
thing to happen to it. So the property under test is not "does it look nice".
It is: DELETE THE HEAD AND EVERY STYLE BLOCK, AND NOTHING CHANGES.

That is checkable, so it is checked here rather than admired in a review.

The rest follows from the same constraint. Outlook on Windows renders through
Word, which has no flexbox, no grid and no CSS positioning, so the layout is
tables. Media queries die on a forward too, so none of them may be carrying
the layout. And the privacy promise is unchanged and unweakened: no image, no
pixel, no url(), no remote anything, enforced where it already was.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_layout as layout           # noqa: E402
import digest_send                       # noqa: E402
import digest_transport as dt            # noqa: E402

UNSUB = ("https://asktherecruiter.com/blog/wp-admin/admin-post.php"
         "?action=alt_digest_unsub&t=" + "a" * 64)
MANAGE = "https://asktherecruiter.com/blog/ai-layoff-tracker/#alt-digest"
FROM = "AskTheRecruiter Trackers <digest@asktherecruiter.com>"
REPLY = "info@asktherecruiter.com"

# The exact shape the site's own composers emit (includes/subscribe.php,
# alt_digest_compose_layoff / _talent / _articles). Copied rather than
# imagined, because a layout that only survives invented input survives
# nothing.
LAYOFF_HTML = (
    '<h2 style="font-size:16px;margin:24px 0 8px;">AI Layoff Tracker</h2>'
    '<p style="margin:0 0 8px;">312 verified entries totalling 48,910 job cuts '
    'across 274 companies in this period.</p>'
    '<ul style="margin:0 0 8px;padding-left:20px;">'
    '<li>Acme Robotics: 1,200 jobs, Austin, TX</li>'
    '<li>Northwind Health: 940 jobs, Ohio</li>'
    '<li>Contoso Cloud: 610 jobs, Dublin</li>'
    '</ul>'
    '<p style="margin:0;"><a href="https://asktherecruiter.com/blog/r/1">'
    'Open the AI Layoff Tracker</a></p>')
LAYOFF_TEXT = ("AI Layoff Tracker\n"
               "312 verified entries totalling 48,910 job cuts across 274 "
               "companies in this period.\n"
               "  - Acme Robotics: 1,200 jobs, Austin, TX\n"
               "  - Northwind Health: 940 jobs, Ohio\n"
               "  - Contoso Cloud: 610 jobs, Dublin\n"
               "Open the tracker: https://asktherecruiter.com/blog/ai-layoff-tracker/\n")

TALENT_HTML = (
    '<h2 style="font-size:16px;margin:24px 0 8px;">Talent Intelligence Tracker</h2>'
    '<p style="margin:0 0 8px;">88 new signals from 61 companies in this '
    'period, 54 verified against primary documents.</p>'
    '<ul style="margin:0 0 8px;padding-left:20px;">'
    '<li>Fabrikam: opens a 400 seat engineering hub in Warsaw</li>'
    '</ul>'
    '<p style="margin:0;"><a href="https://asktherecruiter.com/blog/r/2">'
    'Open the Talent Intelligence Tracker</a></p>')
TALENT_TEXT = ("Talent Intelligence Tracker\n"
               "88 new signals from 61 companies in this period, 54 verified "
               "against primary documents.\n"
               "  - Fabrikam: opens a 400 seat engineering hub in Warsaw\n"
               "Open the tracker: https://asktherecruiter.com/blog/talent-intelligence-tracker/\n")

ARTICLES_HTML = (
    '<h2 style="font-size:16px;margin:24px 0 8px;">From the blog</h2>'
    '<ul style="margin:0 0 8px;padding-left:20px;">'
    '<li style="margin:0 0 8px;"><a href="https://asktherecruiter.com/blog/r/3">'
    'What a WARN notice actually tells you</a><br>The filing is a legal '
    'minimum, not a headcount.</li>'
    '</ul>')
ARTICLES_TEXT = ("From the blog\n"
                 "  - What a WARN notice actually tells you\n"
                 "    The filing is a legal minimum, not a headcount.\n"
                 "    https://asktherecruiter.com/blog/2026/08/warn-notice/\n")


def payload(sections=("layoff",), **over):
    available = {
        "layoff": {"html": LAYOFF_HTML, "text": LAYOFF_TEXT},
        "talent": {"html": TALENT_HTML, "text": TALENT_TEXT},
        "articles": {"html": ARTICLES_HTML, "text": ARTICLES_TEXT},
    }
    base = {
        "available": True,
        "freq": "weekly",
        "send_id": 7,
        "from": "2026-08-07",
        "to": "2026-08-14",
        "subject": "[AskTheRecruiter] Weekly tracker digest",
        "manage_url": MANAGE,
        "sections": {name: available[name] for name in sections},
        "recipients": [{"id": 1, "email": "reader@example.com",
                        "unsub_url": UNSUB, "lists": list(sections)}],
    }
    base.update(over)
    return base


def message(sections=("layoff",), **over):
    data = payload(sections, **over)
    built = digest_send.build_message(data, data["recipients"][0], FROM, REPLY)
    assert built is not None, "the fixture composed nothing to send"
    return built


# A forward, simulated the way a webmail client does it: the head goes, and
# every style block with it. Anything the design needed from either is gone.
_STYLE_BLOCK = re.compile(r"<style\b.*?</style\s*>", re.I | re.S)
_HEAD_BLOCK = re.compile(r"<head\b.*?</head\s*>", re.I | re.S)


def forwarded(html):
    return _HEAD_BLOCK.sub("", _STYLE_BLOCK.sub("", html))


def _visible_tags(html):
    return re.findall(r"<\s*(h1|h2|h3|p|li|a)\b([^>]*)>", html, re.I)


class ForwardingSurvival(unittest.TestCase):
    """The deliverable. A forward deletes the head and the style blocks."""

    def test_there_is_no_style_block_to_lose(self):
        html = message().html
        self.assertNotIn("<style", html.lower(),
                         "a <style> block is deleted on forward, so anything "
                         "it carries is a design that only exists in the inbox")

    def test_stripping_every_style_block_and_the_head_is_a_no_op(self):
        """Byte for byte. Not "still looks acceptable": identical."""
        html = message(("layoff", "talent", "articles")).html
        stripped = _STYLE_BLOCK.sub("", html)
        self.assertEqual(stripped, html,
                         "removing the style blocks changed the message, so "
                         "part of the design lives in one")

    def test_the_layout_still_holds_with_the_head_deleted(self):
        body = forwarded(message(("layoff", "talent", "articles")).html)
        self.assertIn("max-width:600px", body,
                      "the 600px measure was in the head, so a forwarded copy "
                      "runs the full width of the window")
        self.assertIn("<table", body.lower())
        self.assertIn("font-family:", body,
                      "no typography survived the forward")
        self.assertIn("Acme Robotics", body)
        self.assertIn(UNSUB, body)

    def test_every_visible_element_carries_its_own_style(self):
        body = forwarded(message(("layoff", "talent", "articles")).html)
        for tag, attrs in _visible_tags(body):
            self.assertIn("style=", attrs,
                          f"<{tag}> carries no inline style, so it renders as "
                          f"the client's default in a forwarded copy")
            self.assertIn("color:", attrs,
                          f"<{tag}> declares no colour of its own, so it "
                          f"inherits whatever the quoting client sets")

    def test_no_class_or_id_is_load_bearing(self):
        """A class selector needs a stylesheet, and the stylesheet is gone."""
        html = message(("layoff", "talent", "articles")).html
        self.assertNotRegex(html, r'\sclass\s*=',
                            "a class attribute in an email can only be styled "
                            "from a block a forward deletes")


class NoLayoutTheWordEngineCannotDraw(unittest.TestCase):
    """Outlook on Windows renders through Word. Tables, or nothing."""

    def test_no_flex_no_grid_no_positioning(self):
        html = message(("layoff", "talent", "articles")).html
        for pattern, why in (
            (r"display\s*:\s*flex", "flexbox"),
            (r"display\s*:\s*grid", "grid"),
            (r"position\s*:\s*(absolute|relative|fixed|sticky)", "CSS positioning"),
        ):
            self.assertIsNone(re.search(pattern, html, re.I),
                              f"{why} is not rendered by Word, which is the "
                              f"engine behind Outlook on Windows")

    def test_no_media_query_carries_the_layout(self):
        html = message().html
        self.assertNotIn("@media", html,
                         "a media query dies on forward, so it may never be "
                         "what makes the message fit a phone")

    def test_the_shell_is_a_presentational_table_that_is_fluid_then_capped(self):
        html = message().html
        self.assertIn('role="presentation"', html,
                      "a layout table must be hidden from screen readers")
        self.assertIn('width="100%"', html, "the shell does not go fluid")
        self.assertIn("max-width:600px", html, "the shell has no measure")


class LegibleWhenInverted(unittest.TestCase):
    """Many clients invert a light email. Declaring nothing means inheriting
    the client's guess, and the usual result is dark text on dark."""

    @staticmethod
    def _ratio(fg, bg):
        def lum(hexcolor):
            parts = [int(hexcolor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            parts = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                     for c in parts]
            return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]
        a, b = lum(fg), lum(bg)
        hi, lo = max(a, b), min(a, b)
        return (hi + 0.05) / (lo + 0.05)

    @staticmethod
    def _invert(hexcolor):
        return "#" + "".join(f"{255 - int(hexcolor[i:i + 2], 16):02x}"
                             for i in (1, 3, 5))

    def test_the_page_and_the_card_declare_their_own_background(self):
        html = message().html
        self.assertIn(f"background-color:{layout.PAGE_BG}", html)
        self.assertIn(f"background-color:{layout.CARD_BG}", html)

    def test_the_palette_clears_4_5_to_1_upright_and_inverted(self):
        for name, ink in (("body", layout.INK), ("muted", layout.MUTED),
                          ("link", layout.LINK)):
            upright = self._ratio(ink, layout.CARD_BG)
            inverted = self._ratio(self._invert(ink), self._invert(layout.CARD_BG))
            self.assertGreaterEqual(round(upright, 2), 4.5,
                                    f"{name} text is {upright:.2f}:1 on the card")
            self.assertGreaterEqual(round(inverted, 2), 4.5,
                                    f"{name} text is {inverted:.2f}:1 once a "
                                    f"client inverts the message")

    def test_the_message_tells_the_client_it_handles_both_schemes(self):
        self.assertIn('name="color-scheme"', message().html)


class ThePreheader(unittest.TestCase):
    """The snippet the inbox list shows beside the subject. With none, the
    client grabs the first thing it finds, which is usually the unsubscribe."""

    def test_it_leads_with_the_sites_own_sentence_and_is_hidden(self):
        html = message().html
        snippet = layout.preheader_text([("layoff", LAYOFF_HTML, LAYOFF_TEXT)])
        self.assertIn("312 verified entries", snippet)
        self.assertIn(snippet, html)
        block = html[:html.index(snippet)]
        self.assertIn("display:none", block.split("<div")[-1],
                      "the preheader is visible in the body of the message")

    def test_it_sits_before_anything_else_a_client_could_grab(self):
        html = message().html
        self.assertLess(html.index("312 verified entries"), html.index("Unsubscribe"))

    def test_a_sentence_too_long_to_show_is_replaced_not_truncated(self):
        """Cutting a snippet mid figure publishes a wrong number in the inbox."""
        long_text = ("AI Layoff Tracker\n" + "x" * 200 + " 48,910 job cuts.\n")
        snippet = layout.preheader_text([("layoff", LAYOFF_HTML, long_text)])
        self.assertNotIn("...", snippet)
        self.assertNotIn("48,910", snippet)
        self.assertTrue(snippet.strip())

    def test_a_bullet_is_never_read_as_the_summary_sentence(self):
        """The blog section is a heading and then bullets. Taking its first
        bullet put one article title in the inbox snippet as if it were the
        digest's headline."""
        snippet = layout.preheader_text([("articles", ARTICLES_HTML, ARTICLES_TEXT)])
        self.assertNotIn("What a WARN notice", snippet)
        self.assertIn("From the blog", snippet)

    def test_it_is_not_repeated_in_the_visible_body(self):
        html = message().html
        self.assertEqual(html.count("312 verified entries"), 2,
                         "once hidden in the preheader and once in the section")


class TheSubjectSaysWhatChanged(unittest.TestCase):
    def test_it_names_the_tracker_and_the_period(self):
        subject = message().subject
        self.assertIn("AI Layoff Tracker", subject)
        self.assertIn("14 August 2026", subject)
        self.assertNotIn("Your digest", subject)

    def test_it_stays_short_enough_to_read_in_a_list(self):
        for names in (("layoff",), ("layoff", "talent"),
                      ("layoff", "talent", "articles")):
            subject = message(names).subject
            self.assertLessEqual(len(subject), 78, subject)

    def test_three_sections_are_summarised_rather_than_listed_out(self):
        subject = message(("layoff", "talent", "articles")).subject
        self.assertIn("AI Layoff Tracker", subject)
        self.assertIn("2 more", subject)

    def test_a_period_it_cannot_read_falls_back_to_the_sites_subject(self):
        built = message(to="not-a-date")
        self.assertEqual(built.subject, "[AskTheRecruiter] Weekly tracker digest")


class ThePlainTextAlternative(unittest.TestCase):
    """Many readers, every screen reader fallback and every text only client
    see this and nothing else."""

    def test_it_carries_the_figures_the_html_carries(self):
        text = message(("layoff", "talent", "articles")).text
        for figure in ("312 verified entries", "48,910 job cuts", "274 companies",
                       "88 new signals", "54 verified"):
            self.assertIn(figure, text)

    def test_it_carries_the_entries_not_only_the_totals(self):
        text = message(("layoff", "talent", "articles")).text
        for entry in ("Acme Robotics: 1,200 jobs", "Northwind Health: 940 jobs",
                      "Fabrikam", "What a WARN notice actually tells you"):
            self.assertIn(entry, text)

    def test_it_carries_both_ways_out(self):
        text = message().text
        self.assertIn(UNSUB, text)
        self.assertIn(MANAGE, text)
        self.assertIn("no tracking pixels", text)

    def test_it_is_not_a_stripped_tag_byproduct(self):
        text = message(("layoff", "talent")).text
        self.assertNotIn("<", text)
        self.assertNotIn("&amp;", text)
        self.assertIn("AI Layoff Tracker", text)
        self.assertIn("Talent Intelligence Tracker", text)

    def test_no_line_runs_past_a_terminal_width(self):
        """Prose wraps. A URL on its own line does not, because a link broken
        across two lines is a link a reader cannot use."""
        for line in message(("layoff", "talent", "articles")).text.splitlines():
            if " " not in line.strip():
                continue
            self.assertLessEqual(len(line), 78, line)


class ThePromisesAreUnchanged(unittest.TestCase):
    def test_a_real_rendered_digest_passes_the_privacy_check_unmodified(self):
        for names in (("layoff",), ("layoff", "talent", "articles")):
            dt.assert_message_is_clean(message(names))

    def test_it_still_passes_with_no_manage_url(self):
        built = message(manage_url="")
        dt.assert_message_is_clean(built)
        self.assertNotIn("Manage your subscriptions", built.html)

    def test_nothing_in_the_shell_fetches_from_a_server(self):
        html = message(("layoff", "talent", "articles")).html.lower()
        for token in ("<img", "url(", "background=", "src="):
            self.assertNotIn(token, html)

    def test_every_link_says_where_it_goes(self):
        html = message(("layoff", "talent", "articles")).html
        for label in re.findall(r"<a\b[^>]*>(.*?)</a>", html, re.S):
            plain = re.sub(r"<[^>]+>", "", label).strip().lower()
            self.assertNotIn(plain, ("click here", "here", "read more", "link"))
            self.assertGreater(len(plain), 4, label)


class ReadingTheEmailWhenNobodyIsDue(unittest.TestCase):
    """The RUNBOOK tells the owner to read the rendered digest before arming
    the sender. With no confirmed subscriber due, the site composes every
    section from the live endpoints and the job then renders nothing, because
    a message is built per recipient. So the one run that exists to be read
    printed a count and no email.

    A preview may never become a send, and these are the two independent
    reasons it cannot.
    """

    ENV = {"WP_SITE_URL": "https://asktherecruiter.com/blog", "WP_API_KEY": "k",
           "DIGEST_PREVIEW": "1", "DIGEST_FREQ": "weekly"}

    def _run(self, env=None, transport=None):
        import io
        from unittest import mock
        live = payload(("layoff", "talent", "articles"), recipients=[])
        buf = io.StringIO()
        chosen = transport or dt.DryRunTransport("test", buf)
        log = io.StringIO()
        with mock.patch.dict(os.environ, dict(self.ENV, **(env or {})), clear=True), \
                mock.patch.object(digest_send, "_call", return_value=live) as call, \
                mock.patch.object(digest_send, "_record_health") as health, \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(chosen, "test")), \
                mock.patch.object(digest_send.time, "sleep"), \
                mock.patch("sys.stdout", log):
            code = digest_send.main()
        return code, buf.getvalue() + log.getvalue(), call, health

    def test_the_live_sections_render_against_a_placeholder(self):
        code, out, call, _ = self._run()
        self.assertEqual(code, 0)
        self.assertIn("312 verified entries", out)
        self.assertLess(out.index("AI Layoff Tracker"), out.index("From the blog"),
                        "the preview reordered the sections; the site's own "
                        "order is the one a reader sees")
        self.assertIn("Talent Intelligence Tracker", out)
        self.assertIn("DRY RUN, nothing sent", out)
        self.assertEqual([c.args[0] for c in call.call_args_list],
                         ["digest-recipients"],
                         "a preview must never record a send")

    def test_a_transport_that_sends_refuses_the_preview_outright(self):
        class Sending(dt.Transport):
            name, sends = "sending", True

            def __init__(self):
                self.delivered = []

            def _deliver(self, message):
                self.delivered.append(message)
                return "sent"

        transport = Sending()
        code, out, _, _ = self._run(transport=transport)
        self.assertEqual(code, 0)
        self.assertEqual(transport.delivered, [],
                         "a placeholder address reached a transport that sends")
        self.assertIn("this transport SENDS", out or "")

    def test_the_placeholder_can_never_be_a_real_mailbox(self):
        self.assertTrue(digest_send.PREVIEW_ADDRESS.endswith(".invalid"),
                        "a preview address on a routable domain is one "
                        "misconfiguration away from mailing a stranger")

    def test_a_preview_is_kept_out_of_the_health_ledger(self):
        _, out, _, health = self._run()
        health.assert_not_called()
        self.assertIn("not a recipient", out)

    def test_a_real_recipient_is_never_replaced_by_the_placeholder(self):
        import io
        from unittest import mock
        live = payload(("layoff",))
        buf = io.StringIO()
        with mock.patch.dict(os.environ, self.ENV, clear=True), \
                mock.patch.object(digest_send, "_call", return_value=live), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(dt.DryRunTransport("t", buf), "t")), \
                mock.patch.object(digest_send.time, "sleep"):
            digest_send.main()
        self.assertNotIn(digest_send.PREVIEW_ADDRESS, buf.getvalue())

    def test_nothing_to_compose_previews_nothing_rather_than_an_empty_shell(self):
        import io
        from unittest import mock
        live = payload((), recipients=[])
        buf = io.StringIO()
        with mock.patch.dict(os.environ, self.ENV, clear=True), \
                mock.patch.object(digest_send, "_call", return_value=live), \
                mock.patch.object(digest_send, "_record_health"), \
                mock.patch.object(digest_send, "resolve_transport",
                                  return_value=(dt.DryRunTransport("t", buf), "t")):
            code = digest_send.main()
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue(), "")

    def test_the_workflow_exposes_it_and_the_names_agree(self):
        body = open(os.path.join(RAILWAY, "..", ".github", "workflows",
                                 "digest-send.yml"), encoding="utf-8").read()
        self.assertIn("preview:", body)
        self.assertIn("DIGEST_PREVIEW: ${{ github.event.inputs.preview }}", body)


class HouseStyle(unittest.TestCase):
    def test_no_long_dashes_in_the_module_or_in_what_it_renders(self):
        built = message(("layoff", "talent", "articles"))
        source = open(os.path.join(RAILWAY, "digest_layout.py"),
                      encoding="utf-8").read()
        for ch in ("—", "–"):
            self.assertNotIn(ch, source)
            self.assertNotIn(ch, built.html)
            self.assertNotIn(ch, built.text)

    def test_the_layout_derives_no_figure_of_its_own(self):
        """One definition of a headline number, and it is on the site."""
        source = open(os.path.join(RAILWAY, "digest_layout.py"),
                      encoding="utf-8").read()
        source = re.sub(r'""".*?"""', "", source, flags=re.S)
        source = re.sub(r"#.*", "", source)
        for banned in ("aggregate", "SELECT", "job_count", "sum(", "total ="):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
