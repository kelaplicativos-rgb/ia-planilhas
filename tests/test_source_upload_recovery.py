from __future__ import annotations

import zipfile
from dataclasses import dataclass
from io import BytesIO

import pandas as pd

from bling_app_zero.core.source_upload_recovery import recover_uploaded_source_file


@dataclass
class UploadBytes:
    name: str
    data: bytes

    def getvalue(self) -> bytes:
        return self.data


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_recover_uploaded_source_file_does_not_turn_invalid_binary_pdf_in_zip_into_manifest_table() -> None:
    uploaded = UploadBytes('origem.zip', _zip_bytes({'pedido.pdf': b'not a real pdf'}))

    df = recover_uploaded_source_file(uploaded)

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(df.columns) == 0


def test_recover_uploaded_source_file_does_not_turn_broken_xlsx_into_status_table() -> None:
    uploaded = UploadBytes('produtos.xlsx', b'not a real xlsx binary \x00\x00\x00')

    df = recover_uploaded_source_file(uploaded)

    assert isinstance(df, pd.DataFrame)
    assert df.empty
    assert len(df.columns) == 0


def test_recover_uploaded_source_file_reads_nested_zip_csv() -> None:
    inner = _zip_bytes({'produtos.csv': 'SKU;Nome;Preço\nP001;Fone;10,00\n'.encode('utf-8')})
    uploaded = UploadBytes('origem.zip', _zip_bytes({'pasta/dados.zip': inner}))

    df = recover_uploaded_source_file(uploaded)

    assert isinstance(df, pd.DataFrame)
    assert df.columns.tolist() == ['SKU', 'Nome', 'Preço']
    assert df.loc[0, 'SKU'] == 'P001'


def test_recover_uploaded_source_file_turns_unknown_text_into_columns() -> None:
    uploaded = UploadBytes('fornecedor.dat', b'SKU;Nome;Estoque\nP002;Cabo USB;7\n')

    df = recover_uploaded_source_file(uploaded)

    assert isinstance(df, pd.DataFrame)
    assert df.columns.tolist() == ['SKU', 'Nome', 'Estoque']
    assert df.loc[0, 'Nome'] == 'Cabo USB'
