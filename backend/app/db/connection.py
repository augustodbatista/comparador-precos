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
    if os.getenv("MOCK_DB", "false").lower() == "true":
        from mongomock_motor import AsyncMongoMockClient
        return AsyncMongoMockClient()
    url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    return AsyncIOMotorClient(url)


def get_db(client: AsyncIOMotorClient) -> AsyncIOMotorDatabase:
    db_name = os.getenv("DB_NAME", "comparador_precos")
    return client[db_name]
