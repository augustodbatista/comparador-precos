# Normalização Inteligente de Produtos NFC-e — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar pipeline de 3 fases (pré-processamento determinístico → LLM → verificação canônica) que garante `product_id` único e consistente para o mesmo produto físico, e corrigir os dados já existentes no banco.

**Architecture:** `pre_process()` expande abreviações de supermercado e normaliza encoding antes do LLM; o prompt do Groq ganha exemplos dos padrões problemáticos reais; `canonicalize()` compara cada resultado contra produtos já cadastrados via `difflib.SequenceMatcher` e usa o nome canônico existente se similarity ≥ 0.92; um script de batch re-normaliza e funde duplicatas no banco existente.

**Tech Stack:** Python 3.11, FastAPI, Motor (async MongoDB), Groq API `llama-3.3-70b-versatile`, `difflib.SequenceMatcher` (stdlib), `unicodedata` (stdlib) — zero dependências novas.

## Global Constraints

- Python 3.11 (usar `list[str]`, `str | None`, não `List`, `Optional`)
- Sem dependências novas — `difflib` e `unicodedata` são stdlib
- Todos os campos do banco em inglês
- Testes: `pytest` + `pytest-asyncio`; mocks via `unittest.mock`
- `GROQ_API_KEY` via `.env`; fallback silencioso se ausente
- Rodar testes: `cd backend && python -m pytest -v`

---

### Task 1: pre_process, canonicalize e normalize_items atualizado

**Files:**
- Modify: `backend/app/services/normalizer.py`
- Modify: `backend/tests/test_normalizer.py`

**Interfaces:**
- Produces:
  - `pre_process(s: str) -> str`
  - `canonicalize(name: str, existing: list[str]) -> str`
  - `CANONICAL_THRESHOLD: float = 0.92`
  - `normalize_items(descriptions: list[str], existing_names: list[str] | None = None) -> list[str]` (segundo parâmetro novo, opcional)

---

- [ ] **Step 1: Escrever os testes que vão falhar**

Adicionar ao final de `backend/tests/test_normalizer.py`:

```python
# No topo do arquivo, atualizar o import para incluir as novas funções:
from app.services.normalizer import normalize_items, pre_process, canonicalize


class TestPreProcess:
    def test_expande_abreviacao_conhecida(self):
        assert pre_process("CERV BRAHMA 350ML") == "Cerveja BRAHMA 350ML"

    def test_expande_lv_para_longa_vida(self):
        assert pre_process("LEITE LV CAMPONESA 1L") == "LEITE Longa Vida CAMPONESA 1L"

    def test_expande_lvida_para_longa_vida(self):
        assert pre_process("LEITE LVIDA PIRACANJUBA") == "LEITE Longa Vida PIRACANJUBA"

    def test_expande_bisc(self):
        assert pre_process("BISC NEGRESCO 90G") == "Biscoito NEGRESCO 90G"

    def test_normaliza_unicode_nfc(self):
        # NFD: 'ã' como 'a' + combining tilde (̃) → NFC: 'ã'
        nfd_input = "Pão"  # "Pão" em NFD
        assert pre_process(nfd_input) == "Pão"

    def test_preserva_token_desconhecido(self):
        assert pre_process("BRAHMA EXTRA") == "BRAHMA EXTRA"

    def test_string_vazia(self):
        assert pre_process("") == ""

    def test_multiplas_abreviacoes(self):
        assert pre_process("BISC LV SUAV") == "Biscoito Longa Vida Suavizante"


class TestCanonicalize:
    def test_retorna_existente_acima_do_threshold(self):
        existing = ["Cerveja Brahma Lata 350ml", "Arroz Tipo 1 Tora 5kg"]
        # "Cerv Brahma Lata 350ml" vs "Cerveja Brahma Lata 350ml" ≈ 0.94 > 0.92
        result = canonicalize("Cerv Brahma Lata 350ml", existing)
        assert result == "Cerveja Brahma Lata 350ml"

    def test_retorna_nome_novo_abaixo_do_threshold(self):
        existing = ["Pipoca Doce Lin 70g"]
        # "Pipoca Doce Lin 40g" vs "Pipoca Doce Lin 70g" ≈ 0.89 < 0.92
        result = canonicalize("Pipoca Doce Lin 40g", existing)
        assert result == "Pipoca Doce Lin 40g"

    def test_lista_vazia_retorna_nome(self):
        assert canonicalize("Produto Novo", []) == "Produto Novo"

    def test_match_exato_retorna_existente(self):
        existing = ["Cerveja Brahma Lata 350ml"]
        assert canonicalize("Cerveja Brahma Lata 350ml", existing) == "Cerveja Brahma Lata 350ml"

    def test_escolhe_melhor_match(self):
        existing = ["Arroz Tipo 1 5kg", "Cerveja Brahma Lata 350ml"]
        result = canonicalize("Cerv Brahma Lata 350ml", existing)
        assert result == "Cerveja Brahma Lata 350ml"
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
cd backend && python -m pytest tests/test_normalizer.py::TestPreProcess tests/test_normalizer.py::TestCanonicalize -v
```

