"""Guards for the WARN import-boundary sanitizer.

Both defects here reached the PUBLIC table before they were caught, so these
tests exist to keep them out: Wisconsin's table smuggles a footnote (wrapped in
markup) inside the employer cell, and several states mark a withdrawn notice by
appending RESCINDED/CANCELLED to the employer name rather than removing the row.
"""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Only stub `requests` (a bare stub is enough for warn_import's real deps to
# import offline). Do NOT install fake `sources.*` modules: they persist in
# sys.modules and shadow the real sources.warn / sources.warn_custom for every
# test loaded after this one, which silently breaks their parsers. See the same
# note in tests/test_warn_generic_drift.py.
_rq = sys.modules.get("requests")
if _rq is None:
    _rq = types.ModuleType("requests")
    sys.modules["requests"] = _rq
if not hasattr(_rq, "RequestException"):
    _rq.RequestException = Exception

import warn_import as W  # noqa: E402

_WI = ('Wisconsin Green, LLC<br/></a><a><em style="font-size:80%">'
       '* Notice outlines multiple scenarios for layoffs.</em>')


def test_strips_markup_and_footnote_from_employer_name():
    assert W._clean_company(_WI) == "Wisconsin Green, LLC"
    assert W._clean_company('Air Wisconsin Airlines LLC (MKE Hangar)<br/><em>* x</em>') == \
        "Air Wisconsin Airlines LLC (MKE Hangar)"


def test_leaves_a_clean_name_untouched():
    for good in ("Saputo Cheese USA Inc", "Prairie Farms Dairy, Inc."):
        assert W._clean_company(good) == good


def test_detects_every_rescinded_spelling_states_actually_use():
    for bad in ("AeroFarms Inc. - Rescinded", "**JC Penney (Cancelled)",
                "*RESCINDED* Advanced Packaging, Inc.",
                "Noranda Aluminum 1111 N. Airline Hwy WARN RESCINDED",
                "MAXIMUS, Inc. - WARN CANCELLED"):
        assert W._RESCINDED_RX.search(bad), bad


def test_does_not_mistake_cancer_for_cancelled():
    # Word-boundary matching matters: "Cancer Treatment Centers" is a real
    # employer, and a substring match would silently delete its notices.
    for good in ("Cancer Treatment Centers of America", "Cancun Resorts LLC"):
        assert not W._RESCINDED_RX.search(good), good


def test_sanitize_drops_rescinded_keeps_others_and_preserves_hash():
    entries = [
        {"company_name": _WI, "dedup_hash": "h1", "job_count": 59,
         "excerpt": f"Layoff at {_WI} in Washington. 59 employees affected."},
        {"company_name": "AeroFarms Inc. - Rescinded", "dedup_hash": "h2",
         "job_count": 133, "excerpt": "x"},
        {"company_name": "Prairie Farms Dairy, Inc.", "dedup_hash": "h3",
         "job_count": 43, "excerpt": "clean"},
    ]
    out = W._sanitize_warn_entries(entries)
    assert [e["company_name"] for e in out] == ["Wisconsin Green, LLC", "Prairie Farms Dairy, Inc."]
    # The excerpt must lose the footnote too, not just the company field.
    assert "<" not in out[0]["excerpt"] and "Notice outlines" not in out[0]["excerpt"]
    assert out[0]["excerpt"].startswith("Layoff at Wisconsin Green, LLC in Washington.")
    # The hash stays keyed to the same source row, so the correction lands on the
    # EXISTING stored row instead of forking a second copy under the clean name.
    assert out[0]["dedup_hash"] == "h1"


def test_strips_pasted_site_address_from_employer_name():
    # Louisiana (436 rows) and California paste the notice's site address into
    # the employer cell, which fragments company identity: the polluted row
    # never groups with the plain company name in totals or the directory.
    cases = [
        ("SafeSource Direct L.L.C. 200 St. Nazaire Rd. Broussard, LA, 70518",
         "SafeSource Direct L.L.C."),
        ("Walmart (1345 Crossman Ave.)", "Walmart"),
        ("University Hospital & Clinics 2390 W. Congress St. Lafayette, LA 70506",
         "University Hospital & Clinics"),
    ]
    for raw, expected in cases:
        assert W._clean_company(raw) == expected, raw


def test_unescapes_entities_and_drops_repeated_update_markers():
    assert W._clean_company("Bingham &amp; Taylor") == "Bingham & Taylor"
    assert W._clean_company("Update: Update: Noranda Aluminum") == "Noranda Aluminum"


def test_address_stripping_never_damages_a_legitimate_name():
    # These all contain digits and/or address-like words; none may be truncated.
    for good in ("Prairie Farms Dairy, Inc. Shullsburg Creamery", "7-Eleven, Inc.",
                 "3M Company", "Air Wisconsin Airlines LLC (MKE Hangar)",
                 "Saputo Cheese USA Inc"):
        assert W._clean_company(good) == good, good


def test_handles_ranged_street_numbers_and_dangling_site_markers():
    # A range ("1500-1552") stops a plain \d+ match, so these escaped the first
    # pass; and cutting an address can leave an orphaned site label behind.
    assert W._clean_company("Off Duty Officers, Inc. (1500-1552 Encinitas Blvd.)") == \
        "Off Duty Officers, Inc."
    assert W._clean_company("Winn Dixie Store No. 1411 5901 Airline Drive Metairie, LA 70003") == \
        "Winn Dixie Store"


def test_drops_rows_whose_employer_cell_is_only_punctuation():
    # Tennessee's list yields employer cells of "." and ",". Published as-is
    # they are rows no reader can verify. The guard is ALPHANUMERIC, not
    # alphabetic, because "118-118" is a real (UK) company.
    out = W._sanitize_warn_entries([
        {"company_name": ".", "excerpt": "x", "dedup_hash": "a", "job_count": 51},
        {"company_name": ",", "excerpt": "x", "dedup_hash": "b", "job_count": 46},
        {"company_name": "118-118", "excerpt": "x", "dedup_hash": "c", "job_count": 180},
    ])
    assert [e["company_name"] for e in out] == ["118-118"]
