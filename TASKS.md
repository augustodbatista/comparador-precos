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
- `backend/app/routes/receipts.py`
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

## Task 6 — Normalização de nomes de produtos ❌

Limpar e padronizar as descrições brutas da SEFAZ para comparação entre lojas.
Estratégia ainda indefinida — pode usar heurísticas, fuzzy matching ou LLM.

**Arquivos planejados:**
- `backend/app/services/normalizer.py`
- `backend/tests/test_normalizer.py`

---

## Task 7 — Persistência no MongoDB (Motor) ✅

Motor + Atlas. `POST /receipts` persiste o cupom na primeira leitura (201) e retorna dados existentes na segunda (200), sem re-fetch na SEFAZ.

**Arquivos criados:**
- `backend/app/db/connection.py` — Motor client + helper get_db
- `backend/app/db/repositories/receipts.py` — find_by_access_key, insert_receipt
- `backend/tests/test_db_receipts.py` — 5 testes com mongomock-motor

**Arquivos modificados:**
- `backend/main.py` — lifespan abre/fecha Motor client
- `backend/app/routes/receipts.py` — fluxo com lookup de DB antes do fetch
- `backend/tests/test_receipts_endpoint.py` — 10 testes (4 novos + 6 existentes)
- `backend/app/db/repositories/products.py`
- `backend/app/db/repositories/prices.py`

---

## Task 8a — Histórico de Cupons ✅

`GET /receipts` retorna a lista de cupons persistidos no MongoDB, do mais recente para o mais antigo.
Aceita `limit` (1–100, padrão 50) e `skip` (padrão 0) para paginação.

Compatibilidade mantida:
- `GET /receipts?url=...` continua consultando uma NFC-e específica
- `POST /receipts` continua salvando o cupom de forma idempotente

**Arquivos modificados:**
- `backend/app/db/repositories/receipts.py` — `list_receipts`
- `backend/app/routes/receipts.py` — listagem em `GET /receipts`
- `backend/tests/test_db_receipts.py` — testes de listagem/paginação
- `backend/tests/test_receipts_endpoint.py` — testes de integração do histórico

---

## Task 8b — Endpoints de comparação de preços ✅

Expor a comparação de preços de produtos via API.

**Endpoints criados:**
- `GET /prices/latest?product_id=` — último preço registrado
- `GET /prices/lowest?product_id=` — menor preço já visto

**Arquivos criados:**
- `backend/app/routes/prices.py`
- `backend/app/db/repositories/prices.py`
- `backend/tests/test_prices_endpoint.py`

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

## Totais de testes

| Módulo | Arquivo | Testes |
|---|---|---|
| Backend | test_qr_parser.py | 14 |
| Backend | test_nfce_fetcher.py | 4 |
| Backend | test_html_parser.py | 19 |
| Backend | test_db_receipts.py | 7 |
| Backend | test_receipts_endpoint.py | 13 |
| Backend | test_prices_endpoint.py | 7 |
| Frontend | parseNfceQr.test.ts | 11 |
| Frontend | App.test.tsx | 1 |
| Frontend | QrReader.test.tsx | 8 |
| Frontend | PriceConsultation.test.tsx | 5 |
| **Total** | | **89** |
