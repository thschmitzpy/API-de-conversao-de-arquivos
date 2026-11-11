import ipaddress
import socket
from urllib.parse import urlsplit

MAX_CALLBACK_URL_LENGTH = 2048


class UnsafeCallbackUrl(ValueError):
    pass


def _is_public(raw_ip: str) -> bool:
    ip = ipaddress.ip_address(raw_ip.split("%", 1)[0])
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


def validate_callback_url(url: str, *, allow_private: bool = False) -> None:
    if len(url) > MAX_CALLBACK_URL_LENGTH:
        raise UnsafeCallbackUrl(
            f"callback_url excede {MAX_CALLBACK_URL_LENGTH} caracteres"
        )

    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeCallbackUrl("callback_url deve usar http ou https")
    if not parts.hostname:
        raise UnsafeCallbackUrl("callback_url sem host")
    if parts.username or parts.password:
        raise UnsafeCallbackUrl("callback_url nao pode conter credenciais")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeCallbackUrl("callback_url com porta invalida") from exc

    if allow_private:
        return

    try:
        infos = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeCallbackUrl("host do callback_url nao resolve") from exc

    # Todos os IPs precisam ser publicos: o cliente HTTP pode escolher qualquer um.
    if not all(_is_public(info[4][0]) for info in infos):
        raise UnsafeCallbackUrl(
            "callback_url aponta para endereco interno ou reservado"

        )
