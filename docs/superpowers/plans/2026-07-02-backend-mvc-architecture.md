# Backend MVC Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `backend/app/` into 5 explicit layers — `models/`, `views/`, `controllers/`, `services/`, `repositories/` — per the professor's MVC requirement, with zero behavior change.

**Architecture:** Pure structural refactor. `routes/` becomes `controllers/`; the Pydantic classes embedded in the two route files split out into `models/` (input/domain — `ReceiptData` and its nested types) and `views/` (output-only DTOs — `ProductItem`, `PriceResponse`, `OllamaHealthResponse`); `app/db/repositories/` and `app/db/connection.py` flatten into `app/repositories/`. `services/` is untouched.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Motor, pytest + pytest-asyncio.

## Global Constraints

- No behavior change: every existing test must pass, unmodified in assertions, after every task.
- No new dependencies.
- Folder/package names in English (`models`, `views`, `controllers`, `services`, `repositories`), matching the existing `services`/`repositories` convention.
- Full backend test suite (`python -m pytest`) must be green after every task, run from `backend/`.
- `backend/scripts/` and `backend/main.py` are out of scope beyond the specific import-line updates called out below.

Spec: `docs/superpowers/specs/2026-07-02-backend-mvc-architecture-design.md`

---

### Task 1: Flatten `db/repositories/` and `db/connection.py` into `app/repositories/`

**Files:**
- Create: `backend/app/repositories/__init__.py` (empty, matches `app/routes/__init__.py` / `app/services/__init__.py` convention)
- Move: `backend/app/db/connection.py` → `backend/app/repositories/connection.py`
- Move: `backend/app/db/repositories/receipts.py` → `backend/app/repositories/receipts.py`
- Move: `backend/app/db/repositories/prices.py` → `backend/app/repositories/prices.py`
- Move: `backend/app/db/repositories/products.py` → `backend/app/repositories/products.py`
- Delete: `backend/app/db/` (whole directory, once emptied by the moves above)
- Modify: `backend/main.py:8`
- Modify: `backend/app/routes/receipts.py:15-17`
- Modify: `backend/app/routes/prices.py:16-17`
- Rename: `backend/tests/test_db_receipts.py` → `backend/tests/test_repositories_receipts.py`
- Rename: `backend/tests/test_db_products.py` → `backend/tests/test_repositories_products.py`
- Modify: `backend/tests/test_receipts_endpoint.py:111`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `app.repositories.connection.{get_client, get_db, create_indexes}`, `app.repositories.receipts.{find_by_access_key, insert_receipt, list_receipts}`, `app.repositories.prices.{insert_prices, find_product_ids_by_description, get_latest_price, get_lowest_price, get_price_history}`, `app.repositories.products.{upsert_product, list_products, list_all_product_names}` — all with identical signatures to their `app.db.*` predecessors. Later tasks (2 and 3) import from these new paths.

- [ ] **Step 1: Confirm baseline is green**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass (baseline before touching anything).

- [ ] **Step 2: Create the new `repositories/` package and move files into it**

```bash
cd backend
mkdir -p app/repositories
touch app/repositories/__init__.py
git mv app/db/connection.py app/repositories/connection.py
git mv app/db/repositories/receipts.py app/repositories/receipts.py
git mv app/db/repositories/prices.py app/repositories/prices.py
git mv app/db/repositories/products.py app/repositories/products.py
git rm app/db/__init__.py
rmdir app/db/repositories app/db 2>/dev/null || true
```

None of the 4 moved files need internal content changes — they only import from `motor`, `datetime`, `pymongo.errors`, not from each other or from `app.db`.

- [ ] **Step 3: Update `main.py`'s import**

In `backend/main.py`, change line 8 from:
```python
from app.db.connection import create_indexes, get_client, get_db
```
to:
```python
from app.repositories.connection import create_indexes, get_client, get_db
```

- [ ] **Step 4: Update `app/routes/receipts.py`'s imports**

