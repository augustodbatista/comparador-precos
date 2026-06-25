import re
from typing import NamedTuple
from urllib.parse import urlparse, parse_qs


class NfceData(NamedTuple):
    """Dados extraídos de um QR Code de NFC-e.

    Usa NamedTuple em vez de @dataclass: mesma interface (acesso por atributo,
    equality por valor, imutabilidade), mas mais idiomático para structs pequenas.
    """
    url: str         # URL original do QR Code (usada para buscar o HTML na SEFAZ)
    access_key: str  # chave de acesso de 44 dígitos (usada como ID único do cupom)


# Regex para validar chave de acesso: exatamente 44 dígitos numéricos (padrão SEFAZ/ABRASF)
_KEY_RE = re.compile(r"^\d{44}$")

# Regex de fallback: lookbehind/lookahead negativos evitam capturar sequências
# com mais de 44 dígitos (ex: CPF embutido junto à chave)
_FALLBACK_RE = re.compile(r"(?<!\d)(\d{44})(?!\d)")


def parse_qr_nfce(raw: str) -> NfceData | None:
    """Extrai URL e chave de acesso do conteúdo bruto de um QR Code NFC-e.

    Tenta três estratégias em ordem de confiabilidade:
    1. Query params chNFe / chConsNFCe — maioria dos estados (SP, RS)
    2. Query param p no formato "<chave>|<cDest>|<hash>" — MG, DF e outros
    3. Fallback: regex de 44 dígitos em qualquer parte da URL — BA, PE e não-padrão

    Retorna None para qualquer entrada que não seja uma NFC-e válida.
    """
    trimmed = raw.strip()
    if not trimmed:
        return None

    # Valida que é uma URL HTTP/HTTPS antes de tentar parsear os params
    parsed = urlparse(trimmed)
    if parsed.scheme not in ("http", "https"):
        return None

    params = parse_qs(parsed.query)

    # Estratégia 1: SP, RS e maioria dos estados expõem a chave diretamente no query param
    for param in ("chNFe", "chConsNFCe"):
        values = params.get(param, [])
        if values and _KEY_RE.match(values[0]):
            return NfceData(url=trimmed, access_key=values[0])

    # Estratégia 2: MG e outros usam o formato "<chave44d>|<cDest>|<cHashQRCode>" no param "p"
    # A chave de acesso é sempre o segmento 0 (antes do primeiro "|")
    p_values = params.get("p", [])
    if p_values:
        candidate = p_values[0].split("|")[0]
        if _KEY_RE.match(candidate):
            return NfceData(url=trimmed, access_key=candidate)

    # Estratégia 3: fallback para estados com formato não-padrão (BA, PE etc.)
    # Menos preciso — só usado quando as duas estratégias acima falham
    match = _FALLBACK_RE.search(trimmed)
    if match:
        return NfceData(url=trimmed, access_key=match.group(1))

    return None
