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

async function start(section) {
  const response = await fetch(section.dataset.tracker);
  if (!response.ok) throw new Error("Tracker data unavailable");
  const data = await response.json();
  if (data.schema !== 1 || !Array.isArray(data.records)) throw new Error("Invalid tracker data");
  const records = [...data.records].sort((a, b) =>
    (b.layoff_date || "").localeCompare(a.layoff_date || ""));
  const form = section.querySelector("form");
  const status = section.querySelector("[role=status]");
  const filters = [...form.querySelectorAll("select")];
  for (const select of filters) {
    const values = [...new Set(records.map((row) => row[select.name]).filter(Boolean))].sort();
    for (const value of values) select.add(new Option(value, value));
  }
  const more = section.querySelector("[data-more]");
  let limit = 50;
  const update = () => {
    const input = new FormData(form);
    const query = Object.fromEntries(input);
    for (const select of filters) query[select.name] = input.getAll(select.name);
    const filtered = filterRecords(records, query);
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