Change lines 15-17 from:
```python
from app.db.repositories.prices import insert_prices, find_product_ids_by_description
from app.db.repositories.products import upsert_product, list_all_product_names
from app.db.repositories.receipts import find_by_access_key, insert_receipt, list_receipts
```
to:
```python
from app.repositories.prices import insert_prices, find_product_ids_by_description
from app.repositories.products import upsert_product, list_all_product_names
from app.repositories.receipts import find_by_access_key, insert_receipt, list_receipts
```

- [ ] **Step 5: Update `app/routes/prices.py`'s imports**

Change lines 16-17 from:
```python
from app.db.repositories.prices import get_latest_price, get_lowest_price, get_price_history
from app.db.repositories.products import list_products
```
to:
```python
from app.repositories.prices import get_latest_price, get_lowest_price, get_price_history
from app.repositories.products import list_products
```

- [ ] **Step 6: Rename and update the repository test files**

```bash
cd backend
git mv tests/test_db_receipts.py tests/test_repositories_receipts.py
git mv tests/test_db_products.py tests/test_repositories_products.py
```

In `tests/test_repositories_receipts.py`, change:
- Line 2 docstring: `"""Testes unitários para app/db/repositories/receipts.py.` → `"""Testes unitários para app/repositories/receipts.py.`
- Line 12: `from app.db.repositories.receipts import find_by_access_key, insert_receipt, list_receipts` → `from app.repositories.receipts import find_by_access_key, insert_receipt, list_receipts`

In `tests/test_repositories_products.py`, change:
- Line 5: `from app.db.repositories.products import list_all_product_names` → `from app.repositories.products import list_all_product_names`

- [ ] **Step 7: Update the inline import in `test_receipts_endpoint.py`**

In `backend/tests/test_receipts_endpoint.py`, change line 111 from:
```python
        from app.db.repositories.receipts import insert_receipt
```
to:
```python
        from app.repositories.receipts import insert_receipt
```

- [ ] **Step 8: Verify no stale `app.db` references remain**

Run: `cd backend && grep -rn "app\.db\." app/ tests/ main.py`
Expected: no output (empty).

- [ ] **Step 9: Run the full suite**

Run: `cd backend && python -m pytest -v`
Expected: same pass count as Step 1, all green.

- [ ] **Step 10: Commit**

```bash
cd backend
git add app/repositories app/routes/receipts.py app/routes/prices.py main.py \
        tests/test_repositories_receipts.py tests/test_repositories_products.py \
        tests/test_receipts_endpoint.py
git add -u app/db  # stages the deletions
git commit -m "refactor: app/db/repositories + connection.py viram app/repositories/

Camada de repositórios sobe pro topo de app/, junto de models/views/controllers/
services/ que vêm nas próximas tasks. Sem mudança de comportamento."
```

---

### Task 2: Extract Pydantic schemas into `models/` and `views/`

**Files:**
- Create: `backend/app/models/__init__.py` (empty)
- Create: `backend/app/models/receipt.py`
- Create: `backend/app/views/__init__.py` (empty)
- Create: `backend/app/views/price.py`
- Create: `backend/app/views/health.py`
- Modify: `backend/app/routes/receipts.py` (remove the 5 classes, import `ReceiptData` from `app.models.receipt`)
- Modify: `backend/app/routes/prices.py` (remove the 3 classes, import from `app.views.price` / `app.views.health`)

**Interfaces:**
- Consumes: `app.repositories.*` from Task 1 (unchanged usage).
- Produces: `app.models.receipt.{IssuerData, ItemData, TotalsData, InvoiceData, ReceiptData}`, `app.views.price.{ProductItem, PriceResponse}`, `app.views.health.OllamaHealthResponse` — same field definitions as before, just relocated. No other task depends on these beyond what routes/receipts.py and routes/prices.py already use.

- [ ] **Step 1: Confirm baseline is green**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Create `app/models/__init__.py` and `app/models/receipt.py`**

