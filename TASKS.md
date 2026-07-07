# Tasks — Comparador de Preços NFC-e

## Legenda
✅ Concluída | 🔄 Em andamento | ❌ Pendente

---

## Task 1 — Setup inicial ✅

Estrutura de pastas, `requirements.txt`, `main.py` esqueleto, `.env.example`.

**Arquivos criados:**
- `backend/main.py`
- `backend/requirements.txt`
- `backend/.env.example`
- `backend/app/` (estrutura de pastas vazia)
- `tests/__init__.py`

---

## Task 2 — `parse_qr_nfce` no backend ✅

Função Python que extrai URL e chave de acesso do conteúdo bruto de um QR Code NFC-e.
Suporta: `chNFe` (SP/RS), `chConsNFCe` (RS legado), param `p` (MG/DF), fallback regex.

**Arquivos criados:**
- `backend/app/services/qr_parser.py`
- `backend/tests/test_qr_parser.py` — 14 testes

---

## Task 3 — QR Reader no frontend ✅

Componente React que usa a câmera do celular para ler QR Codes de cupons fiscais.
Exibe chave de acesso, URL e botões para abrir/copiar. Deploy no Vercel.

**Arquivos criados:**
- `frontend/src/components/QrReader.tsx`
- `frontend/src/utils/parseNfceQr.ts`
- `frontend/src/components/QrReader.test.tsx` — 6 testes
- `frontend/src/utils/parseNfceQr.test.ts` — 11 testes

**Deploy:** https://comparador-precos-xi.vercel.app

---

## Task 4 — Endpoint `POST /receipts` ✅

Endpoint que recebe a URL da NFC-e, valida, busca o HTML na SEFAZ com headers de browser e retorna.
CORS configurado para Vercel. HTML cru retornado por enquanto (parser vem na Task 5).

**Arquivos criados/modificados:**
- `backend/app/controllers/receipts.py`
- `backend/app/services/nfce_fetcher.py`
- `backend/tests/test_nfce_fetcher.py` — 4 testes
- `backend/tests/test_receipts_endpoint.py` — 6 testes
- `backend/main.py` — adicionado CORS e `include_router`

---

## Task 5 — Parser HTML com BeautifulSoup4 ✅

Parseia o HTML retornado pela SEFAZ e extrai campos estruturados.
Suporte atual: MG (portalsped.fazenda.mg.gov.br). SP será adicionado com fixture real.

**O que extrai:**
- `issuer`: CNPJ, razão social, endereço
- `items[]`: código interno, descrição, quantidade, unidade, `unit_price = total / qty`, valor total
- `totals`: valor total, valor pago, quantidade de itens
- `invoice`: modelo, série, número, data de emissão (ISO 8601)

**Arquivos criados:**
- `backend/app/services/html_parser.py`
- `backend/tests/test_html_parser.py` — 19 testes
- `backend/tests/fixtures/mg_sefaz.html` — fixture HTML real da SEFAZ MG

**Endpoint atualizado:**
- `POST /receipts` retorna JSON estruturado (substituiu campo `html` cru)
- `test_receipts_endpoint.py` atualizado — 7 testes

---

## Task 6 — Normalização de nomes de produtos ✅

Normaliza as descrições brutas da SEFAZ (ex: "LEITE MOCA 395G") via Ollama (qwen2.5:7b)
no momento do `POST /receipts`. O normalized_name viabiliza comparação cross-store:
produtos iguais em lojas diferentes têm codes internos distintos mas o mesmo normalized_name.

**Decisões:**
- Ollama como serviço separado local (`OLLAMA_URL=http://localhost:11434`)
- Batch: todos os itens do cupom em uma única chamada (evita N round-trips)
- `format: json` na API do Ollama garante saída JSON válida
- Fallback silencioso: Ollama fora → normalized_name = description original, insert não trava
- product_id nas queries de preço passou de código interno para normalized_name (cross-store)
- PriceResponse agora expõe todos os campos disponíveis: endereço, invoice, receipt_url

**Arquivos criados:**
- `backend/app/services/normalizer.py` — normalize_items() com fallback
- `backend/tests/test_normalizer.py` — 5 testes (mock httpx)

