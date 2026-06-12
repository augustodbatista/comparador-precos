import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.qr_parser import parse_qr_nfce
from app.services.nfce_fetcher import fetch_nfce_html, NfceFetchError

router = APIRouter()


class ReceiptRequest(BaseModel):
    url: str


class ReceiptResponse(BaseModel):
    access_key: str
    html: str  # HTML cru da SEFAZ — será parseado pelo BeautifulSoup na Task 5


@router.post("/receipts", response_model=ReceiptResponse)
async def create_receipt(body: ReceiptRequest) -> ReceiptResponse:
    """Recebe a URL do QR Code, valida que é uma NFC-e, busca o HTML na SEFAZ e retorna.

    Mapeamento de erros:
    - 422: URL sintaticamente válida mas semanticamente não é uma NFC-e
    - 502: A SEFAZ retornou um erro (4xx/5xx) — Bad Gateway para o cliente
    - 504: Timeout ao acessar a SEFAZ — Gateway Timeout
    """
    # 422 (Unprocessable Entity): chegou bem-formada mas não é NFC-e semanticamente
    nfce_data = parse_qr_nfce(body.url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

    try:
        html = await fetch_nfce_html(nfce_data.url)
    except NfceFetchError as e:
        # 502 (Bad Gateway): SEFAZ é serviço externo; erro dela não é culpa do cliente
        raise HTTPException(status_code=502, detail=f"SEFAZ retornou erro: {e.status_code}")
    except httpx.TimeoutException:
        # 504 (Gateway Timeout): diferencia lentidão da SEFAZ de outros erros
        raise HTTPException(status_code=504, detail="Timeout ao acessar a SEFAZ")

    return ReceiptResponse(access_key=nfce_data.access_key, html=html)
