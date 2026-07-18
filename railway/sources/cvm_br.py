"""Discovery-only CVM (Brazil) IPE filings-index client.

This module reads one official yearly IPE filings index from CVM's open-data
portal (dados.cvm.gov.br).  It does not download filing bodies (the official
``Link_Download`` URL is retained as discovery metadata only), classify a
document, post a tracker event, report live source health, or change the
market registry.  A future scheduled connector must persist its own cursor
only after the complete index has been fetched and parsed, and must report
source health around that work.

Interface verified 2026-07-18: the dataset "Cias Abertas: Documentos:
Periódicos e Eventuais (IPE)" publishes one ZIP per delivery year at
``https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{YYYY}.zip``
(history since 2003; current and prior-year files refresh weekly).  Each ZIP
holds one semicolon-delimited, ISO-8859-1 encoded CSV whose header is the
13 columns pinned in ``EXPECTED_COLUMNS`` (data dictionary:
``https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/META/meta_ipe_cia_aberta.txt``).
Material-fact filings — the Brazilian 8-K analog — are rows whose
``Categoria`` equals ``"Fato Relevante"``.  No API key is required.

Data licence and attribution (required for reuse of this ODbL dataset):
contains information from "Cias Abertas: Documentos: Periódicos e Eventuais
(IPE)", CVM — Portal de Dados Abertos
(https://dados.cvm.gov.br/dataset/cia_aberta-doc-ipe), made available under
the Open Database License (ODbL).
"""
from __future__ import annotations

import csv
import io
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

import requests


INDEX_URL_TEMPLATE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{year}.zip"
DATASET_PAGE_URL = "https://dados.cvm.gov.br/dataset/cia_aberta-doc-ipe"
METADATA_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/META/meta_ipe_cia_aberta.txt"
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
MAX_ATTEMPTS = 3
MAX_INDEX_BYTES = 100 * 1024 * 1024  # Defensive bound; real yearly ZIPs are a few MB.
FIRST_INDEX_YEAR = 2003  # Oldest yearly file published by the portal.
CSV_ENCODING = "latin-1"  # Portal CSVs are ISO-8859-1.
CSV_DELIMITER = ";"
FATO_RELEVANTE = "Fato Relevante"
ODBL_ATTRIBUTION = (
    'Contains information from "Cias Abertas: Documentos: Periódicos e Eventuais (IPE)", '
    "CVM — Portal de Dados Abertos (https://dados.cvm.gov.br/dataset/cia_aberta-doc-ipe), "
    "made available under the Open Database License (ODbL)."
)

# Exact header of ipe_cia_aberta_{YYYY}.csv, in file order.  Parsing hard-fails
# if the publisher ever changes this structure so drift is caught loudly.
EXPECTED_COLUMNS = (
    "CNPJ_Companhia",
    "Nome_Companhia",
    "Codigo_CVM",
    "Data_Referencia",
    "Categoria",
    "Tipo",
    "Especie",
    "Assunto",
    "Data_Entrega",
    "Tipo_Apresentacao",
    "Protocolo_Entrega",
    "Versao",
    "Link_Download",
)


