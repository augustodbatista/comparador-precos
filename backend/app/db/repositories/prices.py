"""
Repositório para a coleção 'prices'.

Cada item de um cupom gera um documento nesta coleção.
product_id é o normalized_name — chave de busca para comparação cross-store.
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "prices"


def _to_result(doc: dict) -> dict:
    return {
        "product_id": doc["product_id"],
        "description": doc["original_description"],
        "normalized_name": doc["product_id"],
        "unit_price": doc["unit_price"],
        "quantity": doc["quantity"],
        "unit": doc["unit"],
        "total_value": doc["total_value"],
        "purchase_date": doc["purchase_date"],
        "invoice_number": doc["invoice_number"],
        "invoice_series": doc["invoice_series"],
        "invoice_model": doc["invoice_model"],
        "issuer_name": doc["issuer_name"],
        "issuer_cnpj": doc["issuer_cnpj"],
        "issuer_address": doc["issuer_address"],
        "receipt_access_key": doc["receipt_id"],
        "receipt_url": doc["receipt_url"],
    }


async def insert_prices(db: AsyncIOMotorDatabase, receipt: dict, items: list[dict]) -> None:
    """Insere um registro de preço para cada item do cupom."""
    if not items:
        return
    now = datetime.now(timezone.utc)
    docs = [
        {
            "product_id": item.get("normalized_name") or item["description"],
            "receipt_id": receipt["access_key"],
            "original_description": item["description"],
            "internal_code": item.get("code", ""),
            "quantity": item["qty"],
            "unit": item["unit"],
            "unit_price": item["unit_price"],
            "total_value": item["total"],
            "purchase_date": receipt["invoice"]["issued_at"],
            "invoice_number": receipt["invoice"]["number"],
            "invoice_series": receipt["invoice"]["series"],
            "invoice_model": receipt["invoice"]["model"],
            "issuer_cnpj": receipt["issuer"]["cnpj"],
            "issuer_name": receipt["issuer"]["name"],
            "issuer_address": receipt["issuer"]["address"],
            "receipt_url": receipt["url"],
            "created_at": now,
        }
        for item in items
    ]
    await db[COLLECTION].insert_many(docs)


async def get_latest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Último preço registrado para o produto (purchase_date mais recente)."""
    doc = await db[COLLECTION].find_one(
        {"product_id": product_id},
        sort=[("purchase_date", -1)],
    )
    return _to_result(doc) if doc else None


async def get_lowest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Menor unit_price já registrado. Desempata pelo mais recente."""
    doc = await db[COLLECTION].find_one(
        {"product_id": product_id},
        sort=[("unit_price", 1), ("purchase_date", -1)],
    )
    return _to_result(doc) if doc else None


async def get_price_history(db: AsyncIOMotorDatabase, product_id: str, limit: int = 50) -> list[dict]:
    """Histórico completo de preços para o produto, do mais recente ao mais antigo."""
    cursor = (
        db[COLLECTION]
        .find({"product_id": product_id})
        .sort("purchase_date", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_to_result(d) for d in docs]
