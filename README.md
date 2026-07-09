# Comparador de Preços NFC-e

Escaneia QR Codes de cupons fiscais eletrônicos (NFC-e), extrai os produtos e preços, e permite comparar o preço de um produto entre diferentes lojas ao longo do tempo. Multi-usuário: cada conta tem seu próprio histórico de cupons, mas o catálogo de preços é compartilhado entre todos.

---

## O que faz

1. **Login / cadastro** — conta com senha (bcrypt) e sessão via JWT
2. **Escaneia** o QR Code impresso no cupom com a câmera do celular
3. **Busca** o HTML da nota na SEFAZ (contornando CORS e bloqueios de User-Agent)
4. **Extrai** emitente, produtos, quantidades, preços e dados da nota fiscal
5. **Normaliza** os nomes dos produtos via Groq (ex: `REFRIG COCA COLA PET 2L` → `Refrigerante Coca-Cola Pet 2L`)
6. **Salva** no MongoDB: cabeçalho do cupom em `receipts` (privado por usuário), cada item em `prices`, catálogo em `products`
7. **Compara** o último preço e o menor preço já registrado para qualquer produto, entre todas as lojas

---

## Arquitetura

```
[Celular / Browser]
       │  login + escaneia QR Code
       ▼
[Frontend — Vercel]          https://comparador-precos-xi.vercel.app
  React 18 + TypeScript       (Authorization: Bearer <JWT>)
       │  POST /auth/login    GET /receipts   POST /receipts
       │  GET /prices/latest  GET /prices/lowest  GET /prices/history
       ▼
[Backend — Render]           https://comparador-precos-yiqd.onrender.com
  Python 3.11 + FastAPI
       │  GET (SEFAZ)          POST (normalização)
       ▼                              ▼
[SEFAZ MG / outros]          [Groq API]
                               llama-3.3-70b-versatile
       │
       ▼
[MongoDB Atlas]              collections: users, receipts, prices, products
```

### Collections MongoDB

| Collection | Conteúdo |
|---|---|
| `users` | Conta: `email` (único), senha hasheada, telefone |
| `receipts` | Cabeçalho do cupom: emitente, totais, dados da nota, `access_key` (único global), `user_id` (privado por usuário) |
| `prices` | Um documento por item comprado: preço, quantidade, data, loja (compartilhado) |
| `products` | Catálogo de produtos únicos por `normalized_name` (compartilhado) |

### Normalização de nomes (pipeline de 3 fases)

O `POST /receipts` normaliza cada descrição bruta da SEFAZ em `backend/app/services/normalizer.py`:

1. **`pre_process`** — expansão determinística de abreviações (`LVIDA`→`Longa Vida`, `REFRIG`→`Refrigerante`, …) e normalização de encoding (NFC)
2. **LLM (Groq)** — Title Case, expansão residual e correção de typos
3. **`canonicalize`** — fuzzy match (`SequenceMatcher ≥ 0.97`) contra produtos já existentes, garantindo que o mesmo produto não apareça com dois nomes

Fallback silencioso: se a `GROQ_API_KEY` faltar ou a API falhar, as fases 1 e 3 rodam sozinhas — o insert nunca trava.

---

## Pré-requisitos

