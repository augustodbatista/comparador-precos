"""
Repositório para consulta de preços na coleção 'receipts'.

product_id é o normalized_name gerado pelo Ollama (Task 6).
Cupons sem normalized_name (salvos antes da Task 6) não aparecem nas queries.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "receipts"


def _build_price_result(product_id: str, item: dict, doc: dict) -> dict:
    """Monta o dict de resposta com todos os campos disponíveis no documento."""
    return {
        # Identificação do produto
        "product_id": product_id,
        "description": item["description"],          # descrição bruta da SEFAZ
        "normalized_name": item.get("normalized_name"),  # nome limpo gerado pelo Ollama

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
        "issuer_address": doc["issuer"]["address"],  # identifica a filial

        # Rastreabilidade: link de volta ao cupom original na SEFAZ
        "receipt_access_key": doc["access_key"],
        "receipt_url": doc["url"],
    }


async def get_latest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Retorna o último preço registrado para o produto (normalized_name mais recente)."""
    doc = await db[COLLECTION].find_one(
        {"items.normalized_name": product_id},
        sort=[("invoice.issued_at", -1)],
    )
    if not doc:
        return None

    item = next((i for i in doc["items"] if i.get("normalized_name") == product_id), None)
    if not item:
        return None

    return _build_price_result(product_id, item, doc)


async def get_lowest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Retorna o menor unit_price já visto para o produto entre todas as lojas.

    Desempata pelo mais recente quando dois registros têm o mesmo preço mínimo.
    """
    pipeline = [
        {"$match": {"items.normalized_name": product_id}},
        {"$unwind": "$items"},
        {"$match": {"items.normalized_name": product_id}},
        # Ordena por preço ASC e data DESC para desempate automático
        {"$sort": {"items.unit_price": 1, "invoice.issued_at": -1}},
        {"$limit": 1},
    ]
    docs = await db[COLLECTION].aggregate(pipeline).to_list(length=1)
    if not docs:
        return None

    doc = docs[0]
    return _build_price_result(product_id, doc["items"], doc)
