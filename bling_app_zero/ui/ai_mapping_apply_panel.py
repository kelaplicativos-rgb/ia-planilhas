from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_config import ai_is_enabled, get_ai_settings
from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_autofluxo import pause_home_autofluxo_for_manual_review
from bling_app_zero.ui.mapping_constants import EMPTY_CHOOSE_OPTION, EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION

RESPONSIBLE_FILE = 'bling_app_zero/ui/ai_mapping_apply_panel.py'
MIN_CONFIDENCE_TO_APPLY = 0.85
EMPTY_VALUES = {'', EMPTY_CHOOSE_OPTION, EMPTY_LEAVE_OPTION, MANUAL_WRITE_OPTION}


def _target_dataframe_from_columns(target_columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=[str(column) for column in target_columns])


def _is_empty_mapping_value(value: object) -> bool:
    return str(value or '').strip() in EMPTY_VALUES


def _eligible_suggestions(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    *,
    operation: str,
) -> tuple[list[dict[str, object]], str]:
    result = suggest_mapping_with_openai(df_source, _target_dataframe_from_columns(target_columns), operation=operation)
    suggestions = result.data.get('suggestions', []) if isinstance(result.data, dict) else []
    engine = str(result.data.get('engine') or 'local') if isinstance(result.data, dict) else 'local'
    rows: list[dict[str, object]] = []
    source_columns = {str(column) for column in df_source.columns}
    for item in suggestions:
        target = str(item.get('target_column') or '')
        source = str(item.get('source_column') or '')
        confidence = float(item.get('confidence') or 0)
        if not target or not source or source not in source_columns:
            continue
        if confidence < MIN_CONFIDENCE_TO_APPLY:
            continue
        current_value = current_mapping.get(target, '')
        if not _is_empty_mapping_value(current_value):
            continue
        rows.append(
            {
                'Campo do modelo': target,
                'Origem sugerida': source,
                'Confiança': f'{round(confidence * 100)}%',
                'confidence_float': confidence,
                'Motor': 'OpenAI' if str(item.get('engine') or engine).startswith('openai') else 'Local',
                'Motivo': item.get('reason', ''),
            }
        )
    return rows, engine


def _apply_suggestions(mapping_key: str, current_mapping: dict[str, str], rows: list[dict[str, object]], *, operation: str, engine: str) -> int:
    updated = dict(current_mapping)
    applied = 0
    for row in rows:
        target = str(row.get('Campo do modelo') or '')
        source = str(row.get('Origem sugerida') or '')
        if not target or not source:
            continue
        if not _is_empty_mapping_value(updated.get(target, '')):
            continue
        updated[target] = source
        applied += 1
    if applied:
        st.session_state[mapping_key] = updated
        if operation == 'cadastro':
            st.session_state.pop('cadastro_mapping_confirmed', None)
            st.session_state.pop('cadastro_mapping_signature', None)
        pause_home_autofluxo_for_manual_review('mapeamento' if operation == 'cadastro' else 'gerar_estoque', reason='ai_mapping_suggestions_applied')
        add_audit_event(
            'ai_mapping_suggestions_applied',
            area='AI',
            details={
                'operation': operation,
                'applied': applied,
                'engine': engine,
                'mapping_key': mapping_key,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    return applied


def _render_ai_suggestions_body(
    *,
    settings,
    rows: list[dict[str, object]],
    engine: str,
    mapping_key: str,
    current_mapping: dict[str, str],
    operation: str,
) -> None:
    engine_label = 'OpenAI validada' if engine == 'openai_validated' else 'Local seguro'
    st.caption(f'Modo {settings.mode} · Motor: {engine_label}. Preenche apenas campos vazios com confiança alta.')
    if not rows:
        st.info('Nenhuma sugestão nova com confiança alta para aplicar agora.')
        return

    display_rows = [{key: value for key, value in row.items() if key != 'confidence_float'} for row in rows]
    st.dataframe(pd.DataFrame(display_rows).astype(str), use_container_width=True, height=220)
    st.warning('Revise antes de continuar. A confirmação final do mapeamento continua manual.')

    if st.button('Aplicar sugestões da IA', use_container_width=True, key=f'{mapping_key}_apply_ai_suggestions'):
        applied = _apply_suggestions(mapping_key, current_mapping, rows, operation=operation, engine=engine)
        if applied:
            st.success(f'{applied} sugestão(ões) aplicada(s). Revise e confirme o mapeamento manualmente.')
            st.rerun()
        else:
            st.info('Nenhuma sugestão foi aplicada porque os campos já estavam preenchidos.')


def render_ai_mapping_apply_panel(
    df_source: pd.DataFrame,
    target_columns: list[str],
    current_mapping: dict[str, str],
    mapping_key: str,
    *,
    operation: str,
    embedded: bool = False,
) -> None:
    """Aplica sugestões da IA somente com clique do usuário."""
    if not isinstance(df_source, pd.DataFrame) or df_source.empty or not target_columns:
        return

    if not ai_is_enabled():
        st.caption('Sugestões automáticas inativas. Ative a IA na sidebar para usar este recurso.')
        return

    settings = get_ai_settings()
    rows, engine = _eligible_suggestions(df_source, target_columns, current_mapping, operation=operation)

    if embedded:
        _render_ai_suggestions_body(
            settings=settings,
            rows=rows,
            engine=engine,
            mapping_key=mapping_key,
            current_mapping=current_mapping,
            operation=operation,
        )
        return

    with st.expander('🤖 Aplicar sugestões da IA', expanded=False):
        _render_ai_suggestions_body(
            settings=settings,
            rows=rows,
            engine=engine,
            mapping_key=mapping_key,
            current_mapping=current_mapping,
            operation=operation,
        )


__all__ = ['MIN_CONFIDENCE_TO_APPLY', 'render_ai_mapping_apply_panel']
