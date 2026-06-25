# Comparador de Preços NFC-e — Contexto do Projeto

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | React 18 + TypeScript + Vite — deploy no Vercel |
| Backend | Python 3.11 + FastAPI + httpx + BeautifulSoup4 |
| Banco | MongoDB via Motor (driver async) — Task 7 |
| Testes backend | pytest + pytest-asyncio |
| Testes frontend | Vitest + Testing Library |

## Repositório

- GitHub: https://github.com/augustodbatista/comparador-precos
- Frontend live: https://comparador-precos-xi.vercel.app
- Backend: local por enquanto (deploy previsto após Task 5)

## Decisões arquiteturais

- **Backend faz GET na SEFAZ, não o frontend** — SEFAZ bloqueia requests sem headers de browser; CORS impede acesso direto do browser
- **SEFAZ não expõe EAN** — só código interno da loja; normalização de nomes é responsabilidade da API
- **Todos os campos do banco em inglês**
- **`<a target="_blank">` em vez de `window.open`** — popup blocker bloqueia `window.open` em callbacks assíncronos no mobile
- **Headers mobile no httpx** — alguns estados (PE, CE) verificam User-Agent antes de servir a página
- **Normalização via Ollama (Task 6)** — qwen2.5:7b rodando localmente em `http://localhost:11434`; todos os itens de um cupom são enviados em um único prompt batch; fallback silencioso se Ollama estiver fora (normalized_name fica igual à description original); `product_id` nas queries de preço é o `normalized_name`, não o código interno da loja — isso viabiliza comparação cross-store
- **OLLAMA_URL** — variável de ambiente configurável; padrão `http://localhost:11434`

## Schema MongoDB (Task 7)

```
receipts  → { accessKey (unique), url, issuer{}, items[], totals{}, invoice{}, createdAt }
products  → { productName }
prices    → { productId, receiptId, internalCode, originalDescription,
              quantity, unit, unitPrice, totalValue, purchaseDate, issuerCNPJ, issuerName }
```

## Metodologia

- XP + TDD: red-green-refactor, baby steps
- Mostrar plano e aguardar aprovação antes de criar qualquer arquivo
- Trabalhar uma task por vez
- Commits pequenos com mensagens claras

## Estrutura de pastas

```
comparador-precos/
├── CLAUDE.md               ← este arquivo
├── TASKS.md                ← progresso das tasks
├── README.md               ← documentação pública
├── backend/
│   ├── main.py             ← FastAPI app + CORS + routers
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── routes/
│   │   │   ├── receipts.py         ← GET e POST /receipts
│   │   │   └── prices.py           ← GET /prices/latest e /prices/lowest
│   │   ├── db/
│   │   │   ├── connection.py       ← get_client(), get_db()
│   │   │   └── repositories/
│   │   │       ├── receipts.py     ← find_by_access_key(), insert_receipt(), list_receipts()
│   │   │       └── prices.py       ← get_latest_price(), get_lowest_price()
│   │   └── services/
│   │       ├── qr_parser.py        ← parse_qr_nfce()
│   │       ├── nfce_fetcher.py     ← fetch_nfce_html()
│   │       └── html_parser.py      ← parse_nfce_html() — MG suportado; SP a implementar
│   └── tests/
│       ├── fixtures/mg_sefaz.html  ← HTML real da SEFAZ MG (Casa Rena, 07/06/2026)
│       ├── test_qr_parser.py
│       ├── test_nfce_fetcher.py
│       ├── test_html_parser.py
│       ├── test_db_receipts.py
│       ├── test_prices_endpoint.py
│       └── test_receipts_endpoint.py
└── frontend/
    ├── vercel.json
    └── src/
        ├── App.tsx
        ├── components/
        │   ├── QrReader.tsx        ← scanner + tela de resultado
        │   └── PriceConsultation.tsx ← consulta de preços por código de produto
        ├── config/
        │   └── api.ts              ← API_URL (VITE_API_URL ou fallback Render)
        └── utils/
            └── parseNfceQr.ts     ← parser de URL NFC-e (lado cliente, valida antes de chamar backend)
```

## Como rodar localmente

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env        # ajustar MONGODB_URL se necessário
uvicorn main:app --reload   # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

## Como rodar os testes

```bash
# Backend (da pasta backend/)
python -m pytest -v

# Frontend (da pasta frontend/)
npm run test:run
```

## Decisões de simplificação (refatoração jun/2026)

### `ReceiptData` absorveu `ReceiptHistoryItem`
Antes existia uma subclasse `ReceiptHistoryItem(ReceiptData)` com um único campo extra
`created_at: datetime | None = None`. Uma subclasse para um campo opcional é overhead sem
benefício: o mesmo efeito é alcançado colocando `created_at` diretamente em `ReceiptData`
como opcional. O campo fica `None` quando o cupom vem direto da SEFAZ (GET com `?url=`)
e preenchido quando vem do banco (histórico). O endpoint GET agora retorna `ReceiptData`
nos dois casos, e o POST aceita `ReceiptData` normalmente — Pydantic ignora `created_at`
no body de entrada porque o banco sempre sobrescreve com `datetime.now()`.

### POST /receipts: try/insert ao invés de find/check
O fluxo antigo fazia `find_by_access_key` antes de qualquer insert: no caminho feliz
(cupom novo, que é 99% dos casos) isso desperdiçava uma ida ao banco só para confirmar
que o documento não existe. O fluxo novo tenta o insert direto e captura `DuplicateKeyError`
do MongoDB — o índice único em `access_key` garante a colisão. Resultado: caminho feliz
cai de 2 round-trips para 1; o caminho de colisão continua em 2 (insert falha + find).

### `NfceData`: `NamedTuple` no lugar de `@dataclass`
`@dataclass(frozen=True)` e `NamedTuple` têm a mesma interface de uso (acesso por
atributo, equality por valor, imutabilidade). `NamedTuple` é idiomático Python para
"struct pequena e imutável" e não requer `from dataclasses import dataclass`. Os testes
continuam passando sem alteração porque ambos suportam `NfceData(url=x, access_key=y)`
e comparação com `==`.

### Diretório `backend/app/models/` deletado
Estava previsto para uma task futura mas nunca foi preenchido — continha apenas um
`__init__.py` vazio. Código especulativo vira dívida; deletado enquanto não há nada lá.
Os modelos Pydantic vivem em `routes/receipts.py` (onde são usados) e em `routes/prices.py`.

## Formatos de QR Code NFC-e suportados

| Estado | Formato do param | Estratégia usada |
|---|---|---|
| SP, RS | `?chNFe=<44d>` | param direto |
| RS legado | `?chConsNFCe=<44d>` | param direto |
| MG, DF e outros | `?p=<44d>\|<cDest>\|<hash>` | segmento 0 do param p |
| BA, PE e não-padrão | chave embutida na URL | fallback regex 44 dígitos |

## App Mobile

O site web original fica em `frontend/`. O app mobile híbrido fica em `mobile/` e usa Ionic React + Capacitor.

Comandos principais:

```bash
cd mobile
npm install
npm run ionic:serve
npm run android
cd android
.\gradlew.bat assembleDebug
```

O backend precisa aceitar a origem `capacitor://localhost` para chamadas vindas do WebView Android.