import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import create_indexes, get_client, get_db
from app.routes.receipts import router as receipts_router
from app.routes.prices import router as prices_router

# Usa o logger do uvicorn para que as mensagens apareçam junto com o tráfego HTTP nos logs do Render
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação: conecta ao MongoDB no startup e fecha a conexão no shutdown."""
    client = get_client()

    # mongomock-motor (usado nos testes) não precisa de ping real; detectamos pelo nome da classe
    is_mock = hasattr(client, "__class__") and client.__class__.__name__ == "AsyncMongoMockClient"

    if not is_mock:
        try:
            # Ping com timeout curto para detectar problema de conexão logo no startup
            await asyncio.wait_for(client.admin.command('ping'), timeout=10)
            logger.info("Conexão com o MongoDB estabelecida com sucesso!")
        except Exception as e:
            # Warn mas não derruba o servidor — requests individuais vão falhar
            # se o banco estiver inacessível, sem impedir o startup.
            logger.warning(f"Ping ao MongoDB falhou no startup: {e}")

    # Armazena o cliente e o banco em app.state para que os routes acessem via request.app.state
    app.state.motor_client = client
    app.state.db = get_db(client)

    # Cria os índices das 3 collections (idempotente — seguro chamar a cada restart)
    await create_indexes(app.state.db)

    yield  # A aplicação roda aqui

    # Shutdown: fecha a conexão com o MongoDB
    client.close()


# Instância principal do FastAPI; o lifespan gerencia a conexão com o banco
app = FastAPI(title="Comparador de Preços NFC-e", lifespan=lifespan)

# Configuração de CORS — permite requests do Vite local e de qualquer subdomínio Vercel/Render
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server em desenvolvimento local
    # Starlette não suporta wildcard em allow_origins; regex cobre Vercel e Render
    allow_origin_regex=r"https://(.*\.vercel\.app|.*\.onrender\.com)",
    # credentials=True exigiria origem literal — quebraria o regex acima
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Registra os roteadores — cada um agrupa seus próprios endpoints
app.include_router(receipts_router)  # GET /receipts, POST /receipts
app.include_router(prices_router)    # GET /products, GET /prices/latest, /lowest, /history
