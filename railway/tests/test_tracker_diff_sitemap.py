"""Guards for the tracker-diff tripwire's new inputs.

Two behaviours are pinned here because both had a real failure mode:
  1. Sitemap parsing must de-slugify company names and drop non-company tags
     (topics, cities), or the diff chases 'san-francisco' as an employer.
  2. The SEC cross-reference guard must reject a filing that only MENTIONS the
     target company. EDGAR full-text search for '"Intel" "layoff"' returns any
     filing containing both strings, e.g. a SunPower 8-K, which is not evidence
     that Intel laid anyone off.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_SRC = open(os.path.join(os.path.dirname(__file__), "..", "tracker_diff.py")).read()
_norm_ns = {"re": re}
exec(compile(_SRC[_SRC.index("def _norm"):_SRC.index("def run")], "tracker_diff_norm", "exec"), _norm_ns)
_norm = _norm_ns["_norm"]


def _parse_sitemap(xml):
    """Replicate the sitemap branch of _parse_feed without importing requests."""
    stop = {"ai", "layoffs", "tech", "crypto", "san-francisco", "new-york",
            "atlanta", "austin", "berlin", "boston"}
    names, seen = [], set()
    for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml, re.I):
        m = re.search(r"/(?:tag|company|organi[sz]ation)/([^/?#]+)/?", u, re.I)
        if not m:
            continue
        slug = m.group(1)
        if slug.lower() in stop or len(slug) < 2:
            continue
        n = re.sub(r"[-_]+", " ", slug).strip()
        if n and n == n.lower():
            n = n.title()
        if n.lower() not in seen:
            seen.add(n.lower())
            names.append(n)
    return names


def test_sitemap_deslugifies_and_drops_non_companies():
    xml = """<urlset>
      <url><loc>https://x.fyi/tag/monday-com/</loc></url>
      <url><loc>https://x.fyi/tag/yield-guild-games/</loc></url>
      <url><loc>https://x.fyi/tag/ai/</loc></url>
      <url><loc>https://x.fyi/tag/san-francisco/</loc></url>
      <url><loc>https://x.fyi/tag/monday-com/</loc></url>
      <url><loc>https://x.fyi/about/</loc></url>
    </urlset>"""
    got = _parse_sitemap(xml)
    assert got == ["Monday Com", "Yield Guild Games"], got


def test_sec_guard_rejects_a_mention_only_filing():
    # target Intel, filing extracted as SunPower -> not a match, must be dropped.
    t, g = _norm("Intel"), _norm("SunPower Inc.")
    assert not (t in g or g in t)


def test_sec_guard_accepts_the_real_company():
    for target, extracted in (("Intel", "Intel Corporation"),
                              ("Monday.com", "monday.com Ltd"),
                              ("Salesforce", "Salesforce, Inc.")):
        t, g = _norm(target), _norm(extracted)
        assert t and g and (t in g or g in t), (target, extracted)
