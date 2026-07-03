# Reorganização do backend em camadas MVC

## Contexto

Requisito passado pelo professor: organizar o código em camadas de arquitetura
MVC, com pacotes para models, controllers, views, services e repositories.

Escopo: **só o backend** (FastAPI). O frontend React não é alterado.

## Por que "views" numa API REST

Uma API REST não tem view renderizada no servidor. Interpretação adotada:
- **models** = schemas de entrada / entidades de domínio (o que o sistema recebe e manipula)
- **views** = schemas de saída puros (o que a API devolve pro cliente, sem uso como entrada)

`ReceiptData` (e seus tipos aninhados `IssuerData`, `ItemData`, `TotalsData`,
`InvoiceData`) é ao mesmo tempo body de `POST /receipts` e `response_model` de
`GET`/`POST /receipts` — indo contra a separação estrita entrada/saída. Decisão:
fica em `models/`, como entidade de domínio (o "cupom fiscal"), já que a saída
nesse caso é literalmente o mesmo dado de entrada persistido, não um DTO
derivado. Os schemas que são *só* saída (`ProductItem`, `PriceResponse`,
`OllamaHealthResponse`) vão para `views/`.

## Arquitetura

`backend/app/` passa a ter 5 pacotes irmãos, todos no mesmo nível:

```
backend/app/
  models/        — schemas de entrada / entidades de domínio (Pydantic)
  views/         — schemas de saída puros (Pydantic)
  controllers/   — routers do FastAPI (era routes/) — só orquestra, sem lógica de negócio
  services/      — já existe, não muda de lugar
  repositories/  — sobe um nível: era app/db/repositories/, vira app/repositories/
```

`app/db/connection.py` (client Motor + criação de índices) entra dentro de
`repositories/` — é a única coisa que usa, então não cria um 6º pacote (`db/`)
só pra um arquivo.

`main.py` e `backend/scripts/` ficam onde estão: `main.py` é o entrypoint, não
uma camada; o script de manutenção (`dedup_and_renormalize.py`) não faz parte
do ciclo request/response — só reusa `services/`/`repositories/` como
consumidor externo, igual já faz hoje.

## Abordagem escolhida

Move mecânico na granularidade atual dos arquivos (sem quebrar em um arquivo
por entidade, sem introduzir classes de domínio separadas dos schemas
Pydantic). É um refactor puro: nenhum comportamento muda, nenhum teste novo é
necessário.

Alternativas descartadas:
- Granularidade fina por entidade (um arquivo por classe): infla o projeto de
  ~2 arquivos de rota pra ~10 arquivos pequenos sem ganho real de
  manutenibilidade nesse tamanho de projeto.
- Separação completa domínio/API (Clean Architecture, dataclasses de domínio +
  conversão explícita pra/de Pydantic): dobra a quantidade de tipos e
  adiciona código de tradução que não resolve nenhum problema real hoje.

## Mapeamento de arquivos

| Atual | Novo |
|---|---|
| `app/routes/receipts.py` (classes `IssuerData`, `ItemData`, `TotalsData`, `InvoiceData`, `ReceiptData`) | `app/models/receipt.py` |
| `app/routes/prices.py` (classes `ProductItem`, `PriceResponse`) | `app/views/price.py` |
| `app/routes/prices.py` (classe `OllamaHealthResponse`) | `app/views/health.py` |
| `app/routes/receipts.py` (router + endpoints) | `app/controllers/receipts.py` |
| `app/routes/prices.py` (router + endpoints) | `app/controllers/prices.py` |
| `app/services/*` | inalterado |
| `app/db/connection.py` | `app/repositories/connection.py` |
| `app/db/repositories/receipts.py` | `app/repositories/receipts.py` |
| `app/db/repositories/prices.py` | `app/repositories/prices.py` |
| `app/db/repositories/products.py` | `app/repositories/products.py` |

`__init__.py`: os pacotes de topo (`routes/`, `services/`) já têm; `db/repositories/`
não tinha por ser aninhado. `repositories/` agora fica no topo, então ganha um
`__init__.py`, junto com `models/`, `views/`, `controllers/`.

## Testes

Todos os arquivos de teste continuam em `backend/tests/`, sem subpastas.
Mudanças necessárias:
- `test_db_receipts.py` → `test_repositories_receipts.py`
- `test_db_products.py` → `test_repositories_products.py`
- Imports diretos: `from app.db.repositories...` → `from app.repositories...`
- `patch("app.routes.receipts...")` → `patch("app.controllers.receipts...")`
  (ocorre em `test_receipts_endpoint.py`)
- `patch("app.routes.prices...")` → `patch("app.controllers.prices...")`
  (ocorre em `test_prices_endpoint.py`)

## Ordem de execução

Passos pequenos, rodando `python -m pytest` depois de cada um — mantém a
suíte verde o tempo todo (é refactor, não feature nova, então não há
red-green-refactor clássico; a rede de segurança é "nunca fica quebrado por
mais de um passo"):

1. `repositories/`: move `connection.py` + `db/repositories/*.py`, adiciona
   `__init__.py`, atualiza imports em `routes/receipts.py` e `routes/prices.py`.
2. `models/` e `views/`: extrai as classes Pydantic de `routes/receipts.py` e
   `routes/prices.py`, atualiza os imports dentro das próprias rotas.
3. `controllers/`: renomeia `routes/` → `controllers/`, atualiza `main.py`.
4. Testes: atualiza patches/imports, renomeia os 2 arquivos `test_db_*.py`,
   roda a suíte completa uma última vez.

## Documentação

Atualiza a seção "Estrutura de pastas" do `CLAUDE.md` pra refletir os 5
pacotes novos (hoje documenta `routes/` e `db/repositories/`).

## Fora de escopo

- Frontend (React) — não muda.
- `backend/scripts/` — não faz parte da camada MVC (é um script de manutenção
  standalone), fica onde está.
- Qualquer mudança de comportamento, endpoint, schema de dados ou lógica de
  negócio — este é um refactor estrutural puro.
