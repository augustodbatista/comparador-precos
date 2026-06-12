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
    html: str


@router.post("/receipts", response_model=ReceiptResponse)
async def create_receipt(body: ReceiptRequest) -> ReceiptResponse:
    nfce_data = parse_qr_nfce(body.url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

    try:
        html = await fetch_nfce_html(nfce_data.url)
    except NfceFetchError as e:
        raise HTTPException(status_code=502, detail=f"SEFAZ retornou erro: {e.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao acessar a SEFAZ")

    return ReceiptResponse(access_key=nfce_data.access_key, html=html)
