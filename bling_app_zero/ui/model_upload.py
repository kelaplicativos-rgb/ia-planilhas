from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.home_shared import preview_df, read_upload_fast

MODEL_SPREADSHEET_TYPES = ['xlsx', 'xls', 'csv', 'xlsm', 'xlsb']


@dataclass
class ModelUploadResult:
    cadastro_model_file: Any | None = None
    cadastro_model_df: pd.DataFrame | None = None
    estoque_model_file: Any | None = None
    estoque_model_df: pd.DataFrame | None = None
    model_file: Any | None = None
    model_df: pd.DataFrame | None = None
    attachments: list[Any] | None = None
    ignored_files: list[Any] | None = None


def _file_name(file: Any) -> str:
    return str(getattr(file, 'name', 'arquivo')).strip()


def _file_ext(file: Any) -> str:
    name = _file_name(file).lower()
    return name.rsplit('.', 1)[-1] if '.' in name else ''


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
    if any(term in name for term in ['modelo', 'bling', 'cadastro', 'produto', 'layout', 'importacao', 'importação']):
        score += 35
    if any(term in columns for term in ['gtin', 'ean', 'preço', 'preco', 'descrição', 'descricao', 'ncm', 'marca', 'categoria']):
        score += 70
    if any(term in columns for term in ['depósito', 'deposito', 'balanço', 'balanco']):
        score -= 45
    return score


def _score_estoque_model(file: Any, df: pd.DataFrame | None) -> int:
    name = _file_name(file).lower()
    columns = _column_text(df)
    score = 0
    if any(term in name for term in ['modelo', 'bling', 'estoque', 'layout', 'importacao', 'importação']):
        score += 35
    if any(term in columns for term in ['depósito', 'deposito', 'balanço', 'balanco', 'estoque', 'quantidade', 'saldo']):
        score += 80
    if any(term in columns for term in ['gtin', 'ean', 'ncm', 'marca', 'categoria']):
        score -= 25
    return score


def _pick_cadastro(loaded: list[tuple[Any, pd.DataFrame | None]]) -> tuple[Any | None, pd.DataFrame | None]:
    if not loaded:
        return None, None
    file, df = max(loaded, key=lambda item: _score_cadastro_model(item[0], item[1]))
    if _score_cadastro_model(file, df) < 45:
        return None, None
    return file, df


def _pick_estoque(loaded: list[tuple[Any, pd.DataFrame | None]], used_file: Any | None) -> tuple[Any | None, pd.DataFrame | None]:
    candidates = [item for item in loaded if item[0] is not used_file] or loaded
    if not candidates:
        return None, None
    file, df = max(candidates, key=lambda item: _score_estoque_model(item[0], item[1]))
    if _score_estoque_model(file, df) < 45:
        return None, None
    return file, df


def render_model_upload_box(
    title: str,
    operation: str,
    key: str,
    required_model: bool = False,
) -> ModelUploadResult:
    st.markdown(f'#### {title}')
    st.caption('Anexe aqui somente as planilhas modelo do Bling. A origem deste fluxo é o site/URL.')

    files = st.file_uploader(
        '📎 Anexar planilhas modelo',
        type=MODEL_SPREADSHEET_TYPES,
        accept_multiple_files=True,
        key=key,
        help='Aceita modelo de cadastro e modelo de estoque ao mesmo tempo.',
    )

    if not files:
        st.info('Nenhuma planilha modelo anexada ainda.')
        return ModelUploadResult(attachments=[], ignored_files=[])

    selected_files = list(files)
    supported_files = [file for file in selected_files if _file_ext(file) in MODEL_SPREADSHEET_TYPES]
    ignored_files = [file for file in selected_files if _file_ext(file) not in MODEL_SPREADSHEET_TYPES]

    if ignored_files:
        st.warning('Arquivo(s) ignorado(s): ' + ', '.join(_file_name(file) for file in ignored_files))

    loaded = [(file, _safe_read(file)) for file in supported_files]
    cadastro_file, cadastro_df = _pick_cadastro(loaded)
    estoque_file, estoque_df = _pick_estoque(loaded, cadastro_file)

    model_file, model_df = (estoque_file, estoque_df) if operation == 'estoque' else (cadastro_file, cadastro_df)

    st.success(f'{len(supported_files)} planilha(s) modelo aceita(s).')
    cards = st.columns(min(len(supported_files), 3))
    for index, file in enumerate(supported_files):
        with cards[index % len(cards)]:
            role = 'Planilha modelo'
            if file is cadastro_file:
                role = 'Modelo cadastro Bling'
            elif file is estoque_file:
                role = 'Modelo estoque Bling'
            st.info(f'📎 {role}\n\n{_file_name(file)}')

    if isinstance(cadastro_df, pd.DataFrame):
        preview_df('Preview do modelo de cadastro', cadastro_df)
    if isinstance(estoque_df, pd.DataFrame):
        preview_df('Preview do modelo de estoque', estoque_df)

    if required_model and model_df is None:
        st.warning('Modelo Bling obrigatório ainda não detectado.')

    return ModelUploadResult(
        cadastro_model_file=cadastro_file,
        cadastro_model_df=cadastro_df,
        estoque_model_file=estoque_file,
        estoque_model_df=estoque_df,
        model_file=model_file,
        model_df=model_df,
        attachments=supported_files,
        ignored_files=ignored_files,
    )
