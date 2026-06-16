from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.db.repositories.prices import get_latest_price, get_lowest_price

router = APIRouter()


class PriceResponse(BaseModel):
    product_id: str
    description: str
    unit_price: float
    quantity: float
    unit: str
    total_value: float
    purchase_date: str
    issuer_name: str
    issuer_cnpj: str
    receipt_access_key: str


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
