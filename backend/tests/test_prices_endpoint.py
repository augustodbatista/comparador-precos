from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from main import app

# Fixtures: cada receipt tem header + itens separados.
# Os itens são inseridos diretamente em 'prices' para simular o schema de 3 collections.

RECEIPT_HEADERS = [
    {
        "access_key": "11111111111111111111111111111111111111111111",
        "url": "https://url1",
        "issuer": {"name": "Supermercado A", "cnpj": "11111111000111", "address": "Rua A, 100"},
        "totals": {"total": 31.00, "paid": 31.00, "items_count": 2},
        "invoice": {"model": "65", "series": "1", "number": "101", "issued_at": "2026-06-07T10:00:00"},
    },
    {
        "access_key": "22222222222222222222222222222222222222222222",
        "url": "https://url2",
        "issuer": {"name": "Supermercado B", "cnpj": "22222222000122", "address": "Rua B, 200"},
        "totals": {"total": 4.90, "paid": 4.90, "items_count": 1},
        "invoice": {"model": "65", "series": "1", "number": "102", "issued_at": "2026-06-07T12:00:00"},
    },
    {
        "access_key": "33333333333333333333333333333333333333333333",
        "url": "https://url3",
        "issuer": {"name": "Supermercado C", "cnpj": "33333333000133", "address": "Rua C, 300"},
        "totals": {"total": 18.00, "paid": 18.00, "items_count": 1},
        "invoice": {"model": "65", "series": "1", "number": "103", "issued_at": "2026-06-07T14:00:00"},
    },
    {
        # Mesmo preço mínimo que receipt 2 (4.90), mas mais recente — ganha no desempate
        "access_key": "44444444444444444444444444444444444444444444",
        "url": "https://url4",
        "issuer": {"name": "Supermercado D", "cnpj": "44444444000144", "address": "Rua D, 400"},
        "totals": {"total": 4.90, "paid": 4.90, "items_count": 1},
        "invoice": {"model": "65", "series": "1", "number": "104", "issued_at": "2026-06-07T15:00:00"},
    },
]

# Preços: um documento por item comprado
PRICE_DOCS = [
    # Receipt 1 — Supermercado A
    {
        "product_id": "Leite Moça 395g",
        "receipt_id": "11111111111111111111111111111111111111111111",
        "original_description": "LEITE MOCA 395G",
        "internal_code": "P1",
        "quantity": 2.0, "unit": "UN", "unit_price": 5.50, "total_value": 11.00,
        "purchase_date": "2026-06-07T10:00:00",
        "invoice_number": "101", "invoice_series": "1", "invoice_model": "65",
        "issuer_cnpj": "11111111000111", "issuer_name": "Supermercado A", "issuer_address": "Rua A, 100",
        "receipt_url": "https://url1",
    },
    {
        "product_id": "Arroz Tora Tipo 1 5kg",
        "receipt_id": "11111111111111111111111111111111111111111111",
        "original_description": "ARROZ TIPO1 5KG TORA",
        "internal_code": "P2",
        "quantity": 1.0, "unit": "UN", "unit_price": 20.00, "total_value": 20.00,
        "purchase_date": "2026-06-07T10:00:00",
        "invoice_number": "101", "invoice_series": "1", "invoice_model": "65",
        "issuer_cnpj": "11111111000111", "issuer_name": "Supermercado A", "issuer_address": "Rua A, 100",
        "receipt_url": "https://url1",
    },
    # Receipt 2 — Supermercado B
    {
        "product_id": "Leite Moça 395g",
        "receipt_id": "22222222222222222222222222222222222222222222",
        "original_description": "LEITE MOCA NESTLE 395G",
        "internal_code": "X9",
        "quantity": 1.0, "unit": "UN", "unit_price": 4.90, "total_value": 4.90,
        "purchase_date": "2026-06-07T12:00:00",
        "invoice_number": "102", "invoice_series": "1", "invoice_model": "65",
        "issuer_cnpj": "22222222000122", "issuer_name": "Supermercado B", "issuer_address": "Rua B, 200",
        "receipt_url": "https://url2",
    },
    # Receipt 3 — Supermercado C
    {
        "product_id": "Leite Moça 395g",
        "receipt_id": "33333333333333333333333333333333333333333333",
        "original_description": "LT MOCA 395G",
        "internal_code": "LT1",
        "quantity": 3.0, "unit": "UN", "unit_price": 6.00, "total_value": 18.00,
        "purchase_date": "2026-06-07T14:00:00",
        "invoice_number": "103", "invoice_series": "1", "invoice_model": "65",
        "issuer_cnpj": "33333333000133", "issuer_name": "Supermercado C", "issuer_address": "Rua C, 300",
        "receipt_url": "https://url3",
    },
    # Receipt 4 — Supermercado D (mais recente, empata preço com receipt 2)
    {
        "product_id": "Leite Moça 395g",
        "receipt_id": "44444444444444444444444444444444444444444444",
        "original_description": "LEITE MOCA PROMOCAO 395G",
        "internal_code": "P1",
        "quantity": 1.0, "unit": "UN", "unit_price": 4.90, "total_value": 4.90,
        "purchase_date": "2026-06-07T15:00:00",
        "invoice_number": "104", "invoice_series": "1", "invoice_model": "65",
        "issuer_cnpj": "44444444000144", "issuer_name": "Supermercado D", "issuer_address": "Rua D, 400",
        "receipt_url": "https://url4",
    },
]

