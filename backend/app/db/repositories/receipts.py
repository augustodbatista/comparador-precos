"""
Repositório para a coleção 'receipts' no MongoDB.

Armazena apenas o cabeçalho do cupom (issuer, invoice, totals).
Os itens vivem na coleção 'prices' — um doc por item.
access_key tem índice único — inserir duplicata lança DuplicateKeyError.
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError  # noqa: F401 — reexportado para uso nos routes

COLLECTION = "receipts"


def _price_to_item(price: dict) -> dict:
    """Reconstrói o shape de item a partir de um documento de prices."""
    return {
        "code": price.get("internal_code", ""),
        "description": price["original_description"],
        "normalized_name": price["product_id"],
        "qty": price["quantity"],
        "unit": price["unit"],
        "unit_price": price["unit_price"],
        "total": price["total_value"],
    }


async def _attach_items(db: AsyncIOMotorDatabase, receipt: dict) -> dict:
    """Junta os itens de 'prices' no documento de receipt."""
    prices = await (
        db["prices"]
        .find({"receipt_id": receipt["access_key"]}, {"_id": 0})
        .to_list(length=None)
    )
    receipt["items"] = [_price_to_item(p) for p in prices]
    return receipt


async def find_by_access_key(db: AsyncIOMotorDatabase, access_key: str) -> dict | None:
    """Busca um cupom pela chave de acesso, incluindo os itens de 'prices'."""
    doc = await db[COLLECTION].find_one({"access_key": access_key}, {"_id": 0})
    if not doc:
        return None
    return await _attach_items(db, doc)


async def list_receipts(db: AsyncIOMotorDatabase, *, limit: int = 50, skip: int = 0) -> list[dict]:
    """Lista cupons do mais recente ao mais antigo, com itens incluídos."""
    cursor = (
        db[COLLECTION]
        .find({}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    receipts = await cursor.to_list(length=limit)
    return [await _attach_items(db, r) for r in receipts]


async def insert_receipt(db: AsyncIOMotorDatabase, doc: dict) -> dict:
    """Insere o cabeçalho do cupom (sem items[]). Lança DuplicateKeyError se access_key já existe."""
    header = {k: v for k, v in doc.items() if k != "items"}
    to_insert = {**header, "created_at": datetime.now(timezone.utc)}
    await db[COLLECTION].insert_one(to_insert)
    to_insert.pop("_id", None)
    return to_insert
