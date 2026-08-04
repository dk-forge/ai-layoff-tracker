"""Generate the health page's per-country source table from the code itself.

Parses TRUSTED_DOMAINS entries in sources/gdelt.py (domain + country comment)
and emits a static PHP partial, so the public table can never drift from what
the collector actually scans. Re-run after allowlist changes:

    python3 generate_country_table.py
"""
import re
from collections import OrderedDict
from pathlib import Path

SRC = Path(__file__).parent / "sources" / "gdelt.py"
OUT = Path(__file__).parent.parent / "wordpress-plugin" / "ai-layoff-tracker" / "templates" / "partials" / "country-sources-table.php"

OFFICIAL = {
    # No jurisdiction count here: this file is generated offline and cannot read
    # the live data, so a number typed in would be a fourth, permanently stale
    # answer to a question alt_coverage_counts() already owns.
    "United States": "SEC EDGAR 8-K/6-K incl. Item 2.05 (2×/day) · official state WARN registers (daily)",
    "European Union": "Eurofound ERM restructuring monitor (daily)",
    "United Kingdom": "Companies House identity checks (on demand); LSE RNS pending licence",
    "Japan": "EDINET discovery probe, 2×/day (list-only)",
    "South Korea": "OpenDART discovery probe, 2×/day (list-only)",
    "Canada": "Quebec collective-dismissal lists: candidate (courtesy notice pending)",
    "Brazil": "CVM filings index: discovery client built, pending promotion",
    "Denmark": "Jobindsats varsel API: key application pending",
}

# Countries whose news scanning ALSO rides Eurofound ERM coverage.
EU = {"Germany", "France", "Spain", "Italy", "Netherlands", "Belgium", "Sweden",
      "Denmark", "Norway", "Finland", "Ireland", "Poland", "Austria", "Portugal",
      "Greece", "Czech Republic", "Czechia", "Hungary", "Romania", "Bulgaria",
      "Croatia", "Slovakia", "Slovenia", "Lithuania", "Latvia", "Estonia",
      "Luxembourg", "Malta", "Cyprus"}

COUNTRY_FIXES = {
    # Canonical names so the public table is consistent (and so an audit script
    # searching for "United Kingdom" actually finds it).
    "UK": "United Kingdom", "UAE": "United Arab Emirates", "USA": "United States",
    "Cote d'Ivoire": "Côte d'Ivoire", "DR Congo": "DR Congo",
    "Congo-Brazzaville": "Congo (Brazzaville)", "Central African Rep.": "Central African Republic",
}

# --- What is allowed to count as a country -------------------------------
# "We scan N countries" is a claim about geographic reach, so it has to be
# derived from real countries only. The parser reads gdelt.py's OWN comments,
# and the US metro block labels its lines with the outlet or the state
# ("# Tampa Bay Times", "# Oklahoma - Tulsa World"). Those became country ROWS
# and the public figure read 203 when the honest answer was 180: 21 US metro
# outlets and US states plus 2 grouping rows, an 11 percent overcount on a
# number journalists quote. The count is now whitelisted against real country
# and territory names; anything else is folded into a row that is explicitly
# not a country and is never counted. Direction of failure matters: an
# unrecognised name UNDERstates reach rather than inflating it, and the
# generator prints it so the omission is visible rather than silent.
GROUPING_ROWS = {"EU-wide", "European Union", "Global & multi-region English press"}

US_STATE_NAMES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
}

# US metro / local outlet labels gdelt.py uses as its inline comment. These are
# outlets, not places, so they fold into the United States row.
US_LOCAL_LABELS = {
    "APM Marketplace", "Arizona Republic", "Atlanta Journal-Constitution",
    "Austin", "Boston Globe Media", "Charlotte", "Columbus Dispatch",
    "Greenfield Recorder", "Las Vegas R-J", "Nashville",
    "Philadelphia Inquirer", "Pittsburgh Post-Gazette", "Raleigh NC",
    "San Diego", "St. Louis Post-Dispatch", "Tampa Bay Times", "The Oregonian",
}

