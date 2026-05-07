from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import preview_df, read_upload_fast

SUPPORTED_TYPES = ['xlsx', 'xls', 'csv', 'xml', 'pdf']
MODEL_HINTS = ['modelo', 'bling', 'cadastro', 'estoque', 'layout', 'importacao', 'importação']
SOURCE_HINTS = ['origem', 'fornecedor', 'produtos', 'produto', 'lista', 'base', 'catalogo', 'catálogo', 'xml', 'pdf']


@dataclass
class SmartUploadResult:
    source_file: Any | None = None
    source_df: pd.DataFrame | None = None
    model_file: Any | None = None
    model_df: pd.DataFrame | None = None
    attachments: list[Any] | None = None


def _file_name(file: Any) -> str:
    return str(getattr(file, 'name', 'arquivo')).strip()


def _file_ext(file: Any) -> str:
    name = _file_name(file).lower()
    return name.rsplit('.', 1)[-1] if '.' in name else ''


def _safe_read(file: Any) -> pd.DataFrame | None:
    try:
        return read_upload_fast(file)
    except Exception as exc:
        st.warning(f'Não consegui ler { _file_name(file) }: {exc}')
        return None


def _score_model(file: Any, df: pd.DataFrame | None, operation: str) -> int:
    name = _file_name(file).lower()
    columns = ' '.join(map(str, df.columns)).lower() if isinstance(df, pd.DataFrame) else ''
    score = 0

    if any(hint in name for hint in MODEL_HINTS):
        score += 40
    if operation in name:
        score += 40
    if 'obrigat' in columns:
        score += 30
    if 'bling' in name or 'bling' in columns:
        score += 25
    if operation == 'estoque' and any(term in columns for term in ['depósito', 'deposito', 'balanço', 'balanco', 'estoque']):
        score += 40
    if operation == 'cadastro' and any(term in columns for term in ['gtin', 'ean', 'preço', 'preco', 'descrição', 'descricao', 'ncm']):
        score += 25
    if _file_ext(file) in ['xml', 'pdf']:
        score -= 80
    return score


def _score_source(file: Any, df: pd.DataFrame | None, operation: str) -> int:
    name = _file_name(file).lower()
    columns = ' '.join(map(str, df.columns)).lower() if isinstance(df, pd.DataFrame) else ''
    score = 0

    if any(hint in name for hint in SOURCE_HINTS):
        score += 35
    if _file_ext(file) in ['xml', 'pdf']:
        score += 80
    if operation == 'estoque' and any(term in columns for term in ['quantidade', 'saldo', 'estoque', 'sku', 'codigo', 'código']):
        score += 25
    if operation == 'cadastro' and any(term in columns for term in ['produto', 'nome', 'descricao', 'descrição', 'preco', 'preço']):
        score += 25
    if any(hint in name for hint in MODEL_HINTS):
        score -= 30
    return score


def _classify(files: list[Any], operation: str, allow_model: bool) -> SmartUploadResult:
    loaded: list[tuple[Any, pd.DataFrame | None]] = [(file, _safe_read(file)) for file in files]
    if not loaded:
        return SmartUploadResult(attachments=[])

    source_file = None
    source_df = None
    model_file = None
    model_df = None

    if allow_model:
        model_file, model_df = max(loaded, key=lambda item: _score_model(item[0], item[1], operation))

    source_candidates = [item for item in loaded if item[0] is not model_file]
    if not source_candidates and loaded:
        source_candidates = loaded

    source_file, source_df = max(source_candidates, key=lambda item: _score_source(item[0], item[1], operation))

    return SmartUploadResult(
        source_file=source_file,
        source_df=source_df,
        model_file=model_file if model_file is not source_file else None,
        model_df=model_df if model_file is not source_file else None,
        attachments=files,
    )


def render_smart_upload_box(
    title: str,
    operation: str,
    key: str,
    allow_model: bool = True,
    required_model: bool = False,
    accepted_types: list[str] | None = None,
) -> SmartUploadResult:
    st.markdown(f'#### {title}')
    st.caption('Anexe aqui como no WhatsApp: pode soltar a origem e o modelo juntos. O sistema reconhece automaticamente.')

    files = st.file_uploader(
        '📎 Anexar planilhas, XML ou PDF',
        type=accepted_types or SUPPORTED_TYPES,
        accept_multiple_files=True,
        key=key,
        help='Pode anexar mais de um arquivo de uma vez. O sistema identifica origem e modelo pelo nome e pelas colunas.',
    )

    if not files:
        st.info('Nenhum arquivo anexado ainda. Clique no clipe ou arraste os arquivos para cá.')
        return SmartUploadResult(attachments=[])

    result = _classify(list(files), operation=operation, allow_model=allow_model)

    st.success(f'{len(files)} arquivo(s) anexado(s).')
    cards = st.columns(min(len(files), 3))
    for index, file in enumerate(files):
        with cards[index % len(cards)]:
            role = 'Origem'
            if result.model_file is file:
                role = 'Modelo Bling'
            st.info(f'📎 {role}\n\n{_file_name(file)}')

    if result.source_df is not None:
        preview_df('Preview automático da origem detectada', result.source_df)
    elif result.source_file is not None:
        st.warning(f'Origem detectada, mas ainda sem preview tabular: {_file_name(result.source_file)}')

    if allow_model:
        if result.model_df is not None:
            with st.expander('Modelo Bling detectado', expanded=False):
                preview_df('Preview do modelo detectado', result.model_df)
        elif required_model:
            st.warning('Modelo Bling ainda não detectado. Anexe o modelo junto da origem.')

    return result
