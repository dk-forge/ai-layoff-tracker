/* Standalone iframe widget: state/national aggregate only, no publisher data collection. */
(() => {
  const config = window.altWidgetData;
  const value = document.getElementById('alt-widget-value');
  const label = document.getElementById('alt-widget-label');
  if (!config || !value || !label) return;
  const qs = new URLSearchParams(config.params || {}).toString();
  fetch(config.apiUrl + 'aggregate?' + qs, { credentials: 'same-origin' })
    .then(response => response.ok ? response.json() : Promise.reject(new Error('HTTP ' + response.status)))
    .then(data => {
      const totals = data && data.totals ? data.totals : {};
      const announced = Number(totals.announced_jobs || 0);
      const verified = Math.max(0, Number(totals.jobs || 0) - announced);
      const entries = Math.max(0, Number(totals.entries || 0) - Number(totals.announced_entries || 0));
      value.textContent = verified.toLocaleString('en-US');
      label.textContent = entries.toLocaleString('en-US') + ' verified source-linked event' + (entries === 1 ? '' : 's');
    })
    .catch(() => {
      value.textContent = 'Unavailable';
      label.textContent = 'Live data could not be loaded';
    });
})();
