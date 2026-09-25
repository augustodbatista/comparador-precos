"""
Endpoints de cupons fiscais (NFC-e).

GET  /receipts         — lista histórico salvo no banco (do usuário autenticado)
GET  /receipts?url=... — busca um cupom na SEFAZ pelo QR Code
POST /receipts         — salva um cupom no banco com normalização de nomes
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pymongo.errors import DuplicateKeyError

from app.controllers.auth import get_current_user
from app.controllers.dependencies import exigir_banco_pronto
from app.models.receipt import ReceiptData
from app.repositories.prices import insert_prices, find_product_ids_by_description
from app.repositories.products import upsert_product, list_all_product_names
from app.repositories.receipts import find_any_by_access_key, find_by_access_key_for_user, insert_receipt, list_receipts
from app.services.html_parser import ParseError, parse_nfce_html
from app.services.nfce_fetcher import NfceFetchError, fetch_nfce_html
from app.services.normalizer import normalize_items, pre_process, is_regression
from app.services.qr_parser import parse_qr_nfce

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/receipts", response_model=ReceiptData | list[ReceiptData])
async def get_receipts(
    request: Request,
    current_user: str = Depends(get_current_user),
    url: str | None = Query(None, description="URL do QR Code da NFC-e"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> ReceiptData | list[ReceiptData]:
    """Consulta ou lista cupons DO USUÁRIO AUTENTICADO.

    Sem ?url → retorna o histórico salvo no banco (paginado), só os cupons deste usuário.
    Com ?url  → busca a nota na SEFAZ, parseia e retorna (sem salvar).
               Se ESTE usuário já tiver essa chave salva, retorna o registro salvo direto.
               Se pertencer a outro usuário, comporta-se como cupom novo (rebusca na SEFAZ).
    """
    db = request.app.state.db

    if url is None:
        docs = await list_receipts(db, current_user, limit=limit, skip=skip)
        return [ReceiptData(**doc) for doc in docs]

    nfce_data = parse_qr_nfce(url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

    # Só reaproveita cache se o cupom é DESTE usuário — de outro dono, comporta-se como novo
    existing = await find_by_access_key_for_user(db, nfce_data.access_key, current_user)
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
async def save_receipt(
    body: ReceiptData,
    request: Request,
    response: Response,
    current_user: str = Depends(get_current_user),
    _: None = Depends(exigir_banco_pronto),
) -> ReceiptData:
    """Persiste um cupom no banco (associado ao usuário autenticado) com normalização de nomes.

    Fluxo:
    1. Normaliza os nomes dos itens via Ollama (fallback silencioso se Ollama estiver fora)
    2. Tenta inserir o cabeçalho em 'receipts', associado ao current_user
       - DuplicateKeyError, mesmo dono → cupom já existe → retorna 200 (idempotente)
       - DuplicateKeyError, outro dono → 409, sem devolver os dados do dono original
    3. Registra cada item como preço em 'prices' (coleção compartilhada entre usuários)
    4. Cadastra produtos novos em 'products' (catálogo compartilhado)

    Status codes:
    - 201: cupom salvo com sucesso
    - 200: cupom já existia no banco PARA ESTE USUÁRIO (idempotente — nenhum dado duplicado)
    - 409: cupom já existe, mas pertence a outra conta
    """
    db = request.app.state.db

    descriptions = [item.description for item in body.items]
    existing_names = await list_all_product_names(db)
    normalized = await normalize_items(descriptions, existing_names)

    current_product_ids = await find_product_ids_by_description(db, descriptions)
    final_names = []
    for desc, norm in zip(descriptions, normalized):
        current = current_product_ids.get(desc)
        if current and (norm == pre_process(desc) or is_regression(norm, current)):
            final_names.append(current)
        else:
            final_names.append(norm)

    items = [
        item.model_copy(update={"normalized_name": name})
        for item, name in zip(body.items, final_names)
    ]
    body = body.model_copy(update={"items": items})

    try:
        inserted_header = await insert_receipt(db, body.model_dump(), user_id=current_user)
    except DuplicateKeyError:
        existing = await find_any_by_access_key(db, body.access_key)
        if existing and existing.get("user_id") == current_user:
            # Reenvio idempotente do próprio usuário (ex.: duplo clique) — comportamento preservado
            response.status_code = 200
            return ReceiptData(**existing)
        # Chave já pertence a OUTRO usuário — nunca retorna os dados dele
        raise HTTPException(status_code=409, detail="Este cupom já foi salvo por outra conta.")

    for item in items:
        await upsert_product(db, item.normalized_name or item.description)

    await insert_prices(db, body.model_dump(), [item.model_dump() for item in items])

    return body.model_copy(update={"created_at": inserted_header["created_at"]})
