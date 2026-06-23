from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTION = "products"


async def upsert_product(db: AsyncIOMotorDatabase, normalized_name: str) -> None:
    """Cadastra o produto se ainda não existir. Idempotente."""
    await db[COLLECTION].update_one(
        {"normalized_name": normalized_name},
        {"$setOnInsert": {
            "normalized_name": normalized_name,
            "created_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


async def list_products(db: AsyncIOMotorDatabase) -> list[dict]:
    """Lista todos os produtos cadastrados em ordem alfabética."""
    cursor = db[COLLECTION].find({}, {"_id": 0, "normalized_name": 1}).sort("normalized_name", 1)
    return await cursor.to_list(length=1000)
