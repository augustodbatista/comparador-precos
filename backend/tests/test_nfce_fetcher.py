import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.services.nfce_fetcher import fetch_nfce_html, NfceFetchError

URL = "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=31260661585865266267650040002426521200179790|3|1"


def _mock_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("erro", request=MagicMock(), response=resp)
        if status_code >= 400 else None
    )
    return resp


@pytest.mark.asyncio
class TestFetchNfceHtml:
    async def test_retorna_html_quando_sefaz_200(self):
        html = "<html><body>Cupom</body></html>"
        with patch("app.services.nfce_fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=_mock_response(200, html))

            result = await fetch_nfce_html(URL)

        assert result == html

    async def test_lanca_NfceFetchError_quando_sefaz_403(self):
        with patch("app.services.nfce_fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=_mock_response(403))

            with pytest.raises(NfceFetchError) as exc_info:
                await fetch_nfce_html(URL)

        assert exc_info.value.status_code == 403

    async def test_lanca_NfceFetchError_quando_sefaz_500(self):
        with patch("app.services.nfce_fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=_mock_response(500))

            with pytest.raises(NfceFetchError) as exc_info:
                await fetch_nfce_html(URL)

        assert exc_info.value.status_code == 500

    async def test_propaga_timeout_exception(self):
        with patch("app.services.nfce_fetcher.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )

            with pytest.raises(httpx.TimeoutException):
                await fetch_nfce_html(URL)
