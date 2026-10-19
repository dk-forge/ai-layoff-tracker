<?php
/**
 * THE TALENT DIGEST COMPOSER, extracted from subscribe.php (2026-10-12) so the
 * talent redesign lands in a file of its own instead of a 9k-line one.
 * subscribe.php require_once's this file at load, so every existing caller
 * and harness that loads subscribe.php still gets alt_digest_compose_talent.
 */

/**
 * Compose the talent-tracker section, again through the REST layer. The
 * talent plugin is a SEPARATE plugin on the same install; if it is inactive
 * its namespace does not resolve and this quietly returns null.
 */
function alt_digest_compose_talent($from, $to, $send_id = 0, $freq = '') {
    if (!function_exists('rest_do_request')) return null;
    /*
      WHICH TIER IS BEING COMPOSED, AND WHY THIS SECTION IS NOW TOLD.

      Until 2026-08-26 this composer took three arguments and every caller that
      passed a fourth (digest-api.php and digest-archive.php already do, for the
      layoff composer's sake) had it silently ignored. It reads $freq now for
      ONE reason: the Indeed "jobs in" backdrop below, which pairs our talent
      signals with the whole-market hiring demand.

      THE BACKDROP HAS ONE HOME PER EDITION, AND $is_monthly IS THE SWITCH.
      The MONTHLY edition already renders the identical Indeed block in the
      layoff section (alt_digest_compose_layoff, gated on $is_monthly there),
      placed after the tracker's own tables - the marquee "jobs out vs jobs in"
      brief. A monthly dual-list subscriber gets BOTH sections concatenated, so
      rendering the backdrop here too would print it twice in one email. So the
      rule is: the talent section carries the backdrop for the DAILY and WEEKLY
      cadences (where the layoff section never has it), and DEFERS to the layoff
      section on the monthly edition. That is "render it once, in one section"
      by construction - the block only ever lives in a single composed section
      for a given tier, so no downstream assembler (the in-WordPress sender, the
      relay, or the public archive) can double it, and none of them needs a
      per-recipient dedup pass. See the backdrop block lower down for the rest.

      The one state this does not cover is a MONTHLY, TALENT-ONLY subscriber,
      who would get neither copy. That state is not reachable through the
      product: the signup form applies ONE frequency across all of a
      subscriber's lists (alt_digest_prefs_from_post) and does not offer monthly
      at all until alt_digest_monthly_enabled() is filtered on, so there is no
      UI path to a talent list set to monthly on its own.
    */
    $is_daily = (strtolower(trim((string) $freq)) === 'daily');
    $more_rows = array();
    $cat_counts = array();
    $cat_items = array();
    $is_monthly = (alt_digest_valid_freq($freq) === 'monthly'
                   && strtolower(trim((string) $freq)) === 'monthly');
    $agg = new WP_REST_Request('GET', '/talent/v1/aggregate');
    $agg->set_param('since', $from);
    $agg->set_param('until', $to);
    $agg->set_param('include', 'fresh');
    $res = rest_do_request($agg);
    if (!$res || $res->is_error()) return null;
    $data = (array) $res->get_data();
    $total = (int) ($data['total'] ?? 0);
    if ($total === 0) return null;

    // Same rule as the layoff section: a block that cannot state its own
    // window does not go out. See alt_digest_date_range for why.
    $range = alt_digest_date_range($from, $to);
    if ($range === '') return null;
    // The prepositional form of the same window. See alt_digest_span_phrase.
    $span = alt_digest_span_phrase($from, $to);
    if ($span === '') return null;

    $url = home_url('/talent-intelligence-tracker/');
    $companies_n = (int) ($data['companies'] ?? 0);
    $verified_n = (int) ($data['verified'] ?? 0);
    $verified = alt_digest_number($verified_n);
    $totalf = alt_digest_number($total);

    /*
      HOW MANY OF THEM ARE ABOUT HIRING AT ALL, MEASURED, AND READ BEFORE THE
      FIRST WORD THAT NAMES THE UNIT.

      THE DEFECT. The edition is headed "N hiring signals" and the count is
      every signal in the window. Measured on the live database over the daily
      window of 2026-08-27/28: 9 of 27 rows carry signal_direction 'hiring',
      17 are 'neutral' and 1 is 'comp_shift'. Over the week 2026-08-17 to
      2026-08-23 it is 215 of 1,075. So the majority of a "hiring signals"
      count is funding rounds, leadership moves and site news.

      THE ANSWER IS A MEASUREMENT, NOT A REDEFINITION. The unit note below
      already says a hiring signal is "one sourced employer update", which is
      a true description of what is counted and also the shape of caveat this
      file is not allowed to lean on: a definition wide enough to make a
      funding round a hiring signal has rescued the label by widening it. So
      the composer asks the endpoint the question instead and prints the
      answer. The reader gets the mix, not a permissive gloss on the word.

      IT IS READ HERE, AT THE TOP, AND NOT WHERE ITS NOTE IS PRINTED. The
      reading used to happen four paragraphs down, after the headline, the
      unit line and the lede had already committed to the word "hiring" - so
      the one measurement that could contradict them arrived too late to be
      consulted, and the delivered edition of 2026-08-28 said "30 hiring
      signals" in its subject with "9 of the 30" in its body. The NOTE still
      prints in its old position, byte for byte; only the question is asked
      earlier. See alt_digest_talent_signal_noun for what now reads it.

      GUARDS, SAME SHAPE AS "OTHER TALENT ACTIVITY" BELOW and for the reasons
      spelled out there: array_key_exists rather than isset so a null is not
      read as a zero, a failed call yields NO figure because an endpoint that
      cannot answer is UNKNOWN, and a total equal to the headline is the
      signature of a filter the endpoint ignored and is discarded. What that
      last guard gives up is a window in which every single signal states a
      hiring direction; the observed shares are 33% and 20%, so it is not a
      window this data produces, and a suppressed true line costs a line while
      a headline-in-disguise costs a number. $hiring_n stays NULL through
      both, and null is UNKNOWN rather than zero.
    */
    $hiring_n = null;
    $dreq = new WP_REST_Request('GET', '/talent/v1/aggregate');
    $dreq->set_param('since', $from);
    $dreq->set_param('until', $to);
    $dreq->set_param('include', 'fresh');
    $dreq->set_param('direction', 'hiring');
    $dres = rest_do_request($dreq);
    if ($dres && !$dres->is_error()) {
        $ddata = (array) $dres->get_data();
        if (array_key_exists('total', $ddata)
            && (int) $ddata['total'] !== $total) {
            $hiring_n = (int) $ddata['total'];
        }
    }
    /*
      THE NOUN THIS EDITION'S FIGURE MAY WEAR, decided once from that reading
      and read by the headline unit line, the lede, the ranked list's heading
      and the subject fragment. Four surfaces, one derivation, so they cannot
      disagree with each other or with the mix note.
    */
    $signal_noun = alt_digest_talent_signal_noun($total, $hiring_n);
    /*
      WHERE, AND WHY THIS ONE SAYS LESS THAN THE LAYOFF SECTION'S.

      Same defect, same fix: this composer sends no country parameter, so the
      count is worldwide, and until 2026-08-17 the headline never said so.

      It stops at "worldwide" and does not add the layoff section's measured
      "including entries with no country recorded", because here that clause
      would be unmeasured. The talent aggregate returns `by_country` capped at
      40 values against 84 live countries, so a shortfall against the total
      cannot tell an unplaced signal from one below the cut-off. An unmeasured
      caveat is the same fault as a fixed one. If that endpoint ever ships a
      placed/unplaced split, use alt_digest_geo_scope() here too.
    */
    $scope = $range . ', worldwide, ' . alt_digest_talent_basis() . '.';
    /*
      THE UNIT SITS UNDER THE FIGURE, NOT ABOVE IT, and this is not cosmetic.

      This printed an eyebrow reading "New hiring signals", then the number.
      In the same message the layoff section prints a number and then "verified
      job cuts", so the two headline figures were built in opposite orders, and
      a reader comparing them had to notice that "1,376" and "16,842" count
      completely different things from labels sitting on opposite sides.

      A HIRING SIGNAL IS NOT A JOB AND IS NOT A CUT. It is a published
      indication that a company is hiring, mostly unverified, and one signal
      may name hundreds of jobs or none. The layoff tracker's unit has a filing
      or a named report behind every row. Setting the two side by side without
      binding each number to its own unit is the single most misleading thing
      this email can do, and it is why the subject line carries the units too.
    */
    $html = '<h2>Talent Intelligence Tracker</h2>'
          . '<p data-alt="stat">' . esc_html($totalf) . '</p>'
          . '<p data-alt="unit">'
          . esc_html(alt_digest_verb($total, $signal_noun, $signal_noun . 's'))
          . '</p>'
          . '<p data-alt="scope">' . esc_html($scope) . '</p>';
    /*
      WHAT THE UNIT IS, IN THE READER'S WORDS, BESIDE THE FIGURE IT COUNTS.

      THE DEFECT THE OWNER READ. "1,379 hiring signals" sat above a ranked list
      whose top row named 2,200 jobs. Nothing in the message said those two
      numbers count different things, so the only available reading is that the
      week held 1,379 jobs and one employer supplied 2,200 of them. The rule
      was already written down in the comment above this one, and a rule that
      lives only in a comment is a rule the reader never gets.

      IT IS NOT THE VERIFIED SPLIT AND DOES NOT REPLACE IT. The sentence below
      says how many signals carry a primary document, which is a different
      question: this one says what ONE of them is. Both are short and both
      travel with the figure, because a reader who quotes the headline takes
      whatever is next to it and nothing else.
    */
    /*
      WHAT A COUNT MEANS, NOT JUST WHAT A SIGNAL IS. The sibling talent plugin
      classifies every row by what its headcount MEANS (pipeline/count_meaning),
      and a just-merged fix reworded job-board scan deltas from "opened N roles"
      to "listed N more active postings than our previous scan": a board's
      active-posting count rising is an OBSERVATION, not a confirmed opening -
      old listings expire while new ones appear. That distinction has to reach
      this email, because the headline count here (an /aggregate COUNT over the
      window) includes those job-board scans alongside confirmed announcements.

      IT IS ONE SENTENCE, NOT A BREAKDOWN, AND DELIBERATELY SO. /talent/v1/
      aggregate does not expose a split by signal type or count-meaning: the
      include=fresh mode this section reads returns only scalars (total,
      companies, verified, money), and even the full response groups only by
      pillar, direction and confidence, none of which is the confirmed-vs-scan
      distinction. Deriving a split from the 40 sampled /query rows would be a
      partial count published as a whole one, which is the exact fabrication the
      iron rules forbid. So the honest move is to state plainly what the count
      can and cannot mean, consistent with the merged "opened roles" wording,
      and to leave the split unstated because it is unmeasured here.
    */
    /*
      THE NOTE DEFINES THE WORD THE HEADLINE JUST USED, so it reads the same
      derivation. It said "A hiring signal is ..." under a figure now labelled
      "talent and employer-activity signals", which defines a term the reader
      was never shown. On an all-hiring window this is byte-identical to the
      approved sentence, which is the property to preserve.
    */
    $unit_note = 'A ' . $signal_noun . ' is one sourced employer update, not one job. '
               . 'Job counts below are the roles named in that update. Some '
               . 'signals are job-board scans, where a rise means the employer '
               . 'listed more active postings than our previous scan, not that '
               . 'it confirmed new openings.';
    // SIGNALS FIRST, CAVEATS LAST (owner, 2026-10-01: "this email is not
    // helpful"). The four notes below are true and stay byte for byte, but
    // they used to sit between the headline and the ranked signals, so a
    // reader met four paragraphs of method before a single company. They are
    // held here and printed under "How to read these numbers" after the
    // activity counts. test_digest_talent_signals_first.py holds the order.
    $notes_html = '<p data-alt="note">' . esc_html($unit_note) . '</p>';
    /*
      NOT "NEW". A daily edition covers yesterday and today (alt_digest_window,
      deliberate), so every signal dated yesterday was also in yesterday's
      edition, and "108 new signals" was a claim the window could not support
      for roughly half of them. The subject line never said "new"; the unit
      line and this lede did. The figure is unchanged: it is the count of
      signals dated in the window, which is what it always was.
    */
    $lede = alt_digest_count($total, $signal_noun) . ', ' . $scope;
    // The same rule as the layoff section, same reason. This lede happens to
    // fit today; composing the snippet anyway means it keeps fitting when
    // somebody adds a clause to the body, which is exactly how the other one
    // broke. See alt_digest_fit_preheader.
    /*
      THE PREVIEW ADDS, IT NEVER REPEATS. This read "1,376 new hiring signals,
      August 10-16" beside a subject reading "1,376 hiring signals · Aug 10-16",
      which is the same sentence twice, and the owner saw it in his own inbox.

      THE VERIFIED SPLIT IS THE SECOND-MOST-USEFUL FACT ABOUT THIS TRACKER and
      it is the one a sceptical reader wants first. A hiring signal is a
      published indication, mostly unverified; how many carry a primary
      document behind them is exactly what the headline figure does not say.
      The company count follows, because a thousand signals from thirty
      companies is a different week from a thousand from six hundred.
    */
    $preheader = alt_digest_fit_preheader(
        $verified . ' of ' . $totalf . ' verified against a primary document',
        array('from ' . alt_digest_count($companies_n, 'company', 'companies')));
    $text = "Talent Intelligence Tracker\n{$lede}\n";
    $notes_text = $unit_note . "\n";
    $detail = 'From ' . alt_digest_count($companies_n, 'company', 'companies') . ', '
            . $range . '. ' . $verified . ' of the ' . $totalf . ' '
            /*
              THE VERB AGREES WITH THE COUNT IN FRONT OF IT, which is the
              verified figure and not the total. This read the total, so a live
              send published "1 of the 186 are verified against primary
              documents". The verified count is one on most days, so this was
              the sentence a sceptical reader met most often.
            */
            . alt_digest_verb($verified_n, 'is', 'are')
            /*
              WHAT THE REST ARE, WITHOUT PUTTING THEM ALL IN ONE BIN.

              THE DEFECT. This closed "The rest are published indications we
              have not confirmed", and on the daily edition of 2026-08-28 the
              figure in front of it was ZERO - so the sentence said that
              nothing in the email was evidence of anything. Ten of that day's
              rows were readings of the employers' OWN careers boards. A
              Greenhouse or Ashby board is the employer publishing, first hand;
              calling it an unconfirmed indication is not a caution, it is a
              wrong statement about where the fact came from.

              TWO AXES, NOT ONE, and conflating them is the whole fault. WHO
              PUBLISHED IT (the employer itself, or somebody reporting on it)
              and WHAT IT ESTABLISHES (a filed figure, or a measurement we
              took) are independent. A first-party board reading is
              first-party AND unfiled, both true at once, and a sentence with
              one bin cannot hold that.

              THE FIGURE IS NOT WIDENED TO RESCUE THE WORD. "Verified" still
              means a filed primary document and the count in front of it is
              unchanged - promoting a board reading into it would overstate our
              own measurement as a figure the employer filed. What changes is
              the description of the remainder, which was simply untrue.

              NO COUNT IS ADDED HERE, deliberately. /talent/v1/aggregate
              exposes no collector split and no collector filter, so the only
              way to count the board rows would be to tally the 40 sampled
              /query rows and print the result as if it covered the window.
              That is a partial count published as a whole one. The classes
              are named; the split stays unstated because it is unmeasured.
            */
            . ' verified against a primary document, which here means a filed '
            . 'one. The rest are of two kinds: news reports we have not '
            . 'independently confirmed, and readings of employers\' own job '
            . 'boards. A board reading is first-party, but it is our '
            . 'measurement rather than a figure the employer filed.';
    $notes_html .= '<p data-alt="note">' . esc_html($detail) . '</p>';
    $notes_text .= $detail . "\n";

    /*
      PROVISIONAL, AND THE LAYOFF SECTION HAS SAID SO FOR WEEKS. Measured on
      2026-09-04 by re-reading the previous edition's window (2026-09-02 to
      2026-09-03) one day after it was sent: the edition said 111 signals from
      110 companies; the same window read 207 from 205, because the collectors
      keep capturing signals for days after the date they carry. Every figure
      in the edition was right when it was read (the 111 reproduces exactly
      from the rows' own captured_at stamps), and a reader who opened the link
      a day later met a number nearly twice as large with nothing in the email
      saying that would happen. The overlap sentence is EARNED BY THE WINDOW,
      not granted by the tier: it prints only for the two-day daily pair, the
      way a week label is earned only by a Monday-to-Sunday span (2.20.144).
    */
    $ft_p = strtotime($from . ' 00:00:00 UTC');
    $tt_p = strtotime($to . ' 00:00:00 UTC');
    $provisional = 'Figures for this window are provisional: signals keep '
                 . 'arriving for days after the date they carry, so the '
                 . 'tracker will show more for the same dates later.';
    if ($ft_p !== false && $tt_p !== false && ($tt_p - $ft_p) === DAY_IN_SECONDS) {
        $provisional .= ' A daily edition covers yesterday and today, so a '
                      . 'signal dated yesterday was also in yesterday\'s edition.';
    }
    $notes_html .= '<p data-alt="note">' . esc_html($provisional) . '</p>';
    $notes_text .= $provisional . "\n";

    /*
      THE MEASURED HIRING SHARE, PRINTED WHERE IT ALWAYS WAS. The reading
      itself moved to the top of the composer (see the block that sets
      $hiring_n) so that the words naming the unit could consult it; this is
      unchanged in position, wording and guards. A NULL reading prints nothing,
      because an endpoint that could not answer is UNKNOWN and a suppressed
      equal-to-the-headline answer is a filter that was ignored.

      IT IS STILL WORTH PRINTING NOW THE LABEL IS DERIVED. The noun says the
      window holds more than hiring; this says how much more, measured.
    */
    if ($hiring_n !== null) {
        // THE LINE CARRIES ITS OWN WINDOW, like every other figure line
        // here: lifted out on its own it is still true and still says
        // what it covers. See tests/test_digest_scope_rules.py.
        $mix = alt_digest_number($hiring_n) . ' of the ' . $totalf
             . ' signals listed ' . $span . ' '
             . alt_digest_verb($hiring_n, 'states', 'state')
             . ' a direction of hiring. The rest are other employer '
             . 'activity in the same window: funding, leadership, pay and '
             . 'site news. That activity names no roles, and this tracker '
             . 'follows it because it tends to come before hiring.';
        $notes_html .= '<p data-alt="note">' . esc_html($mix) . '</p>';
        $notes_text .= $mix . "\n";
    }

    /*
      ASK FOR MORE THAN FIVE, BECAUSE THE FIVE THAT ARRIVE ARE THE WRONG FIVE.

      THE DEFECT. This asked for 5 rows and printed them. A live send led with
      an untranslated Spanish headline and two funding rounds while a signal
      naming 2,200 jobs created sat below the fold of the list. The obvious
      diagnosis, "it is sorted by recency", is wrong and the real one matters:
      /talent/v1/query already DEFAULTS to sort=notable, so this was already
      getting materiality first. The problem is that materiality is saturated.
      Measured live over the week to 2026-08-16: 1,349 signals, of which 264
      are graded high, 1,082 medium and 3 routine. A grade that 99.8% of rows
      pass is not a ranking, so the tiebreak, recency, decided the list. And
      recency is close to random in a weekly digest, because every row in it
      is from the same week by construction.

      WHY NOT sort=largest, WHICH THE ENDPOINT DOES HONOUR. Only 64 of those
      1,349 rows carry a headcount at all, and MySQL sorts NULLs last on DESC,
      so that parameter returns five headcount stories and nothing else can
      ever compete for a slot. It replaces one bad ranking with a narrower one.

      SO THE RANKING IS DONE HERE, over a wider fetch, on a field already on
      every row. See alt_digest_talent_rank.
    */
    $q = new WP_REST_Request('GET', '/talent/v1/query');
    $q->set_param('since', $from);
    $q->set_param('until', $to);
    $q->set_param('per_page', 40);
    $qres = rest_do_request($q);
    if ($qres && !$qres->is_error()) {
        $qdata = (array) $qres->get_data();
        /*
          TOP FIVE, THEN "MORE" (owner-approved 2026-10-12). Ranked by roles
          named as before; ties now go to US/UK/EU and English-speaking
          markets (alt_digest_audience_order), and the next ten sit under a
          compact "More" list instead of being dropped.
        */
        $rows = alt_digest_talent_rank(
            is_array($qdata['rows'] ?? null) ? $qdata['rows'] : array(), 15);
        if (function_exists('alt_digest_audience_order')) {
            $rows = alt_digest_audience_order($rows, 'alt_digest_talent_roles_named');
        }
        $more_rows = array_slice($rows, 5);
        $rows = array_slice($rows, 0, 5);
        if ($rows) {
            /*
              THE CAPTION CARRIES THE LANGUAGE ANSWER, ONCE, FOR THE WHOLE
              LIST. Two of the five rows in the live send of 2026-08-18 were
              Portuguese and Spanish, and in an English digest they read as
              unfinished work rather than as worldwide coverage.

              MEASURED before choosing, over 2026-08-11 to 2026-08-18: 1,411
              signals, of which 64 (4.5%) are already excluded on script. Of
              the 77 that name a headcount, and so of the only rows this list
              can ever show, 17 are Latin-script and not English. Those 17 are
              22% of the rows and 74% of the jobs named. Two of the top five by
              size and four of the top ten. Dropping non-English rows would
              delete three quarters of the biggest signals of the week to tidy
              a fifth of the list, so it is not done.

              THE ROW IS NOT LABELLED WITH A LANGUAGE EITHER, because we do not
              store one and would have to infer it from the headline. That is
              the same class of guess the script filter had to be corrected for
              once, and a short headline is the worst case for it: a stopword
              classifier run over this week could not decide 68 of 1,347
              Latin-script headlines, German and Portuguese among them. Naming
              a language we guessed is a claim the reader cannot check, in a
              product whose whole pitch is that every claim can be checked.

              SO THE ROW CARRIES ITS SOURCE, WHICH IS STORED AND NOT INFERRED,
              and the caption says plainly that the headline is a quotation.
              A reader who meets a Portuguese line then knows why it is there
              and who published it, and a reporter gets the outlet they need to
              go and check it. `source_name` is present on 100% of the week's
              rows; a row missing it prints nothing rather than a placeholder.
            */
            /*
              "THE TRACKER'S OWN ORDER" MEANT NOTHING TO A READER. It is the
              order the endpoint returned, which is newest first, and saying so
              costs three words and stops the caption gesturing at an internal
              detail nobody outside this repo can check.
            */
            /*
              THE CAPTION IS DERIVED FROM THE ROWS IT SITS OVER, and until now
              it made two claims that were false for a whole class of them.

              THE PROVENANCE CLAIM IS THE SERIOUS ONE. "Each headline is quoted
              as its source published it, in that source's own language" was
              printed unconditionally. A job-board row's headline is not a
              quotation of anything: nobody published it. The talent tracker's
              own collector COMPOSES that sentence out of two readings of the
              board ("...listed 23 more active postings in London than our
              previous scan"). On the delivered edition of 2026-08-28 every
              single row in this list was a board reading, so the email made a
              false statement about the provenance of 100% of what it showed -
              in a paragraph whose job is to tell a journalist how to cite it.

              AND THE ORDERING CLAIM NAMED THE WRONG UNIT. "the signals naming
              the most jobs first" over a list of postings deltas is the same
              relabelling the row parentheses were doing.

              FIXED PROSE AROUND VARIABLE DATA IS WHAT BROKE IT, so the fix is
              not a wider sentence that covers both cases at once. The rows are
              in hand, they are counted, and the caption says what is actually
              in the list - the same rule the undated-rows note below follows.
              A list of reported rows keeps the old sentence byte for byte,
              because for those rows it was always true.
            */
            $scan_n = 0;
            foreach ($rows as $ranked) {
                if (alt_digest_talent_is_scan($ranked)) $scan_n++;
            }
            $reported_n = count($rows) - $scan_n;
            if ($scan_n === 0) {
                $order = 'the signals naming the most jobs first, then newest '
                       . 'first.';
                $prov = 'Each headline is quoted as its source published it, '
                      . 'in that source\'s own language.';
            } elseif ($reported_n === 0) {
                $order = 'the signals listing the most postings first, then '
                       . 'newest first.';
                $prov = 'Each line is our own description of what the '
                      . 'employer\'s job board listed on two dates, not a '
                      . 'headline anyone published.';
            } else {
                $order = 'the signals naming the most jobs or postings first, '
                       . 'then newest first.';
                $prov = 'A news headline is quoted as its source published it, '
                      . 'in that source\'s own language. A job-board line is '
                      . 'our own description of what the employer\'s board '
                      . 'listed on two dates, not a headline anyone published.';
            }
            /*
              AND THE HEADING OVER THEM, DERIVED FROM THE SAME TWO COUNTS.

              "Biggest hiring signals" sat over a list that was, on the
              delivered edition of 2026-08-28, five readings of employers' own
              job boards ranked by how much their posting counts had risen.
              None of those five is a hiring signal in the sense the heading
              promises, and the caption directly beneath already said so - it
              is the same fixed-prose-over-variable-data fault the caption was
              fixed for, one line higher up.

              THE THREE BRANCHES ARE THE CAPTION'S, deliberately, because they
              answer the same question about the same rows. An ALL-REPORTED
              list keeps the approved heading byte for byte: it was always true
              there, and rewriting it everywhere would trade one wrong fixed
              phrase for another - the same over-correction guard
              tests/test_digest_talent_observation.py holds for the caption.
            */
            if ($reported_n === 0) {
                $heading = 'Largest observed job-board increases';
            } elseif ($scan_n === 0) {
                $heading = $is_daily ? 'Top hiring today' : 'Biggest hiring signals';
            } else {
                $heading = 'Biggest signals and job-board increases';
            }
            $caption = $range . ', ' . $order . ' ' . $prov;
            $html .= '<h3>' . esc_html($heading) . '</h3>'
                   . '<p data-alt="caption">' . esc_html($caption) . '</p>'
                   . '<ul>';
            $text .= "\n" . $heading . "\n" . $caption . "\n";
            $undated = 0;
            $resume_candidates = array();
            foreach ($rows as $row) {
                $row = (array) $row;
                /*
                  THE LABEL ONLY WHEN THE HEADLINE DOES NOT ALREADY CARRY IT.
                  See alt_digest_headline_names_company for the measurement and
                  for why this is not a prefix strip and not an unconditional
                  drop. With no headline the label IS the row, and with no
                  company the headline is.
                */
                $co = trim((string) ($row['company'] ?? ''));
                $head = trim((string) ($row['headline'] ?? ''));
                if ($head === '') {
                    $line = $co;
                } elseif ($co === '' || alt_digest_headline_names_company($co, $head)) {
                    $line = $head;
                } else {
                    $line = $co . ': ' . $head;
                }
                $line = alt_digest_plain_dashes($line);
                if ($line === '') continue;
                // The signal's own publication date, which is also what the
                // since/until window selects on. Some signals reach us with
                // no date on the source; those show none rather than borrow
                // the day we captured them.
                $pub = substr((string) ($row['published_date'] ?? ''), 0, 10);
                $when = alt_digest_date_range($pub, $pub);
                /*
                  THE NUMBER THAT DID THE RANKING IS SHOWN, because a list
                  claiming to lead with the biggest signals and printing no
                  size is asking to be taken on trust. A row naming no jobs
                  shows none: this is the stored headcount, never a guess, and
                  a zero here means "the source stated no number", not "zero
                  jobs", so it is omitted rather than printed as a measurement.
                */
                $facts = array();
                list($lang_tag, $gist) = alt_digest_talent_language_bits($row);
                if ($lang_tag !== '') $facts[] = $lang_tag;
                $jobs = alt_digest_talent_roles_named($row);
                /*
                  AND THE UNIT THAT NUMBER IS IN. A board reading's headcount
                  is a net rise in postings the employer's board DISPLAYED
                  between two of our scans, which is not 23 jobs and is not a
                  hire. See alt_digest_postings_phrase for the delivered line
                  that contradicted itself inside four words.
                */
                $is_scan = alt_digest_talent_is_scan($row);
                // Redesign stage 2: the resume line reads the same figure.
                $resume_candidates[] = array('company' => $co, 'jobs' => (int) $jobs,
                                             'scan' => $is_scan);
                if ($jobs > 0) {
                    $facts[] = $is_scan ? alt_digest_postings_phrase($jobs)
                                        : alt_digest_jobs_phrase($jobs);
                }
                /*
                  WHERE, WHICH THIS LIST DID NOT SAY UNTIL 2026-08-20.

                  The biggest-cuts table two blocks up prints "(Massachusetts,
                  United States, takes effect 18 August 2026)" on every row.
                  This one printed jobs, outlet and date, so the email answered
                  "where" for every cut and for no hire, and a reader meeting a
                  10,000-role spree could not tell whether it was in the United
                  Kingdom or in India.

                  A ROW WITH NO PLACE SAYS SO, in the same words the cuts use.
                  43% of live rows carry no country, and they carry no city and
                  no region either, so there is nothing to fall back to and
                  nothing to infer from. Guessing from the outlet's own country
                  is the one tempting move and it is wrong: The Sun is a
                  British paper that reports hiring in other countries.
                */
                $place = alt_digest_talent_place($row);
                $facts[] = ($place !== '') ? $place : 'location not recorded';
                // WHO PUBLISHED IT. The row's own stored outlet, never
                // derived from the URL and never guessed: a row that carries
                // no source name prints no source, in the same way a row that
                // carries no date prints no date.
                $outlet = alt_digest_plain_dashes(trim((string) ($row['source_name'] ?? '')));
                if ($outlet !== '') $facts[] = $outlet;
                /*
                  A DATE MEANS TWO DIFFERENT THINGS ON THE TWO KINDS OF ROW,
                  and printing them identically made one of them a claim we
                  cannot support. A news row's date is when the outlet
                  PUBLISHED. A job-board row was never published, and the
                  collector stamps the day it READ the board - so a bare date
                  there says an outlet published something on a day nobody
                  published anything. Naming the act costs three characters.
                */
                if ($when !== '') {
                    $facts[] = $is_scan ? ('board read ' . $when) : $when;
                } else { $undated++; }
                /*
                  THE HEADLINE IS A LINK, and until 2026-08-20 it was the only
                  list in this email that was not.

                  Every layoff block links each row to the thing that lets a
                  reader check it. These rows shipped as plain text, so the one
                  block whose whole content is somebody else's reporting was
                  the one block a reader could not follow.

                  IT LINKS TO THE SOURCE, not to us, and that follows the rule
                  alt_digest_rank_table states: link text should say where the
                  link goes. The visible text here IS the outlet's headline,
                  quoted as they published it, so the article is the only
                  destination that text honestly promises. `source_url` is
                  present on 100% of live rows.

                  NOT COUNTED, AND NOT PRETENDED TO BE. alt_digest_track_link
                  wraps first-party destinations only, by design, because a
                  counter that forwards anywhere is an open redirect on our own
                  domain. An external link is handed over plain rather than
                  routed through a guard it cannot pass.

                  WHERE A ROW SOMEHOW CARRIES NO USABLE SOURCE, the fallback is
                  the talent tracker filtered to that company and window, which
                  is the same fallback the biggest-cuts table uses when a row
                  has no entry page. That one IS first-party, so it is counted.
                */
                $src = trim((string) ($row['source_url'] ?? ''));
                $href = '';
                $plain = '';
                if (alt_digest_external_link_ok($src)) {
                    $href = $src;
                    $plain = $src;
                } elseif ($co !== '') {
                    $plain = alt_digest_talent_url($from, $to,
                        array('company' => $co));
                    $href = alt_digest_track_link($send_id, $plain);
                }
                $shown = esc_html($line);
                if ($href !== '') {
                    $shown = '<a href="' . esc_url($href) . '">' . $shown . '</a>';
                }
                if ($facts) {
                    // Outside the anchor, exactly as alt_digest_rank_table
                    // keeps its qualifiers outside: a screen reader should not
                    // announce the parenthesis as the name of the destination.
                    $shown .= ' ' . esc_html('(' . implode(', ', $facts) . ')');
                    $line .= ' (' . implode(', ', $facts) . ')';
                }
                if ($gist !== '') $shown .= '<br><span data-alt="gist">' . esc_html($gist) . '</span>';
                $html .= '<li>' . $shown . '</li>';
                $text .= '  - ' . $line . "\n";
                if ($gist !== '') $text .= '    ' . $gist . "\n";
                // The plain destination, never the counted one: a text reader
                // should not be handed a machine-shaped URL to squint at.
                if ($plain !== '') $text .= '    ' . $plain . "\n";
            }
            $html .= '</ul>';
            if ($more_rows) {
                list($m_html, $m_text) = alt_digest_talent_compact_list($more_rows, $from, $to, $send_id);
                $html .= '<h3>More</h3>' . $m_html;
                $text .= "\nMore\n" . $m_text;
            }
            /*
              THE RESUME LINE (redesign stage 2): when one employer in this list
              names 500 or more jobs in a reported signal, a reader may want to
              apply. Job-board scans never trigger it (postings, not hires).
            */
            if (function_exists('alt_digest_talent_resume_line')
                    && function_exists('alt_resume_cta_url')) {
                list($rl_html, $rl_text) = alt_digest_talent_resume_line(
                    $resume_candidates, alt_resume_cta_url('digest-talent'));
                $html .= $rl_html;
                $text .= $rl_text;
            }
            /*
              THE CAVEAT ONLY WHEN IT IS TRUE, AND COUNTED WHEN IT IS.

              This used to print "A signal whose source carries no date shows
              none" whenever ANY row was dated, which is almost always, and
              so it appeared on sends where every row carried a date. That is
              the same fault the layoff country block had: fixed prose around
              variable data, correct on average and wrong in the particular
              case a reader happens to check.
            */
            if ($undated > 0) {
                // Agreement, because "1 of the signals show no date" is the
                // same carelessness as "1 jobs" and lands on the same reader.
                $basis = ($undated === 1)
                    ? ('One signal listed ' . $span . ' shows no date, because the '
                       . 'source carries none; the window placed it by the day we '
                       . 'captured it.')
                    : ($undated . ' signals listed ' . $span . ' show no date, because '
                       . 'the source carries none; the window placed them by the day '
                       . 'we captured them.');
                $html .= '<p data-alt="note">' . esc_html($basis) . '</p>';
                $text .= $basis . "\n";
            }
        }
    }

    /*
      OTHER TALENT ACTIVITY, BECAUSE THE FORM PROMISES IT AND THE EMAIL DID NOT.

      The signup checkbox reads "hiring, leadership and compensation signals".
      The digest delivered hiring and nothing else, so two thirds of what a
      subscriber consented to was invisible in every edition they received.

      EACH COUNT IS ITS OWN QUERY, ON THIS WINDOW, AGAINST THE TALENT PLUGIN'S
      OWN VOCABULARY. Leadership and pay are pillars, a closed four-value list
      the pipeline always sets. A funding round is NOT a pillar: it is a
      predicate over the amount and stage fields, which is why it is asked for
      as `funding=1` and not as a category name. These are the same three
      specifications that page's own "I'm looking for" control offers, so a
      count here and the view the reader lands on are the same question.

      THEY OVERLAP BY DESIGN AND THE LINE SAYS SO. A funded employer can also
      be hiring, and a pay change can sit on a row that is also a leadership
      move. Summing them, or subtracting them from the headline, would be
      arithmetic on sets that are not disjoint. The caption states it rather
      than leaving a reader to add three numbers and find they do not fit.

      THE COUNT ONLY, NEVER THE DOLLARS. The talent tracker's funding AMOUNTS
      are known to be materially wrong: fund raises and IPOs are counted as
      company rounds and one stored figure is off by more than an order of
      magnitude. That is the sibling repo's defect to fix. Publishing a count
      of rounds does not depend on it; publishing a total raised would.

      A FAILED CALL PRINTS NO LINE, and this is the difference that matters. An
      endpoint that cannot answer is UNKNOWN, and a category rendered as "0"
      because a request failed is a measurement we did not make, published as
      one we did. A real zero from a working call is a real zero and prints.
    */
    $activity = array();
    foreach (array(
        array('Leadership moves', 'pillar', 'leadership_change'),
        array('Funding rounds', 'funding', '1'),
        array('Pay and benefits changes', 'pillar', 'rewards_comp'),
    ) as $cat) {
        list($cat_label, $cat_key, $cat_value) = $cat;
        $creq = new WP_REST_Request('GET', '/talent/v1/aggregate');
        $creq->set_param('since', $from);
        $creq->set_param('until', $to);
        $creq->set_param('include', 'fresh');
        $creq->set_param($cat_key, $cat_value);
        $cres = rest_do_request($creq);
        if (!$cres || $cres->is_error()) continue;
        $cdata = (array) $cres->get_data();
        // array_key_exists, not isset: a null total is an answer we cannot
        // read, and isset() would quietly turn it into a zero.
        if (!array_key_exists('total', $cdata)) continue;
        /*
          A FILTER THE ENDPOINT IGNORED RETURNS THE HEADLINE, AND THAT IS THE
          FAILURE THIS LINE EXISTS FOR.

          MEASURED AGAINST THE LIVE ROUTE ON 2026-08-19, not reasoned about.
          /talent/v1/aggregate does not validate these values: it drops one it
          does not recognise and answers with the UNFILTERED total. Over the
          window 2026-08-10 to 2026-08-16, where the unfiltered total is 1,387:

            pillar=leadership_change    846   honoured
            funding=1                   182   honoured
            pillar=rewards_comp          97   honoured
            pillar=company_development  229   honoured
            pillar=leadership_chang   1,387   IGNORED - one character short
            pillar=hiring_expansion   1,387   IGNORED - not a pillar at all
            pillar=                   1,387   IGNORED
            funding=0                 1,387   IGNORED
            funding=banana            1,387   IGNORED

          So a one-character typo here, or the sibling plugin renaming a pillar,
          publishes "Leadership moves 1,387" - the worldwide headline, wearing a
          category label, as a measurement. That is strictly worse than a wrong
          zero: a zero invites a question and a plausible large number does not.
          The error is SILENT, it is in the other repo's gift to cause, and no
          call fails, so the failed-call guard above cannot see it.

          THE TEST IS EQUALITY WITH THE HEADLINE, because that is the exact
          signature of the fault and this composer already holds the headline.
          It costs no extra request.

          WHAT IT GIVES UP, STATED PLAINLY: a genuine week in which every single
          signal fell into one category would be suppressed. Three categories
          cannot all equal the total, the categories overlap rather than
          partition, and the observed shares are 61%, 13% and 7%, so that week
          is not one this data produces. A suppressed true line costs a line. A
          published headline-in-disguise costs a number, and this product is
          built on the numbers being checkable.

          OMITTED AND NOT ZEROED. This is UNKNOWN - we did not measure the
          category - and the rule this file keeps is that absence of a signal is
          never a pass and never a zero.
        */
        if ((int) $cdata['total'] === $total) continue;
        $cat_counts[$cat_label] = (int) $cdata['total'];
        /*
          THE TOP THREE NAMED ITEMS IN THE CATEGORY (owner-approved
          2026-10-12): the same filter on /query, audience-ordered, three rows.
          A failed call prints no list; the count above still stands.
        */
        $iq = new WP_REST_Request('GET', '/talent/v1/query');
        $iq->set_param('since', $from);
        $iq->set_param('until', $to);
        $iq->set_param('per_page', 20);
        $iq->set_param($cat_key, $cat_value);
        $ires = rest_do_request($iq);
        if ($ires && !$ires->is_error()) {
            $idata = (array) $ires->get_data();
            $irows = is_array($idata['rows'] ?? null) ? $idata['rows'] : array();
            if (function_exists('alt_digest_audience_order')) {
                $irows = alt_digest_audience_order($irows, function ($r) { return 0; });
            }
            if ($irows) $cat_items[$cat_label] = array_slice($irows, 0, 3);
        }
        $activity[] = array(
            'label'  => $cat_label,
            'figure' => alt_digest_number((int) $cdata['total']),
            'url'    => alt_digest_track_link($send_id, alt_digest_talent_url(
                            $from, $to, array($cat_key => $cat_value))),
        );
    }
    if ($activity) {
        list($act_html, $act_text) = alt_digest_inline_series($activity);
        // The heading above already says what this is. See the region and
        // industry lines in the layoff section for the same shape.
        $act_caption = $range . ', worldwide';
        $act_tail = '. These categories overlap with the hiring signals above '
                  . 'and with each other, so they do not sum to the headline.';
        $html .= '<h3>Other talent activity</h3>'
               . '<p data-alt="series">' . esc_html($act_caption . ': ') . $act_html
               . esc_html($act_tail) . '</p>';
        $text .= "\nOther talent activity\n" . $act_caption . ': '
               . $act_text . $act_tail . "\n";
        foreach ($cat_items as $cat_label => $items) {
            list($c_html, $c_text) = alt_digest_talent_compact_list($items, $from, $to, $send_id);
            $html .= '<p data-alt="kicker">' . esc_html($cat_label) . '</p>' . $c_html;
            $text .= "\n" . $cat_label . "\n" . $c_text;
        }
    }

    /*
      WHERE (owner, 2026-10-19: "still not by geography ... State and
      country?"). Same window and same basis as the headline: the composer
      sends no filter but the window, so these count the same signals. See
      alt_digest_talent_where for the guards.
    */
    if (function_exists('alt_digest_talent_where')) {
        list($w_html, $w_text) = alt_digest_talent_where($from, $to, $send_id, $range, $total);
        $html .= $w_html;
        $text .= $w_text;
    }

    // One year-to-date line, for the reason spelled out in
    // alt_digest_compose_layoff: this data revises upward, so any
    // period-over-period delta manufactures a fall out of a reporting lag.
    // Year to date only grows. Do not add a delta here later either.
    // "How to read these numbers" is now the footnote at the bottom
    // (owner-approved 2026-10-12); see "Notes" before "Cite this".

    $year = substr((string) $to, 0, 4);
    if (preg_match('/^\d{4}$/', $year)) {
        $ytd_req = new WP_REST_Request('GET', '/talent/v1/aggregate');
        $ytd_req->set_param('since', $year . '-01-01');
        $ytd_req->set_param('until', $to);
        $ytd_req->set_param('include', 'fresh');
        $ytd_res = rest_do_request($ytd_req);
        $ytd_range = alt_digest_date_range($year . '-01-01', $to);
        if ($ytd_res && !$ytd_res->is_error() && $ytd_range !== '') {
            $ytd_total = (int) (((array) $ytd_res->get_data())['total'] ?? 0);
            if ($ytd_total > 0) {
                /*
                  THE BASIS IS STATED ONCE PER EDITION, NOT ONCE PER FIGURE.

                  Both scope lines printed the whole 27-word basis sentence,
                  about eighty lines apart in the same email, and the delivered
                  edition of 2026-09-14 read as though the second figure were
                  hedging separately. One definition still governs both - this
                  line is inside the same composer and after the window scope
                  line unconditionally, so the sentence the reader is referred
                  back to is the one alt_digest_talent_basis() returned.
                  test_digest_talent_observation holds that ordering, because
                  a back-reference to a sentence that is not there is worse
                  than the repetition it replaced.
                */
                $ytd_scope = $ytd_range . ', worldwide, counted on the same '
                           . 'basis as the window figure above.';
                // "2026 YTD", the year first, matching the layoff section. A
                // reader scanning headings meets the year before the
                // abbreviation, which is the same principle the month-first
                // date format follows.
                /*
                  THE SAME DERIVATION, OVER ITS OWN WINDOW, WHICH IS WHY THE
                  READING IS NULL AND NOT $hiring_n.

                  $hiring_n was measured over the EDITION's window. This figure
                  covers the year, and no hiring-direction reading is taken for
                  the year, so its mix is UNKNOWN. Passing the two-day reading
                  here would stamp one window's measurement on another's
                  figure - the shape the containment-pair rule exists to
                  forbid - and passing nothing at all would leave the year
                  wearing a label the day was just corrected out of.

                  So it goes through the same function with an explicit null.
                  UNKNOWN resolves to the noun that is true either way, and the
                  argument says at the call site that nobody measured this one.
                */
                $ytd_noun = alt_digest_talent_signal_noun($ytd_total, null);
                $html .= '<h3>' . esc_html($year) . ' YTD</h3>'
                       . '<p data-alt="stat">' . esc_html(alt_digest_number($ytd_total)) . '</p>'
                       . '<p data-alt="unit">'
                       . esc_html(alt_digest_verb($ytd_total, $ytd_noun,
                                                  $ytd_noun . 's')) . '</p>'
                       . '<p data-alt="scope">' . esc_html($ytd_scope) . '</p>';
                $text .= "\n{$year} YTD\n"
                       . alt_digest_count($ytd_total, $ytd_noun) . ', '
                       . $ytd_scope . "\n";
            }
        }
    }

    /*
      JOBS IN: THE INDEED BACKDROP, IN THE TALENT SECTION, and this is its
      natural home: the talent section is about hiring, and Indeed Hiring Lab's
      US Job Postings Index is the whole-market context for hiring. It is placed
      AFTER our own signals (the headline, the biggest signals, the activity
      lines and the YTD figure) and BEFORE the footer link and citation, so a
      reader has read the tracker's own figures before meeting the outside
      series - the same running order the monthly layoff section uses.

      IT IS THE SAME alt_digest_indeed_block() the monthly layoff section reuses,
      guarded the same way: a WHOLE-BLOCK omission when the sibling talent plugin
      or its data is absent (function_exists inside the helper, null return here
      omits it), never a fabricated figure. The block heads and sources itself
      ("Jobs in: US hiring demand", Indeed Hiring Lab, CC BY 4.0, its own as-of
      dates) and its own copy says it is external context "not counted in the
      totals above" - so a reader never adds this whole-market index
      level (base 100 = February 1, 2020) to our signal counts. It is a THIRD
      distinct unit from a cut and a hiring signal, and it says so.

      $is_monthly GATES IT OUT of the talent section, because on the monthly
      edition the layoff section already carries the identical block - see the
      $is_monthly note at the top of this function for why one home per edition
      is the whole dedup story.
    */
    if (!$is_monthly && function_exists('alt_digest_indeed_block')) {
        $indeed = alt_digest_indeed_block();
        if ($indeed !== null) {
            $html .= $indeed['html'];
            $text .= $indeed['text'];
        }
    }

    /*
      THE LINK CARRIES THE WINDOW THE LABEL PROMISES. It used to point at the
      bare page, which opens on the tracker's own default window, under a label
      reading "for August 10-16, 2026". See alt_digest_talent_url.

      $url, the unparameterised page, is still what the citation below prints,
      and deliberately: a bibliography entry names the work, and the window it
      covers is already a separate field in that entry.
    */
    $open = alt_digest_talent_url($from, $to);
    $click = alt_digest_track_link($send_id, $open);
    $link_text = 'Open the Talent Intelligence Tracker for ' . $range;
    $html .= '<p><a href="' . esc_url($click) . '">' . esc_html($link_text) . '</a></p>';
    $text .= "\n{$link_text}:\n{$open}\n";

    /*
      THIS SECTION IS AS CITABLE AS THE OTHER ONE, and until now only one of
      them said so. A reader who quotes a hiring-signal figure out of this
      email has the same problem a reader quoting a layoff figure has: the
      email is a snapshot and the database behind it keeps moving.

      NO "AS OF" STAMP HERE, and that is honest absence rather than an
      oversight. The layoff citation carries one because api.php publishes the
      layoff table's last write. The talent endpoints publish no equivalent, so
      this cites the window and the access time, which are the two facts we
      really have. Do not fill the gap with the layoff tracker's stamp: they
      are separate databases on separate ingest schedules.

      Plain text, not an anchor, for the reason spelled out on
      alt_digest_cite_note: a citation is a string somebody pastes, and a
      counted link in a published story records our click counter instead of
      our address.
    */
    $read_date = alt_digest_date_range(gmdate('Y-m-d'), gmdate('Y-m-d'));
    if ($read_date !== '') {
        $read_date .= ' at ' . gmdate('H:i') . ' UTC';
        list($cite, $cite_url, $cite_note) = alt_digest_cite_note(
            'Talent Intelligence Tracker', $range, $url, $read_date, '');
        $html .= '<h3>Notes</h3>' . $notes_html;
        $text .= "\nNotes\n" . $notes_text;
        $notes_html = '';
        $html .= '<h3>Cite this</h3>'
               . '<p data-alt="note">' . esc_html($cite) . '</p>'
               . '<p data-alt="note">' . esc_html($cite_url) . '</p>';
        $text .= "\nCite this\n" . $cite . "\n" . $cite_url . "\n";
    }
    /*
      ITS OWN SUBJECT AND ITS OWN METRIC FRAGMENT, EACH BOUND TO ITS UNIT.

      A signal is not a "job" and not a "cut", and the combined edition's
      subject sets this figure beside the layoff tracker's. Two numbers side by
      side are read as the same quantity unless each says what it counts, so
      the unit lives inside the fragment rather than being implied by position.

      AND THE UNIT IS THE ONE THIS EDITION MEASURED, not a word typed here.
      This read 'hiring signal' unconditionally, so the subject of 2026-08-28
      promised "30 hiring signals" over a window in which nine of the thirty
      stated a direction of hiring - the contradiction being printed, in the
      same message, four lines below the fold. The subject is the line most
      recipients only ever see, so it is the worst place in the product for a
      hardcoded claim about variable data. See alt_digest_talent_signal_noun.
    */
    $metric = alt_digest_count($total, $signal_noun);
    if ($is_daily && function_exists('alt_digest_talent_daily_metric')) {
        $daily_metric = alt_digest_talent_daily_metric(
            $cat_counts['Funding rounds'] ?? null, $cat_counts['Leadership moves'] ?? null);
        if ($daily_metric !== '') $metric = $daily_metric;
    }
    return array('html' => $html, 'text' => $text, 'preheader' => $preheader,
                 'metric' => $metric);
}

