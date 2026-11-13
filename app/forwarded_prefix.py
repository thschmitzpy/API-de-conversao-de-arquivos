import re

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

# Um ou mais segmentos simples ("/api", "/v1/api"). Barra no fim, "//host" ou
# qualquer outro caractere fazem o header ser ignorado.
_PREFIX_RE = re.compile(r"(/[A-Za-z0-9_-]+)+")


class ForwardedPrefixMiddleware:

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            prefix = Headers(scope=scope).get("x-forwarded-prefix", "")
            if _PREFIX_RE.fullmatch(prefix):
                scope = {**scope, "root_path": scope.get("root_path", "") + prefix}
        await self.app(scope, receive, send)
