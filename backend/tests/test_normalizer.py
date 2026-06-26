"""
Testes unitários para o serviço de normalização de produtos.
httpx é mockado — nenhuma chamada real ao Groq é feita.
"""
import json
import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.normalizer import normalize_items, pre_process, canonicalize


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
        descriptions = ["CERV BRAHMA", "LEITE LV"]
        expected = ["Cerveja BRAHMA", "LEITE Longa Vida"]

        with patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            with patch("app.services.normalizer._GROQ_API_KEY", ""):
                result = await normalize_items(descriptions)

        assert result == expected

    async def test_fallback_quando_groq_fora(self):
        descriptions = ["CERV BRAHMA", "LEITE LV"]
        expected = ["Cerveja BRAHMA", "LEITE Longa Vida"]

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("connection refused")

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
                with patch("app.services.normalizer._GROQ_API_KEY", "test-key"):
                    MockClient.return_value.__aenter__.return_value = mock_client
                    result = await normalize_items(descriptions)

        assert result == expected

    async def test_fallback_quando_json_invalido(self):
        descriptions = ["CERV BRAHMA"]
        expected = ["Cerveja BRAHMA"]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "não é json"}}]}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        with patch("app.services.normalizer._GROQ_API_KEY", "test-key"):
            with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
                MockClient.return_value.__aenter__.return_value = mock_client
                result = await normalize_items(descriptions)

        assert result == expected

    async def test_fallback_quando_tamanho_diverge(self):
        descriptions = ["CERV BRAHMA", "LEITE LV", "BISC NEGRESCO"]
        names_incompletas = ["Cerveja Brahma", "Leite Longa Vida"]
        expected = ["Cerveja BRAHMA", "LEITE Longa Vida", "Biscoito NEGRESCO"]

        mock_client = AsyncMock()
        mock_client.post.return_value = _mock_groq_response(names_incompletas)

        with patch("app.services.normalizer._GROQ_API_KEY", "test-key"):
            with patch("app.services.normalizer.httpx.AsyncClient") as MockClient:
                MockClient.return_value.__aenter__.return_value = mock_client
                result = await normalize_items(descriptions)

        assert result == expected


class TestPreProcess:
    def test_expande_abreviacao_conhecida(self):
        assert pre_process("CERV BRAHMA 350ML") == "Cerveja BRAHMA 350ML"

    def test_expande_lv_para_longa_vida(self):
        assert pre_process("LEITE LV CAMPONESA 1L") == "LEITE Longa Vida CAMPONESA 1L"

    def test_expande_lvida_para_longa_vida(self):
        assert pre_process("LEITE LVIDA PIRACANJUBA") == "LEITE Longa Vida PIRACANJUBA"

    def test_expande_bisc(self):
        assert pre_process("BISC NEGRESCO 90G") == "Biscoito NEGRESCO 90G"

    def test_normaliza_unicode_nfc(self):
        # NFD: 'ã' como 'a' + combining tilde → NFC: 'ã'
        nfd_input = unicodedata.normalize("NFD", "Pão")
        assert pre_process(nfd_input) == "Pão"

    def test_preserva_token_desconhecido(self):
        assert pre_process("BRAHMA EXTRA") == "BRAHMA EXTRA"

    def test_string_vazia(self):
        assert pre_process("") == ""

    def test_multiplas_abreviacoes(self):
        assert pre_process("BISC LV SUAV") == "Biscoito Longa Vida Suavizante"


class TestCanonicalize:
    def test_retorna_existente_acima_do_threshold(self):
        existing = ["Bombom Lacta Favoritos 250.6g", "Arroz Tipo 1 Tora 5kg"]
        # "Bom Bom Lacta Favoritos 250.6g" vs "Bombom Lacta Favoritos 250.6g" ≈ 0.983 > 0.97
        result = canonicalize("Bom Bom Lacta Favoritos 250.6g", existing)
        assert result == "Bombom Lacta Favoritos 250.6g"

    def test_retorna_nome_novo_abaixo_do_threshold(self):
        existing = ["Pipoca Doce Lin 1kg"]
        # "Pipoca Doce Lin 40g" vs "Pipoca Doce Lin 1kg" ≈ 0.895 < 0.97 → produto diferente
        result = canonicalize("Pipoca Doce Lin 40g", existing)
        assert result == "Pipoca Doce Lin 40g"

    def test_lista_vazia_retorna_nome(self):
        assert canonicalize("Produto Novo", []) == "Produto Novo"

    def test_match_exato_retorna_existente(self):
        existing = ["Cerveja Brahma Lata 350ml"]
        assert canonicalize("Cerveja Brahma Lata 350ml", existing) == "Cerveja Brahma Lata 350ml"

    def test_escolhe_melhor_match(self):
        existing = ["Arroz Tipo 1 5kg", "Bombom Lacta Favoritos 250.6g"]
        # "Bom Bom Lacta Favoritos 250.6g" ≈ 0.983 com "Bombom Lacta..." > 0.97
        result = canonicalize("Bom Bom Lacta Favoritos 250.6g", existing)
        assert result == "Bombom Lacta Favoritos 250.6g"
