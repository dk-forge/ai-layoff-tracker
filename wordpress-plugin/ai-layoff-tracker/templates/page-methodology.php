<?php if (!defined('ABSPATH')) exit;
/**
 * Standalone methodology page. The detailed version of what used to live in the
 * collapsed #alt-metric-definitions block on the tracker. The tracker keeps a
 * short overview that links here; this is the full, formatted reference for
 * journalists and researchers.
 */
// Coverage counts have exactly one owner, alt_coverage_counts(); the old
// literal 48 fallback here was itself one of the disagreeing numbers, so
// there is no hardcoded figure to fall back to any more.
$alt_warn_phrase = function_exists('alt_warn_states_phrase') ? alt_warn_states_phrase() : 'covered US states';
?>
<main class="alt-wrap alt-method-page">
  <p class="alt-eyebrow">AskTheRecruiter · AI Layoff Tracker</p>
  <h1>Methodology &amp; sources</h1>
  <p class="alt-lead"><span class="alt-lead-text">How we collect, verify, classify and count every number on this tracker. We wrote it for journalists and researchers who need to check a figure before they cite it. We estimate nothing into existence. Every published number traces back to a primary source.</span></p>
  <p><a href="<?php echo esc_url(home_url('/ai-layoff-tracker/')); ?>">&larr; Back to the tracker</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/sources/')); ?>">Data sources</a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>"><?php echo esc_html(alt_page_link_label('page-ai-quotes.php', 'AI layoffs, in the employer\'s own words')); ?></a> · <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/press/')); ?>">Press kit and soundbites</a></p>

  <?php /*
     A CONTENTS LIST IS A PROMISE ABOUT WHAT IS DOWN THERE.

     Seven of these thirteen labels used to be a paraphrase of the heading
     they land on, and one pair reversed its meaning: "Coverage & limits"
     landed on "Coverage and honest limitations", "Self-audit" on "The tracker
     audits itself", "What the numbers mean" on "What the summary cards mean".
     A reader who scans the list, picks an entry and arrives at a different
     title cannot tell whether they mis-clicked or whether the page moved
     under them, and either way they lose the thread on the page that exists
     to be checked line by line.

     So every label below is the heading's own words, verbatim, including "and"
     where the heading says "and". Shorten a heading and this list has to be
     re-shortened with it; copy the heading and it cannot drift.

     The ORDER is the document's order too. "How the AI tag works" was listed
     fourth while its section sits after "Reason tags", so reading down the
     list walked you back up the page.
  */ ?>
  <nav class="alt-method-toc" aria-label="On this page">
    <b>On this page:</b>
    <a href="#m-cards">What the summary cards mean</a> ·
    <a href="#m-sources">Where the data comes from</a> ·
    <a href="#m-extract">How we extract and check an entry</a> ·
    <a href="#m-reasons">Reason tags</a> ·
    <a href="#m-ai">How the AI tag works</a> ·
    <a href="#m-roles">How "Roles most impacted" works</a> ·
    <a href="#m-coverage">Coverage and honest limitations</a> ·
    <a href="#m-jurisdictions">What qualifies as a record, by jurisdiction</a> ·
    <a href="#m-notice-gap">WARN notice periods, measured</a> ·
    <a href="#m-differ">Why our totals differ from other headline numbers</a> ·
    <a href="#m-editions">The email editions and their evidence tiers</a> ·
    <a href="#m-audit">The tracker audits itself</a> ·
    <a href="#m-who">Who runs this</a> ·
    <a href="#m-use">Using the data</a>
  </nav>

  <section class="alt-method-sec" id="m-cards">
    <h2>What the summary cards mean</h2>
    <p><b>Verified job cuts</b> is the main figure. It counts cuts with a filing or an independently reported source behind them. <b>Explicitly AI-attributed</b> is a subset of Verified job cuts. It counts only the cuts whose source explicitly names AI as a cause. <b>Announced job cuts</b> is a separate announcement-history figure: source-linked plans reported at the announcement stage. When we can confidently match a later filing or report, we link or merge it. An announcement we have not matched does <b>not</b> mean the cuts went unexecuted. We do not count announced cuts in the Verified or AI-attributed totals, so the cards do not double-count.</p>
    <p><b>Geography in the cards.</b> Country and US-state filters describe the documented location of affected jobs, not an employer's headquarters or every place it operates. A national announcement with no source-supported job-location state stays state-unspecified. We never infer a state for it.</p>
    <p><b>What this is.</b> A continuously updated, source-linked database of publicly reported layoffs worldwide. It records the source, evidence quote, entry status and revision history, so anyone can check every figure independently. It does not claim complete coverage in every country.</p>
  </section>

  <section class="alt-method-sec" id="m-sources">
    <h2>Where the data comes from</h2>
    <p>Every entry always carries a source label:</p>
    <ul class="alt-method-list">
      <li><span class="alt-badge alt-badge-gold">SEC filing</span> Legal 8-K and 6-K filings that we pull from SEC EDGAR full-text search. These are the strongest evidence we hold. They cover US public companies and foreign private issuers that file with the SEC.</li>
      <li><span class="alt-badge alt-badge-warn">WARN notice</span> State government mass-layoff filings from <?php echo esc_html($alt_warn_phrase); ?>.</li>
      <li><span class="alt-badge alt-badge-silver">Press release</span> Investor-relations and newsroom feeds that we have reviewed. This is the "Press release" source in the tracker's filter.</li>
      <li><span class="alt-badge alt-badge-bronze">News</span> Named reports that we find through GDELT and Google News. We keep one only when the record has usable evidence. Eurofound ERM is a separately labeled European announcement source with its own threshold.</li>
    </ul>
    <?php /*
       A CADENCE TYPED HERE GOES STALE WITHOUT ANYONE NOTICING.

       This sentence read "twice daily (morning and after US market close, ET)"
       while the cron had gone ONCE daily on 2026-08-14 and moved to the
       evening on 2026-08-18. The tracker's own status strip was right the
       whole time, because it derives the cadence from the real cron. So does
       this now: data/ingest-schedule.json, generated from railway/railway.toml
       and drift-guarded by tests/test_ingest_schedule.py. Without a schedule
       the clause is OMITTED, not guessed — same contract as every other
       generated figure on this page.

       The WARN and anomaly-review hours are NOT derived (they are GitHub
       workflow crons, which this generator does not read), so they state the
       cadence only. They previously named 11 AM ET and noon ET; the workflows
       actually run at 9 AM ET and 11 AM ET, and both had been wrong long
       enough that nobody could date it. An unguarded hour is a promise this
       page cannot keep.
    */ ?>
    <?php
    $alt_ing     = function_exists('alt_ingest_schedule') ? alt_ingest_schedule() : null;
    $alt_ing_n   = $alt_ing ? count($alt_ing['utc_hours']) : 0;
    $alt_ing_lbl = function_exists('alt_ingest_times_label') ? alt_ingest_times_label() : '';
    $alt_ing_say = '';
    if ($alt_ing_n) {
        $alt_ing_say = 'News and SEC filings: '
            . (function_exists('alt_ingest_cadence_phrase') ? alt_ingest_cadence_phrase() : '')
            . ($alt_ing_lbl ? ', at ' . $alt_ing_lbl : '') . '. ';
    }
    ?>
    <p><b>How often it updates.</b> <?php echo esc_html($alt_ing_say); ?>WARN notices: daily, sweeping every covered state. An automated anomaly review runs daily. It flags statistically unusual entries for a person to inspect: very large single notices, the same company filing in several states, and weak source links. The review catches them before anyone else does. A monthly self-audit re-opens a random sample of published rows and re-checks each one against its own source.</p>
  </section>

  <section class="alt-method-sec" id="m-extract">
    <h2>How we extract and check an entry</h2>
    <p>We search for layoffs in many dialects. The word list covers &ldquo;layoffs&rdquo;, &ldquo;job cuts&rdquo;, &ldquo;redundancies&rdquo;, &ldquo;retrenchment&rdquo;, &ldquo;dismissals&rdquo;, &ldquo;sackings&rdquo; and more than thirty other phrasings. We run it across GDELT's 65-language translated index, so a report that never uses the word "layoff" still surfaces. A model pulls the facts out of news stories and filings, and every core fact must appear in the source text. Counts parse conservatively: a range resolves to the lower bound. Countries and industries normalize through fixed vocabularies, and we throw out any value that is not plausible. Each new record carries an evidence confidence and a publication status. Exact fingerprints, same-company guards and cross-source comparison prevent double counting. A candidate we are unsure about stays provisional, and it never quietly inflates the verified totals. WARN filings skip the language model. They also stay exempt from fuzzy dedup, because one employer can legally file several distinct notices.</p>
  </section>

  <section class="alt-method-sec" id="m-reasons">
    <h2>Reason tags</h2>
    <p>Each entry can carry one or more reason tags. We assign a tag only when the stored source text explicitly supports it. An entry whose source states no reason stays untagged, and we never guess one. Two tags in the fixed vocabulary cover AI. <b>AI or automation</b> means the employer names AI or automation, with a quote on file. <b>AI press-linked</b> means the press ties the cuts to AI without the employer saying it. The rest of the vocabulary is <b>Revenue decline</b>, <b>Restructuring</b>, <b>Merger / acquisition</b>, <b>Offshoring</b>, <b>Product discontinued</b>, <b>Cost reduction</b>, <b>Macroeconomic</b>, <b>Plant / site closure</b>, and <b>Bankruptcy / insolvency</b>. One more tag, <b>Government / public sector</b>, covers public-sector actions such as federal reductions in force. A private contractor losing government work does not qualify. You can filter by tag on the tracker, and the API returns them as <code>reason_tags</code>. We read the two AI tags from the source text. They are a different measure from the AI headline tiles, which count the AI attribution flags <code>ai_explicit</code> and <code>ai_causation</code>. A tag labels one entry&rsquo;s stated reason, while a tile counts the jobs behind an attribution. Both draw the speaker line the same way. <b>AI or automation</b> and the strict tile each need the employer to name AI. <b>AI press-linked</b> and the broad measure each hold the cuts where only the press said it. The tracker labels the two apart, so no one reads one as the other.</p>
  </section>

  <section class="alt-method-sec" id="m-ai">
    <h2>How the AI tag works</h2>
    <p>We sort each mention of AI into five classes: a <em>primary cause</em>, a contributing cause, a selection or operations tool, background context, and an explicit denial. Only a primary or contributing cause can earn the AI tag. Each one must carry an exact supporting quote from the source text. AI investment, projections about future automation, and AI used to select workers do not qualify on their own. <b>The strict AI tag also requires the employer to have attributed the cuts to AI.</b> A news report counts when it quotes or reports the employer naming AI, because the words are still the employer&rsquo;s. A journalist&rsquo;s own characterisation does not count, even when it is unambiguous. <b>Cuts made to hire people with stronger AI skills do not earn the strict tag either.</b> The test is whether the work went away or the required skill changed. If a system now does the work, that is an AI layoff. If the same work still needs doing by different people, that is restructuring. Next to the strict tag we keep a second, separately labeled measure: <b>AI-linked, broad</b>. The two tiers differ on both counts, speaker and strength. The strict tier holds cuts the employer itself blamed on AI, with the exact quote on file. The broad tier holds every other AI link, so a press characterisation the employer never made belongs there. It also counts cuts made while a company funds an AI pivot, and AI-driven market disruption. The API reports the strict tag in <code>ai_explicit</code> and the broad measure in <code>ai_broad_jobs</code>. We never mix the broad measure into the strict verified-AI totals, so the two are never added together. We publish every strict AI attribution with its quote on the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-quotes/')); ?>"><?php echo esc_html(alt_page_link_label('page-ai-quotes.php', 'AI layoffs, in the employer\'s own words')); ?></a> page.</p>
  </section>

  <section class="alt-method-sec" id="m-roles">
    <h2>How "Roles most impacted" works</h2>
    <p>Some sources name which teams lost jobs. A source might say it is "laying off customer-support and recruiting staff." A model reads that stored text and maps it to a fixed set of role categories. A second, independent pass must agree, and a supporting quote must be there, before we store the category. We infer nothing from a company's industry, and we guess nothing. Each bar shows the <b>total job cuts</b> we tie to that team. The orange segment and the 🤖 figure show how many of those were <b>AI-linked</b>. A bar with no orange means job cuts we could not tie to AI, not an error. This chart covers <em>only</em> the minority of records whose source actually named the teams affected. So it is a sample of where cuts land, never a breakdown of the full total.</p>
  </section>

  <section class="alt-method-sec" id="m-coverage">
    <h2>Coverage and honest limitations</h2>
    <p>Our US depth is greatest, because of the WARN and SEC sources. Europe has structured coverage of large announcements through Eurofound ERM. Outside those live collectors, country-level coverage comes from worldwide news discovery and any company newsroom feed we have reviewed by hand. Named filing systems such as SEDAR+, RNS, ASX, TDnet and HKEXnews are research candidates. We do not quietly treat them as live feeds. WARN and ERM each set their own thresholds and geography rules, so no one should sum them as a complete national census. Multi-state and multi-country entries can overlap, and the entry and source fields disclose that risk. An entry dated in the future is announced or filed, but not yet complete. Filtering the table by a country also includes cuts by employers <em>headquartered</em> there whose layoff spanned multiple countries. Each such row keeps its true "Multiple countries" label, and we never recount it as that country alone. The headline totals stay on the stricter job-location basis, so a global figure never inflates them.</p>
    <h3 id="alt-counting-basis">The two counting bases, side by side</h3>
    <p>Both numbers below are correct. They answer different questions. We publish the stricter one and disclose the other, so anyone comparing us with an outside estimate can compare like with like.</p>
    <?php if (function_exists('alt_basis_table_html')) echo alt_basis_table_html('United States'); ?>
    <p><b>What we leave out.</b> Rumored or unsourced layoffs. Layoffs with no stated job count. Forward-looking projections, such as "could cost X jobs by 2050," rather than announced or executed cuts. Look-back summary articles that would double-count entries we already track.</p>
    <h3>We preserve the source links</h3>
    <p>Sources rot: states roll WARN notices into annual archives, and outlets move or delete articles. So we send every cited source URL to the Internet Archive (Wayback Machine) on an automatic schedule. Each entry shows its archived copy next to the original link. An entry whose source has no snapshot yet says so on the page, along with the date of its next automatic check. You can always see what is there and what is still missing.</p>
    <?php if (function_exists('alt_archive_coverage_line_html')) echo alt_archive_coverage_line_html(); ?>
  </section>

  <section class="alt-method-sec" id="m-jurisdictions">
    <h2>What qualifies as a record, by jurisdiction</h2>
    <p>Filing rules differ from place to place. Different laws and different thresholds trigger a US state WARN notice, an SEC filing, a Eurofound ERM announcement and a press report. So what enters this tracker for one place is not the same thing as what enters it for another. The table below states, for each jurisdiction, exactly which register we read and what its own rules admit. We build it from the collectors&rsquo; own configuration, so it cannot drift from what actually runs. When a source does not document a threshold, the table says UNKNOWN instead of filling one in.</p>
    <?php
    // GENERATED partial (railway/generate_jurisdiction_table.py): derived from
    // the collectors' own state lists and documented thresholds, never typed.
    $alt_jt = ALT_PLUGIN_DIR . 'templates/partials/jurisdiction-table.php';
    if (is_readable($alt_jt)) include $alt_jt;
    ?>

    <h3 id="alt-notice-registers">What a notice register does not tell you</h3>
    <p>A notice register records what an employer told the authority it intends to do. It does not record what happened next. Several of our sources are registers of this kind. Each publisher states the limitation itself, and we pass it on rather than smoothing it over.</p>
    <p><b>Quebec.</b> The ministry publishes the collective-dismissal notices it received each month. It says four things about that list. The notices are an intention to dismiss, not a finished layoff. A dismissal may fall outside the month its notice arrived in. A layoff later cancelled stays on the list. And each monthly list is a snapshot, so the ministry does not revise it afterwards. A Quebec total therefore runs high against dismissals actually carried out. We publish these rows as filed notices, and every row says so.</p>
    <p><b>Poland, Mazovia.</b> The regional labour office prints two numbers in the same paragraph. One counts people who lost work that month. The other counts people named in that month&rsquo;s new notifications. We read the second and ignore the first. They measure different things, and adding them would count the same job twice.</p>
    <p><b>US state WARN.</b> The same gap exists here, with one difference that matters. Most states mark a notice rescinded or cancelled, and we drop those rows. Quebec publishes no such marker, so we cannot make the same correction there.</p>
  </section>

  <section class="alt-method-sec" id="m-notice-gap">
    <h2>WARN notice periods, measured</h2>
    <p>The federal WARN Act (29 U.S.C. 2102(a)) requires covered employers to give 60 days&rsquo; written notice before a qualifying mass layoff or plant closing. Many state WARN records carry both the official notice date and the effective date, so we can measure the recorded notice period directly. The figures below are pure date arithmetic on those two recorded fields.</p>
    <?php if (function_exists('alt_notice_gap_table_html')) echo alt_notice_gap_table_html(); ?>
    <p><b>What a short gap does and does not mean.</b> The statute itself allows shorter notice under three exceptions: a faltering company, unforeseeable business circumstances, and a natural disaster (29 U.S.C. 2102(b); 20 C.F.R. 639.9). An employer may also pay wages in place of part of the period. Only a court may decide whether an exception applies (29 U.S.C. 2104). So we report a gap shorter than 60 days as exactly that: a recorded gap shorter than 60 days. It is a timing observation, not a statement that any employer failed to comply with anything. Some states also run their own notice laws with longer periods. The comparison here is against the federal 60-day period only.</p>
  </section>

  <section class="alt-method-sec" id="m-differ">
    <h2>Why our totals differ from other headline numbers</h2>
    <p>Three kinds of trackers measure three different things. Government statistics (BLS) count <em>every</em> separation in the economy, millions per month, with no event-level detail. Announcement surveys count corporate <em>intentions</em>. When a CEO announces "20,000 cuts over the next two years," the full 20,000 lands in their total that day. Much of that may come through attrition, get scaled back, or never produce a single filing. This tracker counts only what has a <em>verifiable document or quoted primary source behind it</em>. That means the WARN notices and SEC filings that appear as those 20,000 cuts actually execute, plus reported cuts with a named-outlet source.</p>
    <p>Treat our verified figure as a documented floor. It is smaller than the estimates, but every single number is clickable back to a legal filing or a named outlet. Since July 2026 we also track <em>announcement-stage</em> cuts as their own labeled tier. We tag them "Announced" in the table and show them as a separate headline number, so one page answers both questions. Unlike the announcement surveys, every announcement here links to its source too.</p>
    <p><b>Where the uncounted cuts go.</b> US reporting law leaves large, legal gaps that no receipts-based tracker can see. Naming them is part of being honest about what our floor is. The federal WARN Act requires a public notice only when a single site loses 50 or more people at an employer of 100 or more. So a company that spreads the same cuts across many smaller offices files nothing. An employer can also skip the public notice entirely by paying wages in place of the 60-day warning, and that layoff never reaches a state database. A global "reducing headcount by 10,000" announcement often resolves to far fewer US filings. Overseas cuts, natural attrition and voluntary buyouts, none of which file WARN, come out of the total first. Small businesses and contractor terminations rarely generate any filing or news at all. The economy-wide total for those uncounted cuts comes from statistical estimates, such as US Bureau of Labor Statistics surveys and weekly unemployment-claims data. Those estimates do not name an employer, and we do not restate them as tracker rows. A number we cannot trace to a source is exactly what this tracker exists not to publish.</p>
    <p>Compare us with the public trackers category by category, and our number is not always the smaller one. We run <em>higher</em> than WARN-only aggregators, because we add SEC filings and named news on top of the same notices. We run <em>at or above</em> tech-event trackers by job volume. On our broad measure we run <em>at or above</em> the announcement AI surveys, with a quote on every entry. We run <em>lower</em> only on all-industry totals. That gap is receiptless cuts: federal-workforce reductions, buyouts, attrition, and small closings that file nothing. We do not claim them, because we cannot source them.</p>
  </section>

  <section class="alt-method-sec" id="m-editions">
    <h2>The email editions and their evidence tiers</h2>
    <p>The tracker sends email editions in three cadences. A <b>daily</b> edition covers the last two days and is provisional. A <b>weekly</b> edition covers the previous complete week (Monday to Sunday). A <b>monthly</b> edition covers the current month so far and is the "jobs out vs jobs in" brief: it sets our verified cuts beside the level of US hiring demand from Indeed Hiring Lab. Every edition names the window it covers, in its dateline and again beside each figure.</p>
    <h3>What triggers a daily send</h3>
    <p>A daily edition goes out when the day has news worth a reader's inbox. Any one of these is enough:</p>
    <ul class="alt-method-list">
      <li>a layoff of <b>250 or more roles</b> entering the tracker,</li>
      <li>a <b>new WARN notice or regulatory filing</b> (an SEC 8-K, or an equivalent primary document), or</li>
      <li>a <b>confirmed leadership change or return-to-office decision</b> at a tracked employer.</li>
    </ul>
    <p>A change in the Indeed job-postings backdrop does <b>not</b> trigger a send. That series is whole-market context, not a layoff or filing of its own, and moving it out of the "jobs in" panel and into a send trigger would confuse the two. The weekly and monthly editions run on their own fixed schedule regardless, because a quiet week or month is itself a reading and suppressing it would turn "nothing happened" into "we did not look."</p>
    <h3>The evidence tiers</h3>
    <p>Every counted cut in an edition carries an evidence tier, strongest first. The tiers describe how well the cut is documented, never how large it is.</p>
    <ul class="alt-method-list">
      <li><b>Employer-confirmed.</b> The employer itself stated the cut, in its own filing, release or on-record statement. This is the only tier the strict AI attribution can draw on, because the strict AI tag requires the employer to have named AI.</li>
      <li><b>Primary-document verified.</b> A legal or regulatory document records the cut: a WARN notice, an SEC 8-K, or an equivalent government or exchange filing. The strongest documentary evidence we hold.</li>
      <li><b>Corroborated.</b> Two or more independent named outlets report the same cut with a job count, without a primary document behind it yet.</li>
      <li><b>Reported.</b> A single named outlet reports the cut. We keep it only when the record carries usable evidence, and it stays the weakest tier until a document or a second source arrives.</li>
    </ul>
    <h3>The source types</h3>
    <p>Each cut also carries the kind of source it came from:</p>
    <ul class="alt-method-list">
      <li><span class="alt-badge alt-badge-warn">WARN notice</span> a US state mass-layoff filing.</li>
      <li><span class="alt-badge alt-badge-gold">SEC 8-K</span> a legal filing pulled from SEC EDGAR.</li>
      <li><span class="alt-badge alt-badge-bronze">News</span> a named report found through worldwide news discovery.</li>
      <li><span class="alt-badge alt-badge-silver">Job board</span> whole-market hiring-demand context from a job board, currently Indeed Hiring Lab (CC&nbsp;BY&nbsp;4.0). This is the "jobs in" backdrop on the monthly edition. It is never counted in any verified or AI total; it describes the labour market, not an employer.</li>
    </ul>
  </section>

  <section class="alt-method-sec" id="m-audit">
    <h2>The tracker audits itself</h2>
    <p>Once a month, an automated audit draws a random sample of rows we have already published. It re-opens each row's own cited source. It then checks that the source still supports that company, that count and that date. We write the result to the public health ledger, flattering or not. A mismatch goes to a person for review through the corrections process. We never silently edit it.</p>
    <?php
    // Masked read, like every other reader of this option (see
    // alt_source_health_masked in db.php). This page only quotes the audit
    // row's detail, but reading the option raw is the habit that let
    // /quality-status publish retired collectors as live.
    $alt_sh = alt_source_health_masked();
    $alt_audit = is_array($alt_sh) && isset($alt_sh['source_audit']) ? $alt_sh['source_audit'] : null;
    if (is_array($alt_audit) && !empty($alt_audit['detail'])) : ?>
    <p class="alt-method-audit"><b>Latest audit result:</b> <?php echo esc_html($alt_audit['detail']); ?><?php if (!empty($alt_audit['checked_at'])) : ?> <span class="alt-muted">(checked <?php echo esc_html(gmdate('M j, Y', strtotime($alt_audit['checked_at']))); ?>)</span><?php endif; ?></p>
    <?php endif; ?>
    <p>You need no permission to check our work. Every row links to its source, and the <a href="<?php echo esc_url(home_url('/ai-layoff-tracker/ai-tracker-health/')); ?>">health page</a> shows each collector's live status.</p>
    <p><b>Audit this tracker.</b> An <a href="https://github.com/dk-forge/ai-layoff-tracker/blob/main/docs/AUDIT.md" target="_blank" rel="noopener">auditor&rsquo;s pack</a> indexes everything an outside reviewer needs. It covers the recall gold set and its protocol, the live data-integrity invariants, the monthly source-audit sampling, and the corrections log. It also lists the exact commands to re-run each measurement offline.</p>
  </section>

  <?php /* DRAFT FOR OWNER REVIEW (2026-08-03): the prose in this "Who runs
       this" section is a draft written from facts already published on this
       site and in the public repo (operator identity, CC BY 4.0 licensing,
       corrections route). The business-practice statements (no paid
       placement, no severance or outplacement services) were supplied in the
       owner's brief for this section; the owner should confirm or reword
       them before treating this section as final. Nothing here states
       anything about funding, because nothing about funding is derivable
       from the repo. */ ?>
  <section class="alt-method-sec" id="m-who">
    <h2>Who runs this</h2>
    <p><a href="https://asktherecruiter.com">AskTheRecruiter.com</a> builds and operates this tracker. The data is free to use with attribution (CC BY 4.0). There is no paid tier for the dataset and no paid placement in it. An employer cannot pay to be added, removed or reworded. The operator does not sell severance or outplacement services to the companies that appear here. Corrections reach us through the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>, and we disclose every accepted fix in the public corrections log. The collection and checking code is public in the <a href="https://github.com/dk-forge/ai-layoff-tracker" target="_blank" rel="noopener">tracker&rsquo;s repository</a>.</p>
  </section>

  <section class="alt-method-sec" id="m-use">
    <h2>Using the data</h2>
    <p><b>How to phrase a citation.</b> Our totals cover what this methodology documents: a verifiable floor, not a census of every layoff that happened. The accurate phrasing is <em>"According to AskTheRecruiter's AI Layoff Tracker, N job cuts are documented for [period]"</em> rather than <em>"there were exactly N layoffs."</em> No tracker of any kind observes every layoff. Ours is the one where you can trace each counted cut back to its document.</p>
    <p>Free with attribution to <b>asktherecruiter.com</b> (CC BY 4.0). The CSV and JSON buttons download exactly what your current filters show, or the full dataset when you set no filter. Each chart offers its own image or data download. For programmatic access, call <code>GET /blog/wp-json/layoffs/v1/query</code>. It is paginated, and its filter params match the page: years, quarters, months, industry, country, state, sources, reasons, q, from, to. Call <code>GET /blog/wp-json/layoffs/v1/aggregate</code> for totals and breakdowns. Corrections get priority via the <a href="<?php echo esc_url(home_url('/contact/')); ?>">contact page</a>, and we disclose every fix in the corrections log on the tracker.</p>
  </section>
</main>