**Arquivos modificados:**
- `backend/app/controllers/receipts.py` — ItemData.normalized_name + POST chama normalizer
- `backend/app/controllers/prices.py` — PriceResponse completo (endereço, invoice, url)
- `backend/app/repositories/prices.py` — query por normalized_name, _build_price_result
- `backend/.env` — OLLAMA_URL adicionado
- `backend/tests/test_prices_endpoint.py` — fixtures com normalized_name, queries por nome
- `backend/tests/test_receipts_endpoint.py` — mock normalize_items nos testes POST

---

## Task 7 — Persistência no MongoDB (Motor) ✅

Motor + Atlas. `POST /receipts` persiste o cupom na primeira leitura (201) e retorna dados existentes na segunda (200), sem re-fetch na SEFAZ.

**Arquivos criados:**
- `backend/app/repositories/connection.py` — Motor client + helper get_db
- `backend/app/repositories/receipts.py` — find_by_access_key, insert_receipt
- `backend/tests/test_repositories_receipts.py` — 5 testes com mongomock-motor

**Arquivos modificados:**
- `backend/main.py` — lifespan abre/fecha Motor client
- `backend/app/controllers/receipts.py` — fluxo com lookup de DB antes do fetch
- `backend/tests/test_receipts_endpoint.py` — 10 testes (4 novos + 6 existentes)
- `backend/app/repositories/products.py`
- `backend/app/repositories/prices.py`

---

## Task 8a — Histórico de Cupons ✅

`GET /receipts` retorna a lista de cupons persistidos no MongoDB, do mais recente para o mais antigo.
Aceita `limit` (1–100, padrão 50) e `skip` (padrão 0) para paginação.

Compatibilidade mantida:
- `GET /receipts?url=...` continua consultando uma NFC-e específica
- `POST /receipts` continua salvando o cupom de forma idempotente

**Arquivos modificados:**
- `backend/app/repositories/receipts.py` — `list_receipts`
- `backend/app/controllers/receipts.py` — listagem em `GET /receipts`
- `backend/tests/test_repositories_receipts.py` — testes de listagem/paginação
- `backend/tests/test_receipts_endpoint.py` — testes de integração do histórico

---

## Task 8b — Endpoints de comparação de preços ✅

Expor a comparação de preços de produtos via API.

**Endpoints criados:**
- `GET /prices/latest?product_id=` — último preço registrado
- `GET /prices/lowest?product_id=` — menor preço já visto

**Arquivos criados:**
- `backend/app/controllers/prices.py`
- `backend/app/repositories/prices.py`
- `backend/tests/test_prices_endpoint.py`

---

## Task 9 — Reorganização em camadas MVC ✅

Backend reorganizado em 5 camadas explícitas, atendendo a requisito de arquitetura MVC passado
pelo professor. Refactor estrutural puro — sem mudança de comportamento em nenhum endpoint.
Executado via subagent-driven development: uma task por camada, com revisão de spec/qualidade
a cada uma, mais revisão final da branch inteira antes do merge.

**Camadas:**
- `app/models/` — schemas Pydantic de entrada/domínio (`ReceiptData` e tipos aninhados)
- `app/views/` — schemas Pydantic só de saída (`ProductItem`, `PriceResponse`, `OllamaHealthResponse`)
- `app/controllers/` — routers do FastAPI (era `app/routes/`)
- `app/services/` — inalterado
- `app/repositories/` — sobe de `app/db/repositories/` + `app/db/connection.py`

**Arquivos criados:**
- `backend/app/models/receipt.py`
- `backend/app/views/price.py`
- `backend/app/views/health.py`

**Arquivos movidos/renomeados:**
- `backend/app/routes/` → `backend/app/controllers/`
- `backend/app/db/connection.py` → `backend/app/repositories/connection.py`
- `backend/app/db/repositories/*.py` → `backend/app/repositories/*.py`
- `backend/tests/test_db_receipts.py` → `backend/tests/test_repositories_receipts.py`
- `backend/tests/test_db_products.py` → `backend/tests/test_repositories_products.py`

