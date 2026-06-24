"""
Re-normaliza via Ollama todos os itens em 'prices' cujo product_id ainda é igual
à original_description (i.e., o fallback foi usado e nunca foi normalizado de verdade).

Atualiza prices.product_id e faz upsert em products.
Idempotente: roda quantas vezes quiser sem duplicar dados.

Uso:
    cd backend/
    python scripts/renormalize_prices.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.normalizer import normalize_items

load_dotenv()

BATCH = 5  # itens por chamada ao Ollama (menor = menos risco de alucinação)


async def main() -> None:
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]

    # Itens onde product_id == original_description (fallback não normalizado)
    raw_docs = await db["prices"].find(
        {"$expr": {"$eq": ["$product_id", "$original_description"]}},
        {"_id": 1, "product_id": 1, "original_description": 1},
    ).to_list(length=None)

    if not raw_docs:
        print("Nada para re-normalizar.")
        client.close()
        return

    print(f"{len(raw_docs)} itens para normalizar (em lotes de {BATCH})...")

    updated = 0
    for i in range(0, len(raw_docs), BATCH):
        batch = raw_docs[i : i + BATCH]
        descriptions = [d["original_description"] for d in batch]
        normalized = await normalize_items(descriptions)

        for doc, norm_name in zip(batch, normalized):
            if norm_name == doc["original_description"]:
                print(f"  sem mudança: {doc['original_description']}")
                continue

            print(f"  {doc['original_description']} -> {norm_name}")

            # Atualiza o product_id no doc de prices
            await db["prices"].update_many(
                {"original_description": doc["original_description"], "product_id": doc["original_description"]},
                {"$set": {"product_id": norm_name}},
            )

            # Remove produto antigo se não houver mais referências
            still_used = await db["prices"].count_documents({"product_id": doc["original_description"]})
            if not still_used:
                await db["products"].delete_one({"normalized_name": doc["original_description"]})

            # Cadastra produto novo
            now = datetime.now(timezone.utc)
            await db["products"].update_one(
                {"normalized_name": norm_name},
                {"$setOnInsert": {"normalized_name": norm_name, "created_at": now}},
                upsert=True,
            )
            updated += 1

    print(f"\nConcluído. {updated}/{len(raw_docs)} itens atualizados.")
    client.close()


asyncio.run(main())
