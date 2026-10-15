"""Render the subscriber digest from SAMPLE data to local files. Sends nothing.

    python3 railway/digest_preview.py OUT_DIR [--archive]

Writes OUT_DIR/email.html (inline chart parts swapped for local files so a
browser can open it), OUT_DIR/chart-N.png, OUT_DIR/email.txt and, with
--archive, OUT_DIR/archive.html (the cleaned public copy). The data is
fictional and fixed; no network, no credential, no recipient. Used to make the
light/dark preview screenshots for review, and by tests as a realistic fixture.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import digest_send  # noqa: E402

UNSUB = ("https://asktherecruiter.com/blog/wp-admin/admin-post.php"
         "?action=alt_digest_unsub&t=" + "a" * 64)
MANAGE = ("https://asktherecruiter.com/blog/ai-layoff-tracker/preferences/1-"
          + "b" * 64 + "/")

SAMPLE_LAYOFF_HTML = (
    '<h2>AI Layoff Tracker</h2>'
    '<p data-alt="kicker">Verified job cuts this week</p>'
    '<p data-alt="stat">48,910</p>'
    '<p data-alt="scope">October 6-12, 2026, counted by the date the cuts '
    'take effect.</p>'
    '<p data-alt="change-up">&#9650; Up 6,120 on the week before</p>'
    '<p data-alt="finding">Three employers named AI as a reason for cuts '
    'this week, covering 4,300 jobs.</p>'
    '<h3>Last eight weeks</h3>'
    '<p data-alt="weeks">Aug 24 31,400 · Aug 31 28,900 · Sep 7 35,200 · '
    'Sep 14 39,800 · Sep 21 33,100 · Sep 28 37,600 · Oct 5 42,790 · '
    'Oct 12 48,910</p>'
    '<h3>Where the cuts landed</h3>'
    '<p data-alt="series">By region: United States 30,100 · Europe 9,800 · '
    'Asia Pacific 5,400 · Canada 2,100 · Latin America 1,510.</p>'
    '<h3>Top stories</h3>'
    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
    '<tr><td data-alt="label"><a href="https://asktherecruiter.com/blog/r/9">'
    'Acme Robotics (Austin, TX), source: SEC 8-K</a></td>'
    '<td data-alt="figure" align="right" width="30%">6,200 jobs</td></tr>'
    '<tr><td data-alt="label"><a href="https://asktherecruiter.com/blog/r/10">'
    'Northwind Health (Ohio), source: WARN notice</a></td>'
    '<td data-alt="figure" align="right" width="30%">2,940 jobs</td></tr>'
    '<tr><td data-alt="label-last"><a href="https://asktherecruiter.com/blog/r/11">'
    'Contoso Logistics (Rotterdam), source: news report</a></td>'
    '<td data-alt="figure-last" align="right" width="30%">1,150 jobs</td></tr>'
    '</table>'
    '<p><a href="https://asktherecruiter.com/blog/r/1">'
    'Open the AI Layoff Tracker</a></p>')

SAMPLE_LAYOFF_TEXT = (
    "AI Layoff Tracker\n"
    "48,910 verified job cuts, October 6-12, 2026, counted by the date the "
    "cuts take effect.\nUp 6,120 on the week before.\n"
    "Three employers named AI as a reason for cuts this week, covering 4,300 jobs.\n"
    "\nLast eight weeks\n"
    "  Aug 24 31,400 · Aug 31 28,900 · Sep 7 35,200 · Sep 14 39,800 · "
    "Sep 21 33,100 · Sep 28 37,600 · Oct 5 42,790 · Oct 12 48,910\n"
    "\nWhere the cuts landed\n"
    "  United States 30,100 · Europe 9,800 · Asia Pacific 5,400 · Canada "
    "2,100 · Latin America 1,510\n"
    "\nTop stories\n"
    "  Acme Robotics (Austin, TX), source: SEC 8-K: 6,200 jobs\n"
    "    https://asktherecruiter.com/blog/r/9\n"
    "  Northwind Health (Ohio), source: WARN notice: 2,940 jobs\n"
    "    https://asktherecruiter.com/blog/r/10\n"
    "  Contoso Logistics (Rotterdam), source: news report: 1,150 jobs\n"
    "    https://asktherecruiter.com/blog/r/11\n"
    "\nOpen the tracker: https://asktherecruiter.com/blog/ai-layoff-tracker/\n")

SAMPLE_ARTICLES_HTML = (
    '<h2>From the blog</h2>'
    '<ul><li><a href="https://asktherecruiter.com/blog/r/3">'
    'What a WARN notice actually tells you</a><br>The filing is a legal '
    'minimum, not a headcount.</li></ul>')
SAMPLE_ARTICLES_TEXT = ("From the blog\n"
                        "  - What a WARN notice actually tells you\n"
                        "    https://asktherecruiter.com/blog/r/3\n")


def sample_payload() -> dict:
    sections = ("layoff", "articles")
    return {
        "available": True, "freq": "weekly", "send_id": 0,
        "from": "2026-10-06", "to": "2026-10-12",
        "subject": "Weekly tracker digest",
        "sections": {
            "layoff": {"html": SAMPLE_LAYOFF_HTML, "text": SAMPLE_LAYOFF_TEXT},
            "articles": {"html": SAMPLE_ARTICLES_HTML, "text": SAMPLE_ARTICLES_TEXT},
        },
        "recipients": [{"id": 1, "email": "reader@example.invalid",
                        "unsub_url": UNSUB, "manage_url": MANAGE,
                        "lists": list(sections)}],
    }


def sample_message():
    data = sample_payload()
    return digest_send.build_message(
        data, data["recipients"][0],
        "AskTheRecruiter.com <digest@asktherecruiter.com>",
        "info@asktherecruiter.com")


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    out = argv[0]
    os.makedirs(out, exist_ok=True)
    message = sample_message()
    html = message.html
    for image in message.images:
        name = image["filename"]
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(image["png"])
        html = html.replace(f'src="cid:{image["cid"]}"', f'src="{name}"')
    with open(os.path.join(out, "email.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(os.path.join(out, "email.txt"), "w", encoding="utf-8") as fh:
        fh.write(message.text)
    if "--archive" in argv:
        import digest_archive
        record = digest_archive.public_record(sample_payload(), "weekly")
        with open(os.path.join(out, "archive-body.html"), "w", encoding="utf-8") as fh:
            fh.write(record["html"] if record else "")
    print(f"preview written to {out} ({len(message.images)} chart(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
