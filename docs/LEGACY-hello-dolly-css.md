# The CSS that lives inside a plugin pretending to be Hello Dolly

**This file is a BACKUP, not a live stylesheet.** Nothing loads it. It exists so
that if the plugin holding the real copy is overwritten, the site can be
restored from version control in minutes instead of reconstructed from memory.

## Why it exists

The WordPress install at `/blog` carries a plugin that declares itself
`Hello Dolly v1.7.3 by Matt Mullenweg`. Every line of the real Hello Dolly is
gone; roughly 500 lines of this site's own code sit in its place. An earlier
Claude session put them there, using a stock plugin slot as a dumping ground.

WordPress still treats that slot as the plugin from wordpress.org. **The next
Hello Dolly update overwrites the file**, which does not merely restore the
Mailjet box we removed on 2026-08-15 - it deletes the blog card grid, the
article typography and the mobile fixes at the same instant, with no error and
nothing to roll back to. Auto-updates were switched off through WordPress core
on 2026-08-15, but the operator who did it reported that Bluehost's own plugin
may centrally override that flag, so the protection is UNCERTAIN, not proven.

Hence this copy. Restoring is then a paste, not an archaeology exercise.

## What is NOT captured here

Only the two CSS blocks. The rest of that file was migrated or retired on
2026-08-15: the analytics footer and the two read-only REST endpoints moved to a
WPCode snippet; the public subscribe endpoint, the post-writing endpoint, the
Mailjet forwarding block, the Mailjet box and the Mailjet loader script were all
disabled. Verified live: the Mailjet iframe, its loader and the box markup are
gone, and `atr/v1` now exposes only `/audit` and `/posts`.

## The load-order trap, which is why this is a backup and not a port

`assets/blog-reading.css` in this repo was written to **override** the first
block below. In particular it overrides

    .entry-content h2 { margin: 2.2rem 0 .8rem !important; }

whose `0` sets the left and right margins and therefore cancels the automatic
side margins WordPress uses to centre constrained content. That single shorthand
is what put every heading 420px away from its own paragraph until 2026-08-15.

So this CSS cannot simply be pasted into this plugin and enqueued. If our copy
loads AFTER `blog-reading.css`, the override loses and the two-column defect
comes straight back. A real port has to establish the load order deliberately
and prove it by measurement, not assume it. Until that is done, this file stays
inert.

## Block 1 - `atr_css()`, injected with `wp_add_inline_style('wp-block-library', ...)` at priority 99

