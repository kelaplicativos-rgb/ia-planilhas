from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO, StringIO
from typing import Any

import pandas as pd

from bling_app_zero.core.html_product_extractor import (
    clean_columns as _clean_html_columns,
    clean_text as _html_clean,
    decode_html_bytes,
    read_html_product_bytes,
    read_mhtml_product_bytes,
)

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None

SPREADSHEET_EXTENSIONS = ('.xlsx', '.xls', '.xlsm', '.xlsb')
TEXT_EXTENSIONS = ('.txt', '.tsv')
HTML_EXTENSIONS = ('.html', '.htm')
MHTML_EXTENSIONS = ('.mht', '.mhtml')
ZIP_EXTENSIONS = ('.zip',)
SUPPORTED_SUPPLIER_EXTENSIONS = SPREADSHEET_EXTENSIONS + ('.csv', '.xml', '.pdf') + TEXT_EXTENSIONS + HTML_EXTENSIONS + MHTML_EXTENSIONS + ZIP_EXTENSIONS

NFE_ITEM_TAGS = {'det'}
NFE_PRODUCT_TAGS = {'prod'}
COMMON_ITEM_TAGS = {'item', 'produto', 'product', 'det', 'row', 'linha'}


def _decode_bytes(data: bytes) -> str:
    return decode_html_bytes(data)


def _detect_separator(text: str) -> str:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        return dialect.delimiter
    except Exception:
        candidates = [',', ';', '\t', '|']
        return max(candidates, key=lambda sep: sample.count(sep))


def _clean(value: object) -> str:
    return _html_clean(value)


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    return _clean_html_columns(df)


