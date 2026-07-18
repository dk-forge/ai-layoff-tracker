# Country-period recall benchmark protocol

This protocol measures the tracker against a disclosed independent sample. It
does not estimate a country's total layoffs, certify the tracker as complete,
or describe the result as an accuracy score.

## A valid sample

Each sample must have one country and one closed date period. Its reference
events must be independently assembled before matching against this tracker:
a public dataset with terms permitting the comparison, or a documented manual
sample of public reports. The retained reference set must be openly reviewable
at a stable URL and contain the source URL, company, event date and stated job
count for every event. Do not use an opaque publisher corpus, a paywalled
dataset, or a sample created by searching this tracker first.

## Matching and publication

A reference event counts as matched only when an editor can identify the same
underlying event among canonical tracker rows. Matching may use company,
date/count context and retained source links; a similar article is not enough.
Cross-country and cross-period matches are excluded. Canonical deduplication
means several source reports supporting one event still count once.

Publish the denominator, matched numerator, reference-set URL, country,
period, method and measurement date through:

`POST /blog/wp-json/layoffs/v1/benchmarks/recall` (API key required)

The public read endpoint is:

`GET /blog/wp-json/layoffs/v1/benchmarks/recall`

The endpoint reports `sample_recall = matched_events / reference_events` and
always labels it as a sample measurement. Empty history means no current
measured sample; it never means zero layoffs or zero coverage.

## Independence gate

For a manually assembled reference set, source transcription and tracker
matching must be separated in time: first seal the independently transcribed
manifest, then match it to canonical events, then obtain a second-editor
review of every decision. A scheduled import's row count, an approximate
company-name search, or a model suggestion cannot substitute for a completed
same-event review. Keep the denominator and numerator absent until that gate
is complete.

## Current status

The historical June–July 2026 5/35 result was collected before the later
source and deduplication changes. It is retained in the project history as a
superseded baseline, not published through the endpoint as a current result.
Re-measure from an independently documented reference set before posting the
first public country-period benchmark.

The California June 2026 candidate has completed all three independence
passes with distinct actors (2026-07-18): the transcription review verified
every field against the official PDF and corrected a selection error at three
page boundaries before any match decision existed; the matching editor
recorded per-row evidenced decisions on the live API; and the publication
reviewer independently re-derived the positional sample from the sealed PDF
and re-verified all twelve decisions, confirming reference_events = 12 and
matched_events = 11. The manifest is `publication_reviewed_ready_to_retain`.
Publication now requires only the two key-holder steps in
`recall-reference-sets/CA_US_2026_06_PUBLICATION_CHECKLIST.md`: commit the
reviewed manifest at a stable public URL, then post the bounded figures to
the keyed endpoint with that URL. No recall number is public until then.
