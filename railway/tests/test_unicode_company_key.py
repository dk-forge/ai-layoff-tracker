"""alt_company_key() reads non-Latin scripts, and no Latin key moves.

THE DEFECT. Until 2.20.203 the key's strip was preg_replace('/[^a-z0-9 ]/'):
an ASCII-only class without /u. A name written wholly in a non-Latin script
("捷豹路虎", "Сбербанк", "สยามคูโบต้า") came out as the EMPTY string, and every
fuzzy and superset pass excludes empty keys (`company_key <> ''` in db.php,
mirrored by dedupe_llm.norm_company). So every such row was silently
un-dedupable, and worse, the /add "rebadge suspect" check compared
`company_key = ''`, so a new non-Latin row could be refused because some
OTHER empty-keyed row had the same count half a year earlier.

WHAT THE FIX MAY NOT DO. company_key is stored, derived on write, and groups
rows for dedup and for company pages. A Latin key that moved by one byte would
split an employer's history between old and new rows. So the new strip keeps
the Latin ranges exactly as the old one did (accents still become spaces), and
the byte-identity half below is proved over every code point in those ranges
and over real names, not asserted.

WHAT IT DOES NOT DO. It does not transliterate. A non-Latin key only equals a
name in the same script; cross-script identity stays a hand-kept lookup.

Every PHP assertion runs the plugin's own functions, lifted from api.php.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import dedupe_llm  # noqa: E402
import entity_resolution as er  # noqa: E402

API_PHP_PATH = ROOT / "wordpress-plugin/ai-layoff-tracker/includes/api.php"
PHP = shutil.which("php")

#: The pre-2.20.203 function, verbatim apart from its name, as the reference
#: the byte-identity proof compares against.
LEGACY_PHP = r"""
function legacy_company_key($name) {
    $k = strtolower((string) $name);
    $nonlatin = alt_nonlatin_company_alias($k);
    if ($nonlatin !== '') return $nonlatin;
    $k = preg_replace('/[^a-z0-9 ]/', ' ', $k);
    $k = preg_replace('/\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp|group|holdings|holding|technologies|technology|systems|solutions|the|com)\b/', ' ', $k);
    $k = preg_replace('/\b(america|americas|usa|us|international|global|worldwide|na)\b/', ' ', $k);
    $k = trim(preg_replace('/\s+/', ' ', $k));
    return alt_canonical_company($k);
}
"""

LIFTED = ("alt_company_key", "alt_company_key_body", "alt_company_key_is_utf8", "alt_company_key_chars",
          "alt_canonical_company", "alt_nonlatin_company_alias")


def _php(expr_per_name, names, raw=False):
    """Evaluate a PHP expression over $n for each name, with the lifted code.

    `raw` passes names as hex so invalid UTF-8 can reach the function.
    """
    code = (
        "$src = file_get_contents($argv[1]);"
        "foreach (json_decode($argv[3]) as $fn) {"
        "  $start = strpos($src, \"function $fn(\");"
        "  if ($start === false) { fwrite(STDERR, \"missing $fn\"); exit(2); }"
        "  $end = strpos($src, \"\\n}\\n\", $start);"
        "  eval(substr($src, $start, $end - $start + 3)); }"
        "eval($argv[4]);"
        "$out = [];"
        "foreach (json_decode($argv[2]) as $i => $n) {"
        + ("  $n = hex2bin($n);" if raw else "")
        + f"  $out[] = {expr_per_name}; }}"
        "echo json_encode($out, JSON_INVALID_UTF8_SUBSTITUTE);")
    payload = [n.hex() for n in names] if raw else names
    run = subprocess.run(
        [PHP, "-r", code, str(API_PHP_PATH), json.dumps(payload),
         json.dumps(LIFTED), LEGACY_PHP],
        capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        raise AssertionError(f"php failed: {run.stderr[:800]}")
    return json.loads(run.stdout)


#: One name per script the tracker has actually stored or plausibly will.
NON_LATIN = {
    "cjk": "捷豹路虎汽车",
    "japanese": "トヨタ自動車",
    "korean": "삼성전자",
    "cyrillic": "Сбербанк",
    "arabic": "أرامكو السعودية",
    "arabic_harakat": "مُحَمَّد للتجارة",
    "hebrew": "אל על",
    "greek": "Τράπεζα Πειραιώς",
    "thai": "ปูนซิเมนต์ไทย",
    "devanagari": "टाटा स्टील",
}

#: Real Latin names in the shapes the live table holds (sampled 2026-09-16 from
#: /query), plus the edge cases most likely to move: accents, Turkish dotted I,
#: Kelvin sign, fullwidth, ligatures, emoji with a variation selector, marks.
LATIN = [
    "Amazon.com, Inc.", "The Boeing Company", "Oracle America, Inc.",
    "Société Générale", "Nestlé S.A.", "Deutsche Börse AG", "Škoda Auto",
    "Volkswagen Group", "Tata Motors’ JLR", "Nguyễn Kim", "İş Bankası",
    "Türk Telekom", "Øresundsbron", "Łukasiewicz", "Ørsted A/S",
    "Kelvin Kinetics K", "ＩＢＭ Japan", "Ofﬁce Depot", "Apple❤️",
    "Café Rouge", "Straße GmbH", "Ångström Labs", "Mañana Foods",
    "Crédit Agricole", "L'Oréal", "Zürich Insurance", "µTech", "Company²",
    "Ⅻ Holdings", "𝐁𝐨𝐥𝐝 Corp", "Energoremont – Bobov dol JSC",
    "Manteca District Ambulance Service - Hwy 49", "UPDATE Acme Co",
    "", "   ", "Inc.", "3M", "AT&T", "H&M Hennes & Mauritz",
]

#: Mixed-script names, the shapes the live sample held on 2026-09-16.
MIXED = ["LG 电子 Inc.", "普利司通 (Bridgestone)", "هيئة الإذاعة البريطانية BBC",
         "VI.K.Ι (Meat Industry of Epirus)", "Coсбер", "Сбербанк Inc"]


@unittest.skipUnless(PHP, "php binary not available")
class NonLatinNamesHaveAKey(unittest.TestCase):

    def test_every_script_keys_non_empty_on_the_server(self):
        keys = _php("alt_company_key($n)", list(NON_LATIN.values()))
        for (script, name), key in zip(NON_LATIN.items(), keys):
            with self.subTest(script=script):
                self.assertNotEqual("", key, name)

    def test_and_in_both_python_mirrors(self):
        for script, name in NON_LATIN.items():
            with self.subTest(script=script):
                self.assertNotEqual("", er.entity_key(name), name)
                self.assertNotEqual("", dedupe_llm.norm_company(name), name)

    def test_marks_do_not_split_a_word(self):
        """Thai vowels and Arabic harakat are marks; stripping them to spaces
        would cut one word into several and make one name key two ways."""
        thai, arabic = _php("alt_company_key($n)",
                            [NON_LATIN["thai"], NON_LATIN["arabic_harakat"]])
        self.assertEqual(NON_LATIN["thai"], thai)
        self.assertEqual("مُحَمَّد للتجارة", arabic)

    def test_case_folds_within_a_script(self):
        upper, lower = _php("alt_company_key($n)", ["СБЕРБАНК", "сбербанк"])
        self.assertEqual(upper, lower)
        self.assertEqual(er.entity_key("СБЕРБАНК"), er.entity_key("сбербанк"))

    def test_it_does_not_transliterate(self):
        cyr, lat = _php("alt_company_key($n)", ["Сбербанк", "Sberbank"])
        self.assertNotEqual(cyr, lat)

    def test_a_mixed_name_keeps_its_latin_key(self):
        """A non-empty ASCII key is never replaced. Live, every mixed name was
        "native (Latin)" or "native Latin", and the Latin half is the part that
        meets the employer's other rows: row 179233 "普利司通 (Bridgestone)"
        must keep keying "bridgestone"."""
        names = ["LG 电子 Inc.", "普利司通 (Bridgestone)", "هيئة الإذاعة البريطانية BBC"]
        self.assertEqual(["lg", "bridgestone", "bbc"], _php("alt_company_key($n)", names))
        self.assertEqual(["lg", "bridgestone", "bbc"], [er.entity_key(n) for n in names])
        self.assertEqual(["lg", "bridgestone", "bbc"], [dedupe_llm.norm_company(n) for n in names])

    def test_a_name_that_is_only_a_legal_form_plus_script_still_keys(self):
        """"Сбербанк Inc" has an ASCII pass that strips to '' and must fall
        through to the Unicode pass, not stop at the empty ASCII result."""
        self.assertEqual(["сбербанк"], _php("alt_company_key($n)", ["Сбербанк Inc"]))
        self.assertEqual("сбербанк", er.entity_key("Сбербанк Inc"))
        self.assertEqual("сбербанк", dedupe_llm.norm_company("Сбербанк Inc"))

    def test_word_boundaries_are_unicode_aware(self):
        """"co" glued to a Cyrillic word is not the legal form "Co". A byte
        pattern sees a boundary before the first UTF-8 byte and strips it."""
        self.assertEqual(["coсбер"], _php("alt_company_key($n)", ["Coсбер"]))
        self.assertEqual("coсбер", er.entity_key("Coсбер"))

    def test_the_recorded_cross_script_alias_still_wins(self):
        self.assertEqual(["jaguar land rover"] * 2,
                         _php("alt_company_key($n)", ["捷豹路虎", "JLR"]))

    def test_invalid_utf8_takes_the_old_ascii_strip(self):
        """A /u pattern returns null on invalid UTF-8; the key must not."""
        got = _php("[alt_company_key($n), legacy_company_key($n)]",
                   [b"Acme \xff\xfe Corp"], raw=True)
        self.assertEqual(got[0][1], got[0][0])
        self.assertEqual("acme", got[0][0])


@unittest.skipUnless(PHP, "php binary not available")
class NoLatinKeyMoves(unittest.TestCase):

    def test_real_and_edge_case_latin_names_key_exactly_as_before(self):
        pairs = _php("[legacy_company_key($n), alt_company_key($n)]", LATIN)
        moved = {n: p for n, p in zip(LATIN, pairs) if p[0] != p[1]}
        self.assertFalse(moved, f"Latin keys moved: {moved}")

    def test_every_code_point_in_the_latin_ranges_strips_as_before(self):
        """Exhaustive over U+0000..U+036F and every range the strip keeps as
        Latin: each character inside a name, and ALONE (where the ASCII pass
        is empty and the Unicode pass runs), keys as it did."""
        ranges = [(0x0000, 0x036F)] + list(er._KEY_LATIN_RANGES)
        names = []
        for low, high in ranges:
            for code in range(low, high + 1):
                if 0xD800 <= code <= 0xDFFF:
                    continue
                ch = chr(code)
                names.append(f"acme{ch}widget {ch} corp")
                names.append(f"{ch}{ch} {ch} Inc")
        self.assertGreater(len(names), 8000)
        pairs = _php("[legacy_company_key($n), alt_company_key($n)]", names)
        moved = [(n, p) for n, p in zip(names, pairs) if p[0] != p[1]]
        self.assertFalse(moved[:20], f"{len(moved)} Latin code points moved a key")

    def test_only_an_empty_key_can_change(self):
        """The whole blast radius, stated as a property: a key that was not
        empty before is byte-identical now, for every name in this file."""
        names = list(NON_LATIN.values()) + LATIN + MIXED
        pairs = _php("[legacy_company_key($n), alt_company_key($n)]", names)
        for name, (old, new) in zip(names, pairs):
            with self.subTest(name=name):
                if old != "":
                    self.assertEqual(old, new)
        changed = [n for n, p in zip(names, pairs) if p[0] != p[1]]
        self.assertEqual(set(changed), set(NON_LATIN.values()) | {"Coсбер", "Сбербанк Inc"})


@unittest.skipUnless(PHP, "php binary not available")
class PhpAndPythonAgree(unittest.TestCase):
    """Two copies of one strip: drift fails here (two-copies-drifted)."""

    SAMPLE = list(NON_LATIN.values()) + LATIN + MIXED + ["СБЕРБАНК"]

    def test_the_character_strip_is_identical(self):
        php = _php("alt_company_key_chars(strtolower($n))", self.SAMPLE)
        for name, key in zip(self.SAMPLE, php):
            with self.subTest(name=name):
                self.assertEqual(key, er.company_key_chars(name))

    def test_the_character_strip_is_identical_code_point_by_code_point(self):
        """Every BMP letter, digit and mark block the tracker is likely to meet,
        so a Unicode-category disagreement between PCRE and Python shows up."""
        names = [chr(c) for c in range(0x0370, 0x3100) if not 0xD800 <= c <= 0xDFFF]
        php = _php("alt_company_key_chars(strtolower($n))", names)
        bad = [(hex(ord(n)), k, er.company_key_chars(n))
               for n, k in zip(names, php) if k != er.company_key_chars(n)]
        self.assertFalse(bad[:20], f"{len(bad)} code points disagree")

    def test_norm_company_matches_the_server_key_where_the_lists_agree(self):
        """norm_company carries three extra legal forms (sa, ag, platforms) and
        no alias map, a pre-existing and documented difference; on names that
        touch neither, it must equal the server's key."""
        names = [n for n in self.SAMPLE
                 if not any(w in n.lower() for w in (" sa", " ag", "platforms", "jlr", "捷豹"))]
        php = _php("alt_company_key($n)", names)
        for name, key in zip(names, php):
            with self.subTest(name=name):
                self.assertEqual(key, dedupe_llm.norm_company(name))

    def test_entity_key_matches_the_server_key(self):
        names = [n for n in self.SAMPLE if "Ｉ" not in n and "ﬁ" not in n
                 and "K" not in n and "\U0001d401" not in n
                 and "µ" not in n and "²" not in n and "Ⅻ" not in n
                 and "́" not in n]
        # entity_key NFKC-folds first (fullwidth, ligatures, compatibility
        # letters become ASCII there), a pre-existing difference the filter
        # above leaves out rather than hides.
        php = _php("alt_company_key($n)", names)
        for name, key in zip(names, php):
            with self.subTest(name=name):
                self.assertEqual(key, er.entity_key(name))


