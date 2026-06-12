import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from main import app

RECEIPT_1 = {
    "access_key": "11111111111111111111111111111111111111111111",
    "url": "https://url1",
    "issuer": {"name": "Supermercado A", "cnpj": "11111111000111", "address": "Rua A"},
    "items": [
        {"code": "P1", "description": "Leite Moça", "qty": 2.0, "unit": "UN", "unit_price": 5.50, "total": 11.00},
        {"code": "P2", "description": "Arroz 5kg", "qty": 1.0, "unit": "UN", "unit_price": 20.00, "total": 20.00}
    ],
    "totals": {"total": 31.00, "paid": 31.00, "items_count": 2},
    "invoice": {"model": "65", "series": "1", "number": "101", "issued_at": "2026-06-07T10:00:00"}
}

RECEIPT_2 = {
    "access_key": "22222222222222222222222222222222222222222222",
    "url": "https://url2",
    "issuer": {"name": "Supermercado B", "cnpj": "22222222000122", "address": "Rua B"},
    "items": [
        {"code": "P1", "description": "Leite Moça Nestle", "qty": 1.0, "unit": "UN", "unit_price": 4.90, "total": 4.90}
    ],
    "totals": {"total": 4.90, "paid": 4.90, "items_count": 1},
    "invoice": {"model": "65", "series": "1", "number": "102", "issued_at": "2026-06-07T12:00:00"}
}

RECEIPT_3 = {
    "access_key": "33333333333333333333333333333333333333333333",
    "url": "https://url3",
    "issuer": {"name": "Supermercado C", "cnpj": "33333333000133", "address": "Rua C"},
    "items": [
        {"code": "P1", "description": "Leite Moca", "qty": 3.0, "unit": "UN", "unit_price": 6.00, "total": 18.00}
    ],
    "totals": {"total": 18.00, "paid": 18.00, "items_count": 1},
    "invoice": {"model": "65", "series": "1", "number": "103", "issued_at": "2026-06-07T14:00:00"}
}

# Usado para testar empate de preço unitário mais baixo, priorizando o mais recente
RECEIPT_4 = {
    "access_key": "44444444444444444444444444444444444444444444",
    "url": "https://url4",
    "issuer": {"name": "Supermercado D", "cnpj": "44444444000144", "address": "Rua D"},
    "items": [
        {"code": "P1", "description": "Leite Moça Promoção", "qty": 1.0, "unit": "UN", "unit_price": 4.90, "total": 4.90}
    ],
    "totals": {"total": 4.90, "paid": 4.90, "items_count": 1},
    "invoice": {"model": "65", "series": "1", "number": "104", "issued_at": "2026-06-07T15:00:00"}
}


@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]
    await mock_db["receipts"].create_index("access_key", unique=True)

    # Popula com os dados de teste
    await mock_db["receipts"].insert_many([
        RECEIPT_1.copy(),
        RECEIPT_2.copy(),
        RECEIPT_3.copy(),
        RECEIPT_4.copy()
    ])

    app.state.db = mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    mock_client.close()


@pytest.mark.asyncio
class TestPricesEndpoints:
    # ---------------------------------------------------------------------------
    # Testes para GET /prices/latest
    # ---------------------------------------------------------------------------
    async def test_latest_price_retorna_200_com_dados_corretos(self, client):
        response = await client.get("/prices/latest", params={"product_id": "P1"})
        assert response.status_code == 200
        body = response.json()
        assert body["product_id"] == "P1"
        assert body["unit_price"] == 4.90  # O mais recente é o RECEIPT_4 (15:00), que tem preço 4.90
        assert body["description"] == "Leite Moça Promoção"
        assert body["issuer_name"] == "Supermercado D"
        assert body["purchase_date"] == "2026-06-07T15:00:00"

    async def test_latest_price_retorna_200_para_outro_produto(self, client):
        response = await client.get("/prices/latest", params={"product_id": "P2"})
        assert response.status_code == 200
        body = response.json()
        assert body["product_id"] == "P2"
        assert body["unit_price"] == 20.00
        assert body["issuer_name"] == "Supermercado A"

    async def test_latest_price_retorna_404_para_produto_inexistente(self, client):
        response = await client.get("/prices/latest", params={"product_id": "P_INEXISTENTE"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Produto não encontrado"

    async def test_latest_price_retorna_422_se_paramentro_ausente(self, client):
        response = await client.get("/prices/latest")
        assert response.status_code == 422

    # ---------------------------------------------------------------------------
    # Testes para GET /prices/lowest
    # ---------------------------------------------------------------------------
    async def test_lowest_price_retorna_200_com_menor_preco(self, client):
        # O menor preço para P1 é 4.90 (do RECEIPT_2 e RECEIPT_4)
        # Deve desempatar retornando o mais recente, que é o RECEIPT_4 (15:00)
        response = await client.get("/prices/lowest", params={"product_id": "P1"})
        assert response.status_code == 200
        body = response.json()
        assert body["product_id"] == "P1"
        assert body["unit_price"] == 4.90
        assert body["description"] == "Leite Moça Promoção"
        assert body["issuer_name"] == "Supermercado D"
        assert body["purchase_date"] == "2026-06-07T15:00:00"

    async def test_lowest_price_retorna_404_para_produto_inexistente(self, client):
        response = await client.get("/prices/lowest", params={"product_id": "P_INEXISTENTE"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Produto não encontrado"

    async def test_lowest_price_retorna_422_se_paramentro_ausente(self, client):
        response = await client.get("/prices/lowest")
        assert response.status_code == 422
