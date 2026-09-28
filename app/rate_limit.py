from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_settings.rate_limit_storage_url,
    enabled=_settings.rate_limit_enabled,
    strategy="moving-window",
    headers_enabled=True,
)
