import re
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs


@dataclass(frozen=True)
class NfceData:
    url: str
    access_key: str


_KEY_RE = re.compile(r"^\d{44}$")
_FALLBACK_RE = re.compile(r"(?<!\d)(\d{44})(?!\d)")


def parse_qr_nfce(raw: str) -> NfceData | None:
    trimmed = raw.strip()
    if not trimmed:
        return None

    parsed = urlparse(trimmed)
    if parsed.scheme not in ("http", "https"):
        return None

    params = parse_qs(parsed.query)

    # chNFe (SP, RS e maioria dos estados)
    for param in ("chNFe", "chConsNFCe"):
        values = params.get(param, [])
        if values and _KEY_RE.match(values[0]):
            return NfceData(url=trimmed, access_key=values[0])

    # param p (MG e outros): "<chave>|<cDest>|<hash>"
    p_values = params.get("p", [])
    if p_values:
        candidate = p_values[0].split("|")[0]
        if _KEY_RE.match(candidate):
            return NfceData(url=trimmed, access_key=candidate)

    # fallback: 44 dígitos consecutivos em qualquer parte da URL
    match = _FALLBACK_RE.search(trimmed)
    if match:
        return NfceData(url=trimmed, access_key=match.group(1))

    return None
