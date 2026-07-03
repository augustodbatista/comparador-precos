# Sistema de Login Multi-Usuário (JWT + bcrypt) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar autenticação multi-usuário (signup/login com JWT + bcrypt) ao backend FastAPI e frontend React, tornando `receipts` privado por usuário enquanto `products`/`prices` continuam compartilhados.

**Architecture:** JWT stateless via header `Authorization: Bearer`, seguindo as camadas MVC já existentes (`models/views/controllers/services/repositories`) sem criar um 6º pacote. Backend guarda `user_id` (= email) só no documento Mongo interno de `receipts`, nunca no schema `ReceiptData` — Pydantic descarta chaves não declaradas, tornando vazamento estruturalmente impossível. `access_key` continua globalmente único; ao detectar `DuplicateKeyError` de outro dono, o endpoint responde 409 sem devolver os dados do dono original.

**Tech Stack:** Python 3.11 + FastAPI + PyJWT + bcrypt (backend), React 18 + TypeScript (frontend), pytest + pytest-asyncio + mongomock-motor / Vitest + Testing Library (testes).

## Global Constraints

- Nenhuma nova pasta de topo em `backend/app/` além de `models/views/controllers/services/repositories` já existentes.
- `access_key` em `receipts` continua globalmente único (não vira índice composto).
- `user_id` nunca é campo do schema `ReceiptData` (`backend/app/models/receipt.py`) — só existe no documento Mongo interno.
- JWT: HS256, claim `sub` = email, expiração fixa de 7 dias, sem refresh token.
- Senha: bcrypt direto (não `passlib`), 8–72 caracteres (bcrypt trunca silenciosamente acima de 72).
- Token via header `Authorization: Bearer`, não cookie — `allow_credentials` do CORS em `backend/main.py` permanece `False`; único ajuste de CORS é adicionar `"Authorization"` a `allow_headers`.
- `GET /health/ollama` continua público (sem `Depends(get_current_user)`) — é chamado no mount do `App.tsx` antes de qualquer login.
- Sem lib de rotas nova no frontend (`react-router-dom` etc.) — não existe nenhuma hoje em `frontend/package.json`.
- Fora de escopo: OAuth, 2FA, reset de senha por email, refresh token, verificação de email.
- Full backend suite (`cd backend && python -m pytest -v`) e full frontend suite (`cd frontend && npm run test:run`) verdes ao final de cada task que os toca.

---

### Task 1: Serviço de autenticação (hash de senha + JWT)

**Files:**
- Create: `backend/app/services/auth.py`
- Test: `backend/tests/test_auth_service.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/.env`

**Interfaces:**
- Produces: `hash_password(password: str) -> str` (async), `verify_password(password: str, hashed: str) -> bool` (async), `create_access_token(email: str) -> str`, `decode_access_token(token: str) -> str` (retorna o email; levanta `jwt.ExpiredSignatureError` ou `jwt.InvalidTokenError`). Também exporta as constantes `JWT_SECRET_KEY`, `ALGORITHM` (usadas apenas pelos testes deste arquivo para forjar um token expirado).
- Consumes: nada (primeira task, sem dependência de outras).

- [ ] **Step 1: Adicionar as dependências novas**

Em `backend/requirements.txt`, adicionar duas linhas (em qualquer posição, ex. após `python-dotenv==1.0.1`):
```
PyJWT==2.13.0
bcrypt==5.0.0
```

Instalar: `cd backend && pip install PyJWT==2.13.0 bcrypt==5.0.0`

- [ ] **Step 2: Gerar e adicionar `JWT_SECRET_KEY` ao `.env` local**

```bash
cd backend
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))" >> .env
```
Confirmar que `backend/.env` agora tem uma linha `JWT_SECRET_KEY=<64 caracteres hex>` além de `MONGODB_URL`, `DB_NAME`, `GROQ_API_KEY`.

- [ ] **Step 3: Escrever o teste falhando**

Criar `backend/tests/test_auth_service.py`:
```python
"""
Testes unitários para hash de senha (bcrypt) e JWT (PyJWT).
Sem mocks — roda o bcrypt/PyJWT de verdade (hash bcrypt é rápido o bastante pra teste).
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.services.auth import (
    ALGORITHM,
    JWT_SECRET_KEY,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.asyncio
class TestHashPassword:
    async def test_hash_nao_e_igual_a_senha_original(self):
        hashed = await hash_password("minhasenha123")
        assert hashed != "minhasenha123"

    async def test_verify_aceita_senha_correta(self):
        hashed = await hash_password("minhasenha123")
        assert await verify_password("minhasenha123", hashed) is True

    async def test_verify_rejeita_senha_errada(self):
        hashed = await hash_password("minhasenha123")
        assert await verify_password("outrasenha", hashed) is False

    async def test_hashes_diferentes_para_mesma_senha(self):
        # bcrypt gera salt aleatório a cada chamada — dois hashes da mesma senha diferem
        h1 = await hash_password("minhasenha123")
        h2 = await hash_password("minhasenha123")
        assert h1 != h2


class TestAccessToken:
    def test_create_e_decode_roundtrip(self):
        token = create_access_token("user@example.com")
        assert decode_access_token(token) == "user@example.com"

    def test_token_adulterado_levanta_invalid_token(self):
        token = create_access_token("user@example.com")
        adulterado = token[:-1] + ("A" if token[-1] != "A" else "B")
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(adulterado)

    def test_token_expirado_levanta_expired_signature(self):
        # Forja um token com exp no passado, direto com PyJWT (não usa create_access_token,
        # que sempre gera 7 dias de validade) — mesma SECRET_KEY/ALGORITHM do módulo real.
        past = datetime.now(timezone.utc) - timedelta(days=1)
        expired_token = jwt.encode(
            {"sub": "user@example.com", "iat": past - timedelta(days=1), "exp": past},
            JWT_SECRET_KEY,
            algorithm=ALGORITHM,
        )
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(expired_token)
```

- [ ] **Step 4: Rodar o teste para confirmar que falha**

Run: `cd backend && python -m pytest tests/test_auth_service.py -v`
Expected: `ModuleNotFoundError: No module named 'app.services.auth'` (ou erro de import equivalente) — o módulo ainda não existe.

- [ ] **Step 5: Implementar `app/services/auth.py`**

Criar `backend/app/services/auth.py`:
```python
"""
Hashing de senha (bcrypt) e emissão/validação de JWT (PyJWT).

Sem imports de FastAPI — segue o mesmo padrão de app/services/*.py: funções puras
que levantam suas próprias exceções, traduzidas para HTTPException na camada de
controller (app/controllers/auth.py).
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()  # idempotente — mesmo padrão de app/repositories/connection.py

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    # Diferente de GROQ_API_KEY (degrada graciosamente), não existe fallback seguro
    # para o segredo do JWT — um valor hardcoded seria um buraco de segurança.
    raise RuntimeError(
        "JWT_SECRET_KEY não configurada. Defina no backend/.env (dev) ou nas "
        "variáveis de ambiente do Render (produção)."
    )

ALGORITHM = "HS256"
EXPIRE_DAYS = 7


def _hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password_sync(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


async def hash_password(password: str) -> str:
    """bcrypt é CPU-bound (~200-300ms) — roda em thread separada pra não travar o event loop."""
    return await asyncio.to_thread(_hash_password_sync, password)


async def verify_password(password: str, hashed: str) -> bool:
    return await asyncio.to_thread(_verify_password_sync, password, hashed)


def create_access_token(email: str) -> str:
    """Gera um JWT com 'sub' = email e expiração fixa de 7 dias (sem refresh token)."""
    now = datetime.now(timezone.utc)
    payload = {"sub": email, "iat": now, "exp": now + timedelta(days=EXPIRE_DAYS)}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    """Decodifica e valida o JWT, retornando o email (claim 'sub').

    Levanta jwt.ExpiredSignatureError ou jwt.InvalidTokenError — traduzidas
    para HTTPException 401 em controllers/auth.py.
    """
    payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    return payload["sub"]
```

