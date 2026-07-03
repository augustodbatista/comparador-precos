"""Testes para o repositório de usuários — mongomock-motor, mesmo padrão de test_repositories_receipts.py."""
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import DuplicateKeyError

from app.repositories.users import find_by_email, insert_user


@pytest_asyncio.fixture
async def db():
    client = AsyncMongoMockClient()
    database = client["test_db"]
    await database["users"].create_index("email", unique=True)
    yield database
    client.close()


@pytest.mark.asyncio
class TestInsertUser:
    async def test_persiste_no_banco(self, db):
        await insert_user(db, "user@example.com", "hashedvalue")
        count = await db["users"].count_documents({"email": "user@example.com"})
        assert count == 1

    async def test_retorna_doc_criado(self, db):
        result = await insert_user(db, "user@example.com", "hashedvalue")
        assert result["email"] == "user@example.com"
        assert result["hashed_password"] == "hashedvalue"
        assert "created_at" in result

    async def test_email_duplicado_levanta_duplicate_key_error(self, db):
        await insert_user(db, "user@example.com", "hashedvalue")
        with pytest.raises(DuplicateKeyError):
            await insert_user(db, "user@example.com", "outrohash")


@pytest.mark.asyncio
class TestFindByEmail:
    async def test_retorna_none_quando_nao_existe(self, db):
        result = await find_by_email(db, "naoexiste@example.com")
        assert result is None

    async def test_retorna_doc_quando_existe(self, db):
        await insert_user(db, "user@example.com", "hashedvalue")
        result = await find_by_email(db, "user@example.com")
        assert result is not None
        assert result["hashed_password"] == "hashedvalue"
