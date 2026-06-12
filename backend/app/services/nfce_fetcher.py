import httpx

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
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


async def fetch_nfce_html(url: str) -> str:
    async with httpx.AsyncClient(
        headers=BROWSER_HEADERS,
        timeout=httpx.Timeout(15.0),
        follow_redirects=True,
    ) as client:
        response = await client.get(url)

    if response.status_code >= 400:
        raise NfceFetchError(response.status_code, f"SEFAZ retornou erro: {response.status_code}")

    return response.text
