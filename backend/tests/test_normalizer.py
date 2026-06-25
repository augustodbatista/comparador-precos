"""
Testes unitários para o serviço de normalização de produtos.
httpx é mockado — nenhuma chamada real ao Groq é feita.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.normalizer import normalize_items


def _mock_groq_response(names: list[str]):
    """Monta um mock de resposta do endpoint /chat/completions do Groq."""
    body = {"choices": [{"message": {"content": json.dumps({"names": names})}}]}
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
        mock_client.post.return_value = _mock_groq_response(normalized)

        with patch("app.services.normalizer._GROQ_API_KEY", "test-key"):
            with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
                MockClient.return_value.__aenter__.return_value = mock_client
                result = await normalize_items(descriptions)

        assert result == normalized

    async def test_lista_vazia_retorna_lista_vazia(self):
        result = await normalize_items([])
        assert result == []

    async def test_fallback_quando_api_key_ausente(self):
        descriptions = ["PRODUTO A", "PRODUTO B"]

        with patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            with patch("app.services.normalizer._GROQ_API_KEY", ""):
                result = await normalize_items(descriptions)

        assert result == descriptions

    async def test_fallback_quando_groq_fora(self):
        descriptions = ["PRODUTO A", "PRODUTO B"]

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("connection refused")

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
                with patch("app.services.normalizer._GROQ_API_KEY", "test-key"):
                    MockClient.return_value.__aenter__.return_value = mock_client
                    result = await normalize_items(descriptions)

        assert result == descriptions

    async def test_fallback_quando_json_invalido(self):
        descriptions = ["PRODUTO A"]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "não é json"}}]}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("app.services.normalizer._GROQ_API_KEY", "test-key"):
            with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
                MockClient.return_value.__aenter__.return_value = mock_client
                result = await normalize_items(descriptions)

        assert result == descriptions

    async def test_fallback_quando_tamanho_diverge(self):
        descriptions = ["PRODUTO A", "PRODUTO B", "PRODUTO C"]
        names_incompletas = ["Produto A", "Produto B"]

        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_groq_response(names_incompletas)

        with patch("app.services.normalizer._GROQ_API_KEY", "test-key"):
            with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
                MockClient.return_value.__aenter__.return_value = mock_client
                result = await normalize_items(descriptions)

        assert result == descriptions
