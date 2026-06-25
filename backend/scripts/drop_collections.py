"""Apaga todas as collections do banco (receipts, products, prices).

Use este script para resetar o banco antes de começar uma nova carga de dados.
ATENÇÃO: operação destrutiva e irreversível — todos os cupons e preços serão perdidos.

Uso:
    cd backend/
    python scripts/drop_collections.py
"""
import asyncio
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Carrega as variáveis do .env (MONGODB_URL, DB_NAME)
load_dotenv()


async def main() -> None:
    # Conecta ao banco configurado nas variáveis de ambiente
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]

    # Apaga cada collection e confirma no terminal
    for name in ("receipts", "products", "prices"):
        await db[name].drop()
        print(f"dropped: {name}")

    client.close()


asyncio.run(main())
