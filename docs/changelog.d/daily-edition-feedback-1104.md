---
version: 2.20.296
type: fix
area: digest
date: 2026-11-05
---
- subscribe.php `alt_digest_compose_articles`: section labelled ALT_CAREER_RESOURCES with an opt-in note; per-item "Why it matters" and kind-specific CTA (`alt_digest_article_kind`); excerpts containing a question fall back to the first real sentence; subject metric is "N ways to strengthen your applications" instead of the featured title.
- Gate: `alt_digest_articles_only_for_layoff_reader` (wp_mail sender) and `digest_send.build_message` (relay) send nothing when a layoff-list reader would get articles alone; `usable_sections` puts articles last. Uses the existing `consent_articles` list, no new consent, no migration.
- Footer condensed in both mirrors (alt_digest_footer_blocks / FOOTER_BLOCKS), one paragraph in the relay HTML; tracking sentences unchanged.
- Tests: test_digest_edition_feedback_1104.py; test_digest_career_insights.py updated for the 2026-11-04 ruling.
