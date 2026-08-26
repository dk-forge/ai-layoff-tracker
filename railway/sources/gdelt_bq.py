"""GDELT via Google's BigQuery public mirror (gdelt-bq.gdeltv2).

The public DOC API shares one rate-limited endpoint with the whole internet
and abandons windows under sustained 429s; the BigQuery mirror is the same
underlying dataset with per-project quota (1 TB of scanned bytes per month on
the free sandbox — orders of magnitude above this collector's use). This
module activates only when GCP_BIGQUERY_CREDENTIALS_JSON is configured and
callers fall back to the public API on any failure, so it can never reduce
availability.

Scan discipline: only needed columns are referenced, every query carries a
partition filter and a hard maximum_bytes_billed cap, and results are LIMITed.
The DOC API's 250-record cap does not apply here, which also removes the need
for the segment-query rotation on BigQuery-served windows.
"""
from __future__ import annotations

import json
import os
import re

MAX_BYTES_BILLED = 30 * 1024**3  # hard per-query cap, well inside free tier
RESULT_LIMIT = 900


def available() -> bool:
    return bool(os.environ.get("GCP_BIGQUERY_CREDENTIALS_JSON"))


def _client():
    from google.cloud import bigquery
    from google.oauth2 import service_account

    info = json.loads(os.environ["GCP_BIGQUERY_CREDENTIALS_JSON"])
    creds = service_account.Credentials.from_service_account_info(info)
    return bigquery, bigquery.Client(project=info["project_id"], credentials=creds)


def title_pattern(terms) -> str:
    """RE2 alternation over the shared discovery vocabulary (lowercased)."""
    escaped = [re.escape(t.lower()) for t in terms if t and t.strip()]
    return "|".join(escaped) if escaped else "$^"


def _seendate(date_int) -> str:
    s = str(date_int or "")
    return f"{s[0:8]}T{s[8:14]}Z" if len(s) == 14 else ""


def rows_to_articles(rows):
    """Map GKG rows to the DOC-API article shape the pipeline consumes."""
    articles = []
    for row in rows:
        url = (row.get("url") or "").strip()
        domain = (row.get("domain") or "").strip().lower()
        if not url or not domain:
            continue
        articles.append({
            "url": url,
            "domain": domain,
            "title": (row.get("title") or "").strip(),
            "seendate": _seendate(row.get("date_int")),
        })
    return articles


def company_pattern(company) -> str:
    """RE2 literal match for one employer name (lowercased, whitespace-normal)."""
    name = re.sub(r"\s+", " ", (company or "").strip().lower())
    return re.escape(name) if name else "$^"


def query_company_articles(company, start, end, terms):
    """Alternate coverage of one already-recorded event, narrowly matched.

    Used by the evidence-enrichment worker when a row's cited article and its
    archive snapshot are both unreadable: the page title must name the company
    AND carry the shared layoff vocabulary, inside a bounded partition window.
    The trusted-domain gate and the exact-quote evidence rules stay downstream
    and unchanged — this helper only surfaces candidate URLs.
    """
    bigquery, client = _client()
    sql = """
        SELECT
            DocumentIdentifier AS url,
            LOWER(SourceCommonName) AS domain,
            DATE AS date_int,
            REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>') AS title
        FROM `gdelt-bq.gdeltv2.gkg_partitioned`
        WHERE _PARTITIONTIME >= TIMESTAMP(@day_start)
          AND _PARTITIONTIME < TIMESTAMP(@day_end)
          AND DATE >= @window_start AND DATE <= @window_end
          AND REGEXP_CONTAINS(
              LOWER(IFNULL(REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>'), '')),
              @company_re)
          AND REGEXP_CONTAINS(
              LOWER(IFNULL(REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>'), '')),
              @title_re)
        LIMIT 60
    """
    job = client.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        query_parameters=[
            bigquery.ScalarQueryParameter("day_start", "STRING", start.strftime("%Y-%m-%d")),
            # exclusive end bound: the day AFTER the window's end date
            bigquery.ScalarQueryParameter("day_end", "STRING", _next_day(end)),
            bigquery.ScalarQueryParameter("window_start", "INT64", int(start.strftime("%Y%m%d%H%M%S"))),
            bigquery.ScalarQueryParameter("window_end", "INT64", int(end.strftime("%Y%m%d%H%M%S"))),
            bigquery.ScalarQueryParameter("company_re", "STRING", company_pattern(company)),
            bigquery.ScalarQueryParameter("title_re", "STRING", title_pattern(terms)),
        ],
    ))
    return rows_to_articles(dict(row) for row in job.result())


# The mirror has a row cap exactly like the public API's `maxrecords`, and it
# is binding in the same silent way. Named once so `gdelt_reach` can say
# whether a mirror window was TRUNCATED rather than complete.
#
# It is no longer binding on the ANSWER, only on one page of it: a window that
# fills a page is WALKED to completion by a deterministic (date, url) cursor
# (see query_window_walk), instead of losing everything below the 900th row the
# way a bare `LIMIT 900` did. The number stays as the page size.
MIRROR_LIMIT = 900

