import re
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs


@dataclass(frozen=True)
class NfceData:
    url: str
    access_key: str


# Chave de acesso NFC-e tem exatamente 44 dígitos numéricos (padrão SEFAZ/ABRASF)
_KEY_RE = re.compile(r"^\d{44}$")

# Lookbehind/lookahead negativos evitam capturar sequências vizinhas com mais de 44 dígitos
_FALLBACK_RE = re.compile(r"(?<!\d)(\d{44})(?!\d)")


def parse_qr_nfce(raw: str) -> NfceData | None:
    """Extrai URL e chave de acesso do conteúdo bruto de um QR Code NFC-e.

    Tenta três estratégias em ordem de confiabilidade:
    1. Query params chNFe / chConsNFCe (maioria dos estados)
    2. Query param p no formato <chave>|<cDest>|<hash> (MG e outros)
    3. Fallback: 44 dígitos consecutivos em qualquer parte da URL

    Retorna None para qualquer entrada que não seja uma NFC-e válida.
    """
    trimmed = raw.strip()
    if not trimmed:
        return None

    parsed = urlparse(trimmed)
    if parsed.scheme not in ("http", "https"):
        return None

    params = parse_qs(parsed.query)

    # SP, RS e maioria dos estados expõem a chave diretamente no query param
    for param in ("chNFe", "chConsNFCe"):
        values = params.get(param, [])
        if values and _KEY_RE.match(values[0]):
            return NfceData(url=trimmed, access_key=values[0])

    # MG e outros: formato "<chave44d>|<cDest>|<cHashQRCode>" — a chave é sempre o segmento 0
    p_values = params.get("p", [])
    if p_values:
        candidate = p_values[0].split("|")[0]
        if _KEY_RE.match(candidate):
            return NfceData(url=trimmed, access_key=candidate)

    # Estados com formato não-padrão (BA, PE etc.) — último recurso; menos preciso
    match = _FALLBACK_RE.search(trimmed)
    if match:
        return NfceData(url=trimmed, access_key=match.group(1))

    return None
