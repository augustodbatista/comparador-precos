"""
Modelos de domínio do cupom fiscal (NFC-e).

Usados tanto como corpo de entrada (POST /receipts) quanto como formato de
saída (GET/POST /receipts) — o cupom persistido é literalmente o mesmo
formato que foi recebido, não um DTO derivado.
"""
from datetime import datetime

from pydantic import BaseModel


class IssuerData(BaseModel):
    """Dados do estabelecimento emissor da nota."""
    name: str
    cnpj: str
    address: str


class ItemData(BaseModel):
    """Um item (produto) da nota fiscal."""
    code: str                          # código interno da loja
    description: str                   # nome bruto da SEFAZ (caixa alta, abreviado)
    normalized_name: str | None = None # nome normalizado pelo Ollama (None antes de salvar)
    qty: float
    unit: str
    unit_price: float
    total: float


class TotalsData(BaseModel):
    """Totais da nota fiscal."""
    total: float
    paid: float
    items_count: int


class InvoiceData(BaseModel):
    """Dados da nota fiscal (número, série, modelo, data de emissão)."""
    model: str
    series: str
    number: str
    issued_at: str  # formato ISO: "YYYY-MM-DDTHH:MM:SS"


class ReceiptData(BaseModel):
    """Representação completa de um cupom fiscal.

    created_at é None quando o cupom vem direto da SEFAZ (GET ?url=) e
    preenchido quando vem do banco (histórico ou após POST).
    Pydantic ignora created_at no body do POST — o banco sempre sobrescreve com datetime.now().
    """
    access_key: str
    url: str
    issuer: IssuerData
    items: list[ItemData]
    totals: TotalsData
    invoice: InvoiceData
    created_at: datetime | None = None
