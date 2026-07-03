"""
Hashing de senha (bcrypt) e emissão/validação de JWT (PyJWT).

Sem imports de FastAPI — segue o mesmo padrão de app/services/*.py: funções puras
que levantam suas próprias exceções, traduzidas para HTTPException na camada de
controller (app/controllers/auth.py).
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()  # idempotente — mesmo padrão de app/repositories/connection.py

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    # Diferente de GROQ_API_KEY (degrada graciosamente), não existe fallback seguro
    # para o segredo do JWT — um valor hardcoded seria um buraco de segurança.
    raise RuntimeError(
        "JWT_SECRET_KEY não configurada. Defina no backend/.env (dev) ou nas "
        "variáveis de ambiente do Render (produção)."
    )

ALGORITHM = "HS256"
EXPIRE_DAYS = 7


def _hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password_sync(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


async def hash_password(password: str) -> str:
    """bcrypt é CPU-bound (~200-300ms) — roda em thread separada pra não travar o event loop."""
    return await asyncio.to_thread(_hash_password_sync, password)


async def verify_password(password: str, hashed: str) -> bool:
    return await asyncio.to_thread(_verify_password_sync, password, hashed)


def create_access_token(email: str) -> str:
    """Gera um JWT com 'sub' = email e expiração fixa de 7 dias (sem refresh token)."""
    now = datetime.now(timezone.utc)
    payload = {"sub": email, "iat": now, "exp": now + timedelta(days=EXPIRE_DAYS)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    """Decodifica e valida o JWT, retornando o email (claim 'sub').

    Levanta jwt.ExpiredSignatureError ou jwt.InvalidTokenError — traduzidas
    para HTTPException 401 em controllers/auth.py.
    """
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    return payload["sub"]
