from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import preview_df, read_upload_fast

SUPPORTED_TYPES = ['xlsx', 'xls', 'csv', 'xml', 'pdf', 'xlsm', 'xlsb', 'txt']
MODEL_HINTS = ['modelo', 'bling', 'cadastro', 'estoque', 'layout', 'importacao', 'importação']
SOURCE_HINTS = ['origem', 'fornecedor', 'produtos', 'produto', 'lista', 'base', 'catalogo', 'catálogo', 'xml', 'pdf', 'export']


@dataclass
class SmartUploadResult:
    source_file: Any | None = None
    source_df: pd.DataFrame | None = None
    model_file: Any | None = None
    model_df: pd.DataFrame | None = None
    cadastro_model_file: Any | None = None
    cadastro_model_df: pd.DataFrame | None = None
    estoque_model_file: Any | None = None
    estoque_model_df: pd.DataFrame | None = None
    attachments: list[Any] | None = None
    ignored_files: list[Any] | None = None


def _file_name(file: Any) -> str:
    return str(getattr(file, 'name', 'arquivo')).strip()


def _file_ext(file: Any) -> str:
    name = _file_name(file).lower()
    return name.rsplit('.', 1)[-1] if '.' in name else ''


def _normalize_types(accepted_types: list[str] | None) -> list[str]:
    values = accepted_types or SUPPORTED_TYPES
    return [str(value).lower().lstrip('.') for value in values]


def _split_supported_files(files: list[Any], accepted_types: list[str] | None) -> tuple[list[Any], list[Any]]:
    allowed = set(_normalize_types(accepted_types))
    supported: list[Any] = []
    ignored: list[Any] = []
    for file in files:
        if _file_ext(file) in allowed:
            supported.append(file)
        else:
            ignored.append(file)
    return supported, ignored


def _safe_read(file: Any) -> pd.DataFrame | None:
    try:
        return read_upload_fast(file)
    except Exception as exc:
        st.warning(f'Não consegui ler {_file_name(file)}: {exc}')
        return None


def _column_text(df: pd.DataFrame | None) -> str:
    return ' '.join(map(str, df.columns)).lower() if isinstance(df, pd.DataFrame) else ''


def _score_cadastro_model(file: Any, df: pd.DataFrame | None) -> int:
    name = _file_name(file).lower()
    columns = _column_text(df)
    score = 0
    if any(hint in name for hint in MODEL_HINTS):
        score += 25
    if 'cadastro' in name or 'produto' in name:
        score += 50
    if 'bling' in name or 'bling' in columns:
        score += 20
    if 'obrigat' in columns:
        score += 20
    if any(term in columns for term in ['gtin', 'ean', 'preço', 'preco', 'descrição', 'descricao', 'ncm', 'marca', 'categoria']):
        score += 45
    if any(term in columns for term in ['depósito', 'deposito', 'balanço', 'balanco']):
        score -= 40
    if _file_ext(file) in ['xml', 'pdf']:
        score -= 80
    return score


def _score_estoque_model(file: Any, df: pd.DataFrame | None) -> int:
    name = _file_name(file).lower()
    columns = _column_text(df)
    score = 0
    if any(hint in name for hint in MODEL_HINTS):
        score += 25
    if 'estoque' in name:
        score += 60
    if 'bling' in name or 'bling' in columns:
        score += 20
    if 'obrigat' in columns:
        score += 20
    if any(term in columns for term in ['depósito', 'deposito', 'balanço', 'balanco', 'estoque']):
        score += 60
    if any(term in columns for term in ['gtin', 'ean', 'ncm', 'marca', 'categoria']):
        score -= 25
    if _file_ext(file) in ['xml', 'pdf']:
        score -= 80
    return score


def _score_source(file: Any, df: pd.DataFrame | None, operation: str) -> int:
    name = _file_name(file).lower()
    columns = _column_text(df)
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
    if _score_cadastro_model(file, df) >= 80 or _score_estoque_model(file, df) >= 80:
        score -= 80
    return score


def _pick_best_candidate(loaded: list[tuple[Any, pd.DataFrame | None]], scorer) -> tuple[Any | None, pd.DataFrame | None, int]:
    if not loaded:
        return None, None, 0
    file, df = max(loaded, key=lambda item: scorer(item[0], item[1]))
    return file, df, int(scorer(file, df))


def _is_same_file(left: Any, right: Any) -> bool:
    return left is right


def _is_any_same_file(file: Any, candidates: list[Any]) -> bool:
    return any(_is_same_file(file, candidate) for candidate in candidates if candidate is not None)