Esperado: `ImportError` — `pre_process` e `canonicalize` não existem ainda.

- [ ] **Step 3: Substituir o conteúdo completo de normalizer.py**

```python
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
```

- [ ] **Step 4: Atualizar o import no topo de test_normalizer.py**

Localizar a linha:
```python
from app.services.normalizer import normalize_items
```
Substituir por:
```python
from app.services.normalizer import normalize_items, pre_process, canonicalize
```

- [ ] **Step 5: Rodar toda a suite do normalizer**

```bash
cd backend && python -m pytest tests/test_normalizer.py -v
```

Esperado: todos PASS (os testes existentes continuam passando — `existing_names` é opcional e os mocks continuam funcionando).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/normalizer.py backend/tests/test_normalizer.py
git commit -m "feat: pipeline de normalização em 3 fases (pre_process, canonicalize, LLM melhorado)"
```

---

### Task 2: list_all_product_names + atualização do POST /receipts

**Files:**
- Modify: `backend/app/db/repositories/products.py`
- Create: `backend/tests/test_db_products.py`
- Modify: `backend/app/routes/receipts.py`
- Modify: `backend/tests/test_receipts_endpoint.py` (fix assinatura do mock)

**Interfaces:**
- Consumes: `normalize_items(descriptions, existing_names)` da Task 1
- Produces: `list_all_product_names(db: AsyncIOMotorDatabase) -> list[str]`

---

- [ ] **Step 1: Escrever o teste para list_all_product_names**

Criar `backend/tests/test_db_products.py`:

```python
"""Testes para o repositório de produtos."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.db.repositories.products import list_all_product_names


@pytest.mark.asyncio
class TestListAllProductNames:
    async def test_retorna_lista_de_nomes(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[
            {"normalized_name": "Arroz Tipo 1 Tora 5kg"},
            {"normalized_name": "Cerveja Brahma Lata 350ml"},
        ])
        mock_db["products"].find.return_value = mock_cursor

        result = await list_all_product_names(mock_db)

        assert result == ["Arroz Tipo 1 Tora 5kg", "Cerveja Brahma Lata 350ml"]

    async def test_retorna_lista_vazia_quando_sem_produtos(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        mock_db["products"].find.return_value = mock_cursor

        result = await list_all_product_names(mock_db)

        assert result == []
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

```bash
cd backend && python -m pytest tests/test_db_products.py -v
```

Esperado: `ImportError` — `list_all_product_names` não existe ainda.

- [ ] **Step 3: Implementar list_all_product_names em products.py**

Adicionar ao final de `backend/app/db/repositories/products.py`:

```python
async def list_all_product_names(db: AsyncIOMotorDatabase) -> list[str]:
    """Retorna todos os normalized_name cadastrados. Usado para canonicalização no POST /receipts."""
    cursor = db[COLLECTION].find({}, {"_id": 0, "normalized_name": 1})
    docs = await cursor.to_list(length=10_000)
    return [d["normalized_name"] for d in docs]
```

- [ ] **Step 4: Rodar o teste para confirmar que passa**

```bash
cd backend && python -m pytest tests/test_db_products.py -v
```

Esperado: PASS.

- [ ] **Step 5: Atualizar routes/receipts.py**

Localizar o import:
```python
from app.db.repositories.products import upsert_product
```
Substituir por:
```python
from app.db.repositories.products import upsert_product, list_all_product_names
```

No body de `save_receipt`, localizar:
```python
    descriptions = [item.description for item in body.items]
    normalized = await normalize_items(descriptions)
```
Substituir por:
```python
    descriptions = [item.description for item in body.items]
    existing_names = await list_all_product_names(db)
    normalized = await normalize_items(descriptions, existing_names)
```

- [ ] **Step 6: Corrigir _normalize_passthrough em test_receipts_endpoint.py**

O mock atual tem assinatura de 1 argumento. A rota agora passa `existing_names` como segundo argumento, causando `TypeError`.

Localizar em `backend/tests/test_receipts_endpoint.py`:
```python
async def _normalize_passthrough(descriptions):
    return descriptions
```
Substituir por:
```python
async def _normalize_passthrough(descriptions, existing_names=None):
    return descriptions
```

- [ ] **Step 7: Rodar a suite completa**

```bash
cd backend && python -m pytest -v
```

Esperado: todos PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/repositories/products.py backend/tests/test_db_products.py backend/app/routes/receipts.py backend/tests/test_receipts_endpoint.py
git commit -m "feat: canonicalização via list_all_product_names no POST /receipts"
```

---

### Task 3: Script dedup_and_renormalize + remoção de renormalize_prices.py

**Files:**
- Create: `backend/scripts/dedup_and_renormalize.py`
- Delete: `backend/scripts/renormalize_prices.py`

**Interfaces:**
- Consumes: `normalize_items(descriptions, existing_names)` e `CANONICAL_THRESHOLD` da Task 1

---

- [ ] **Step 1: Criar backend/scripts/dedup_and_renormalize.py**

```python
"""
Re-normaliza todos os produtos no banco com o pipeline completo (pre_process + LLM + canonicalize)
e funde duplicatas detectadas por similaridade.

