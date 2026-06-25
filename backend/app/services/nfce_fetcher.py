import httpx

# Headers de browser mobile — necessários porque alguns estados (PE, CE) verificam
# o User-Agent antes de servir o HTML da nota. Sem esses headers, a SEFAZ retorna 403.
# QR Codes são escaneados de celulares, então simular um browser mobile é o comportamento esperado.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 10; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class NfceFetchError(Exception):
    """Encapsula o status HTTP da SEFAZ para que o endpoint mapeie cada caso
    em um código de resposta próprio:
    - status >= 400 da SEFAZ → 502 Bad Gateway na API
    - timeout                → 504 Gateway Timeout na API
    """

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code  # status HTTP original da SEFAZ (ex: 403, 500)


async def fetch_nfce_html(url: str) -> str:
    """Faz GET na URL da SEFAZ simulando um browser mobile e retorna o HTML completo.

    - Timeout de 15s: a SEFAZ pode ser lenta em horários de pico fiscal (final de mês).
    - follow_redirects=True: alguns estados redirecionam HTTP→HTTPS ou entre subdomínios.
    - Lança NfceFetchError se a SEFAZ retornar status >= 400.
    - Deixa httpx.TimeoutException propagar — o endpoint a captura e retorna 504.
    """
    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
    ) as client:
        response = await client.get(url)

    # Não usa raise_for_status() porque precisamos do status_code para NfceFetchError
    if response.status_code >= 400:
        raise NfceFetchError(response.status_code, f"SEFAZ retornou erro: {response.status_code}")

    return response.text
