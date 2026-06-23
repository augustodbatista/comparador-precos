from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from app.db.repositories.receipts import find_by_access_key, insert_receipt, list_receipts
from app.services.html_parser import ParseError, parse_nfce_html
from app.services.nfce_fetcher import NfceFetchError, fetch_nfce_html
from app.services.normalizer import normalize_items
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
    # Preenchido pelo normalizer (Ollama) no momento do insert.
    # None em cupons antigos salvos antes da Task 6.
    normalized_name: str | None = None
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
    # None quando o cupom vem fresco da SEFAZ; preenchido pelo banco ao salvar.
    # Campo opcional para que o mesmo modelo sirva tanto ao GET /receipts?url=
    # (sem timestamp) quanto ao histórico (com timestamp) — evita uma subclasse
    # ReceiptHistoryItem que existia só por causa deste único campo.
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# GET /receipts
# Sem url: lista o histórico salvo no MongoDB.
# Com url: busca o HTML na SEFAZ, parseia com BS4 e retorna JSON estruturado.
# Não salva no banco — o frontend exibe os dados e o usuário decide salvar.
# Se o cupom já estiver no banco, retorna os dados salvos sem chamar a SEFAZ.
# ---------------------------------------------------------------------------

@router.get("/receipts", response_model=ReceiptData | list[ReceiptData])
async def get_receipts(
    request: Request,
    url: str | None = Query(None, description="URL do QR Code da NFC-e"),
    limit: int = Query(50, ge=1, le=100, description="Quantidade máxima de cupons no histórico"),
    skip: int = Query(0, ge=0, description="Quantidade de cupons a pular no histórico"),
) -> ReceiptData | list[ReceiptData]:
    """Lista o histórico salvo ou consulta uma URL de QR Code.

    Mapeamento de erros:
    - 422: URL não é uma NFC-e válida, ou HTML não reconhecido
    - 502: SEFAZ retornou erro HTTP
    - 504: Timeout ao acessar a SEFAZ
    """
    db = request.app.state.db

    if url is None:
        docs = await list_receipts(db, limit=limit, skip=skip)
        # Docs do banco sempre têm created_at; ReceiptData aceita porque o campo é opcional.
        return [ReceiptData(**doc) for doc in docs]

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

    # Normaliza os nomes antes do insert. Pode levar 30-50s em CPU com qwen2.5:7b;
    # o fallback retorna os nomes originais se o Ollama estiver indisponível.
    descriptions = [item.description for item in body.items]
    normalized = await normalize_items(descriptions)
    items = [
        item.model_copy(update={"normalized_name": name})
        for item, name in zip(body.items, normalized)
    ]
    body = body.model_copy(update={"items": items})

    try:
        # Caminho feliz (novo cupom): uma única ida ao banco.
        # insert_receipt adiciona created_at e retorna o doc inserido.
        inserted = await insert_receipt(db, body.model_dump())
        return ReceiptData(**inserted)
    except DuplicateKeyError:
        # access_key já existe — o índice único do MongoDB detecta a colisão.
        # Buscamos o doc salvo para devolvê-lo inteiro (pode ter created_at diferente
        # do body recebido). Status 200 sinaliza "já existia" ao frontend.
        response.status_code = 200
        existing = await find_by_access_key(db, body.access_key)
        return ReceiptData(**existing)
