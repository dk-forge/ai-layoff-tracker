# Recall reference-set manifests

This directory holds reproducible input manifests for the country-period
recall protocol in `../RECALL_BENCHMARK_PROTOCOL.md`. A manifest is not a
tracker import and never creates, edits or deletes a layoff event.

## Publication rule

Only publish a recall measurement after all of the following are true:

1. The manifest has one country and one closed period.
2. Every row was assembled independently of the tracker and retains an
   openly reviewable primary/reference URL, company, relevant event date and
   stated job count.
3. An editor has recorded a same-event canonical match or a documented
   non-match for every row. A similar article or company name is not enough.
4. A reviewer has checked the row count, country/period boundary and every
   match decision.
5. The committed manifest has a stable public GitHub URL. Only then may its
   bounded numerator and denominator be posted to
   `/benchmarks/recall`.

Do not post a percentage from a template, a partial manifest, an opaque
publisher corpus, a paywalled dataset, or a reference set assembled by first
searching this tracker. Recall is a sample measurement, not a completeness or
accuracy claim.

## California June 2026 template

`ca-us-2026-06.template.json` reserves the first candidate scope: United
States, California notices, 1–30 June 2026. The candidate reference document
is the California Employment Development Department's FY 2025–26 public WARN
report. It exposes employer, notice/effective dates and affected-worker counts,
but the template deliberately contains **no event rows, matches, denominator,
numerator or recall result**.

Before converting it to a published manifest, copy the template to a new
non-template filename, add one independently transcribed row per selected
official notice, record the source row/page location, and have a second editor
perform the matching review. Keep the selection rule fixed before any tracker
lookup—for example, a reproducible systematic sample over the official June
notice rows. Do not silently exclude no-match rows.

This is a United States country-period sample with a clearly disclosed
California source scope. It does not measure all United States layoffs or all
California layoffs outside the relevant WARN requirements.
