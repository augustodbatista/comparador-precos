# Comparador de Preços NFC-e

Escaneia QR Codes de cupons fiscais eletrônicos (NFC-e), extrai os produtos e preços, e permite comparar o preço de um produto entre diferentes lojas ao longo do tempo.

---

## O que faz

1. **Escaneia** o QR Code impresso no cupom com a câmera do celular
2. **Busca** o HTML da nota na SEFAZ (contornando CORS e bloqueios de User-Agent)
3. **Extrai** emitente, produtos, quantidades, preços e dados da nota fiscal
4. **Normaliza** os nomes dos produtos via Ollama (ex: `REFRI COCA COLA PET 2L` → `Refrigerante Coca-Cola 2l`)
5. **Salva** no MongoDB: cabeçalho do cupom em `receipts`, cada item em `prices`, catálogo em `products`
6. **Compara** o último preço e o menor preço já registrado para qualquer produto

---

## Arquitetura

```
[Celular / Browser]
       │  escaneia QR Code
       ▼
[Frontend — Vercel]          https://comparador-precos-xi.vercel.app
  React 18 + TypeScript
       │  GET /receipts?url=   POST /receipts
       │  GET /prices/latest   GET /prices/lowest
       ▼
[Backend — Render]           https://comparador-precos-yiqd.onrender.com
  Python 3.11 + FastAPI
       │  GET (SEFAZ)          POST /api/chat (normalização)
       ▼                              ▼
[SEFAZ MG / outros]          [Ollama local via ngrok]
                               qwen2.5:7b
       │
       ▼
[MongoDB Atlas]              collection: receipts, prices, products
```

### Collections MongoDB

| Collection | Conteúdo |
|---|---|
| `receipts` | Cabeçalho do cupom: emitente, totais, dados da nota, `access_key` (único) |
| `prices` | Um documento por item comprado: preço, quantidade, data, loja |
| `products` | Catálogo de produtos únicos por `normalized_name` |

---

## Pré-requisitos

### Para rodar localmente

| Componente | Versão |
|---|---|
| Python | 3.11+ |
| Node.js | 18+ |
| MongoDB | Atlas (ou local) |
| Ollama | qualquer versão recente |
| Modelo Ollama | `qwen2.5:7b` |

### Para normalização em produção (Render → Ollama local)

- **ngrok** — expõe o Ollama local para a internet
- **OLLAMA_ORIGINS=\*** — necessário para o Ollama aceitar requests externos

---

## Como rodar localmente

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # editar MONGODB_URL e DB_NAME
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

### 3. Ollama

```bash
# Instalar o modelo (só na primeira vez)
ollama pull qwen2.5:7b

# Rodar com permissão para requests externos (ngrok)
$env:OLLAMA_ORIGINS="*"; ollama serve   # Windows PowerShell
OLLAMA_ORIGINS="*" ollama serve         # Linux / macOS
```

---

## Variáveis de ambiente

### Backend (`.env`)

| Variável | Padrão | Descrição |
|---|---|---|
| `MONGODB_URL` | — | URI de conexão com o MongoDB Atlas |
| `DB_NAME` | `comparador_precos` | Nome do banco de dados |
| `OLLAMA_URL` | `http://localhost:11434` | URL do Ollama (local ou ngrok) |

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
- Variáveis de ambiente no painel do Render: `MONGODB_URL`, `DB_NAME`, `OLLAMA_URL`

### Ollama → ngrok (normalização em produção)

O Render não tem acesso ao Ollama local. Para normalizar os nomes em produção:

```powershell
# 1. Rodar o Ollama com ORIGINS aberto
[System.Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "*", "User")
# reiniciar o Ollama (tray icon → Quit → reabrir)

# 2. Expor via ngrok
ngrok http 11434
# Copiar a URL gerada: https://xxxx.ngrok-free.app

# 3. Atualizar OLLAMA_URL no Render
# Render Dashboard → comparador-precos-api → Environment → OLLAMA_URL = https://xxxx.ngrok-free.app
```

> **Atenção:** A URL do ngrok muda toda vez que o ngrok reinicia. Atualizar o `OLLAMA_URL` no Render quando isso acontecer.

---

## API

### `GET /receipts`

Lista o histórico de cupons salvos, do mais recente ao mais antigo.

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

Salva um cupom no banco. Idempotente: retorna `201` na primeira vez e `200` nas seguintes.  
Normaliza os nomes dos produtos via Ollama antes de salvar (fallback para descrição original se Ollama estiver fora).

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
# Backend (72 testes)
cd backend
python -m pytest -v

# Frontend
cd frontend
npm run test:run
```

---

## Scripts de manutenção

Localizados em `backend/scripts/`. Rodar sempre de dentro da pasta `backend/`:

### `renormalize_prices.py`

Re-normaliza via Ollama todos os itens em `prices` cujo `product_id` ainda é igual à `original_description` (fallback não normalizado). Usar quando cupons foram salvos sem Ollama disponível.

```bash
cd backend
python scripts/renormalize_prices.py
```

Após rodar, reconstruir o catálogo manualmente:

```bash
python -c "
import asyncio, os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
load_dotenv()
async def main():
    client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
    db = client[os.getenv('DB_NAME', 'comparador_precos')]
    ids = await db['prices'].distinct('product_id')
    await db['products'].drop()
    now = datetime.now(timezone.utc)
    await db['products'].insert_many([{'normalized_name': i, 'created_at': now} for i in ids])
    await db['products'].create_index('normalized_name', unique=True)
    print(f'{len(ids)} produtos')
    client.close()
asyncio.run(main())
"
```

### `backfill_normalized_names.py`

Migra cupons salvos no schema antigo (com `items[]` dentro de `receipts`) para o schema atual (itens em `prices`). Idempotente.

```bash
cd backend
python scripts/backfill_normalized_names.py
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

- **ngrok gratuito**: URL muda a cada reinicialização; atualizar `OLLAMA_URL` no Render manualmente
- **Ollama em CPU**: normalização leva ~30–60s por cupom com qwen2.5:7b; sem GPU é lento
- **Normalização inconsistente**: Ollama pode gerar nomes ligeiramente diferentes para o mesmo produto em chamadas separadas, gerando entradas duplicadas no catálogo
- **SEFAZ**: suporte completo apenas para MG; outros estados podem ter variações no HTML
