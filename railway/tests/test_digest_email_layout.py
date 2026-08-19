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
#
# UPDATED 2026-08-17 to the shape the composers emit AFTER the scope rewrite.
# Two things changed and both matter to this file. The site now marks a line
# with `data-alt` instead of choosing a size, and the ranked lists are two
# column tables rather than bullet lists, because a bullet list cannot align a
# column of figures. So the fixtures carry a `data-alt`, a `<table>` and an
# `align` attribute, and the tests below check that all three survive a
# forward with their styling attached.
LAYOFF_HTML = (
    '<h2>AI Layoff Tracker</h2>'
    '<p data-alt="kicker">Verified job cuts</p>'
    '<p data-alt="stat">48,910</p>'
    '<p data-alt="scope">August 7-14, 2026, counted by the date the cuts '
    'take effect.</p>'
    '<p data-alt="note">312 entries are verified. Including announced '
    'estimates, August 7-14, 2026 holds 374 entries and 61,000 job cuts '
    'across 274 companies.</p>'
    '<h3>Biggest cuts</h3>'
    '<p data-alt="caption">August 7-14, 2026, verified and announced '
    'together, ranked by job count.</p>'
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
    '<tr><td data-alt="label"><a href="https://asktherecruiter.com/blog/r/9">'
    'Acme Robotics (Austin, TX, takes effect 9 Aug 2026)</a></td>'
    '<td data-alt="figure" align="right" width="34%">1,200 jobs</td></tr>'
    '<tr><td data-alt="label-last">Northwind Health (Ohio)</td>'
    '<td data-alt="figure-last" align="right" width="34%">940 jobs</td></tr>'
    '</table>'
    '<p><a href="https://asktherecruiter.com/blog/r/1">'
    'Open the AI Layoff Tracker</a></p>')
LAYOFF_TEXT = ("AI Layoff Tracker\n"
               "48,910 verified job cuts, August 7-14, 2026, counted by the "
               "date the cuts take effect.\n"
               "312 entries are verified. Including announced estimates, 7 to "
               "August 14, 2026 holds 374 entries and 61,000 job cuts across "
               "274 companies.\n"
               "\nBiggest cuts\n"
               "August 7-14, 2026, verified and announced together, ranked "
               "by job count.\n"
               "  Acme Robotics (Austin, TX, takes effect 9 Aug 2026): 1,200 jobs\n"
               "    https://asktherecruiter.com/blog/layoff/acme-robotics-2026-08-09/\n"
               "  Northwind Health (Ohio): 940 jobs\n"
               "\nOpen the tracker: https://asktherecruiter.com/blog/ai-layoff-tracker/\n")

TALENT_HTML = (
    '<h2>Talent Intelligence Tracker</h2>'
    '<p data-alt="kicker">New hiring signals</p>'
    '<p data-alt="stat">88</p>'
    '<p data-alt="scope">August 7-14, 2026, counted by the date the source '
    'published.</p>'
    '<p data-alt="note">From 61 companies, August 7-14, 2026. 54 of the 88 '
    'are verified against primary documents.</p>'
    '<ul>'
    '<li>Fabrikam: opens a 400 seat engineering hub in Warsaw (9 Aug 2026)</li>'
    '</ul>'
    '<p><a href="https://asktherecruiter.com/blog/r/2">'
    'Open the Talent Intelligence Tracker</a></p>')