- [ ] **Step 6: Rodar o teste para confirmar que passa**

Run: `cd backend && python -m pytest tests/test_auth_service.py -v`
Expected: `7 passed`

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/services/auth.py tests/test_auth_service.py requirements.txt
git commit -m "feat: adiciona serviço de auth (hash bcrypt + JWT)"
```
Nota: `backend/.env` está no `.gitignore` (mesma convenção de `MONGODB_URL`/`GROQ_API_KEY`) — não entra no commit.

---

### Task 2: Repositório de usuários

**Files:**
- Create: `backend/app/repositories/users.py`
- Test: `backend/tests/test_repositories_users.py`
- Modify: `backend/app/repositories/connection.py`

**Interfaces:**
- Consumes: nada novo (usa só `motor.motor_asyncio.AsyncIOMotorDatabase`, já usado em todo `repositories/`).
- Produces: `find_by_email(db, email: str) -> dict | None`, `insert_user(db, email: str, hashed_password: str) -> dict` (levanta `pymongo.errors.DuplicateKeyError` se o email já existir).

- [ ] **Step 1: Escrever o teste falhando**

Criar `backend/tests/test_repositories_users.py`:
```python
"""Testes para o repositório de usuários — mongomock-motor, mesmo padrão de test_repositories_receipts.py."""
import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import DuplicateKeyError

from app.repositories.users import find_by_email, insert_user


@pytest_asyncio.fixture
async def db():
    client = AsyncMongoMockClient()
    database = client["test_db"]
    await database["users"].create_index("email", unique=True)
    yield database
    client.close()


@pytest.mark.asyncio
class TestInsertUser:
    async def test_persiste_no_banco(self, db):
        await insert_user(db, "user@example.com", "hashedvalue")
        count = await db["users"].count_documents({"email": "user@example.com"})
        assert count == 1

    async def test_retorna_doc_criado(self, db):
        result = await insert_user(db, "user@example.com", "hashedvalue")
        assert result["email"] == "user@example.com"
        assert result["hashed_password"] == "hashedvalue"
        assert "created_at" in result

    async def test_email_duplicado_levanta_duplicate_key_error(self, db):
        await insert_user(db, "user@example.com", "hashedvalue")
        with pytest.raises(DuplicateKeyError):
            await insert_user(db, "user@example.com", "outrohash")


@pytest.mark.asyncio
class TestFindByEmail:
    async def test_retorna_none_quando_nao_existe(self, db):
        result = await find_by_email(db, "naoexiste@example.com")
        assert result is None

    async def test_retorna_doc_quando_existe(self, db):
        await insert_user(db, "user@example.com", "hashedvalue")
        result = await find_by_email(db, "user@example.com")
        assert result is not None
        assert result["hashed_password"] == "hashedvalue"
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd backend && python -m pytest tests/test_repositories_users.py -v`
Expected: `ModuleNotFoundError: No module named 'app.repositories.users'`

- [ ] **Step 3: Implementar `app/repositories/users.py`**

Criar `backend/app/repositories/users.py`:
```python
"""
Repositório para a coleção 'users' no MongoDB.

Regra de unicidade: email tem índice unique — inserir um email já existente
lança DuplicateKeyError (capturado no controller como 409).
"""
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError  # noqa: F401 — reexportado para uso no controller

COLLECTION = "users"


async def find_by_email(db: AsyncIOMotorDatabase, email: str) -> dict | None:
    """Busca um usuário pelo email (já normalizado para minúsculas pelo controller)."""
    return await db[COLLECTION].find_one({"email": email})


async def insert_user(db: AsyncIOMotorDatabase, email: str, hashed_password: str) -> dict:
    """Insere um novo usuário. Lança DuplicateKeyError se o email já existir."""
    doc = {"email": email, "hashed_password": hashed_password, "created_at": datetime.now(timezone.utc)}
    await db[COLLECTION].insert_one(doc)
    return doc
```

- [ ] **Step 4: Rodar o teste para confirmar que passa**

Run: `cd backend && python -m pytest tests/test_repositories_users.py -v`
Expected: `5 passed`

- [ ] **Step 5: Adicionar o índice único em `users.email`**

Em `backend/app/repositories/connection.py`, adicionar ao final de `create_indexes` (depois da linha do índice composto `(product_id, unit_price, purchase_date)`):
```python
    await db["users"].create_index("email", unique=True)
```
Atualizar também o docstring de `create_indexes` (lista de índices) para incluir a linha `- users.email: unique — impede cadastro duplicado`.

- [ ] **Step 6: Rodar a suíte completa pra confirmar que nada quebrou**

Run: `cd backend && python -m pytest -v`
Expected: todos passando — nenhum teste anterior quebrou, mais os 5 novos de `test_repositories_users.py`.

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/repositories/users.py app/repositories/connection.py tests/test_repositories_users.py
git commit -m "feat: adiciona repositório de usuários + índice único em email"
```

---

### Task 3: Endpoints de signup/login + dependency de usuário autenticado

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/views/auth.py`
- Create: `backend/app/controllers/auth.py`
- Test: `backend/tests/test_auth_endpoint.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: `hash_password`, `verify_password`, `create_access_token`, `decode_access_token` de `app.services.auth` (Task 1); `find_by_email`, `insert_user`, `DuplicateKeyError` de `app.repositories.users` (Task 2).
- Produces: `POST /auth/signup` (201, body `TokenResponse`), `POST /auth/login` (200, body `TokenResponse`), e a dependency `get_current_user(authorization: str | None = Header(None)) -> str` (retorna o email do usuário autenticado) — usada por `Depends(get_current_user)` nas Tasks 4 e 5.

- [ ] **Step 1: Adicionar `email-validator` (exigido pelo `EmailStr` do Pydantic)**

Em `backend/requirements.txt`, adicionar:
```
email-validator==2.3.0
```
Instalar: `cd backend && pip install email-validator==2.3.0`

- [ ] **Step 2: Escrever o teste falhando**

Criar `backend/tests/test_auth_endpoint.py`:
```python
"""Testes de integração para POST /auth/signup e POST /auth/login."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from main import app


@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]
    await mock_db["users"].create_index("email", unique=True)
    app.state.db = mock_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    mock_client.close()


@pytest.mark.asyncio
class TestSignup:
    async def test_retorna_201_com_token(self, client):
        response = await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "user@example.com"
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 0

    async def test_normaliza_email_para_minusculas(self, client):
        response = await client.post("/auth/signup", json={"email": "User@Example.COM", "password": "senha1234"})
        assert response.json()["email"] == "user@example.com"

    async def test_retorna_409_para_email_duplicado(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        response = await client.post("/auth/signup", json={"email": "user@example.com", "password": "outrasenha"})
        assert response.status_code == 409

    async def test_retorna_422_para_email_invalido(self, client):
        response = await client.post("/auth/signup", json={"email": "nao-e-email", "password": "senha1234"})
        assert response.status_code == 422

    async def test_retorna_422_para_senha_curta(self, client):
        response = await client.post("/auth/signup", json={"email": "user@example.com", "password": "1234567"})
        assert response.status_code == 422


@pytest.mark.asyncio
class TestLogin:
    async def test_retorna_200_com_token_para_credenciais_corretas(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        response = await client.post("/auth/login", json={"email": "user@example.com", "password": "senha1234"})
        assert response.status_code == 200
        assert response.json()["email"] == "user@example.com"

    async def test_retorna_401_para_senha_errada(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        response = await client.post("/auth/login", json={"email": "user@example.com", "password": "senhaerrada"})
        assert response.status_code == 401

    async def test_retorna_401_para_email_inexistente(self, client):
        response = await client.post("/auth/login", json={"email": "naoexiste@example.com", "password": "senha1234"})
        assert response.status_code == 401

    async def test_mensagem_generica_nao_revela_qual_campo_errou(self, client):
        await client.post("/auth/signup", json={"email": "user@example.com", "password": "senha1234"})
        r_senha_errada = await client.post("/auth/login", json={"email": "user@example.com", "password": "senhaerrada"})
        r_email_inexistente = await client.post("/auth/login", json={"email": "outro@example.com", "password": "senha1234"})
        assert r_senha_errada.json()["detail"] == r_email_inexistente.json()["detail"]
```

