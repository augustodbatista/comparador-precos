"""
Testes unitários para app/db/repositories/receipts.py.
Usa mongomock-motor como banco in-memory — sem conexão real ao Atlas.
"""
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import DuplicateKeyError

from app.db.repositories.receipts import find_by_access_key, insert_receipt, list_receipts

SAMPLE_DOC = {
    "access_key": "31260621253729001979650140000347721508645310",
    "url": "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=...",
    "issuer": {"name": "CASA RENA S/A", "cnpj": "21253729001979", "address": "AV. ARGENTINA, 270"},
    "items": [{"code": "5173", "description": "SUCO", "qty": 1.0, "unit": "TP", "unit_price": 7.99, "total": 7.99}],
    "totals": {"total": 7.99, "paid": 7.99, "items_count": 1},
    "invoice": {"model": "65", "series": "14", "number": "34772", "issued_at": "2026-06-07T11:36:44"},
}


def sample_doc(access_key: str) -> dict:
    return {**SAMPLE_DOC, "access_key": access_key}


@pytest_asyncio.fixture
async def db():
    # mongomock-motor simula o AsyncIOMotorDatabase em memória
    client = AsyncMongoMockClient()
    database = client["test_db"]
    # cria índice único na coleção igual ao que existirá no Atlas
    await database["receipts"].create_index("access_key", unique=True)
    yield database
    client.close()


@pytest.mark.asyncio
class TestFindByAccessKey:
    async def test_retorna_none_quando_nao_existe(self, db):
        result = await find_by_access_key(db, "00000000000000000000000000000000000000000000")
        assert result is None

    async def test_retorna_doc_quando_existe(self, db):
        await insert_receipt(db, SAMPLE_DOC.copy())
        result = await find_by_access_key(db, SAMPLE_DOC["access_key"])
        assert result is not None
        assert result["issuer"]["name"] == "CASA RENA S/A"


@pytest.mark.asyncio
class TestInsertReceipt:
    async def test_persiste_no_banco(self, db):
        await insert_receipt(db, SAMPLE_DOC.copy())
        count = await db["receipts"].count_documents({"access_key": SAMPLE_DOC["access_key"]})
        assert count == 1

    async def test_retorna_doc_sem_id(self, db):
        result = await insert_receipt(db, SAMPLE_DOC.copy())
        assert "_id" not in result

    async def test_duplicate_levanta_duplicate_key_error(self, db):
        await insert_receipt(db, SAMPLE_DOC.copy())
        with pytest.raises(DuplicateKeyError):
            await insert_receipt(db, SAMPLE_DOC.copy())


@pytest.mark.asyncio
class TestListReceipts:
    async def test_retorna_cupons_ordenados_por_created_at_desc(self, db):
        older = {**sample_doc("1" * 44), "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc)}
        newer = {**sample_doc("2" * 44), "created_at": datetime(2026, 6, 2, tzinfo=timezone.utc)}
        await db["receipts"].insert_many([older, newer])

        result = await list_receipts(db)

        assert [doc["access_key"] for doc in result] == ["2" * 44, "1" * 44]
        assert "_id" not in result[0]

    async def test_respeita_limit_e_skip(self, db):
        docs = [
            {**sample_doc("1" * 44), "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc)},
            {**sample_doc("2" * 44), "created_at": datetime(2026, 6, 2, tzinfo=timezone.utc)},
            {**sample_doc("3" * 44), "created_at": datetime(2026, 6, 3, tzinfo=timezone.utc)},
        ]
        await db["receipts"].insert_many(docs)

        result = await list_receipts(db, limit=1, skip=1)

        assert len(result) == 1
        assert result[0]["access_key"] == "2" * 44
