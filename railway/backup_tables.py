#!/usr/bin/env python3
"""What the off-host backup is allowed to contain, and the guard that proves it.

Stdlib only, no network, no keys. `backup_export.py` uses it to decide what to
write; `ops_status.py` and the tests import the same definitions, so there is
exactly ONE statement of what may leave the host and it is the one under test.

THE GUARD IS THREE LAYERS AND ONLY THE FIRST TWO ARE THE GUARD
--------------------------------------------------------------
The artifact lands in a PUBLIC repository's release assets. `wp_alt_subscribers`
holds addresses, consent records and two live tokens, so "did anything personal
get in" cannot be answered by looking at the bytes afterwards and hoping.

  1. TABLE ALLOWLIST (complete).  The plugin's /backup-table route serves a
     hard-coded allowlist and 400s on everything else, and TABLES below names
     the same set on this side. The set of tables is finite and written down in
     two places that a test asserts agree, so this layer is COMPLETE: a table
     nobody named cannot be fetched.

  2. COLUMN ALLOWLIST (complete).  Every column of every exported table is
     pinned in TABLES. A column the server returns that is not pinned FAILS the
     run. This is what makes the boundary survive the future: the day somebody
     adds `email` to an exported table, the backup goes red and a human looks,
     instead of the column riding along. A new legitimate column is a one-line
     review-and-add, and the failure message says so.

  3. VALUE SHAPES (INCOMPLETE, and not the guard).  Layer 3 scans values for
     address-shaped and token-shaped strings. It is a DENYLIST and it is here
     as depth, never as the boundary: `excerpt`, `roles` and `source_url` hold
     arbitrary prose scraped from the open web, so no content rule over them
     can ever be complete. Do not "simplify" the guard down to this layer. Its
     one real job is catching a column that was pinned correctly but whose
     CONTENT changed meaning underneath us.

Layer 3 is proved by a positive control before it is trusted: the exporter
seeds a synthetic address and a synthetic token through the same scanner on
every run, and refuses to proceed if the scanner fails to flag them. A detector
that has only ever been observed to pass is not a detector. See
`assert_scanner_detects_seeded_personal_data`.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence


class PersonalDataInExport(Exception):
    """Raised when anything the export must never carry reached the artifact."""


class UnpinnedColumn(Exception):
    """Raised when the server returned a column the allowlist does not name."""


# --------------------------------------------------------------------------
# Layer 1 + 2: what may be exported, column by column.
#
# `restorable` mirrors the plugin's own annotation and is what docs/RECOVERY.md
# reads. `bulk` = /bulk rebuilds these rows. `derived` = rebuilt by re-running a
# job, so the file is evidence rather than the restore path. `manual` = there is
# no automated return path today, and the runbook says so out loud.
#
# THREE STATES, NOT TWO, AND THEY ARE DIFFERENT KEYS ON PURPOSE.
#   `optional`      the table may not EXIST on a given install (it ships with
#                   the release that introduces it, and FTPS deploys race). An
#                   absent optional table is skipped with a reason, never
#                   recorded as zero rows: "we could not read it" and "it is
#                   empty" are different answers.
#   `may_be_empty`  the table exists and holding nothing is a legitimate fact.
#                   `warn_transparency` is an editorial register nobody has
#                   written into yet. The first live export FAILED the whole
#                   run on it, which was this table being misclassified rather
#                   than the check being wrong.
# Every table states BOTH explicitly rather than defaulting, so adding a table
# forces the decision instead of inheriting one. A table declared
# `may_be_empty: False` still fails the run at zero rows, and that is the check
# that catches a walk which returned nothing.
# --------------------------------------------------------------------------
TABLES: Dict[str, dict] = {
    "layoffs": {
        "pk": "id",
        "restorable": "bulk",
        "optional": False,
        "may_be_empty": False,
        "why": "The curated corpus. The rows that cost real money in LLM extraction.",
        "columns": [
            "id", "post_id", "dedup_hash", "company", "company_key", "ticker",
            "job_count", "job_count_max", "layoff_date", "announcement_date",
            "industry", "country", "employer_country",
            "employer_country_evidence", "announcement_evidence", "state",
            "source_type", "verification_level", "source_name", "source_url",
            "ai_explicit", "ai_causation", "confidence", "review_status",
            "announced", "edited", "ai_language", "reason_tags", "roles",
            "role_categories", "roles_evidence", "excerpt", "event_id",
            "superset_of", "updated_at",
        ],
    },
    "events": {
        "pk": "id",
        "restorable": "derived",
        "optional": False,
        "may_be_empty": False,
        "why": "Canonical events. One real event counted once.",
        "columns": ["id", "event_key", "canonical_layoff_id", "created_at"],
    },
    "source_reports": {
        "pk": "id",
        "restorable": "derived",
        "optional": False,
        "may_be_empty": False,
        "why": "Every corroborating source for an event, kept instead of discarded.",
        "columns": [
            "id", "event_id", "report_key", "source_name", "source_type",
            "verification_level", "source_url", "excerpt", "evidence_hash",
            "ai_causation", "ai_language", "observed_at",
        ],
    },
    "archive": {
        "pk": "id",
        "restorable": "manual",
        "optional": False,
        "may_be_empty": False,
        "why": (
            "Wayback permalinks. Rate-limited into existence over about a week, "
            "so re-earning them costs another week."
        ),
        "columns": [
            "id", "url_hash", "source_url", "archived_url", "status",
            "attempts", "checked_at", "archived_at",
        ],
    },
    "company_directory": {
        "pk": "id",
        "restorable": "manual",
        "optional": False,
        "may_be_empty": False,
        "why": "Reviewed employer identities. Human review, not derivable.",
        "columns": [
            "id", "company_key", "slug", "display_name", "aliases",
            "review_status", "reviewed_at", "created_at", "updated_at",
        ],
    },
    "warn_transparency": {
        "pk": "id",
        "restorable": "manual",
        "optional": False,
        # LEGITIMATELY EMPTY TODAY. The first live export read 0 rows here and
        # the drift check FAILED the whole run on "a required table exported
        # ZERO rows", which was this table being misclassified rather than the
        # check being wrong. It is an editorial register that a human writes
        # into, and nobody has written into it yet. `optional` cannot express
        # that: the table EXISTS, so "absent" is the wrong word, and reporting
        # it as absent would hide the day it really did disappear.
        "may_be_empty": True,
        "why": "Editorial WARN-transparency register. Human adjudication, and empty until somebody adjudicates.",
        "columns": [
            "id", "record_key", "state", "employer", "related_layoff_id",
            "assessment_status", "notice_date", "affected_date",
            "exception_evidence", "adjudication_url", "source_name",
            "source_url", "evidence_excerpt", "evidence_hash", "created_at",
        ],
    },
    "source_runs": {
        "pk": "id",
        "restorable": "manual",
        "optional": False,
        "may_be_empty": False,
        "why": (
            "Collector telemetry. The history behind every staleness verdict; "
            "without it 'has this source ever worked' is unanswerable."
        ),
        "columns": ["id", "source", "status", "entries", "detail", "attempted_at"],
    },
    "digest_editions": {
        "pk": "id",
        "restorable": "manual",
        "optional": True,
        "may_be_empty": True,
        "why": "Published digest editions. They render public archive URLs that have been linked.",
        "columns": [
            "id", "send_id", "freq", "slug", "window_from", "window_to",
            "data_cut", "composed_at", "published_at", "sections", "corrections",
        ],
    },
    "digest_sends": {
        "pk": "id",
        "restorable": "manual",
        "optional": True,
        "may_be_empty": True,
        # Read the column list before assuming this is personal data. It is a
        # per-RUN log: how many were eligible and how many got it. There is no
        # address column and no recipient id, by deliberate design.
        "why": "Per-run send counts. No address column and no recipient id exists in this table.",
        "columns": ["id", "freq", "sent_at", "recipients", "eligible"],
    },
    "digest_links": {
        "pk": "id",
        "restorable": "manual",
        "optional": True,
        "may_be_empty": True,
        # Aggregate counters. No subscriber id, no IP, no user agent, no
        # per-click row, so it cannot answer "who clicked" even in principle.
        # `url` is a destination this site composed and allow-listed; the
        # per-recipient wrapper is built at render time and never stored.
        "why": "Aggregate click counters per (send, link). Cannot answer 'who clicked'.",
        "columns": ["id", "send_id", "link_hash", "url", "clicks"],
    },
    "post_claps": {
        "pk": "post_id",
        "restorable": "manual",
        "optional": True,
        "may_be_empty": True,
        "why": "A post id and a count. Nowhere to record who, when or from where.",
        "columns": ["post_id", "claps"],
    },
}


# --------------------------------------------------------------------------
# What is deliberately NOT exported. Naming it is the point: an exclusion
# nobody wrote down is one the next session re-litigates.
# --------------------------------------------------------------------------
FORBIDDEN_TABLES: Dict[str, str] = {
    "alt_subscribers": (
        "Personal data: email addresses, consent records, and two live tokens "
        "(confirm_token, unsub_token). The artifact is published to a PUBLIC "
        "repository. A private destination is an owner decision that has not "
        "been made; docs/RECOVERY.md states the options."
    ),
}

# Not owned by this plugin and not served by /backup-table. Rank Math's own
# redirect table is read through the existing keyed /seo-redirects route, whose
# column list is already pinned server-side, and is restored through Rank Math's
# own importer. docs/RECOVERY.md covers it.
EXTERNAL_TABLES: Dict[str, str] = {
    "rank_math_redirections": (
        "Owned by the Rank Math SEO plugin, not by this one. Backed up through "
        "the existing keyed /seo-redirects route; restored through Rank Math's "
        "own redirection importer, which is a manual step."
    ),
}


# --------------------------------------------------------------------------
# Layer 3: value shapes. DEPTH, NOT THE BOUNDARY. See the module docstring.
# --------------------------------------------------------------------------

# An address anywhere in a value. Deliberately broad: a false positive here
# costs a human two minutes, a false negative costs a breach notification.
_ADDRESS = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# The subscriber tokens are CHAR(64) hex. Nothing else this export carries is a
# bare 64-hex string EXCEPT evidence_hash, which is a sha256 of public source
# text and is pinned as an exception below rather than widened out of the rule.
_TOKEN64 = re.compile(r"\b[a-f0-9]{64}\b")

# Columns whose values are legitimately 64-hex and are NOT tokens. Listed one by
# one; there is no pattern-based escape from the token rule.
#
# THE URL ENTRIES WERE ADJUDICATED, NOT ASSUMED. The first live run of this
# export stopped on `layoffs.source_url: a 64-hex token-shaped string`, which is
# the guard doing its job. The row was
#
#   id=177145  source_name='Yahoo'
#   https://finnhub.io/api/news?id=58420ea0...3c3bfa
#
# a Finnhub article identifier that happens to be a sha256-shaped digest. One
# row in 11,800 scanned. A URL column can legitimately carry an external
# provider's hex id, and a SUBSCRIBER token can never reach one of these:
# `confirm_token` and `unsub_token` exist only in wp_alt_subscribers, which is
# not exportable, and the digest's own click wrapper stores the PLAIN
# destination (alt_digest_track_link) with the per-recipient part built at
# render time and never written down. So the exemption is correct and it is
# narrow: it covers URL columns by name, one at a time, and every non-URL
# column in every exported table still refuses a bare 64-hex string.
_HASH_COLUMNS = frozenset({
    ("source_reports", "evidence_hash"),
    ("warn_transparency", "evidence_hash"),
    # URL columns: an external provider's hex identifier is not our token.
    ("layoffs", "source_url"),
    ("source_reports", "source_url"),
    ("warn_transparency", "source_url"),
    ("warn_transparency", "adjudication_url"),
    ("archive", "source_url"),
    ("archive", "archived_url"),
    ("digest_links", "url"),
})

# `source_url` and `adjudication_url` can legitimately carry an address inside a
# public mailto: or a contact page a state WARN office publishes. Those are
# published-by-the-source addresses, not our subscribers, and refusing them
# would fail the backup over a state government's own contact link. They are
# named here so the exception is a decision on the record rather than a hole.
_ADDRESS_TOLERANT = frozenset({
    ("layoffs", "source_url"),
    ("layoffs", "excerpt"),
    ("layoffs", "roles_evidence"),
    ("layoffs", "employer_country_evidence"),
    ("layoffs", "announcement_evidence"),
    ("source_reports", "source_url"),
    ("source_reports", "excerpt"),
    ("warn_transparency", "source_url"),
    ("warn_transparency", "adjudication_url"),
    ("warn_transparency", "exception_evidence"),
    ("warn_transparency", "evidence_excerpt"),
    ("archive", "source_url"),
    ("archive", "archived_url"),
    ("digest_editions", "sections"),
    ("digest_editions", "corrections"),
})


def scan_value(table: str, column: str, value) -> List[str]:
    """Layer-3 findings for one cell. Empty list means nothing flagged.

    Returns REASONS, never the offending value: this result is printed into a
    public Actions log, and echoing the thing we are protecting would be the
    whole defect in reverse.
    """
    if not isinstance(value, str) or not value:
        return []
    found: List[str] = []
    if (table, column) not in _ADDRESS_TOLERANT and _ADDRESS.search(value):
        found.append(f"{table}.{column}: an address-shaped string")
    if (table, column) not in _HASH_COLUMNS and _TOKEN64.search(value):
        found.append(f"{table}.{column}: a 64-hex token-shaped string")
    return found


def scan_row(table: str, row: dict) -> List[str]:
    findings: List[str] = []
    for column, value in row.items():
        findings.extend(scan_value(table, column, value))
    return findings


def assert_columns_pinned(table: str, columns: Iterable[str]) -> None:
    """Layer 2. Raise on any column the allowlist does not name."""
    pinned = set(TABLES[table]["columns"])
    unknown = sorted(set(columns) - pinned)
    if unknown:
        raise UnpinnedColumn(
            f"{table}: the site returned column(s) {unknown} that "
            f"railway/backup_tables.py does not pin. THE BACKUP HAS STOPPED ON "
            f"PURPOSE. Read the new column's schema before doing anything else: "
            f"if it holds personal data it must be removed from the plugin's "
            f"alt_backup_tables() allowlist, and if it is ordinary data add it "
            f"to TABLES['{table}']['columns'] here. Do not widen this check."
        )


# --------------------------------------------------------------------------
# The positive control. Run before the scanner is trusted, every run.
# --------------------------------------------------------------------------

# Synthetic and obviously so. These never touch the artifact; they are fed to
# the scanner and thrown away.
SEEDED_ADDRESS = "seeded-canary@example-not-a-real-domain.invalid"
SEEDED_TOKEN = "f" * 64


def assert_scanner_detects_seeded_personal_data() -> None:
    """Prove layer 3 fires BEFORE trusting that it passed on real rows.

    A guard that has only ever been seen to pass is indistinguishable from a
    guard that does nothing, and this repo has been bitten by exactly that
    shape more than once. So the detector is exercised against a known-positive
    on every run, in the run's own environment, and a scanner that misses the
    seed stops the export rather than blessing it.

    Seeded through a column that is NOT in the tolerant set, because a control
    fired through a tolerated column would prove nothing.
    """
    probe_column = ("layoffs", "company")
    assert probe_column not in _ADDRESS_TOLERANT, "the control column must not be tolerated"
    assert probe_column not in _HASH_COLUMNS, "the control column must not be hash-exempt"

    if not scan_value("layoffs", "company", f"Acme Corp {SEEDED_ADDRESS}"):
        raise PersonalDataInExport(
            "POSITIVE CONTROL FAILED: the address detector did not flag a "
            "seeded address. The scanner is not working, so a clean scan of "
            "the real rows proves nothing. Export refused."
        )
    if not scan_value("layoffs", "company", f"Acme Corp {SEEDED_TOKEN}"):
        raise PersonalDataInExport(
            "POSITIVE CONTROL FAILED: the token detector did not flag a "
            "seeded 64-hex token. Export refused."
        )
    # And the exemptions must still be narrow: a tolerated column tolerates,
    # but a hash column must still refuse an ADDRESS.
    if not scan_value("source_reports", "evidence_hash", SEEDED_ADDRESS):
        raise PersonalDataInExport(
            "POSITIVE CONTROL FAILED: a hash-exempt column stopped flagging "
            "addresses, so the exemption is wider than it was written to be. "
            "Export refused."
        )


def assert_allowlists_disjoint() -> None:
    """Layer 1. The exported set and the forbidden set can never intersect."""
    overlap = set(TABLES) & set(FORBIDDEN_TABLES)
    if overlap:
        raise PersonalDataInExport(
            f"A forbidden table is in the export allowlist: {sorted(overlap)}. "
            f"Export refused."
        )
    # Belt and braces on the raw names too, since the plugin keys on the
    # prefixed physical name and this side keys on the logical one.
    for logical in TABLES:
        physical = f"alt_{logical}"
        if physical in FORBIDDEN_TABLES:
            raise PersonalDataInExport(
                f"'{logical}' resolves to the forbidden table '{physical}'. Export refused."
            )


def restorable_summary() -> Sequence[tuple]:
    """(table, restorable, why) for docs and for ops_status, in a stable order."""
    return tuple(
        (name, spec["restorable"], spec["why"])
        for name, spec in sorted(TABLES.items())
    )