- [ ] **Step 3: Rodar o teste para confirmar que falha**

Run: `cd backend && python -m pytest tests/test_auth_endpoint.py -v`
Expected: erro de coleção — `main.py` ainda não expõe `/auth/signup`/`/auth/login` (404 nos primeiros asserts, ou `ModuleNotFoundError` se preferir rodar após criar só o teste).

- [ ] **Step 4: Implementar `app/models/user.py`**

Criar `backend/app/models/user.py`:
```python
"""
Modelos de entrada para autenticação (signup/login).
"""
from pydantic import BaseModel, EmailStr, field_validator

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72  # bcrypt trunca silenciosamente acima disso — validamos em vez de deixar truncar


class SignupRequest(BaseModel):
    """Corpo de POST /auth/signup."""
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def valida_tamanho_senha(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres")
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Senha deve ter no máximo {MAX_PASSWORD_LENGTH} caracteres")
        return v


class LoginRequest(BaseModel):
    """Corpo de POST /auth/login."""
    email: EmailStr
    password: str
```

- [ ] **Step 5: Implementar `app/views/auth.py`**

Criar `backend/app/views/auth.py`:
```python
"""Schema de resposta (view) da autenticação."""
from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Resposta de signup/login — o frontend guarda access_token e email, sem decodificar o JWT."""
    access_token: str
    token_type: str = "bearer"
    email: str
```

- [ ] **Step 6: Implementar `app/controllers/auth.py`**

Criar `backend/app/controllers/auth.py`:
```python
"""
Endpoints de autenticação e dependency de usuário autenticado.

POST /auth/signup — cria conta (público)
POST /auth/login  — autentica e retorna JWT (público)

get_current_user é usado via Depends() pelos demais controllers (receipts, prices)
para proteger seus endpoints.
"""
import jwt
from fastapi import APIRouter, Header, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from app.models.user import LoginRequest, SignupRequest
from app.repositories.users import find_by_email, insert_user
from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password
from app.views.auth import TokenResponse

router = APIRouter()


@router.post("/auth/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, request: Request) -> TokenResponse:
    db = request.app.state.db
    email = body.email.lower()
    hashed = await hash_password(body.password)
    try:
        await insert_user(db, email, hashed)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    token = create_access_token(email)
    return TokenResponse(access_token=token, email=email)


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    db = request.app.state.db
    email = body.email.lower()
    user = await find_by_email(db, email)
    # Mensagem genérica — não revela se o problema foi o email ou a senha
    if not user or not await verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    token = create_access_token(email)
    return TokenResponse(access_token=token, email=email)


async def get_current_user(authorization: str | None = Header(None)) -> str:
    """Dependency usada por outros controllers para exigir autenticação.

    Extrai e valida o JWT do header Authorization, retornando o email do usuário.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticação ausente")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada, faça login novamente")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
```

- [ ] **Step 7: Registrar o router e liberar o header `Authorization` no CORS**

Em `backend/main.py`, adicionar o import (junto aos outros dois routers, linha 9-10):
```python
from app.controllers.auth import router as auth_router
```
Mudar `allow_headers` (linha 59) de:
```python
    allow_headers=["Content-Type"],
```
para:
```python
    allow_headers=["Content-Type", "Authorization"],
```
E adicionar o registro do router (linha 63, antes de `receipts_router`):
```python
app.include_router(auth_router)      # POST /auth/signup, POST /auth/login
app.include_router(receipts_router)  # GET /receipts, POST /receipts
app.include_router(prices_router)    # GET /products, GET /prices/latest, /lowest, /history
```

- [ ] **Step 8: Rodar o teste para confirmar que passa**

Run: `cd backend && python -m pytest tests/test_auth_endpoint.py -v`
Expected: `9 passed`

- [ ] **Step 9: Rodar a suíte completa**

Run: `cd backend && python -m pytest -v`
Expected: todos passando — nenhum teste anterior quebrou, mais os 9 novos de `test_auth_endpoint.py`.

- [ ] **Step 10: Commit**

```bash
cd backend
git add app/models/user.py app/views/auth.py app/controllers/auth.py main.py requirements.txt tests/test_auth_endpoint.py
git commit -m "feat: adiciona endpoints POST /auth/signup e POST /auth/login"
```

---

### Task 4: Escopar `receipts` por usuário + corrigir vazamento em duplicata

**Files:**
- Modify: `backend/app/repositories/receipts.py`
- Modify: `backend/app/repositories/connection.py`
- Modify: `backend/app/controllers/receipts.py`
- Modify: `backend/tests/test_receipts_endpoint.py`
- Modify: `backend/tests/test_repositories_receipts.py`

**Interfaces:**
- Consumes: `get_current_user` de `app.controllers.auth` (Task 3).
- Produces: `find_by_access_key_for_user(db, access_key, user_id) -> dict | None`, `find_any_by_access_key(db, access_key) -> dict | None`, `list_receipts(db, user_id, *, limit=50, skip=0) -> list[dict]` (assinatura muda — `user_id` passa a ser obrigatório), `insert_receipt(db, doc, user_id) -> dict` (assinatura muda — novo parâmetro `user_id`).

Esta é a task de maior risco do plano — mexe no fluxo de duplicata que hoje vaza dados entre usuários uma vez que `receipts` fica privado. Ler `backend/app/controllers/receipts.py` e `backend/app/repositories/receipts.py` por completo antes de começar.

- [ ] **Step 1: Escrever os testes falhando em `test_receipts_endpoint.py`**

Primeiro, adicionar a dependency override na fixture `client` (topo do arquivo, logo depois dos imports existentes) — isso mantém todos os ~20 testes já existentes passando sem precisar tocar em cada um, autenticados como um usuário fixo de teste:
```python
from app.controllers.auth import get_current_user

TEST_USER = "test@example.com"


@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]
    await mock_db["receipts"].create_index("access_key", unique=True)
    await mock_db["products"].create_index("normalized_name", unique=True)
    await mock_db["prices"].create_index("product_id")
    app.state.db = mock_db
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    mock_client.close()
```
(Isso substitui a fixture `client` atual — mesma estrutura, só ganha as duas linhas de `dependency_overrides` e a constante `TEST_USER`.)