/**
 * A compact list: "Company: headline (place)", the headline linked to its
 * source exactly as the main list links it. Used for "More" and for the top
 * three named items per category (owner-approved 2026-10-12).
 */
function alt_digest_talent_compact_list($rows, $from, $to, $send_id) {
    $html = '<ul>';
    $text = '';
    foreach ((array) $rows as $row) {
        $row = (array) $row;
        $co = trim((string) ($row['company'] ?? ''));
        $head = trim((string) ($row['headline'] ?? ''));
        if ($head === '') { $line = $co; }
        elseif ($co === '' || alt_digest_headline_names_company($co, $head)) { $line = $head; }
        else { $line = $co . ': ' . $head; }
        $line = alt_digest_plain_dashes($line);
        if ($line === '') continue;
        $place = alt_digest_talent_place($row);
        $src = trim((string) ($row['source_url'] ?? ''));
        $href = '';
        if (alt_digest_external_link_ok($src)) {
            $href = $src;
        } elseif ($co !== '') {
            $href = alt_digest_track_link($send_id, alt_digest_talent_url($from, $to, array('company' => $co)));
        }
        $shown = esc_html($line);
        if ($href !== '') $shown = '<a href="' . esc_url($href) . '">' . $shown . '</a>';
        list($lang_tag, $gist) = alt_digest_talent_language_bits($row);
        $paren = implode(', ', array_filter(array($lang_tag, $place), 'strlen'));
        if ($paren !== '') { $shown .= ' ' . esc_html('(' . $paren . ')'); $line .= ' (' . $paren . ')'; }
        if ($gist !== '') $shown .= '<br><span data-alt="gist">' . esc_html($gist) . '</span>';
        $html .= '<li>' . $shown . '</li>';
        $text .= '  - ' . $line . "\n";
        if ($gist !== '') $text .= '    ' . $gist . "\n";
    }
    return array($html . '</ul>', $text);
}

