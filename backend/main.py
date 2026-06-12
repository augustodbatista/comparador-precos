from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.connection import get_client, get_db
from app.routes.receipts import router as receipts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Abre conexão com o Atlas na inicialização e fecha no shutdown
    client = get_client()
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