Depois, dentro da classe `TestPostReceipts`, adicionar (usando os helpers já existentes `_get_parsed_body` e `receipt_doc`):
```python
    async def test_retorna_409_quando_cupom_pertence_a_outro_usuario(self, client):
        body = await self._get_parsed_body(client)
        with patch("app.controllers.receipts.normalize_items", new=_normalize_passthrough):
            await client.post("/receipts", json=body)

        # Troca de usuário — outro dono tentando salvar o MESMO access_key
        app.dependency_overrides[get_current_user] = lambda: "outro@example.com"
        with patch("app.controllers.receipts.normalize_items", new=_normalize_passthrough):
            response = await client.post("/receipts", json=body)
        app.dependency_overrides[get_current_user] = lambda: TEST_USER  # restaura pro teardown

        assert response.status_code == 409
        assert "issuer" not in response.json()
        assert "items" not in response.json()

    async def test_retorna_200_quando_o_mesmo_usuario_reenvia(self, client):
        body = await self._get_parsed_body(client)
        with patch("app.controllers.receipts.normalize_items", new=_normalize_passthrough):
            await client.post("/receipts", json=body)
            response = await client.post("/receipts", json=body)  # reenvio, mesmo TEST_USER
        assert response.status_code == 200
        assert response.json()["access_key"] == VALID_KEY
```
Na classe `TestGetReceipts`, adicionar:
```python
    async def test_historico_nao_vaza_entre_usuarios(self, client):
        meu = receipt_doc("1" * 44, datetime(2026, 6, 1, tzinfo=timezone.utc))
        de_outro = receipt_doc("2" * 44, datetime(2026, 6, 2, tzinfo=timezone.utc))
        await app.state.db["receipts"].insert_many([
            {**meu, "user_id": TEST_USER},
            {**de_outro, "user_id": "outro@example.com"},
        ])

        response = await client.get("/receipts")

        assert response.status_code == 200
        access_keys = [r["access_key"] for r in response.json()]
        assert access_keys == ["1" * 44]

    async def test_get_por_url_de_cupom_de_outro_usuario_rebusca_na_sefaz(self, client):
        from app.repositories.receipts import insert_receipt as _insert_direto
        with patch("app.controllers.receipts.fetch_nfce_html", new=AsyncMock(return_value=MG_HTML)):
            parsed = await client.get("/receipts", params={"url": VALID_URL})
        # Salva como se fosse de outro usuário, direto no banco (bypassa o controller)
        await app.state.db["receipts"].delete_many({})
        from app.services.html_parser import parse_nfce_html as _parse
        doc = {"access_key": VALID_KEY, "url": VALID_URL, **_parse(MG_HTML)}
        doc.pop("items", None)
        await _insert_direto(app.state.db, doc, user_id="outro@example.com")

        mock_fetch = AsyncMock(return_value=MG_HTML)
        with patch("app.controllers.receipts.fetch_nfce_html", new=mock_fetch):
            response = await client.get("/receipts", params={"url": VALID_URL})

        assert response.status_code == 200
        assert mock_fetch.call_count == 1  # rebuscou — não usou o cache do outro usuário
```

- [ ] **Step 2: Rodar os testes novos para confirmar que falham**

Run: `cd backend && python -m pytest tests/test_receipts_endpoint.py -v`
Expected: falhas nos 4 testes novos (a maioria dos ~20 antigos já deve falhar também, já que `get_current_user` ainda não está sendo exigido pelos endpoints — comportamento esperado nesta etapa).

- [ ] **Step 3: Atualizar `test_repositories_receipts.py` (renomeado na Task 1 do refactor MVC para `test_repositories_receipts.py`)**

Cada chamada a `insert_receipt(db, ...)` no arquivo precisa do novo parâmetro `user_id`, e `list_receipts` precisa do novo parâmetro posicional `user_id`. Adicionar `USER_ID = "test@example.com"` no topo do arquivo (junto de `SAMPLE_DOC`), e:
- Em todo `insert_receipt(db, SAMPLE_DOC.copy())` → `insert_receipt(db, SAMPLE_DOC.copy(), USER_ID)`
- Em todo `insert_receipt(db, sample_doc(...))` → mesma troca
- Em `list_receipts(db)` / `list_receipts(db, limit=1, skip=1)` → `list_receipts(db, USER_ID)` / `list_receipts(db, USER_ID, limit=1, skip=1)`
- Nos testes de `list_receipts` que inserem docs diretamente via `db["receipts"].insert_many([...])`, cada dict precisa ganhar `"user_id": USER_ID`.

Adicionar duas classes de teste novas ao final do arquivo:
```python
@pytest.mark.asyncio
class TestFindByAccessKeyForUser:
    async def test_retorna_none_para_outro_dono(self, db):
        await insert_receipt(db, SAMPLE_DOC.copy(), "dono@example.com")
        result = await find_by_access_key_for_user(db, SAMPLE_DOC["access_key"], "outro@example.com")
        assert result is None

    async def test_retorna_doc_para_o_dono_correto(self, db):
        await insert_receipt(db, SAMPLE_DOC.copy(), "dono@example.com")
        result = await find_by_access_key_for_user(db, SAMPLE_DOC["access_key"], "dono@example.com")
        assert result is not None


@pytest.mark.asyncio
class TestFindAnyByAccessKey:
    async def test_retorna_doc_independente_do_dono(self, db):
        await insert_receipt(db, SAMPLE_DOC.copy(), "dono@example.com")
        result = await find_any_by_access_key(db, SAMPLE_DOC["access_key"])
        assert result is not None
        assert result["access_key"] == SAMPLE_DOC["access_key"]
```
E atualizar o import no topo:
```python
from app.repositories.receipts import (
    find_any_by_access_key,
    find_by_access_key_for_user,
    insert_receipt,
    list_receipts,
)
```

- [ ] **Step 4: Rodar `test_repositories_receipts.py` pra confirmar que falha**

Run: `cd backend && python -m pytest tests/test_repositories_receipts.py -v`
Expected: `ImportError` — `find_by_access_key_for_user`/`find_any_by_access_key` ainda não existem, e `insert_receipt`/`list_receipts` ainda não aceitam `user_id`.

- [ ] **Step 5: Implementar as mudanças em `app/repositories/receipts.py`**

Substituir `find_by_access_key` e adicionar `find_any_by_access_key`, e atualizar `list_receipts`/`insert_receipt`:
```python
async def find_by_access_key_for_user(db: AsyncIOMotorDatabase, access_key: str, user_id: str) -> dict | None:
    """Busca um cupom que PERTENCE a este usuário. Usado por GET ?url= (cache check)."""
    doc = await db[COLLECTION].find_one({"access_key": access_key, "user_id": user_id}, {"_id": 0})
    if not doc:
        return None
    return await _attach_items(db, doc)


async def find_any_by_access_key(db: AsyncIOMotorDatabase, access_key: str) -> dict | None:
    """Busca um cupom independente do dono. USO INTERNO APENAS — só pra resolver
    conflito de DuplicateKeyError no POST (decidir 200-próprio vs 409-de-outro).
    Nunca retornar diretamente ao cliente sem checar owner == current_user antes.
    """
    doc = await db[COLLECTION].find_one({"access_key": access_key}, {"_id": 0})
    if not doc:
        return None
    return await _attach_items(db, doc)


async def list_receipts(db: AsyncIOMotorDatabase, user_id: str, *, limit: int = 50, skip: int = 0) -> list[dict]:
    """Lista cupons DO USUÁRIO do mais recente ao mais antigo, com os itens incluídos."""
    cursor = (
        db[COLLECTION]
        .find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    receipts = await cursor.to_list(length=limit)
    return [await _attach_items(db, r) for r in receipts]


async def insert_receipt(db: AsyncIOMotorDatabase, doc: dict, user_id: str) -> dict:
    """Insere o cabeçalho do cupom, associado ao usuário que salvou.

    - Remove items[] do documento antes de inserir (os itens vão para 'prices')
    - Adiciona user_id e created_at
    - Lança DuplicateKeyError se access_key já existir (capturado no controller)
    """
    header = {k: v for k, v in doc.items() if k != "items"}
    to_insert = {**header, "user_id": user_id, "created_at": datetime.now(timezone.utc)}
    await db[COLLECTION].insert_one(to_insert)
    to_insert.pop("_id", None)
    return to_insert
```
Remover a função antiga `find_by_access_key` (foi substituída pelas duas novas acima). Atualizar o docstring do módulo (topo do arquivo) trocando a menção a "capturado no route" por "capturado no controller", e mencionando que `receipts` agora é privado por `user_id`.