Fases:
    1. Re-normalizar — mapeia cada original_description → novo product_id
    2. Fundir duplicatas — detecta clusters com similarity >= CANONICAL_THRESHOLD,
       escolhe o nome mais longo como canônico
    3. Relatório — imprime resumo de todas as mudanças

Uso:
    cd backend/
    python scripts/dedup_and_renormalize.py           # aplica as mudanças
    python scripts/dedup_and_renormalize.py --dry-run # simula sem tocar no banco
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.normalizer import normalize_items, CANONICAL_THRESHOLD

load_dotenv()

BATCH = 10  # descrições originais por chamada ao Groq


def _find_clusters(names: list[str]) -> list[list[str]]:
    """Agrupa nomes com similarity >= CANONICAL_THRESHOLD em clusters.

    Usa union-find implícito: cada nome entra no primeiro cluster ao qual é similar.
    """
    assigned = [False] * len(names)
    clusters = []
    for i, a in enumerate(names):
        if assigned[i]:
            continue
        cluster = [a]
        assigned[i] = True
        for j in range(i + 1, len(names)):
            if assigned[j]:
                continue
            if SequenceMatcher(None, a.lower(), names[j].lower()).ratio() >= CANONICAL_THRESHOLD:
                cluster.append(names[j])
                assigned[j] = True
        if len(cluster) > 1:
            clusters.append(cluster)
    return clusters


async def main(dry_run: bool) -> None:
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL"))
    db = client[os.getenv("DB_NAME", "comparador_precos")]
    prefix = "[DRY-RUN] " if dry_run else ""

    # ── Fase 1: Re-normalizar ──────────────────────────────────────────────────
    print("=== FASE 1: Re-normalização via pipeline completo ===\n")

    all_prices = await db["prices"].find(
        {}, {"_id": 0, "original_description": 1, "product_id": 1}
    ).to_list(length=None)

    # Mapeia descrição original → product_id atual (primeira ocorrência)
    desc_to_current: dict[str, str] = {}
    for doc in all_prices:
        desc = doc["original_description"]
        if desc not in desc_to_current:
            desc_to_current[desc] = doc["product_id"]

    unique_descs = list(desc_to_current.keys())
    print(f"{len(unique_descs)} descrições originais distintas encontradas.")

    # Carrega produtos existentes como âncoras iniciais
    existing_docs = await db["products"].find(
        {}, {"_id": 0, "normalized_name": 1}
    ).to_list(length=None)
    anchors: list[str] = [d["normalized_name"] for d in existing_docs]

    desc_to_new: dict[str, str] = {}
    for i in range(0, len(unique_descs), BATCH):
        batch = unique_descs[i: i + BATCH]
        normalized = await normalize_items(batch, anchors)
        for desc, new_name in zip(batch, normalized):
            desc_to_new[desc] = new_name
            if new_name not in anchors:
                anchors.append(new_name)

    phase1_changes: list[tuple[str, str, str]] = []  # (desc, old, new)
    for desc, new_name in desc_to_new.items():
        old_name = desc_to_current[desc]
        if old_name == new_name:
            continue
        phase1_changes.append((desc, old_name, new_name))
        print(f"  {prefix}{old_name!r}\n      → {new_name!r}  (desc: {desc!r})\n")

        if not dry_run:
            await db["prices"].update_many(
                {"original_description": desc},
                {"$set": {"product_id": new_name}},
            )
            now = datetime.now(timezone.utc)
            await db["products"].update_one(
                {"normalized_name": new_name},
                {"$setOnInsert": {"normalized_name": new_name, "created_at": now}},
                upsert=True,
            )
            still_used = await db["prices"].count_documents({"product_id": old_name})
            if not still_used:
                await db["products"].delete_one({"normalized_name": old_name})

    print(f"{len(phase1_changes)} re-normalizações na Fase 1.\n")

    # ── Fase 2: Fundir duplicatas remanescentes ────────────────────────────────
    print("=== FASE 2: Fusão de duplicatas remanescentes ===\n")

    current_products = await db["products"].find(
        {}, {"_id": 0, "normalized_name": 1}
    ).to_list(length=None)
    current_names = [d["normalized_name"] for d in current_products]
    products_before = len(current_names)

    clusters = _find_clusters(current_names)
    phase2_merges: list[tuple[str, list[str]]] = []

    for cluster in clusters:
        canonical = max(cluster, key=len)  # mais longo = mais completo
        others = [n for n in cluster if n != canonical]
        phase2_merges.append((canonical, others))
        print(f"  Cluster canônico: {canonical!r}")
        for other in others:
            print(f"    {prefix}fundindo {other!r} → {canonical!r}")
            if not dry_run:
                await db["prices"].update_many(
                    {"product_id": other},
                    {"$set": {"product_id": canonical}},
                )
                await db["products"].delete_one({"normalized_name": other})

    if not clusters:
        print("  Nenhuma duplicata encontrada.")

    total_merged = sum(len(o) for _, o in phase2_merges)
    print(f"\n{total_merged} produtos fundidos em {len(clusters)} clusters.\n")

    # ── Fase 3: Relatório ──────────────────────────────────────────────────────
    print("=== RESUMO ===\n")
    products_after = await db["products"].count_documents({}) if not dry_run else "N/A (dry-run)"
    print(f"  Produtos antes da Fase 2 : {products_before}")
    print(f"  Produtos após            : {products_after}")
    print(f"  Re-normalizações (Fase 1): {len(phase1_changes)}")
    print(f"  Fusões (Fase 2)          : {total_merged}")
    if dry_run:
        print("\n  [DRY-RUN] Nenhuma alteração foi feita no banco.")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-normaliza e deduplica produtos no banco.")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem alterar o banco")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
