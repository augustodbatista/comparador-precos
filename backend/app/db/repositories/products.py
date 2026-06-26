"""
Repositório para a coleção 'products'.

Mantém o catálogo de produtos únicos já vistos no sistema.
Cada produto é identificado pelo seu normalized_name (nome normalizado pelo Ollama).
Este catálogo é usado pelo frontend para montar a lista de busca na tela de Preços.
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

# Nome da collection no banco
COLLECTION = "products"


async def upsert_product(db: AsyncIOMotorDatabase, normalized_name: str) -> None:
    """Cadastra o produto no catálogo se ainda não existir. Operação idempotente.

    Usa $setOnInsert para que chamadas repetidas com o mesmo nome não alterem
    o created_at original — o produto é inserido apenas uma vez.
    """
    await db[COLLECTION].update_one(
        {"normalized_name": normalized_name},           # filtro: busca pelo nome
        {"$setOnInsert": {                               # só executa na inserção (upsert novo)
            "normalized_name": normalized_name,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,  # insere se não encontrar, atualiza (sem fazer nada) se encontrar
    )


async def list_products(db: AsyncIOMotorDatabase) -> list[dict]:
    """Lista todos os produtos do catálogo em ordem alfabética.

    Retorna apenas o campo normalized_name (sem _id) para uso no frontend.
    Limite de 1000 — suficiente para qualquer uso doméstico razoável.
    """
    cursor = (
        db[COLLECTION]
        .find({}, {"_id": 0, "normalized_name": 1})  # projeta só o nome; exclui _id
        .sort("normalized_name", 1)                   # ordem alfabética crescente
    )
    return await cursor.to_list(length=1000)


async def list_all_product_names(db: AsyncIOMotorDatabase) -> list[str]:
    """Retorna todos os normalized_name cadastrados. Usado para canonicalização no POST /receipts."""
    cursor = db[COLLECTION].find({}, {"_id": 0, "normalized_name": 1})
    docs = await cursor.to_list(length=10_000)
    return [d["normalized_name"] for d in docs]