- [ ] **Step 6: Adicionar o índice composto `(user_id, created_at)`**

Em `backend/app/repositories/connection.py`, adicionar (depois do índice `users.email` da Task 2):
```python
    # Índice composto para GET /receipts (filtra por usuário, ordena por mais recente)
    await db["receipts"].create_index([("user_id", 1), ("created_at", -1)])
```

- [ ] **Step 7: Rodar `test_repositories_receipts.py` pra confirmar que passa**

Run: `cd backend && python -m pytest tests/test_repositories_receipts.py -v`
Expected: todos passando (contagem original + 3 novos).

- [ ] **Step 8: Implementar as mudanças em `app/controllers/receipts.py`**

Substituir o conteúdo do arquivo:
```python
"""
Endpoints de cupons fiscais (NFC-e).

GET  /receipts         — lista histórico salvo no banco (do usuário autenticado)
GET  /receipts?url=... — busca um cupom na SEFAZ pelo QR Code
POST /receipts         — salva um cupom no banco com normalização de nomes
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pymongo.errors import DuplicateKeyError

from app.controllers.auth import get_current_user
from app.models.receipt import ReceiptData
from app.repositories.prices import insert_prices, find_product_ids_by_description
from app.repositories.products import upsert_product, list_all_product_names
from app.repositories.receipts import find_any_by_access_key, find_by_access_key_for_user, insert_receipt, list_receipts
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
    current_user: str = Depends(get_current_user),
    url: str | None = Query(None, description="URL do QR Code da NFC-e"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
) -> ReceiptData | list[ReceiptData]:
    """Consulta ou lista cupons DO USUÁRIO AUTENTICADO.

    Sem ?url → retorna o histórico salvo no banco (paginado), só os cupons deste usuário.
    Com ?url  → busca a nota na SEFAZ, parseia e retorna (sem salvar).
               Se ESTE usuário já tiver essa chave salva, retorna o registro salvo direto.
               Se pertencer a outro usuário, comporta-se como cupom novo (rebusca na SEFAZ).
    """
    db = request.app.state.db

    if url is None:
        docs = await list_receipts(db, current_user, limit=limit, skip=skip)
        return [ReceiptData(**doc) for doc in docs]

    nfce_data = parse_qr_nfce(url)
    if nfce_data is None:
        raise HTTPException(status_code=422, detail="URL não é uma NFC-e válida")

    # Só reaproveita cache se o cupom é DESTE usuário — de outro dono, comporta-se como novo
    existing = await find_by_access_key_for_user(db, nfce_data.access_key, current_user)
    if existing:
        return ReceiptData(**existing)

    try:
        html = await fetch_nfce_html(nfce_data.url)
    except NfceFetchError as e:
        raise HTTPException(status_code=502, detail=f"SEFAZ retornou erro: {e.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Timeout ao acessar a SEFAZ")

    try:
        parsed = parse_nfce_html(html)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=f"Não foi possível extrair dados da nota: {e}")

    return ReceiptData(access_key=nfce_data.access_key, url=nfce_data.url, **parsed)


@router.post("/receipts", response_model=ReceiptData, status_code=201)
async def save_receipt(
    body: ReceiptData,
    request: Request,
    response: Response,
    current_user: str = Depends(get_current_user),
) -> ReceiptData:
    """Persiste um cupom no banco (associado ao usuário autenticado) com normalização de nomes.

    Fluxo:
    1. Normaliza os nomes dos itens via Ollama (fallback silencioso se Ollama estiver fora)
    2. Tenta inserir o cabeçalho em 'receipts', associado ao current_user
       - DuplicateKeyError, mesmo dono → cupom já existe → retorna 200 (idempotente)
       - DuplicateKeyError, outro dono → 409, sem devolver os dados do dono original
    3. Registra cada item como preço em 'prices' (coleção compartilhada entre usuários)
    4. Cadastra produtos novos em 'products' (catálogo compartilhado)

    Status codes:
    - 201: cupom salvo com sucesso
    - 200: cupom já existia no banco PARA ESTE USUÁRIO (idempotente — nenhum dado duplicado)
    - 409: cupom já existe, mas pertence a outra conta
    """
    db = request.app.state.db

    descriptions = [item.description for item in body.items]
    existing_names = await list_all_product_names(db)
    normalized = await normalize_items(descriptions, existing_names)

    current_product_ids = await find_product_ids_by_description(db, descriptions)
    final_names = []
    for desc, norm in zip(descriptions, normalized):
        current = current_product_ids.get(desc)
        if current and (norm == pre_process(desc) or is_regression(norm, current)):
            final_names.append(current)
        else:
            final_names.append(norm)

    items = [
        item.model_copy(update={"normalized_name": name})
        for item, name in zip(body.items, final_names)
    ]
    body = body.model_copy(update={"items": items})

    try:
        inserted_header = await insert_receipt(db, body.model_dump(), user_id=current_user)
    except DuplicateKeyError:
        existing = await find_any_by_access_key(db, body.access_key)
        if existing and existing.get("user_id") == current_user:
            # Reenvio idempotente do próprio usuário (ex.: duplo clique) — comportamento preservado
            response.status_code = 200
            return ReceiptData(**existing)
        # Chave já pertence a OUTRO usuário — nunca retorna os dados dele
        raise HTTPException(status_code=409, detail="Este cupom já foi salvo por outra conta.")

    for item in items:
        await upsert_product(db, item.normalized_name or item.description)

    await insert_prices(db, body.model_dump(), [item.model_dump() for item in items])

    return body.model_copy(update={"created_at": inserted_header["created_at"]})
```

- [ ] **Step 9: Rodar toda a suíte de receipts**

Run: `cd backend && python -m pytest tests/test_receipts_endpoint.py tests/test_repositories_receipts.py -v`
Expected: todos passando.

- [ ] **Step 10: Rodar a suíte completa**

Run: `cd backend && python -m pytest -v`
Expected: todos passando (contagem cresce em 4 testes de `test_receipts_endpoint.py` + 3 de `test_repositories_receipts.py` sobre o total da Task 3).

- [ ] **Step 11: Commit**

```bash
cd backend
git add app/repositories/receipts.py app/repositories/connection.py app/controllers/receipts.py \
        tests/test_receipts_endpoint.py tests/test_repositories_receipts.py
git commit -m "feat: escopa receipts por usuário e corrige vazamento de dados em duplicata"
```

---

### Task 5: Proteger `/products` e `/prices/*`

**Files:**
- Modify: `backend/app/controllers/prices.py`
- Modify: `backend/tests/test_prices_endpoint.py`

**Interfaces:**
- Consumes: `get_current_user` de `app.controllers.auth` (Task 3).
- Produces: nada novo — só adiciona autenticação obrigatória aos endpoints existentes (`/products`, `/prices/latest`, `/prices/lowest`, `/prices/history`). `/health/ollama` fica como está, sem autenticação.

- [ ] **Step 1: Atualizar a fixture de `test_prices_endpoint.py`**

