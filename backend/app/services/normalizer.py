"""
Serviço de normalização de nomes de produtos via Ollama (qwen2.5:7b).

Por que batch em vez de uma chamada por produto:
    Inference em CPU é lenta (~4-6 tok/s no qwen2.5:7b). Enviar todos os itens
    de um cupom em um único prompt custa O(1) chamadas HTTP e ~150-200 tokens de
    saída para 15 produtos, em vez de 15 chamadas sequenciais.

Por que fallback silencioso:
    O insert não pode travar por Ollama estar fora. normalized_name=None é aceitável
    — o cupom é salvo e pode ser re-normalizado depois. A comparação de preços
    simplesmente não encontra esses itens até normalização rodar.
"""
import json
import os

import httpx

# URL configurável via env; padrão aponta para Ollama local
_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
_MODEL = "qwen2.5:7b"
# Generoso: qwen2.5:7b em CPU leva ~30-50s para um cupom de 15 itens
_TIMEOUT = 90.0

_SYSTEM_PROMPT = (
    "Você normaliza descrições brutas de produtos de supermercado extraídas de NFC-e. "
    "Receba um JSON com a chave 'items' (array de strings em caixa alta com abreviações). "
    "Retorne um JSON com a chave 'names' contendo um array de strings normalizadas "
    "na mesma ordem: capitalize corretamente, expanda abreviações óbvias, "
    "mantenha marca, quantidade e unidade quando presentes. "
    "Não invente informações ausentes no original. "
    "Exemplo: 'ARROZ TIPO1 5KG TORA' → 'Arroz Tipo 1 Tora 5kg'."
)


async def normalize_items(descriptions: list[str]) -> list[str]:
    """Normaliza uma lista de descrições de produtos em uma única chamada ao Ollama.

    Retorna a lista normalizada na mesma ordem. Em caso de falha (Ollama fora,
    timeout, JSON inválido ou tamanho divergente), retorna as descrições originais.
    """
    if not descriptions:
        return []

    payload = json.dumps({"items": descriptions}, ensure_ascii=False)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_OLLAMA_URL}/api/chat",
                json={
                    "model": _MODEL,
                    # format=json força o modelo a emitir JSON válido
                    "format": "json",
                    # stream=false aguarda a resposta completa antes de retornar
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                },
            )
            response.raise_for_status()

            content = json.loads(response.json()["message"]["content"])
            names = content.get("names", [])

            # Tamanho divergente indica alucinação ou truncamento — descarta tudo
            if len(names) == len(descriptions):
                return [str(n) for n in names]

    except Exception:
        # Qualquer falha (rede, timeout, JSON malformado) → fallback silencioso
        pass

    return descriptions
