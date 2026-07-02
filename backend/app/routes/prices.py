"""
Endpoints de consulta de preços e catálogo de produtos.

GET /products              — lista todos os produtos do catálogo
GET /prices/latest         — último preço registrado para um produto
GET /prices/lowest         — menor preço já visto para um produto
GET /prices/history        — histórico completo de preços de um produto
GET /health/ollama         — verifica se o Ollama está acessível
"""
import os

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from app.views.price import ProductItem, PriceResponse
from app.views.health import OllamaHealthResponse
from app.repositories.prices import get_latest_price, get_lowest_price, get_price_history
from app.repositories.products import list_products

router = APIRouter()


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

@router.get("/health/ollama", response_model=OllamaHealthResponse)
async def ollama_health() -> OllamaHealthResponse:
    """Verifica se a Groq API está configurada e a chave é válida.

    Timeout/erro de rede é tratado como "ok" (benefício da dúvida) — só um 401
    (chave inválida/revogada) é reportado como falha, para não gerar falsos
    negativos por instabilidade transitória da Groq.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return OllamaHealthResponse(status="offline", url="groq", reason="api_key_missing")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code == 401:
            return OllamaHealthResponse(status="offline", url="groq", reason="http_error")
    except Exception:
        pass
    return OllamaHealthResponse(status="ok", url="groq", reason="ok")
