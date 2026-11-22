import assert from "node:assert/strict";
import test from "node:test";
import { filterRecords, jobsByMonth } from "../static_site_assets/tracker.mjs";

const records = [
  { company: "Acme", country: "UK", industry: "Tech", layoff_date: "2026-01-04", ai_explicit: "1", job_count: "20", superset_of: "0" },
  { company: "Acme", country: "US", industry: "Tech", layoff_date: "2026-01-05", ai_explicit: "1", job_count: "5", superset_of: "1" },
  { company: "Other", country: "UK", industry: "Retail", layoff_date: "2026-02-01", ai_explicit: "0", job_count: "40", superset_of: "0" },
];

test("filters combine across dimensions and match any selection within a dimension", () => {
  assert.deepEqual(filterRecords(records, {
    search: "acme", country: ["UK", "US"], industry: ["Tech"], ai: true,
    from: "2026-01-04", to: "2026-01-05",
  }), records.slice(0, 2));
  assert.deepEqual(filterRecords(records, { country: ["UK"], to: "2026-01-31" }), records.slice(0, 1));
});

test("the chart excludes overlapping counts while the table keeps their records", () => {
  assert.equal(filterRecords(records, {}).length, 3);
  assert.deepEqual(jobsByMonth(records), [["2026-01", 20], ["2026-02", 40]]);
});
