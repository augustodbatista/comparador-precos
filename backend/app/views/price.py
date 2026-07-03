"""Schemas de resposta (view) do catálogo de produtos e consulta de preços."""
from pydantic import BaseModel


class ProductItem(BaseModel):
    """Produto do catálogo retornado por GET /products."""
    normalized_name: str  # nome legível gerado pelo Ollama (usado como product_id nas queries)


class PriceResponse(BaseModel):
    """Resposta completa de uma consulta de preço.

    Contém dados do produto, da compra (quantidade, preço), da nota fiscal
    e da loja — tudo em um único documento para evitar joins no cliente.
    """
    product_id: str           # = normalized_name (chave de busca cross-store)
    description: str          # nome bruto original da SEFAZ (para auditoria)
    normalized_name: str | None

    unit_price: float
    quantity: float
    unit: str
    total_value: float

    purchase_date: str        # data de emissão da nota (ISO format)
    invoice_number: str
    invoice_series: str
    invoice_model: str

    issuer_name: str          # nome do estabelecimento
    issuer_cnpj: str
    issuer_address: str

    receipt_access_key: str   # chave de acesso de 44 dígitos da NF-e
    receipt_url: str          # URL do QR Code (para link direto ao cupom na SEFAZ)
