"""
Testes para html_parser.py — extração de dados estruturados do HTML da SEFAZ.
Fixture: tests/fixtures/mg_sefaz.html (HTML real da SEFAZ MG, Casa Rena S/A, 07/06/2026)
"""
from pathlib import Path

import pytest

from app.services.html_parser import ParseError, parse_nfce_html

FIXTURES = Path(__file__).parent / "fixtures"
MG_HTML = (FIXTURES / "mg_sefaz.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# issuer
# ---------------------------------------------------------------------------

def test_issuer_name():
    result = parse_nfce_html(MG_HTML)
    assert result["issuer"]["name"] == "CASA RENA S/A"


def test_issuer_cnpj():
    result = parse_nfce_html(MG_HTML)
    assert result["issuer"]["cnpj"] == "21253729001979"


def test_issuer_address_contains_city():
    result = parse_nfce_html(MG_HTML)
    assert "PARA DE MINAS" in result["issuer"]["address"]


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------

def test_items_count():
    result = parse_nfce_html(MG_HTML)
    # 13 itens visíveis na tabela myTable (SUCO, H2OH, CAMPO LARGO, CEBOLA,
    # CEBOLINHA, POMAROLA x2, TOMATE, HERSHEYS, AGUA SAO L, PAO VALE, QJO PARM,
    # MAC AMALIA, PAO RENA, AGUA MINALBA — 15 linhas, 2 delas são POMAROLA repetida)
    assert len(result["items"]) == 15


def test_first_item_description():
    result = parse_nfce_html(MG_HTML)
    assert result["items"][0]["description"] == "SUCO D VALLE MA+S 1L"


def test_first_item_code():
    result = parse_nfce_html(MG_HTML)
    assert result["items"][0]["code"] == "5173"


def test_first_item_qty():
    result = parse_nfce_html(MG_HTML)
    assert result["items"][0]["qty"] == pytest.approx(1.0)


def test_first_item_unit():
    result = parse_nfce_html(MG_HTML)
    assert result["items"][0]["unit"] == "TP"


def test_first_item_total():
    result = parse_nfce_html(MG_HTML)
    assert result["items"][0]["total"] == pytest.approx(7.99)


def test_first_item_unit_price_calculated():
    # unit_price = total / qty (MG não exibe preço unitário diretamente)
    result = parse_nfce_html(MG_HTML)
    assert result["items"][0]["unit_price"] == pytest.approx(7.99)


def test_weighted_item_unit_price():
    # Cebola: qty=0.550, total=2.74 → unit_price ≈ 4.98
    cebola = next(i for i in parse_nfce_html(MG_HTML)["items"] if "CEBOLA" in i["description"])
    assert cebola["unit_price"] == pytest.approx(2.74 / 0.550, rel=1e-3)


# ---------------------------------------------------------------------------
# totals
# ---------------------------------------------------------------------------

def test_totals_total():
    result = parse_nfce_html(MG_HTML)
    assert result["totals"]["total"] == pytest.approx(124.10)


def test_totals_paid():
    result = parse_nfce_html(MG_HTML)
    assert result["totals"]["paid"] == pytest.approx(124.10)


def test_totals_items_count():
    result = parse_nfce_html(MG_HTML)
    assert result["totals"]["items_count"] == 15


# ---------------------------------------------------------------------------
# invoice
# ---------------------------------------------------------------------------

def test_invoice_number():
    result = parse_nfce_html(MG_HTML)
    assert result["invoice"]["number"] == "34772"


def test_invoice_series():
    result = parse_nfce_html(MG_HTML)
    assert result["invoice"]["series"] == "14"


def test_invoice_model():
    result = parse_nfce_html(MG_HTML)
    assert result["invoice"]["model"] == "65"


def test_invoice_issued_at():
    result = parse_nfce_html(MG_HTML)
    assert result["invoice"]["issued_at"] == "2026-06-07T11:36:44"


# ---------------------------------------------------------------------------
# erro
# ---------------------------------------------------------------------------

def test_parse_error_on_empty_html():
    with pytest.raises(ParseError):
        parse_nfce_html("<html><body></body></html>")