TALENT_TEXT = ("Talent Intelligence Tracker\n"
               "88 new hiring signals, August 7-14, 2026, counted by the "
               "date the source published.\n"
               "From 61 companies, August 7-14, 2026. 54 of the 88 are "
               "verified against primary documents.\n"
               "  - Fabrikam: opens a 400 seat engineering hub in Warsaw "
               "(9 Aug 2026)\n"
               "\nOpen the tracker: https://asktherecruiter.com/blog/talent-intelligence-tracker/\n")

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
    return re.findall(r"<\s*(h1|h2|h3|p|li|a|td)\b([^>]*)>", html, re.I)


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
        self.assertIn("48,910 verified job cuts", snippet)
        self.assertIn(snippet, html)
        block = html[:html.index(snippet)]
        self.assertIn("display:none", block.split("<div")[-1],
                      "the preheader is visible in the body of the message")

    def test_it_sits_before_anything_else_a_client_could_grab(self):
        html = message().html
        self.assertLess(html.index("48,910 verified job cuts"),
                        html.index("Unsubscribe"))

    def test_a_sentence_too_long_to_show_is_replaced_not_truncated(self):
        """Cutting a snippet mid figure publishes a wrong number in the inbox."""
        long_text = ("AI Layoff Tracker\n" + "x" * 200 + " 48,910 job cuts.\n")
        snippet = layout.preheader_text([("layoff", LAYOFF_HTML, long_text)])
        self.assertNotIn("...", snippet)
        self.assertNotIn("48,910", snippet)
        self.assertTrue(snippet.strip())

    def test_the_snippet_describes_the_section_the_subject_leads_with(self):
        """THE ASSERTION THAT WOULD HAVE CAUGHT IT.

        The old preheader walked EVERY section and took the first summary
        sentence that fitted 130 characters. On 2026-08-17 the layoff lede
        grew a measured geography clause and reached 143, so the walk went
        past it and took the talent section's sentence. The live digest went
        out with a subject leading "AI Layoff Tracker" beside a snippet
        reading "1,332 new hiring signals".

        The subject and the snippet are the two things every recipient sees
        before deciding whether to open. Describing different trackers is
        precisely the mismatch that stops someone opening.
        """
        over = "AI Layoff Tracker\n" + "48,910 verified job cuts, " + "y" * 140 + "\n"
        talent = "Talent Intelligence Tracker\n1,332 new hiring signals, this week.\n"
        parts = [("layoff", LAYOFF_HTML, over), ("talent", LAYOFF_HTML, talent)]

        subject = layout.subject_line(
            {"from": "2026-08-10", "to": "2026-08-16", "freq": "weekly"}, parts)
        snippet = layout.preheader_text(parts)

        self.assertTrue(subject.startswith("AI Layoff Tracker"), subject)
        self.assertNotIn("1,332", snippet,
                         "the subject leads with the layoff tracker and the "
                         "snippet is quoting the talent tracker's figure")
        self.assertNotIn("hiring signals", snippet)
        self.assertIn("AI Layoff Tracker", snippet,
                      "the snippet does not name the section the subject "
                      "leads with")

    def test_the_two_lines_are_built_from_one_definition_of_leading(self):
        """Not a coincidence that holds until somebody edits one of them:
        subject_line and preheader_text ask the same function which section
        leads, so they cannot drift apart."""
        # An empty text part is the one shape that cannot name itself. Any
        # non-empty first line IS the heading, by section_heading's definition.
        parts = [("layoff", LAYOFF_HTML, "   \n\n"),
                 ("talent", LAYOFF_HTML, "Talent Intelligence Tracker\nA lead.\n")]
        self.assertEqual(layout.section_heading(
            layout.part_text(layout.leading_part(parts))),
            "Talent Intelligence Tracker",
            "a section that cannot name itself is skipped by the subject, so "
            "it must be skipped by the snippet too")

    def test_the_sites_own_snippet_is_preferred_over_a_body_sentence(self):
        """A preheader has one purpose and one hard ceiling, so the site
        composes one for that ceiling. The body sentence is then free to be as
        long as it needs to be where there is room for it."""
        composed = "48,910 verified job cuts, August 10-17, 2026, worldwide."
        over = "AI Layoff Tracker\n" + "48,910 verified job cuts, " + "y" * 140 + "\n"
        snippet = layout.preheader_text([("layoff", LAYOFF_HTML, over, composed)])
        self.assertEqual(snippet, composed)

    def test_a_snippet_the_site_composed_too_long_is_still_not_used(self):
        """The ceiling is the ceiling. A composer that hands us 200 characters
        has a bug, and honouring it would put the bug in the inbox."""
        snippet = layout.preheader_text(
            [("layoff", LAYOFF_HTML, LAYOFF_TEXT, "z" * 200)])
        self.assertNotIn("zzz", snippet)
        self.assertIn("48,910 verified job cuts", snippet,
                      "it should have fallen back to this section's own lead")

    def test_an_older_plugin_build_sending_no_snippet_still_works(self):
        """The three-member part is the shape before 2026-08-17. A missing
        member is a real state, not a crash."""
        snippet = layout.preheader_text([("layoff", LAYOFF_HTML, LAYOFF_TEXT)])
        self.assertIn("48,910 verified job cuts", snippet)

    def test_a_section_with_nothing_usable_still_names_itself(self):
        """The last rung carries no figure, which is the point: a snippet with
        a number in it that this module derived would be a second place a
        figure can be wrong."""
        over = "AI Layoff Tracker\n" + "y" * 200 + "\n"
        snippet = layout.preheader_text([("layoff", LAYOFF_HTML, over)])
        self.assertEqual(snippet, "AI Layoff Tracker: what changed this period.")

    def test_a_bullet_is_never_read_as_the_summary_sentence(self):
        """The blog section is a heading and then bullets. Taking its first
        bullet put one article title in the inbox snippet as if it were the
        digest's headline."""
        snippet = layout.preheader_text([("articles", ARTICLES_HTML, ARTICLES_TEXT)])
        self.assertNotIn("What a WARN notice", snippet)
        self.assertIn("From the blog", snippet)

    def test_it_is_not_repeated_in_the_visible_body(self):
        html = message().html
        self.assertEqual(html.count("48,910 verified job cuts"), 1,
                         "the preheader sentence is the text part's, so the "
                         "HTML carries it once, hidden")


