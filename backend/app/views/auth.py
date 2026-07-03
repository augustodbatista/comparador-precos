"""Schema de resposta (view) da autenticação."""
from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Resposta de signup/login — o frontend guarda access_token e email, sem decodificar o JWT."""
    access_token: str
    token_type: str = "bearer"
    email: str
