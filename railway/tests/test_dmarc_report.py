"""Local synthetic aggregate reports; no mail, DNS or receiver access."""
import gzip
import tempfile
import unittest
import zipfile
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO

from railway import dmarc_report as report


def xml(dkim="pass", spf="fail", count="3"):
    return (f'<feedback><report_metadata><date_range><begin>0</begin><end>60</end></date_range></report_metadata>'
            f'<policy_published><p>none</p><adkim>r</adkim><aspf>r</aspf></policy_published>'
            f'<record><row><source_ip>192.0.2.1</source_ip><count>{count}</count>'
            f'<policy_evaluated><dkim>{dkim}</dkim><spf>{spf}</spf></policy_evaluated></row>'
            f'<auth_results><dkim><selector>fixture</selector><domain>example.invalid</domain>'
            f'<result>{dkim}</result></dkim></auth_results></record></feedback>').encode()


class AggregateReports(unittest.TestCase):
    def test_xml_gzip_and_zip_produce_the_same_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            plain, gz, archive = base / "report.xml", base / "report.gz", base / "report.zip"
            plain.write_bytes(xml()); gz.write_bytes(gzip.compress(xml()))
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("report.xml", xml()); handle.writestr("readme.txt", "not XML")
            for path in [plain, gz, archive]:
                with self.subTest(format=path.suffix):
                    result = report.analyse([str(path)])
                    self.assertEqual((result["total"], result["failing"]), (3, 0))
                    self.assertEqual(result["selectors"], ["fixture@example.invalid"])
                    self.assertEqual(result["windows"], ["1970-01-01 00:00 .. 1970-01-01 00:01"])

    def test_exit_codes_distinguish_ready_not_ready_and_unknown(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            path = Path(directory) / "report.xml"
            for dkim, spf, count, expected in [("pass", "fail", "3", 0), ("fail", "pass", "3", 0), ("fail", "fail", "3", 1), ("fail", "fail", "0", 3)]:
                path.write_bytes(xml(dkim, spf, count))
                self.assertEqual(report.report([str(path)]), expected)
            self.assertEqual(report.report([str(Path(directory) / "missing.xml")]), 3)

    def test_public_return_contract_documents_not_ready_as_one(self):
        self.assertIn("1 =", report.report.__doc__)
        self.assertNotIn("2 =", report.report.__doc__)
