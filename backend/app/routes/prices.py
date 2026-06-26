"""
Endpoints de consulta de preços e catálogo de produtos.

GET /products              — lista todos os produtos do catálogo
GET /prices/latest         — último preço registrado para um produto
GET /prices/lowest         — menor preço já visto para um produto
GET /prices/history        — histórico completo de preços de um produto
GET /health/ollama         — verifica se o Ollama está acessível
"""
import os

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db.repositories.prices import get_latest_price, get_lowest_price, get_price_history
from app.db.repositories.products import list_products

router = APIRouter()


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class ProductItem(BaseModel):
    """Produto do catálogo retornado por GET /products."""
    normalized_name: str  # nome legível gerado pelo Ollama (usado como product_id nas queries)


class PriceResponse(BaseModel):
    """Resposta completa de uma consulta de preço.

    Contém dados do produto, da compra (quantidade, preço), da nota fiscal
    e da loja — tudo em um único documento para evitar joins no cliente.
    """
    product_id: str           # = normalized_name (chave de busca cross-store)
    description: str          # nome bruto original da SEFAZ (para auditoria)
    normalized_name: str | None

    unit_price: float
    quantity: float
    unit: str
    total_value: float

    purchase_date: str        # data de emissão da nota (ISO format)
    invoice_number: str
    invoice_series: str
    invoice_model: str

    issuer_name: str          # nome do estabelecimento
    issuer_cnpj: str
    issuer_address: str

    receipt_access_key: str   # chave de acesso de 44 dígitos da NF-e
    receipt_url: str          # URL do QR Code (para link direto ao cupom na SEFAZ)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/products", response_model=list[ProductItem])
async def list_products_endpoint(request: Request) -> list[ProductItem]:
    """Lista todos os produtos únicos do catálogo em ordem alfabética.

    Usado pelo frontend para popular a lista de busca na tela de Preços.
    """
    db = request.app.state.db
    products = await list_products(db)
    return [ProductItem(**p) for p in products]


@router.get("/prices/latest", response_model=PriceResponse)
async def read_latest_price(
    request: Request,
    product_id: str = Query(..., description="normalized_name do produto"),
) -> PriceResponse:
    """Retorna o último preço registrado para o produto (purchase_date mais recente).

    product_id deve ser o normalized_name exato retornado por GET /products.
    """
    db = request.app.state.db
    result = await get_latest_price(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return PriceResponse(**result)


@router.get("/prices/lowest", response_model=PriceResponse)
async def read_lowest_price(
    request: Request,
    product_id: str = Query(..., description="normalized_name do produto"),
) -> PriceResponse:
    """Retorna o menor preço unitário já registrado para o produto entre todas as lojas.

    Em caso de empate de preço, retorna o registro mais recente.
    """
    db = request.app.state.db
    result = await get_lowest_price(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return PriceResponse(**result)


@router.get("/prices/history", response_model=list[PriceResponse])
async def read_price_history(
    request: Request,
    product_id: str = Query(..., description="normalized_name do produto"),
    limit: int = Query(50, ge=1, le=200),
) -> list[PriceResponse]:
    """Retorna o histórico completo de preços do produto, do mais recente ao mais antigo.

    O parâmetro limit controla quantos registros retornar (máx. 200).
    Usado pelo botão "Ver todos os preços" na tela de Preços do frontend.
    """
    db = request.app.state.db
    results = await get_price_history(db, product_id, limit=limit)
    if not results:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return [PriceResponse(**r) for r in results]


# ---------------------------------------------------------------------------
# Health check do Ollama
# ---------------------------------------------------------------------------

class OllamaHealthResponse(BaseModel):
    status: str  # "ok" | "offline"
    url: str
    reason: str  # "ok" | "api_key_missing" | "http_error" | "timeout" | "connection_error"


@router.get("/health/ollama", response_model=OllamaHealthResponse)
async def ollama_health() -> OllamaHealthResponse:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return OllamaHealthResponse(status="offline", url="groq", reason="api_key_missing")
    return OllamaHealthResponse(status="ok", url="groq", reason="ok")
