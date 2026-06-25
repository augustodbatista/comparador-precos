"""
Serviço de normalização de nomes de produtos via Groq API (llama-3.3-70b-versatile).

Por que batch em vez de uma chamada por produto:
    Enviar todos os itens de um cupom em um único prompt custa O(1) chamadas HTTP
    e ~150-200 tokens de saída para 15 produtos, em vez de 15 chamadas sequenciais.

Por que fallback silencioso:
    O insert não pode travar por falha na API. normalized_name igual à descrição
    original é aceitável — o cupom é salvo e pode ser re-normalizado depois com
    o script renormalize_prices.py.

Configuração:
    GROQ_API_KEY — variável de ambiente obrigatória em produção.
    Sem a chave, o serviço retorna as descrições originais sem normalizar.
"""
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_MODEL = "llama-3.3-70b-versatile"
_TIMEOUT = 30.0
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_SYSTEM_PROMPT = (
    "Você normaliza descrições brutas de produtos de supermercado extraídas de NFC-e. "
    "Receba um JSON com a chave 'items' (array de strings em caixa alta com abreviações). "
    "Retorne um JSON com a chave 'names' contendo um array de strings normalizadas na mesma ordem.\n\n"
    "Regras OBRIGATÓRIAS:\n"
    "- Capitalize corretamente (Title Case), sem alterar o significado das palavras.\n"
    "- Expanda apenas abreviações óbvias e universais (ex: 'KG' → 'kg', 'LT' → 'lt', 'UN' → 'un', 'PCT' → 'pacote').\n"
    "- Mantenha marcas, categorias de produto, quantidades e unidades exatamente como estão no original.\n"
    "- NÃO traduza, NÃO simplifique, NÃO substitua palavras por sinônimos.\n"
    "- NÃO invente informações ausentes no original.\n"
    "- Se não souber o significado de uma abreviação, mantenha como está.\n\n"
    "Exemplos:\n"
    "- 'ARROZ TIPO1 5KG TORA' → 'Arroz Tipo 1 Tora 5kg'\n"
    "- 'ENERGETICO MONSTER 473ML' → 'Energético Monster 473ml'\n"
    "- 'REFRIG COCA COLA 2L' → 'Refrigerante Coca-Cola 2L'\n"
    "- 'BISC RECHEADO OREO 90G' → 'Biscoito Recheado Oreo 90g'\n"
    "- 'FGO FRANGO CONG KG' → 'Frango Congelado kg'"
)


async def normalize_items(descriptions: list[str]) -> list[str]:
    """Normaliza uma lista de descrições de produtos em uma única chamada ao Groq.

    Retorna a lista normalizada na mesma ordem. Em caso de falha (chave ausente,
    timeout, JSON inválido ou tamanho divergente), retorna as descrições originais
    e loga um warning — visível nos logs do Render para diagnóstico.
    """
    if not descriptions:
        return []

    if not _GROQ_API_KEY:
        logger.warning("normalize_items: GROQ_API_KEY não configurada — salvando descrições originais")
        return descriptions

    payload = json.dumps({"items": descriptions}, ensure_ascii=False)

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
            return [str(n) for n in names]

    except Exception as exc:
        logger.warning(
            "normalize_items fallback (%s: %s) — salvando descrições originais",
            type(exc).__name__,
            exc,
        )

    return descriptions
