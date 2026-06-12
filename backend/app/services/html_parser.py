"""
Parser de HTML da SEFAZ para extração de dados estruturados de NFC-e.
Suporta: MG (portalsped.fazenda.mg.gov.br)
"""
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup


class ParseError(Exception):
    """Lançado quando o HTML não contém a estrutura esperada de uma NFC-e."""


def parse_nfce_html(html: str) -> dict[str, Any]:
    """Extrai issuer, items, totals e invoice do HTML retornado pela SEFAZ."""
    soup = BeautifulSoup(html, "html.parser")

    # Tenta detectar o estado pelo domínio ou estrutura e delega ao parser correto.
    # Por ora só MG é suportado; SP será adicionado quando tivermos fixture real.
    if _is_mg(soup):
        return _parse_mg(soup)

    raise ParseError("Estrutura de HTML não reconhecida — estado não suportado")


# ---------------------------------------------------------------------------
# detecção de estado
# ---------------------------------------------------------------------------

def _is_mg(soup: BeautifulSoup) -> bool:
    """MG usa <tbody id="myTable"> para a tabela de itens."""
    return soup.find("tbody", id="myTable") is not None


# ---------------------------------------------------------------------------
# parser MG
# ---------------------------------------------------------------------------

def _parse_mg(soup: BeautifulSoup) -> dict[str, Any]:
    return {
        "issuer": _mg_issuer(soup),
        "items": _mg_items(soup),
        "totals": _mg_totals(soup),
        "invoice": _mg_invoice(soup),
    }


def _mg_issuer(soup: BeautifulSoup) -> dict[str, str]:
    # O emitente fica na primeira tabela com class "table text-center"
    table = soup.find("table", class_="text-center")
    if not table:
        raise ParseError("Tabela de emitente não encontrada")

    # Nome: <th class="text-uppercase"> > H4 > b
    name_tag = table.find("th", class_="text-uppercase")
    name = name_tag.get_text(strip=True) if name_tag else ""
    if not name:
        raise ParseError("Nome do emitente não encontrado")

    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else []
    if len(rows) < 2:
        raise ParseError("Dados do emitente incompletos")

    # Linha 0: "CNPJ: 21253729001979 -, Inscrição Estadual: ..."
    cnpj_text = rows[0].get_text(strip=True)
    cnpj_match = re.search(r"CNPJ:\s*(\d+)", cnpj_text)
    cnpj = cnpj_match.group(1) if cnpj_match else ""

    # Linha 1: endereço em itálico
    address = rows[1].get_text(strip=True)

    return {"name": name, "cnpj": cnpj, "address": address}


def _mg_items(soup: BeautifulSoup) -> list[dict[str, Any]]:
    tbody = soup.find("tbody", id="myTable")
    if not tbody:
        raise ParseError("Tabela de itens (myTable) não encontrada")

    items = []
    for row in tbody.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 4:
            continue

        # td[0]: <h7>NOME</h7>(Código: X)
        td0_text = tds[0].get_text(separator="|", strip=True)
        # separador "|" garante que nome e código fiquem separados mesmo sem espaço
        name_part, _, code_part = td0_text.partition("(Código:")
        description = name_part.strip(" |")
        code = code_part.rstrip(")").strip()

        # td[1]: "Qtde total de ítens: 1.000"
        qty_text = tds[1].get_text(strip=True)
        qty_match = re.search(r"[\d]+[.,][\d]+", qty_text)
        qty = float(qty_match.group().replace(",", ".")) if qty_match else 0.0

        # td[2]: "UN: TP"
        unit_text = tds[2].get_text(strip=True)
        unit = unit_text.replace("UN:", "").strip()

        # td[3]: "Valor total R$: R$ 7,99"
        total_text = tds[3].get_text(strip=True)
        total_match = re.search(r"R\$\s*([\d]+[.,][\d]+)", total_text)
        total = float(total_match.group(1).replace(",", ".")) if total_match else 0.0

        # MG não exibe preço unitário — calculado a partir de total / qty
        unit_price = round(total / qty, 4) if qty else 0.0

        items.append({
            "code": code,
            "description": description,
            "qty": qty,
            "unit": unit,
            "unit_price": unit_price,
            "total": total,
        })

    if not items:
        raise ParseError("Nenhum item encontrado na nota")

    return items


def _mg_totals(soup: BeautifulSoup) -> dict[str, Any]:
    # Totais ficam em div.row com rótulos em <strong> seguidos do valor em outro div
    totals: dict[str, Any] = {"total": 0.0, "paid": 0.0, "items_count": 0}

    for row_div in soup.find_all("div", class_="row"):
        label = row_div.get_text(separator="|", strip=True)

        if "Qtde total de" in label:
            # O valor numérico fica em div.col-lg-2 > strong
            val_div = row_div.find("div", class_=re.compile(r"col-lg-2"))
            if val_div:
                totals["items_count"] = int(val_div.get_text(strip=True))

        elif "Valor total R$" in label and "Valor pago" not in label:
            val_div = row_div.find("div", class_=re.compile(r"col-lg-2"))
            if val_div:
                totals["total"] = float(val_div.get_text(strip=True).replace(",", "."))

        elif "Valor pago R$" in label:
            val_div = row_div.find("div", class_=re.compile(r"col-lg-2"))
            if val_div:
                totals["paid"] = float(val_div.get_text(strip=True).replace(",", "."))

    return totals


def _mg_invoice(soup: BeautifulSoup) -> dict[str, str]:
    # Número, série, modelo e data ficam em tabela com cabeçalho "Modelo | Série | Número | Data Emissão"
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Modelo" in headers and "Número" in headers and "Data Emissão" in headers:
            row = table.find("tbody").find("tr")
            if not row:
                continue
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue
            # Converte "07/06/2026 11:36:44" → "2026-06-07T11:36:44"
            issued_at = _parse_br_datetime(cells[3])
            return {
                "model": cells[0],
                "series": cells[1],
                "number": cells[2],
                "issued_at": issued_at,
            }

    raise ParseError("Dados da nota fiscal não encontrados")


def _parse_br_datetime(value: str) -> str:
    """Converte 'DD/MM/YYYY HH:MM:SS' para 'YYYY-MM-DDTHH:MM:SS'."""
    try:
        dt = datetime.strptime(value.strip(), "%d/%m/%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return value
