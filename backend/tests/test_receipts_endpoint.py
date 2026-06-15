"""
Testes de integração para GET /receipts e POST /receipts.
- fetch_nfce_html é mockado para isolar do acesso real à SEFAZ.
- O banco usa mongomock-motor (in-memory) injetado em app.state.db.
- O parser HTML roda de verdade usando a fixture mg_sefaz.html.
"""
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from app.services.nfce_fetcher import NfceFetchError
from main import app

FIXTURES = Path(__file__).parent / "fixtures"
MG_HTML = (FIXTURES / "mg_sefaz.html").read_text(encoding="utf-8")

VALID_URL = "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=31260661585865266267650040002426521200179790|3|1"
VALID_KEY = "31260661585865266267650040002426521200179790"


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
    async def test_retorna_200_com_dados_estruturados(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
            response = await client.get("/receipts/by-url", params={"url": VALID_URL})

        assert response.status_code == 200
        body = response.json()
        assert body["access_key"] == VALID_KEY
        assert body["issuer"]["name"] == "CASA RENA S/A"
        assert len(body["items"]) == 15
        assert body["totals"]["total"] == pytest.approx(124.10)

    async def test_retorna_dados_do_banco_sem_chamar_sefaz_se_ja_existe(self, client):
        # Salva via POST primeiro
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
            await client.get("/receipts/by-url", params={"url": VALID_URL})

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
            response = await client.get("/receipts/by-url", params={"url": VALID_URL})

        assert response.status_code == 200
        assert mock_fetch.call_count == 0  # SEFAZ não foi chamada

    async def test_retorna_422_para_url_invalida(self, client):
        response = await client.get("/receipts/by-url", params={"url": "https://google.com"})
        assert response.status_code == 422
        assert "NFC-e" in response.json()["detail"]

    async def test_retorna_422_quando_html_nao_reconhecido(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value="<html><body>erro</body></html>")):
            response = await client.get("/receipts/by-url", params={"url": VALID_URL})
        assert response.status_code == 422

    async def test_retorna_502_quando_sefaz_retorna_erro(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(side_effect=NfceFetchError(403, "Forbidden"))):
            response = await client.get("/receipts/by-url", params={"url": VALID_URL})
        assert response.status_code == 502

    async def test_retorna_504_em_timeout(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
            response = await client.get("/receipts/by-url", params={"url": VALID_URL})
        assert response.status_code == 504


@pytest.mark.asyncio
class TestPostReceipts:
    async def _get_parsed_body(self, client):
        """Helper: obtém dados parseados via GET para usar no POST."""
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
            r = await client.get("/receipts/by-url", params={"url": VALID_URL})
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


@pytest.mark.asyncio
class TestListReceipts:
    async def test_retorna_lista_vazia_se_banco_vazio(self, client):
        response = await client.get("/receipts")
        assert response.status_code == 200
        assert response.json() == []

    async def test_retorna_cupons_ordenados_por_data_decrescente(self, client):
        from app.db.repositories.receipts import insert_receipt
        doc_old = {
            "access_key": "11111111111111111111111111111111111111111111",
            "url": "https://url1",
            "issuer": {"name": "Loja A", "cnpj": "11111111000111", "address": "End A"},
            "items": [],
            "totals": {"total": 10.0, "paid": 10.0, "items_count": 0},
            "invoice": {"model": "65", "series": "1", "number": "1", "issued_at": "2026-06-07T10:00:00"}
        }
        doc_new = {
            "access_key": "22222222222222222222222222222222222222222222",
            "url": "https://url2",
            "issuer": {"name": "Loja B", "cnpj": "22222222000122", "address": "End B"},
            "items": [],
            "totals": {"total": 20.0, "paid": 20.0, "items_count": 0},
            "invoice": {"model": "65", "series": "1", "number": "2", "issued_at": "2026-06-07T12:00:00"}
        }
        await insert_receipt(app.state.db, doc_old)
        await insert_receipt(app.state.db, doc_new)

        response = await client.get("/receipts")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["access_key"] == "22222222222222222222222222222222222222222222"
        assert body[1]["access_key"] == "11111111111111111111111111111111111111111111"

    async def test_paginacao_retorna_itens_corretos(self, client):
        from app.db.repositories.receipts import insert_receipt
        for i in range(3):
            doc = {
                "access_key": f"{i}1111111111111111111111111111111111111111111",
                "url": f"https://url{i}",
                "issuer": {"name": f"Loja {i}", "cnpj": f"{i}1111111000111", "address": f"End {i}"},
                "items": [],
                "totals": {"total": 10.0, "paid": 10.0, "items_count": 0},
                "invoice": {"model": "65", "series": "1", "number": str(i), "issued_at": f"2026-06-07T10:00:0{i}"}
            }
            await insert_receipt(app.state.db, doc)

        # Página 1 com limite 2 (deve trazer as duas mais recentes: i=2 e i=1)
        response = await client.get("/receipts", params={"page": 1, "limit": 2})
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        assert body[0]["access_key"] == "21111111111111111111111111111111111111111111"
        assert body[1]["access_key"] == "11111111111111111111111111111111111111111111"

        # Página 2 com limite 2 (deve trazer a mais antiga restante: i=0)
        response2 = await client.get("/receipts", params={"page": 2, "limit": 2})
        assert response2.status_code == 200
        body2 = response2.json()
        assert len(body2) == 1
        assert body2[0]["access_key"] == "01111111111111111111111111111111111111111111"
