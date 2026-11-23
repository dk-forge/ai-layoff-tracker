export function filterRecords(records, filters) {
  const search = (filters.search || "").trim().toLowerCase();
  return records.filter((row) =>
    (!search || row.company.toLowerCase().includes(search)) &&
    ["country", "industry", "state", "source_type"].every((key) =>
      !filters[key]?.length || filters[key].includes(row[key])) &&
    (!filters.ai || Number(row.ai_explicit) === 1) &&
    (!filters.from || (row.layoff_date && row.layoff_date >= filters.from)) &&
    (!filters.to || (row.layoff_date && row.layoff_date <= filters.to))
  );
}

export function jobsByMonth(records) {
  const totals = new Map();
  for (const row of records) {
    if (Number(row.superset_of) !== 0 || !row.layoff_date) continue;
    const month = row.layoff_date.slice(0, 7);
    totals.set(month, (totals.get(month) || 0) + Number(row.job_count));
  }
  return [...totals].sort(([left], [right]) => left.localeCompare(right));
}

const attribution = "AI Layoff Tracker - asktherecruiter.com";
const exportFields = [
  "company", "job_count", "layoff_date", "announcement_date", "industry", "country",
  "state", "source_type", "verification_level", "source_url", "ai_explicit", "superset_of",
];

function csvCell(value) {
  const text = String(value ?? "");
  const safe = /^(?:[\t\r\n]|\s*[=+@-])/.test(text) ? "'" + text : text;
  return '"' + safe.replaceAll('"', '""') + '"';
}

export function trackerExport(format, records, exportedAt) {
  if (format === "json") {
    return JSON.stringify({
      source: attribution,
      license: "Free to use with attribution to asktherecruiter.com.",
      exported_at: exportedAt, data: records, total_records: records.length,
    });
  }
  const lines = [[...exportFields, "exported_at", "source_attribution"].join(",")];
  for (const row of records) {
    lines.push([...exportFields.map((key) => row[key]), exportedAt, attribution].map(csvCell).join(","));
  }
  return "\uFEFF" + lines.join("\r\n") + "\r\n";
}

function download(format, records, exportedAt) {
  const type = format === "csv" ? "text/csv;charset=utf-8" : "application/json";
  const url = URL.createObjectURL(new Blob([trackerExport(format, records, exportedAt)], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `ai-layoff-tracker.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderChart(root, records) {
  const months = jobsByMonth(records).slice(-24);
  const max = Math.max(1, ...months.map(([, total]) => total));
  root.replaceChildren(...months.map(([month, total]) => {
    const item = document.createElement("li");
    const bar = document.createElement("meter");
    bar.max = max;
    bar.value = total;
    bar.setAttribute("aria-hidden", "true");
    item.append(`${month} · ${total.toLocaleString()} jobs `, bar);
    return item;
  }));
}

function renderRows(root, records) {
  root.replaceChildren(...records.map((record) => {
    const row = document.createElement("tr");
    for (const key of ["company", "layoff_date", "country", "job_count"]) {
      row.insertCell().textContent = record[key] ?? "";
    }
    const sourceCell = row.insertCell();
    if (/^https?:\/\//i.test(record.source_url || "")) {
      const link = document.createElement("a");
      link.href = record.source_url;
      link.textContent = "Source";
      sourceCell.append(link);
    }
    return row;
  }));
}

export function embedFilters(search) {
  const params = new URLSearchParams(search);
  const value = (key) => params.get(key) || "";
  const list = (key) => value(key).split(",").map((item) => item.trim()).filter(Boolean);
  return {
    search: value("company"),
    country: list("country"), industry: list("industry"), state: list("state"),
    source_type: list("sources"), from: value("from"), to: value("to"), ai: value("ai") === "1",
  };
}

function renderEmbed(section, data, records) {
  const params = new URLSearchParams(window.location.search);
  const filtered = filterRecords(records, embedFilters(params));
  if (params.get("view") === "chart") {
    section.querySelector("[data-embed-chart]").hidden = false;
    renderChart(section.querySelector("[data-chart]"), filtered);
  } else {
    section.querySelector("[data-embed-widget]").hidden = false;
    renderRows(section.querySelector("tbody"), filtered.slice(0, 10));
  }
  section.querySelector("[role=status]").textContent =
    `${filtered.length.toLocaleString()} matching records. Backup captured ${data.exported_at.slice(0, 10)} UTC.`;
}

async function start(section) {
  const response = await fetch(section.dataset.tracker);
  if (!response.ok) throw new Error("Tracker data unavailable");
  const data = await response.json();
  if (data.schema !== 1 || !Array.isArray(data.chunks) || !data.chunks.length) {
    throw new Error("Invalid tracker data");
  }
  const base = new URL(section.dataset.tracker, document.baseURI);
  const chunks = await Promise.all(data.chunks.map(async (name) => {
    if (!/^tracker-records-[0-9]+\.json$/.test(name)) throw new Error("Invalid tracker chunk");
    const chunk = await fetch(new URL(name, base));
    if (!chunk.ok) throw new Error("Tracker chunk unavailable");
    const rows = await chunk.json();
    if (!Array.isArray(rows)) throw new Error("Invalid tracker chunk");
    return rows;
  }));
  const records = chunks.flat().sort((a, b) =>
    (b.layoff_date || "").localeCompare(a.layoff_date || ""));
  if (section.hasAttribute("data-tracker-embed")) {
    renderEmbed(section, data, records);
    return;
  }
  const form = section.querySelector("form");
  const status = section.querySelector("[role=status]");
  const filters = [...form.querySelectorAll("select")];
  for (const select of filters) {
    const values = [...new Set(records.map((row) => row[select.name]).filter(Boolean))].sort();
    for (const value of values) select.add(new Option(value, value));
  }
  const more = section.querySelector("[data-more]");
  let limit = 50;
  let filtered = [];
  for (const button of form.querySelectorAll("[data-export]")) {
    button.addEventListener("click", () => download(button.dataset.export, filtered, data.exported_at));
  }
  const update = () => {
    const input = new FormData(form);
    const query = Object.fromEntries(input);
    for (const select of filters) query[select.name] = input.getAll(select.name);
    filtered = filterRecords(records, query);
    renderRows(section.querySelector("tbody"), filtered.slice(0, limit));
    renderChart(section.querySelector("[data-chart]"), filtered);
    more.hidden = filtered.length <= limit;
    status.textContent = `Showing ${Math.min(limit, filtered.length).toLocaleString()} of ${filtered.length.toLocaleString()} matching records. Backup captured ${data.exported_at.slice(0, 10)} UTC.`;
  };
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    limit = 50;
    update();
  });
  more.addEventListener("click", () => {
    limit += 50;
    update();
  });
  update();
  form.hidden = false;
}

if (typeof document !== "undefined") {
  for (const section of document.querySelectorAll("[data-tracker]")) {
    start(section).catch(() => {
      section.querySelector("[role=status]").textContent = "Tracker data could not load.";
    });
  }
}