**Docs:**
- `CLAUDE.md` — estrutura de pastas atualizada
- `docs/superpowers/specs/2026-07-02-backend-mvc-architecture-design.md`
- `docs/superpowers/plans/2026-07-02-backend-mvc-architecture.md`

**PR:** #7 (merged)

---

## Task F — Integração frontend → API ✅

O leitor de QR Code consulta o backend, exibe os dados estruturados do cupom e permite salvar a NFC-e.

**Arquivos modificados:**
- `frontend/src/components/QrReader.tsx`
- `frontend/src/components/QrReader.test.tsx`
- `frontend/src/index.css`

---

## Task F2 — Tela de consulta de preços ✅

Tela frontend para consultar o último preço e o menor preço registrado de um produto pelo código interno.

**Endpoints consumidos:**
- `GET /prices/latest?product_id=`
- `GET /prices/lowest?product_id=`

**Arquivos criados/modificados:**
- `frontend/src/components/PriceConsultation.tsx`
- `frontend/src/components/PriceConsultation.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.test.tsx`
- `frontend/src/config/api.ts`
- `frontend/src/vite-env.d.ts`
- `frontend/src/index.css`

---

## Task 10 — Login multi-usuário (JWT + bcrypt) ✅

Sistema de autenticação completo: cadastro/login com senha hasheada (bcrypt) e sessão via
JWT (7 dias, header Authorization). `receipts` privado por usuário; `products`/`prices`
continuam compartilhados entre contas. Corrigido vazamento de dados que existiria no fluxo
de duplicata de `POST /receipts` uma vez que cupons ficam privados.

**Arquivos criados:**
- `backend/app/models/user.py`, `backend/app/views/auth.py`, `backend/app/services/auth.py`
- `backend/app/repositories/users.py`, `backend/app/controllers/auth.py`
- `frontend/src/components/Auth.tsx`
- `backend/.env.example`

**Arquivos modificados:**
- `backend/app/repositories/connection.py` — índices de `users.email` e `receipts.(user_id, created_at)`
- `backend/app/repositories/receipts.py`, `backend/app/controllers/receipts.py` — scoping por usuário
- `backend/app/controllers/prices.py` — exige autenticação
- `backend/main.py` — registra `auth_router`, CORS libera header `Authorization`
- `frontend/src/config/api.ts` — `apiFetch` com injeção de JWT e tratamento de 401
- `frontend/src/App.tsx` — gate de login/logout
- `frontend/src/components/{QrReader,PriceConsultation,ReceiptHistory}.tsx` — usam `apiFetch`
- `render.yaml` — nova var `JWT_SECRET_KEY`

---

## Totais de testes

| Módulo | Arquivo | Testes |
|---|---|---|
| Backend | test_qr_parser.py | 14 |
| Backend | test_nfce_fetcher.py | 4 |
| Backend | test_html_parser.py | 19 |
| Backend | test_repositories_receipts.py | 7 |
| Backend | test_normalizer.py | 5 |
| Backend | test_receipts_endpoint.py | 13 |
| Backend | test_prices_endpoint.py | 7 |
| Frontend | parseNfceQr.test.ts | 11 |
| Frontend | App.test.tsx | 1 |
| Frontend | QrReader.test.tsx | 8 |
| Frontend | PriceConsultation.test.tsx | 5 |
| **Total** | | **94** |

---

## App Mobile Ionic/Capacitor

Criado app mobile separado em `mobile/`, mantendo o site web original em `frontend/`.

**Estrutura principal:**
- `mobile/src/` — telas Ionic React
- `mobile/capacitor.config.ts` — configuração Capacitor
- `mobile/android/` — projeto Android nativo

**Validação executada:**
- `cd mobile && npm run build`
- `cd mobile && npm run test:run -- --reporter=dot`
- `cd mobile && npm run android`
- `cd mobile/android && .\gradlew.bat assembleDebug`

**Status:**
- Build web OK
- 27 testes mobile OK
- Capacitor sync Android OK
- APK debug gerado em `mobile/android/app/build/outputs/apk/debug/app-debug.apk`