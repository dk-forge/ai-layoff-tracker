"""Generate the methodology page's cross-jurisdiction comparability table.

WARN thresholds vary by US state and filing regimes vary by country (WARN vs
SEC vs ERM vs press-only), so a reader comparing a Texas total with a France
total is comparing two different definitions of "a record". This generator
derives a per-jurisdiction "what qualifies as a record here" table FROM THE
COLLECTORS' OWN CONFIGS and emits a static PHP partial, so the public table
can never drift from what the code actually ingests.

Derivation rules (guarded by tests/test_jurisdiction_table.py):
- Covered US jurisdictions come from the three real state lists the WARN
  importer sweeps (sources/warn.py ALL_STATES, warn_custom.CUSTOM_STATES,
  warn_new_states.NEW_CUSTOM_STATES), parsed from the source, never typed.
- The 60-day federal notice period comes from
  warn_transparency_evidence.STATUTORY_NOTICE_DAYS.
- The ERM inclusion threshold and history floor are parsed out of
  erm_import.py's own docstring/constants.
- Where a jurisdiction's statutory threshold is NOT encoded anywhere in this
  repo (per-state mini-WARN thresholds, Quebec, Mazowieckie), the table says
  UNKNOWN in plain words instead of inventing a number.

Re-run after collector changes:

    python3 generate_jurisdiction_table.py
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from warn_transparency_evidence import STATUTORY_NOTICE_DAYS  # noqa: E402

OUT = (HERE.parent / "wordpress-plugin" / "ai-layoff-tracker" / "templates"
       / "partials" / "jurisdiction-table.php")

STATE_NAMES = {
    "AK": "Alaska", "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DC": "District of Columbia", "DE": "Delaware", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "IA": "Iowa", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "MA": "Massachusetts", "MD": "Maryland", "ME": "Maine",
    "MI": "Michigan", "MN": "Minnesota", "MO": "Missouri", "MS": "Mississippi",
    "MT": "Montana", "NC": "North Carolina", "ND": "North Dakota",
    "NE": "Nebraska", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NV": "Nevada", "NY": "New York", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VA": "Virginia",
    "VT": "Vermont", "WA": "Washington", "WI": "Wisconsin",
    "WV": "West Virginia", "WY": "Wyoming",
}


def _codes_in_block(source_text, name):
    """Two-letter codes in the module-level `NAME = [...]` / `{...}` literal.

    Read via the AST, not a regex: the list literals carry comments containing
    brackets (e.g. `table[0]`), which silently truncated a lazy regex match
    and under-reported coverage by an entire state list.
    """
    import ast
    for node in ast.parse(source_text).body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if name not in targets:
            continue
        if isinstance(node.value, ast.Dict):
            elts = node.value.keys
        elif isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
            elts = node.value.elts
        else:
            break
        codes = [e.value for e in elts
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)
                 and re.fullmatch(r"[A-Z]{2}", e.value)]
        if not codes:
            raise SystemExit(f"{name} parsed to zero jurisdictions; the "
                             "literal moved and the parser must follow it")
        return codes
    raise SystemExit(f"could not find {name} in the collector source")


def covered_warn_jurisdictions():
    """Union of the three real state lists the daily WARN sweep runs."""
    codes = set()
    codes.update(_codes_in_block(
        (HERE / "sources" / "warn.py").read_text(), "ALL_STATES"))
    codes.update(_codes_in_block(
        (HERE / "sources" / "warn_custom.py").read_text(), "CUSTOM_STATES"))
    codes.update(_codes_in_block(
        (HERE / "sources" / "warn_new_states.py").read_text(),
        "NEW_CUSTOM_STATES"))
    unknown = codes - set(STATE_NAMES)
    if unknown:
        raise SystemExit(f"unmapped jurisdiction code(s): {sorted(unknown)}")
    return sorted(codes)


def erm_threshold():
    """ERM's inclusion threshold, parsed from erm_import.py's own docstring."""
    text = (HERE / "erm_import.py").read_text()
    m = re.search(r"Inclusion threshold:\s*(.+?)\s+[—-]\s+small events", text)
    if not m:
        raise SystemExit("erm_import.py no longer documents its inclusion "
                         "threshold; update the parser, not the table")
    # Deterministic prose transform of the derived string (no invented facts,
    # and no ">=" glyphs in UI copy).
    t = m.group(1).strip()
    t = t.replace(">=", "at least ").replace("250+", "250 or larger")
    return t


def erm_min_year():
    text = (HERE / "erm_import.py").read_text()
    m = re.search(r'ERM_MIN_DATE.*?"(\d{4})-\d{2}-\d{2}"', text)
    if not m:
        raise SystemExit("erm_import.py MIN_DATE not found")
    return m.group(1)


def edgar_reads_item_205():
    text = (HERE / "sources" / "edgar.py").read_text()
    return '"item 2.05"' in text


def _require(path, phrase):
    """The table may only name a register whose collector still exists."""
    if phrase not in (HERE / path).read_text():
        raise SystemExit(f"{path} no longer mentions '{phrase}'; the "
                         "jurisdiction table would misdescribe it")


def render():
    states = covered_warn_jurisdictions()
    _require("sources/quebec.py", "avis de licenciements collectifs")
    _require("sources/wup_mazowieckie.py", "zwolnienia grupowe")
    if not edgar_reads_item_205():
        raise SystemExit("edgar.py no longer searches Item 2.05; fix the "
                         "SEC row before regenerating")
    state_list = ", ".join(
        "{n} ({c})".format(n=STATE_NAMES[c], c=c) for c in states)
    days = int(STATUTORY_NOTICE_DAYS)
    thr = erm_threshold()
    since = erm_min_year()

    unknown_cell = ("Not encoded in this tracker&rsquo;s collectors: UNKNOWN "
                    "here rather than guessed.")
    rows = [
        (
            "United States (state WARN notices, {n} jurisdictions)".format(
                n=len(states)),
            "Official state WARN registers, swept daily.",
            "An employer&rsquo;s advance written notice filed with the state "
            "under the WARN Act or a state equivalent. Federal baseline: "
            "notice is generally required {d} days ahead for larger single-"
            "site cuts.".format(d=days),
            "The federal statute sets the baseline, but several states run "
            "mini-WARN laws with lower headcount thresholds or longer notice "
            "periods. Per-state statutory thresholds are "
            + unknown_cell
            + ' <details class="alt-more-outlets"><summary>Jurisdictions '
              "swept</summary>{s}</details>".format(s=state_list),
        ),
        (
            "United States (SEC EDGAR)",
            "8-K and 6-K filings from SEC full-text search, twice daily, "
            "including Item 2.05 (costs associated with exit or disposal "
            "activities).",
            "A filing whose text states a workforce reduction; the job count "
            "must appear verbatim in the filing.",
            "No headcount threshold. What triggers a filing is securities-"
            "law materiality and disclosure practice, not a fixed number of "
            "jobs, so small cuts at public companies can be absent.",
        ),
        (
            "European Union + Norway (Eurofound ERM)",
            "Eurofound&rsquo;s European Restructuring Monitor announcement "
            "factsheets, daily, history back to {y}.".format(y=since),
            "A restructuring announcement curated by Eurofound&rsquo;s "
            "national correspondents.",
            "ERM&rsquo;s own inclusion floor: {t}. Smaller layoffs are absent "
            "by design.".format(t=thr),
        ),
        (
            "Quebec, Canada",
            "Monthly collective-dismissal notice lists (avis de "
            "licenciements collectifs) published by the provincial ministry "
            "(MESS).",
            "A collective-dismissal notice the employer must file under "
            "Quebec&rsquo;s Act respecting labour standards.",
            "The statutory headcount threshold is " + unknown_cell,
        ),
        (
            "Mazowieckie, Poland",
            "WUP Warszawa&rsquo;s monthly collective-redundancy register "
            "(zwolnienia grupowe); Poland&rsquo;s other 15 voivodeships "
            "publish no employer-named register and stay news-covered.",
            "An employer-named collective-redundancy notification in the "
            "regional labour office&rsquo;s monthly post.",
            "The statutory threshold is " + unknown_cell,
        ),
        (
            "Everywhere else",
            "Worldwide news monitoring (GDELT 65-language index and Google "
            "News) over an allowlist of named outlets; no government filing "
            "register is read.",
            "A named-outlet report with usable evidence in its text; the "
            "count parses from the source and rumors are excluded.",
            "No filing threshold exists on this path: qualification is "
            "editorial (a citable source), so coverage depends on press "
            "attention, not on a statute.",
        ),
    ]
    body = "\n".join(
        "<tr><th>{j}</th><td>{r}</td><td>{q}</td><td>{t}</td></tr>".format(
            j=j, r=r, q=q, t=t) for j, r, q, t in rows)
    return (
        "<?php if (!defined('ABSPATH')) exit; "
        "// GENERATED by railway/generate_jurisdiction_table.py - do not "
        "hand-edit ?>\n"
        '<div class="alt-health-table-wrap"><table class="alt-basis-table '
        'alt-jurisdiction-table"><thead><tr><th>Jurisdiction</th>'
        "<th>Register we read</th><th>What qualifies as a record here</th>"
        "<th>Filing threshold</th></tr></thead><tbody>\n"
        + body
        + "\n</tbody></table></div>\n"
        "<p class=\"alt-muted\">Because these definitions and thresholds "
        "differ, per-jurisdiction totals document different things and are "
        "not directly comparable with each other. Thresholds shown are the "
        "ones the source itself documents; anything not encoded in the "
        "collectors is marked UNKNOWN rather than filled in.</p>\n")


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render())
    print(f"wrote {OUT}")
