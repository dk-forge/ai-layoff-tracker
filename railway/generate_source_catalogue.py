"""Render the public source catalogue partial from railway/data/source_catalogue.json.

WHY. The country-by-country publisher research used to live in conversation.
A publisher we probed and refused is worth as much as one we wired -- it is
the difference between "we hold nothing on Bahrain" and "we hold nothing on
Bahrain because GDN Online's feed paths 404 and News of Bahrain serves HTML at
its rss.xml" -- and neither answer survives if the evidence is only in a chat
log. The catalogue is repo data; this script renders it, so the public page
can never drift from what the collectors and the research actually say.

Re-run after editing the catalogue:

    python3 railway/generate_source_catalogue.py

`tests/test_source_catalogue_render.py` fails if the committed partial does
not match a fresh render, so a catalogue edit that was never rendered goes red
in CI rather than quietly leaving a stale table on the site.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "data" / "source_catalogue.json"
OUT = (HERE.parent / "wordpress-plugin" / "ai-layoff-tracker" / "templates"
       / "partials" / "source-catalogue-table.php")

STATUS_LABEL = {
    "wired": ("Connected", "alt-cat-wired"),
    "researched": ("Researched, watched through its market sweep", "alt-cat-researched"),
    "refused": ("Researched, not connected", "alt-cat-refused"),
}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def render(data):
    rows = data["sources"]
    counts = data["counts"]
    out = [
        "<?php if (!defined('ABSPATH')) exit;",
        "/**",
        " * GENERATED FILE - do not edit by hand.",
        " * Source: railway/data/source_catalogue.json",
        " * Regenerate: python3 railway/generate_source_catalogue.py",
        " */",
        "?>",
        '<h2 id="alt-src-catalogue">Every publisher we researched, connected or not</h2>',
        "<p>This is the full publisher research behind the tracker, country by "
        "country. <b>Connected</b> means a collector reads that publisher's own "
        "feed. <b>Researched, watched through its market sweep</b> means the "
        "publisher is known and its stories reach us through its country's own "
        "news edition, searched in that country's own language, but we do not "
        "read a feed of its own. <b>Researched, not connected</b> means we "
        "checked it first hand and could not use it, and the reason is printed "
        "next to it. A country we hold nothing on should be a row that says "
        "why, not a gap you have to notice.</p>",
        '<p class="alt-muted">'
        f'{counts["total"]} publishers across the research set: '
        f'{counts["wired"]} connected, {counts["researched"]} watched through a '
        f'market sweep, {counts["refused"]} researched and not connected. '
        f'Feeds were probed first hand on {esc(data["measured"])}. '
        'Every refusal was measured at least twice. We never bypass a paywall, '
        'a bot wall or a certificate error, and we follow every robots.txt.</p>',
        '<div class="alt-health-table-wrap"><table class="alt-sortable '
        'alt-sources-table alt-catalogue-table">',
        "<thead><tr><th>Country or region</th><th>Publisher</th>"
        "<th>Language</th><th>Status</th><th>What we measured</th></tr></thead>",
        "<tbody>",
    ]
    for r in rows:
        label, cls = STATUS_LABEL[r["status"]]
        detail = r.get("reason") or r.get("evidence") or ""
        if r.get("note"):
            detail = f"{detail} {r['note']}".strip()
        out.append(
            "<tr>"
            f"<td>{esc(r['country'])}</td>"
            f"<td><b>{esc(r['publisher'])}</b></td>"
            f"<td>{esc(r['language'])}</td>"
            f'<td><span class="alt-cat-status {cls}">{esc(label)}</span></td>'
            f"<td>{esc(detail)}</td>"
            "</tr>")
    out += ["</tbody></table></div>", """<style>
  .alt-cat-status { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:700; white-space:nowrap; }
  .alt-cat-wired { background:rgba(34,197,94,.14); color:#15803d; }
  .alt-cat-researched { background:rgba(59,130,246,.14); color:#1d4ed8; }
  .alt-cat-refused { background:rgba(148,163,184,.18); color:var(--alt-muted); }
  .alt-catalogue-table td:nth-child(5) { max-width: 520px; }
</style>"""]
    return "\n".join(out) + "\n"


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(data), encoding="utf-8")
    print(f"wrote {OUT} ({data['counts']['total']} rows)")


if __name__ == "__main__":
    main()
