from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from app.db.repositories.receipts import find_by_access_key, insert_receipt, list_receipts
from app.services.html_parser import ParseError, parse_nfce_html
from app.services.nfce_fetcher import NfceFetchError, fetch_nfce_html
from app.services.qr_parser import parse_qr_nfce

router = APIRouter()


# ---------------------------------------------------------------------------
# Modelos compartilhados
# ---------------------------------------------------------------------------

class IssuerData(BaseModel):
    name: str
    cnpj: str
    address: str


class ItemData(BaseModel):
    code: str
    description: str
    qty: float
    unit: str
    unit_price: float
    total: float


class TotalsData(BaseModel):
    total: float
    paid: float
    items_count: int


class InvoiceData(BaseModel):
    model: str
    series: str
    number: str
    issued_at: str


class ReceiptData(BaseModel):
    """Dados estruturados de um cupom fiscal — retornados pelo GET e enviados no POST."""
    access_key: str
    url: str
    issuer: IssuerData
    items: list[ItemData]
    totals: TotalsData
    invoice: InvoiceData


class ReceiptHistoryItem(ReceiptData):
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# GET /receipts
# Sem url: lista o histórico salvo no MongoDB.
# Com url: busca o HTML na SEFAZ, parseia com BS4 e retorna JSON estruturado.
# Não salva no banco — o frontend exibe os dados e o usuário decide salvar.
# Se o cupom já estiver no banco, retorna os dados salvos sem chamar a SEFAZ.
# ---------------------------------------------------------------------------

@router.get("/receipts", response_model=ReceiptData | list[ReceiptHistoryItem])
async def get_receipts(
    request: Request,
    url: str | None = Query(None, description="URL do QR Code da NFC-e"),
    limit: int = Query(50, ge=1, le=100, description="Quantidade máxima de cupons no histórico"),
    skip: int = Query(0, ge=0, description="Quantidade de cupons a pular no histórico"),
) -> ReceiptData | list[ReceiptHistoryItem]:
    """Lista o histórico salvo ou consulta uma URL de QR Code.

    Mapeamento de erros:
    - 422: URL não é uma NFC-e válida, ou HTML não reconhecido
    - 502: SEFAZ retornou erro HTTP
    - 504: Timeout ao acessar a SEFAZ
    """
    db = request.app.state.db

    if url is None:
        docs = await list_receipts(db, limit=limit, skip=skip)
        return [ReceiptHistoryItem(**doc) for doc in docs]

    nfce_data = parse_qr_nfce(url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

    # Cupom já salvo anteriormente — retorna do banco sem re-buscar na SEFAZ
    existing = await find_by_access_key(db, nfce_data.access_key)
    if existing:
        return ReceiptData(**existing)

    try:
        html = await fetch_nfce_html(nfce_data.url)
    except NfceFetchError as e:
        raise HTTPException(status_code=502, detail=f"SEFAZ retornou erro: {e.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao acessar a SEFAZ")

    try:
        parsed = parse_nfce_html(html)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=f"Não foi possível extrair dados da nota: {e}")

    return ReceiptData(access_key=nfce_data.access_key, url=nfce_data.url, **parsed)


# ---------------------------------------------------------------------------
# POST /receipts
# Recebe os dados já parseados (vindos do GET) e salva no MongoDB.
# Acionado quando o usuário clica em "Salvar" no frontend.
# ---------------------------------------------------------------------------

@router.post("/receipts", response_model=ReceiptData, status_code=201)
async def save_receipt(body: ReceiptData, request: Request, response: Response) -> ReceiptData:
    """Persiste um cupom fiscal no MongoDB.

    - 201: cupom salvo com sucesso
    - 200: cupom já existia no banco (idempotente)
    """
    db = request.app.state.db

    # Idempotência: se já existe, retorna sem duplicar
    existing = await find_by_access_key(db, body.access_key)
    if existing:
        response.status_code = 200
        return ReceiptData(**existing)

    doc = body.model_dump()
    await insert_receipt(db, doc)
    return body
