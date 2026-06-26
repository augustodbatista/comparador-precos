"""
Serviço de normalização de nomes de produtos via Groq API (llama-3.3-70b-versatile).

Pipeline de 3 fases:
    1. pre_process   — expansão determinística de abreviações e correção de encoding NFC
    2. LLM (Groq)   — Title Case, expansão residual, correção de typos
    3. canonicalize  — fuzzy match contra produtos existentes; garante unicidade no banco

Por que batch:
    O(1) chamadas ao Groq para N produtos de um cupom.

Por que fallback silencioso:
    O insert não pode travar por falha de API. Se o LLM falhar, pre_process +
    canonicalize já melhoram o resultado vs a descrição bruta original.
"""
import json
import logging
import os
import unicodedata
from difflib import SequenceMatcher

import httpx

logger = logging.getLogger(__name__)

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_MODEL = "llama-3.3-70b-versatile"
_TIMEOUT = 30.0
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

CANONICAL_THRESHOLD = 0.92

_ABBREVS: dict[str, str] = {
    # Categorias de produto
    "BISC": "Biscoito",
    "CERV": "Cerveja",
    "REFRIG": "Refrigerante",
    "ENERG": "Energético",
    "DET": "Detergente",    "DETER": "Detergente",
    "DESOD": "Desodorante",
    "DESINF": "Desinfetante",
    "ACHOC": "Achocolatado",
    "LIMP": "Limpador",
    "SUAV": "Suavizante",
    "AMAC": "Amaciante",    "AMC": "Amaciante",
    "SABAO": "Sabão",
    # Leite longa vida — causa-raiz dos 3 nomes no banco
    "LV": "Longa Vida",     "LVIDA": "Longa Vida",  "L.V.": "Longa Vida",
    # Carnes / frios
    "FGO": "Frango",
    "BOV": "Bovino",
    "LING": "Linguiça",     "LINGUI": "Linguiça",
    "MORT": "Mortadela",
    # Embalagem / unidade
    "PCT": "Pacote",        "EMB": "Embalagem",
    "CX": "Caixa",          "FR": "Frasco",
    "BD": "Bandeja",        "SC": "Sachê",
    "LT": "Lata",           "GAL": "Galão",
    # Papel / higiene
    "PAP": "Papel",         "HIG": "Higiênico",
    "CAF": "Café",
}

_SYSTEM_PROMPT = (
    "Você normaliza descrições brutas de produtos de supermercado extraídas de NFC-e. "
    "Receba um JSON com a chave 'items' (array de strings). "
    "Retorne um JSON com a chave 'names' contendo um array de strings normalizadas na mesma ordem.\n\n"
    "Regras OBRIGATÓRIAS:\n"
    "- Capitalize em Title Case.\n"
    "- Corrija typos óbvios preservando o significado (ex: 'COZA' → 'Coxa', 'BOM BOM' → 'Bombom').\n"
    "- Expanda as abreviações abaixo quando aparecerem:\n"
    "  BISC→Biscoito, CERV→Cerveja, REFRIG→Refrigerante, ENERG→Energético,\n"
    "  DET/DETER→Detergente, DESOD→Desodorante, DESINF→Desinfetante,\n"
    "  ACHOC→Achocolatado, LIMP→Limpador, SUAV→Suavizante, AMAC→Amaciante,\n"
    "  LV/LVIDA/L.V.→Longa Vida, FGO→Frango, BOV→Bovino, LING→Linguiça,\n"
    "  MORT→Mortadela, PCT→Pacote, CX→Caixa, PAP→Papel, LT→Lata, SC→Sachê,\n"
    "  BD→Bandeja, CAF→Café.\n"
    "- Mantenha marcas, quantidades, unidades e sabores exatamente como estão.\n"
    "- NÃO invente informações ausentes no original.\n"
    "- Se não souber o significado de uma abreviação, mantenha como está.\n\n"
    "Exemplos:\n"
    "- 'CERV BRAHMA LATA 350ML' → 'Cerveja Brahma Lata 350ml'\n"
    "- 'REFRIG COCA COLA PET 2L' → 'Refrigerante Coca-Cola Pet 2L'\n"
    "- 'LEITE LVIDA CAMPONESA 1L INT' → 'Leite Longa Vida Camponesa 1l Integral'\n"
    "- 'COZA SOBRECOCA FGO KG' → 'Coxa Sobrecoxa Frango kg'\n"
    "- 'BOM BOM LACTA FAVORITOS 250G' → 'Bombom Lacta Favoritos 250g'\n"
    "- 'ENERG LT MONSTER 473ML ULTRA' → 'Energético Lata Monster 473ml Ultra'\n"
    "- 'BISC NESTLE RECH NEGRESCO 90G BAUNILHA' → 'Biscoito Nestle Recheado Negresco 90g Baunilha'\n"
)


