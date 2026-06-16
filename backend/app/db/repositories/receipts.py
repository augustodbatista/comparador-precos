"""
Repositório para a coleção 'receipts' no MongoDB.
access_key tem índice único — inserir duplicata lança DuplicateKeyError.
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError  # noqa: F401 — reexportado para uso nos testes

COLLECTION = "receipts"


async def find_by_access_key(db: AsyncIOMotorDatabase, access_key: str) -> dict | None:
    """Busca um cupom pela chave de acesso. Retorna None se não encontrado."""
    doc = await db[COLLECTION].find_one({"access_key": access_key})
    if doc:
        doc.pop("_id", None)
    return doc


async def list_receipts(db: AsyncIOMotorDatabase, *, limit: int = 50, skip: int = 0) -> list[dict]:
    """Lista cupons salvos, do mais recente para o mais antigo."""
    cursor = (
        db[COLLECTION]
        .find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def insert_receipt(db: AsyncIOMotorDatabase, doc: dict) -> dict:
    """Insere um novo cupom. Lança DuplicateKeyError se access_key já existe."""
    to_insert = {**doc, "created_at": datetime.now(timezone.utc)}
    await db[COLLECTION].insert_one(to_insert)
    to_insert.pop("_id", None)
    return to_insert


async def list_receipts(db: AsyncIOMotorDatabase, page: int = 1, limit: int = 20) -> list[dict]:
    """Lista todos os cupons salvos, ordenados por data de emissão decrescente."""
    skip = (page - 1) * limit
    cursor = db[COLLECTION].find().sort("invoice.issued_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc.pop("_id", None)
    return docs
