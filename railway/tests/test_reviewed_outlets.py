"""Every reviewed addition to the news allowlist is a claim, and no allowlist
domain may be a host the refusal ledger says refused us.

Worldwide-coverage audit, 2026-09-02: after the native-vocabulary fix the
GDELT allowlist still kept 2 of 244 Spanish candidates, 0 of 39 French and
0 of 50 Turkish. Those are allowlist failures. The fix is outlets, and an
outlet added to `TRUSTED_DOMAINS` is a public claim on the Sources page
("a reviewed allowlist of that country's news outlets"), so the addition has
to carry its review the way `reviewed_feeds.json` carries one for a press
feed: outlet, country, language, standing and a date, not a bare domain.

Three things fail here, each proved by mutation on 2026-09-02:

  * a domain inside the `2026-09-02 reviewed outlets` block of gdelt.py that
    `railway/reviewed_outlets.json` does not argue for;
  * a registry entry the allowlist does not actually carry, or one with an
    empty standing, an unknown country, or a bad date;
  * ANY domain in `TRUSTED_DOMAINS` that equals, sits under, or sits above a
    host recorded in `country_coverage.REFUSAL_LEDGER`. The ledger is binding
    (CLAUDE.md), and this is the check that makes "I checked the ledger" a
    property of the code rather than of one session's memory.

No network. Nothing here fetches an outlet, by rule.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.dirname(HERE)
sys.path.insert(0, RAILWAY)

import generate_country_table as gct  # noqa: E402
from country_coverage import REFUSAL_LEDGER  # noqa: E402
from sources.gdelt import TRUSTED_DOMAINS  # noqa: E402

REGISTRY = os.path.join(RAILWAY, "reviewed_outlets.json")
GDELT_SRC = os.path.join(RAILWAY, "sources", "gdelt.py")
# Every dated reviewed-outlets pass writes its own "# --- YYYY-MM-DD reviewed
# outlets: BEGIN" / "...: END" pair (2026-09-02 was the first, 2026-09-03 the
# second). A guard hardcoded to one date's markers only ever re-checks that
# one pass; a later block would sit unaudited right next to it, which is
# exactly the gap a "systematic, worst-country-first" review is supposed to
# close. So this matches EVERY such block by pattern, not by a literal date.
BLOCK_RX = re.compile(
    r"# --- (\d{4}-\d{2}-\d{2}) reviewed outlets: BEGIN(.*?)"
    r"# --- \1 reviewed outlets: END",
    re.DOTALL,
)

REQUIRED = ("domain", "outlet", "country", "language", "kind", "standing")


def _registry():
    with open(REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)


def _block_domains(text=None):
    """Domains literally written inside ANY dated reviewed-outlets block."""
    if text is None:
        with open(GDELT_SRC, encoding="utf-8") as fh:
            text = fh.read()
    doms = []
    for _date, body in BLOCK_RX.findall(text):
        doms.extend(re.findall(r'"([a-z0-9.\-]+)"', body))
    return doms


def ledger_hosts(ledger=REFUSAL_LEDGER):
    """Bare hosts named by the refusal ledger, `www.` and paths stripped.

    The `host` field is prose-shaped in places ("a.gov, b.gov",
    "*.gov.in and *.nic.in (labour.gov.in, ...)", "www.uwv.nl/nl/webpublicaties").
    Pull every host-looking token out of it; a wildcard becomes its suffix.
    """
    out = set()
    for entry in ledger:
        for tok in re.findall(r"[A-Za-z0-9*][A-Za-z0-9.\-*]*\.[A-Za-z]{2,}", entry["host"]):
            h = tok.lower().lstrip("*.").split("/", 1)[0]
            if h.startswith("www."):
                h = h[4:]
            if h:
                out.add(h)
    return out


def refusal_collisions(domains, hosts):
    """(domain, refused host) pairs where one is the other or lies under it."""
    hits = []
    for d in sorted(domains):
        for h in sorted(hosts):
            if d == h or d.endswith("." + h) or h.endswith("." + d):
                hits.append((d, h))
    return hits


class RegistryIsAReviewedClaim(unittest.TestCase):

    def setUp(self):
        self.reg = _registry()
        self.entries = self.reg["outlets"]

    def test_every_entry_carries_its_review(self):
        for e in self.entries:
            for key in REQUIRED:
                self.assertTrue(str(e.get(key, "")).strip(),
                                "%s: empty %s" % (e.get("domain"), key))
            # A standing is an argument, not a label. One clause is not enough.
            self.assertGreaterEqual(len(e["standing"].split()), 12,
                                    "%s: standing is not an argument" % e["domain"])
            self.assertIn(e["country"], gct.COUNTRIES, e["domain"])
            self.assertRegex(e["language"], r"^[a-z]{2}$", e["domain"])
            self.assertRegex(e["domain"], r"^[a-z0-9.\-]+\.[a-z]+$", e["domain"])

    def test_review_date_is_a_real_past_date(self):
        d = date.fromisoformat(self.reg["reviewed_at"])
        self.assertLessEqual(d, date.today())
        self.assertTrue(self.reg.get("reviewer", "").strip())

    def test_no_domain_is_registered_twice(self):
        doms = [e["domain"] for e in self.entries]
        self.assertEqual(len(doms), len(set(doms)), "duplicate registry domain")

    def test_no_entry_duplicates_an_outlet_the_allowlist_already_admits(self):
        # elpais.com already admits cincodias.elpais.com by suffix; a registry
        # entry for a subdomain of an existing entry is padding, not reach.
        older = set(TRUSTED_DOMAINS) - set(e["domain"] for e in self.entries)
        for e in self.entries:
            covered = [o for o in older if e["domain"].endswith("." + o)]
            self.assertEqual([], covered,
                             "%s is already admitted by %s" % (e["domain"], covered))


class AllowlistAndRegistryAgree(unittest.TestCase):

    def test_every_registry_domain_is_in_the_allowlist(self):
        missing = sorted(e["domain"] for e in _registry()["outlets"]
                         if e["domain"] not in TRUSTED_DOMAINS)
        self.assertEqual([], missing, "registry claims the allowlist does not carry")

    def test_every_domain_in_the_reviewed_block_is_in_the_registry(self):
        argued = set(e["domain"] for e in _registry()["outlets"])
        unargued = sorted(d for d in _block_domains() if d not in argued)
        self.assertEqual([], unargued,
                         "domains in the reviewed block with no registry claim")

    def test_the_block_is_not_empty_and_is_parsed_by_the_country_table(self):
        block = _block_domains()
        self.assertGreater(len(block), 0)
        rows = gct.parse()
        placed = set()
        for country, doms in rows.items():
            placed.update(doms)
        lost = sorted(d for d in block if d not in placed)
        self.assertEqual([], lost, "reviewed domains the country table drops")
        # And each landed on its country, not in the multi-region bucket.
        by_country = {e["domain"]: e["country"] for e in _registry()["outlets"]}
        for country, doms in rows.items():
            for d in doms:
                if d in by_country:
                    self.assertEqual(by_country[d], country, d)


class TheRefusalLedgerIsBinding(unittest.TestCase):

    def test_ledger_hosts_parse_to_bare_hosts(self):
        hosts = ledger_hosts()
        self.assertIn("legifrance.gouv.fr", hosts)
        self.assertIn("datos.comunidad.madrid", hosts)
        self.assertIn("uwv.nl", hosts)          # path stripped
        self.assertIn("gov.in", hosts)          # wildcard became its suffix
        self.assertNotIn("www.gov.ie", hosts)   # www stripped
        self.assertIn("gov.ie", hosts)

    def test_no_allowlist_domain_matches_a_refused_host(self):
        hits = refusal_collisions(TRUSTED_DOMAINS, ledger_hosts())
        self.assertEqual([], hits,
                         "allowlist domains that the refusal ledger says refused us")

    def test_no_registry_domain_matches_a_refused_host(self):
        hits = refusal_collisions([e["domain"] for e in _registry()["outlets"]],
                                  ledger_hosts())
        self.assertEqual([], hits)

    def test_the_collision_check_catches_a_refused_host_and_its_children(self):
        # Direct guard on the matcher, independent of today's allowlist.
        hosts = {"legifrance.gouv.fr", "gov.in"}
        self.assertEqual([("legifrance.gouv.fr", "legifrance.gouv.fr")],
                         refusal_collisions({"legifrance.gouv.fr"}, hosts))
        self.assertEqual([("pib.gov.in", "gov.in")],
                         refusal_collisions({"pib.gov.in"}, hosts))
        self.assertEqual([("gouv.fr", "legifrance.gouv.fr")],
                         refusal_collisions({"gouv.fr"}, hosts))
        self.assertEqual([], refusal_collisions({"lemonde.fr"}, hosts))


if __name__ == "__main__":
    unittest.main()
