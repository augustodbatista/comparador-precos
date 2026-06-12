import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
import httpx
from httpx import AsyncClient, ASGITransport
from main import app
from app.services.nfce_fetcher import NfceFetchError

VALID_URL = "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=31260661585865266267650040002426521200179790|3|1"
VALID_KEY = "31260661585865266267650040002426521200179790"
SAMPLE_HTML = "<html><body>Nota Fiscal</body></html>"


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestPostReceipts:
    async def test_retorna_200_com_access_key_e_html(self, client):
        with patch("app.routes.receipts.fetch_nfce_html", new=AsyncMock(return_value=SAMPLE_HTML)):
            response = await client.post("/receipts", json={"url": VALID_URL})

        assert response.status_code == 200
        body = response.json()
        assert body["access_key"] == VALID_KEY
        assert body["html"] == SAMPLE_HTML

    async def test_retorna_422_para_url_invalida(self, client):
        response = await client.post("/receipts", json={"url": "https://google.com"})
        assert response.status_code == 422
        assert "NFC-e" in response.json()["detail"]

    async def test_retorna_502_quando_sefaz_retorna_403(self, client):
        with patch(
            "app.routes.receipts.fetch_nfce_html",
            new=AsyncMock(side_effect=NfceFetchError(403, "Forbidden")),
        ):
            response = await client.post("/receipts", json={"url": VALID_URL})

        assert response.status_code == 502

    async def test_retorna_504_em_timeout(self, client):
        with patch(
            "app.routes.receipts.fetch_nfce_html",
            new=AsyncMock(side_effect=httpx.TimeoutException("timeout")),
        ):
            response = await client.post("/receipts", json={"url": VALID_URL})

        assert response.status_code == 504

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