PRODUCT_DOCS = [
    {"normalized_name": "Leite Moça 395g"},
    {"normalized_name": "Arroz Tora Tipo 1 5kg"},
]


@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]

    await mock_db["receipts"].create_index("access_key", unique=True)
    await mock_db["products"].create_index("normalized_name", unique=True)
    await mock_db["prices"].create_index("product_id")

    now = datetime.now(timezone.utc)
    await mock_db["receipts"].insert_many([{**h, "created_at": now} for h in RECEIPT_HEADERS])
    await mock_db["prices"].insert_many([{**p, "created_at": now} for p in PRICE_DOCS])
    await mock_db["products"].insert_many([{**p, "created_at": now} for p in PRODUCT_DOCS])

    app.state.db = mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    mock_client.close()


@pytest.mark.asyncio
class TestPricesEndpoints:
    # -----------------------------------------------------------------------
    # GET /prices/latest
    # -----------------------------------------------------------------------
    async def test_latest_price_retorna_200_com_dados_corretos(self, client):
        response = await client.get("/prices/latest", params={"product_id": "Leite Moça 395g"})
        assert response.status_code == 200
        body = response.json()
        # Receipt 4 é o mais recente (15:00) com esse product_id
        assert body["product_id"] == "Leite Moça 395g"
        assert body["unit_price"] == 4.90
        assert body["description"] == "LEITE MOCA PROMOCAO 395G"
        assert body["normalized_name"] == "Leite Moça 395g"
        assert body["issuer_name"] == "Supermercado D"
        assert body["issuer_cnpj"] == "44444444000144"
        assert body["issuer_address"] == "Rua D, 400"
        assert body["purchase_date"] == "2026-06-07T15:00:00"
        assert body["invoice_number"] == "104"
        assert body["invoice_series"] == "1"
        assert body["invoice_model"] == "65"
        assert body["receipt_access_key"] == "44444444444444444444444444444444444444444444"
        assert body["receipt_url"] == "https://url4"

    async def test_latest_price_retorna_200_para_outro_produto(self, client):
        response = await client.get("/prices/latest", params={"product_id": "Arroz Tora Tipo 1 5kg"})
        assert response.status_code == 200
        body = response.json()
        assert body["unit_price"] == 20.00
        assert body["issuer_name"] == "Supermercado A"
        assert body["issuer_address"] == "Rua A, 100"

    async def test_latest_price_retorna_404_para_produto_inexistente(self, client):
        response = await client.get("/prices/latest", params={"product_id": "Produto Inexistente"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Produto não encontrado"

    async def test_latest_price_retorna_422_se_paramentro_ausente(self, client):
        response = await client.get("/prices/latest")
        assert response.status_code == 422

    # -----------------------------------------------------------------------
    # GET /prices/lowest
    # -----------------------------------------------------------------------
    async def test_lowest_price_retorna_200_com_menor_preco(self, client):
        # Preço mínimo: 4.90 (receipt 2 e 4). Desempate por data: receipt 4 (15:00)
        response = await client.get("/prices/lowest", params={"product_id": "Leite Moça 395g"})
        assert response.status_code == 200
        body = response.json()
        assert body["unit_price"] == 4.90
        assert body["issuer_name"] == "Supermercado D"
        assert body["issuer_address"] == "Rua D, 400"
        assert body["purchase_date"] == "2026-06-07T15:00:00"
        assert body["receipt_url"] == "https://url4"

    async def test_lowest_price_retorna_404_para_produto_inexistente(self, client):
        response = await client.get("/prices/lowest", params={"product_id": "Produto Inexistente"})
        assert response.status_code == 404

    async def test_lowest_price_retorna_422_se_paramentro_ausente(self, client):
        response = await client.get("/prices/lowest")
        assert response.status_code == 422

    # -----------------------------------------------------------------------
    # GET /prices/history
    # -----------------------------------------------------------------------
    async def test_history_retorna_lista_do_mais_recente(self, client):
        response = await client.get("/prices/history", params={"product_id": "Leite Moça 395g"})
        assert response.status_code == 200
        body = response.json()
        # 4 registros de Leite Moça 395g (receipts 1,2,3,4)
        assert len(body) == 4
        # Ordenado do mais recente para o mais antigo
        assert body[0]["purchase_date"] == "2026-06-07T15:00:00"
        assert body[-1]["purchase_date"] == "2026-06-07T10:00:00"

    async def test_history_retorna_404_para_produto_inexistente(self, client):
        response = await client.get("/prices/history", params={"product_id": "Inexistente"})
        assert response.status_code == 404

    # -----------------------------------------------------------------------
    # GET /products
    # -----------------------------------------------------------------------
    async def test_products_lista_todos_os_produtos(self, client):
        response = await client.get("/products")
        assert response.status_code == 200
        body = response.json()
        names = [p["normalized_name"] for p in body]
        assert "Leite Moça 395g" in names
        assert "Arroz Tora Tipo 1 5kg" in names


@pytest.mark.asyncio
class TestOllamaHealth:
    async def test_retorna_ok_quando_ollama_acessivel(self, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        with patch("app.routes.prices.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            response = await client.get("/health/ollama")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_retorna_offline_quando_ollama_inacessivel(self, client):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("connection refused")

        with patch("app.routes.prices.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            response = await client.get("/health/ollama")

        assert response.status_code == 200
        assert response.json()["status"] == "offline"