def _best_frame(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Escolhe a melhor aba preservando planilhas modelo sem linhas.

    Modelos de importação do Bling normalmente vêm apenas com cabeçalho.
    O pandas lê esses arquivos como DataFrame vazio, mas com colunas válidas.
    Antes essa função descartava DataFrames vazios e fazia o upload do modelo
    parecer sem cabeçalho, bloqueando a próxima fase do wizard.
    """
    structured: list[pd.DataFrame] = []
    header_only: list[pd.DataFrame] = []

    for frame in frames:
        if not isinstance(frame, pd.DataFrame) or len(frame.columns) == 0:
            continue
        cleaned = _clean_columns(frame).fillna('').astype(str).reset_index(drop=True)
        if cleaned.empty:
            header_only.append(cleaned)
        else:
            structured.append(cleaned)

    if structured:
        structured.sort(key=lambda df: len(df) * max(1, len(df.columns)), reverse=True)
        return structured[0]

    if header_only:
        header_only.sort(key=lambda df: len(df.columns), reverse=True)
        return header_only[0]

    return pd.DataFrame()


def _read_csv_bytes(data: bytes) -> pd.DataFrame:
    text = _decode_bytes(data)
    sep = _detect_separator(text)
    return _clean_columns(pd.read_csv(StringIO(text), sep=sep, dtype=str).fillna(''))


def _read_text_bytes(data: bytes) -> pd.DataFrame:
    text = _decode_bytes(data)
    if '\t' in text[:8192]:
        return _clean_columns(pd.read_csv(StringIO(text), sep='\t', dtype=str).fillna(''))
    rows = [[_clean(part) for part in re.split(r'\s{2,}|;|\|', line) if _clean(part)] for line in text.splitlines() if _clean(line)]
    rows = [row for row in rows if row]
    if len(rows) < 2:
        return pd.DataFrame([{'Arquivo TXT': 'texto', 'Conteúdo': text[:20000]}]) if text.strip() else pd.DataFrame()
    width = max(len(row) for row in rows)
    normalized = [row + [''] * (width - len(row)) for row in rows]
    columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(normalized[0])]
    return _clean_columns(pd.DataFrame(normalized[1:], columns=columns))


def _read_excel_bytes(data: bytes, file_name: str) -> pd.DataFrame:
    buffer = BytesIO(data)
    try:
        sheets = pd.read_excel(buffer, sheet_name=None, dtype=str).values()
        return _best_frame([sheet.fillna('') for sheet in sheets])
    except Exception:
        buffer.seek(0)
        df = pd.read_excel(buffer, dtype=str).fillna('')
        return _clean_columns(df)


def _read_html_bytes(data: bytes) -> pd.DataFrame:
    """Leitor universal de HTML.

    A saída fica mais rica para o mapeamento, mas o download continua fiel ao
    modelo anexado na primeira etapa. Este leitor apenas cria aliases úteis
    como Descrição Produto/Título/Nome/Produto para aumentar a chance de
    preencher campos de nome quando o fornecedor usa tabelas ou cards.
    """
    return read_html_product_bytes(data)


def _read_mhtml_bytes(data: bytes) -> pd.DataFrame:
    """Leitor universal de MHTML/MHT.

    Usa o extrator modular para encontrar tabelas, cards e títulos salvos no
    arquivo do navegador, sem distinguir estoque/cadastro. A distinção continua
    sendo exclusivamente o contrato/modelo anexado pelo usuário.
    """
    return read_mhtml_product_bytes(data)


def _xml_tag_name(tag: str) -> str:
    return str(tag or '').split('}', 1)[-1].strip()


def _xml_child_texts(element: ET.Element, prefix: str = '') -> dict[str, str]:
    data: dict[str, str] = {}
    for child in list(element):
        name = _xml_tag_name(child.tag)
        key = f'{prefix}{name}' if not prefix else f'{prefix}.{name}'
        children = list(child)
        text = _clean(child.text)
        if children:
            data.update(_xml_child_texts(child, key))
        elif text:
            data[key] = text
        for attr, value in child.attrib.items():
            data[f'{key}@{attr}'] = _clean(value)
    return data


def _nfe_item_to_row(det: ET.Element) -> dict[str, str]:
    row: dict[str, str] = {}
    n_item = det.attrib.get('nItem')
    if n_item:
        row['nItem'] = _clean(n_item)
    for child in list(det):
        child_name = _xml_tag_name(child.tag)
        if child_name in NFE_PRODUCT_TAGS:
            for product_child in list(child):
                row[_xml_tag_name(product_child.tag)] = _clean(product_child.text)
        else:
            row.update(_xml_child_texts(child, child_name))
    return row


def _read_xml_bytes(data: bytes, file_name: str = 'xml') -> pd.DataFrame:
    text = _decode_bytes(data)
    try:
        root = ET.fromstring(text.encode('utf-8'))
    except Exception:
        try:
            root = ET.fromstring(text)
        except Exception:
            return pd.DataFrame([{'Arquivo XML': file_name, 'Conteúdo XML': text[:50000]}])

    rows: list[dict[str, str]] = []
    for element in root.iter():
        name = _xml_tag_name(element.tag).lower()
        if name in NFE_ITEM_TAGS:
            row = _nfe_item_to_row(element)
            if row:
                rows.append(row)

    if not rows:
        for element in root.iter():
            name = _xml_tag_name(element.tag).lower()
            if name in COMMON_ITEM_TAGS:
                row = _xml_child_texts(element)
                if len(row) >= 2:
                    rows.append(row)

    if not rows:
        flat = _xml_child_texts(root)
        if flat:
            rows.append(flat)

    if not rows:
        return pd.DataFrame([{'Arquivo XML': file_name, 'Conteúdo XML': text[:50000]}])

    return _clean_columns(pd.DataFrame(rows).fillna(''))


def _split_pdf_table_line(line: str) -> list[str]:
    clean = _clean(line)
    if not clean:
        return []
    parts = [part.strip() for part in re.split(r'\s{2,}|\t|;|\|', clean) if part.strip()]
    return parts


def _read_pdf_bytes(data: bytes, file_name: str = 'pdf') -> pd.DataFrame:
    if PdfReader is None:
        return pd.DataFrame([{'Arquivo PDF': file_name, 'Status': 'Leitor de PDF indisponível no ambiente.'}])

    try:
        reader = PdfReader(BytesIO(data))
        page_texts = [page.extract_text() or '' for page in reader.pages]
        text = '\n'.join(page_texts)
    except Exception as exc:
        return pd.DataFrame([{'Arquivo PDF': file_name, 'Status': f'Não foi possível ler o PDF: {exc}'}])

    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    table_rows = [_split_pdf_table_line(line) for line in lines]
    table_rows = [row for row in table_rows if len(row) >= 2]

    if len(table_rows) >= 2:
        width = max(len(row) for row in table_rows)
        normalized = [row + [''] * (width - len(row)) for row in table_rows]
        header_index = 0
        for idx, row in enumerate(normalized[:10]):
            row_text = ' '.join(row).lower()
            if any(term in row_text for term in ('codigo', 'código', 'sku', 'produto', 'descricao', 'descrição', 'preco', 'preço', 'qtde', 'quantidade')):
                header_index = idx
                break
        columns = [_clean(value) or f'Coluna {idx + 1}' for idx, value in enumerate(normalized[header_index])]
        data_rows = normalized[header_index + 1 :]
        if data_rows:
            return _clean_columns(pd.DataFrame(data_rows, columns=columns))

    if text.strip():
        return pd.DataFrame([{'Arquivo PDF': file_name, 'Texto extraído': text[:50000]}])
    return pd.DataFrame([{'Arquivo PDF': file_name, 'Status': 'PDF sem texto extraível. Pode ser imagem/scan.'}])


def _read_inner_file_bytes(data: bytes, file_name: str) -> pd.DataFrame:
    lower = str(file_name or '').lower()
    if lower.endswith('.csv'):
        return _read_csv_bytes(data)
    if lower.endswith(TEXT_EXTENSIONS):
        return _read_text_bytes(data)
    if lower.endswith(SPREADSHEET_EXTENSIONS):
        return _read_excel_bytes(data, file_name)
    if lower.endswith(HTML_EXTENSIONS):
        return _read_html_bytes(data)
    if lower.endswith(MHTML_EXTENSIONS):
        return _read_mhtml_bytes(data)
    if lower.endswith('.xml'):
        return _read_xml_bytes(data, file_name)
    return pd.DataFrame()


def _read_zip_bytes(data: bytes, file_name: str = 'arquivo.zip') -> pd.DataFrame:
    """Lê ZIP exportado pelo Bling quando ele contém CSV/XLSX interno.

    O importador/modelo do Bling pode baixar arquivos compactados, como o
    modelo de preços multiloja. O sistema precisa abrir o ZIP e usar a planilha
    interna como contrato final, em vez de descartar o arquivo pelo `.zip`.
    """
    frames: list[pd.DataFrame] = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                inner_name = str(info.filename or '')
                lower = inner_name.lower()
                if not lower.endswith(('.csv', '.xlsx', '.xls', '.xlsm', '.xlsb', '.txt', '.tsv', '.html', '.htm', '.mht', '.mhtml', '.xml')):
                    continue
                try:
                    frame = _read_inner_file_bytes(archive.read(info), inner_name)
                except Exception:
                    frame = pd.DataFrame()
                if isinstance(frame, pd.DataFrame) and len(frame.columns) > 0:
                    frames.append(frame)
    except Exception:
        return pd.DataFrame()
    return _best_frame(frames)


def read_uploaded_file(uploaded_file: Any) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    name_original = str(getattr(uploaded_file, 'name', '') or 'arquivo')
    name = name_original.lower()
    data = uploaded_file.getvalue()

    if name.endswith('.csv'):
        return _read_csv_bytes(data)
    if name.endswith(TEXT_EXTENSIONS):
        return _read_text_bytes(data)
    if name.endswith(SPREADSHEET_EXTENSIONS):
        return _read_excel_bytes(data, name_original)
    if name.endswith(HTML_EXTENSIONS):
        return _read_html_bytes(data)
    if name.endswith(MHTML_EXTENSIONS):
        return _read_mhtml_bytes(data)
    if name.endswith('.xml'):
        return _read_xml_bytes(data, name_original)
    if name.endswith('.pdf'):
        return _read_pdf_bytes(data, name_original)
    if name.endswith(ZIP_EXTENSIONS):
        return _read_zip_bytes(data, name_original)
    return pd.DataFrame()


def ensure_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy().fillna('')
    return pd.DataFrame()


__all__ = [
    'SUPPORTED_SUPPLIER_EXTENSIONS',
    'ensure_dataframe',
    'read_uploaded_file',
]