class TheSubjectSaysWhatChanged(unittest.TestCase):
    def test_it_names_the_tracker_and_the_period(self):
        subject = message().subject
        self.assertIn("AI Layoff Tracker", subject)
        # The window, not the send date: a weekly subject carries the ISO
        # week and the dates it covers. See digest_layout.period_phrase.
        self.assertIn("August 7-14", subject)
        self.assertNotIn("Your digest", subject)

    def test_it_stays_short_enough_to_read_in_a_list(self):
        for names in (("layoff",), ("layoff", "talent"),
                      ("layoff", "talent", "articles")):
            subject = message(names).subject
            self.assertLessEqual(len(subject), 78, subject)

    def test_three_sections_are_never_listed_out_or_counted(self):
        """WHAT THIS USED TO ASSERT, AND WHY IT WAS THE DEFECT.

        It required the subject to contain "2 more". That is what the old rule
        produced for a subscriber to all three lists, which is to say for the
        normal case, and the owner read a delivered send and called it out:
        "AI Layoff Tracker and 2 more" is machine output, not an edition.

        A masthead does not list its own contents. The subject names the
        section a reader meets first and then dates the edition; the other
        sections are in the body. So the assertion is inverted: the count must
        NOT be there, and the edition must be.
        """
        subject = message(("layoff", "talent", "articles")).subject
        self.assertIn("AI Layoff Tracker", subject)
        self.assertNotIn("more", subject)
        self.assertNotIn("Talent", subject)
        # The window, not the send date: a weekly subject carries the ISO
        # week and the dates it covers. See digest_layout.period_phrase.
        self.assertIn("August 7-14", subject)

    def test_a_period_it_cannot_read_falls_back_to_the_sites_subject(self):
        built = message(to="not-a-date")
        self.assertEqual(built.subject, "[AskTheRecruiter] Weekly tracker digest")


class ThePlainTextAlternative(unittest.TestCase):
    """Many readers, every screen reader fallback and every text only client
    see this and nothing else."""

    def test_it_carries_the_figures_the_html_carries(self):
        text = message(("layoff", "talent", "articles")).text
        for figure in ("48,910 verified job cuts", "312 entries are verified",
                       "274 companies", "88 new hiring signals",
                       "54 of the 88 are verified"):
            self.assertIn(figure, text)

    def test_it_carries_the_entries_not_only_the_totals(self):
        text = message(("layoff", "talent", "articles")).text
        for entry in ("Acme Robotics", "1,200 jobs", "Northwind Health",
                      "940 jobs", "Fabrikam",
                      "What a WARN notice actually tells you"):
            self.assertIn(entry, text)

    def test_it_carries_both_ways_out(self):
        text = message().text
        self.assertIn(UNSUB, text)
        self.assertIn(MANAGE, text)
        # The measurement disclosure, read from the one place that composes it
        # rather than quoted. Quoting made this a second definition of the
        # sentence, so it reddened on a wording change that broke nothing.
        # What matters here is that the disclosure reaches the plain text part
        # at all, whatever the relay state has it currently saying.
        self.assertIn(layout.TRACKING_SENTENCES[0], " ".join(text.split()))

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
        self.assertIn("48,910", out)
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


