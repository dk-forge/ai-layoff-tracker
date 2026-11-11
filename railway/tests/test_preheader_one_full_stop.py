"""A preheader ends in ONE full stop, never "..".

The talent daily of 2026-11-11 (data/email_archive/2026/11/2026-11-11-daily.html)
shipped the preheader "11 hiring signals, led by ... (plans 500 roles in
Bordeaux).." because alt_talent_render_daily passes a lead that already ends
in a full stop and alt_digest_fit_preheader appends another. The fix belongs in
the one function every preheader goes through, so this runs the real PHP.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
SUBSCRIBE = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker", "includes",
    "subscribe.php"))
PHP = shutil.which("php")


def _extract(name):
    with open(SUBSCRIBE, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"\nfunction %s\s*\(.*?\n\}" % re.escape(name), src, re.S)
    if not m:
        raise AssertionError("could not extract %s" % name)
    return m.group(0)


def _fit(cases):
    runner = ("<?php\n" + _extract("alt_digest_fit_preheader") + "\n"
              "$out = array();\n"
              "foreach (json_decode($argv[1], true) as $c) {\n"
              "    $out[] = alt_digest_fit_preheader($c[0], $c[1]);\n"
              "}\n"
              "echo json_encode($out);\n")
    with tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(runner)
    try:
        res = subprocess.run([PHP, fh.name, json.dumps(cases)],
                             capture_output=True, text=True, check=True)
    finally:
        os.unlink(fh.name)
    return json.loads(res.stdout)


@unittest.skipUnless(PHP, "php not installed")
class PreheaderOneFullStop(unittest.TestCase):
    def test_lead_that_already_ends_in_a_full_stop(self):
        lead = ("11 hiring signals, led by Electro Mobility Materials Europe "
                "(EMME) (plans 500 roles in Bordeaux).")
        self.assertEqual(_fit([[lead, []]]), [lead])

    def test_full_stop_before_optional_clauses(self):
        self.assertEqual(_fit([["3 hiring signals.", ["2 funding rounds"]]]),
                         ["3 hiring signals, 2 funding rounds."])

    def test_plain_lead_still_gets_its_full_stop(self):
        self.assertEqual(_fit([["3 hiring signals", []]]), ["3 hiring signals."])

    def test_no_preheader_ever_ends_in_two_full_stops(self):
        for line in _fit([["a.", []], ["a..", ["b"]], ["a. ", []]]):
            self.assertFalse(line.endswith(".."), line)


if __name__ == "__main__":
    unittest.main()