```css
/* === AskTheRecruiter.com Custom Styles === */

/* Hide date, author, captions everywhere */
figcaption,.wp-element-caption{display:none!important}
.wp-block-post-author-name,.wp-block-post-author,.wp-block-post-author-biography{display:none!important}
.wp-block-post-date,.time,wp-block-post-date{display:none!important}
.wp-block-post-terms{display:none!important}

/* Override any theme rule hiding post titles on homepage */
.home .wp-block-post-title,
.home .wp-block-post-template .wp-block-post-title {
  display: block !important;
}
.home .wp-block-post-template .wp-block-post-title a {
  display: block !important;
}

/* Hide "Written by in [category]" author meta group */
.wp-block-group.has-small-font-size{display:none!important}
.wp-block-post-author{display:none!important}

/* ============================================
   BLOG CARD GRID - Professional layout
   ============================================ */

/* Grid container */
.wp-block-query .wp-block-post-template,
.wp-block-post-template {
  display: grid !important;
  grid-template-columns: repeat(3, 1fr) !important;
  gap: 1.75rem !important;
  margin: 0 !important;
  padding: 0 !important;
  list-style: none !important;
}

/* Individual card */
.wp-block-post-template .wp-block-post,
.wp-block-post-template li.wp-block-post {
  display: flex !important;
  flex-direction: column !important;
  background: #fff !important;
  border: 1px solid #e8e8e8 !important;
  border-radius: 10px !important;
  overflow: hidden !important;
  transition: box-shadow 0.2s ease, transform 0.2s ease !important;
  margin: 0 !important;
  padding: 0 !important;
}

.wp-block-post-template .wp-block-post:hover,
.wp-block-post-template li.wp-block-post:hover {
  box-shadow: 0 6px 20px rgba(0,0,0,0.10) !important;
  transform: translateY(-2px) !important;
}

/* Card: featured image area - ALWAYS takes same space */
.wp-block-post-template .wp-block-post-featured-image {
  width: 100% !important;
  aspect-ratio: 16 / 9 !important;
  overflow: hidden !important;
  flex-shrink: 0 !important;
  background: #f0f4f0 !important;
  display: block !important;
}

/* When no image, still reserve the space with a subtle gradient */
.wp-block-post-template .wp-block-post-featured-image:empty {
  background: linear-gradient(135deg, #e8efe8 0%, #d4e4d4 100%) !important;
  min-height: 180px !important;
}

.wp-block-post-template .wp-block-post-featured-image img {
  width: 100% !important;
  height: 100% !important;
  object-fit: cover !important;
  display: block !important;
}

.wp-block-post-template .wp-block-post-featured-image a {
  display: block !important;
  width: 100% !important;
  height: 100% !important;
}

/* Card: content area below image */
.wp-block-post-template .wp-block-post-title,
.wp-block-post-template h2.wp-block-post-title {
  font-size: 1rem !important;
  font-weight: 700 !important;
  line-height: 1.4 !important;
  color: #1a1a1a !important;
  margin: 1rem 1rem 0.5rem !important;
  padding: 0 !important;
}

.wp-block-post-template .wp-block-post-title a {
  text-decoration: none !important;
  color: inherit !important;
}

.wp-block-post-template .wp-block-post-title a:hover {
  color: #2d5a2d !important;
}

/* Card: excerpt */
.wp-block-post-template .wp-block-post-excerpt {
  font-size: .85rem !important;
  color: #555 !important;
  margin: 0 1rem 1rem !important;
  line-height: 1.55 !important;
  flex-grow: 1 !important;
}

.wp-block-post-template .wp-block-post-excerpt p {
  margin: 0 !important;
}

.wp-block-post-template .wp-block-post-excerpt__more-link {
  display: none !important;
}

.wp-block-post-template .wp-block-post-date {
  display: none !important;
}

.wp-block-post-template .wp-block-post-terms {
  display: none !important;
}

/* === ARTICLE PAGE === */
.single .wp-block-post-featured-image,
.single-post .wp-block-post-featured-image {
  margin: 0 0 2rem !important;
  border-radius: 10px !important;
  overflow: hidden !important;
}

.single .wp-block-post-featured-image img,
.single-post .wp-block-post-featured-image img {
  width: 100% !important;
  object-fit: cover !important;
  display: block !important;
}

.entry-content p,.wp-block-post-content p {
  font-size: 1.05rem !important;
  line-height: 1.78 !important;
  color: #2a2a2a !important;
  margin-bottom: 1.2rem !important;
}

.entry-content h2,.wp-block-post-content h2 {
  font-size: 1.45rem !important;
  font-weight: 700 !important;
  color: #1a1a1a !important;
  margin: 2.2rem 0 .8rem !important;
  padding-bottom: .35rem !important;
  border-bottom: 2px solid #eef3ee !important;
}

.entry-content h3,.wp-block-post-content h3 {
  font-size: 1.15rem !important;
  font-weight: 600 !important;
  color: #222 !important;
  margin: 1.5rem 0 .5rem !important;
}

.wp-block-separator {
  border-top: 2px solid #eef3ee !important;
  margin: 2.5rem 0 !important;
}

.wp-block-post-terms {
  display: none !important;
}

/* FAQ section styling */
.entry-content h2.wp-block-heading:last-of-type,
.wp-block-post-content h2.wp-block-heading:last-of-type {
  border-bottom: none !important;
}

/* === PAGINATION === */
.wp-block-query-pagination {
  margin: 2.5rem 0 1rem !important;
  justify-content: center !important;
}

/* === RESPONSIVE === */
@media (max-width: 900px) {
  .wp-block-post-template {
    grid-template-columns: repeat(2, 1fr) !important;
    gap: 1.25rem !important;
  }
}

@media (max-width: 600px) {
  .wp-block-post-template {
    grid-template-columns: 1fr !important;
    gap: 1rem !important;
  }
  .wp-block-post-template .wp-block-post-title {
    font-size: .95rem !important;
  }
}

/* === HOMEPAGE SECTION HEADERS === */
.wp-block-heading {
  font-size: 1.5rem;
  font-weight: 700;
  text-align: center;
  margin-bottom: 1rem;
}

/* Cloudflare / admin bar spacing fix */
html body.admin-bar { padding-top: 32px !important; }
```

## Block 2 - `atr_mobile_fixes_head()`, echoed on `wp_head` at priority 100

```css
/* Prevent any element from forcing horizontal scroll on small screens */
@media (max-width: 781px){
html, body { overflow-x: hidden; }

/* Category / blog post grids: collapse multi-column query loops to a single column
so card titles have full width instead of wrapping one letter per line. */
.wp-block-post-template.is-layout-grid,
ul.wp-block-post-template.columns-2,
ul.wp-block-post-template.columns-3,
ul.wp-block-post-template.columns-4 {
	grid-template-columns: 1fr !important;
	display: grid !important;
}
.wp-block-post-template.is-layout-grid > li,
ul.wp-block-post-template > li {
	width: auto !important;
	min-width: 0 !important;
}
.wp-block-post-title, .wp-block-post-title a { word-break: normal !important; overflow-wrap: anywhere; }
}

/* Header CTA button overflowing the viewport on phones.
   The hamburger menu already provides navigation, and the hero has its own CTA,
   so hide the header button on small screens to remove the clipped overflow. */
@media (max-width: 600px){
.atr-header .wp-block-button,
.atr-header .wp-block-buttons {
	display: none !important;
}
/* Keep the header tidy: allow it to use the freed space */
.atr-header { flex-wrap: nowrap !important; }
}
```

## If the plugin file is wiped before the real port lands

1. Paste Block 1 into a WPCode PHP snippet using
   `wp_add_inline_style('wp-block-library', $css)` on `wp_enqueue_scripts` at
   priority 99, and Block 2 into a snippet echoing a `<style>` on `wp_head` at
   priority 100. Same hooks and same priorities as the original, because the
   overrides in `blog-reading.css` were measured against exactly that order.
2. Then re-measure the article page. The heading and paragraph must share an x
   position; if headings jump to the left edge, the load order is wrong.

Recorded 2026-08-16.
