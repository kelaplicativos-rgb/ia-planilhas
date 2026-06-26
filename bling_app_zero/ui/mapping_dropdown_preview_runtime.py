from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/mapping_dropdown_preview_runtime.py'
PATCH_VERSION = 'dropdown_preview_source_or_model_v6_full_table_preview'
FULL_TABLE_PATCH_VERSION = 'full_table_preview_v1'
BLANKS = {'', 'nan', 'none', 'null', '<na>'}
_CONTEXT: dict[str, Any] = {'source': None, 'target': None}

FULL_PREVIEW_STATE_KEYS = (
    'mapeiaai_universal_model_df',
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'mapeiaai_universal_source_df',
    'mapeiaai_universal_processed_df',
    'df_origem_unificada',
    'df_origem_site',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_universal',
    'df_site_bruto_universal',
    'df_site_bruto',
    'df_produtos_origem',
    'cadastro_wizard_df_para_mapear',
    'df_origem_cadastro_precificada',
    'mapeiaai_universal_output_df',
    'neutral_final_output_state_v1',
    'final_download_df_snapshot',
)


def _blank(value: object) -> bool:
    return str(value or '').strip().casefold() in BLANKS


def _norm(value: object) -> str:
    text = str(value or '').strip().casefold()
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '', text)


def _clean(value: object) -> str:
    text = str(value or '').replace('\t', ' ').replace('\n', ' ').strip()
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text


def _matching_column(df: Any, column: str) -> str:
    if not isinstance(df, pd.DataFrame) or not column:
        return ''
    if column in df.columns:
        return column
    wanted = _norm(column)
    if not wanted:
        return ''
    for candidate in [str(c) for c in df.columns]:
        if _norm(candidate) == wanted:
            return candidate
    return ''


def _samples(df: Any, column: str, limit: int = 2) -> list[str]:
    actual_column = _matching_column(df, column)
    if not actual_column:
        return []
    out: list[str] = []
    try:
        for value in df[actual_column].dropna().astype(str).tolist():
            text = _clean(value)
            if _blank(text):
                continue
            if text not in out:
                out.append(text)
            if len(out) >= limit:
                break
    except Exception:
        return []
    return out


def _column_state(df: Any, column: str, limit: int = 2) -> tuple[str, str, list[str]]:
    actual_column = _matching_column(df, column)
    if not actual_column:
        return 'missing', '', []
    values = _samples(df, actual_column, limit=limit)
    if values:
        return 'values', actual_column, values
    return 'empty', actual_column, []


def _short(values: list[str], size: int = 72) -> str:
    text = ' | '.join(values)
    return text if len(text) <= size else text[: size - 1].rstrip() + '…'


def _icon(label: object) -> str:
    text = str(label or '').strip()
    for mark in ('🟢', '🟡', '🔴', '⚪'):
        if text.startswith(mark):
            return mark
    return '🟡'


def _source_column_state(column: str, limit: int = 2, source: Any | None = None) -> tuple[str, str, list[str]]:
    # A origem precisa ser SEMPRE o DataFrame atual recebido pelo render.
    # Não varrer st.session_state aqui: isso mistura capturas antigas e mostra produto de outra operação.
    frame = source if isinstance(source, pd.DataFrame) else _CONTEXT.get('source')
    return _column_state(frame, column, limit=limit)


def _model_column_state(column: str, target_name: str = '', limit: int = 2) -> tuple[str, str, list[str]]:
    model = _CONTEXT.get('target')
    checked: list[str] = []
    for candidate in (column, target_name):
        candidate = str(candidate or '').strip()
        if candidate and candidate not in checked:
            checked.append(candidate)
    first_empty: tuple[str, str, list[str]] | None = None
    for candidate in checked:
        state, actual_column, values = _column_state(model, candidate, limit=limit)
        if state == 'values':
            return state, actual_column, values
        if state == 'empty' and first_empty is None:
            first_empty = (state, actual_column, values)
    return first_empty or ('missing', '', [])


def _status_text(status: str, column: str) -> str:
    if status == 'empty':
        return f'coluna {column} vazia' if column else 'coluna vazia'
    if status == 'missing':
        return 'não existe'
    return ''


def _model_samples(column: str, target_name: str = '', limit: int = 2) -> tuple[str, list[str]]:
    _status, actual_column, values = _model_column_state(column, target_name, limit=limit)
    return actual_column, values


def _preview_label(column: str, current_label: object, target_name: str = '') -> str:
    icon = _icon(current_label)

    # Cada opção do dropdown deve mostrar a prévia da própria coluna da origem.
    # Ex.: opção IdProduto só pode ler origem['IdProduto']; nunca Nome/Código nem session antiga.
    source_status, source_column, source_values = _source_column_state(column, limit=2)
    if source_values:
        label = column if source_column == column else f'{column} -> origem {source_column}'
        return f'{icon} {label}: origem {_short(source_values)}'

    model_status, model_column, model_values = _model_column_state(column, target_name, limit=2)
    if model_values:
        label = column if model_column == column else f'{column} -> modelo {model_column}'
        return f'{icon} {label}: modelo {_short(model_values)}'

    source_info = _status_text(source_status, source_column or column)
    model_info = _status_text(model_status, model_column or target_name or column)
    return f'{icon} {column}: origem {source_info}; modelo {model_info}'


def _as_text_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df.copy().fillna('').astype(str)


