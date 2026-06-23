from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from app.db.repositories.prices import insert_prices
from app.db.repositories.products import upsert_product
from app.db.repositories.receipts import find_by_access_key, insert_receipt, list_receipts
from app.services.html_parser import ParseError, parse_nfce_html
from app.services.nfce_fetcher import NfceFetchError, fetch_nfce_html
from app.services.normalizer import normalize_items
from app.services.qr_parser import parse_qr_nfce

router = APIRouter()


class IssuerData(BaseModel):
    name: str
    cnpj: str
    address: str


class ItemData(BaseModel):
    code: str
    description: str
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
    access_key: str
    url: str
    issuer: IssuerData
    items: list[ItemData]
    totals: TotalsData
    invoice: InvoiceData
    created_at: datetime | None = None


@router.get("/receipts", response_model=ReceiptData | list[ReceiptData])
async def get_receipts(
    request: Request,
    url: str | None = Query(None, description="URL do QR Code da NFC-e"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> ReceiptData | list[ReceiptData]:
    """Lista o histórico salvo ou consulta uma URL de QR Code."""
    db = request.app.state.db

    if url is None:
        docs = await list_receipts(db, limit=limit, skip=skip)
        return [ReceiptData(**doc) for doc in docs]

    nfce_data = parse_qr_nfce(url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

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


@router.post("/receipts", response_model=ReceiptData, status_code=201)
async def save_receipt(body: ReceiptData, request: Request, response: Response) -> ReceiptData:
    """Persiste um cupom: cabeçalho em 'receipts', itens em 'prices', produtos em 'products'.

    - 201: cupom salvo com sucesso
    - 200: cupom já existia no banco (idempotente)
    """
    db = request.app.state.db

    # Normaliza os nomes via Ollama. Fallback retorna descriptions originais se Ollama estiver fora.
    descriptions = [item.description for item in body.items]
    normalized = await normalize_items(descriptions)
    items = [
        item.model_copy(update={"normalized_name": name})
        for item, name in zip(body.items, normalized)
    ]
    body = body.model_copy(update={"items": items})

    # Tenta inserir o cabeçalho. DuplicateKeyError = cupom já existe.
    try:
        inserted_header = await insert_receipt(db, body.model_dump())
    except DuplicateKeyError:
        response.status_code = 200
        existing = await find_by_access_key(db, body.access_key)
        return ReceiptData(**existing)

    # Cadastra produtos novos no catálogo (idempotente via upsert)
    for item in items:
        await upsert_product(db, item.normalized_name or item.description)

    # Insere um registro de preço por item
    await insert_prices(db, body.model_dump(), [item.model_dump() for item in items])

    return body.model_copy(update={"created_at": inserted_header["created_at"]})
