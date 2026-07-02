"""Schema de resposta (view) do health check da Groq."""
from pydantic import BaseModel


class OllamaHealthResponse(BaseModel):
    status: str  # "ok" | "offline"
    url: str
    reason: str  # "ok" | "api_key_missing" | "http_error"
