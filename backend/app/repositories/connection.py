"""
Motor client e helpers de conexão com o MongoDB Atlas.

O cliente é criado no lifespan do FastAPI e armazenado em app.state,
evitando singletons globais que dificultam os testes (cada test fixture
injeta seu próprio mock client em app.state.db sem tocar aqui).
"""
import os

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConfigurationError

# Carrega variáveis do .env (ignorado em produção onde as vars já estão no ambiente)
load_dotenv()


def get_client() -> AsyncIOMotorClient:
    """Cria e retorna um cliente Motor. A URL padrão aponta para MongoDB local."""
    url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    # 5s em vez dos 30s padrão do driver: uma conexão saudável com o Atlas leva
    # menos de 1s, e com o banco fora é melhor responder 503 logo do que deixar
    # o startup e cada gravação pendurados.
    return AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)


def get_db(client: AsyncIOMotorClient) -> AsyncIOMotorDatabase:
    """Retorna o banco de dados configurado pela variável DB_NAME."""
    db_name = os.getenv("DB_NAME", "comparador_precos")
    return client[db_name]


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Cria os índices das 4 collections. Idempotente — seguro chamar a cada startup.

    Índices criados:
    - receipts.access_key: unique — evita cupons duplicados
    - products.normalized_name: unique — evita produtos duplicados no catálogo
    - prices.product_id: busca rápida por produto
    - prices.(product_id, purchase_date): último preço por produto
    - prices.(product_id, unit_price, purchase_date): menor preço por produto
    - users.email: unique — impede cadastro duplicado
    - receipts.(user_id, created_at): histórico paginado por usuário, mais recente primeiro
    """
    await db["receipts"].create_index("access_key", unique=True)
    await db["products"].create_index("normalized_name", unique=True)
    await db["prices"].create_index("product_id")
    # Índice composto para GET /prices/latest (ordena por data decrescente)
    await db["prices"].create_index([("product_id", 1), ("purchase_date", -1)])
    # Índice composto para GET /prices/lowest (ordena por preço crescente, depois data)
    await db["prices"].create_index([("product_id", 1), ("unit_price", 1), ("purchase_date", -1)])
    await db["users"].create_index("email", unique=True)
    # Índice composto para GET /receipts (filtra por usuário, ordena por mais recente)
    await db["receipts"].create_index([("user_id", 1), ("created_at", -1)])


class BancoIndisponivel:
    """Ocupa o lugar do banco quando nem o cliente do MongoDB pôde ser criado.

    Caso real (set/2026): o cluster do Atlas deixou de existir e o construtor
    do cliente falhou ao resolver o registro SRV da MONGODB_URL. Em vez de
    derrubar o app, ele sobe com este objeto em app.state.db: qualquer acesso a
    uma collection lança ConfigurationError, que o main.py converte em 503.
    """

    def __init__(self, erro: Exception):
        self.erro = erro

    def __getitem__(self, nome):
        raise ConfigurationError(f"banco indisponível ({self.erro})")


async def garantir_indices(state) -> None:
    """Cria os índices do banco atual se ainda não existirem. Idempotente.

    Chamado no startup e antes de toda gravação. No startup o banco pode estar
    fora (cluster do Atlas pausado); nesse caso a criação é adiada para a
    primeira gravação, que só prossegue depois dela. Isso importa porque o
    cadastro depende do índice único de users.email para recusar e-mail
    duplicado: gravar sem o índice deixaria passar duplicatas.

    `state` é o app.state do FastAPI. O controle é pelo próprio objeto do
    banco, então trocar app.state.db (como os testes fazem) refaz a checagem.
    """
    db = state.db
    if getattr(state, "indices_prontos_para", None) is db:
        return
    await create_indexes(db)
    state.indices_prontos_para = db
