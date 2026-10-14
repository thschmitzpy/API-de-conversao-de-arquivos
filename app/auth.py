import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings

api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="ApiKeyAuth",
    description="Chave de acesso definida em API_KEYS no ambiente",
    auto_error=False,
)


def require_api_key(
    x_api_key: Annotated[str | None, Depends(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    allowed = settings.allowed_api_keys

    if not allowed:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "API_KEYS nao configurado no ambiente",
        )

    if x_api_key is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Header X-API-Key ausente",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    for allowed_key in allowed:
        if hmac.compare_digest(x_api_key, allowed_key):
            return

    raise HTTPException(status.HTTP_403_FORBIDDEN, "API key invalida")
