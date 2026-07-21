"""EDINET (Japan) + OpenDART (Korea) filing extraction — activates the probes.

For each recent official filing, downloads the body via the existing evidence
stage and, when it carries a STRONG Japanese/Korean layoff-vocabulary match,
routes the matched excerpts through the SAME DeepSeek extractor + guards + poster
as every other source. The extractor's verbatim-count and quotable-statement
gates mean a filing only becomes an event if it genuinely states a countable
layoff — so a misread foreign filing posts NOTHING rather than bad data. That
keeps the spirit of the human-review gate while making the pipeline autonomous.

Low yield by nature (few JP/KR filings state a parseable headcount cut). Ships
DORMANT per market; bounded per run to respect each API's rate limits.

Env: EDINET_API_KEY_JP, OPENDART_API_KEY_KR,
     FOREIGN_MAX (docs scanned/run/market, default 25), FOREIGN_DRY=1.
"""
import os
import sys
import time

from sources import edinet, opendart
from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

MAX_DOCS = max(1, min(120, int(os.environ.get("FOREIGN_MAX", "25"))))
DRY = os.environ.get("FOREIGN_DRY", "").lower() in {"1", "true", "yes"}


def _strong_excerpts(evidence):
    return " ".join(
        m.excerpt for m in getattr(evidence, "matches", ()) or ()
        if getattr(m, "tier", "") == "strong" and getattr(m, "excerpt", ""))


def _ingest(cfg, key):
    label = cfg["label"]
    posted = ai = scanned = candidates = 0
    try:
        target = cfg["latest_date"]()
        listing = cfg["list_fn"](target, api_key=key)
        docs = list(getattr(listing, cfg["list_attr"], ()) or ())
    except Exception as exc:
        print(f"{label}: list failed: {exc}", flush=True)
        if not DRY:
            report_source_health(label, "degraded", 0, f"list failed: {exc}")
        return 0, 0
    print(f"{label}: {len(docs)} filings listed for {target}; scanning up to {MAX_DOCS}", flush=True)
    for d in docs[:MAX_DOCS]:
        doc_id = d.get(cfg["doc_key"])
        if not doc_id:
            continue
        scanned += 1
        try:
            ev = cfg["evidence_fn"](doc_id, api_key=key)
        except Exception as exc:
            print(f"  {label}: evidence {doc_id} failed: {exc}", flush=True)
            time.sleep(0.6)
            continue
        time.sleep(0.6)
        if not getattr(ev, "is_review_candidate", False):
            continue
        candidates += 1
        excerpts = _strong_excerpts(ev)
        if not excerpts:
            continue
        company = next((d.get(k) for k in cfg["name_keys"] if d.get(k)), "")
        raw = {
            "source_type": "filing",
            "source_name": cfg["source_name"],
            "verification_level": "gold",  # official regulatory filing
            "source_url": getattr(ev, "source_url", "") or d.get("source_url", ""),
            "title": f"{company} — {cfg['source_name']}".strip(" —"),
            "raw_text": (f"{company}. {excerpts}").strip()[:2000],
        }
        try:
            ex = extract_layoff_data(raw)
        except Exception:
            continue
        if not ex:
            continue  # extractor guards rejected it (no verbatim count / not a layoff)
        if DRY:
            print(f"  DRY [{label}] {ex.get('company_name')} {ex.get('job_count')} ({ex.get('layoff_date')})", flush=True)
            continue
        if post_to_wordpress(ex) == "posted":
            posted += 1
            ai += 1 if ex.get("ai_explicit") else 0
            print(f"  + [{label}] {ex.get('company_name')} {ex.get('job_count')} ({ex.get('layoff_date')})", flush=True)
    detail = f"{scanned} scanned, {candidates} layoff-candidate filings, {posted} posted ({ai} AI)"
    print(f"{label}: {detail}", flush=True)
    if not DRY:
        report_source_health(label, "ok", posted, detail)
    return posted, ai


MARKETS = [
    {"env": "EDINET_API_KEY_JP", "label": "edinet_jp", "source_name": "EDINET filing (Japan)",
     "latest_date": edinet.latest_complete_list_date, "list_fn": edinet.list_documents_for_date,
     "list_attr": "documents", "evidence_fn": edinet.fetch_document_evidence,
     "doc_key": "document_id", "name_keys": ["filer_name"]},
    {"env": "OPENDART_API_KEY_KR", "label": "opendart_kr", "source_name": "OpenDART filing (Korea)",
     "latest_date": opendart.latest_complete_list_date, "list_fn": opendart.list_disclosures,
     "list_attr": "disclosures", "evidence_fn": opendart.fetch_document_evidence,
     "doc_key": "filing_number", "name_keys": ["corporation_name", "filer_name"]},
]


def run():
    active = [(m, os.environ.get(m["env"])) for m in MARKETS if os.environ.get(m["env"])]
    if not active:
        print("No EDINET_API_KEY_JP / OPENDART_API_KEY_KR set — foreign filings ingest dormant.")
        return
    tot_p = tot_ai = 0
    for cfg, key in active:
        p, a = _ingest(cfg, key)
        tot_p += p
        tot_ai += a
    print(f"foreign filings: {tot_p} posted ({tot_ai} AI)", flush=True)


def main():
    if not os.environ.get("WP_SITE_URL"):
        print("WP_SITE_URL required")
        return 1
    if not DRY and not os.environ.get("WP_API_KEY"):
        print("WP_API_KEY required (or set FOREIGN_DRY=1)")
        return 1
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY:
            report_source_health("foreign_filings", "degraded", 0, f"foreign filings failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