if __name__ == "__main__":
    unittest.main()


DB_PHP_PATH = ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php"

REDERIVE_HARNESS = r"""
define('ARRAY_A', 'ARRAY_A');
class WP_Error { public $code; function __construct($c, $m = '', $d = null) { $this->code = $c; } }
class WP_REST_Request {
    private $p; function __construct($p) { $this->p = $p; }
    function get_param($k) { return $this->p[$k] ?? null; }
}
function rest_ensure_response($x) { return $x; }
function alt_db_table() { return 'wp_alt_layoffs'; }
$GLOBALS['flushed'] = 0;
function alt_flush_caches() { $GLOBALS['flushed']++; }
class FakeDb {
    public $rows; public $updates = array(); public $last_error = '';
    function __construct($rows) { $this->rows = $rows; }
    function prepare($sql, ...$a) { return $sql; }
    function get_results($sql, $mode) { return $this->rows; }
    function update($t, $data, $where) { $this->updates[] = array($where['id'], $where['company_key'], $data['company_key']); return 1; }
}
"""


@unittest.skipUnless(PHP, "php binary not available")
class TheRederiveEndpointIsDryByDefault(unittest.TestCase):
    """The backfill is built, not run. These prove what it WOULD do."""

    ROWS = [
        {"id": 176955, "company": "大甲李綜合醫院", "company_key": ""},
        {"id": 179237, "company": "捷豹路虎", "company_key": ""},       # alias: drift, left alone
        {"id": 179240, "company": "مصر للغزل والنسيج", "company_key": ""},
        {"id": 900001, "company": "…", "company_key": ""},             # still empty: unchanged
    ]

    def _run(self, params):
        db_src = DB_PHP_PATH.read_text(encoding="utf-8")
        api_src = API_PHP_PATH.read_text(encoding="utf-8")

        def lift(src, fn):
            start = src.index(f"function {fn}(")
            return src[start:src.index("\n}\n", start) + 3]

        code = (REDERIVE_HARNESS
                + "".join(lift(api_src, f) for f in LIFTED)
                + lift(db_src, "alt_normalize_company_ws")
                + lift(db_src, "alt_api_company_key_rederive")
                + "$wpdb = new FakeDb(json_decode($argv[1], true));"
                + "$out = alt_api_company_key_rederive(new WP_REST_Request(json_decode($argv[2], true)));"
                + "echo json_encode(array('out' => $out, 'updates' => $wpdb->updates, 'flushed' => $GLOBALS['flushed']));")
        run = subprocess.run([PHP, "-r", code, json.dumps(self.ROWS), json.dumps(params)],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, run.returncode, run.stderr[:800])
        return json.loads(run.stdout)

    def test_a_dry_run_writes_nothing_and_reports_the_plan(self):
        got = self._run({"limit": 500})
        self.assertTrue(got["out"]["dry_run"])
        self.assertEqual([], got["updates"])
        self.assertEqual(0, got["flushed"])
        self.assertEqual([176955, 179240], [c["id"] for c in got["out"]["changed"]])
        self.assertEqual([179237], [d["id"] for d in got["out"]["drift"]])
        self.assertEqual(1, got["out"]["unchanged"])
        self.assertEqual(900001, got["out"]["next_after_id"])

    def test_a_string_true_is_still_a_dry_run(self):
        self.assertEqual([], self._run({"apply": "true"})["updates"])
        self.assertEqual([], self._run({"apply": 1})["updates"])

    def test_apply_writes_only_the_planned_rows_guarded_on_the_old_key(self):
        got = self._run({"apply": True})
        self.assertEqual([[176955, "", "大甲李綜合醫院"],
                          [179240, "", "مصر للغزل والنسيج"]], got["updates"])
        self.assertEqual(1, got["flushed"])


class TheDirectoryDoesNotPublishANonLatinKey(unittest.TestCase):
    """A non-Latin key is new, so the weekly directory autopilot would meet it
    for the first time and sanitize_title() its name into a percent-encoded
    slug. It must park the key before any slug is built."""

    def test_the_autopilot_parks_a_non_latin_key_before_slugging(self):
        src = DB_PHP_PATH.read_text(encoding="utf-8")
        body = src[src.index("function alt_api_company_directory_autopilot("):]
        body = body[:body.index("\n}\n")]
        guard = body.find("preg_match('/[^\\x00-\\x7F]/', $key)")
        self.assertNotEqual(-1, guard, "the non-Latin key guard is gone")
        self.assertLess(guard, body.index("$slug = sanitize_title($name);"))
        self.assertIn("alt_company_directory_park_pending($key, $name)",
                      body[guard:guard + 400])
