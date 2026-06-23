"""
Testes unitários para o serviço de normalização de produtos.
httpx é mockado — nenhuma chamada real ao Ollama é feita.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.normalizer import normalize_items


def _mock_ollama_response(names: list[str]):
    """Monta um mock de resposta do /api/chat do Ollama."""
    body = {"message": {"content": json.dumps({"names": names})}}
    mock_resp = MagicMock()
    mock_resp.json.return_value = body
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


@pytest.mark.asyncio
class TestNormalizeItems:
    async def test_retorna_nomes_normalizados(self):
        descriptions = ["ARROZ TIPO1 5KG TORA", "FEIJAO CARIOCA 1KG CAMIL"]
        normalized = ["Arroz Tipo 1 Tora 5kg", "Feijão Carioca Camil 1kg"]

        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_ollama_response(normalized)

        with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            result = await normalize_items(descriptions)

        assert result == normalized

    async def test_lista_vazia_retorna_lista_vazia(self):
        # Não deve chamar o Ollama
        result = await normalize_items([])
        assert result == []

    async def test_fallback_quando_ollama_fora(self):
        descriptions = ["PRODUTO A", "PRODUTO B"]

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("connection refused")

        with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            result = await normalize_items(descriptions)

        # Deve retornar as descrições originais sem lançar exceção
        assert result == descriptions

    async def test_fallback_quando_json_invalido(self):
        descriptions = ["PRODUTO A"]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        # Ollama retorna conteúdo que não é JSON válido
        mock_resp.json.return_value = {"message": {"content": "não é json"}}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            result = await normalize_items(descriptions)

        assert result == descriptions

    async def test_fallback_quando_tamanho_diverge(self):
        # Modelo retornou menos itens do que o enviado — descarta tudo
        descriptions = ["PRODUTO A", "PRODUTO B", "PRODUTO C"]
        names_incompletas = ["Produto A", "Produto B"]  # falta um item

        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_ollama_response(names_incompletas)

        with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            result = await normalize_items(descriptions)

        assert result == descriptions
