import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from main import app

# normalized_name é o campo que as queries usam (Task 6).
# Os itens de lojas diferentes têm descriptions diferentes mas o mesmo normalized_name,
# o que é exatamente o que viabiliza a comparação cross-store.

RECEIPT_1 = {
    "access_key": "11111111111111111111111111111111111111111111",
    "url": "https://url1",
    "issuer": {"name": "Supermercado A", "cnpj": "11111111000111", "address": "Rua A, 100"},
    "items": [
        {
            "code": "P1", "description": "LEITE MOCA 395G",
            "normalized_name": "Leite Moça 395g",
            "qty": 2.0, "unit": "UN", "unit_price": 5.50, "total": 11.00,
        },
        {
            "code": "P2", "description": "ARROZ TIPO1 5KG TORA",
            "normalized_name": "Arroz Tora Tipo 1 5kg",
            "qty": 1.0, "unit": "UN", "unit_price": 20.00, "total": 20.00,
        },
    ],
    "totals": {"total": 31.00, "paid": 31.00, "items_count": 2},
    "invoice": {"model": "65", "series": "1", "number": "101", "issued_at": "2026-06-07T10:00:00"},
}

RECEIPT_2 = {
    "access_key": "22222222222222222222222222222222222222222222",
    "url": "https://url2",
    "issuer": {"name": "Supermercado B", "cnpj": "22222222000122", "address": "Rua B, 200"},
    "items": [
        {
            "code": "X9", "description": "LEITE MOCA NESTLE 395G",
            "normalized_name": "Leite Moça 395g",  # mesmo produto, código diferente
            "qty": 1.0, "unit": "UN", "unit_price": 4.90, "total": 4.90,
        },
    ],
    "totals": {"total": 4.90, "paid": 4.90, "items_count": 1},
    "invoice": {"model": "65", "series": "1", "number": "102", "issued_at": "2026-06-07T12:00:00"},
}

RECEIPT_3 = {
    "access_key": "33333333333333333333333333333333333333333333",
    "url": "https://url3",
    "issuer": {"name": "Supermercado C", "cnpj": "33333333000133", "address": "Rua C, 300"},
    "items": [
        {
            "code": "LT1", "description": "LT MOCA 395G",
            "normalized_name": "Leite Moça 395g",
            "qty": 3.0, "unit": "UN", "unit_price": 6.00, "total": 18.00,
        },
    ],
    "totals": {"total": 18.00, "paid": 18.00, "items_count": 1},
    "invoice": {"model": "65", "series": "1", "number": "103", "issued_at": "2026-06-07T14:00:00"},
}

# Mesmo preço mínimo que RECEIPT_2 (4.90), mas mais recente — deve ganhar no desempate
RECEIPT_4 = {
    "access_key": "44444444444444444444444444444444444444444444",
    "url": "https://url4",
    "issuer": {"name": "Supermercado D", "cnpj": "44444444000144", "address": "Rua D, 400"},
    "items": [
        {
            "code": "P1", "description": "LEITE MOCA PROMOCAO 395G",
            "normalized_name": "Leite Moça 395g",
            "qty": 1.0, "unit": "UN", "unit_price": 4.90, "total": 4.90,
        },
    ],
    "totals": {"total": 4.90, "paid": 4.90, "items_count": 1},
    "invoice": {"model": "65", "series": "1", "number": "104", "issued_at": "2026-06-07T15:00:00"},
}


@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]
    await mock_db["receipts"].create_index("access_key", unique=True)
    await mock_db["receipts"].insert_many([
        RECEIPT_1.copy(), RECEIPT_2.copy(), RECEIPT_3.copy(), RECEIPT_4.copy()
    ])
    app.state.db = mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    mock_client.close()


@pytest.mark.asyncio
class TestPricesEndpoints:
    # ---------------------------------------------------------------------------
    # GET /prices/latest
    # ---------------------------------------------------------------------------
    async def test_latest_price_retorna_200_com_dados_corretos(self, client):
        response = await client.get("/prices/latest", params={"product_id": "Leite Moça 395g"})
        assert response.status_code == 200
        body = response.json()
        # RECEIPT_4 é o mais recente (15:00) com esse normalized_name
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
        assert body["product_id"] == "Arroz Tora Tipo 1 5kg"
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

    # ---------------------------------------------------------------------------
    # GET /prices/lowest
    # ---------------------------------------------------------------------------
    async def test_lowest_price_retorna_200_com_menor_preco(self, client):
        # Preço mínimo de "Leite Moça 395g" é 4.90 (RECEIPT_2 e RECEIPT_4).
        # Desempate por data mais recente → RECEIPT_4 (15:00)
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