/**
 * THE LANGUAGE TAG AND THE ENGLISH GIST, both read from the talent tracker's
 * stored columns and never inferred here (owner-approved 2026-10-12).
 *
 * The comment in the ranked list above explains why this composer refused to
 * name a language it would have had to guess. The tracker now stores one
 * (talent-intelligence-tracker pipeline/language.py: free, local, an ISO
 * 639-1 code that is NULL whenever its detector is not confident), so the tag
 * prints exactly that stored code and nothing when it is absent, malformed or
 * English. The gist is the tracker's own stored summary, printed only when
 * the tracker says that summary is English; no translation is made here or
 * anywhere (no extra AI spend). An unknown code is shown as the code.
 *
 * Returns array(tag, gist), each '' when it does not apply.
 */
function alt_digest_talent_language_bits($row) {
    $row = (array) $row;
    $code = strtolower(trim((string) ($row['language'] ?? '')));
    if (!preg_match('/^[a-z]{2}$/', $code) || $code === 'en') return array('', '');
    $names = array(
        'ar' => 'Arabic', 'bn' => 'Bengali', 'cs' => 'Czech', 'da' => 'Danish',
        'de' => 'German', 'el' => 'Greek', 'es' => 'Spanish', 'fa' => 'Persian',
        'fr' => 'French', 'he' => 'Hebrew', 'hi' => 'Hindi', 'hy' => 'Armenian',
        'id' => 'Indonesian', 'it' => 'Italian', 'ja' => 'Japanese',
        'ka' => 'Georgian', 'ko' => 'Korean', 'nl' => 'Dutch', 'no' => 'Norwegian',
        'pl' => 'Polish', 'pt' => 'Portuguese', 'ro' => 'Romanian',
        'ru' => 'Russian', 'sr' => 'Serbian', 'sv' => 'Swedish', 'ta' => 'Tamil',
        'th' => 'Thai', 'tr' => 'Turkish', 'uk' => 'Ukrainian', 'zh' => 'Chinese',
    );
    $tag = isset($names[$code]) ? ('in ' . $names[$code]) : ('language: ' . $code);
    $gist = '';
    $summary = trim((string) ($row['summary'] ?? ''));
    if ($summary !== '' && strtolower((string) ($row['summary_language'] ?? '')) === 'en') {
        if (function_exists('mb_strlen') && mb_strlen($summary) > 240) {
            $summary = rtrim(mb_substr($summary, 0, 237)) . '...';
        }
        $gist = 'English summary: ' . alt_digest_plain_dashes($summary);
    }
    return array($tag, $gist);
}

