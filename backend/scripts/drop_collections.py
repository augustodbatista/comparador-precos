"""Apaga todas as collections do banco (receipts, products, prices)."""
import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


async def main() -> None:
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]

    for name in ("receipts", "products", "prices"):
        await db[name].drop()
        print(f"dropped: {name}")

    client.close()


asyncio.run(main())
