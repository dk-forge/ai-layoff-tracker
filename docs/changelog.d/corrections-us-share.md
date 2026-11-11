---
version: 2.20.312
type: fix
area: data-integrity
date: 2026-11-11
---
- db.php: `alt_row_in_us_headline()` (country OR employer_country = United States, the us_all_time rule); `alt_log_correction(..., $jobs, $us_jobs)` stores `us_jobs` beside a measured `jobs` (absent stays absent; a same-day collapse with an unmeasured share drops it); /trash (all three id spaces), the undated cleanup and /merge-events pass it; /corrections serves it.
- corrections_reader.DisclosedRemovals.split_by_side(); data_integrity.CONTAINMENT_SIDE_FIELDS: ContainmentInvariant subtracts disclosed non-US removals from the complement and PASSes under the floor; any unplaced entry leaves the FAIL.
- Tests: test_disclosed_removals_by_side.py (+11), test_corrections_log_job_counts.py merge-call assertion extended.