def pre_process(s: str) -> str:
    """Expande abreviações conhecidas e normaliza encoding para NFC.

    Tokens separados por espaço: se o token em maiúsculas estiver em _ABBREVS,
    é substituído; caso contrário, mantido intacto. O LLM cuida do Title Case.
    """
    if not s:
        return s
    s = unicodedata.normalize("NFC", s)
    return " ".join(_ABBREVS.get(t.upper(), t) for t in s.split())


def canonicalize(name: str, existing: list[str]) -> str:
    """Retorna o nome canônico existente se similarity >= CANONICAL_THRESHOLD.

    Previne que o mesmo produto físico apareça com dois nomes no banco.
    Threshold 0.92: captura 'Cerv Brahma' vs 'Cerveja Brahma' (≈0.94)
    sem fundir produtos distintos como 'Pipoca 40g' vs 'Pipoca 70g' (≈0.89).
    """
    if not existing:
        return name
    name_lower = name.lower()
    best_ratio, best_match = 0.0, name
    for candidate in existing:
        r = SequenceMatcher(None, name_lower, candidate.lower()).ratio()
        if r > best_ratio:
            best_ratio, best_match = r, candidate
    return best_match if best_ratio >= CANONICAL_THRESHOLD else name


async def normalize_items(
    descriptions: list[str],
    existing_names: list[str] | None = None,
) -> list[str]:
    """Normaliza descrições brutas em 3 fases: pré-processo → LLM → canonicalize.

    existing_names: produtos já no banco, usados como âncoras de canonicalização.
    Cada nome normalizado neste batch também vira âncora para os itens seguintes,
    garantindo convergência mesmo quando o mesmo produto aparece duas vezes no cupom.
    """
    if not descriptions:
        return []

    anchors = list(existing_names or [])
    preprocessed = [pre_process(d) for d in descriptions]

    if not _GROQ_API_KEY:
        logger.warning("normalize_items: GROQ_API_KEY não configurada — usando pré-processamento apenas")
        result = []
        for name in preprocessed:
            canonical = canonicalize(name, anchors)
            anchors.append(canonical)
            result.append(canonical)
        return result

    payload = json.dumps({"items": preprocessed}, ensure_ascii=False)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _GROQ_URL,
                headers={
                    "Authorization": f"Bearer {_GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                },
            )
            response.raise_for_status()

        content = json.loads(response.json()["choices"][0]["message"]["content"])
        names = content.get("names", [])

        if len(names) == len(descriptions):
            result = []
            for name in names:
                canonical = canonicalize(str(name), anchors)
                anchors.append(canonical)
                result.append(canonical)
            return result
        else:
            logger.warning(
                "normalize_items: resposta do LLM com tamanho divergente (%d vs %d) — usando pré-processamento",
                len(names),
                len(descriptions),
            )

    except Exception as exc:
        logger.warning(
            "normalize_items fallback (%s: %s) — usando pré-processamento apenas",
            type(exc).__name__,
            exc,
        )

    # Fallback: pré-processamento + canonicalize sem LLM
    result = []
    for name in preprocessed:
        canonical = canonicalize(name, anchors)
        anchors.append(canonical)
        result.append(canonical)
    return result
