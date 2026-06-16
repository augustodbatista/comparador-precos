"""
Repositório para consulta de preços na coleção 'receipts'.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "receipts"


async def get_latest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Busca o último preço registrado para o produto.

    Procura por cupons que contenham o item com 'code' igual a 'product_id',
    ordenando pelo campo 'invoice.issued_at' decrescente (mais recente primeiro).
    """
    doc = await db[COLLECTION].find_one(
        {"items.code": product_id},
        sort=[("invoice.issued_at", -1)]
    )
    if not doc:
        return None

    item = next((i for i in doc["items"] if i["code"] == product_id), None)
    if not item:
        return None

    return {
        "product_id": product_id,
        "description": item["description"],
        "unit_price": item["unit_price"],
        "quantity": item["qty"],
        "unit": item["unit"],
        "total_value": item["total"],
        "purchase_date": doc["invoice"]["issued_at"],
        "issuer_name": doc["issuer"]["name"],
        "issuer_cnpj": doc["issuer"]["cnpj"],
        "receipt_access_key": doc["access_key"]
    }


async def get_lowest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Busca o menor preço já visto para o produto entre todas as lojas.

    Usa agregação para extrair o item com o menor unit_price.
    Se houver empate de preço, retorna o mais recente com base no 'invoice.issued_at'.
    """
    pipeline = [
        {"$match": {"items.code": product_id}},
        {"$unwind": "$items"},
        {"$match": {"items.code": product_id}},
        {"$sort": {"items.unit_price": 1, "invoice.issued_at": -1}},
        {"$limit": 1}
    ]
    cursor = db[COLLECTION].aggregate(pipeline)
    docs = await cursor.to_list(length=1)
    if not docs:
        return None

    doc = docs[0]
    item = doc["items"]
    return {
        "product_id": product_id,
        "description": item["description"],
        "unit_price": item["unit_price"],
        "quantity": item["qty"],
        "unit": item["unit"],
        "total_value": item["total"],
        "purchase_date": doc["invoice"]["issued_at"],
        "issuer_name": doc["issuer"]["name"],
        "issuer_cnpj": doc["issuer"]["cnpj"],
        "receipt_access_key": doc["access_key"]
    }
