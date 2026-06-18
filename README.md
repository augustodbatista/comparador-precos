# Comparador de Preços NFC-e

Sistema colaborativo de comparação de preços via leitura de cupons fiscais eletrônicos (NFC-e).

## Como funciona

1. Usuário escaneia o QR Code impresso no cupom fiscal com o celular
2. O app extrai a URL e a chave de acesso da NFC-e
3. O backend busca a página da SEFAZ com headers de browser (evitando bloqueios)
4. O HTML é parseado para extrair emitente, produtos, quantidades e valores
5. Os preços são armazenados e comparados com compras anteriores em outras lojas

## Funcionalidades atuais

- **Leitor de QR Code** via câmera do celular — acesse em https://comparador-precos-xi.vercel.app
- **Suporte a múltiplos estados**: SP, RS, MG, BA e outros formatos de NFC-e
- **Extração da chave de acesso** (44 dígitos) e URL da SEFAZ
- **API backend** que busca o HTML da SEFAZ contornando CORS e bloqueios por User-Agent
- **Consulta de preços por código de produto** com último preço e menor preço registrado
- **Salvar cupons parseados** no MongoDB para histórico e comparação

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.11 + FastAPI + httpx |
| Parser HTML | BeautifulSoup4 *(MG suportado; SP a implementar)* |
| Banco de dados | MongoDB + Motor *(em desenvolvimento)* |
| Deploy frontend | Vercel |

## Como rodar localmente

### Pré-requisitos

- Python 3.11+
- Node.js 18+
- MongoDB (necessário para persistência local)

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

API disponível em `http://localhost:8000`
Documentação interativa em `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App disponível em `http://localhost:5173`

## API

### `GET /receipts`

Lista o histórico de cupons salvos no MongoDB.

**Query params opcionais:**
- `limit` — quantidade máxima de cupons (1–100, padrão 50)
- `skip` — quantidade de cupons a pular (padrão 0)

### `GET /receipts?url=...`

Recebe a URL de uma NFC-e, busca o HTML na SEFAZ e retorna os dados estruturados.

**Exemplo:**
```text
/receipts?url=https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=...
```

### `POST /receipts`

Salva um cupom já parseado no MongoDB. É idempotente: retorna `201` quando cria e `200` quando o cupom já existe.

**Request:**
```json
{
  "access_key": "31260661585865266267650040002426521200179790",
  "url": "https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=...",
  "issuer": { "name": "CASA RENA S/A", "cnpj": "21253729001979", "address": "AV. ARGENTINA, 270..." },
  "items": [
    { "code": "5173", "description": "SUCO D VALLE MA+S 1L", "qty": 1.0, "unit": "TP", "unit_price": 7.99, "total": 7.99 }
  ],
  "totals": { "total": 124.10, "paid": 124.10, "items_count": 15 },
  "invoice": { "model": "65", "series": "14", "number": "34772", "issued_at": "2026-06-07T11:36:44" }
}
```

**Erros de `GET /receipts?url=...`:**
| Status | Significado |
|---|---|
| 422 | URL não é uma NFC-e válida |
| 502 | SEFAZ retornou erro |
| 504 | Timeout ao acessar a SEFAZ |

### `GET /prices/latest?product_id=...`

Retorna o último preço registrado para um produto.

### `GET /prices/lowest?product_id=...`

Retorna o menor preço já visto para um produto, desempatando pelo registro mais recente.

## Testes

```bash
# Backend (64 testes no total)
cd backend && python -m pytest -v

# Frontend (24 testes no total)
cd frontend && npm run test:run
```

## Roadmap

Veja [TASKS.md](TASKS.md) para o progresso detalhado.

| Task | Status |
|---|---|
| 1. Setup inicial | ✅ |
| 2. Parser de QR Code no backend | ✅ |
| 3. Leitor de QR Code no frontend | ✅ |
| 4. Endpoint POST /receipts | ✅ |
| 5. Parser HTML (BeautifulSoup4) | ✅ |
| 6. Normalização de nomes de produtos | ❌ |
| 7. Persistência no MongoDB | ✅ |
| 8a. Histórico de cupons (`GET /receipts`) | ✅ |
| 8b. Endpoints de preços | ✅ |
| F. Integração frontend → API | ✅ |
| F2. Tela de consulta de preços | ✅ |

## Licença

MIT
