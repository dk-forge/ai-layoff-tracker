(() => {
  const api = altHealthData.apiUrl;
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '—').replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const fmt = v => v ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(v)) + ' UTC' : 'Not yet reported';
  // A failed/running collection did not produce a count. Showing "0 found"
  // would incorrectly turn an unavailable query into evidence of zero news.
  const entriesLabel = x => (x && x.status === 'ok')
    ? `${Number(x.entries || 0).toLocaleString()} found`
    : 'No completed count';
  // [coverage target, cadence, country/region, collection method]. The
  // region+method pair renders under the source id in both tables so a reader
  // can see what country a collector serves and how it collects.
  const meta = {
    edgar: ['SEC EDGAR 8-K/6-K; US and foreign issuers', 'Twice daily', 'United States', 'Official filings API'],
    warn_us: ['State WARN mass-layoff notices', 'Daily', 'United States', 'State labor-agency notices'],
    newsapi: ['Worldwide licensed news discovery', 'Twice daily', 'Worldwide', 'Licensed news API'],
    gdelt: ['Worldwide multilingual news discovery', 'Twice daily', 'Worldwide', 'Open news-index API'],
    gdelt_historical: ['Worldwide historical news recovery', 'Daily, success-anchored', 'Worldwide', 'Open news-index API'],
    press_releases: ['Reviewed company-controlled IR/newsroom feeds', 'Twice daily', 'Per reviewed company (US · DE)', 'Company RSS/Atom feeds'],
    eurofound_erm: ['Eurofound ERM restructuring announcements', 'Daily', 'European Union', 'Official monitor dataset'],
    context_enrichment: ['Existing source-linked records', 'Daily evidence-only', 'Internal', 'Evidence re-read'],
    edinet_jp: ['EDINET daily filing list — discovery only, nothing ingested', 'Twice daily', 'Japan', 'Official filings API'],
    opendart_kr: ['OpenDART disclosure list — discovery only, nothing ingested', 'Twice daily', 'South Korea', 'Official filings API'],
    cvm_br: ['CVM Fato Relevante yearly index — discovery only, nothing ingested', 'Twice daily', 'Brazil', 'Official open-data portal'],
    companies_house_uk: ['Registered-identity checks; identity support only', 'On demand', 'United Kingdom', 'Official registry API'],
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

  Promise.all(['quality-status', 'integrity-status', 'status', 'review-queue', 'benchmarks/challenger', 'benchmarks/recall', 'dataset-releases'].map(get)).then(([q, i, s, r, c, rec, ledger]) => {
    const h = q.source_health || {};
    const degraded = Object.values(h).filter(x => x.status === 'degraded').length;
    const completeness = i.metadata_completeness || {};
    $('alt-health-updated').textContent = `Pipeline: ${s.pipeline_phase || 'live'} · last data write ${fmt(s.last_updated)} · checked ${fmt(q.generated_at)}`;
    $('alt-health-summary').innerHTML = `<div><b>${i.canonical_events.toLocaleString()}</b><span>canonical events</span></div><div><b>${i.source_reports.toLocaleString()}</b><span>retained reports</span></div><div><b>${degraded}</b><span>degraded source${degraded === 1 ? '' : 's'}</span></div><div><b>${i.source_report_hashes_remaining.toLocaleString()}</b><span>evidence hashes pending</span></div>`;
    $('alt-health-sources').innerHTML = Object.entries(h).map(([id, x]) => {
      const m = meta[id] || ['Operational collector', 'See source-health'];
      return `<tr><th>${srcLabel(id)}</th><td>${esc(m[0])}</td><td>${esc(m[1])}</td><td><time>${esc(fmt(x.checked_at))}</time></td><td>${esc(entriesLabel(x))}</td><td><span class="alt-health-status alt-health-${esc(x.status)}">${esc(x.status)}</span> ${esc(x.detail || '')}</td></tr>`;
    }).join('') || '<tr><td colspan="6">No collector reports yet.</td></tr>';
    $('alt-health-workstreams').innerHTML = (q.workstreams || []).map(x => `<p><span class="alt-health-status alt-health-${esc(x.status)}">${esc(x.status)}</span> <b>${esc(x.id.replaceAll('_', ' '))}</b><br>${esc(x.scope)}</p>`).join('');
    const last = Array.isArray(c) && c[0] ? c[0] : null;
    $('alt-health-backlogs').innerHTML = `<p><b>Retained event-source links:</b> ${Number(i.canonical_events_without_linked_source_reports || 0).toLocaleString()} canonical event${Number(i.canonical_events_without_linked_source_reports || 0) === 1 ? '' : 's'} missing a linked retained-source record. This is a visible event-graph integrity gap; the canonical row may still have its own source URL.</p><p><b>Evidence hash backfill:</b> ${i.source_report_hashes_remaining.toLocaleString()} retained excerpts pending.</p><p><b>Industry metadata:</b> ${Number(completeness.rows_missing_industry || 0).toLocaleString()} rows remain blank rather than inferred.</p><p><b>US job-location state:</b> ${Number(completeness.us_rows_missing_job_location_state || 0).toLocaleString()} US rows are state-unspecified; headquarters and office footprint are never substituted.</p><p><b>Editorial review:</b> ${(r.total || 0).toLocaleString()} high-impact records queued.</p><p><b>Challenger:</b> ${last ? `${Number(last.tracker_ai_primary_announced_us_employer_jobs_ytd).toLocaleString()} strict tracker vs ${Number(last.challenger_ai_jobs_ytd).toLocaleString()} benchmark` : 'No retained comparison yet'}.</p><p><b>Country recall:</b> ${(rec || []).length ? 'published sample available' : 'no current independently documented sample published'}.</p>`;
    const releases = Array.isArray(ledger.releases) ? ledger.releases.slice().sort((a, b) => String(a.released_at).localeCompare(String(b.released_at))) : [];
    const first = releases[0], latest = releases[releases.length - 1];
    const changes = q.last_30_days_disclosed_changes || {};
    if (latest) {
      const eventDelta = first ? Number(latest.canonical_events || 0) - Number(first.canonical_events || 0) : 0;
      const reportDelta = first ? Number(latest.source_reports || 0) - Number(first.source_reports || 0) : 0;
      $('alt-health-release-report').innerHTML = `<p><b>Current public release:</b> ${esc(latest.plugin_version || '—')} · dataset revision ${Number(latest.dataset_revision || 0).toLocaleString()} · released ${esc(fmt(latest.released_at))}.</p><p><b>Ledger window:</b> ${first ? `${esc(fmt(first.released_at))} to ${esc(fmt(latest.released_at))}` : 'latest snapshot only'} · net canonical events ${eventDelta >= 0 ? '+' : ''}${eventDelta.toLocaleString()} · net retained reports ${reportDelta >= 0 ? '+' : ''}${reportDelta.toLocaleString()}. This is net change, not gross additions.</p><p><b>Disclosed actions, rolling 30 days:</b> ${Number(changes.corrected || 0).toLocaleString()} corrected · ${Number(changes.removed || 0).toLocaleString()} removed · ${Number(changes.merged || 0).toLocaleString()} merged · ${Number(changes.reclassified || 0).toLocaleString()} reclassified · ${Number(changes.enriched || 0).toLocaleString()} enriched.</p><p><b>Coverage status now:</b> ${degraded ? `${degraded} source${degraded === 1 ? ' is' : 's are'} visibly degraded; see Collector operations above.` : 'No source is currently marked degraded.'}</p>`;
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