class TheVariantMechanism(unittest.TestCase):
    """The site says WHAT a line is; this module says how it looks.

    The composer marks a headline figure `data-alt="stat"` and never picks a
    size. So there is one place that decides what a stat looks like and one
    place that decides which figure is one, and neither can drift into the
    other's job.
    """

    def test_the_marker_is_consumed_and_never_reaches_a_reader(self):
        html = message(("layoff", "talent")).html
        self.assertNotIn("data-alt", html,
                         "the variant marker was left in the message, so a "
                         "mail client gets to decide what it means")

    def test_the_headline_figure_is_larger_than_the_prose_around_it(self):
        html = message().html
        stat = layout.VARIANT_STYLES[("p", "stat")]
        self.assertIn(stat, html, "the stat line did not get the stat style")
        self.assertIn("font-size:34px", stat)
        self.assertIn("font-size:15px", layout.TAG_STYLES["p"])

    def test_an_unknown_variant_falls_back_to_the_plain_tag_style(self):
        """A typo in the site's markup costs a design detail, never a
        paragraph's readability in a forwarded copy."""
        out = layout.restyle('<p data-alt="not-a-real-variant">Hello</p>')
        self.assertNotIn("data-alt", out)
        self.assertIn(layout.TAG_STYLES["p"], out)

    def test_the_ranked_table_aligns_its_figures_with_an_attribute(self):
        """Word ignores half of CSS and honours `align`, so the alignment
        that makes a column of figures readable cannot be a property."""
        body = forwarded(message().html)
        self.assertIn('align="right"', body)
        self.assertIn("white-space:nowrap", body,
                      "a figure that wraps is a figure that stops lining up")

    def test_every_content_cell_carries_its_own_style_after_a_forward(self):
        """The shell's own cells paint the page and are checked elsewhere.
        These are the cells the SITE emitted, which is where a forward would
        otherwise strip the typography off a column of figures."""
        styled = layout.restyle(LAYOFF_HTML)
        cells = re.findall(r"<\s*td\b([^>]*)>", styled, re.I)
        self.assertTrue(cells, "the fixture has no table cell to check")
        body = forwarded(message().html)
        for attrs in cells:
            self.assertIn("style=", attrs)
            self.assertIn("font-family:", attrs)
            self.assertIn("color:", attrs)
            self.assertIn(attrs.strip(), body,
                          "the cell reached the message with different styling "
                          "than restyle produced")


class TheTrackingSentenceIsTrue(unittest.TestCase):
    """The footer used to promise no pixel and no open tracking. The owner
    turned open and click tracking ON in Brevo on 2026-08-16, and Brevo adds
    both at the relay, after this code has handed the message over. So the
    email carried a promise its own delivery broke.

    Our message still embeds nothing. The check that enforces that is
    deliberately untouched, and these tests hold both halves of the position
    at once: the message is clean, and the copy no longer claims more.
    """

    def test_the_old_promise_is_gone_from_both_parts(self):
        built = message(("layoff", "talent"))
        for part in (built.html, built.text):
            self.assertNotIn("no tracking pixels", part)
            self.assertNotIn("cannot tell whether you opened", part)

    @staticmethod
    def _flat(part):
        """The plain text part is wrapped to a terminal width, so a sentence
        crosses a line break. Compare on the words, not on the line endings."""
        return " ".join(part.split())

    def test_both_parts_say_plainly_what_is_measured(self):
        """Whatever the relay state, both parts must name what is recorded and
        say that unsubscribing stops it. The two states make DIFFERENT promises
        and each has to be checked against its own, because the failure this
        guards against is a footer describing the other one."""
        built = message(("layoff", "talent"))
        for part in (built.html, built.text):
            flat = self._flat(part)
            if layout.RELAY_TRACKING_ON:
                self.assertIn("records whether you open this email", flat)
                self.assertIn("which links you follow", flat)
                self.assertIn("Unsubscribing stops the email and the measuring",
                              flat)
            else:
                # The negative is the whole promise, so it is pinned rather
                # than left to the absence of the positive.
                self.assertIn("records nothing about how you read this email",
                              flat)
                self.assertIn("adds no invisible image", flat)
                # And the counter that survives is named, so the footer does
                # not read as "nothing is counted", which is not true.
                self.assertIn("counter on our own site", flat)
                self.assertIn("Unsubscribing stops the email and the counting",
                              flat)
            self.assertNotIn("no tracking pixels", flat)

    def test_the_two_parts_cannot_disagree(self):
        """One source of the words, so a fix to one is a fix to both."""
        built = message()
        for sentence in layout.TRACKING_SENTENCES:
            self.assertIn(sentence, self._flat(built.text))
            self.assertIn(sentence, self._flat(built.html))

    def test_our_own_message_still_embeds_nothing_that_fetches(self):
        """The tracking is the relay's. Do not weaken this to match the copy."""
        built = message(("layoff", "talent", "articles"))
        dt.assert_message_is_clean(built)
        lowered = built.html.lower()
        for token in ("<img", "url(", "src=", "background="):
            self.assertNotIn(token, lowered)


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
