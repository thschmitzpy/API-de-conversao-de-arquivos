import socket

import pytest

from app.webhook import url_guard
from app.webhook.url_guard import UnsafeCallbackUrl, validate_callback_url


def _fake_dns(monkeypatch, *ips):
    def _getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", _getaddrinfo)


def test_url_publica_passa(monkeypatch):
    _fake_dns(monkeypatch, "93.184.215.14")
    validate_callback_url("https://cliente.example/webhook")


@pytest.mark.parametrize(
    "url",
    ["ftp://cliente.example/x", "file:///etc/passwd", "javascript:alert(1)"],
)
def test_esquema_nao_http_rejeitado(url):
    with pytest.raises(UnsafeCallbackUrl, match="http ou https"):
        validate_callback_url(url)


def test_url_sem_host_rejeitada():
    with pytest.raises(UnsafeCallbackUrl, match="sem host"):
        validate_callback_url("http:///webhook")


def test_credenciais_na_url_rejeitadas():
    with pytest.raises(UnsafeCallbackUrl, match="credenciais"):
        validate_callback_url("http://user:senha@cliente.example/")


def test_porta_invalida_rejeitada():
    with pytest.raises(UnsafeCallbackUrl, match="porta"):
        validate_callback_url("http://cliente.example:99999/")


def test_url_longa_demais_rejeitada():
    with pytest.raises(UnsafeCallbackUrl, match="excede"):
        validate_callback_url("https://cliente.example/" + "a" * 2048)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/",
        "http://localhost/",
        "http://2130706433/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.10/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
    ],
)
def test_ip_interno_rejeitado(url):
    with pytest.raises(UnsafeCallbackUrl, match="interno ou reservado"):
        validate_callback_url(url)


def test_dominio_que_resolve_para_ip_privado_rejeitado(monkeypatch):
    _fake_dns(monkeypatch, "10.96.0.15")
    with pytest.raises(UnsafeCallbackUrl, match="interno ou reservado"):
        validate_callback_url("https://parece-publico.example/")


def test_basta_um_ip_privado_entre_varios(monkeypatch):
    _fake_dns(monkeypatch, "93.184.215.14", "127.0.0.1")
    with pytest.raises(UnsafeCallbackUrl, match="interno ou reservado"):
        validate_callback_url("https://cliente.example/")


def test_host_que_nao_resolve_rejeitado(monkeypatch):
    def _falha(*_args, **_kwargs):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", _falha)
    with pytest.raises(UnsafeCallbackUrl, match="nao resolve"):
        validate_callback_url("https://nao-existe.invalid/")


def test_allow_private_libera_ip_interno():
    validate_callback_url("http://127.0.0.1:9999/hook", allow_private=True)


def test_allow_private_nao_libera_esquema_invalido():
    with pytest.raises(UnsafeCallbackUrl, match="http ou https"):
        validate_callback_url("file:///etc/passwd", allow_private=True)