```bash
cd backend
mkdir -p app/models
touch app/models/__init__.py
```

Write `backend/app/models/receipt.py`:
```python
"""
Modelos de domínio do cupom fiscal (NFC-e).

Usados tanto como corpo de entrada (POST /receipts) quanto como formato de
saída (GET/POST /receipts) — o cupom persistido é literalmente o mesmo
formato que foi recebido, não um DTO derivado.
"""
from datetime import datetime

from pydantic import BaseModel


class IssuerData(BaseModel):
    """Dados do estabelecimento emissor da nota."""
    name: str
    cnpj: str
    address: str


class ItemData(BaseModel):
    """Um item (produto) da nota fiscal."""
    code: str                          # código interno da loja
    description: str                   # nome bruto da SEFAZ (caixa alta, abreviado)
    normalized_name: str | None = None # nome normalizado pelo Ollama (None antes de salvar)
    qty: float
    unit: str
    unit_price: float
    total: float


class TotalsData(BaseModel):
    """Totais da nota fiscal."""
    total: float
    paid: float
    items_count: int


class InvoiceData(BaseModel):
    """Dados da nota fiscal (número, série, modelo, data de emissão)."""
    model: str
    series: str
    number: str
    issued_at: str  # formato ISO: "YYYY-MM-DDTHH:MM:SS"


class ReceiptData(BaseModel):
    """Representação completa de um cupom fiscal.

    created_at é None quando o cupom vem direto da SEFAZ (GET ?url=) e
    preenchido quando vem do banco (histórico ou após POST).
    Pydantic ignora created_at no body do POST — o banco sempre sobrescreve com datetime.now().
    """
    access_key: str
    url: str
    issuer: IssuerData
    items: list[ItemData]
    totals: TotalsData
    invoice: InvoiceData
    created_at: datetime | None = None
```

- [ ] **Step 3: Create `app/views/__init__.py`, `app/views/price.py`, `app/views/health.py`**

```bash
cd backend
mkdir -p app/views
touch app/views/__init__.py
```

Write `backend/app/views/price.py`:
```python
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
```

Write `backend/app/views/health.py`:
```python
"""Schema de resposta (view) do health check da Groq."""
from pydantic import BaseModel


class OllamaHealthResponse(BaseModel):
    status: str  # "ok" | "offline"
    url: str
    reason: str  # "ok" | "api_key_missing" | "http_error"
```

- [ ] **Step 4: Rewrite `app/routes/receipts.py` to import the model instead of defining it**

