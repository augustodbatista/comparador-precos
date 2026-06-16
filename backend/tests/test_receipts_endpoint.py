"""
Testes de integração para GET /receipts e POST /receipts.
- fetch_nfce_html é mockado para isolar do acesso real à SEFAZ.
- O banco usa mongomock-motor (in-memory) injetado em app.state.db.
- O parser HTML roda de verdade usando a fixture mg_sefaz.html.
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.services.html_parser import parse_nfce_html
from app.services.nfce_fetcher import NfceFetchError
from main import app

FIXTURES = Path(__file__).parent / "fixtures"
MG_HTML = (FIXTURES / "mg_sefaz.html").read_text(encoding="utf-8")

VALID_URL = "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=31260661585865266267650040002426521200179790|3|1"
VALID_KEY = "31260661585865266267650040002426521200179790"


def receipt_doc(access_key: str, created_at: datetime) -> dict:
    return {
        "access_key": access_key,
        "url": f"https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p={access_key}|3|1",
        **parse_nfce_html(MG_HTML),
        "created_at": created_at,
    }


@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]
    await mock_db["receipts"].create_index("access_key", unique=True)
    app.state.db = mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    mock_client.close()


@pytest.mark.asyncio
class TestGetReceipts:
    async def test_lista_historico_salvo_sem_url(self, client):
        older = receipt_doc("1" * 44, datetime(2026, 6, 1, tzinfo=timezone.utc))
        newer = receipt_doc("2" * 44, datetime(2026, 6, 2, tzinfo=timezone.utc))
        await app.state.db["receipts"].insert_many([older, newer])

        response = await client.get("/receipts")

        assert response.status_code == 200
        body = response.json()
        assert [receipt["access_key"] for receipt in body] == ["2" * 44, "1" * 44]
        assert body[0]["created_at"].startswith("2026-06-02T00:00:00")

    async def test_lista_historico_respeita_limit_e_skip(self, client):
        docs = [
            receipt_doc("1" * 44, datetime(2026, 6, 1, tzinfo=timezone.utc)),
            receipt_doc("2" * 44, datetime(2026, 6, 2, tzinfo=timezone.utc)),
            receipt_doc("3" * 44, datetime(2026, 6, 3, tzinfo=timezone.utc)),
        ]
        await app.state.db["receipts"].insert_many(docs)

        response = await client.get("/receipts", params={"limit": 1, "skip": 1})

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["access_key"] == "2" * 44

    async def test_retorna_200_com_dados_estruturados(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
            response = await client.get("/receipts", params={"url": VALID_URL})

        assert response.status_code == 200
        body = response.json()
        assert body["access_key"] == VALID_KEY
        assert body["issuer"]["name"] == "CASA RENA S/A"
        assert len(body["items"]) == 15
        assert body["totals"]["total"] == pytest.approx(124.10)

    async def test_retorna_dados_do_banco_sem_chamar_sefaz_se_ja_existe(self, client):
        # Salva via POST primeiro
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
            await client.get("/receipts", params={"url": VALID_URL})

        # Segunda chamada ao GET não deve chamar a SEFAZ
        mock_fetch = AsyncMock(return_value=MG_HTML)
        with patch("app.routes.receipts.fetch_nfce_html", new=mock_fetch):
            # Para ter algo no banco, precisamos salvar antes via POST
            pass

        # Insere diretamente no banco para simular cupom já salvo
        from app.db.repositories.receipts import insert_receipt
        from app.services.html_parser import parse_nfce_html
        from app.services.qr_parser import parse_qr_nfce
        nfce = parse_qr_nfce(VALID_URL)
        parsed = parse_nfce_html(MG_HTML)
        await insert_receipt(app.state.db, {"access_key": nfce.access_key, "url": nfce.url, **parsed})

        mock_fetch = AsyncMock(return_value=MG_HTML)
        with patch("app.routes.receipts.fetch_nfce_html", new=mock_fetch):
            response = await client.get("/receipts", params={"url": VALID_URL})

        assert response.status_code == 200
        assert mock_fetch.call_count == 0  # SEFAZ não foi chamada

    async def test_retorna_422_para_url_invalida(self, client):
        response = await client.get("/receipts", params={"url": "https://google.com"})
        assert response.status_code == 422
        assert "NFC-e" in response.json()["detail"]

    async def test_retorna_422_quando_html_nao_reconhecido(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value="<html><body>erro</body></html>")):
            response = await client.get("/receipts", params={"url": VALID_URL})
        assert response.status_code == 422

    async def test_retorna_502_quando_sefaz_retorna_erro(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(side_effect=NfceFetchError(403, "Forbidden"))):
            response = await client.get("/receipts", params={"url": VALID_URL})
        assert response.status_code == 502

    async def test_retorna_504_em_timeout(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
            response = await client.get("/receipts", params={"url": VALID_URL})
        assert response.status_code == 504


@pytest.mark.asyncio
class TestPostReceipts:
    async def _get_parsed_body(self, client):
        """Helper: obtém dados parseados via GET para usar no POST."""
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
            r = await client.get("/receipts", params={"url": VALID_URL})
        return r.json()

    async def test_retorna_201_ao_salvar_novo_cupom(self, client):
        body = await self._get_parsed_body(client)
        response = await client.post("/receipts", json=body)
        assert response.status_code == 201
        assert response.json()["access_key"] == VALID_KEY

    async def test_retorna_200_quando_cupom_ja_existe(self, client):
        body = await self._get_parsed_body(client)
        await client.post("/receipts", json=body)
        response = await client.post("/receipts", json=body)
        assert response.status_code == 200

    async def test_dados_persistidos_no_banco(self, client):
        body = await self._get_parsed_body(client)
        await client.post("/receipts", json=body)
        doc = await app.state.db["receipts"].find_one({"access_key": VALID_KEY})
        assert doc is not None
        assert doc["issuer"]["cnpj"] == "21253729001979"

    async def test_retorna_422_sem_body(self, client):
        response = await client.post("/receipts")
        assert response.status_code == 422

    async def test_cors_preflight(self, client):
        response = await client.options(
            "/receipts",
            headers={
                "Origin": "https://comparador-precos-xi.vercel.app",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
