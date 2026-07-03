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
        if len(v.encode("utf-8")) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Senha muito longa (máx. {MAX_PASSWORD_LENGTH} bytes)")
        return v


class LoginRequest(BaseModel):
    """Corpo de POST /auth/login."""
    email: EmailStr
    password: str
