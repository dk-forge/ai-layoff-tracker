<?php
/**
 * Intro paragraph + H2 + 3-question FAQ on every tracker shortcode page, and
 * the FAQPage JSON-LD built from exactly that visible FAQ (2.20.256, #446
 * items 2 and 3). Owner ruling 2026-10-14: Claude writes the wording, the
 * owner edits it in the PR.
 *
 * Rules the copy follows, pinned by railway/tests/test_page_faq.py:
 *  - every figure and the year come from alt_page_faq_facts() at render time;
 *    a figure that cannot be read is 0 or '' there, and the sentence that
 *    would carry it is dropped, never printed as 0 and never guessed;
 *  - the JSON-LD is printed inside the same block as the visible FAQ, from the
 *    same strings, so it exists only on a page that shows it;
 *  - the tracker page keeps its own FAQ (alt_faq_items) and gets nothing here.
 * The Rank Math fields and the tracker's live meta description are not
 * touched: this file writes page body markup only.
 */
if (!defined('ABSPATH')) exit;

/** Render-time facts. Each value is 0 or '' when it cannot be read. */
function alt_page_faq_facts() {
    $f = array('y' => (int) gmdate('Y'), 'entries' => 0, 'jobs' => 0, 'ai_jobs' => 0,
               'all' => 0, 'countries' => 0, 'start' => '', 'warn_states' => '', 'cadence' => '');
    try {
        if (function_exists('alt_live_numbers')) {
            $n = alt_live_numbers();
            if (is_array($n)) {
                foreach (array('entries', 'jobs', 'ai_jobs', 'all', 'countries') as $k) {
                    $f[$k] = isset($n[$k]) ? max(0, (int) $n[$k]) : 0;
                }
                // 'start' falls back to a typed year inside alt_live_numbers
                // when the table is unreadable; only trust it with real rows.
                if ($f['all'] > 0 && !empty($n['start'])) $f['start'] = (string) $n['start'];
            }
        }
        if (function_exists('alt_coverage_counts') && function_exists('alt_warn_states_phrase')) {
            $c = alt_coverage_counts();
            if (is_array($c) && !empty($c['states'])) $f['warn_states'] = (string) alt_warn_states_phrase();
        }
        if (function_exists('alt_ingest_cadence_phrase')) $f['cadence'] = (string) alt_ingest_cadence_phrase();
    } catch (\Throwable $e) {
        // Keep whatever was read; missing figures drop their sentences.
    }
    return $f;
}

/** Pure: join the non-empty sentences. */
function alt_page_faq_join($parts) {
    return trim(implode(' ', array_filter(array_map('trim', $parts), 'strlen')));
}

