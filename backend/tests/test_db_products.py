"""Testes para o repositório de produtos."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.db.repositories.products import list_all_product_names


@pytest.mark.asyncio
class TestListAllProductNames:
    async def test_retorna_lista_de_nomes(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[
            {"normalized_name": "Arroz Tipo 1 Tora 5kg"},
            {"normalized_name": "Cerveja Brahma Lata 350ml"},
        ])
        mock_db["products"].find.return_value = mock_cursor

        result = await list_all_product_names(mock_db)

        assert result == ["Arroz Tipo 1 Tora 5kg", "Cerveja Brahma Lata 350ml"]

    async def test_retorna_lista_vazia_quando_sem_produtos(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_db["products"].find.return_value = mock_cursor

        result = await list_all_product_names(mock_db)

        assert result == []
