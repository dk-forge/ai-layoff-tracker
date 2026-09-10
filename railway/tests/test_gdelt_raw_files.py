"""Quota-free GDELT GKG file fallback, hermetic and source-complete."""
import io
import os
import sys
import unittest
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources import gdelt_raw  # noqa: E402


START = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 9, 12, 15, tzinfo=timezone.utc)


def zipped_row(*, title="quarterly results", themes="", domain="example.com",
               url="https://example.com/a", stamp="20260909120000"):
    fields = [""] * 27
    fields[1] = stamp
    fields[3] = domain
    fields[4] = url
    fields[8] = themes
    fields[26] = f"<PAGE_TITLE>{title}</PAGE_TITLE>"
    raw = ("\t".join(fields) + "\n").encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("batch.gkg.csv", raw)
    return out.getvalue()


class RawFileContract(unittest.TestCase):

    def test_every_interval_requires_english_and_translingual_streams(self):
        urls = [url for _stamp, _stream, url in gdelt_raw.file_urls(START, END)]
        self.assertEqual(len(urls), 4)  # 12:00 + 12:15, two streams each
        self.assertTrue(any("20260909120000.gkg.csv.zip" in u for u in urls))
        self.assertTrue(any("20260909120000.translation.gkg.csv.zip" in u for u in urls))

    def test_native_entity_title_and_dismissal_theme_are_both_selected(self):
        payloads = {
            "english": zipped_row(
                title="Company &#x5927;&#x89C4;&#x6A21;&#x88C1;&#x5458; plan",
                url="https://example.com/native"),
            "translation": zipped_row(
                title="neutral title", themes="WB_2790_LABOR_REDUNDANCY;",
                url="https://example.org/theme"),
        }

        def fetch(url):
            return payloads["translation" if ".translation." in url else "english"]

        articles, complete = gdelt_raw.query_window_walk(
            START, START, ["大规模裁员"], fetch_fn=fetch, workers=1)
        self.assertTrue(complete)
        self.assertEqual({a["url"] for a in articles},
                         {"https://example.com/native", "https://example.org/theme"})
        native = next(a for a in articles if a["url"].endswith("native"))
        self.assertIn("大规模裁员", native["title"])

    def test_one_missing_required_stream_is_partial_not_silently_complete(self):
        def fetch(url):
            if ".translation." in url:
                return None
            return zipped_row(url="https://example.com/english")

        articles, complete = gdelt_raw.query_window_walk(
            START, START, ["layoffs"], fetch_fn=fetch, workers=1)
        self.assertFalse(complete)
        self.assertEqual(len(articles), 0)  # fixture title does not match

    def test_rows_outside_the_requested_timestamp_are_not_leaked_in(self):
        payload = zipped_row(title="layoffs", stamp="20260909115959")
        articles, complete = gdelt_raw.query_window_walk(
            START, START, ["layoffs"], fetch_fn=lambda _url: payload, workers=1)
        self.assertTrue(complete)
        self.assertEqual(articles, [])


if __name__ == "__main__":
    unittest.main()
