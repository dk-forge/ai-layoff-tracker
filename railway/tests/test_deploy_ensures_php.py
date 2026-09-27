"""Deploy 376 (2026-09-27) failed with `php: command not found` on the VPS
runner. The deploy must install php-cli on a self-hosted runner that lacks it,
before the PHP lint step runs."""
import unittest
from pathlib import Path

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "deploy-plugin.yml"


class DeployEnsuresPhp(unittest.TestCase):
    def test_self_hosted_runner_installs_php_before_lint(self):
        text = WF.read_text()
        ensure = text.index("Ensure a PHP CLI on the self-hosted runner")
        lint = text.index("Lint every plugin PHP file before upload")
        self.assertLess(ensure, lint)
        block = text[ensure:lint]
        for needle in ("command -v php", "apt-get install", "php-cli"):
            self.assertIn(needle, block)


if __name__ == "__main__":
    unittest.main()