class CvmApiError(RuntimeError):
    """A classified, secret-free CVM open-data request failure."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


@dataclass(frozen=True)
class CvmFilingIndex:
    year: int
    retrieved_at: str
    filings: tuple[dict[str, Any], ...]
    attribution: str
    complete: bool


def _valid_year(value: int | str) -> int:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}", text):
        raise ValueError("year must be a four-digit calendar year")
    year = int(text)
    if year < FIRST_INDEX_YEAR or year > 2100:
        raise ValueError(f"year must be between {FIRST_INDEX_YEAR} and 2100")
    return year


def index_url(year: int | str) -> str:
    """Return the official yearly ZIP index URL for a validated year."""
    return INDEX_URL_TEMPLATE.format(year=_valid_year(year))


def document_url(link: str) -> str:
    """Validate that a Link_Download value is an official https CVM URL.

    The URL is kept verbatim as public provenance; it is never fetched here.
    """
    value = str(link or "").strip()
    if not value or len(value) > 1000 or any(ch.isspace() or ord(ch) < 32 for ch in value):
        raise ValueError("document link must be a single printable URL")
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or (host != "cvm.gov.br" and not host.endswith(".cvm.gov.br")):
        raise ValueError("document link must be an https cvm.gov.br URL")
    return value


def _candidate(row: dict[str, str]) -> dict[str, Any] | None:
    protocol = str(row.get("Protocolo_Entrega") or "").strip()
    if not protocol:
        return None
    try:
        source_url = document_url(row.get("Link_Download") or "")
    except ValueError:
        return None  # Never emit a candidate whose link is not an official CVM URL.
    # Retain official metadata exactly enough to distinguish a later
    # resubmission (Tipo_Apresentacao RE/RC) from an original delivery (AP).
    # No factual field is interpreted as a job count, job location, industry,
    # or employer domicile.
    return {
        "delivery_protocol": protocol,
        "company_cnpj": str(row.get("CNPJ_Companhia") or ""),
        "company_name": str(row.get("Nome_Companhia") or ""),
        "cvm_code": str(row.get("Codigo_CVM") or ""),
        "reference_date": str(row.get("Data_Referencia") or ""),
        "category": str(row.get("Categoria") or ""),
        "document_type": str(row.get("Tipo") or ""),
        "document_species": str(row.get("Especie") or ""),
        "subject": str(row.get("Assunto") or ""),
        "delivered_at": str(row.get("Data_Entrega") or ""),
        "presentation_type": str(row.get("Tipo_Apresentacao") or ""),
        "version": str(row.get("Versao") or ""),
        "source_name": "CVM IPE filings index",
        "source_url": source_url,
        "scope": "Discovery metadata only; filing body has not been retrieved or classified as a layoff event.",
    }


def _retry_delay(attempt: int) -> float:
    return min(30.0, float(2 ** attempt))


def _parse_index(content: bytes, year: int) -> list[dict[str, str]]:
    """Extract the yearly CSV member and return raw rows keyed by header.

    Raises ``zipfile.BadZipFile`` for a corrupt archive (possibly a truncated
    transfer, so the caller may retry) and ``CvmApiError`` for structural
    drift, which must fail loudly rather than be papered over.
    """
    archive = zipfile.ZipFile(io.BytesIO(content))  # May raise BadZipFile.
    expected_member = f"ipe_cia_aberta_{year}.csv"
    members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if expected_member in members:
        member = expected_member
    elif len(members) == 1:
        member = members[0]
    else:
        raise CvmApiError("malformed_response", "CVM IPE archive did not contain the expected CSV index")
    text = archive.read(member).decode(CSV_ENCODING)
    reader = csv.reader(io.StringIO(text), delimiter=CSV_DELIMITER)
    try:
        header = next(reader)
    except StopIteration:
        raise CvmApiError("malformed_response", "CVM IPE index CSV was empty") from None
    if tuple(column.strip() for column in header) != EXPECTED_COLUMNS:
        raise CvmApiError("malformed_response", "CVM IPE index CSV header drifted from the documented structure")
    rows: list[dict[str, str]] = []
    for values in reader:
        if len(values) != len(EXPECTED_COLUMNS):
            continue  # Tolerate stray blank/short lines; structure drift is caught above.
        rows.append(dict(zip(EXPECTED_COLUMNS, values)))
    return rows


def list_filings_for_year(
    year: int | str,
    *,
    categories: tuple[str, ...] | None = (FATO_RELEVANTE,),
    http_get: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> CvmFilingIndex:
    """Fetch one complete yearly index of filing metadata from the portal.

    ``categories`` filters rows by exact ``Categoria`` value and defaults to
    Fatos Relevantes only; pass ``None`` to keep every category.  No API key
    exists for this open-data endpoint.  429/5xx responses and corrupt
    transfers retry a bounded number of times; callers receive a classified
    exception and therefore must not advance a persisted cursor.
    """
    requested_year = _valid_year(year)
    url = index_url(requested_year)
    get = http_get or requests.get
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/zip"}, timeout=60)
        except Exception as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise CvmApiError("network", "CVM IPE index request failed") from exc
        status = int(getattr(response, "status_code", 0) or 0)
        if status == 429:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise CvmApiError("rate_limited", "CVM IPE index request was rate limited")
        if status in {401, 403}:
            raise CvmApiError("forbidden", "CVM IPE index access was refused")
        if status == 404:
            raise CvmApiError("not_found", "CVM IPE index for the requested year is not published")
        if status >= 500:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise CvmApiError("upstream", "CVM IPE index service failed")
        if status >= 400:
            raise CvmApiError("request", f"CVM IPE index returned HTTP {status}")
        content = getattr(response, "content", None)
        if not isinstance(content, (bytes, bytearray)) or not content:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise CvmApiError("malformed_response", "CVM IPE index returned an empty body")
        if len(content) > MAX_INDEX_BYTES:
            raise CvmApiError("malformed_response", "CVM IPE index exceeded the defensive size bound")
        try:
            rows = _parse_index(bytes(content), requested_year)
        except zipfile.BadZipFile as exc:
            if attempt + 1 < MAX_ATTEMPTS:
                sleep(_retry_delay(attempt))
                continue
            raise CvmApiError("malformed_response", "CVM IPE index was not a readable ZIP archive") from exc
        wanted = None if categories is None else {str(item) for item in categories}
        candidates = tuple(
            candidate
            for candidate in (
                _candidate(row)
                for row in rows
                if wanted is None or str(row.get("Categoria") or "").strip() in wanted
            )
            if candidate is not None
        )
        return CvmFilingIndex(
            year=requested_year,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            filings=candidates,
            attribution=ODBL_ATTRIBUTION,
            complete=True,
        )
    raise AssertionError("unreachable")


def next_cursor_after_success(year: int | str, result: CvmFilingIndex) -> str | None:
    """Return the newest delivery date only for the matching successful index.

    The yearly file is republished weekly, so the safe cursor is the latest
    ``Data_Entrega`` actually parsed — a future scheduler re-reads the index
    and resumes after that date instead of skipping coverage.  A failed,
    partial, mismatched, or empty parse returns ``None`` so the same year
    stays queued.
    """
    requested_year = _valid_year(year)
    if not isinstance(result, CvmFilingIndex) or not result.complete or result.year != requested_year:
        return None
    newest: date | None = None
    for row in result.filings:
        text = str(row.get("delivered_at") or "")[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            continue
        try:
            delivered = date.fromisoformat(text)
        except ValueError:
            continue
        if newest is None or delivered > newest:
            newest = delivered
    return newest.isoformat() if newest is not None else None