/** Pure: the copy for one template, or null when the page gets none. */
function alt_page_faq_content($file, $f, $base) {
    $base = rtrim((string) $base, '/') . '/';
    $nf = function ($v) { return number_format((float) $v); };
    $y = (int) $f['y'];
    $link = function ($path, $label) use ($base) {
        return '<a href="' . esc_url($base . $path) . '">' . esc_html($label) . '</a>';
    };
    $meth = $link('ai-layoff-tracker/methodology/', 'Methodology');
    $srcs = $link('ai-layoff-tracker/sources/', 'Data Sources');
    $has_total = $f['entries'] > 0 && $f['jobs'] > 0;

    // Sentence builders. Each returns '' when its figure is unreadable.
    $total = $has_total
        ? 'So far in ' . $y . ', the tracker holds ' . $nf($f['entries']) . ' verified layoff entries totaling '
          . $nf($f['jobs']) . ' job cuts worldwide, counted by effective date.'
        : '';
    $ai_of_total = ($has_total && $f['ai_jobs'] > 0)
        ? 'In ' . $nf($f['ai_jobs']) . ' of those job cuts, the company or a named report gave AI or automation as a reason.'
        : '';
    $ai_alone = $f['ai_jobs'] > 0
        ? 'So far in ' . $y . ', the sources we cite attribute ' . $nf($f['ai_jobs'])
          . ' verified job cuts to AI or automation, counted by effective date.'
        : '';
    $ai_rule = 'We count a layoff as AI-attributed only when the company, its filing or a named news report gives AI or automation as a reason.';
    $ai_limit = 'That records what the source said. It does not show that AI caused the cut, and we do not estimate cuts nobody attributed.';
    $total_basis = 'Some views on this site count by filing date instead, which gives a different total for the same year.';
    $total_fallback = 'The ' . $link('ai-layoff-tracker/', 'tracker') . ' page shows the current total for ' . $y . ', and the ' . $meth . ' page explains how it is counted.';
    $coverage = ($f['all'] > 0 && $f['countries'] > 0 && $f['start'] !== '')
        ? 'The dataset runs from ' . esc_html($f['start']) . ' to today and covers ' . $nf($f['countries'])
          . ' countries, with ' . $nf($f['all']) . ' entries in all.'
        : '';
    $warn = $f['warn_states'] !== '' ? 'We import WARN notices from ' . esc_html($f['warn_states']) . '.' : '';
    $cadence = $f['cadence'] !== ''
        ? 'We collect news reports and SEC filings ' . esc_html($f['cadence']) . ', and import WARN notices every day.'
        : '';
    $refresh = 'The figures in this section refresh at least once an hour.';
    $where = 'Each entry comes from an SEC filing, a US state WARN notice, the European Restructuring Monitor or a named news report, and links to that source.';
    $read_more = 'Our ' . $meth . ' page explains how we check and count each entry, and the ' . $srcs . ' page lists every source.';
    $license = 'The data is free to use under a CC BY 4.0 license, with credit to asktherecruiter.com.';
    $downloads = 'CSV and JSON downloads and a public API serve the same data.';

    $q_total = array('How many layoffs have there been in ' . $y . '?',
        $has_total ? alt_page_faq_join(array($total, $total_basis)) : $total_fallback);
    $q_ai = array('How many layoffs were blamed on AI in ' . $y . '?',
        alt_page_faq_join(array($ai_alone, $ai_rule, $ai_limit, 'The ' . $meth . ' page sets out the rule.')));
    $q_where = array('Where does this data come from?', alt_page_faq_join(array($where, $read_more)));
    $q_ai_rule = array('What counts as an AI-attributed layoff?', alt_page_faq_join(array(
        $ai_rule, 'A layoff at an AI company, or one that follows an AI product launch, does not count on its own.',
        'We record what the source said and do not judge whether AI really caused the cut.')));

    $pages = array(
        'page-dashboard.php' => array(
            'intro' => array('This dashboard charts the layoffs in the AI Layoff Tracker: jobs cut per month, the reasons companies gave, and the running total of AI-attributed cuts.', $total, $ai_of_total),
            'h2'    => 'Layoff data: common questions',
            'faq'   => array($q_total, $q_ai, $q_where),
        ),
        'page-us-registry.php' => array(
            'intro' => array('This registry lists every US state and territory and shows where each one publishes its official WARN notices.', $warn, 'Each row shows how we read that register and when we last collected it.'),
            'h2'    => 'WARN notices: common questions',
            'faq'   => array(
                array('What is a WARN notice?', alt_page_faq_join(array(
                    'A WARN notice is an advance warning that US employers must file before a mass layoff or plant closing.',
                    'The federal WARN Act usually requires 60 days of notice, and some states set stricter rules.',
                    'Each notice names the employer, the location and the number of workers affected.'))),
                array('Which states does the tracker cover?', alt_page_faq_join(array(
                    $warn, 'Coverage depends on what each state publishes, and the table on this page shows the source and status for each one.',
                    'The ' . $srcs . ' page links to every register.'))),
                array('Do WARN notices say whether AI caused a layoff?', alt_page_faq_join(array(
                    'Rarely. A WARN notice reports the number of workers and the date, not the reason.',
                    'We mark a layoff as AI-attributed only when the company or a named report gave AI as a reason, as the ' . $meth . ' page explains.'))),
            ),
        ),
        'page-methodology.php' => array(
            'intro' => array('This page explains how the AI Layoff Tracker finds, checks and counts layoffs.', $total, 'Each entry links to the source behind it, and the ' . $srcs . ' page lists them all.'),
            'h2'    => 'How we count: common questions',
            'faq'   => array(
                $q_ai_rule,
                array('What is the difference between verified and announced job cuts?', alt_page_faq_join(array(
                    'Verified cuts have a filing or a named report of cuts taking place behind them.',
                    'Announced cuts are company plans reported when they are announced.',
                    'We track those in a separate tier and never add them to the verified totals, because plans can shrink or happen through attrition.'))),
                array('How do you avoid counting a layoff twice?', alt_page_faq_join(array(
                    'We merge reports of the same layoff from different outlets into one entry.',
                    'When a state WARN notice lists a company-wide figure, we count only the jobs in that state.',
                    'Separate WARN notices stay separate, because companies often file several close together.',
                    'The ' . $srcs . ' page lists every source we read.'))),
            ),
        ),
        'page-sources.php' => array(
            'intro' => array('This page lists every source the AI Layoff Tracker reads, with links so you can check the raw records yourself.', $coverage),
            'h2'    => 'Data sources: common questions',
            'faq'   => array(
                array('Where does this data come from?', alt_page_faq_join(array(
                    'Four kinds of sources: SEC filings, US state WARN notices, the European Restructuring Monitor and named news reports.',
                    $warn, 'Each entry links to the source it came from, and the ' . $meth . ' page explains how we check it.'))),
                array('Are news reports primary sources?', alt_page_faq_join(array(
                    'No. An SEC filing and a WARN notice are primary sources, but a news report is not.',
                    'The tracker labels a news-based entry as a source report rather than an official filing.'))),
                array('How often is the data updated?', alt_page_faq_join(array(
                    $cadence, $refresh,
                    'The ' . $link('ai-layoff-tracker/ai-tracker-health/', 'Tracker Health') . ' page shows when each collector last ran.'))),
            ),
        ),
        'page-press.php' => array(
            'intro' => array('This page is for journalists and researchers who want to cite or reuse the AI Layoff Tracker.', $total, $ai_of_total),
            'h2'    => 'For journalists: common questions',
            'faq'   => array(
                $q_ai,
                array('Can I use this data in my reporting?', alt_page_faq_join(array(
                    'Yes. ' . $license, $downloads,
                    'Please cite the date you read the figures, because totals change as new records arrive.'))),
                $q_where,
            ),
        ),
        'page-ai-quotes.php' => array(
            'intro' => array('This page collects the words employers used when they linked a layoff to AI, quoted from the source we cite.', $ai_alone, 'A quote shows what a company said, not proof that AI caused the cut.'),
            'h2'    => 'AI layoff quotes: common questions',
            'faq'   => array(
                array('Which companies have blamed AI for layoffs?', alt_page_faq_join(array(
                    'The list on this page names each one, with the exact quote and a link to its source.', $ai_alone))),
                array('Does a quote prove AI caused the layoff?', alt_page_faq_join(array(
                    'No. It shows that the company, its filing or a named report gave AI as a reason.',
                    'Companies can cite AI for many reasons, and we do not test their motives.'))),
                array('How do you decide a layoff is AI-attributed?', alt_page_faq_join(array(
                    'The source must name AI or automation as a reason for the cut.',
                    'The ' . $meth . ' page sets out the rule, and the ' . $srcs . ' page lists where the quotes come from.'))),
            ),
        ),
        'page-publisher.php' => array(
            'intro' => array('Newsrooms, blogs and researchers can embed live figures and charts from the AI Layoff Tracker on their own sites.', $total, 'Each widget links back to the tracker view behind it.'),
            'h2'    => 'Embedding the tracker: common questions',
            'faq'   => array(
                array('Can I embed the tracker on my site?', alt_page_faq_join(array(
                    'Yes. Build a widget on this page and paste the code into your own page.',
                    'The numbers update on their own, and each widget links to the tracker view behind it.'))),
                array('Is the data free to use?', alt_page_faq_join(array('Yes. ' . $license, $downloads))),
                $q_where,
            ),
        ),
        'page-health.php' => array(
            'intro' => array('This page shows whether each data feed behind the AI Layoff Tracker is running, and when it last ran.', $cadence, 'When a source goes down, we show a gap instead of counting it as zero.'),
            'h2'    => 'Tracker health: common questions',
            'faq'   => array(
                array('How often is the tracker updated?', alt_page_faq_join(array(
                    $cadence, 'This page lists when each collector last ran.', $refresh))),
                array('How do you check your own accuracy?', alt_page_faq_join(array(
                    'Every month an automated audit draws a random sample of published entries.',
                    'It reopens each cited source to confirm the company, the number and the date.',
                    'We correct or remove entries that fail, and this page shows the latest result.'))),
                $q_where,
            ),
        ),
        'page-ai-tracker.php' => array(
            'intro' => array('This view follows layoffs that companies or named reports attributed to AI, automation or robotics.', $ai_alone, 'It counts what sources said, not the full effect of AI on jobs.'),
            'h2'    => 'AI-attributed layoffs: common questions',
            'faq'   => array($q_ai, $q_ai_rule, $q_where),
        ),
    );
    if (!isset($pages[$file])) return null;
    $p = $pages[$file];
    return array('intro' => alt_page_faq_join($p['intro']), 'h2' => $p['h2'], 'faq' => $p['faq']);
}

