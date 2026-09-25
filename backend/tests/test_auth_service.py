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
        # Adultera o PRIMEIRO caractere da assinatura, não o último. Em base64url,
        # o último caractere de uma assinatura de 32 bytes carrega só 4 bits de
        # dado: trocar A/B/C/D entre si mexe apenas nos 2 bits descartados, e a
        # assinatura continua válida. Isso fazia o teste falhar em ~6% das
        # execuções (4 de 64 tokens). O primeiro caractere carrega 6 bits inteiros.
        header, payload, assinatura = token.split(".")
        trocado = "A" if assinatura[0] != "A" else "B"
        adulterado = f"{header}.{payload}.{trocado}{assinatura[1:]}"
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
