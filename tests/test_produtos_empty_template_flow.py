from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl import Workbook

from bling_app_zero.core.files import read_uploaded_file
from bling_app_zero.core.final_template_exporter import template_contract_columns
from bling_app_zero.ui.shared_mapping import encode_fixed_value
from bling_app_zero.universal.output_builder import build_universal_output


BASE_COLUMNS = [
    'ID',
    'Código',
    'Descrição',
    'Unidade',
    'NCM',
    'Origem',
    'Preço',
    'Estoque',
    'GTIN/EAN',
    'Marca',
    'Categoria do produto',
]
PRODUTOS_COLUMNS = BASE_COLUMNS + [f'Campo extra {index}' for index in range(1, 49)]


class UploadedBytes:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _xlsx_bytes(columns: list[str], blank_rows: int = 4) -> bytes:
    workbook = Workbook()
    ws = workbook.active
    ws.title = 'produtos'
    ws.append(columns)
    for _ in range(blank_rows):
        ws.append([''] * len(columns))
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _blank_workbook_bytes() -> bytes:
    workbook = Workbook()
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_produtos_xlsx_with_headers_and_no_products_is_valid_model() -> None:
    data = _xlsx_bytes(PRODUTOS_COLUMNS)

    model = read_uploaded_file(UploadedBytes('produtos.xlsx', data))

    assert model.empty
    assert model.columns.tolist() == PRODUTOS_COLUMNS
    assert len(model.columns) == 59


def test_template_contract_fallback_recovers_header_columns() -> None:
    data = _xlsx_bytes(PRODUTOS_COLUMNS)

    columns = template_contract_columns('produtos.xlsx', data)

    assert columns == PRODUTOS_COLUMNS


def test_empty_model_contract_can_be_filled_from_origin_rows() -> None:
    model = read_uploaded_file(UploadedBytes('produtos.xlsx', _xlsx_bytes(PRODUTOS_COLUMNS)))
    source = pd.DataFrame({'SKU origem': ['P001'], 'Nome origem': ['Caneca'], 'Valor origem': ['12.90']})
    mapping = {
        'Código': 'SKU origem',
        'Descrição': 'Nome origem',
        'Preço': 'Valor origem',
        'Marca': encode_fixed_value('Mega Center'),
    }

    output = build_universal_output(source, model, mapping)

    assert output.shape == (1, 59)
    assert output.loc[0, 'Código'] == 'P001'
    assert output.loc[0, 'Descrição'] == 'Caneca'
    assert output.loc[0, 'Preço'] == '12.90'
    assert output.loc[0, 'Marca'] == 'Mega Center'
    assert output.loc[0, 'ID'] == ''


def test_totally_blank_workbook_has_no_contract_columns() -> None:
    data = _blank_workbook_bytes()

    model = read_uploaded_file(UploadedBytes('vazio.xlsx', data))
    columns = template_contract_columns('vazio.xlsx', data)

    assert model.empty
    assert model.columns.tolist() == []
    assert columns == []