# Real countries and inhabited territories. ISO 3166-1 common English names,
# plus the territory names the allowlist actually uses. "Georgia" is the
# country; the US state of the same name is caught earlier, in the US metro
# block, because gdelt.py never labels a line with a bare US state that also
# names a country.
COUNTRIES = frozenset({
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola",
    "Antigua & Barbuda", "Antigua and Barbuda", "Argentina", "Armenia",
    "Aruba", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain",
    "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin",
    "Bermuda", "Bhutan", "Bolivia", "Bosnia", "Bosnia and Herzegovina",
    "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi",
    "Cambodia", "Cameroon", "Canada", "Cape Verde", "Cayman Islands",
    "Central African Republic", "Chad", "Chile", "China", "Colombia",
    "Comoros", "Congo (Brazzaville)", "Cook Islands", "Costa Rica", "Croatia",
    "Cuba", "Curaçao", "Cyprus", "Czechia", "Czech Republic", "Côte d'Ivoire",
    "DR Congo", "Denmark", "Djibouti", "Dominica", "Dominican Republic",
    "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea",
    "Estonia", "Eswatini", "Ethiopia", "Faroe Islands", "Fiji", "Finland",
    "France", "French Polynesia", "Gabon", "Gambia", "Georgia", "Germany",
    "Ghana", "Gibraltar", "Greece", "Greenland", "Grenada", "Guam",
    "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras",
    "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq",
    "Ireland", "Isle of Man", "Israel", "Italy", "Jamaica", "Japan", "Jersey",
    "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait",
    "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya",
    "Liechtenstein", "Lithuania", "Luxembourg", "Macau", "Madagascar",
    "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands",
    "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco",
    "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
    "Nauru", "Nepal", "Netherlands", "New Caledonia", "New Zealand",
    "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia",
    "Northern Mariana Islands", "Norway", "Oman", "Pakistan", "Palau",
    "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru",
    "Philippines", "Poland", "Portugal", "Puerto Rico", "Qatar", "Romania",
    "Russia", "Rwanda", "Samoa", "San Marino", "Saudi Arabia", "Senegal",
    "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia",
    "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea",
    "South Sudan", "Spain", "Sri Lanka", "St. Lucia", "Saint Lucia", "Sudan",
    "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan",
    "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga",
    "Trinidad & Tobago", "Trinidad and Tobago", "Tunisia", "Turkey",
    "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu",
    "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
    # Two-country labels the allowlist keeps deliberately paired.
    "Russia / Ukraine", "Mexico / Argentina",
})

CATCH_ALL = "Global & multi-region English press"

# Labels the parser could not place. Filled by parse() and printed by the
# generator, so a genuine country arriving under an unfamiliar spelling is
# noticed instead of quietly vanishing into the multi-region bucket.
UNRECOGNISED = {}


def classify(country):
    """Return (row_label, counts_as_country).

    A label that is not a real country never reaches the public country count.
    US states and US metro outlets fold into the United States row, because
    that is what they are; anything else unrecognised falls into the existing
    multi-region bucket and is reported by the generator.
    """
    if country in COUNTRIES:
        return country, True
    if country in GROUPING_ROWS:
        return country, False
    if country in US_STATE_NAMES or country in US_LOCAL_LABELS:
        return "United States", True
    return CATCH_ALL, False


def parse():
    countries = OrderedDict()
    pending_comment = ""
    text = SRC.read_text()
    body = text.split("TRUSTED_DOMAINS = {", 1)[1].split("\n}", 1)[0]
    for line in body.splitlines():
        # gdelt.py uses TWO comment styles and the old parser only understood
        # one, so every domain on a line without its own trailing comment was
        # silently dropped: 106 of 705 outlets (15%) - including AP, BBC, Axios
        # and Al Jazeera - were missing from the public table, making the page
        # UNDER-report our real coverage. Track the current country instead:
        #   A)  "a.com", "b.com",   # Country      (inline trailing comment)
        #   B)  # Country
        #       "a.com", "b.com",                  (comment above the block)
        standalone = re.match(r'\s*#\s*(.+)$', line)
        if standalone:
            pending_comment = standalone.group(1).strip()
            continue
        m = re.match(r'\s*((?:"[a-z0-9.\-]+",\s*)+)#\s*(.+)$', line)
        if m:
            domains = re.findall(r'"([a-z0-9.\-]+)"', m.group(1))
            comment = m.group(2).strip()
            pending_comment = comment
        else:
            m2 = re.match(r'\s*((?:"[a-z0-9.\-]+",?\s*)+)$', line)
            if not m2 or not pending_comment:
                continue
            domains = re.findall(r'"([a-z0-9.\-]+)"', m2.group(1))
            comment = pending_comment
        # Worldwide-block style: "Country — Outlet (note)"; legacy style: "Country"
        country = re.split(r"\s+[—-]\s+", comment, maxsplit=1)[0].strip()
        country = re.sub(r"\s*\(.*\)$", "", country)
        stop = {"npr", "network", "daily", "dailies", "news", "business", "wire",
                "wires", "trade", "tv", "press", "journal", "radio", "regional",
                "national", "general", "tech", "finance", "metro", "coverage",
                "outlets", "more", "dupes", "harmless", "english", "paywalled",
                "acbj", "sibling", "banner", "tribune", "gulf", "nordics", "crain's"}
        words = country.split()
        if (not re.match(r"^[A-ZÀ-Ü]", country) or len(words) > 3
                or any(w.strip("().,'&—-").lower() in stop for w in words)):
            country = CATCH_ALL
        if "/" in country and country not in ("Russia / Ukraine", "Mexico / Argentina"):
            country = country.split("/")[0].strip()
        country = COUNTRY_FIXES.get(country, country)
        for splitter in (" / ",):
            if splitter in country:
                country = country.split(splitter)[0].strip()
        label, is_country = classify(country)
        if not is_country and label == CATCH_ALL and country not in GROUPING_ROWS:
            UNRECOGNISED.setdefault(country, []).extend(domains)
        countries.setdefault(label, [])
        for d in domains:
            if d not in countries[label]:
                countries[label].append(d)
    return countries


