from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.receipts import router as receipts_router

app = FastAPI(title="Comparador de Preços NFC-e")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    # Starlette não suporta wildcard em allow_origins; regex cobre todos os preview deployments do Vercel
    allow_origin_regex=r"https://.*\.vercel\.app",
    # credentials=True exigiria origem literal — quebraria o regex acima
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(receipts_router)
