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
    reason_backfill: ['Untagged non-WARN records; reason tags only', 'Daily evidence-only', 'Internal', 'Stored-excerpt classification'],
    role_enrichment: ['Role categories from already-stored row text', 'Daily evidence-only', 'Internal', 'Stored-evidence re-read'],
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

  // Each endpoint retries once and degrades to null on failure, so one flaky
  // fetch renders as a visible gap in its own section instead of blanking the
  // entire page (observed live 2026-07-19).
  const safeGet = path => get(path).catch(() => get(path)).catch(() => null);

  // Benchmark race: our cells are live aggregates; Challenger cells come from
  // the stored monthly reconciliation records; layoffs.fyi cells are dated
  // manual snapshots (leads-only policy — no automated pulls without their
  // permission).
  const FYI = { asOf: '2026-07-18', techTotal: 121326, techAI: 95829, history: ['2026-07-18'] };
  const CHAL_STATIC = { asOf: '2026-06 report', techTotal: 139156 };
  // Verified 2026-07-19 from each publisher's own year pages/reports (see
  // docs/QUALITY_ROADMAP_HANDOVER.md). fyi = worldwide tech, began Mar 2020.
  const BENCH_HISTORY = {
    2019: { chal: 592556, chalAI: null, fyi: null },
    2020: { chal: 2304755, chalAI: null, fyi: 80998 },
    2021: { chal: 321970, chalAI: null, fyi: 15823 },
    2022: { chal: 363824, chalAI: null, fyi: 165269 },
    2023: { chal: 721677, chalAI: 4247, fyi: 265660 },
    2024: { chal: 761358, chalAI: 12742, fyi: 152922 },
    2025: { chal: 1206374, chalAI: 54836, fyi: 122606 },
    2026: { chal: null, chalAI: null, fyi: 121326 }, // 2026 Challenger cells fill from the stored YTD records
  };
  function renderBenchMonthly() {
    const body = document.getElementById('alt-bench-monthly');
    if (!body) return;
    const agg = p => fetch(api + 'aggregate?' + p, { headers: { Accept: 'application/json' } }).then(r => r.json()).catch(() => null);
    Promise.all([
      safeGet('benchmarks/challenger'),
      agg('years=2026&country=United%20States&country_basis=employer'),
    ]).then(([chal, usEmp]) => {
      const fmtN = v => (v == null ? '—' : Number(v).toLocaleString('en-US'));
      const pct = (ours, bench) => {
        if (ours == null || !(bench > 0)) return '—';
        const p2 = Math.round(100 * ours / bench);
        const cls = p2 >= 90 ? 'alt-pct-good' : (p2 >= 60 ? 'alt-pct-mid' : 'alt-pct-low');
        return '<span class="' + cls + '">' + p2 + '%</span>';
      };
      const byMonth = {};
      ((usEmp && usEmp.series) || []).forEach(r2 => { byMonth[r2.month] = r2; });
      const recs = (Array.isArray(chal) ? chal : []).filter(r2 => r2.reference_month)
        .sort((a, b) => a.reference_month < b.reference_month ? -1 : 1);
      if (!recs.length) { body.innerHTML = '<tr><td colspan="9">No stored Challenger months yet.</td></tr>'; return; }
      // Running sums: single months are timing-noisy (each tracker books
      // the same event in a different month); the cumulative % is the
      // convergent signal.
      let cChal = 0, cAtr = 0, cChalAi = 0, cAtrAi = 0;
      body.innerHTML = recs.map(r2 => {
        const m = byMonth[r2.reference_month] || {};
        cChal += r2.challenger_total_jobs_month || 0;
        cAtr += m.jobs || 0;
        cChalAi += r2.challenger_ai_jobs_month || 0;
        cAtrAi += m.ai_broad_jobs || 0;
        return '<tr><td><b>' + r2.reference_month + '</b></td>' +
          '<td>' + fmtN(r2.challenger_total_jobs_month) + '</td><td>' + fmtN(m.jobs) + '</td><td>' + pct(m.jobs, r2.challenger_total_jobs_month) + '</td><td>' + pct(cAtr, cChal) + '</td>' +
          '<td>' + fmtN(r2.challenger_ai_jobs_month) + '</td><td>' + fmtN(m.ai_broad_jobs) + '</td><td>' + pct(m.ai_broad_jobs, r2.challenger_ai_jobs_month) + '</td><td>' + pct(cAtrAi, cChalAi) + '</td></tr>';
      }).join('');
    }).catch(() => {
      body.innerHTML = '<tr><td colspan="7">Monthly trend could not load this time — refresh to retry.</td></tr>';
    });
  }
  renderBenchMonthly();

  function renderBenchHistory() {
    const body = document.getElementById('alt-bench-history');
    if (!body) return;
    const years = Object.keys(BENCH_HISTORY).sort().reverse();
    const agg = p => fetch(api + 'aggregate?' + p, { headers: { Accept: 'application/json' } }).then(r => r.json()).catch(() => null);
    Promise.all(years.map(y => Promise.all([
      agg('years=' + y + '&country=United%20States'),
      agg('years=' + y + '&industry=Technology'),
    ]))).then(rows => {
      const fmtN = v => (v == null ? '—' : Number(v).toLocaleString('en-US'));
      const pctBadge = (ours, bench) => {
        if (ours == null || !(bench > 0)) return '—';
        const p2 = Math.round(100 * ours / bench);
        const cls = p2 >= 90 ? 'alt-pct-good' : (p2 >= 60 ? 'alt-pct-mid' : 'alt-pct-low');
        return '<span class="' + cls + '">' + p2 + '%</span>';
      };
      body.innerHTML = years.map((y, i) => {
        const h = BENCH_HISTORY[y];
        const us = rows[i][0] && rows[i][0].totals ? rows[i][0].totals : {};
        const tech = rows[i][1] && rows[i][1].totals ? rows[i][1].totals : {};
        return '<tr><td><b>' + y + '</b></td>' +
          '<td>' + fmtN(h.chal) + '</td><td>' + fmtN(us.jobs) + '</td><td>' + pctBadge(us.jobs, h.chal) + '</td>' +
          '<td>' + fmtN(h.chalAI) + '</td><td>' + fmtN(us.ai_broad_jobs) + '</td><td>' + pctBadge(us.ai_broad_jobs, h.chalAI) + '</td>' +
          '<td>' + fmtN(h.fyi) + '</td><td>' + fmtN(tech.jobs) + '</td><td>' + pctBadge(tech.jobs, h.fyi) + '</td></tr>';
      }).join('');
      // Fill 2026 Challenger cells from the stored reconciliation records
      safeGet('benchmarks/challenger').then(chal => {
        const latest = Array.isArray(chal) && chal.length ? chal[0] : null;
        if (!latest) return;
        const firstRow = body.querySelector('tr');
        if (!firstRow) return;
        const cells = firstRow.querySelectorAll('td');
        if (cells.length >= 7) {
          const pctInto = (cell, oursTxt, bench) => {
            const ours = Number(String(oursTxt).replace(/[^0-9]/g, ''));
            if (!ours || !(bench > 0)) return;
            const p2 = Math.round(100 * ours / bench);
            const cls = p2 >= 90 ? 'alt-pct-good' : (p2 >= 60 ? 'alt-pct-mid' : 'alt-pct-low');
            cell.innerHTML = '<span class="' + cls + '">' + p2 + '%</span>';
          };
          if (latest.challenger_total_jobs_ytd) {
            cells[1].textContent = Number(latest.challenger_total_jobs_ytd).toLocaleString('en-US') + ' YTD';
            pctInto(cells[3], cells[2].textContent, latest.challenger_total_jobs_ytd);
          }
          if (latest.challenger_ai_jobs_ytd) {
            cells[4].textContent = Number(latest.challenger_ai_jobs_ytd).toLocaleString('en-US') + ' YTD';
            pctInto(cells[6], cells[5].textContent, latest.challenger_ai_jobs_ytd);
          }
        }
      });
    }).catch(() => {
      body.innerHTML = '<tr><td colspan="7">Year-by-year comparison could not load this time — refresh to retry.</td></tr>';
    });
  }
  renderBenchHistory();
  function renderBenchRace() {
    const body = document.getElementById('alt-bench-race');
    if (!body) return;
    const agg = p => fetch(api + 'aggregate?' + p, { headers: { Accept: 'application/json' } }).then(r => r.json()).catch(() => null);
    Promise.all([
      agg('years=2026&country=United%20States'),
      agg('years=2026&industry=Technology'),
      agg('years=2026'),
      safeGet('benchmarks/challenger'),
      safeGet('source-runs?days=7&per_page=100'),
      // Employer basis: evidenced/curated US domicile, plus blank-domicile
      // US-job-location fallback — the Challenger-comparable scope, which
      // includes US-HQ multi-country events the plain US filter cannot see.
      agg('years=2026&country=United%20States&country_basis=employer'),
    ]).then(([us, tech, world, chal, runsResp, usEmp]) => {
      const fmtN = v => (v == null ? '—' : Number(v).toLocaleString('en-US'));
      const latest = Array.isArray(chal) && chal.length ? chal[0] : {};
      const chalTotalYtd = latest.challenger_total_jobs_ytd;
      const chalAiYtd = latest.challenger_ai_jobs_ytd;
      const chalTotalMo = latest.challenger_total_jobs_month;
      const chalAiMo = latest.challenger_ai_jobs_month;
      const refMonth = latest.reference_month || '';
      // Challenger's YTD runs through their reference month; comparing our
      // FULL-year totals (July + future-dated plans included) against it
      // overstated us. Sum our monthly series through that month instead.
      const throughRef = (aggResp, field) => {
        if (!aggResp || !aggResp.series) return aggResp && aggResp.totals ? aggResp.totals[field] : null;
        if (!refMonth) return aggResp.totals ? aggResp.totals[field] : null;
        let sum = 0;
        aggResp.series.forEach(r2 => { if (r2.month <= refMonth) sum += r2[field] || 0; });
        return sum;
      };
      const usJobs = throughRef(us, 'jobs');
      const usBroad = throughRef(us, 'ai_broad_jobs');
      const usEmpJobs = throughRef(usEmp, 'jobs');
      const usEmpBroad = throughRef(usEmp, 'ai_broad_jobs');
      const techJobs = tech && tech.totals ? tech.totals.jobs : null;
      const techBroad = tech && tech.totals ? tech.totals.ai_broad_jobs : null;
      const worldJobs = world && world.totals ? world.totals.jobs : null;
      const worldBroad = world && world.totals ? world.totals.ai_broad_jobs : null;
      const pct = (ours, bench) => {
        if (ours == null || !(bench > 0)) return '—';
        const p2 = Math.round(100 * ours / bench);
        const cls = p2 >= 90 ? 'alt-pct-good' : (p2 >= 60 ? 'alt-pct-mid' : 'alt-pct-low');
        return '<span class="' + cls + '">' + p2 + '%</span>';
      };
      const row = (label, c, f, a, vs) => '<tr><td>' + label + '</td><td>' + c + '</td><td>' + f + '</td><td><b>' + a + '</b></td><td>' + vs + '</td></tr>';
      const group = label => '<tr class="alt-bench-group"><th colspan="5">' + label + '</th></tr>';
      body.innerHTML =
        group('ALL CUTS — United States') +
        row('By US employer, through ' + (refMonth || 'YTD') + ' (Challenger-comparable)', fmtN(chalTotalYtd), '—', fmtN(usEmpJobs), pct(usEmpJobs, chalTotalYtd)) +
        row('By US job location, through ' + (refMonth || 'YTD'), fmtN(chalTotalYtd), '—', fmtN(usJobs), pct(usJobs, chalTotalYtd)) +
        row('Latest Challenger report month' + (refMonth ? ' (' + refMonth + ')' : ''), fmtN(chalTotalMo), '—', '—', '—') +
        group('AI CUTS — United States') +
        row('By US employer, broad, through ' + (refMonth || 'YTD') + ' (Challenger-comparable)', fmtN(chalAiYtd), '—', fmtN(usEmpBroad), pct(usEmpBroad, chalAiYtd)) +
        row('By US job location, broad, through ' + (refMonth || 'YTD'), fmtN(chalAiYtd), '—', fmtN(usBroad), pct(usBroad, chalAiYtd)) +
        row('Latest Challenger report month' + (refMonth ? ' (' + refMonth + ')' : ''), fmtN(chalAiMo), '—', '—', '—') +
        group('TECH — worldwide (layoffs.fyi-comparable · fyi as of ' + FYI.asOf + ')') +
        row('Tech cuts (Challenger sector col, ' + CHAL_STATIC.asOf + ')', fmtN(CHAL_STATIC.techTotal), fmtN(FYI.techTotal), fmtN(techJobs), pct(techJobs, FYI.techTotal)) +
        row('Tech AI cuts (broad)', '—', fmtN(FYI.techAI), fmtN(techBroad), pct(techBroad, FYI.techAI)) +
        group('WORLDWIDE — ATR only (no benchmark measures this)') +
        row('All industries, all countries', '—', '—', fmtN(worldJobs), '') +
        row('AI cuts, broad', '—', '—', fmtN(worldBroad), '');
      // Per-column update history: last 3 timestamps each, all live.
      const fmtT = iso => { try { return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch (e) { return iso; } };
      const chalTimes = (Array.isArray(chal) ? chal : [])
        .map(r2 => r2.recorded_at).filter(Boolean)
        .sort().reverse().map(fmtT)
        .filter((v, i2, a) => a.indexOf(v) === i2).slice(0, 3);
      const atrTimes = ((runsResp && runsResp.runs) || [])
        .filter(r2 => r2.status === 'ok' && r2.attempted_at)
        .map(r2 => r2.attempted_at).sort().reverse().slice(0, 3).map(fmtT);
      const upd = document.getElementById('alt-bench-race-updated');
      if (upd) upd.innerHTML =
        '<b>Column update history (last 3):</b> ' +
        'ATR data pulls: ' + (atrTimes.join(' · ') || 'none in 7 days') +
        ' &nbsp;|&nbsp; Challenger stored reports: ' + (chalTimes.join(' · ') || 'none yet') +
        ' &nbsp;|&nbsp; layoffs.fyi manual snapshots: ' + FYI.history.join(' · ');
    }).catch(() => {
      body.innerHTML = '<tr><td colspan="5">Benchmark comparison could not load this time — refresh to retry.</td></tr>';
    });
  }
  renderBenchRace();
  // Ops page left open stays current: benchmark tables re-render every
  // 5 minutes, and a hidden tab reloads fully every 10 so every section
  // (runs, summary, ledger) refreshes without anyone touching it.
  setInterval(function () { renderBenchRace(); renderBenchMonthly(); renderBenchHistory(); }, 300000);
  setInterval(function () { if (document.hidden) location.reload(); }, 600000);
  Promise.all(['quality-status', 'integrity-status', 'status', 'review-queue', 'benchmarks/challenger', 'benchmarks/recall', 'dataset-releases'].map(safeGet)).then(([q, i, s, r, c, rec, ledger]) => {
    q = q || { source_health: {}, workstreams: [], last_30_days_disclosed_changes: {} };
    i = i || { canonical_events: 0, source_reports: 0, source_report_hashes_remaining: 0, metadata_completeness: {}, canonical_events_without_linked_source_reports: 0 };
    s = s || {}; r = r || {}; rec = rec || []; ledger = ledger || {};
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
