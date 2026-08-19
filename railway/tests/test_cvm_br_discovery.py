"""Focused guards for the inactive CVM (Brazil) IPE discovery-only foundation."""
import io
import sys
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources.cvm_br import (
    CvmApiError,
    ODBL_ATTRIBUTION,
    document_url,
    list_filings_for_year,
    next_cursor_after_success,
)


# Inline slice matching the real ipe_cia_aberta_{YYYY}.csv structure verified
# against the live portal on 2026-07-18 (semicolon-delimited, ISO-8859-1).
CSV_HEADER = (
    "CNPJ_Companhia;Nome_Companhia;Codigo_CVM;Data_Referencia;Categoria;Tipo;"
    "Especie;Assunto;Data_Entrega;Tipo_Apresentacao;Protocolo_Entrega;Versao;Link_Download"
)
DOC_URL = (
    "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&descTipo=IPE"
    "&CodigoInstituicao=1&numProtocolo=1476522&numSequencia=1001228&numVersao=1"
)
CSV_ROWS = [
    # Original Fato Relevante delivery (accented Portuguese text exercises latin-1).
    "00.000.000/0001-91;BANCO DO BRASIL S.A.;1023;2026-02-11;Fato Relevante;;;"
    f"Projeções 2026;2026-02-11;AP - Apresentação;001023IPE110220260100646147-02;1;{DOC_URL}",
    # Different category: excluded by the default Fato Relevante filter.
    "00.000.000/0001-91;BANCO DO BRASIL S.A.;1023;2026-03-01;Comunicado ao Mercado;;;"
    f"Esclarecimentos;2026-03-01;AP - Apresentação;001023IPE010320260100000001-01;1;{DOC_URL}",
    # Voluntary resubmission of a Fato Relevante: retained with its status.
    "00.000.000/0001-91;BANCO DO BRASIL S.A.;1023;2026-01-19;Fato Relevante;;;"
    f"Payout 2026;2026-01-19;RE - Reapresentação Espontânea;001023IPE190120260180917778-84;2;{DOC_URL}",
    # Off-portal link: candidate must be dropped, never emitted unvalidated.
    "00.000.000/0001-91;BANCO DO BRASIL S.A.;1023;2026-04-02;Fato Relevante;;;"
    "Link estranho;2026-04-02;AP - Apresentação;001023IPE020420260100000002-02;1;https://evil.example.com/doc",
    # Missing delivery protocol: dropped.
    "00.000.000/0001-91;BANCO DO BRASIL S.A.;1023;2026-05-05;Fato Relevante;;;"
    f"Sem protocolo;2026-05-05;AP - Apresentação;;1;{DOC_URL}",
]


def _zip_bytes(csv_text, member="ipe_cia_aberta_2026.csv"):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, csv_text.encode("latin-1"))
    return buffer.getvalue()


def _fixture_zip():
    return _zip_bytes(CSV_HEADER + "\r\n" + "\r\n".join(CSV_ROWS) + "\r\n")


class _Response:
    def __init__(self, status_code=200, content=b""):
        self.status_code = status_code
        self.content = content


class CvmBrDiscoveryTests(unittest.TestCase):
    def test_filters_fato_relevante_and_keeps_official_link_scope_and_attribution(self):
        calls = []

        def get(*args, **kwargs):
            calls.append((args, kwargs))
            return _Response(content=_fixture_zip())

        result = list_filings_for_year(2026, http_get=get)
        self.assertEqual(calls[0][0][0], "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_2026.zip")
        self.assertEqual(calls[0][1]["headers"]["User-Agent"], "AiLayoffTracker/1.0 (+https://asktherecruiter.com)")
        self.assertTrue(result.complete)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.attribution, ODBL_ATTRIBUTION)
        self.assertIn("ODbL", result.attribution)
        self.assertIn("dados.cvm.gov.br", result.attribution)
        # Default filter keeps only validly linked Fatos Relevantes.
        self.assertEqual(len(result.filings), 2)
        original, resubmission = result.filings
        self.assertEqual(original["subject"], "Projeções 2026")  # latin-1 decoded intact
        self.assertEqual(original["category"], "Fato Relevante")
        self.assertEqual(original["presentation_type"], "AP - Apresentação")
        self.assertEqual(resubmission["presentation_type"], "RE - Reapresentação Espontânea")
        for row in result.filings:
            self.assertTrue(row["source_url"].startswith("https://www.rad.cvm.gov.br/"))
            self.assertIn("Discovery metadata only", row["scope"])
            self.assertNotIn("job_count", row)
            self.assertNotIn("employer_country", row)
        # categories=None keeps every category but still drops invalid rows.
        everything = list_filings_for_year(2026, categories=None, http_get=lambda *_, **__: _Response(content=_fixture_zip()))
        self.assertEqual(len(everything.filings), 3)
        self.assertEqual({row["category"] for row in everything.filings}, {"Fato Relevante", "Comunicado ao Mercado"})

    def test_header_drift_fails_loudly_and_corrupt_zip_retries_are_bounded(self):
        drifted = _zip_bytes(CSV_HEADER.replace("Link_Download", "Nova_Coluna") + "\r\n")
        with self.assertRaisesRegex(CvmApiError, "header drifted") as caught:
            list_filings_for_year(2026, http_get=lambda *_, **__: _Response(content=drifted), sleep=lambda _s: None)
        self.assertEqual(caught.exception.kind, "malformed_response")
        sleeps = []
        with self.assertRaisesRegex(CvmApiError, "ZIP"):
            list_filings_for_year(2026, http_get=lambda *_, **__: _Response(content=b"not a zip"), sleep=sleeps.append)
        self.assertEqual(len(sleeps), 2)
        with self.assertRaises(ValueError):
            list_filings_for_year(1999)

    def test_rate_limit_is_bounded_and_does_not_produce_cursor(self):
        sleeps = []
        with self.assertRaisesRegex(CvmApiError, "rate limited") as caught:
            list_filings_for_year(2026, http_get=lambda *_, **__: _Response(status_code=429), sleep=sleeps.append)
        self.assertEqual(caught.exception.kind, "rate_limited")
        self.assertEqual(len(sleeps), 2)
        self.assertIsNone(next_cursor_after_success(2026, object()))

    def test_cursor_is_newest_delivery_date_only_for_matching_complete_year(self):
        result = list_filings_for_year(2026, http_get=lambda *_, **__: _Response(content=_fixture_zip()))
        self.assertEqual(next_cursor_after_success(2026, result), "2026-02-11")
        self.assertIsNone(next_cursor_after_success(2025, result))
        empty = list_filings_for_year(
            2026,
            categories=("Categoria Inexistente",),
            http_get=lambda *_, **__: _Response(content=_fixture_zip()),
        )
        self.assertEqual(empty.filings, ())
        self.assertIsNone(next_cursor_after_success(2026, empty))

    def test_document_url_only_accepts_official_https_cvm_hosts(self):
        self.assertEqual(document_url(DOC_URL), DOC_URL)
        for bad in ("http://www.rad.cvm.gov.br/doc", "https://evil.example.com/doc",
                    "https://fakecvm.gov.br/doc", "", "https://www.rad.cvm.gov.br/a b"):
            with self.assertRaises(ValueError):
                document_url(bad)


if __name__ == "__main__":
    unittest.main()
