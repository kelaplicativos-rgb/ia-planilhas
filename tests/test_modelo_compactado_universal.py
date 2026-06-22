from __future__ import annotations

from io import BytesIO
import zipfile

from bling_app_zero.core.modelo_compactado_universal import resolver_modelo


def _zip_com_csv() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as pacote:
        pacote.writestr('modelo.csv', 'Codigo;Nome\n1;Produto\n')
    return buffer.getvalue()


def test_resolve_modelo_csv_dentro_de_arquivo_compactado() -> None:
    modelo = resolver_modelo('modelo_cliente.zip', _zip_com_csv())
    assert modelo.nome_planilha == 'modelo.csv'
    assert modelo.extensao == '.csv'
    assert modelo.origem_compactada is True
    assert modelo.conteudo.decode('utf-8') == 'Codigo;Nome\n1;Produto\n'


def test_resolve_modelo_csv_direto() -> None:
    modelo = resolver_modelo('modelo.csv', b'Codigo;Nome\n')
    assert modelo.nome_planilha == 'modelo.csv'
    assert modelo.extensao == '.csv'
    assert modelo.origem_compactada is False
