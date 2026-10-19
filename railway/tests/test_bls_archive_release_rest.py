"""bls-archive.yml publishes over REST, never via gh's GraphQL release lookup.

Regression for run 38220160618 (2026-10-12): `gh release view/upload` said
"release not found" for a release that existed. Offline workflow read.
"""
import pathlib
import unittest

WF = (pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows"
      / "bls-archive.yml").read_text(encoding="utf-8")


class BlsArchiveRest(unittest.TestCase):
    def test_no_gh_release_subcommands(self):
        code = "\n".join(l for l in WF.splitlines() if not l.strip().startswith("#"))
        self.assertNotIn("gh release ", code)

    def test_resolves_by_tag_and_creates_on_miss(self):
        self.assertIn('releases/tags/$tag', WF)
        self.assertIn('-X POST "repos/$repo/releases"', WF)

    def test_replaces_same_name_assets(self):
        self.assertIn("releases/assets/$old", WF)
        self.assertIn("uploads.github.com", WF)


if __name__ == "__main__":
    unittest.main()
