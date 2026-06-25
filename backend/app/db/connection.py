"""
Motor client e helpers de conexão com o MongoDB Atlas.

O cliente é criado no lifespan do FastAPI e armazenado em app.state,
evitando singletons globais que dificultam os testes (cada test fixture
injeta seu próprio mock client em app.state.db sem tocar aqui).
"""
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Carrega variáveis do .env (ignorado em produção onde as vars já estão no ambiente)
load_dotenv()


def get_client() -> AsyncIOMotorClient:
    """Cria e retorna um cliente Motor. A URL padrão aponta para MongoDB local."""
    url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    return AsyncIOMotorClient(url)


def get_db(client: AsyncIOMotorClient) -> AsyncIOMotorDatabase:
    """Retorna o banco de dados configurado pela variável DB_NAME."""
    db_name = os.getenv("DB_NAME", "comparador_precos")
    return client[db_name]


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Cria os índices das 3 collections. Idempotente — seguro chamar a cada startup.

    Índices criados:
    - receipts.access_key: unique — evita cupons duplicados
    - products.normalized_name: unique — evita produtos duplicados no catálogo
    - prices.product_id: busca rápida por produto
    - prices.(product_id, purchase_date): último preço por produto
    - prices.(product_id, unit_price, purchase_date): menor preço por produto
    """
    await db["receipts"].create_index("access_key", unique=True)
    await db["products"].create_index("normalized_name", unique=True)
    await db["prices"].create_index("product_id")
    # Índice composto para GET /prices/latest (ordena por data decrescente)
    await db["prices"].create_index([("product_id", 1), ("purchase_date", -1)])
    # Índice composto para GET /prices/lowest (ordena por preço crescente, depois data)
    await db["prices"].create_index([("product_id", 1), ("unit_price", 1), ("purchase_date", -1)])
