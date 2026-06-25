"""
Repositório para a coleção 'prices'.

Cada item de um cupom gera um documento independente nesta collection.
Isso permite comparar preços do mesmo produto entre lojas e datas diferentes.

Chave de busca: product_id = normalized_name do produto.
Usar o nome normalizado (em vez do código interno da loja) é o que viabiliza
a comparação cross-store, já que cada loja tem seu próprio sistema de códigos.
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

# Nome da collection no banco
COLLECTION = "prices"


def _to_result(doc: dict) -> dict:
    """Converte um documento interno de 'prices' para o formato da API (PriceResponse).

    Renomeia campos internos (ex: original_description → description) e
    agrega informações de loja e nota que ficam desnormalizadas no documento.
    """
    return {
        "product_id": doc["product_id"],
        "description": doc["original_description"],    # descrição bruta da SEFAZ
        "normalized_name": doc["product_id"],          # mesmo que product_id — nome legível
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
        "receipt_access_key": doc["receipt_id"],       # receipt_id no banco = access_key na API
        "receipt_url": doc["receipt_url"],
    }


async def insert_prices(db: AsyncIOMotorDatabase, receipt: dict, items: list[dict]) -> None:
    """Insere um documento de preço para cada item do cupom.

    Os dados de cabeçalho (loja, nota fiscal, data) são desnormalizados em cada
    documento de preço para que cada consulta seja auto-suficiente sem joins.
    """
    if not items:
        return

    now = datetime.now(timezone.utc)

    # Monta os documentos de preço — um por item, com dados do cabeçalho desnormalizados
    docs = [
        {
            "product_id": item.get("normalized_name") or item["description"],  # fallback para description se não normalizado
            "receipt_id": receipt["access_key"],
            "original_description": item["description"],      # nome bruto da SEFAZ (preservado para auditoria)
            "internal_code": item.get("code", ""),            # código interno da loja (varia entre lojas)
            "quantity": item["qty"],
            "unit": item["unit"],
            "unit_price": item["unit_price"],
            "total_value": item["total"],
            "purchase_date": receipt["invoice"]["issued_at"], # data de emissão da nota
            "invoice_number": receipt["invoice"]["number"],
            "invoice_series": receipt["invoice"]["series"],
            "invoice_model": receipt["invoice"]["model"],
            "issuer_cnpj": receipt["issuer"]["cnpj"],
            "issuer_name": receipt["issuer"]["name"],
            "issuer_address": receipt["issuer"]["address"],
            "receipt_url": receipt["url"],                    # URL do QR Code (para link direto ao cupom)
            "created_at": now,
        }
        for item in items
    ]
    await db[COLLECTION].insert_many(docs)


async def get_latest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Retorna o documento de preço com a purchase_date mais recente para o produto.

    Usa o índice composto (product_id, purchase_date DESC) para performance.
    """
    doc = await db[COLLECTION].find_one(
        {"product_id": product_id},
        sort=[("purchase_date", -1)],  # mais recente primeiro
    )
    return _to_result(doc) if doc else None


async def get_lowest_price(db: AsyncIOMotorDatabase, product_id: str) -> dict | None:
    """Retorna o documento de preço com o menor unit_price para o produto.

    Em caso de empate de preço, desempata pelo mais recente (purchase_date DESC).
    Usa o índice composto (product_id, unit_price ASC, purchase_date DESC).
    """
    doc = await db[COLLECTION].find_one(
        {"product_id": product_id},
        sort=[("unit_price", 1), ("purchase_date", -1)],
    )
    return _to_result(doc) if doc else None


async def get_price_history(db: AsyncIOMotorDatabase, product_id: str, limit: int = 50) -> list[dict]:
    """Retorna o histórico completo de preços do produto, do mais recente ao mais antigo.

    O limite padrão de 50 evita payloads muito grandes, mas pode ser ajustado via query param.
    """
    cursor = (
        db[COLLECTION]
        .find({"product_id": product_id})
        .sort("purchase_date", -1)  # mais recente primeiro
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return [_to_result(d) for d in docs]