Adicionar a mesma dependency override da Task 4 (topo do arquivo, junto dos imports):
```python
from app.controllers.auth import get_current_user
```
E na fixture `client` (adicionar as duas linhas de override, mantendo o resto igual):
```python
@pytest_asyncio.fixture
async def client():
    mock_client = AsyncMongoMockClient()
    mock_db = mock_client["test_db"]

    await mock_db["receipts"].create_index("access_key", unique=True)
    await mock_db["products"].create_index("normalized_name", unique=True)
    await mock_db["prices"].create_index("product_id")

    now = datetime.now(timezone.utc)
    await mock_db["receipts"].insert_many([{**h, "created_at": now} for h in RECEIPT_HEADERS])
    await mock_db["prices"].insert_many([{**p, "created_at": now} for p in PRICE_DOCS])
    await mock_db["products"].insert_many([{**p, "created_at": now} for p in PRODUCT_DOCS])

    app.state.db = mock_db
    app.dependency_overrides[get_current_user] = lambda: "test@example.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    mock_client.close()
```
Adicionar um teste novo (em qualquer classe existente, ex. no final de `TestPricesEndpoints`, ou em uma nova classe `TestPricesRequerAuth`):
```python
@pytest.mark.asyncio
class TestPricesRequerAuth:
    async def test_products_retorna_401_sem_token(self):
        # cliente separado, SEM dependency_overrides, pra testar o caminho real sem auth
        mock_client = AsyncMongoMockClient()
        app.state.db = mock_client["test_db"]
        app.dependency_overrides.clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/products")
        assert response.status_code == 401
        mock_client.close()
```

- [ ] **Step 2: Rodar a suíte de prices para confirmar que o teste novo falha e os antigos ainda passam**

Run: `cd backend && python -m pytest tests/test_prices_endpoint.py -v`
Expected: só `test_products_retorna_401_sem_token` falha (com 200 em vez de 401) — os demais continuam passando graças ao `dependency_overrides`.

- [ ] **Step 3: Adicionar `Depends(get_current_user)` aos 4 endpoints**

Em `backend/app/controllers/prices.py`, adicionar o import:
```python
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.controllers.auth import get_current_user
```
E adicionar `current_user: str = Depends(get_current_user)` como parâmetro em `list_products_endpoint`, `read_latest_price`, `read_lowest_price` e `read_price_history` (não em `ollama_health`). Exemplo pra `list_products_endpoint`:
```python
@router.get("/products", response_model=list[ProductItem])
async def list_products_endpoint(
    request: Request, current_user: str = Depends(get_current_user)
) -> list[ProductItem]:
```
(mesma mudança de assinatura nos outros 3 — só adicionar o parâmetro, corpo da função não muda.)

- [ ] **Step 4: Rodar a suíte de prices para confirmar que tudo passa**

Run: `cd backend && python -m pytest tests/test_prices_endpoint.py -v`
Expected: todos passando.

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd backend && python -m pytest -v`
Expected: todos passando (+1 sobre a Task 4).

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/controllers/prices.py tests/test_prices_endpoint.py
git commit -m "feat: exige autenticação em /products e /prices/*"
```

---

### Task 6: `apiFetch` — wrapper de fetch com JWT e tratamento de 401

**Files:**
- Modify: `frontend/src/config/api.ts`
- Test: `frontend/src/config/api.test.ts`

**Interfaces:**
- Consumes: nada (usa só `localStorage` e `fetch` globais).
- Produces: `getToken(): string | null`, `setToken(token: string): void`, `clearToken(): void`, `setUnauthorizedHandler(handler: () => void): void`, `apiFetch(input: string, init?: RequestInit): Promise<Response>` — usados pelas Tasks 7, 8 e 9.

- [ ] **Step 1: Escrever o teste falhando**

Criar `frontend/src/config/api.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiFetch, getToken, setToken, clearToken, setUnauthorizedHandler } from './api'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockClear()
  fetchMock.mockResolvedValue({ status: 200, ok: true })
  setUnauthorizedHandler(() => {})
})

afterEach(() => {
  localStorage.clear()
})

describe('token storage', () => {
  it('getToken retorna null quando não há token salvo', () => {
    expect(getToken()).toBeNull()
  })

  it('setToken/getToken fazem roundtrip', () => {
    setToken('abc123')
    expect(getToken()).toBe('abc123')
  })

  it('clearToken remove o token salvo', () => {
    setToken('abc123')
    clearToken()
    expect(getToken()).toBeNull()
  })
})

describe('apiFetch', () => {
  it('não anexa Authorization quando não há token', async () => {
    await apiFetch('https://api.test/x')
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBeNull()
  })

  it('anexa Authorization: Bearer quando há token', async () => {
    setToken('meutoken')
    await apiFetch('https://api.test/x')
    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer meutoken')
  })

  it('chama o handler de unauthorized e limpa o token numa resposta 401', async () => {
    setToken('meutoken')
    fetchMock.mockResolvedValueOnce({ status: 401, ok: false })
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await apiFetch('https://api.test/x')

    expect(handler).toHaveBeenCalledOnce()
    expect(getToken()).toBeNull()
  })

  it('não chama o handler numa resposta 200', async () => {
    setToken('meutoken')
    fetchMock.mockResolvedValueOnce({ status: 200, ok: true })
    const handler = vi.fn()
    setUnauthorizedHandler(handler)

    await apiFetch('https://api.test/x')

    expect(handler).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd frontend && npm run test:run -- api.test`
Expected: falha de import — `getToken`/`setToken`/`clearToken`/`apiFetch`/`setUnauthorizedHandler` ainda não existem em `config/api.ts`.

- [ ] **Step 3: Implementar em `frontend/src/config/api.ts`**

Substituir o conteúdo do arquivo:
```ts
// URL base da API. Em desenvolvimento local usa a variável de ambiente VITE_API_URL;
// em produção (Vercel), cai no fallback apontando para o backend no Render.
export const API_URL = import.meta.env.VITE_API_URL || 'https://comparador-precos-yiqd.onrender.com'

const TOKEN_KEY = 'auth_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

/** Wrapper de fetch: injeta Authorization automaticamente e trata 401 globalmente. */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(input, { ...init, headers })
  if (response.status === 401) {
    clearToken()
    onUnauthorized?.()
  }
  return response
}
```

- [ ] **Step 4: Rodar o teste para confirmar que passa**

Run: `cd frontend && npm run test:run -- api.test`
Expected: `7 passed`

- [ ] **Step 5: Rodar a suíte completa do frontend**

Run: `cd frontend && npm run test:run`
Expected: todos passando (28 anteriores + 7 novos = 35) — nada mais foi tocado ainda, então `QrReader`/`PriceConsultation`/`ReceiptHistory`/`App` continuam usando `fetch` direto.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/config/api.ts src/config/api.test.ts
git commit -m "feat: adiciona apiFetch com injeção de JWT e tratamento global de 401"
```

---

### Task 7: Componente `Auth.tsx` (login/signup)

**Files:**
- Create: `frontend/src/components/Auth.tsx`
- Test: `frontend/src/components/Auth.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `API_URL`, `setToken` de `frontend/src/config/api.ts` (Task 6).
- Produces: `export function Auth({ onAuthenticated }: { onAuthenticated: (token: string) => void })` — usado por `App.tsx` na Task 8. (`email` não é repassado: `App.tsx` não exibe o email em nenhum lugar, então o componente não inventa um parâmetro sem consumidor.)

- [ ] **Step 1: Escrever o teste falhando**