Replace the full content of `backend/app/routes/receipts.py` with:
```python
"""
Endpoints de cupons fiscais (NFC-e).

GET  /receipts         — lista histórico salvo no banco
GET  /receipts?url=... — busca um cupom na SEFAZ pelo QR Code
POST /receipts         — salva um cupom no banco com normalização de nomes
"""
import httpx
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pymongo.errors import DuplicateKeyError

from app.models.receipt import ReceiptData
from app.repositories.prices import insert_prices, find_product_ids_by_description
from app.repositories.products import upsert_product, list_all_product_names
from app.repositories.receipts import find_by_access_key, insert_receipt, list_receipts
from app.services.html_parser import ParseError, parse_nfce_html
from app.services.nfce_fetcher import NfceFetchError, fetch_nfce_html
from app.services.normalizer import normalize_items, pre_process, is_regression
from app.services.qr_parser import parse_qr_nfce

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/receipts", response_model=ReceiptData | list[ReceiptData])
async def get_receipts(
    request: Request,
    url: str | None = Query(None, description="URL do QR Code da NFC-e"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> ReceiptData | list[ReceiptData]:
    """Consulta ou lista cupons.

    Sem ?url → retorna o histórico salvo no banco (paginado).
    Com ?url  → busca a nota na SEFAZ, parseia e retorna (sem salvar).
               Se a chave já existir no banco, retorna o registro salvo diretamente.
    """
    db = request.app.state.db

    # Sem URL: retorna histórico paginado do banco
    if url is None:
        docs = await list_receipts(db, limit=limit, skip=skip)
        return [ReceiptData(**doc) for doc in docs]

    # Valida e extrai a chave de acesso do QR Code
    nfce_data = parse_qr_nfce(url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

    # Se o cupom já estiver no banco, retorna sem chamar a SEFAZ
    existing = await find_by_access_key(db, nfce_data.access_key)
    if existing:
        return ReceiptData(**existing)

    # Busca o HTML na SEFAZ simulando um browser mobile
    try:
        html = await fetch_nfce_html(nfce_data.url)
    except NfceFetchError as e:
        raise HTTPException(status_code=502, detail=f"SEFAZ retornou erro: {e.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao acessar a SEFAZ")

    # Parseia o HTML e extrai os dados estruturados
    try:
        parsed = parse_nfce_html(html)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=f"Não foi possível extrair dados da nota: {e}")

    # Retorna os dados sem salvar — o frontend decide se vai chamar POST /receipts
    return ReceiptData(access_key=nfce_data.access_key, url=nfce_data.url, **parsed)


@router.post("/receipts", response_model=ReceiptData, status_code=201)
async def save_receipt(body: ReceiptData, request: Request, response: Response) -> ReceiptData:
    """Persiste um cupom no banco com normalização dos nomes via Ollama.

    Fluxo:
    1. Normaliza os nomes dos itens via Ollama (fallback silencioso se Ollama estiver fora)
    2. Tenta inserir o cabeçalho em 'receipts'
       - DuplicateKeyError → cupom já existe → retorna 200 com o registro existente
    3. Registra cada item como preço em 'prices'
    4. Cadastra produtos novos em 'products'

    Status codes:
    - 201: cupom salvo com sucesso
    - 200: cupom já existia no banco (idempotente — nenhum dado duplicado)
    """
    db = request.app.state.db

    # Extrai as descrições brutas e normaliza via Ollama em um único batch
    # Fallback: se Ollama estiver fora, normalized_name = description original
    descriptions = [item.description for item in body.items]
    existing_names = await list_all_product_names(db)
    normalized = await normalize_items(descriptions, existing_names)

    # Se a descrição já tem um product_id bom de uma compra anterior, não deixa
    # uma normalização pior desta chamada (LLM fora, ou canonicalize numa âncora
    # ruim) sobrescrevê-lo — mesma guarda usada em scripts/dedup_and_renormalize.py.
    current_product_ids = await find_product_ids_by_description(db, descriptions)
    final_names = []
    for desc, norm in zip(descriptions, normalized):
        current = current_product_ids.get(desc)
        if current and (norm == pre_process(desc) or is_regression(norm, current)):
            final_names.append(current)
        else:
            final_names.append(norm)

    # Substitui o normalized_name de cada item pelo resultado do Ollama
    items = [
        item.model_copy(update={"normalized_name": name})
        for item, name in zip(body.items, final_names)
    ]
    body = body.model_copy(update={"items": items})

    # Tenta inserir o cabeçalho. DuplicateKeyError = cupom já existe no banco.
    # Fluxo novo (try/insert) em vez de find/check para economizar 1 round-trip no caminho feliz.
    try:
        inserted_header = await insert_receipt(db, body.model_dump())
    except DuplicateKeyError:
        # Cupom duplicado: retorna 200 com os dados já salvos
        response.status_code = 200
        existing = await find_by_access_key(db, body.access_key)
        return ReceiptData(**existing)

    # Cadastra produtos novos no catálogo (idempotente via upsert — duplicatas são ignoradas)
    for item in items:
        await upsert_product(db, item.normalized_name or item.description)

    # Insere um documento de preço para cada item do cupom
    await insert_prices(db, body.model_dump(), [item.model_dump() for item in items])

    # Retorna o cupom salvo com o created_at preenchido pelo banco
    return body.model_copy(update={"created_at": inserted_header["created_at"]})
```

