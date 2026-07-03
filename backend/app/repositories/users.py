"""
Repositório para a coleção 'users' no MongoDB.

Regra de unicidade: email tem índice unique — inserir um email já existente
lança DuplicateKeyError (capturado no controller como 409).
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError  # noqa: F401 — reexportado para uso no controller

COLLECTION = "users"


async def find_by_email(db: AsyncIOMotorDatabase, email: str) -> dict | None:
    """Busca um usuário pelo email (já normalizado para minúsculas pelo controller)."""
    return await db[COLLECTION].find_one({"email": email}, {"_id": 0})


async def insert_user(db: AsyncIOMotorDatabase, email: str, hashed_password: str, phone: str) -> dict:
    """Insere um novo usuário. Lança DuplicateKeyError se o email já existir."""
    doc = {
        "email": email,
        "hashed_password": hashed_password,
        "phone": phone,
        "created_at": datetime.now(timezone.utc),
    }
    await db[COLLECTION].insert_one(doc)
    # Remove o _id gerado pelo MongoDB antes de retornar (não faz parte do schema público)
    doc.pop("_id", None)
    return doc
