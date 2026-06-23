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
            await asyncio.wait_for(client.admin.command('ping'), timeout=10)
            logger.info("Conexão com o MongoDB estabelecida com sucesso!")
        except Exception as e:
            # Warn mas não derruba o servidor — requests individuais vão falhar
            # se o banco estiver inacessível, sem impedir o startup.
            logger.warning(f"Ping ao MongoDB falhou no startup: {e}")

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
