"""
Motor client e helper de conexão com o MongoDB Atlas.
O cliente é criado no lifespan do FastAPI e armazenado em app.state,
evitando singletons globais que dificultam os testes.
"""
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

load_dotenv()


def get_client() -> AsyncIOMotorClient:
    url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    return AsyncIOMotorClient(url)


def get_db(client: AsyncIOMotorClient) -> AsyncIOMotorDatabase:
    db_name = os.getenv("DB_NAME", "comparador_precos")
    return client[db_name]


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Cria os índices das 3 collections. Idempotente — seguro chamar a cada startup."""
    await db["receipts"].create_index("access_key", unique=True)
    await db["products"].create_index("normalized_name", unique=True)
    await db["prices"].create_index("product_id")
    await db["prices"].create_index([("product_id", 1), ("purchase_date", -1)])
    await db["prices"].create_index([("product_id", 1), ("unit_price", 1), ("purchase_date", -1)])
