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
│   │   │   └── receipts.py         ← POST /receipts
│   │   ├── services/
│   │   │   ├── qr_parser.py        ← parse_qr_nfce()
│   │   │   └── nfce_fetcher.py     ← fetch_nfce_html()
│   │   ├── models/                 ← (Task 7)
│   │   └── db/                     ← (Task 7)
│   └── tests/
│       ├── test_qr_parser.py
│       ├── test_nfce_fetcher.py
│       └── test_receipts_endpoint.py
└── frontend/
    ├── vercel.json
    └── src/
        ├── App.tsx
        ├── components/
        │   └── QrReader.tsx        ← scanner + tela de resultado
        └── utils/
            └── parseNfceQr.ts     ← parser de URL NFC-e (lado cliente)
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

## Formatos de QR Code NFC-e suportados

| Estado | Formato do param | Estratégia usada |
|---|---|---|
| SP, RS | `?chNFe=<44d>` | param direto |
| RS legado | `?chConsNFCe=<44d>` | param direto |
| MG, DF e outros | `?p=<44d>\|<cDest>\|<hash>` | segmento 0 do param p |
| BA, PE e não-padrão | chave embutida na URL | fallback regex 44 dígitos |