- [ ] **Step 5: Rewrite `app/routes/prices.py` to import the views instead of defining them**

Replace the full content of `backend/app/routes/prices.py` with:
```python
"""
Endpoints de consulta de preços e catálogo de produtos.

GET /products              — lista todos os produtos do catálogo
GET /prices/latest         — último preço registrado para um produto
GET /prices/lowest         — menor preço já visto para um produto
GET /prices/history        — histórico completo de preços de um produto
GET /health/ollama         — verifica se o Ollama está acessível
"""
import os

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from app.views.price import ProductItem, PriceResponse
from app.views.health import OllamaHealthResponse
from app.repositories.prices import get_latest_price, get_lowest_price, get_price_history
from app.repositories.products import list_products

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/products", response_model=list[ProductItem])
async def list_products_endpoint(request: Request) -> list[ProductItem]:
    """Lista todos os produtos únicos do catálogo em ordem alfabética.

    Usado pelo frontend para popular a lista de busca na tela de Preços.
    """
    db = request.app.state.db
    products = await list_products(db)
    return [ProductItem(**p) for p in products]


@router.get("/prices/latest", response_model=PriceResponse)
async def read_latest_price(
    request: Request,
    product_id: str = Query(..., description="normalized_name do produto"),
) -> PriceResponse:
    """Retorna o último preço registrado para o produto (purchase_date mais recente).

    product_id deve ser o normalized_name exato retornado por GET /products.
    """
    db = request.app.state.db
    result = await get_latest_price(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return PriceResponse(**result)


@router.get("/prices/lowest", response_model=PriceResponse)
async def read_lowest_price(
    request: Request,
    product_id: str = Query(..., description="normalized_name do produto"),
) -> PriceResponse:
    """Retorna o menor preço unitário já registrado para o produto entre todas as lojas.

    Em caso de empate de preço, retorna o registro mais recente.
    """
    db = request.app.state.db
    result = await get_lowest_price(db, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return PriceResponse(**result)


@router.get("/prices/history", response_model=list[PriceResponse])
async def read_price_history(
    request: Request,
    product_id: str = Query(..., description="normalized_name do produto"),
    limit: int = Query(50, ge=1, le=200),
) -> list[PriceResponse]:
    """Retorna o histórico completo de preços do produto, do mais recente ao mais antigo.

    O parâmetro limit controla quantos registros retornar (máx. 200).
    Usado pelo botão "Ver todos os preços" na tela de Preços do frontend.
    """
    db = request.app.state.db
    results = await get_price_history(db, product_id, limit=limit)
    if not results:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return [PriceResponse(**r) for r in results]


# ---------------------------------------------------------------------------
# Health check do Ollama
# ---------------------------------------------------------------------------

@router.get("/health/ollama", response_model=OllamaHealthResponse)
async def ollama_health() -> OllamaHealthResponse:
    """Verifica se a Groq API está configurada e a chave é válida.

    Timeout/erro de rede é tratado como "ok" (benefício da dúvida) — só um 401
    (chave inválida/revogada) é reportado como falha, para não gerar falsos
    negativos por instabilidade transitória da Groq.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return OllamaHealthResponse(status="offline", url="groq", reason="api_key_missing")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code == 401:
            return OllamaHealthResponse(status="offline", url="groq", reason="http_error")
    except Exception:
        pass
    return OllamaHealthResponse(status="ok", url="groq", reason="ok")
```

- [ ] **Step 6: Verify no BaseModel classes remain in the route files**

Run: `cd backend && grep -n "class.*BaseModel" app/routes/receipts.py app/routes/prices.py`
Expected: no output (empty) — all classes now live in `models/`/`views/`.

- [ ] **Step 7: Run the full suite**