# A hard ceiling on pages per window, so a pathological window (or a stuck
# cursor) can never issue unbounded BigQuery jobs. 40 pages * 900 rows = 36,000
# candidate URLs for one window is far above anything real; hitting it means the
# window is PARTIAL, recorded as such, and retried — never silently truncated.
MAX_PAGES = 40


def query_window_page(start, end, terms, after=None, limit=MIRROR_LIMIT):
    """One deterministic page of the window, ordered by (DATE, url).

    `after` is the (date_int, url) cursor of the last row of the previous page;
    rows are returned strictly after it, so paging by the last cursor walks the
    whole window with no gap and no overlap. A bare `LIMIT` with no ORDER BY (the
    old shape) returned an ARBITRARY 900 rows and dropped the rest with no trace.

    Returns raw row dicts (url/domain/date_int/title) in cursor order, so the
    caller can read the last row as the next page's cursor.
    """
    bigquery, client = _client()
    cursor_clause = ""
    params = [
        bigquery.ScalarQueryParameter("day_start", "STRING", start.strftime("%Y-%m-%d")),
        # exclusive end bound: the day AFTER the window's end date
        bigquery.ScalarQueryParameter("day_end", "STRING", _next_day(end)),
        bigquery.ScalarQueryParameter("window_start", "INT64", int(start.strftime("%Y%m%d%H%M%S"))),
        bigquery.ScalarQueryParameter("window_end", "INT64", int(end.strftime("%Y%m%d%H%M%S"))),
        bigquery.ScalarQueryParameter("title_re", "STRING", title_pattern(terms)),
        bigquery.ScalarQueryParameter("page_limit", "INT64", int(limit)),
    ]
    if after is not None:
        after_date, after_url = after
        # Keyset pagination: strictly after the last (DATE, url) already read.
        cursor_clause = (
            "          AND (DATE > @after_date "
            "OR (DATE = @after_date AND DocumentIdentifier > @after_url))\n"
        )
        params.append(bigquery.ScalarQueryParameter("after_date", "INT64", int(after_date)))
        params.append(bigquery.ScalarQueryParameter("after_url", "STRING", str(after_url)))
    sql = f"""
        SELECT
            DocumentIdentifier AS url,
            LOWER(SourceCommonName) AS domain,
            DATE AS date_int,
            REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>') AS title
        FROM `gdelt-bq.gdeltv2.gkg_partitioned`
        WHERE _PARTITIONTIME >= TIMESTAMP(@day_start)
          AND _PARTITIONTIME < TIMESTAMP(@day_end)
          AND DATE >= @window_start AND DATE <= @window_end
          AND (
            V2Themes LIKE '%UNEMPLOYMENT%'
            OR REGEXP_CONTAINS(
                LOWER(IFNULL(REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>'), '')),
                @title_re)
          )
{cursor_clause}        ORDER BY DATE, DocumentIdentifier
        LIMIT @page_limit
    """
    job = client.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        query_parameters=params,
    ))
    return [dict(row) for row in job.result()]


def query_window_walk(start, end, terms, page_limit=MIRROR_LIMIT, max_pages=MAX_PAGES,
                      page_fn=None):
    """Walk one window to completion across deterministic pages.

    Returns (articles, complete). `complete` is False only when the walk hit
    `max_pages` with a still-full final page — the one honest "we did not reach
    the end" signal, which the caller records as PARTIAL and retries. Every other
    case is complete: a short (or empty) final page means the window is exhausted.

    `page_fn` is injectable so this is testable with no BigQuery client at all;
    it defaults to `query_window_page`.
    """
    fetch = page_fn or query_window_page
    articles, seen, after = [], set(), None
    complete = True
    for _ in range(max_pages):
        rows = fetch(start, end, terms, after=after, limit=page_limit)
        for a in rows_to_articles(rows):
            if a["url"] not in seen:
                seen.add(a["url"])
                articles.append(a)
        if len(rows) < page_limit:
            break
        last = rows[-1]
        after = (last.get("date_int"), (last.get("url") or "").strip())
    else:
        # Loop exhausted max_pages without a short page: there is still more to
        # read, so this window is only partially walked.
        complete = False
    return articles, complete


def query_window_articles(start, end, terms):
    """All matching articles in [start, end] from the GKG mirror.

    Backward-compatible thin wrapper: returns just the walked article list.
    Callers that need to know whether the walk finished use query_window_walk.
    """
    articles, _complete = query_window_walk(start, end, terms)
    return articles


def _next_day(end):
    from datetime import timedelta
    return (end + timedelta(days=1)).strftime("%Y-%m-%d")
