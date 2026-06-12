import httpx

# QR Codes são escaneados de celulares; UA mobile evita bloqueio por estados
# que verificam o agente antes de servir a página (PE e CE são conhecidos por isso)
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
    em um código de resposta próprio (502 para erros da SEFAZ, 504 para timeout)."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


async def fetch_nfce_html(url: str) -> str:
    """Faz GET na URL da SEFAZ simulando um browser mobile e retorna o HTML.

    Lança NfceFetchError se a SEFAZ retornar status >= 400.
    Deixa httpx.TimeoutException propagar para o endpoint tratar como 504.
    """
    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        timeout=httpx.Timeout(15.0),   # SEFAZ pode ser lenta em horários de pico fiscal
        follow_redirects=True,          # alguns estados redirecionam HTTP→HTTPS ou entre subdomínios
    ) as client:
        response = await client.get(url)

    # raise_for_status não é usado porque precisamos do status_code para NfceFetchError
    if response.status_code >= 400:
        raise NfceFetchError(response.status_code, f"SEFAZ retornou erro: {response.status_code}")

    return response.text
