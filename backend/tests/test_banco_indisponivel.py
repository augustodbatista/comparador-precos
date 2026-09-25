"""Comportamento com o MongoDB indisponível (ex.: cluster gratuito do Atlas pausado).

Dois riscos cobertos aqui:

1. Banco fora no startup derrubava o app inteiro: o ping era tolerado, mas o
   create_indexes logo depois lançava ServerSelectionTimeoutError e o uvicorn
   encerrava com "Application startup failed". No Render isso aparece como
   serviço que nunca responde.
2. Subir sem os índices não pode abrir brecha: o cadastro depende do índice
   único de users.email para recusar e-mail duplicado (DuplicateKeyError).
   Nenhuma gravação pode acontecer antes de os índices existirem.
"""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import ServerSelectionTimeoutError

import main
from app.controllers.auth import get_current_user
from main import app

FIXTURES = Path(__file__).parent / "fixtures"
MG_HTML = (FIXTURES / "mg_sefaz.html").read_text(encoding="utf-8")
VALID_URL = "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=31260661585865266267650040002426521200179790|3|1"


# --- Um MongoDB que não responde, como um cluster pausado -----------------

def _fora(*args, **kwargs):
    raise ServerSelectionTimeoutError("cluster pausado")


class _ColecaoFora:
    async def create_index(self, *args, **kwargs):
        _fora()

    async def find_one(self, *args, **kwargs):
        _fora()

    async def insert_one(self, *args, **kwargs):
        _fora()


class _BancoFora:
    def __getitem__(self, nome):
        return _ColecaoFora()


class _AdminFora:
    async def command(self, *args, **kwargs):
        _fora()


class _ClienteFora:
    admin = _AdminFora()

    def __getitem__(self, nome):
        return _BancoFora()

    def close(self):
        pass


def _cliente_http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _signup(email="user@example.com"):
    return {"email": email, "password": "senha1234", "phone": "11912345678"}


# --- Testes -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_startup_nao_derruba_o_app_com_banco_fora(monkeypatch):
    monkeypatch.setattr(main, "get_client", lambda: _ClienteFora())

    # Antes da correção, entrar no lifespan lançava ServerSelectionTimeoutError.
    async with main.lifespan(app):
        assert app.state.db is not None


@pytest.mark.asyncio
async def test_signup_retorna_503_sem_gravar_quando_banco_fora():
    app.state.db = _BancoFora()

    async with _cliente_http() as client:
        response = await client.post("/auth/signup", json=_signup())

    assert response.status_code == 503
    assert "indisponível" in response.json()["detail"]


@pytest.mark.asyncio
async def test_indice_unico_de_email_existe_antes_do_primeiro_cadastro():
    # Banco que voltou depois de um startup sem índices: nada foi criado ainda.
    mock_client = AsyncMongoMockClient()
    app.state.db = mock_client["banco_sem_indices"]

    async with _cliente_http() as client:
        primeiro = await client.post("/auth/signup", json=_signup())
        duplicado = await client.post("/auth/signup", json=_signup())

    mock_client.close()
    assert primeiro.status_code == 201
    # Sem o índice único, o segundo cadastro com o mesmo e-mail passaria com 201.
    assert duplicado.status_code == 409


@pytest.mark.asyncio
async def test_post_receipts_retorna_503_quando_banco_fora():
    mock_client = AsyncMongoMockClient()
    app.state.db = mock_client["test_db"]
    app.dependency_overrides[get_current_user] = lambda: "user@example.com"

    try:
        async with _cliente_http() as client:
            with patch("app.controllers.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
                body = (await client.get("/receipts", params={"url": VALID_URL})).json()

            app.state.db = _BancoFora()
            response = await client.post("/receipts", json=body)
    finally:
        app.dependency_overrides.clear()
        mock_client.close()

    assert response.status_code == 503


def test_cliente_desiste_rapido_de_um_banco_que_nao_responde():
    # O padrão do driver é 30s. Somado ao ping, um startup com o banco fora
    # levava ~40s, e cada gravação ficava 30s pendurada antes do 503.
    from app.repositories.connection import get_client

    cliente = get_client()
    try:
        assert cliente.options.server_selection_timeout == 5
    finally:
        cliente.close()


# --- URL do banco que nem chega a virar cliente ------------------------------
#
# Erro real visto nos logs do Render (set/2026): o cluster do Atlas deixou de
# existir, e o próprio construtor do cliente falhou ao resolver o registro SRV:
#   ConfigurationError: The DNS query name does not exist:
#   _mongodb._tcp.cluster0.xxxx.mongodb.net.
# Isso acontece em get_client(), antes de qualquer ping, e derrubava o startup.

def _get_client_com_url_invalida():
    from pymongo.errors import ConfigurationError

    raise ConfigurationError(
        "The DNS query name does not exist: _mongodb._tcp.cluster0.inexistente.mongodb.net."
    )


@pytest.mark.asyncio
async def test_startup_nao_derruba_o_app_com_url_do_banco_invalida(monkeypatch):
    monkeypatch.setattr(main, "get_client", _get_client_com_url_invalida)

    async with main.lifespan(app):
        pass  # antes da correção, entrar no lifespan lançava ConfigurationError


@pytest.mark.asyncio
async def test_rotas_que_leem_o_banco_respondem_503_com_url_invalida(monkeypatch):
    monkeypatch.setattr(main, "get_client", _get_client_com_url_invalida)
    app.dependency_overrides[get_current_user] = lambda: "user@example.com"

    try:
        async with main.lifespan(app):
            async with _cliente_http() as client:
                login = await client.post(
                    "/auth/login", json={"email": "a@b.com", "password": "senha1234"}
                )
                produtos = await client.get("/products")
                cadastro = await client.post("/auth/signup", json=_signup())
    finally:
        app.dependency_overrides.clear()

    # Sem banco, 503 com mensagem clara -- não um 500 genérico.
    for resposta in (login, produtos, cadastro):
        assert resposta.status_code == 503, resposta.text
        assert "indisponível" in resposta.json()["detail"]