/**
 * THE "WHERE" BLOCK OF THE TALENT EDITION: signals by country (top 8, then
 * "and N more countries"), and for the United States, signals by state (top 8).
 *
 * COUNTS SIGNALS, NEVER MONEY. Every figure is a row count from the talent
 * plugin's own /aggregate (`by_country`, `by_state`), over the SAME window and
 * the same (absent) filters as the headline, so a line here and the headline
 * describe one set of rows. Country is the tracker's own coalesce of job
 * location and employer HQ (tit_country_expr), the same basis its page and its
 * By location table use; nothing is re-derived here.
 *
 * "N MORE" IS MEASURED, NOT INFERRED. `by_country` is capped at 40 values, so
 * the remainder is the endpoint's own distinct-country count minus the printed
 * eight, never the length of a capped list.
 *
 * GUARDS, SAME SHAPE AS "OTHER TALENT ACTIVITY": a failed call prints no line
 * (UNKNOWN, not zero), and a US-filtered total equal to the worldwide headline
 * while other countries are present is the signature of a filter the endpoint
 * ignored, so the state line is dropped rather than published as US-only.
 * Signals with no country recorded are not placed and are not guessed.
 *
 * Returns array(html, text), both '' when nothing can be said.
 */
function alt_digest_talent_where($from, $to, $send_id, $range, $total) {
    $ask = function ($extra) use ($from, $to) {
        $req = new WP_REST_Request('GET', '/talent/v1/aggregate');
        $req->set_param('since', $from);
        $req->set_param('until', $to);
        foreach ($extra as $k => $v) $req->set_param($k, $v);
        $res = rest_do_request($req);
        if (!$res || $res->is_error()) return null;
        return (array) $res->get_data();
    };
    $pairs = function ($list) {
        $out = array();
        foreach ((is_array($list) ? $list : array()) as $row) {
            $row = (array) $row;
            $k = strtoupper(trim((string) ($row['k'] ?? '')));
            $n = (int) ($row['n'] ?? 0);
            if ($k === '' || $n <= 0) continue;
            $out[$k] = $n;
        }
        arsort($out);
        return $out;
    };
    $more = function ($rest, $one, $many) {
        if (function_exists('alt_digest_more_tail')) return alt_digest_more_tail($rest, $one, $many);
        return '.';
    };
    $html = ''; $text = '';
    $world = $ask(array());
    if ($world === null) return array('', '');
    $countries = $pairs($world['by_country'] ?? null);
    if (count($countries) < 1) return array('', '');
    $shown = array_slice($countries, 0, 8, true);
    $rows = array();
    foreach ($shown as $code => $n) {
        $name = function_exists('tit_country_name') ? (string) tit_country_name($code) : '';
        $rows[] = array(
            'label'  => $name !== '' ? $name : $code,
            'figure' => alt_digest_number($n),
            'url'    => alt_digest_track_link($send_id, alt_digest_talent_url(
                            $from, $to, array('country' => $code))),
        );
    }
    $distinct = array_key_exists('countries', $world) ? (int) $world['countries'] : count($countries);
    $tail = $more(max($distinct, count($countries)) - count($rows), 'country', 'countries');
    list($c_html, $c_text) = alt_digest_inline_series($rows);
    $caption = $range . ', signals by country (job location, else employer head office)';
    $html .= '<h3>Where</h3>'
           . '<p data-alt="series">' . esc_html($caption . ': ') . $c_html
           . esc_html($tail) . '</p>';
    $text .= "\nWhere\n" . $caption . ': ' . $c_text . $tail . "\n";

    if (isset($countries['US'])) {
        $us = $ask(array('country' => 'US'));
        $ignored = $us !== null && count($countries) > 1
                   && (int) ($us['total'] ?? -1) === (int) $total;
        if ($us !== null && !$ignored) {
            $states = $pairs($us['by_state'] ?? null);
            if (count($states) > 1) {
                $map = function_exists('alt_us_state_names') ? alt_us_state_names() : array();
                $srows = array();
                foreach (array_slice($states, 0, 8, true) as $code => $n) {
                    $srows[] = array(
                        'label'  => isset($map[$code]) ? $map[$code] : $code,
                        'figure' => alt_digest_number($n),
                        'url'    => alt_digest_track_link($send_id, alt_digest_talent_url(
                                        $from, $to, array('country' => 'US', 'state' => $code))),
                    );
                }
                $stail = $more(count($states) - count($srows), 'state', 'states');
                list($s_html, $s_text) = alt_digest_inline_series($srows);
                $scap = $range . ', US signals by state';
                $html .= '<p data-alt="series">' . esc_html($scap . ': ') . $s_html
                       . esc_html($stail) . '</p>';
                $text .= $scap . ': ' . $s_text . $stail . "\n";
            }
        }
    }
    return array($html, $text);
}

