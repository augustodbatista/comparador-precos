"""
Endpoints de cupons fiscais (NFC-e).

GET  /receipts         — lista histórico salvo no banco
GET  /receipts?url=... — busca um cupom na SEFAZ pelo QR Code
POST /receipts         — salva um cupom no banco com normalização de nomes
"""
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


# ---------------------------------------------------------------------------
# Modelos Pydantic — definem o contrato da API (request e response body)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/receipts", response_model=ReceiptData | list[ReceiptData])
async def get_receipts(
    request: Request,
    url: str | None = Query(None, description="URL do QR Code da NFC-e"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> ReceiptData | list[ReceiptData]:
    """Consulta ou lista cupons.

    Sem ?url → retorna o histórico salvo no banco (paginado).
    Com ?url  → busca a nota na SEFAZ, parseia e retorna (sem salvar).
               Se a chave já existir no banco, retorna o registro salvo diretamente.
    """
    db = request.app.state.db

    # Sem URL: retorna histórico paginado do banco
    if url is None:
        docs = await list_receipts(db, limit=limit, skip=skip)
        return [ReceiptData(**doc) for doc in docs]

    # Valida e extrai a chave de acesso do QR Code
    nfce_data = parse_qr_nfce(url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

    # Se o cupom já estiver no banco, retorna sem chamar a SEFAZ
    existing = await find_by_access_key(db, nfce_data.access_key)
    if existing:
        return ReceiptData(**existing)

    # Busca o HTML na SEFAZ simulando um browser mobile
    try:
        html = await fetch_nfce_html(nfce_data.url)
    except NfceFetchError as e:
        raise HTTPException(status_code=502, detail=f"SEFAZ retornou erro: {e.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao acessar a SEFAZ")

    # Parseia o HTML e extrai os dados estruturados
    try:
        parsed = parse_nfce_html(html)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=f"Não foi possível extrair dados da nota: {e}")

    # Retorna os dados sem salvar — o frontend decide se vai chamar POST /receipts
    return ReceiptData(access_key=nfce_data.access_key, url=nfce_data.url, **parsed)


@router.post("/receipts", response_model=ReceiptData, status_code=201)
async def save_receipt(body: ReceiptData, request: Request, response: Response) -> ReceiptData:
    """Persiste um cupom no banco com normalização dos nomes via Ollama.

    Fluxo:
    1. Normaliza os nomes dos itens via Ollama (fallback silencioso se Ollama estiver fora)
    2. Tenta inserir o cabeçalho em 'receipts'
       - DuplicateKeyError → cupom já existe → retorna 200 com o registro existente
    3. Registra cada item como preço em 'prices'
    4. Cadastra produtos novos em 'products'

    Status codes:
    - 201: cupom salvo com sucesso
    - 200: cupom já existia no banco (idempotente — nenhum dado duplicado)
    """
    db = request.app.state.db

    # Extrai as descrições brutas e normaliza via Ollama em um único batch
    # Fallback: se Ollama estiver fora, normalized_name = description original
    descriptions = [item.description for item in body.items]
    normalized = await normalize_items(descriptions)

    # Substitui o normalized_name de cada item pelo resultado do Ollama
    items = [
        item.model_copy(update={"normalized_name": name})
        for item, name in zip(body.items, normalized)
    ]
    body = body.model_copy(update={"items": items})

    # Tenta inserir o cabeçalho. DuplicateKeyError = cupom já existe no banco.
    # Fluxo novo (try/insert) em vez de find/check para economizar 1 round-trip no caminho feliz.
    try:
        inserted_header = await insert_receipt(db, body.model_dump())
    except DuplicateKeyError:
        # Cupom duplicado: retorna 200 com os dados já salvos
        response.status_code = 200
        existing = await find_by_access_key(db, body.access_key)
        return ReceiptData(**existing)

    # Cadastra produtos novos no catálogo (idempotente via upsert — duplicatas são ignoradas)
    for item in items:
        await upsert_product(db, item.normalized_name or item.description)

    # Insere um documento de preço para cada item do cupom
    await insert_prices(db, body.model_dump(), [item.model_dump() for item in items])

    # Retorna o cupom salvo com o created_at preenchido pelo banco
    return body.model_copy(update={"created_at": inserted_header["created_at"]})
