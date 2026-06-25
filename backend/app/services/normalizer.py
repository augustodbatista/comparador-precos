"""
Serviço de normalização de nomes de produtos via Ollama (qwen2.5:7b).

Por que batch em vez de uma chamada por produto:
    Inference em CPU é lenta (~4-6 tok/s no qwen2.5:7b). Enviar todos os itens
    de um cupom em um único prompt custa O(1) chamadas HTTP e ~150-200 tokens de
    saída para 15 produtos, em vez de 15 chamadas sequenciais.

Por que fallback silencioso:
    O insert não pode travar por Ollama estar fora. normalized_name=None é aceitável
    — o cupom é salvo e pode ser re-normalizado depois com o script renormalize_prices.py.
    A comparação de preços simplesmente não encontra esses itens até normalização rodar.

Configuração:
    OLLAMA_URL — variável de ambiente; padrão http://localhost:11434 (Ollama local).
    Em produção, deve apontar para a URL do ngrok que expõe o Ollama da máquina local.
"""
import json
import logging
import os

import httpx

# Logger nomeado pelo módulo — mensagens aparecem nos logs do Render com contexto claro
logger = logging.getLogger(__name__)

# URL configurável via env; padrão aponta para Ollama local
_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Modelo usado para normalização — deve estar baixado localmente via "ollama pull qwen2.5:7b"
_MODEL = "qwen2.5:7b"

# Generoso: qwen2.5:7b em CPU leva ~30-50s para um cupom de 15 itens
_TIMEOUT = 90.0

# Instrução de sistema enviada ao modelo antes dos dados do usuário
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

    Envia todas as descrições de um cupom em um único prompt batch para minimizar
    o número de chamadas HTTP e o tempo total de inference.

    Retorna a lista normalizada na mesma ordem. Em caso de falha (Ollama fora,
    timeout, JSON inválido ou tamanho divergente), retorna as descrições originais
    e loga um warning com o motivo — visível nos logs do Render para diagnóstico.
    """
    if not descriptions:
        return []

    # Serializa as descrições como JSON para envio ao modelo
    payload = json.dumps({"items": descriptions}, ensure_ascii=False)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_OLLAMA_URL}/api/chat",
                # ngrok free tier bloqueia requests sem esse header (aparece como "browser warning")
                headers={"ngrok-skip-browser-warning": "true"},
                json={
                    "model": _MODEL,
                    "format": "json",   # força o modelo a retornar JSON válido
                    "stream": False,    # aguarda a resposta completa antes de retornar
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": payload},
                    ],
                },
            )
            response.raise_for_status()

            # Extrai o conteúdo JSON da resposta do modelo
            content = json.loads(response.json()["message"]["content"])
            names = content.get("names", [])

            # Tamanho divergente indica alucinação ou truncamento — descarta tudo
            # e usa o fallback para não misturar nomes normalizados com não-normalizados
            if len(names) == len(descriptions):
                return [str(n) for n in names]

    except Exception as exc:
        # Loga o motivo do fallback — essencial para diagnóstico nos logs do Render
        logger.warning(
            "normalize_items fallback (%s: %s) — salvando descrições originais",
            type(exc).__name__,
            exc,
        )

    # Fallback: retorna as descrições originais sem normalização
    return descriptions