def country_count(countries):
    """How many rows in the table are actually countries or territories."""
    return sum(1 for c in countries if classify(c)[1])


def render(countries):
    rows = []
    for country in sorted(countries, key=lambda c: (c == "United States & global English press", c)):
        outlets = countries[country]
        official = OFFICIAL.get(country, "")
        if not official and country in EU:
            official = "Eurofound ERM (EU-wide, daily)"
        if not official:
            official = "News monitoring only; no public government filing register"
        def _a(o):
            return '<a href="https://{d}" target="_blank" rel="noopener">{d}</a>'.format(d=o)
        linked = ", ".join(_a(o) for o in outlets[:14])
        # The overflow used to render as a bare "+N more", which is not
        # verifiable: a journalist checking "do you scan Al Jazeera?" got a
        # number, not an answer, and an answer engine had nothing to index.
        # Keep the visible list short, but put EVERY remaining outlet in the
        # HTML inside a collapsed <details> so the page is complete and
        # crawlable without becoming unreadable.
        rest = outlets[14:]
        if rest:
            linked += (' <details class="alt-more-outlets"><summary>+{k} more</summary>{r}</details>'
                       .format(k=len(rest), r=", ".join(_a(o) for o in rest)))
        rows.append(
            "<tr><th>{c}</th><td>{o}</td><td>{n}</td>"
            "<td>Active &middot; 2&times;/day (13:00 &amp; 22:00 UTC)</td></tr>".format(
                c=country, o=official, n=linked))
    return (
        "<?php if (!defined('ABSPATH')) exit; // GENERATED by railway/generate_country_table.py - do not hand-edit ?>\n"
        "<details class=\"alt-health-section\" open><summary><b>Every country and every outlet we scan ({n} countries, {d} outlets)</b>, generated from the collector's own allowlist</summary>"
        "<div class=\"alt-health-table-wrap\"><table class=\"alt-sortable\"><thead><tr><th>Country</th><th>Official sources</th><th data-nosort>News outlets scanned (via GDELT Translingual + Google News)</th><th>News scan status</th></tr></thead><tbody>\n"
        .format(n=country_count(countries), d=sum(len(v) for v in countries.values()))
        + "\n".join(rows)
        + "\n</tbody></table></div><p>The count is countries and territories only: the two grouping rows (EU-wide, multi-region English press) are listed but not counted, and US metro outlets are part of the United States row rather than places of their own.</p>"
        + "<p>Outlet scanning is allowlist-only: articles surface through GDELT's 65-language index and Google News; sites are never crawled directly. Rotating country/state/industry queries sweep the full matrix every ~6&ndash;9 days on top of the broad twice-daily pull.</p></details>\n")


if __name__ == "__main__":
    countries = parse()
    n_countries = country_count(countries)
    n_outlets = sum(len(v) for v in countries.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(countries))
    # Companion scope partial: the on-page "we monitor N outlets in N
    # countries" claim regenerates with the allowlist, so it can never drift.
    scope = OUT.parent / "scan-scope.php"
    scope.write_text(
        "<?php if (!defined('ABSPATH')) exit; // GENERATED by railway/generate_country_table.py\n"
        f"$alt_scan_countries = {n_countries}; $alt_scan_outlets = {n_outlets};\n")
    print(f"wrote {OUT} — {n_countries} countries, {len(countries)} table rows, "
          f"{n_outlets} outlets (+ scan-scope.php)")
    if UNRECOGNISED:
        print("NOT counted as countries (folded into the multi-region row) — "
              "add any real country below to COUNTRIES:")
        for label in sorted(UNRECOGNISED):
            print(f"  {label}: {', '.join(sorted(set(UNRECOGNISED[label])))}")
