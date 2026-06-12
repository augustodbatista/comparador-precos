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

## Task 5 — Parser HTML com BeautifulSoup4 ❌

Parsear o HTML retornado pela SEFAZ e extrair campos estruturados.

**O que extrair:**
- `issuer`: CNPJ, razão social, endereço
- `items[]`: código interno, descrição, quantidade, unidade, valor unitário, valor total
- `totals`: valor total da nota, descontos, tributos
- `invoice`: número, série, data de emissão, chave de acesso

**Arquivos planejados:**
- `backend/app/services/html_parser.py`
- `backend/tests/test_html_parser.py`

---

## Task 6 — Normalização de nomes de produtos ❌

Limpar e padronizar as descrições brutas da SEFAZ para comparação entre lojas.
Estratégia ainda indefinida — pode usar heurísticas, fuzzy matching ou LLM.

**Arquivos planejados:**
- `backend/app/services/normalizer.py`
- `backend/tests/test_normalizer.py`

---

## Task 7 — Persistência no MongoDB (Motor) ❌

Conectar Motor, criar repositórios para as três coleções.

**Coleções:**
- `receipts`: cupons fiscais (accessKey único)
- `products`: produtos normalizados
- `prices`: histórico de preços por produto/loja

**Arquivos planejados:**
- `backend/app/db/connection.py`
- `backend/app/db/repositories/receipts.py`
- `backend/app/db/repositories/products.py`
- `backend/app/db/repositories/prices.py`

---

## Task 8 — Endpoints de consulta ❌

Expor o histórico e comparação de preços via API.

**Endpoints planejados:**
- `GET /receipts` — histórico de cupons do usuário
- `GET /prices/latest?product_id=` — último preço registrado
- `GET /prices/lowest?product_id=` — menor preço já visto

**Arquivo planejado:**
- `backend/app/routes/prices.py`

---

## Totais de testes

| Módulo | Arquivo | Testes |
|---|---|---|
| Backend | test_qr_parser.py | 14 |
| Backend | test_nfce_fetcher.py | 4 |
| Backend | test_receipts_endpoint.py | 6 |
| Frontend | parseNfceQr.test.ts | 11 |
| Frontend | QrReader.test.tsx | 6 |
| **Total** | | **41** |