| Componente | Versão / Observação |
|---|---|
| Python | 3.11+ |
| Node.js | 18+ |
| MongoDB | Atlas (ou local) |
| Groq API key | grátis em [console.groq.com](https://console.groq.com) — opcional; sem ela a normalização cai no fallback |

---

## Como rodar localmente

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # editar MONGODB_URL, GROQ_API_KEY, JWT_SECRET_KEY
uvicorn main:app --reload
```

API disponível em `http://localhost:8000`
Documentação interativa em `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App disponível em `http://localhost:5173`

---

## Variáveis de ambiente

### Backend (`.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | URI de conexão com o MongoDB |
| `DB_NAME` | `comparador_precos` | Nome do banco de dados |
| `GROQ_API_KEY` | — | Chave da Groq API para normalização (opcional) |
| `JWT_SECRET_KEY` | — | Segredo usado para assinar os tokens JWT |

### Frontend (`.env.local`, opcional)

| Variável | Padrão | Descrição |
|---|---|---|
| `VITE_API_URL` | URL do Render | URL do backend em produção |

---

## Configuração em produção

### Frontend → Vercel

Deploy automático via push no repositório. Sem configuração adicional.

### Backend → Render

- Branch: `master`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Variáveis de ambiente no painel do Render: `MONGODB_URL`, `DB_NAME`, `GROQ_API_KEY`, `JWT_SECRET_KEY`

A normalização em produção chama a Groq API diretamente — sem serviço local nem túnel.

---

## API

Todos os endpoints de `receipts` e `prices` exigem o header `Authorization: Bearer <JWT>`, obtido em `/auth/login` ou `/auth/signup`. `access_key` é único globalmente: ao tentar salvar um cupom de outro dono, o backend responde `409` sem vazar os dados originais.

### `POST /auth/signup`

Cria uma conta e já devolve um JWT. `409` se o e-mail já existir.

### `POST /auth/login`

Autentica e devolve um JWT (validade 7 dias). `401` com mensagem genérica em e-mail/senha inválidos.

### `GET /receipts`

Lista o histórico de cupons **do usuário logado**, do mais recente ao mais antigo.

| Param | Tipo | Padrão | Descrição |
|---|---|---|---|
| `limit` | int | 50 | Máximo de cupons retornados (1–100) |
| `skip` | int | 0 | Cupons a pular (paginação) |

### `GET /receipts?url=<url_qrcode>`

Consulta uma NFC-e pela URL do QR Code. Retorna os dados estruturados sem salvar.
Se o cupom já estiver no banco, retorna os dados salvos sem chamar a SEFAZ.

| Status | Significado |
|---|---|
| 200 | Dados retornados (SEFAZ ou banco) |
| 422 | URL não é uma NFC-e válida |
| 502 | SEFAZ retornou erro |
| 504 | Timeout ao acessar a SEFAZ |

### `POST /receipts`

Salva um cupom no banco, associado ao usuário logado. Idempotente: `201` na primeira vez, `200` nas seguintes.
Normaliza os nomes dos produtos via Groq antes de salvar (fallback para pré-processamento se a API estiver fora). `409` se a `access_key` já pertencer a outro usuário.

### `GET /products`

Lista todos os produtos únicos do catálogo, ordenados alfabeticamente.

### `GET /prices/latest?product_id=<nome>`

Último preço registrado para o produto (`product_id` = `normalized_name`).

### `GET /prices/lowest?product_id=<nome>`

Menor preço já registrado para o produto entre todas as lojas. Desempata pelo mais recente.

### `GET /prices/history?product_id=<nome>&limit=50`

Histórico completo de preços para o produto, do mais recente ao mais antigo.

---

## Testes

```bash
# Backend (132 testes)
cd backend
python -m pytest -v

# Frontend
cd frontend
npm run test:run
```

---

## Scripts de manutenção

Localizados em `backend/scripts/`. Rodar sempre de dentro da pasta `backend/`:

### `dedup_and_renormalize.py`

Re-passa todo o catálogo pelo pipeline de normalização atual, funde entradas duplicadas (ex: nomes all-caps salvos antes da Groq estar configurada) e reconstrói `products`. Usar quando o catálogo acumular variações do mesmo produto.

### `backfill_normalized_names.py`

Migra cupons salvos no schema antigo (com `items[]` dentro de `receipts`) para o schema atual (itens em `prices`). Idempotente.

### `backfill_receipt_user_id.py`

Preenche `user_id` em cupons salvos antes do login multi-usuário existir. Idempotente.

### `drop_collections.py`

Zera collections do banco. Destrutivo — usar só em ambiente de desenvolvimento.

```bash
cd backend
python scripts/dedup_and_renormalize.py
```

---

## Estados de NFC-e suportados

| Estado | Formato do QR Code |
|---|---|
| MG, DF e outros | `?p=<44d>\|<cDest>\|<hash>` |
| SP, RS | `?chNFe=<44d>` |
| RS legado | `?chConsNFCe=<44d>` |
| BA, PE e não-padrão | chave embutida na URL (fallback regex) |

---

## Limitações conhecidas

- **Groq free tier**: sujeito a rate limit; ao estourar, a normalização cai no fallback (pré-processamento apenas) até o limite resetar
- **Normalização inconsistente**: o LLM pode gerar nomes ligeiramente diferentes para o mesmo produto em chamadas separadas; o passo `canonicalize` mitiga, mas não elimina, entradas duplicadas no catálogo
- **SEFAZ**: suporte completo apenas para MG; outros estados podem ter variações no HTML

---

## App Mobile

O site web original permanece em `frontend/`. O app mobile híbrido (Ionic React + Capacitor) fica separado em `mobile/`.

```bash
# Site web
cd frontend
npm install
npm run dev

# App mobile
cd mobile
npm install
npm run ionic:serve
```

Para gerar o Android:

```bash
cd mobile
npm run android
cd android
.\gradlew.bat assembleDebug
```

O APK debug fica em `mobile/android/app/build/outputs/apk/debug/app-debug.apk`.
O backend aceita a origem `capacitor://localhost` para chamadas vindas do WebView Android.
