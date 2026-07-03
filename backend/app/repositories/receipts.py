"""
Repositório para a coleção 'receipts' no MongoDB.

Responsabilidade: armazenar apenas o cabeçalho do cupom (issuer, invoice, totals).
Os itens individuais vivem em 'prices' — um documento por item — para facilitar
a comparação de preços entre lojas sem duplicar dados do cabeçalho.

Regra de unicidade: access_key tem índice unique no MongoDB (globalmente único,
não composto com user_id). 'receipts' é privado por usuário via o campo user_id
em cada documento — inserir um cupom já existente lança DuplicateKeyError
(capturado no controller).
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError  # noqa: F401 — reexportado para uso nos controllers

# Nome da collection no banco
COLLECTION = "receipts"


def _price_to_item(price: dict) -> dict:
    """Reconstrói o shape de ItemData a partir de um documento da collection 'prices'.

    Necessário porque o cabeçalho não armazena os itens — eles precisam ser
    reconstituídos a partir de 'prices' quando o receipt é retornado ao cliente.
    """
    return {
        "code": price.get("internal_code", ""),
        "description": price["original_description"],
        "normalized_name": price["product_id"],  # product_id é o normalized_name
        "qty": price["quantity"],
        "unit": price["unit"],
        "unit_price": price["unit_price"],
        "total": price["total_value"],
    }


async def _attach_items(db: AsyncIOMotorDatabase, receipt: dict) -> dict:
    """Busca os itens de 'prices' e injeta no documento de receipt antes de retornar.

    O cabeçalho é salvo sem items[] para evitar duplicação de dados.
    Esta função reconstrói o array ao ler — transparente para os controllers.
    """
    prices = await (
        db["prices"]
        .find({"receipt_id": receipt["access_key"]}, {"_id": 0})
        .to_list(length=None)
    )
    receipt["items"] = [_price_to_item(p) for p in prices]
    return receipt


async def find_by_access_key_for_user(db: AsyncIOMotorDatabase, access_key: str, user_id: str) -> dict | None:
    """Busca um cupom que PERTENCE a este usuário. Usado por GET ?url= (cache check)."""
    doc = await db[COLLECTION].find_one({"access_key": access_key, "user_id": user_id}, {"_id": 0})
    if not doc:
        return None
    return await _attach_items(db, doc)


async def find_any_by_access_key(db: AsyncIOMotorDatabase, access_key: str) -> dict | None:
    """Busca um cupom independente do dono. USO INTERNO APENAS — só pra resolver
    conflito de DuplicateKeyError no POST (decidir 200-próprio vs 409-de-outro).
    Nunca retornar diretamente ao cliente sem checar owner == current_user antes.
    """
    doc = await db[COLLECTION].find_one({"access_key": access_key}, {"_id": 0})
    if not doc:
        return None
    return await _attach_items(db, doc)


async def list_receipts(db: AsyncIOMotorDatabase, user_id: str, *, limit: int = 50, skip: int = 0) -> list[dict]:
    """Lista cupons DO USUÁRIO do mais recente ao mais antigo, com os itens incluídos."""
    cursor = (
        db[COLLECTION]
        .find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    receipts = await cursor.to_list(length=limit)
    return [await _attach_items(db, r) for r in receipts]


async def insert_receipt(db: AsyncIOMotorDatabase, doc: dict, user_id: str) -> dict:
    """Insere o cabeçalho do cupom, associado ao usuário que salvou.

    - Remove items[] do documento antes de inserir (os itens vão para 'prices')
    - Adiciona user_id e created_at
    - Lança DuplicateKeyError se access_key já existir (capturado no controller)
    """
    header = {k: v for k, v in doc.items() if k != "items"}
    to_insert = {**header, "user_id": user_id, "created_at": datetime.now(timezone.utc)}
    await db[COLLECTION].insert_one(to_insert)
    to_insert.pop("_id", None)
    return to_insert
