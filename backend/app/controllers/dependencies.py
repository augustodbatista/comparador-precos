"""Dependências compartilhadas pelos controllers."""
from fastapi import HTTPException, Request
from pymongo.errors import PyMongoError

from app.repositories.connection import garantir_indices


async def exigir_banco_pronto(request: Request) -> None:
    """Bloqueia a gravação até o banco responder e ter os índices criados.

    Com o banco fora, responde 503 com mensagem clara em vez de um 500
    genérico -- e, principalmente, nunca grava sem os índices únicos.
    """
    try:
        await garantir_indices(request.app.state)
    except PyMongoError:
        raise HTTPException(
            status_code=503,
            detail="Banco de dados indisponível no momento. Tente de novo em instantes.",
        )
