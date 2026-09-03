(() => {
  const api = altHealthData.apiUrl;
  const $ = id => document.getElementById(id);
  // Escapes the QUOTES as well as the angle brackets. This function's output
  // is interpolated into ATTRIBUTES, not only into text: `class="alt-health-
  // ${esc(x.status)}"` and `title="${esc(...)}"` below. A value containing a
  // double quote closed the attribute and everything after it was markup, so
  // an angle-bracket-only escape was no escape at all in exactly the places
  // this is used most. Defence in depth: status and detail come from our own
  // collectors, but the ledger is written by a keyed endpoint and this file
  // paints whatever it is handed.
  const esc = v => String(v ?? 'not recorded').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmt = v => v ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(v)) + ' UTC' : 'Not yet reported';
  // A failed/running collection did not produce a count. Showing "0 found"
  // would incorrectly turn an unavailable query into evidence of zero news.
  const entriesLabel = x => (x && x.status === 'ok')
    ? `${Number(x.entries || 0).toLocaleString()} found`
    : 'No completed count';
  // The Railway-cron cadence, handed over by PHP from data/ingest-schedule.json
  // rather than typed here. Eight collector labels below read 'Twice daily'
  // through the whole of 2026-08-14..20, when the cron had been running once a
  // day since the 14th. A cadence typed into a label has nothing to fail when
  // the schedule moves.
  const cap = t => t ? t.charAt(0).toUpperCase() + t.slice(1) : '';
  const CRON = cap(altHealthData.ingestCadence) || 'On the ingest schedule';
  // [coverage target, cadence, country/region, collection method]. The
  // region+method pair renders under the source id in both tables so a reader
  // can see what country a collector serves and how it collects.
  const meta = {
    edgar: ['SEC EDGAR 8-K/6-K; US and foreign issuers', CRON, 'United States', 'Official filings API'],
    warn_us: ['State WARN mass-layoff notices', 'Daily', 'United States', 'State labor-agency notices'],
    warn_quebec: ['Quebec collective-dismissal notices (MESS)', 'Daily check, monthly register', 'Canada', 'Provincial labour-ministry filings'],
    federal_rif: ['US federal RIF separations (OPM EHRI)', 'Monthly', 'United States', 'Official OPM workforce dataset'],
    warn_hi_ocr: ['Hawaii WARN notices (OCR)', 'Daily', 'United States', 'Scanned state notices, OCR-read'],
    warn_mn_letters: ['Minnesota per-company WARN letters', 'Daily', 'United States', 'State labor-agency notices'],
    warn_mazowieckie: ['Mazowieckie collective dismissals (WUP Warszawa)', 'Daily check, monthly register', 'Poland', 'Official regional labour-office register'],
    source_audit: ['Monthly self-audit (rows re-verified against their sources)', 'Monthly', 'Internal QA', 'Read-only accuracy check'],
    newsapi: ['Retired collector (replaced by Google News RSS)', 'Retired 2026-07-25', 'Worldwide', 'Licensed news API'],
    news_catchup: ['Weekly catch-up sweep of credible outlets (fills weekend gaps)', 'Weekly', 'Worldwide', 'Licensed news API'],
    data_integrity: ['Live data-integrity guards: known duplicates count once, no single row carries a headline, no headline moves without rows to explain it', 'Daily', 'Internal QA', 'Read-only assertions against the public API'],
    google_news: ['Free worldwide layoff-headline discovery (no key)', CRON, 'Worldwide', 'Google News RSS'],
    local_news: ['Local-language market sweep, searching each market in its own words', CRON, '25 markets', 'Google News national editions'],
    regional_feeds: ['Regional news feeds covering low-volume countries: RNZ Pacific, Pacific Island Times, Financial Afrik, Jeune Afrique, Caribbean News Global', CRON, 'Pacific · Francophone Africa · Caribbean', 'Publisher RSS feeds'],
    national_feeds: ['One verified national publisher per mid-sized economy. Egypt, Colombia, Ethiopia, Kazakhstan, Ghana, Pakistan, Jordan, Iraq, Jamaica, Nepal, Papua New Guinea, Paraguay, Serbia and Peru', CRON, '14 countries', 'Publisher RSS feeds'],
    gdelt: ['Worldwide multilingual news discovery', CRON, 'Worldwide', 'Open news-index files, with mirror and API fallbacks'],
    gdelt_historical: ['Worldwide historical news recovery', 'Daily, success-anchored', 'Worldwide', 'Open news-index API'],
    press_releases: ['Reviewed company-controlled IR/newsroom feeds', CRON, 'Per reviewed company (US · DE)', 'Company RSS/Atom feeds'],
    eurofound_erm: ['Eurofound ERM restructuring announcements', 'Daily', 'European Union', 'Official monitor dataset'],
    company_watchlist: ['Targeted sweep of large employers with no current-year entry', 'Daily, rotating slice', 'Worldwide', 'Licensed news API'],
    supplemental_news: ['Non-English / global news expansion (NewsData.io · Marketaux · Finnhub)', 'Daily', 'Worldwide (Europe-weighted)', 'Licensed news APIs'],
    warn_custom_states: ['Custom-scraper WARN states (drift watchdog)', 'Daily', 'United States', 'State labor-agency notices'],
    context_enrichment: ['Existing source-linked records', 'Daily evidence-only', 'Internal', 'Evidence re-read'],
    reason_backfill: ['Untagged non-WARN records; reason tags only', 'Daily evidence-only', 'Internal', 'Stored-excerpt classification'],
    role_enrichment: ['Role categories from already-stored row text', 'Daily evidence-only', 'Internal', 'Stored-evidence re-read'],
    archive_backfill: ['Permanent Internet Archive (Wayback) snapshots of every source link', 'Daily, resumable', 'Internal', 'Wayback availability + Save Page Now'],
    dedupe_llm: ['Cross-source duplicate remover (daily deep scan)', 'Daily', 'Internal', 'Cross-source dedup'],
    edinet_jp: ['EDINET daily filing list, discovery only, nothing ingested', 'Retired 2026-07-24', 'Japan', 'Official filings API'],
    opendart_kr: ['OpenDART disclosure list, discovery only, nothing ingested', 'Retired 2026-07-24', 'South Korea', 'Official filings API'],
    cvm_br: ['CVM Fato Relevante yearly index, discovery only, nothing ingested', 'Retired 2026-07-24', 'Brazil', 'Official open-data portal'],
    companies_house_insolvency: ['UK insolvency signals, lead to targeted news', 'Weekly', 'United Kingdom', 'Official registry API'],
    courtlistener_bankruptcy: ['US bankruptcy petitions, lead to targeted news', 'Weekly', 'United States', 'Federal court dockets'],
    edgar_historical: ['Historical SEC 8-K/6-K backfill (live feed is "edgar")', 'Backfill, resumable', 'United States', 'Official filings API'],
    industry_backfill: ['Industry tags for existing rows, evidence-only', 'Daily evidence-only', 'Internal', 'Stored-evidence re-read'],
    digest_mailer: ['Email digest sender (subscriber digests for both trackers; counts only, never addresses)', 'Daily (WP-Cron, traffic-dependent)', 'Internal', 'Composed from the trackers\u2019 own public APIs and the site\u2019s own posts'],
    digest_weekly: ['Weekly digest slot liveness (the external sender\u2019s own completed-pass signal; counts only, never addresses)', 'Weekly (Mondays, 7:30 AM Eastern)', 'Internal', 'Self-reported by the scheduled sender after a completed weekly pass'],
    link_check: ['Broken-link tripwire: public pages + source-rot sample', 'Daily', 'Internal QA', 'HTTP reachability check'],
    warn_custom_legacy: ['Legacy custom-scraper WARN states (drift watchdog family)', 'Daily', 'United States', 'State labor-agency notices'],
    backup_export: ['Weekly off-host backup of every public table, checked for drift (subscriber data is never included)', 'Weekly (Sundays)', 'Internal', 'Keyed read of our own tables, published as a GitHub release'],
  };
  const srcLabel = id => {
    const m = meta[id];
    return m && m[2]
      ? `${esc(id)}<br><small class="alt-health-src-meta">${esc(m[2])} · ${esc(m[3])}</small>`
      : esc(id);
  };
  const get = path => fetch(api + path + (path.includes('?') ? '&' : '?') + 'cb=' + Date.now()).then(r => r.ok ? r.json() : Promise.reject(path));

  function renderRuns(ledger) {
    const runs = ledger && Array.isArray(ledger.runs) ? ledger.runs : [];
    $('alt-health-runs').innerHTML = runs.map(x => `<tr><td><time>${esc(fmt(x.attempted_at))}</time></td><th>${srcLabel(x.source)}</th><td><span class="alt-health-status alt-health-${esc(x.status)}">${esc(x.status)}</span></td><td>${Number(x.entries || 0).toLocaleString()}</td><td>${esc(x.detail || '')}</td></tr>`).join('') || '<tr><td colspan="5">No collector attempts are recorded for this window. History begins with the ledger release.</td></tr>';
  }

  function loadRuns(days) {
    $('alt-health-runs').innerHTML = '<tr><td colspan="5">Loading collector-run history…</td></tr>';
    return get(`source-runs?days=${encodeURIComponent(days)}&per_page=200`).then(renderRuns).catch(() => {
      $('alt-health-runs').innerHTML = '<tr><td colspan="5">Collector-run history could not be loaded. Please retry.</td></tr>';
    });
  }

  function initWidgetBuilder() {
    const year = $('alt-widget-year'), state = $('alt-widget-state'), code = $('alt-widget-code');
    const copy = $('alt-widget-copy'), tracker = $('alt-widget-tracker-link'), status = $('alt-widget-copy-status');
    if (!year || !state || !code || !copy || !tracker || !window.altHealthData.widgetUrl || !window.altHealthData.trackerUrl) return;
    const currentYear = new Date().getUTCFullYear();
    for (let y = currentYear; y >= 2015; y--) {
      const option = document.createElement('option'); option.value = String(y); option.textContent = String(y); year.appendChild(option);
    }
    const update = () => {
      const selectedState = /^[A-Z]{2}$/.test(state.value) ? state.value : '';
      const widgetUrl = new URL(window.altHealthData.widgetUrl, window.location.origin);
      widgetUrl.searchParams.set('tracker_year', year.value);
      if (selectedState) widgetUrl.searchParams.set('state', selectedState);
      const trackerUrl = new URL(window.altHealthData.trackerUrl, window.location.origin);
      trackerUrl.searchParams.set('years', year.value); trackerUrl.searchParams.set('country', 'United States');
      if (selectedState) trackerUrl.searchParams.set('state', selectedState);
      const scope = selectedState ? selectedState : 'United States';
      code.value = `<iframe src="${widgetUrl.toString()}" title="${scope} layoff tracker widget, ${year.value}" loading="lazy" style="width:100%;max-width:420px;height:220px;border:0"></iframe>`;
      tracker.href = trackerUrl.toString();
      status.textContent = '';
    };
    get('facets').then(facets => {
      (Array.isArray(facets.states) ? facets.states : []).filter(x => /^[A-Z]{2}$/.test(x)).forEach(value => {
        const option = document.createElement('option'); option.value = value; option.textContent = `United States · ${value}`; state.appendChild(option);
      });
    }).catch(() => { /* National widget remains available if facets are unavailable. */ });
    year.addEventListener('change', update); state.addEventListener('change', update); update();
    copy.addEventListener('click', () => {
      const finish = ok => { status.textContent = ok ? 'Widget code copied.' : 'Select and copy the code above.'; };
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(code.value).then(() => finish(true)).catch(() => finish(false));
      else { code.focus(); code.select(); try { finish(document.execCommand('copy')); } catch (_) { finish(false); } }
    });
  }

  initWidgetBuilder();

  // Each endpoint retries once and degrades to null on failure, so one flaky
  // fetch renders as a visible gap in its own section instead of blanking the
  // entire page (observed live 2026-07-19).
  // A stalled fetch that never settles (not reject, just hangs) would otherwise
  // block the Promise.all below FOREVER and leave the whole page stuck on
  // "Loading…" — the fetch retry/.catch can't save a request that never
  // returns. Race every request against an 9s timeout that resolves null, so a
  // single hung endpoint degrades to its own empty section instead of bricking
  // the page (observed live 2026-07-24).
  const withTimeout = (p, ms) => Promise.race([
    p, new Promise(resolve => setTimeout(() => resolve(null), ms)),
  ]);
  // NB: one Promise.all slot is a `null` placeholder (a removed feed). safeGet
  // MUST handle null WITHOUT calling get(null) — get() does path.includes('?'),
  // which throws a synchronous TypeError on null DURING the .map(), before
  // Promise.all runs, so neither .then nor .catch ever fires and the whole page
  // freezes on "Loading…". (A prior timeout-only fix could not catch a
  // synchronous throw.) Short-circuit null to a resolved promise.
  const safeGet = path => path == null
    ? Promise.resolve(null)
    : withTimeout(get(path).catch(() => get(path)).catch(() => null), 9000);

  // (Public competitor benchmark removed — comparison is kept private in the owner's local benchmark, per the standalone-brand rule.)

  setInterval(function () { if (document.hidden) location.reload(); }, 600000);
  Promise.all(['quality-status', 'integrity-status', 'status', 'review-queue', null, 'benchmarks/recall', 'dataset-releases'].map(safeGet)).then(([q, i, s, r, c, rec, ledger]) => {
    q = q || { source_health: {}, workstreams: [], last_30_days_disclosed_changes: {} };
    i = i || { canonical_events: 0, source_reports: 0, source_report_hashes_remaining: 0, metadata_completeness: {}, canonical_events_without_linked_source_reports: 0 };
    s = s || {}; r = r || {}; rec = rec || []; ledger = ledger || {};
    const h = q.source_health || {};
    const degraded = Object.values(h).filter(x => x.status === 'degraded').length;
    const completeness = i.metadata_completeness || {};
    $('alt-health-updated').textContent = `Pipeline: ${s.pipeline_phase || 'live'} · last data write ${fmt(s.last_updated)} · checked ${fmt(q.generated_at)}`;
    $('alt-health-summary').innerHTML = `<div><b>${i.canonical_events.toLocaleString()}</b><span>canonical entries</span></div><div><b>${i.source_reports.toLocaleString()}</b><span>retained reports</span></div><div><b>${degraded}</b><span>degraded source${degraded === 1 ? '' : 's'}</span></div><div><b>${i.source_report_hashes_remaining.toLocaleString()}</b><span>evidence hashes pending</span></div>`;
    // Live collectors first; retired ones sink to the bottom so a reader sees
    // what is running before what we deliberately stood down.
    $('alt-health-sources').innerHTML = Object.entries(h)
      .sort(([, a], [, b]) => (a.status === 'retired' ? 1 : 0) - (b.status === 'retired' ? 1 : 0))
      .map(([id, x]) => {
      const m = meta[id] || ['Operational collector', 'See source-health'];
      return `<tr><th>${srcLabel(id)}</th><td>${esc(m[0])}</td><td>${esc(m[1])}</td><td><time>${esc(fmt(x.checked_at))}</time></td><td>${esc(entriesLabel(x))}</td><td><span class="alt-health-status alt-health-${esc(x.status)}">${esc(x.status)}</span> ${esc(x.detail || '')}</td></tr>`;
    }).join('') || '<tr><td colspan="6">No collector reports yet.</td></tr>';
    $('alt-health-workstreams').innerHTML = (q.workstreams || []).map(x => `<p><span class="alt-health-status alt-health-${esc(x.status)}">${esc(x.status)}</span> <b>${esc(x.id.replaceAll('_', ' '))}</b><br>${esc(x.scope)}</p>`).join('');
    const last = Array.isArray(c) && c[0] ? c[0] : null;
    $('alt-health-backlogs').innerHTML = `<p><b>Retained entry to source links:</b> ${Number(i.canonical_events_without_linked_source_reports || 0).toLocaleString()} canonical entr${Number(i.canonical_events_without_linked_source_reports || 0) === 1 ? 'y' : 'ies'} missing a linked retained-source record. This is a visible integrity gap in the entry to source graph; the canonical row may still have its own source URL.</p><p><b>Evidence hash backfill:</b> ${i.source_report_hashes_remaining.toLocaleString()} retained excerpts pending.</p><p><b>Industry metadata:</b> ${Number(completeness.rows_missing_industry || 0).toLocaleString()} rows remain blank rather than inferred.</p><p><b>US job-location state:</b> ${Number(completeness.us_rows_missing_job_location_state || 0).toLocaleString()} US rows are state-unspecified; headquarters and office footprint are never substituted.</p><p><b>Editorial review:</b> ${(r.total || 0).toLocaleString()} high-impact records queued.</p><p><b>Country recall:</b> ${(rec || []).length ? 'published sample available' : 'no current independently documented sample published'}.</p>`;
    const releases = Array.isArray(ledger.releases) ? ledger.releases.slice().sort((a, b) => String(a.released_at).localeCompare(String(b.released_at))) : [];
    const first = releases[0], latest = releases[releases.length - 1];
    const changes = q.last_30_days_disclosed_changes || {};
    if (latest) {
      const eventDelta = first ? Number(latest.canonical_events || 0) - Number(first.canonical_events || 0) : 0;
      const reportDelta = first ? Number(latest.source_reports || 0) - Number(first.source_reports || 0) : 0;
      $('alt-health-release-report').innerHTML = `<p><b>Current public release:</b> ${esc(latest.plugin_version || 'not recorded')} · dataset revision ${Number(latest.dataset_revision || 0).toLocaleString()} · released ${esc(fmt(latest.released_at))}.</p><p><b>Ledger window:</b> ${first ? `${esc(fmt(first.released_at))} to ${esc(fmt(latest.released_at))}` : 'latest snapshot only'} · net canonical entries ${eventDelta >= 0 ? '+' : ''}${eventDelta.toLocaleString()} · net retained reports ${reportDelta >= 0 ? '+' : ''}${reportDelta.toLocaleString()}. This is net change, not gross additions.</p><p><b>Disclosed actions, rolling 30 days:</b> ${Number(changes.corrected || 0).toLocaleString()} corrected · ${Number(changes.removed || 0).toLocaleString()} removed · ${Number(changes.merged || 0).toLocaleString()} merged · ${Number(changes.reclassified || 0).toLocaleString()} reclassified · ${Number(changes.enriched || 0).toLocaleString()} enriched.</p><p><b>Coverage status now:</b> ${degraded ? `${degraded} source${degraded === 1 ? ' is' : 's are'} visibly degraded; see Collector operations above.` : 'No source is currently marked degraded.'}</p>`;
    } else {
      $('alt-health-release-report').textContent = 'No retained release snapshots are available yet.';
    }
    const window = $('alt-health-run-days');
    loadRuns(window.value);
    window.addEventListener('change', () => loadRuns(window.value));
  }).catch(e => {
    $('alt-health-updated').textContent = 'Health data could not be loaded. Please retry.';
    console.error(e);
  });
})();