Criar `frontend/src/components/Auth.test.tsx`:
```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { Auth } from './Auth'

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  fetchMock.mockClear()
})

describe('Auth', () => {
  it('renderiza o modo login por padrão', () => {
    render(<Auth onAuthenticated={vi.fn()} />)
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('alterna para o modo cadastro e volta', async () => {
    render(<Auth onAuthenticated={vi.fn()} />)
    await userEvent.click(screen.getByText(/criar conta/i))
    expect(screen.getByRole('button', { name: /cadastrar/i })).toBeInTheDocument()

    await userEvent.click(screen.getByText(/já tenho conta/i))
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('login bem-sucedido chama onAuthenticated com token e email', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ access_token: 'tok123', token_type: 'bearer', email: 'user@example.com' }),
    })
    const onAuthenticated = vi.fn()
    render(<Auth onAuthenticated={onAuthenticated} />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))

    await waitFor(() => {
      expect(onAuthenticated).toHaveBeenCalledWith('tok123')
    })
  })

  it('exibe erro em credenciais inválidas', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ detail: 'E-mail ou senha inválidos' }),
    })
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senhaerrada')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/e-mail ou senha inválidos/i)
    })
  })

  it('exibe erro em cadastro com email duplicado', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ detail: 'E-mail já cadastrado' }),
    })
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.click(screen.getByText(/criar conta/i))
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /cadastrar/i }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/e-mail já cadastrado/i)
    })
  })

  it('desabilita o botão enquanto a requisição está pendente', async () => {
    fetchMock.mockImplementationOnce(() => new Promise(() => {}))
    render(<Auth onAuthenticated={vi.fn()} />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senha1234')
    const btn = screen.getByRole('button', { name: /entrar/i })
    await userEvent.click(btn)

    expect(btn).toBeDisabled()
  })
})
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd frontend && npm run test:run -- Auth.test`
Expected: falha de import — `./Auth` ainda não existe.

- [ ] **Step 3: Implementar `frontend/src/components/Auth.tsx`**

```tsx
import { useState } from 'react'
import { API_URL, apiFetch, setToken } from '../config/api'

type Mode = 'login' | 'signup'

export function Auth({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (mode === 'signup' && password.length < 8) {
      setError('A senha deve ter pelo menos 8 caracteres.')
      return
    }

    setIsSubmitting(true)
    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/signup'
      const response = await apiFetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}))
        throw new Error(errData.detail || `Erro (${response.status})`)
      }

      const data = await response.json()
      setToken(data.access_token)
      onAuthenticated(data.access_token)
    } catch (err: any) {
      setError(err.message || 'Erro de conexão.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="card" style={{ maxWidth: '360px', margin: '2rem auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>{mode === 'login' ? 'Entrar' : 'Criar conta'}</h2>

      {error && (
        <div className="alert alert-danger" role="alert" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '0.75rem' }}>
          <label htmlFor="auth-email" style={{ display: 'block', marginBottom: '0.25rem' }}>E-mail</label>
          <input
            id="auth-email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            style={{ width: '100%', padding: '0.5rem 0.75rem', border: '1px solid var(--border-color)', borderRadius: '6px' }}
          />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="auth-password" style={{ display: 'block', marginBottom: '0.25rem' }}>Senha</label>
          <input
            id="auth-password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{ width: '100%', padding: '0.5rem 0.75rem', border: '1px solid var(--border-color)', borderRadius: '6px' }}
          />
        </div>

        <button className="btn btn-primary" type="submit" disabled={isSubmitting} style={{ width: '100%' }}>
          {isSubmitting ? 'Aguarde...' : mode === 'login' ? 'Entrar' : 'Cadastrar'}
        </button>
      </form>

      <button
        type="button"
        onClick={() => { setMode(m => m === 'login' ? 'signup' : 'login'); setError(null) }}
        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', marginTop: '1rem', width: '100%', textAlign: 'center' }}
      >
        {mode === 'login' ? 'Criar conta' : 'Já tenho conta'}
      </button>
    </div>
  )
}
```

- [ ] **Step 4: Rodar o teste para confirmar que passa**

Run: `cd frontend && npm run test:run -- Auth.test`
Expected: `6 passed`

- [ ] **Step 5: Rodar a suíte completa do frontend**

Run: `cd frontend && npm run test:run`
Expected: todos passando (35 anteriores + 6 novos = 41).

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/components/Auth.tsx src/components/Auth.test.tsx
git commit -m "feat: adiciona tela de login/cadastro"
```

---

### Task 8: Gate de login em `App.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `getToken`, `clearToken`, `setUnauthorizedHandler` de `config/api.ts` (Task 6); `Auth` de `components/Auth.tsx` (Task 7).
- Produces: nada novo consumido por outra task — é o topo da árvore.

- [ ] **Step 1: Atualizar `App.test.tsx`**

Substituir o conteúdo do arquivo:
```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import App from './App'

vi.mock('./components/QrReader', () => ({
  QrReader: () => <div>Scanner mock</div>,
}))

const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  localStorage.clear()
  fetchMock.mockClear()
  fetchMock.mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({}) })
})

describe('App', () => {
  it('mostra a tela de login quando não há token salvo', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /entrar/i })).toBeInTheDocument()
    expect(screen.queryByText('Scanner mock')).not.toBeInTheDocument()
  })

  it('login bem-sucedido revela o app principal', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ access_token: 'tok123', token_type: 'bearer', email: 'user@example.com' }),
    })
    render(<App />)

    await userEvent.type(screen.getByLabelText(/e-mail/i), 'user@example.com')
    await userEvent.type(screen.getByLabelText(/senha/i), 'senha1234')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))

    expect(await screen.findByText('Scanner mock')).toBeInTheDocument()
  })

  it('alterna entre scanner e consulta de preços quando autenticado', async () => {
    localStorage.setItem('auth_token', 'tok123')
    render(<App />)

    expect(screen.getByText('Scanner mock')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /preços/i }))

    expect(screen.getByRole('heading', { name: /consulta de preços/i })).toBeInTheDocument()
    expect(screen.queryByText('Scanner mock')).not.toBeInTheDocument()
  })

  it('logout limpa o token e volta pra tela de login', async () => {
    localStorage.setItem('auth_token', 'tok123')
    render(<App />)
    expect(screen.getByText('Scanner mock')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /sair/i }))

    expect(screen.getByRole('heading', { name: /entrar/i })).toBeInTheDocument()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd frontend && npm run test:run -- App.test`
Expected: falham — `App.tsx` ainda não tem gate de login nem botão de logout.

- [ ] **Step 3: Implementar o gate em `frontend/src/App.tsx`**

Substituir o conteúdo do arquivo:
```tsx
import { useEffect, useState } from 'react'
import { QrReader } from './components/QrReader'
import { PriceConsultation } from './components/PriceConsultation'
import { ReceiptHistory } from './components/ReceiptHistory'
import { Auth } from './components/Auth'
import { API_URL, clearToken, getToken, setUnauthorizedHandler } from './config/api'

type AppView = 'scanner' | 'prices' | 'history'

function useDarkMode() {
  const getInitial = () => {
    const stored = localStorage.getItem('theme')
    if (stored === 'dark') return true
    if (stored === 'light') return false
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  const [dark, setDark] = useState(getInitial)

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return [dark, () => setDark(d => !d)] as const
}

function useAuth() {
  const [token, setTokenState] = useState<string | null>(() => getToken())

  useEffect(() => {
    setUnauthorizedHandler(() => setTokenState(null))
  }, [])

  function login(newToken: string) {
    setTokenState(newToken)
  }

  function logout() {
    clearToken()
    setTokenState(null)
  }

  return { token, login, logout }
}

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('scanner')
  const [dark, toggleTheme] = useDarkMode()
  const { token, login, logout } = useAuth()

  // Acorda o backend no Render (free tier dorme após ~15 min sem uso).
  // O ping é fire-and-forget: erros são silenciados. Endpoint público — não exige login.
  useEffect(() => {
    fetch(`${API_URL}/health/ollama`).catch(() => {})
  }, [])

  if (!token) {
    return (
      <main className="app-container">
        <Auth onAuthenticated={login} />
      </main>
    )
  }

  return (
    <main className="app-container">
      <header className="app-header">
        <h1>Comparador de Preços NFC-e</h1>

        <nav className="app-tabs" aria-label="Navegação principal">
          <button
            className={activeView === 'scanner' ? 'app-tab active' : 'app-tab'}
            type="button"
            onClick={() => setActiveView('scanner')}
          >
            Scanner
          </button>
          <button
            className={activeView === 'prices' ? 'app-tab active' : 'app-tab'}
            type="button"
            onClick={() => setActiveView('prices')}
          >
            Preços
          </button>
          <button
            className={activeView === 'history' ? 'app-tab active' : 'app-tab'}
            type="button"
            onClick={() => setActiveView('history')}
          >
            Histórico
          </button>
        </nav>

        <button className="btn btn-outline" type="button" onClick={logout} style={{ marginLeft: 'auto' }}>
          Sair
        </button>
      </header>

      {activeView === 'scanner' && <QrReader />}
      {activeView === 'prices' && <PriceConsultation />}
      {activeView === 'history' && <ReceiptHistory />}

      <button
        className="theme-toggle"
        type="button"
        onClick={toggleTheme}
        aria-label={dark ? 'Ativar modo claro' : 'Ativar modo escuro'}
        title={dark ? 'Modo claro' : 'Modo escuro'}
      >
        {dark ? '☀' : '☾'}
      </button>
    </main>
  )
}
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

Run: `cd frontend && npm run test:run -- App.test`
Expected: `4 passed`

- [ ] **Step 5: Rodar a suíte completa do frontend**

Run: `cd frontend && npm run test:run`
Expected: todos passando (a contagem de `App.test.tsx` muda de 1 pra 4 teste — total geral cresce em 3 sobre a Task 7).

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/App.tsx src/App.test.tsx
git commit -m "feat: adiciona gate de login e logout em App.tsx"
```

