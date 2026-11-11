from app.workers.tasks import (
    GENERIC_ERROR_MESSAGE,
    MAX_ERROR_MESSAGE_LENGTH,
    _public_error_message,
)


def test_value_error_mantem_mensagem_sem_prefixo_da_classe():
    exc = ValueError("crf invalido: '99' (use inteiro entre 18 e 28)")
    assert _public_error_message(exc) == "crf invalido: '99' (use inteiro entre 18 e 28)"


def test_caminho_absoluto_e_substituido():
    exc = ValueError(
        "ffmpeg falhou: /tmp/video-transcode-abc123/input: Invalid data found"
    )
    assert _public_error_message(exc) == (
        "ffmpeg falhou: <arquivo>: Invalid data found"
    )


def test_barra_entre_palavras_nao_e_tratada_como_caminho():
    exc = ValueError("entrada nao e PDF nem imagem suportada (PNG/JPEG/GIF/WEBP)")
    assert _public_error_message(exc) == str(exc)


def test_excecao_que_nao_e_value_error_vira_generica():
    exc = OSError("HTTPConnectionPool(host='minio', port=9000): Max retries exceeded")
    assert _public_error_message(exc) == GENERIC_ERROR_MESSAGE


def test_value_error_vazio_vira_generica():
    assert _public_error_message(ValueError("")) == GENERIC_ERROR_MESSAGE


def test_mensagem_longa_e_cortada():
    message = _public_error_message(ValueError("x" * 1000))
    assert len(message) == MAX_ERROR_MESSAGE_LENGTH
    assert message.endswith("...")
