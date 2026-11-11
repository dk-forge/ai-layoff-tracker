"""postal-address.php as a source string the PHP harnesses prepend, so a
function extracted from a mail file finds alt_mail_postal_address()."""
from pathlib import Path

DIR = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker" / "includes"
SRC = ((DIR / "postal-address.php").read_text(encoding="utf-8")
       .replace("<?php", "", 1).replace("__DIR__", repr(str(DIR))))
