"""
Repositório para consulta de preços na coleção 'receipts'.

product_id é buscado por normalized_name OU description — isso cobre tanto
saves feitos com Ollama rodando (normalized_name correto) quanto saves feitos
via Render sem Ollama (normalized_name = description bruta como fallback).
"""
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "receipts"


def _search_filter(product_id: str) -> dict:
    """Filtro OR: encontra itens pelo nome normalizado ou pela descrição original."""
    return {"$or": [
        {"items.normalized_name": product_id},
        {"items.description": product_id},
    ]}


def _find_item(items: list[dict], product_id: str) -> dict | None:
    """Retorna o item do cupom que corresponde ao product_id buscado."""
    return next(
        (i for i in items
         if i.get("normalized_name") == product_id or i.get("description") == product_id),
        None,
    )


def _build_price_result(product_id: str, item: dict, doc: dict) -> dict:
    """Monta o dict de resposta com todos os campos disponíveis no documento."""
    return {
        # Identificação do produto
        "product_id": product_id,
        "description": item["description"],
        "normalized_name": item.get("normalized_name"),

        # Dados do item no cupom
        "unit_price": item["unit_price"],
        "quantity": item["qty"],
        "unit": item["unit"],
        "total_value": item["total"],

        # Dados da nota fiscal
        "purchase_date": doc["invoice"]["issued_at"],
        "invoice_number": doc["invoice"]["number"],
        "invoice_series": doc["invoice"]["series"],
        "invoice_model": doc["invoice"]["model"],

        # Dados do estabelecimento
        "issuer_name": doc["issuer"]["name"],
        "issuer_cnpj": doc["issuer"]["cnpj"],
        "issuer_address": doc["issuer"]["address"],

        # Rastreabilidade
        "receipt_access_key": doc["access_key"],
        "receipt_url": doc["url"],
    }


async def get_all_products(db: AsyncIOMotorDatabase) -> list[dict]:
    """Lista todos os produtos únicos salvos, por description + normalized_name.

    Agrupa por (description, normalized_name) para expor ambos ao frontend.
    O frontend usa essa lista para mostrar o que está disponível para consulta.
    """
    pipeline = [
        {"$unwind": "$items"},
        {"$group": {
            "_id": "$items.description",
            "description": {"$first": "$items.description"},
            "normalized_name": {"$first": "$items.normalized_name"},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {"_id": 0, "description": 1, "normalized_name": 1}},
    ]
    return await db[COLLECTION].aggregate(pipeline).to_list(length=1000)


async def get_latest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Retorna o último preço registrado para o produto."""
    doc = await db[COLLECTION].find_one(
        _search_filter(product_id),
        sort=[("invoice.issued_at", -1)],
    )
    if not doc:
        return None
    item = _find_item(doc["items"], product_id)
    if not item:
        return None
    return _build_price_result(product_id, item, doc)


async def get_lowest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Retorna o menor unit_price já visto para o produto entre todas as lojas.

    Desempata pelo mais recente quando dois registros têm o mesmo preço mínimo.
    """
    pipeline = [
        {"$match": _search_filter(product_id)},
        {"$unwind": "$items"},
        {"$match": _search_filter(product_id)},
        {"$sort": {"items.unit_price": 1, "invoice.issued_at": -1}},
        {"$limit": 1},
    ]
    docs = await db[COLLECTION].aggregate(pipeline).to_list(length=1)
    if not docs:
        return None
    doc = docs[0]
    return _build_price_result(product_id, doc["items"], doc)
