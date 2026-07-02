"""
Repositório para a coleção 'receipts' no MongoDB.

Responsabilidade: armazenar apenas o cabeçalho do cupom (issuer, invoice, totals).
Os itens individuais vivem em 'prices' — um documento por item — para facilitar
a comparação de preços entre lojas sem duplicar dados do cabeçalho.

Regra de unicidade: access_key tem índice unique no MongoDB.
Inserir um cupom já existente lança DuplicateKeyError (capturado no route).
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError  # noqa: F401 — reexportado para uso nos routes

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
    Esta função reconstrói o array ao ler — transparente para os routes.
    """
    prices = await (
        db["prices"]
        .find({"receipt_id": receipt["access_key"]}, {"_id": 0})
        .to_list(length=None)
    )
    receipt["items"] = [_price_to_item(p) for p in prices]
    return receipt


async def find_by_access_key(db: AsyncIOMotorDatabase, access_key: str) -> dict | None:
    """Busca um cupom pela chave de acesso de 44 dígitos, incluindo os itens de 'prices'.

    Retorna None se o cupom não existir no banco.
    """
    doc = await db[COLLECTION].find_one({"access_key": access_key}, {"_id": 0})
    if not doc:
        return None
    # Anexa os itens vindos de 'prices' antes de retornar
    return await _attach_items(db, doc)


async def list_receipts(db: AsyncIOMotorDatabase, *, limit: int = 50, skip: int = 0) -> list[dict]:
    """Lista cupons do mais recente ao mais antigo, com os itens incluídos em cada um.

    Usa paginação via limit/skip para evitar carregar todos os documentos de uma vez.
    """
    cursor = (
        db[COLLECTION]
        .find({}, {"_id": 0})
        .sort("created_at", -1)  # mais recente primeiro
        .skip(skip)
        .limit(limit)
    )
    receipts = await cursor.to_list(length=limit)
    # Anexa os itens de cada receipt — uma query por cupom (aceitável para volumes pequenos)
    return [await _attach_items(db, r) for r in receipts]


async def insert_receipt(db: AsyncIOMotorDatabase, doc: dict) -> dict:
    """Insere o cabeçalho do cupom na collection 'receipts' (sem o array items[]).

    - Remove items[] do documento antes de inserir (os itens vão para 'prices')
    - Adiciona created_at com o horário atual em UTC
    - Lança DuplicateKeyError se access_key já existir (capturado no route como 200)
    - Retorna o documento inserido sem o campo _id do MongoDB
    """
    # Remove items[] — eles são persistidos separadamente em 'prices'
    header = {k: v for k, v in doc.items() if k != "items"}
    to_insert = {**header, "created_at": datetime.now(timezone.utc)}
    await db[COLLECTION].insert_one(to_insert)
    # Remove o _id gerado pelo MongoDB antes de retornar (não faz parte do schema público)
    to_insert.pop("_id", None)
    return to_insert
