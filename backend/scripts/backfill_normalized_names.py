"""
Migração one-shot: move items[] de 'receipts' para 'prices' + popula 'products'.

Idempotente: pula cupons que já têm preços registrados em 'prices'.
Se Ollama estiver rodando, normaliza as descriptions antes de inserir.

Uso:
    cd backend/
    python scripts/backfill_normalized_names.py
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


async def main() -> None:
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]

    # Garante índices
    await db["prices"].create_index("product_id")
    await db["prices"].create_index([("product_id", 1), ("purchase_date", -1)])
    await db["products"].create_index("normalized_name", unique=True)

    receipts = await db["receipts"].find({}).to_list(length=None)
    print(f"Total de cupons: {len(receipts)}")

    migrated = skipped = 0
    for doc in receipts:
        key = doc["access_key"]
        items = doc.get("items", [])

        if not items:
            print(f"  {key[-8:]} — sem items[], pulando")
            skipped += 1
            continue

        already = await db["prices"].count_documents({"receipt_id": key})
        if already:
            print(f"  {key[-8:]} — já migrado ({already} preços), pulando")
            skipped += 1
            continue

        # Normaliza via Ollama (fallback silencioso)
        descriptions = [i["description"] for i in items]
        print(f"  {key[-8:]} — normalizando {len(descriptions)} item(ns)...")
        normalized = await normalize_items(descriptions)

        now = datetime.now(timezone.utc)
        price_docs = []
        for item, norm_name in zip(items, normalized):
            product_id = norm_name if norm_name != item["description"] else (
                item.get("normalized_name") or item["description"]
            )
            price_docs.append({
                "product_id": product_id,
                "receipt_id": key,
                "original_description": item["description"],
                "internal_code": item.get("code", ""),
                "quantity": item["qty"],
                "unit": item["unit"],
                "unit_price": item["unit_price"],
                "total_value": item["total"],
                "purchase_date": doc["invoice"]["issued_at"],
                "invoice_number": doc["invoice"]["number"],
                "invoice_series": doc["invoice"]["series"],
                "invoice_model": doc["invoice"]["model"],
                "issuer_cnpj": doc["issuer"]["cnpj"],
                "issuer_name": doc["issuer"]["name"],
                "issuer_address": doc["issuer"]["address"],
                "receipt_url": doc["url"],
                "created_at": now,
            })
            print(f"    {item['description']} -> {product_id}")

        await db["prices"].insert_many(price_docs)

        # Cadastra produtos únicos
        for pd in price_docs:
            await db["products"].update_one(
                {"normalized_name": pd["product_id"]},
                {"$setOnInsert": {"normalized_name": pd["product_id"], "created_at": now}},
                upsert=True,
            )

        migrated += 1

    print(f"\nConcluído. {migrated} migrados, {skipped} pulados.")
    client.close()


asyncio.run(main())
