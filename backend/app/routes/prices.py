from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db.repositories.prices import get_latest_price, get_lowest_price, get_price_history
from app.db.repositories.products import list_products

router = APIRouter()


class ProductItem(BaseModel):
    normalized_name: str


class PriceResponse(BaseModel):
    product_id: str
    description: str
    normalized_name: str | None

    unit_price: float
    quantity: float
    unit: str
    total_value: float

    purchase_date: str
    invoice_number: str
    invoice_series: str
    invoice_model: str

    issuer_name: str
    issuer_cnpj: str
    issuer_address: str

    receipt_access_key: str
    receipt_url: str


@router.get("/products", response_model=list[ProductItem])
async def list_products_endpoint(request: Request) -> list[ProductItem]:
    """Lista todos os produtos únicos do catálogo."""
    db = request.app.state.db
    products = await list_products(db)
    return [ProductItem(**p) for p in products]


@router.get("/prices/latest", response_model=PriceResponse)
async def read_latest_price(
    request: Request,
    product_id: str = Query(..., description="normalized_name do produto"),
) -> PriceResponse:
    """Último preço registrado para o produto."""
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
    """Menor preço já visto para o produto entre todas as lojas."""
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
    """Histórico completo de preços para o produto, do mais recente ao mais antigo."""
    db = request.app.state.db
    results = await get_price_history(db, product_id, limit=limit)
    if not results:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return [PriceResponse(**r) for r in results]
