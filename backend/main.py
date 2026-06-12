import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import get_client, get_db
from app.routes.receipts import router as receipts_router
from app.routes.prices import router as prices_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = get_client()

    # Se for o cliente real, tenta dar um ping rápido para verificar a conexão
    is_mock = hasattr(client, "__class__") and client.__class__.__name__ == "AsyncMongoMockClient"

    if not is_mock:
        try:
            await asyncio.wait_for(client.admin.command('ping'), timeout=1.5)
            logger.info("Conexão com o MongoDB estabelecida com sucesso!")
        except Exception:
            logger.warning(
                "Não foi possível conectar ao MongoDB local/Atlas. "
                "Habilitando banco de dados MOCKADO (em memória) para testes..."
            )
            client.close()
            from mongomock_motor import AsyncMongoMockClient
            client = AsyncMongoMockClient()
            is_mock = True

    # Se for mock, popula com dados iniciais se estiver vazio
    if is_mock:
        db = client["comparador_precos"]
        # Criamos o índice único
        await db["receipts"].create_index("access_key", unique=True)
        # Popula dados de demonstração
        from app.db.repositories.mock_data import MOCK_RECEIPTS
        for receipt in MOCK_RECEIPTS:
            try:
                await db["receipts"].insert_one(receipt.copy())
            except Exception:
                pass

    app.state.motor_client = client
    app.state.db = get_db(client)
    yield
    client.close()


app = FastAPI(title="Comparador de Preços NFC-e", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    # Starlette não suporta wildcard em allow_origins; regex cobre Vercel e Render
    allow_origin_regex=r"https://(.*\.vercel\.app|.*\.onrender\.com)",
    # credentials=True exigiria origem literal — quebraria o regex acima
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(receipts_router)
app.include_router(prices_router)