def _same_columns(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    return [str(column) for column in left.columns] == [str(column) for column in right.columns]


def _is_head_preview(sample: pd.DataFrame, full: pd.DataFrame) -> bool:
    if not isinstance(sample, pd.DataFrame) or not isinstance(full, pd.DataFrame):
        return False
    if sample.empty or full.empty:
        return False
    if len(sample) >= len(full):
        return False
    if not _same_columns(sample, full):
        return False
    try:
        sample_text = _as_text_frame(sample).reset_index(drop=True)
        full_head = _as_text_frame(full).head(len(sample_text)).reset_index(drop=True)
        return bool(sample_text.equals(full_head))
    except Exception:
        return False


def _full_preview_for(data: Any) -> pd.DataFrame | None:
    if not isinstance(data, pd.DataFrame):
        return None
    for key in FULL_PREVIEW_STATE_KEYS:
        full = st.session_state.get(key)
        if isinstance(full, pd.DataFrame) and _is_head_preview(data, full):
            return full.copy().fillna('')
    return None


def _table_height(df: pd.DataFrame) -> int:
    rows = int(len(df)) if isinstance(df, pd.DataFrame) else 0
    if rows <= 8:
        return max(260, 42 * (rows + 2))
    if rows <= 30:
        return min(760, 36 * (rows + 2))
    return 720


def _install_full_table_preview_patch() -> None:
    if getattr(st, '_mapeiaai_full_table_preview_runtime_version', '') == FULL_TABLE_PATCH_VERSION:
        return
    original_dataframe = getattr(st, '_mapeiaai_original_dataframe', None) or st.dataframe
    st._mapeiaai_original_dataframe = original_dataframe

    def dataframe_full_content(data=None, *args, **kwargs):
        full = _full_preview_for(data)
        if isinstance(full, pd.DataFrame):
            data = _as_text_frame(full)
            kwargs['use_container_width'] = True
            kwargs['height'] = _table_height(full)
            add_audit_event(
                'full_table_preview_expanded_head_dataframe',
                area='UNIVERSAL',
                status='OK',
                details={
                    'rows': int(len(full)),
                    'columns': int(len(full.columns)),
                    'reason': 'Mostrar todos os conteúdos em vez de head(3), head(30) ou head(80).',
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
        return original_dataframe(data, *args, **kwargs)

    st.dataframe = dataframe_full_content
    st._mapeiaai_full_table_preview_runtime_version = FULL_TABLE_PATCH_VERSION
    add_audit_event('full_table_preview_runtime_installed', area='UNIVERSAL', status='OK', details={'version': FULL_TABLE_PATCH_VERSION, 'responsible_file': RESPONSIBLE_FILE})


def install_mapping_dropdown_preview_runtime() -> None:
    _install_full_table_preview_patch()
    try:
        from bling_app_zero.ui import shared_mapping
    except Exception as exc:
        add_audit_event('mapping_dropdown_preview_runtime_import_failed', area='MAPEAMENTO', status='AVISO', details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
        return

    if getattr(shared_mapping, '_mapeiaai_dropdown_preview_runtime_version', '') == PATCH_VERSION:
        return

    original_render = shared_mapping.render_shared_contract_mapping
    original_ranked = shared_mapping._ranked_source_options
    original_mapping_preview = shared_mapping._render_mapping_preview

    def ranked_with_real_preview(target_name, current_value, source_columns, suggestions_index, source_profiles=None):
        options, labels = original_ranked(target_name, current_value, source_columns, suggestions_index, source_profiles)
        labels = dict(labels or {})
        for column in list(source_columns or []):
            if column in labels:
                labels[column] = _preview_label(str(column), labels[column], str(target_name or ''))
        return options, labels

    def render_mapping_preview_with_model_fallback(target_name, selected_value, source):
        try:
            selected = str(selected_value or '').strip()
            if selected and not shared_mapping.is_fixed_value(selected):
                source_status, source_column, source_samples = _source_column_state(selected, limit=3, source=source)
                icon = shared_mapping.confidence_flag(str(target_name or ''), selected, source).split()[0]
                if source_samples:
                    shared_mapping.st.caption(f'{icon} **{target_name}**. Prévia da origem ({source_column}): {_short(source_samples, 150)}')
                    return

                model_status, model_column, model_values = _model_column_state(selected, str(target_name or ''), limit=3)
                if model_values:
                    shared_mapping.st.caption(f'{icon} **{target_name}**. Prévia do modelo anexado ({model_column}): {_short(model_values, 150)}')
                    return

                source_info = _status_text(source_status, source_column or selected)
                model_info = _status_text(model_status, model_column or str(target_name or selected))
                shared_mapping.st.caption(f'{icon} **{target_name}**. Origem: {source_info}. Modelo: {model_info}.')
                return
        except Exception:
            pass
        return original_mapping_preview(target_name, selected_value, source)

    def render_with_context(source, target, *, signature: str, mapping_state_key: str, engine_state_key: str, key_prefix: str = 'mapeiaai_shared', ai_enabled: bool = True):
        previous_source = _CONTEXT.get('source')
        previous_target = _CONTEXT.get('target')
        _CONTEXT['source'] = source
        _CONTEXT['target'] = target
        try:
            return original_render(source, target, signature=signature, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key, key_prefix=key_prefix, ai_enabled=ai_enabled)
        finally:
            _CONTEXT['source'] = previous_source
            _CONTEXT['target'] = previous_target

    shared_mapping._ranked_source_options = ranked_with_real_preview
    shared_mapping._render_mapping_preview = render_mapping_preview_with_model_fallback
    shared_mapping.render_shared_contract_mapping = render_with_context
    shared_mapping._mapeiaai_dropdown_preview_runtime_version = PATCH_VERSION
    add_audit_event('mapping_dropdown_preview_runtime_installed', area='MAPEAMENTO', status='OK', details={'format': 'Prévia presa ao DataFrame atual; dropdown correto; tabelas mostram conteúdo completo', 'version': PATCH_VERSION, 'responsible_file': RESPONSIBLE_FILE})


__all__ = ['install_mapping_dropdown_preview_runtime']