/** Pure: FAQPage JSON-LD from the same strings the section prints. */
function alt_page_faq_jsonld($faq) {
    $node = array('@context' => 'https://schema.org', '@type' => 'FAQPage', 'mainEntity' => array());
    foreach ($faq as $qa) {
        $node['mainEntity'][] = array('@type' => 'Question', 'name' => $qa[0],
            'acceptedAnswer' => array('@type' => 'Answer', 'text' => $qa[1]));
    }
    return '<script type="application/ld+json">'
         . wp_json_encode($node, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) . '</script>';
}

/** Pure: the intro paragraph and the FAQ section (with its JSON-LD). */
function alt_page_faq_html($c) {
    $intro = '<p class="alt-page-intro">' . $c['intro'] . '</p>';
    $items = '';
    foreach ($c['faq'] as $qa) {
        $items .= '<h3 style="font-size:1.05em;margin:16px 0 4px">' . esc_html($qa[0]) . '</h3><p style="margin:0">' . $qa[1] . '</p>';
    }
    $section = '<section class="alt-page-faq" aria-label="Common questions" style="margin:32px 0 8px">'
             . '<h2>' . esc_html($c['h2']) . '</h2>' . $items . alt_page_faq_jsonld($c['faq']) . '</section>';
    return array($intro, $section);
}

/** Pure: intro after the first </h1> (else first), section inside the last </main> (else last). */
function alt_page_faq_insert($out, $c) {
    if (!$c) return $out;
    list($intro, $section) = alt_page_faq_html($c);
    $at = strpos($out, '</h1>');
    $out = $at === false ? $intro . $out : substr($out, 0, $at + 5) . $intro . substr($out, $at + 5);
    $end = strrpos($out, '</main>');
    return $end === false ? $out . $section : substr($out, 0, $end) . $section . substr($out, $end);
}

/** alt_template() hook. No once-flag: an invisible the_content pass must not claim it. */
function alt_page_faq_template($file, $out) {
    // The tracker page has its own FAQ and FAQPage; never add a second.
    if (!empty($GLOBALS['alt_tracker_rendered'])) return $out;
    $c = alt_page_faq_content($file, alt_page_faq_facts(), home_url('/'));
    return $c ? alt_page_faq_insert($out, $c) : $out;
}