def _classify(files: list[Any], operation: str, allow_model: bool, ignored_files: list[Any] | None = None) -> SmartUploadResult:
    loaded: list[tuple[Any, pd.DataFrame | None]] = [(file, _safe_read(file)) for file in files]
    if not loaded:
        return SmartUploadResult(attachments=files, ignored_files=ignored_files or [])

    cadastro_file = cadastro_df = estoque_file = estoque_df = None
    cadastro_score = estoque_score = 0

    if allow_model:
        cadastro_file, cadastro_df, cadastro_score = _pick_best_candidate(loaded, _score_cadastro_model)
        estoque_candidates = [item for item in loaded if item[0] is not cadastro_file]
        estoque_file, estoque_df, estoque_score = _pick_best_candidate(estoque_candidates or loaded, _score_estoque_model)

        if cadastro_score < 45:
            cadastro_file, cadastro_df = None, None
        if estoque_score < 45:
            estoque_file, estoque_df = None, None

    model_files = [file for file in [cadastro_file, estoque_file] if file is not None]
    source_candidates = [item for item in loaded if not _is_any_same_file(item[0], model_files)]
    if not source_candidates:
        source_candidates = loaded

    source_file, source_df = max(source_candidates, key=lambda item: _score_source(item[0], item[1], operation))

    if operation == 'estoque':
        model_file, model_df = estoque_file, estoque_df
    else:
        model_file, model_df = cadastro_file, cadastro_df

    return SmartUploadResult(
        source_file=source_file,
        source_df=source_df,
        model_file=model_file,
        model_df=model_df,
        cadastro_model_file=cadastro_file,
        cadastro_model_df=cadastro_df,
        estoque_model_file=estoque_file,
        estoque_model_df=estoque_df,
        attachments=files,
        ignored_files=ignored_files or [],
    )


def _render_upload_header(title: str) -> None:
    clean_title = str(title).replace('📎', '').strip()
    st.markdown(f'<div class="bling-upload-title">📎 {clean_title}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="bling-upload-caption">Envie a planilha, PDF ou XML do fornecedor. Se tiver modelos do Bling, envie junto.</div>',
        unsafe_allow_html=True,
    )


def _render_detected_files(result: SmartUploadResult, supported_files: list[Any]) -> None:
    st.success(f'{len(supported_files)} arquivo(s) recebido(s).')
    with st.expander('Ver arquivos detectados', expanded=False):
        for file in supported_files:
            role = 'Origem do fornecedor'
            if result.cadastro_model_file is file:
                role = 'Modelo de cadastro Bling'
            elif result.estoque_model_file is file:
                role = 'Modelo de estoque Bling'
            st.write(f'**{role}:** {_file_name(file)}')


def render_smart_upload_box(
    title: str,
    operation: str,
    key: str,
    allow_model: bool = True,
    required_model: bool = False,
    accepted_types: list[str] | None = None,
) -> SmartUploadResult:
    _render_upload_header(title)

    files = st.file_uploader(
        'Enviar arquivos do fornecedor',
        type=None,
        accept_multiple_files=True,
        key=key,
        help='Envie planilha, PDF, XML e modelos do Bling quando tiver.',
        label_visibility='collapsed',
    )

    if not files:
        return SmartUploadResult(attachments=[], ignored_files=[])

    selected_files = list(files)
    supported_files, ignored_files = _split_supported_files(selected_files, accepted_types)

    if ignored_files:
        st.warning('Ignorado: ' + ', '.join(_file_name(file) for file in ignored_files))

    if not supported_files:
        st.error('Nenhum arquivo compatível.')
        return SmartUploadResult(attachments=[], ignored_files=ignored_files)

    result = _classify(supported_files, operation=operation, allow_model=allow_model, ignored_files=ignored_files)
    _render_detected_files(result, supported_files)

    if result.source_df is not None:
        with st.expander('Ver origem detectada', expanded=False):
            preview_df('Origem detectada', result.source_df)
    elif result.source_file is not None:
        st.warning(f'Arquivo recebido, mas ainda sem tabela detectada: {_file_name(result.source_file)}')

    if allow_model:
        if result.cadastro_model_df is not None:
            with st.expander('Ver modelo de cadastro', expanded=False):
                preview_df('Modelo de cadastro', result.cadastro_model_df)
        if result.estoque_model_df is not None:
            with st.expander('Ver modelo de estoque', expanded=False):
                preview_df('Modelo de estoque', result.estoque_model_df)
        if required_model and result.model_df is None:
            st.warning('Modelo Bling ainda não detectado.')

    return result
