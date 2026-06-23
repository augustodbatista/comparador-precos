from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db.repositories.prices import get_all_products, get_latest_price, get_lowest_price

router = APIRouter()


class ProductItem(BaseModel):
    description: str        # descrição bruta original da SEFAZ (sempre presente)
    normalized_name: str | None  # nome limpo pelo Ollama (None se não normalizado)


class PriceResponse(BaseModel):
    # Identificação do produto
    product_id: str        # normalized_name usado na busca
    description: str       # descrição bruta original da SEFAZ
    normalized_name: str | None  # nome limpo gerado pelo Ollama

    # Dados do item
    unit_price: float
    quantity: float
    unit: str
    total_value: float

    # Dados da nota fiscal
    purchase_date: str     # invoice.issued_at (ISO 8601)
    invoice_number: str
    invoice_series: str
    invoice_model: str

    # Dados do estabelecimento
    issuer_name: str
    issuer_cnpj: str
    issuer_address: str    # identifica a filial específica da rede

    # Rastreabilidade
    receipt_access_key: str
    receipt_url: str       # link direto ao cupom na SEFAZ


@router.get("/products", response_model=list[ProductItem])
async def list_products(request: Request) -> list[ProductItem]:
    """Lista todos os produtos únicos salvos no banco.

    Usado pelo frontend para exibir os produtos disponíveis para consulta de preços,
    eliminando a necessidade de o usuário saber o código ou nome exato de memória.
    """
    db = request.app.state.db
    products = await get_all_products(db)
    return [ProductItem(**p) for p in products]


@router.get("/prices/latest", response_model=PriceResponse)
async def read_latest_price(
    request: Request,
    product_id: str = Query(..., description="ID/código do produto")
) -> PriceResponse:
    """Retorna o último preço registrado para o produto."""
    db = request.app.state.db
    result = await get_latest_price(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return PriceResponse(**result)


@router.get("/prices/lowest", response_model=PriceResponse)
async def read_lowest_price(
    request: Request,
    product_id: str = Query(..., description="ID/código do produto")
) -> PriceResponse:
    """Retorna o menor preço já visto para o produto entre todas as lojas."""
    db = request.app.state.db
    result = await get_lowest_price(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return PriceResponse(**result)
