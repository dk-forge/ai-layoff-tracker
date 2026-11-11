"""The ONE postal address every email footer prints (owner review 2026-11-11).

Read from wordpress-plugin/ai-layoff-tracker/includes/postal-address.json, the
same file the plugin's alt_mail_postal_address() reads, so the Python and PHP
footers can never drift. CAN-SPAM 15 U.S.C. 7704(a)(5) needs a valid physical
postal address; has_street_line() is the check the tests hold it to.
"""
import json
import re
from pathlib import Path

CONFIG = (Path(__file__).resolve().parents[1] / "wordpress-plugin" / "ai-layoff-tracker"
          / "includes" / "postal-address.json")

_STREET = re.compile(r"(?i)(\b(p\.?\s*o\.?\s*box|postbus|postbox|antwoordnummer)\s*\d+)|"
                     r"(\d+\s*[a-z]?\s+\S+)|(\S+\s+\d+\s*[a-z]?\b)")


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def postal_address(cfg: dict | None = None) -> str:
    cfg = config() if cfg is None else cfg
    parts = [str(cfg.get(k) or "").strip() for k in ("name", "street", "locality")]
    parts = [p for p in parts if p] or ["AskTheRecruiter"]
    return ", ".join(parts) + "."


def has_street_line(street: str) -> bool:
    """True when the line is a street address or PO box (a number beside a word)."""
    return bool(street and street.strip() and _STREET.search(street.strip()))
