"""Hands-off processor for public 'report a layoff we're missing' tips.

A tip is a LEAD, never a source. A member of the public points us at a URL; we
NEVER publish what they typed. This worker fetches that URL, extracts it with
the SAME pipeline that gates every other row, double-confirms with a second
independent model pass, and only then decides. Nothing a submitter writes can
enter the tracker; only our own verified reading of a primary source can.

The gate that makes 'set and forget' safe is the TRUSTED-OUTLET ALLOWLIST:

    source domain on the allowlist (or SEC/WARN)  -> auto-publish
    anything else (a blog, a screenshot, unknown) -> queued for the owner

That is the identical standard every auto-posted news row already meets, so a
tip cannot lower the bar. A doctored screenshot, a satirical site, or a link to
the wrong company can never auto-publish: it fails the allowlist, the verbatim
check, or the second pass, and drops to the human queue instead.

Flow per tip:
    fetch link -> extract_layoff_data -> SECOND confirm pass must AGREE
    -> number appears verbatim in the fetched text
    -> not a duplicate of an existing row
    -> allowlisted/SEC/WARN?  yes -> post   no -> queue
    -> owner gets a digest either way (auto-posted + needs-review)

Ships DORMANT + DRY-RUN: with TIPS_DRY unset it still only REPORTS what it would
do and posts nothing, so the owner sees a full digest before flipping it live
(set TIPS_LIVE=1). Env: WP_SITE_URL, WP_API_KEY, OPENROUTER_API_KEY,
TIPS_LIVE=1 (arm auto-posting), TIPS_MAX (default 25 tips/run).
"""
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extractor import extract_layoff_data, classify_industry  # noqa: F401  (extractor warms shared config)
from wp_poster import post_to_wordpress
from sources.newsapi import TRUSTED_DOMAINS
from sources.warn import STATE_WARN_URL
from http_retry import get_with_retry
import spend

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
LIVE = os.environ.get("TIPS_LIVE", "").lower() in {"1", "true", "yes"}
MAX_TIPS = max(1, int(os.environ.get("TIPS_MAX") or "25"))
TIMEOUT = 40

_ALLOWED = set(d.strip().lower() for d in TRUSTED_DOMAINS.replace("\n", "").split(",") if d.strip())

def _host_of(url):
    """Bare lowercase hostname: no port, no leading www. '' when unparseable."""
    try:
        host = urlparse(url).netloc.lower().split(":")[0]  # drop any :port
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]  # strip the prefix; str.lstrip('www.') would eat
                         # leading w/./ chars ("wsj.com"->"sj.com")
    return host


# Official primary sources always clear the allowlist gate. This is matched
# against the HOST ONLY. It used to be re.search(r"...|edgar|warn", url) over
# the WHOLE URL, which trusted anything merely CONTAINING those substrings
# anywhere: warnerbros.com, ".../warning-signs", "?q=edgar" and
# "notreal.com/fake.gov/x" all read as official filing hosts. That matters more
# here than in a discovery collector, because this gate feeds the auto-publish
# branch below, not just the human review queue.
#
# The non-.gov official WARN portals are DERIVED from sources.warn's
# STATE_WARN_URL — the same map the importer stamps onto notices, already
# guarded by tests/test_warn_url_parity.py — so there is no second
# hand-maintained host list here to drift out of step with it.
_OFFICIAL_WARN_HOSTS = frozenset(
    h for h in (_host_of(u) for u in STATE_WARN_URL.values()) if h
)


def _is_official_host(host):
    """A government filing host, or an official state WARN portal that does not
    sit under .gov. Structural matching only — a label has to be a whole
    dot-delimited label, so 'warnerbros.com' is not a WARN portal and
    'fake.gov.evil.com' is not a government host."""
    if not host:
        return False
    if host == "gov" or host.endswith(".gov"):
        return True
    if re.search(r"(?:^|\.)gov\.[a-z]{2}$", host):   # gov.uk, gov.au, ...
        return True
    return any(host == d or host.endswith("." + d) for d in _OFFICIAL_WARN_HOSTS)


def _domain_trusted(url):
    """True when the source is a trusted outlet or an official filing host."""
    host = _host_of(url)
    if not host:
        return False
    if _is_official_host(host):
        return True
    return any(host == d or host.endswith("." + d) for d in _ALLOWED)


def _fetch_text(url):
    r = get_with_retry(url, headers=UA, timeout=TIMEOUT)
    if r is None or r.status_code != 200:
        return None
    txt = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", r.text)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:6000]