Run: `cd backend && python -m pytest -v`
Expected: same pass count as Step 1, all green. (Test files aren't touched in this task — they only ever imported `ReceiptData`/etc. indirectly through the HTTP client, except the one `insert_receipt` import already fixed in Task 1.)

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/models app/views app/routes/receipts.py app/routes/prices.py
git commit -m "refactor: extrai schemas Pydantic de routes/ pra models/ e views/

models/receipt.py = ReceiptData e tipos aninhados (entrada + domínio).
views/price.py e views/health.py = schemas só de saída. routes/ fica só
com os endpoints, sem mudança de comportamento."
```

---

### Task 3: Rename `routes/` to `controllers/`

**Files:**
- Move: `backend/app/routes/` → `backend/app/controllers/` (whole directory)
- Modify: `backend/main.py:9-10`
- Modify: `backend/tests/test_receipts_endpoint.py` (12 `patch("app.routes.receipts...")` call sites)
- Modify: `backend/tests/test_prices_endpoint.py` (4 `patch("app.routes.prices...")` call sites)

**Interfaces:**
- Consumes: `app.models.receipt.ReceiptData`, `app.views.price.*`, `app.views.health.OllamaHealthResponse` from Task 2; `app.repositories.*` from Task 1.
- Produces: `app.controllers.receipts.router`, `app.controllers.prices.router` — same `APIRouter` instances as before, just importable from the new path. Nothing after this task depends on new names beyond `main.py` and the two test files listed above.

- [ ] **Step 1: Confirm baseline is green**

Run: `cd backend && python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Rename the directory**

```bash
cd backend
git mv app/routes app/controllers
```

- [ ] **Step 3: Update `main.py`'s router imports**

In `backend/main.py`, change lines 9-10 from:
```python
from app.routes.receipts import router as receipts_router
from app.routes.prices import router as prices_router
```
to:
```python
from app.controllers.receipts import router as receipts_router
from app.controllers.prices import router as prices_router
```

- [ ] **Step 4: Update the mock-patch paths in `test_receipts_endpoint.py`**

Run:
```bash
cd backend
sed -i 's/app\.routes\.receipts\./app.controllers.receipts./g' tests/test_receipts_endpoint.py
```
This rewrites all 12 occurrences (`patch("app.routes.receipts.fetch_nfce_html", ...)` × 8 at lines 89, 101, 106, 119, 131, 136, 141, 150, plus `patch("app.routes.receipts.normalize_items", ...)` × 4 at lines 156, 163, 170, 211) to `app.controllers.receipts.`.

- [ ] **Step 5: Update the mock-patch paths in `test_prices_endpoint.py`**

Run:
```bash
cd backend
sed -i 's/app\.routes\.prices\./app.controllers.prices./g' tests/test_prices_endpoint.py
```
This rewrites all 4 occurrences of `patch("app.routes.prices.httpx.AsyncClient")` to `app.controllers.prices.httpx.AsyncClient`.

- [ ] **Step 6: Verify no stale `app.routes` references remain anywhere**

Run: `cd backend && grep -rn "app\.routes" app/ tests/ main.py`
Expected: no output (empty).

- [ ] **Step 7: Run the full suite**

Run: `cd backend && python -m pytest -v`
Expected: same pass count as Step 1, all green.

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/controllers main.py tests/test_receipts_endpoint.py tests/test_prices_endpoint.py
git add -u app/routes  # stages the directory removal (git mv already tracked the moves)
git commit -m "refactor: routes/ vira controllers/

Fecha a reorganização em camadas: models/views/controllers/services/
repositories/ agora existem de verdade e no mesmo nível dentro de app/."
```

---

### Task 4: Update `CLAUDE.md` documentation

**Files:**
- Modify: `CLAUDE.md` (repo root)

**Interfaces:**
- Consumes: nothing (pure documentation, run last so the tree it documents is final).
- Produces: nothing consumed by other tasks.

- [ ] **Step 1: Replace the "Estrutura de pastas" backend tree**

In `CLAUDE.md`, replace the block from `├── backend/` through the closing of the backend section (currently ending right before `└── frontend/`) — i.e. replace lines 52-76 — with:

```
├── backend/
│   ├── main.py             ← FastAPI app + CORS + routers
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── models/
│   │   │   └── receipt.py          ← IssuerData, ItemData, TotalsData, InvoiceData, ReceiptData
│   │   ├── views/
│   │   │   ├── price.py            ← ProductItem, PriceResponse
│   │   │   └── health.py           ← OllamaHealthResponse
│   │   ├── controllers/
│   │   │   ├── receipts.py         ← GET e POST /receipts
│   │   │   └── prices.py           ← GET /prices/latest e /prices/lowest
│   │   ├── repositories/
│   │   │   ├── connection.py       ← get_client(), get_db()
│   │   │   ├── receipts.py         ← find_by_access_key(), insert_receipt(), list_receipts()
│   │   │   └── prices.py           ← get_latest_price(), get_lowest_price()
│   │   └── services/
│   │       ├── qr_parser.py        ← parse_qr_nfce()
│   │       ├── nfce_fetcher.py     ← fetch_nfce_html()
│   │       └── html_parser.py      ← parse_nfce_html() — MG suportado; SP a implementar
│   └── tests/
│       ├── fixtures/mg_sefaz.html  ← HTML real da SEFAZ MG (Casa Rena, 07/06/2026)
│       ├── test_qr_parser.py
│       ├── test_nfce_fetcher.py
│       ├── test_html_parser.py
│       ├── test_repositories_receipts.py
│       ├── test_repositories_products.py
│       ├── test_prices_endpoint.py
│       └── test_receipts_endpoint.py
```

- [ ] **Step 2: Fix the now-contradicted note about the deleted `models/` directory**

`CLAUDE.md` currently has (around line 140-143):
```
### Diretório `backend/app/models/` deletado
Estava previsto para uma task futura mas nunca foi preenchido — continha apenas um
`__init__.py` vazio. Código especulativo vira dívida; deletado enquanto não há nada lá.
Os modelos Pydantic vivem em `routes/receipts.py` (onde são usados) e em `routes/prices.py`.
```

Replace it with:
```
### Diretório `backend/app/models/` recriado (jul/2026)
Tinha sido deletado por estar vazio/especulativo (ver histórico do repo). A razão
de deletar deixou de existir quando a reorganização em camadas MVC (models/views/
controllers/services/repositories) passou a colocar conteúdo real ali —
`ReceiptData` e os tipos aninhados (`IssuerData`, `ItemData`, `TotalsData`,
`InvoiceData`). Os schemas que são só resposta (`ProductItem`, `PriceResponse`,
`OllamaHealthResponse`) foram para `views/` em vez de `models/`.
```

- [ ] **Step 3: Verify the doc renders correctly**

Run: `cd /c/comparador-precos && grep -n "routes/\|db/repositories\|db/connection" CLAUDE.md`
Expected: no output (empty) — no stale references to the old structure remain in the doc.

- [ ] **Step 4: Commit**

```bash
cd /c/comparador-precos
git add CLAUDE.md
git commit -m "docs: atualiza CLAUDE.md pra estrutura MVC (models/views/controllers/repositories)"
```

---

## Final Verification

- [ ] Run `cd backend && python -m pytest -v` one more time — full suite green.
- [ ] Run `cd frontend && npm run test:run` — frontend untouched, but confirms nothing cross-cutting broke (there shouldn't be any frontend/backend coupling beyond HTTP, so this is a sanity check, not expected to catch anything).
- [ ] Run `cd backend && python -c "import main"` — confirms the app module graph imports cleanly end-to-end (`main.py` transitively imports every new package).
- [ ] `git log --oneline -4` should show 4 new commits: docs (CLAUDE.md), controllers rename, models/views extraction, repositories flatten — in that reverse-chronological order.
