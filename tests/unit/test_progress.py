from __future__ import annotations

from app.workers.progress import report_progress, reporting_progress


def test_sem_callback_nao_faz_nada():
    report_progress(0.5)


def test_callback_recebe_a_fracao():
    recebidas: list[float] = []
    with reporting_progress(recebidas.append):
        report_progress(0.25)
    assert recebidas == [0.25]


def test_fracao_limitada_entre_0_e_1():
    recebidas: list[float] = []
    with reporting_progress(recebidas.append):
        report_progress(-0.1)
        report_progress(1.7)
    assert recebidas == [0.0, 1.0]


def test_callback_sai_de_cena_ao_fim_do_bloco():
    recebidas: list[float] = []
    with reporting_progress(recebidas.append):
        pass
    report_progress(0.5)
    assert recebidas == []
