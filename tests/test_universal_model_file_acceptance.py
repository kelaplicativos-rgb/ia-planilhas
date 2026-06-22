from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl import Workbook

from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.ui.shared_mapping import encode_fixed_value
from bling_app_zero.universal.output_builder import build_universal_output


class UploadedBytes:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _xlsx_bytes_with_header_only() -> bytes:
    workbook = Workbook()
    ws = workbook.active
    ws.title = 'MODELO'
    ws.append(['Codigo Final', 'Nome Final', 'Loja'])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _xlsx_bytes_with_empty_sheet() -> bytes:
    workbook = Workbook()
    ws = workbook.active
    ws.title = 'VAZIO'
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_header_only_xlsx_model_is_accepted_as_contract() -> None:
    uploaded = UploadedBytes('modelo_header_only.xlsx', _xlsx_bytes_with_header_only())

    model = read_uploaded_file(uploaded)

    assert isinstance(model, pd.DataFrame)
    assert model.empty
    assert model.columns.tolist() == ['Codigo Final', 'Nome Final', 'Loja']


def test_header_only_model_can_be_filled_with_source_rows() -> None:
    model = read_uploaded_file(UploadedBytes('modelo_header_only.xlsx', _xlsx_bytes_with_header_only()))
    source = pd.DataFrame(
        {
            'SKU': ['P001', 'P002'],
            'Produto': ['Caneca', 'Mouse'],
        }
    )
    mapping = {
        'Codigo Final': 'SKU',
        'Nome Final': 'Produto',
        'Loja': encode_fixed_value('Mega Center'),
    }

    output = build_universal_output(source, model, mapping)

    assert output.shape == (2, 3)
    assert output.columns.tolist() == ['Codigo Final', 'Nome Final', 'Loja']
    assert output['Codigo Final'].tolist() == ['P001', 'P002']
    assert output['Nome Final'].tolist() == ['Caneca', 'Mouse']
    assert output['Loja'].tolist() == ['Mega Center', 'Mega Center']


def test_empty_xlsx_without_headers_is_not_a_valid_model_contract() -> None:
    uploaded = UploadedBytes('modelo_sem_cabecalho.xlsx', _xlsx_bytes_with_empty_sheet())

    model = read_uploaded_file(uploaded)

    assert isinstance(model, pd.DataFrame)
    assert model.empty
    assert model.columns.tolist() == []
