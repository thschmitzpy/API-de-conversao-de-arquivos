from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.workers.processors.excel_to_csv import to_csv


def _make_xlsx(sheets: dict[str, list[list]] | None = None) -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    data = sheets or {"Sheet1": [["a", "b"], [1, 2], [3, 4]]}
    for name, rows in data.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _read_csv(result, encoding: str = "utf-8") -> str:
    return result.output.getvalue().decode(encoding)


def test_converte_planilha_simples_com_header():
    result = to_csv(_make_xlsx(), {})

    assert _read_csv(result) == "a,b\n1,2\n3,4\n"


def test_include_header_false_pula_primeira_linha():
    result = to_csv(_make_xlsx(), {"include_header": False})

    assert _read_csv(result) == "1,2\n3,4\n"


def test_delimiter_customizado():
    result = to_csv(_make_xlsx(), {"delimiter": ";"})

    assert _read_csv(result) == "a;b\n1;2\n3;4\n"


def test_encoding_latin1_preserva_acentos():
    xlsx = _make_xlsx({"Sheet1": [["nome"], ["ção"]]})

    result = to_csv(xlsx, {"encoding": "latin-1"})

    assert _read_csv(result, encoding="latin-1") == "nome\nção\n"
    assert "charset=latin-1" in result.output_content_type


def test_sheet_por_nome_selecionada():
    xlsx = _make_xlsx({"Primeira": [["x"], [1]], "Segunda": [["y"], [2]]})

    result = to_csv(xlsx, {"sheet": "Segunda"})

    assert _read_csv(result) == "y\n2\n"
    assert result.result_metadata["sheet_name"] == "Segunda"


def test_sheet_por_indice_selecionada():
    xlsx = _make_xlsx({"Primeira": [["x"], [1]], "Segunda": [["y"], [2]]})

    result = to_csv(xlsx, {"sheet": 1})

    assert result.result_metadata["sheet_name"] == "Segunda"


def test_sheet_default_e_a_primeira():
    xlsx = _make_xlsx({"Primeira": [["x"], [1]], "Segunda": [["y"], [2]]})

    result = to_csv(xlsx, {})

    assert result.result_metadata["sheet_name"] == "Primeira"


def test_datetime_normalizado_para_isoformat():
    xlsx = _make_xlsx({"Sheet1": [["ts"], [datetime(2026, 1, 15, 10, 30, 45)]]})

    result = to_csv(xlsx, {})

    assert "2026-01-15T10:30:45" in _read_csv(result)


def test_date_e_time_normalizados_para_isoformat():
    xlsx = _make_xlsx({"Sheet1": [["d", "t"], [date(2026, 3, 20), time(9, 15)]]})

    result = to_csv(xlsx, {})
    body = _read_csv(result)

    assert "2026-03-20" in body
    assert "09:15:00" in body


def test_celula_none_vira_string_vazia():
    xlsx = _make_xlsx({"Sheet1": [["a", "b"], [1, None]]})

    result = to_csv(xlsx, {})

    assert _read_csv(result) == "a,b\n1,\n"


def test_metadata_reflete_planilha():
    result = to_csv(_make_xlsx(), {})

    meta = result.result_metadata
    assert meta["sheet_name"] == "Sheet1"
    assert meta["rows_written"] == 2
    assert meta["columns"] == 2
    assert meta["encoding"] == "utf-8"
    assert meta["delimiter"] == ","


def test_rows_written_igual_com_e_sem_header():
    com = to_csv(_make_xlsx(), {"include_header": True})
    sem = to_csv(_make_xlsx(), {"include_header": False})

    assert com.result_metadata["rows_written"] == 2
    assert sem.result_metadata["rows_written"] == 2


def test_extensao_e_content_type_de_saida():
    result = to_csv(_make_xlsx(), {})

    assert result.output_extension == "csv"
    assert result.output_content_type == "text/csv; charset=utf-8"


def test_delimiter_com_mais_de_um_char_raises():
    with pytest.raises(ValueError, match="delimiter"):
        to_csv(_make_xlsx(), {"delimiter": ";;"})


def test_delimiter_nao_string_raises():
    with pytest.raises(ValueError, match="delimiter"):
        to_csv(_make_xlsx(), {"delimiter": 1})


def test_encoding_invalido_raises():
    with pytest.raises(ValueError, match="encoding"):
        to_csv(_make_xlsx(), {"encoding": "nao-existe-encoding"})


def test_arquivo_invalido_raises():
    with pytest.raises(ValueError, match="Excel"):
        to_csv(BytesIO(b"nao sou um xlsx"), {})


def test_sheet_por_indice_fora_do_range_raises():
    with pytest.raises(ValueError, match="fora do intervalo"):
        to_csv(_make_xlsx(), {"sheet": 5})


def test_sheet_por_nome_inexistente_raises():
    with pytest.raises(ValueError, match="nao encontrada"):
        to_csv(_make_xlsx(), {"sheet": "Inexistente"})


def test_sheet_como_bool_raises():
    with pytest.raises(ValueError, match="sheet"):
        to_csv(_make_xlsx(), {"sheet": True})


def test_sheet_como_tipo_invalido_raises():
    with pytest.raises(ValueError, match="sheet"):
        to_csv(_make_xlsx(), {"sheet": [0]})
