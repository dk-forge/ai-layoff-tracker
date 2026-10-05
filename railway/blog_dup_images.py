"""Remove the duplicated featured image from stored blog posts.

Calls the keyed layoffs/v1/blog-dup-images route (includes/blog-dup-images.php).
DRY_RUN=1 (default) only lists; DRY_RUN=0 rewrites the matched posts. Emits
GitHub annotations: one summary `dup-images` notice and one per post. The key
is read from WP_API_KEY and never printed.
"""
import json
import os
import sys
import urllib.request

URL = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/blog-dup-images"


def notices(data, dry_run):
    ids = ",".join(str(p["id"]) for p in data.get("posts", []))
    lines = [f"::notice title=dup-images::count={data.get('count', 0)} dry_run={int(dry_run)} "
             f"scanned={data.get('scanned', 0)} fixed={len(data.get('fixed', []))} ids={ids}"]
    for p in data.get("posts", []):
        snippet = " ".join(str(p.get("removed", "")).split())[:160].replace("::", ": :")
        lines.append(f"::notice title=dup-image post {p['id']}::thumb={p.get('thumb')} block={snippet}")
    return lines


def main():
    dry_run = os.environ.get("DRY_RUN", "1").strip().lower() not in ("0", "false", "no")
    key = os.environ["WP_API_KEY"]
    req = urllib.request.Request(
        URL + ("" if dry_run else "?apply=1"), method="GET" if dry_run else "POST",
        headers={"X-Layoff-API-Key": key, "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    for line in notices(data, dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
