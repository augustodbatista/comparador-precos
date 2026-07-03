"""
Modelos de entrada para autenticação (signup/login).
"""
import re

from pydantic import BaseModel, EmailStr, field_validator

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72  # bcrypt trunca silenciosamente acima disso — validamos em vez de deixar truncar


class SignupRequest(BaseModel):
    """Corpo de POST /auth/signup."""
    email: EmailStr
    password: str
    phone: str

    @field_validator("password")
    @classmethod
    def valida_tamanho_senha(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres")
        if len(v.encode("utf-8")) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Senha muito longa (máx. {MAX_PASSWORD_LENGTH} bytes)")
        return v

    @field_validator("phone")
    @classmethod
    def valida_telefone(cls, v: str) -> str:
        # Padrão BR: DDD (2) + número (8 fixo ou 9 celular) = 10 ou 11 dígitos.
        # Normaliza para só dígitos, ignorando máscara ((11) 91234-5678 etc.).
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10 or len(digits) > 11:
            raise ValueError("Telefone deve ter DDD + número (10 ou 11 dígitos)")
        return digits


class LoginRequest(BaseModel):
    """Corpo de POST /auth/login."""
    email: EmailStr
    password: str
