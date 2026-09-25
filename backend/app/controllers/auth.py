"""
Endpoints de autenticação e dependency de usuário autenticado.

POST /auth/signup — cria conta (público)
POST /auth/login  — autentica e retorna JWT (público)

get_current_user é usado via Depends() pelos demais controllers (receipts, prices)
para proteger seus endpoints.
"""
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from app.models.user import LoginRequest, SignupRequest
from app.controllers.dependencies import exigir_banco_pronto
from app.repositories.users import find_by_email, insert_user
from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password
from app.views.auth import TokenResponse

router = APIRouter()


@router.post("/auth/signup", response_model=TokenResponse, status_code=201)
async def signup(
    body: SignupRequest, request: Request, _: None = Depends(exigir_banco_pronto)
) -> TokenResponse:
    db = request.app.state.db
    email = body.email.lower()
    hashed = await hash_password(body.password)
    try:
        await insert_user(db, email, hashed, body.phone)
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