---

### Task 9: Trocar `fetch` por `apiFetch` nos componentes existentes

**Files:**
- Modify: `frontend/src/components/QrReader.tsx`
- Modify: `frontend/src/components/PriceConsultation.tsx`
- Modify: `frontend/src/components/ReceiptHistory.tsx`

**Interfaces:**
- Consumes: `apiFetch` de `config/api.ts` (Task 6).
- Produces: nada novo — última task de código, fecha o fluxo de autenticação ponta a ponta.

- [ ] **Step 1: `QrReader.tsx` — trocar os 3 call sites**

Adicionar `apiFetch` ao import de `../config/api` (linha 4, hoje `import { API_URL } from '../config/api'`):
```tsx
import { API_URL, apiFetch } from '../config/api'
```
Trocar `fetch(` por `apiFetch(` nas 3 ocorrências:
- Linha 255 (health check): `fetch(\`${API_URL}/health/ollama\`)` → `apiFetch(\`${API_URL}/health/ollama\`)`
- Linha 301 (`doFetch`, dentro de `handleScan`): `fetch(\`${API_URL}/receipts?url=...\`, { signal: controller.signal })` → `apiFetch(...)` mesma assinatura
- Linha 358 (`handleSave`, POST): `fetch(\`${API_URL}/receipts\`, { method: 'POST', ... })` → `apiFetch(...)` mesma assinatura

Nenhuma outra linha muda — os 3 `fetch(` seguem com exatamente os mesmos argumentos, só o nome da função troca.

- [ ] **Step 2: `PriceConsultation.tsx` — trocar os 3 call sites**

Adicionar `apiFetch` ao import (linha 2, hoje `import { API_URL } from '../config/api'`):
```tsx
import { API_URL, apiFetch } from '../config/api'
```
Trocar `fetch(` por `apiFetch(` em `fetchPrice` (linha 49), `fetchHistory` (linha 56) e `fetchProducts` (linha 62) — mesma assinatura em cada.

- [ ] **Step 3: `ReceiptHistory.tsx` — trocar o call site**

Adicionar `apiFetch` ao import (linha 2, hoje `import { API_URL } from '../config/api'`):
```tsx
import { API_URL, apiFetch } from '../config/api'
```
Trocar `fetch(` por `apiFetch(` em `fetchReceipts` (linha 6) — mesma assinatura.

- [ ] **Step 4: Rodar a suíte completa do frontend**

Run: `cd frontend && npm run test:run`
Expected: todos passando, mesma contagem da Task 8 — `QrReader.test.tsx` e `PriceConsultation.test.tsx` continuam batendo porque já stubam o `fetch` global (`vi.stubGlobal('fetch', fetchMock)`), e `apiFetch` chama esse mesmo `fetch` por baixo. Se algum teste falhar aqui, é sinal de que alguma asserção dependia de `fetch` ser chamado com exatamente os headers antigos — investigar antes de prosseguir, não ignorar.

- [ ] **Step 5: Teste manual de ponta a ponta**

```bash
# Terminal 1
cd backend && uvicorn main:app --reload
# Terminal 2
cd frontend && npm run dev
```
No navegador: criar 2 contas diferentes, salvar um cupom em cada uma, confirmar que "Histórico" de cada conta só mostra o próprio cupom, e que "Preços" reflete dados de ambas as contas (catálogo compartilhado).

- [ ] **Step 6: Commit**

```bash
cd frontend
git add src/components/QrReader.tsx src/components/PriceConsultation.tsx src/components/ReceiptHistory.tsx
git commit -m "feat: usa apiFetch em todos os componentes — fecha o fluxo de autenticação"
```

---

### Task 10: Documentação

**Files:**
- Modify: `CLAUDE.md`
- Modify: `TASKS.md`
- Modify: `render.yaml`
- Create: `backend/.env.example`

**Interfaces:**
- Consumes: nada (documentação, roda por último).
- Produces: nada.

- [ ] **Step 1: Criar `backend/.env.example`**

```
MONGODB_URL=mongodb://localhost:27017
DB_NAME=comparador_precos
GROQ_API_KEY=
JWT_SECRET_KEY=
```

- [ ] **Step 2: Adicionar `JWT_SECRET_KEY` ao `render.yaml`**

Em `render.yaml` (raiz do repo, não `backend/render.yaml`), adicionar ao `envVars`:
```yaml
      - key: JWT_SECRET_KEY
        sync: false
```
(depois de `DB_NAME`; valor real é setado manualmente no dashboard do Render, nunca commitado.)

- [ ] **Step 3: Atualizar `CLAUDE.md`**

Na seção "Estrutura de pastas", adicionar as linhas novas na árvore de `backend/app/`:
- `models/user.py` (junto de `models/receipt.py`)
- `views/auth.py` (junto de `views/price.py`, `views/health.py`)
- `controllers/auth.py` (junto de `controllers/receipts.py`, `controllers/prices.py`)
- `repositories/users.py` (junto dos outros repositórios)
- `services/auth.py` (junto dos outros services)

E em `tests/`: `test_auth_service.py`, `test_repositories_users.py`, `test_auth_endpoint.py`.

Adicionar uma entrada nova em "Decisões arquiteturais":
```
- **Login multi-usuário (JWT)** — `receipts` privado por usuário (`user_id` = email,
  só no documento Mongo, nunca no schema `ReceiptData`); `products`/`prices` continuam
  globais/compartilhados. `access_key` continua globalmente único — ao detectar
  `DuplicateKeyError` de outro dono em `POST /receipts`, responde 409 sem devolver os
  dados do dono original (ver `app/controllers/receipts.py`). Token via header
  `Authorization: Bearer`, não cookie — evita mexer no `allow_credentials=False` do CORS.
```

- [ ] **Step 4: Adicionar entrada em `TASKS.md`**

Seguindo o formato das entradas existentes (ver Task 9 — Reorganização em camadas MVC), adicionar depois dela:
```
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
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md TASKS.md render.yaml backend/.env.example
git commit -m "docs: documenta o sistema de login multi-usuário"
```