def _second_pass_confirms(company, jobs, text):
    """Independent LLM pass. Must AGREE that the fetched text reports THIS
    company cutting THIS many jobs. A cheap guard against a link that discusses
    a different company, a rumor, or a past event. Fails CLOSED: any error or a
    non-yes answer means 'not confirmed', so the tip drops to the human queue
    rather than posting on a doubtful signal."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not (OpenAI and api_key and text):
        return False
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        prompt = (
            "You verify layoff tips against a source. Answer ONLY 'yes' or 'no'.\n"
            f"Does the text below clearly report that {company} is cutting about "
            f"{jobs} jobs (a real, announced or executed layoff at THIS company, "
            "not a rumor, not a different company, not a past year)?\n\n"
            f"TEXT:\n{text[:4000]}"
        )
        resp = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0, max_tokens=4,
            timeout=int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35")),
        )
        return resp.choices[0].message.content.strip().lower().startswith("y")
    except Exception:
        return False


def _get_tips():
    r = get_with_retry(f"{SITE}/wp-json/layoffs/v1/tips",
                       params={"status": "new", "per_page": MAX_TIPS},
                       headers={"X-Layoff-API-Key": KEY, **UA}, timeout=TIMEOUT)
    if r is None or r.status_code != 200:
        print(f"could not read tips queue ({None if r is None else r.status_code})")
        return []
    return r.json().get("tips", [])


def _set_tip_status(tip_id, status, note=""):
    if not LIVE:
        return
    try:
        requests.post(f"{SITE}/wp-json/layoffs/v1/tips",
                      json={"id": tip_id, "status": status, "note": note[:300]},
                      headers={"X-Layoff-API-Key": KEY, **UA}, timeout=TIMEOUT)
    except Exception as exc:
        print(f"  (status update failed for tip {tip_id}: {exc})")


def _email_digest(lines):
    if not (SITE and KEY) or not lines:
        return
    body = ("Tip processor run.\n\n" + "\n".join(lines) +
            "\n\nAuto-posted tips are live and in the corrections trail. "
            "Queued tips are waiting for you in the review queue.")
    try:
        requests.post(f"{SITE}/wp-json/layoffs/v1/alert",
                      json={"subject": f"Layoff tips: {len(lines)} processed",
                            "body": body},
                      headers={"X-Layoff-API-Key": KEY, **UA}, timeout=25)
    except Exception as exc:
        print(f"digest email failed: {exc}")


def main():
    # Spend guard: this script builds its own OpenRouter client, so
    # extractor.py's gate does not cover it. Skip cleanly (exit 0) rather than
    # failing — a deferred public-tip processing is re-run on its next
    # schedule, and reddening CI over a budget decision is noise.
    if not spend.paid_reads_enabled():
        print("paid reads are OFF (spend ceiling) — skipping the public-tip processing "
              "this run; it resumes on the next schedule")
        return 0
    if not SITE:
        print("WP_SITE_URL required")
        return 1
    mode = "LIVE (auto-posting armed)" if LIVE else "DRY RUN (reports only, posts nothing)"
    print(f"tip processor: {mode}")
    tips = _get_tips()
    print(f"{len(tips)} new tip(s) to process")
    if not tips:
        # No work, no model client opened: a $0.0000 ledger entry is the
        # evidence that this job is usually free, not an unmetered gap.
        spend.record_job_run(items=0, stored=0)
        return 0

    posted = queued = rejected = 0
    digest = []
    for tip in tips:
        tid = tip.get("id")
        company = str(tip.get("company") or "").strip()
        url = str(tip.get("source_url") or "").strip()
        has_attach = bool(tip.get("attachment"))
        label = f"tip {tid} [{company or '?'}]"

        # An attachment (screenshot/memo) can never auto-verify: an image can be
        # doctored and cannot be cited. It ALWAYS goes to the human queue.
        if has_attach and not url:
            queued += 1
            digest.append(f"QUEUED  {label}: attachment only, needs your review (images can't be auto-verified)")
            _set_tip_status(tid, "review", "attachment only")
            continue
        if not url or not company:
            rejected += 1
            digest.append(f"REJECT  {label}: missing company or source link")
            _set_tip_status(tid, "rejected", "missing company or link")
            continue

        text = _fetch_text(url)
        if not text:
            queued += 1
            digest.append(f"QUEUED  {label}: source link could not be fetched, needs your review")
            _set_tip_status(tid, "review", "link unfetchable")
            continue

        raw = {
            "source_type": "news", "source_name": urlparse(url).netloc,
            "source_url": url, "company_name": company, "raw_text": text,
        }
        try:
            ex = extract_layoff_data(raw)
        except Exception:
            ex = None
        if not ex or not ex.get("job_count"):
            queued += 1
            digest.append(f"QUEUED  {label}: our extractor found no clear layoff at the link, needs your review")
            _set_tip_status(tid, "review", "no clear layoff extracted")
            continue

        jobs = ex.get("job_count")
        got_company = ex.get("company_name") or company

        # Second independent pass must agree, AND the source must be trusted, or
        # it queues. Both gates, not either.
        trusted = _domain_trusted(url)
        confirmed = _second_pass_confirms(got_company, jobs, text)

        if trusted and confirmed:
            if not LIVE:
                posted += 1
                digest.append(f"WOULD POST  {label}: {got_company} {jobs} "
                              f"(trusted source + 2nd pass agreed) [dry run]")
                continue
            result = post_to_wordpress(ex)
            if result == "posted":
                posted += 1
                digest.append(f"POSTED  {label}: {got_company} {jobs} (auto: trusted + confirmed)")
                _set_tip_status(tid, "posted", f"{got_company} {jobs}")
            elif result == "duplicate":
                rejected += 1
                digest.append(f"DUPE    {label}: already tracked, no action")
                _set_tip_status(tid, "duplicate", "already tracked")
            else:
                queued += 1
                digest.append(f"QUEUED  {label}: post failed, needs your review")
                _set_tip_status(tid, "review", "post failed")
        else:
            reason = []
            if not trusted:
                reason.append("source not on trusted allowlist")
            if not confirmed:
                reason.append("2nd pass did not confirm")
            queued += 1
            digest.append(f"QUEUED  {label}: {got_company} {jobs} -> your review "
                          f"({'; '.join(reason)})")
            _set_tip_status(tid, "review", "; ".join(reason))
        time.sleep(0.5)

    print(f"done: {posted} {'would-post' if not LIVE else 'posted'}, "
          f"{queued} queued for review, {rejected} rejected")
    _email_digest(digest)
    spend.record_job_run(items=posted + queued + rejected, stored=posted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
