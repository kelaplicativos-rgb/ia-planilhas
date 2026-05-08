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


def _score_model(file: Any, df: pd.DataFrame | None, operation: str) -> int:
    if operation == 'estoque':
        return _score_estoque_model(file, df)
    return _score_cadastro_model(file, df)


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

    model_files = {file for file in [cadastro_file, estoque_file] if file is not None}
    source_candidates = [item for item in loaded if item[0] not in model_files]
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


def render_smart_upload_box(
    title: str,
    operation: str,
    key: str,
    allow_model: bool = True,
    required_model: bool = False,
    accepted_types: list[str] | None = None,
) -> SmartUploadResult:
    st.markdown(f'#### {title}')
    st.caption('Selecione os arquivos. O sistema identifica automaticamente a origem e os modelos quando possível.')

    files = st.file_uploader(
        '📎 Anexar arquivos',
        type=None,
        accept_multiple_files=True,
        key=key,
        help='Selecione os arquivos; a validação acontece depois do anexo.',
    )

    if not files:
        st.info('Nenhum arquivo anexado ainda.')
        return SmartUploadResult(attachments=[], ignored_files=[])

    selected_files = list(files)
    supported_files, ignored_files = _split_supported_files(selected_files, accepted_types)

    if ignored_files:
        st.warning(
            'Arquivo(s) ignorado(s) por tipo não suportado neste fluxo: '
            + ', '.join(_file_name(file) for file in ignored_files)
        )

    if not supported_files:
        st.error('Os arquivos foram selecionados, mas nenhum deles é compatível com este fluxo.')
        return SmartUploadResult(attachments=[], ignored_files=ignored_files)

    result = _classify(supported_files, operation=operation, allow_model=allow_model, ignored_files=ignored_files)

    st.success(f'{len(supported_files)} arquivo(s) anexado(s) e aceito(s).')
    cards = st.columns(min(len(supported_files), 3))
    for index, file in enumerate(supported_files):
        with cards[index % len(cards)]:
            role = 'Origem'
            if result.cadastro_model_file is file:
                role = 'Modelo cadastro Bling'
            elif result.estoque_model_file is file:
                role = 'Modelo estoque Bling'
            st.info(f'📎 {role}\n\n{_file_name(file)}')

    if result.source_df is not None:
        preview_df('Preview automático da origem detectada', result.source_df)
    elif result.source_file is not None:
        st.warning(f'Origem detectada, mas ainda sem preview tabular: {_file_name(result.source_file)}')

    if allow_model:
        if result.cadastro_model_df is not None:
            with st.expander('Modelo cadastro Bling detectado', expanded=False):
                preview_df('Preview do modelo de cadastro', result.cadastro_model_df)
        if result.estoque_model_df is not None:
            with st.expander('Modelo estoque Bling detectado', expanded=False):
                preview_df('Preview do modelo de estoque', result.estoque_model_df)
        if required_model and result.model_df is None:
            st.warning('Modelo Bling ainda não detectado. Anexe o modelo junto da origem.')

    return result