```

- [ ] **Step 2: Testar em dry-run**

```bash
cd backend && python scripts/dedup_and_renormalize.py --dry-run
```

Verificar no output que os pares problemáticos conhecidos aparecem, por exemplo:
- `'Cerv Brahma Lata 350ml'` → `'Cerveja Brahma Lata 350ml'`
- clusters do Leite Longa Vida (`Lv`, `Lvida`, `L.V.`)
- `'Bom Bom Lacta ...'` → `'Bombom Lacta ...'`

Se alguma fusão parecer incorreta (dois produtos distintos sendo fundidos), ajustar `CANONICAL_THRESHOLD` em `normalizer.py` antes de prosseguir.

- [ ] **Step 3: Deletar renormalize_prices.py**

```bash
git rm backend/scripts/renormalize_prices.py
```

- [ ] **Step 4: Rodar suite completa para garantir que nada quebrou**

```bash
cd backend && python -m pytest -v
```

Esperado: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/dedup_and_renormalize.py
git commit -m "feat: script dedup_and_renormalize — re-normaliza e funde duplicatas no banco"
```

---

### Task 4: Aplicar o script no banco real

Task operacional — sem testes automatizados.

---

- [ ] **Step 1: Dry-run final**

```bash
cd backend && python scripts/dedup_and_renormalize.py --dry-run
```

Revisar o output completo. Confirmar que não há fusões incorretas (ex: produtos de tamanhos diferentes sendo fundidos). Se encontrar alguma fusão errada, pare e ajuste o threshold.

- [ ] **Step 2: Aplicar no banco**

```bash
cd backend && python scripts/dedup_and_renormalize.py
```

- [ ] **Step 3: Verificar estado do banco após execução**

```bash
cd backend && python -c "
import os, asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
load_dotenv()

async def check():
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
    db = client[os.getenv('DB_NAME', 'comparador_precos')]
    print('products:', await db['products'].count_documents({}))
    print('prices:  ', await db['prices'].count_documents({}))
    # Verificar se ainda há product_id divergentes dos nomes em products
    product_names = {d['normalized_name'] async for d in db['products'].find({}, {'normalized_name': 1})}
    orphan_prices = await db['prices'].count_documents({'product_id': {'\\$nin': list(product_names)}})
    print('prices sem produto correspondente:', orphan_prices)
    client.close()

asyncio.run(check())
"
```

Esperado: `prices sem produto correspondente: 0`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: aplica dedup_and_renormalize — banco normalizado e sem duplicatas"
```

