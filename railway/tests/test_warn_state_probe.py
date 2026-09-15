"""Offline guards for the eight-state WARN re-probe (railway/warn_state_probe.py).

This does NOT test that any of the eight states is actually in or out today --
that requires the live network, which this module never opens. It pins the
JUDGEMENT LOGIC against stubbed HTTP responses: each criterion's pass and
fail branch, the robots-block-by-name rule, the Content-Signal rule, the
undocumented-XHR-endpoint rule, and the request ORDER (robots.txt before
anything else).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from warn_state_probe import (          # noqa: E402
    STATES, ProbeResponse, parse_robots, robots_blocks_agent,
    looks_statically_readable, has_required_fields, probe_robots, probe_state,
    build_report, AGENT_NAME,
)

_JSON_HEADERS = {"Content-Type": "application/json"}
_HTML_HEADERS = {"Content-Type": "text/html"}

_STATIC_TABLE_HTML = ("<table>" + "".join(
    f"<tr><td>Acme Corp {i}</td><td>2026-01-0{i % 9 + 1}</td>"
    f"<td>{100 + i}</td><td>Employer Notice</td></tr>" for i in range(1, 5)
) + "</table>")

_CLIENT_SIDE_HTML = "<html><body><div id='app'></div><script src='bundle.js'></script></body></html>"

_NO_ROBOTS = ProbeResponse(404, {}, b"")
_PERMISSIVE_ROBOTS = ProbeResponse(200, {}, b"User-agent: *\nDisallow:\n")
_STAR_BLOCKED_ROBOTS = ProbeResponse(200, {}, b"User-agent: *\nDisallow: /\n")
_NAMED_BLOCKED_ROBOTS = ProbeResponse(
    200, {}, (f"User-agent: {AGENT_NAME}\nDisallow: /\n"
              "User-agent: *\nDisallow:\n").encode("utf-8"))
_CONTENT_SIGNAL_ROBOTS = ProbeResponse(
    200, {}, b"User-agent: *\nDisallow:\nContent-Signal: ai-train=no, ai-input=no\n")


def _fetch_map(mapping, calls=None):
    """A stub `fetch(url, ua)` driven by a {substring: ProbeResponse} map, in
    the order given -- first substring match wins. Records every URL called,
    in order, into `calls` when provided."""
    def fetch(url, ua=None, timeout=None):
        if calls is not None:
            calls.append(url)
        for key, resp in mapping.items():
            if key in url:
                return resp
        raise AssertionError(f"unstubbed URL in test: {url}")
    return fetch


class RobotsParsingTests(unittest.TestCase):
    def test_permissive_robots_does_not_block(self):
        blocks, cs = parse_robots("User-agent: *\nDisallow:\n")
        blocked, by = robots_blocks_agent(blocks, AGENT_NAME)
        self.assertFalse(blocked)
        self.assertFalse(cs)

    def test_star_disallow_all_blocks(self):
        blocks, _ = parse_robots("User-agent: *\nDisallow: /\n")
        blocked, by = robots_blocks_agent(blocks, AGENT_NAME)
        self.assertTrue(blocked)
        self.assertEqual(by, "*")

    def test_named_agent_block_takes_precedence_over_permissive_star(self):
        text = (f"User-agent: {AGENT_NAME}\nDisallow: /\n"
                "User-agent: *\nDisallow:\n")
        blocks, _ = parse_robots(text)
        blocked, by = robots_blocks_agent(blocks, AGENT_NAME)
        self.assertTrue(blocked)
        self.assertEqual(by, AGENT_NAME)

    def test_named_agent_allow_survives_a_blocked_star(self):
        # The VA shape, inverted: if OUR name were explicitly allowed while *
        # was blocked, the named group should win and we would NOT be blocked.
        text = f"User-agent: {AGENT_NAME}\nDisallow:\nUser-agent: *\nDisallow: /\n"
        blocks, _ = parse_robots(text)
        blocked, by = robots_blocks_agent(blocks, AGENT_NAME)
        self.assertFalse(blocked)
        self.assertEqual(by, AGENT_NAME)

    def test_content_signal_ai_input_no_is_detected(self):
        _, cs = parse_robots("User-agent: *\nDisallow:\nContent-Signal: ai-train=no, ai-input=no\n")
        self.assertTrue(cs)

    def test_content_signal_without_ai_input_no_is_not_flagged(self):
        _, cs = parse_robots("User-agent: *\nDisallow:\nContent-Signal: ai-train=no, ai-input=yes\n")
        self.assertFalse(cs)


class ProbeRobotsTests(unittest.TestCase):
    def test_missing_robots_txt_is_permitted_not_blocked(self):
        r = probe_robots("https://example.gov/warn", _fetch_map({"robots.txt": _NO_ROBOTS}))
        self.assertFalse(r["blocked"])
        self.assertFalse(r["unreachable"])

    def test_transport_failure_reading_robots_is_unknown_not_permitted(self):
        err = ProbeResponse(None, {}, b"", error="ConnectionError: refused")
        r = probe_robots("https://example.gov/warn", _fetch_map({"robots.txt": err}))
        self.assertTrue(r["unreachable"])
        self.assertFalse(r["blocked"])


class StaticReadabilityTests(unittest.TestCase):
    def test_json_content_type_is_readable(self):
        ok, why = looks_statically_readable("application/json", b"[]")
        self.assertTrue(ok)

    def test_csv_content_type_is_readable(self):
        ok, why = looks_statically_readable("text/csv", b"a,b\n1,2\n")
        self.assertTrue(ok)

    def test_html_with_populated_rows_is_readable(self):
        ok, why = looks_statically_readable("text/html", _STATIC_TABLE_HTML.encode("utf-8"))
        self.assertTrue(ok)

    def test_client_side_rendered_html_is_not_readable(self):
        ok, why = looks_statically_readable("text/html", _CLIENT_SIDE_HTML.encode("utf-8"))
        self.assertFalse(ok)
        self.assertIn("client-side", why)


class RequiredFieldsTests(unittest.TestCase):
    def test_all_three_labels_present_passes(self):
        ok, why = has_required_fields(b"Employer, Date of Notice, Employees Affected")
        self.assertTrue(ok)

    def test_missing_a_label_fails(self):
        ok, why = has_required_fields(b"Employer, Employees Affected")
        self.assertFalse(ok)
        self.assertIn("date", why)


class ProbeStateCriterionTests(unittest.TestCase):
    """Each criterion's pass and fail branch, exercised through probe_state
    with STATES['NY'] standing in for a generic host (URL content doesn't
    matter -- only what the stub returns for it)."""

    def _run(self, url_resp, robots_resp=_PERMISSIVE_ROBOTS):
        fetch = _fetch_map({"robots.txt": robots_resp, "warn": url_resp})
        return probe_state("NY", fetch=fetch)

    def test_criterion_a_fails_on_robots_disallow(self):
        r = self._run(url_resp=ProbeResponse(200, _HTML_HEADERS, _STATIC_TABLE_HTML.encode()),
                       robots_resp=_STAR_BLOCKED_ROBOTS)
        self.assertEqual(r["verdict"], "OUT")
        self.assertEqual(r["failed_criterion"], "a")

    def test_criterion_a_fails_on_named_block_never_renamed_to_dodge_it(self):
        r = self._run(url_resp=ProbeResponse(200, _HTML_HEADERS, _STATIC_TABLE_HTML.encode()),
                       robots_resp=_NAMED_BLOCKED_ROBOTS)
        self.assertEqual(r["verdict"], "OUT")
        self.assertEqual(r["failed_criterion"], "a")
        self.assertEqual(r["robots"]["blocked_by"], AGENT_NAME)

    def test_content_signal_ai_input_no_is_out_like_md(self):
        r = self._run(url_resp=ProbeResponse(200, _HTML_HEADERS, _STATIC_TABLE_HTML.encode()),
                       robots_resp=_CONTENT_SIGNAL_ROBOTS)
        self.assertEqual(r["verdict"], "OUT")
        self.assertEqual(r["failed_criterion"], "a")
        self.assertIn("Content-Signal", r["reason"])

    def test_criterion_a_fails_on_404(self):
        r = self._run(url_resp=ProbeResponse(404, {}, b"not found"))
        self.assertEqual(r["verdict"], "OUT")
        self.assertEqual(r["failed_criterion"], "a")
        self.assertEqual(r["http_status"], 404)

    def test_unreachable_page_is_unknown_not_out(self):
        r = self._run(url_resp=ProbeResponse(None, {}, b"", error="TimeoutError"))
        self.assertEqual(r["verdict"], "UNKNOWN")
        self.assertIsNone(r["failed_criterion"])

    def test_criterion_b_fails_on_client_side_rendering(self):
        r = self._run(url_resp=ProbeResponse(200, _HTML_HEADERS, _CLIENT_SIDE_HTML.encode()))
        self.assertEqual(r["verdict"], "OUT")
        self.assertEqual(r["failed_criterion"], "b")

    def test_criterion_c_fails_with_no_documented_api_even_though_b_passed(self):
        # NY has no documented_open_data_api, so once the body is made to
        # LOOK statically readable, the probe must still stop at (c), not
        # leap to IN just because the markup happened to contain table cells.
        r = self._run(url_resp=ProbeResponse(200, _HTML_HEADERS, _STATIC_TABLE_HTML.encode()))
        self.assertEqual(r["verdict"], "OUT")
        self.assertEqual(r["failed_criterion"], "c")

    def test_undocumented_xhr_endpoint_does_not_make_a_state_eligible(self):
        # GA carries an undocumented_endpoint_note and no documented API. Even
        # with a body that parses as JSON (as if we pointed the probe at the
        # admin-ajax endpoint itself), the probe must not promote it past (c).
        fetch = _fetch_map({"robots.txt": _PERMISSIVE_ROBOTS,
                            STATES["GA"]["url"]: ProbeResponse(200, _JSON_HEADERS, b'{"data": []}')})
        r = probe_state("GA", fetch=fetch)
        self.assertEqual(r["verdict"], "OUT")
        self.assertEqual(r["failed_criterion"], "c")
        self.assertIn("undocumented", r["criterion_c"]["reason"])
        self.assertIn("undocumented_endpoint_note", r)

    def test_criterion_d_fails_when_a_required_field_label_is_missing(self):
        state = dict(STATES["NY"])
        STATES["NY_TEST_WITH_API"] = {**state, "documented_open_data_api": "test-api"}
        try:
            body = ("<table><tr><td>Employer</td><td>Notice Date</td>"
                    "<td>Acme Co</td><td>2026-01-01</td>"
                    "<td>Beta Co</td><td>2026-01-02</td></tr></table>")
            fetch = _fetch_map({"robots.txt": _PERMISSIVE_ROBOTS,
                                state["url"]: ProbeResponse(200, _HTML_HEADERS, body.encode())})
            r = probe_state("NY_TEST_WITH_API", fetch=fetch)
            self.assertEqual(r["verdict"], "OUT")
            self.assertEqual(r["failed_criterion"], "d")
        finally:
            del STATES["NY_TEST_WITH_API"]

    def test_all_four_criteria_pass_yields_in(self):
        state = dict(STATES["NY"])
        STATES["NY_TEST_ALL_PASS"] = {**state, "documented_open_data_api": "test-api"}
        try:
            body = ("<table><tr><td>Employer</td><td>Notice Date</td>"
                    "<td>Employees Affected</td></tr>"
                    "<tr><td>Acme Corp</td><td>2026-01-01</td><td>120</td></tr></table>")
            fetch = _fetch_map({"robots.txt": _PERMISSIVE_ROBOTS,
                                state["url"]: ProbeResponse(200, _HTML_HEADERS, body.encode())})
            r = probe_state("NY_TEST_ALL_PASS", fetch=fetch)
            self.assertEqual(r["verdict"], "IN")
            self.assertIsNone(r["failed_criterion"])
        finally:
            del STATES["NY_TEST_ALL_PASS"]


class RequestOrderTests(unittest.TestCase):
    def test_robots_txt_is_fetched_before_the_page_for_every_state(self):
        for code, cfg in STATES.items():
            calls = []
            fetch = _fetch_map(
                {"robots.txt": _STAR_BLOCKED_ROBOTS, cfg["url"]:
                 ProbeResponse(200, _HTML_HEADERS, _STATIC_TABLE_HTML.encode())},
                calls=calls)
            probe_state(code, fetch=fetch)
            self.assertTrue(calls, f"{code}: no request made at all")
            self.assertIn("robots.txt", calls[0],
                          f"{code}: first request was not robots.txt ({calls[0]})")
            # Blocked by robots -> the page itself must never be requested.
            self.assertEqual(len(calls), 1,
                             f"{code}: a request reached the page after a robots block")

    def test_no_request_at_all_before_robots_is_read(self):
        calls = []
        fetch = _fetch_map({"robots.txt": _PERMISSIVE_ROBOTS,
                            STATES["IL"]["url"]: ProbeResponse(
                                200, _HTML_HEADERS, _CLIENT_SIDE_HTML.encode())},
                           calls=calls)
        probe_state("IL", fetch=fetch)
        self.assertEqual(calls[0], STATES["IL"]["url"].split("://", 1)[0] + "://"
                         + STATES["IL"]["url"].split("://", 1)[1].split("/", 1)[0] + "/robots.txt")


class ReportShapeTests(unittest.TestCase):
    def test_build_report_covers_exactly_the_eight_states_and_costs_nothing(self):
        fetch = _fetch_map({
            "robots.txt": _PERMISSIVE_ROBOTS,
            **{STATES[c]["url"]: ProbeResponse(200, _HTML_HEADERS, _CLIENT_SIDE_HTML.encode())
               for c in STATES},
        })
        report = build_report(fetch=fetch, sleep=0)
        self.assertEqual(set(r["state"] for r in report["results"]), set(STATES))
        self.assertEqual(report["cost_usd"], 0.0)
        self.assertTrue(report["no_recall_measured"])
        self.assertNotIn("reference_events", report)
        self.assertNotIn("summary", report)

    def test_module_imports_and_writes_nothing_belonging_to_other_manifests(self):
        # It may MENTION the existing measurement files in prose (this module's
        # own docstring explains what it does NOT touch); what it must never do
        # is import the module that writes them or define a path that writes
        # to one of their filenames.
        import warn_state_probe as mod
        for forbidden_attr in ("MANIFEST_PATH", "WARN_MEASUREMENT_PATH", "MATCHED_FLOOR"):
            self.assertFalse(hasattr(mod, forbidden_attr))
        self.assertFalse(hasattr(mod, "recall_goldset"))
        self.assertFalse(hasattr(mod, "warn_reference_set"))
        # And the paths it DOES write are its own, new files.
        self.assertEqual(mod.REPORT_JSON.name, "us-warn-state-reprobe.json")
        self.assertEqual(mod.REPORT_MD.name, "us-warn-state-reprobe.md")


if __name__ == "__main__":
    unittest.main()
