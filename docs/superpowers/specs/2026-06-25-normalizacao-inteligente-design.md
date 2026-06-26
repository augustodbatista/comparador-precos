# Design: Normalização Inteligente de Produtos NFC-e

**Data:** 2026-06-25
**Status:** Aprovado

## Problema

O pipeline de normalização atual (Groq `llama-3.3-70b-versatile`) produz nomes inconsistentes para o mesmo produto físico:

- `Cerv Brahma Lata 350ml` vs `Cerveja Brahma Lata 350ml`
- `Leite Lv Piracanjuba 1l Int` vs `Leite Lvida Piracanjuba 1l Intg` vs `Leite Piracanjuba 1l Integral`
- `Bom Bom Lacta Favoritos 250.6g` vs `Bombom Lacta Favoritos 250.6g`
- `Pao De Queijo Mac Pad kg` vs `Pão De Queijo Mac Pad kg`

Essas inconsistências quebram a comparação de preços cross-cupom, que depende de `product_id` idêntico para o mesmo produto.

## Solução: Pipeline em 3 Fases (Abordagem B)

```
raw SEFAZ string
      │
      ▼
┌─────────────────────┐
│   PRÉ-PROCESSO      │  Python puro, zero latência
│   (determinístico)  │  • unicodedata.normalize NFC (Pao→Pão)
│                     │  • dicionário de abreviações de supermercado
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   LLM (Groq)        │  Prompt melhorado com:
│   batch call        │  • lista inline de abreviações conhecidas
│                     │  • exemplos de typo correction
│                     │  • exemplos de compound words
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   CANONICALIZE      │  Python puro
│   (fuzzy check)     │  • compara contra produtos já no banco
│                     │  • similarity > 0.92 → usa nome canônico existente
└──────────┬──────────┘
           │
           ▼
    product_id salvo
```

## Componentes

### 1. `pre_process(s: str) -> str` — em `normalizer.py`

Aplica transformações determinísticas antes de enviar ao LLM:

1. `unicodedata.normalize('NFC', s)` — corrige encoding
2. Tokeniza por espaço e substitui tokens que estejam no dicionário de abreviações
3. Reagrupa em string

**Dicionário de abreviações (`_ABBREVS`):**

```python
{
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
    # Leite longa vida
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
```

### 2. Prompt melhorado — em `normalizer.py` (`_SYSTEM_PROMPT`)

Adições em relação ao prompt atual:
- Instrução explícita de correção de typos (`"COZA" → "Coxa"`, `"BOM BOM" → "Bombom"`)
- Bloco `Abreviações conhecidas` inline (reforça o pré-processamento)
- Exemplos adicionais cobrindo os padrões problemáticos observados no banco

### 3. `canonicalize(name: str, existing: list[str]) -> str` — em `normalizer.py`

```python
CANONICAL_THRESHOLD = 0.92

def canonicalize(name: str, existing: list[str]) -> str:
    best_ratio, best_match = 0.0, None
    name_lower = name.lower()
    for candidate in existing:
        r = SequenceMatcher(None, name_lower, candidate.lower()).ratio()
        if r > best_ratio:
            best_ratio, best_match = r, candidate
    if best_ratio >= CANONICAL_THRESHOLD:
        return best_match
    return name
```

Threshold 0.92 escolhido empiricamente: captura `Cerv Brahma` vs `Cerveja Brahma` (≈0.94) sem fundir produtos diferentes como `Pipoca 40g` vs `Pipoca 70g` (≈0.89).

### 4. `normalize_items(descriptions, existing_names)` — assinatura atualizada

Recebe `existing_names: list[str]` como segundo parâmetro. Internamente:
1. Aplica `pre_process` em cada descrição
2. Envia batch ao Groq
3. Aplica `canonicalize` em cada resultado, acumulando os nomes já normalizados nesta chamada como âncora adicional

### 5. `list_all_product_names(db)` — novo em `repositories/products.py`

Retorna `list[str]` com todos os `normalized_name` da collection `products`. Chamado no POST /receipts antes de `normalize_items`.

### 6. Mudança em `routes/receipts.py` (POST /receipts)

```python
existing_names = await list_all_product_names(db)
normalized = await normalize_items(descriptions, existing_names)
```

Uma query extra por POST. Aceitável dado o volume pessoal do projeto.

### 7. `scripts/dedup_and_renormalize.py` — script novo

Substitui `renormalize_prices.py`. Fluxo em 3 fases:

**Fase 1 — Re-normalizar:**
- Coleta todas as `original_description` distintas em `prices`
- Processa em batches de 10 via novo pipeline (pre_process + LLM + canonicalize)
- Atualiza `prices.product_id` em bulk
- Upsert em `products`

**Fase 2 — Fundir duplicatas remanescentes:**
- Carrega todos os `products.normalized_name`
- Detecta clusters com similarity > 0.92
- Por cluster: canônico = nome mais longo (heurística: mais completo)
- Atualiza `prices.product_id` de não-canônicos → canônico
- Deleta `products` não-canônicos

**Fase 3 — Relatório:**
- N descrições processadas
- N produtos antes / depois
- Lista completa de fusões realizadas

**Flags:**
- `--dry-run`: simula sem tocar no banco

## Arquivos modificados

| Arquivo | Mudança |
|---|---|
| `app/services/normalizer.py` | `pre_process()`, `canonicalize()`, `normalize_items` atualizado |
| `app/routes/receipts.py` | POST passa `existing_names` para `normalize_items` |
| `app/db/repositories/products.py` | `list_all_product_names(db)` |
| `scripts/dedup_and_renormalize.py` | script novo |
| `scripts/renormalize_prices.py` | deletado (coberto pelo novo) |
| `tests/test_normalizer.py` | testes para `pre_process` e `canonicalize` |

## Testes

- `test_pre_process`: expansão de abreviações, NFC encoding, tokens não mapeados intactos
- `test_canonicalize`: match acima do threshold retorna canônico, abaixo retorna nome novo, lista vazia retorna nome novo
- Testes existentes de `normalize_items` atualizados para nova assinatura (passam `existing_names=[]`)

## Fora de escopo

- UI para visualizar/aprovar fusões (o relatório do script é suficiente por ora)
- Cache de `list_all_product_names` (volume atual ~300 produtos, latência irrelevante)
- Threshold configurável por env var (0.92 é fixo até surgir caso concreto que exija ajuste)
