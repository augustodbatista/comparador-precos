"""Testes de integração para POST /auth/signup e POST /auth/login."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from main import app


@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]
    await mock_db["users"].create_index("email", unique=True)
    app.state.db = mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    mock_client.close()


@pytest.mark.asyncio
class TestSignup:
    async def test_retorna_201_com_token(self, client):
        response = await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "user@example.com"
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 0

    async def test_normaliza_email_para_minusculas(self, client):
        response = await client.post("/auth/signup", json={"email": "User@Example.COM", "password": "senha1234"})
        assert response.json()["email"] == "user@example.com"

    async def test_retorna_409_para_email_duplicado(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        response = await client.post("/auth/signup", json={"email": "user@example.com", "password": "outrasenha"})
        assert response.status_code == 409

    async def test_retorna_422_para_email_invalido(self, client):
        response = await client.post("/auth/signup", json={"email": "nao-e-email", "password": "senha1234"})
        assert response.status_code == 422

    async def test_retorna_422_para_senha_curta(self, client):
        response = await client.post("/auth/signup", json={"email": "user@example.com", "password": "1234567"})
        assert response.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_retorna_200_com_token_para_credenciais_corretas(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        response = await client.post("/auth/login", json={"email": "user@example.com", "password": "senha1234"})
        assert response.status_code == 200
        assert response.json()["email"] == "user@example.com"

    async def test_retorna_401_para_senha_errada(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        response = await client.post("/auth/login", json={"email": "user@example.com", "password": "senhaerrada"})
        assert response.status_code == 401

    async def test_retorna_401_para_email_inexistente(self, client):
        response = await client.post("/auth/login", json={"email": "naoexiste@example.com", "password": "senha1234"})
        assert response.status_code == 401

    async def test_mensagem_generica_nao_revela_qual_campo_errou(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        r_senha_errada = await client.post("/auth/login", json={"email": "user@example.com", "password": "senhaerrada"})
        r_email_inexistente = await client.post("/auth/login", json={"email": "outro@example.com", "password": "senha1234"})
        assert r_senha_errada.json()["detail"] == r_email_inexistente.json()["detail"]
