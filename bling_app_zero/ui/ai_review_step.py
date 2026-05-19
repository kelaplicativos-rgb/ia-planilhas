from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ai.ai_config import get_ai_settings
from bling_app_zero.ai.ai_openai_mapping_suggester import suggest_mapping_with_openai
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_shared import df_signature
from bling_app_zero.ui.mapping_preview_builder import build_cadastro_preview
from bling_app_zero.ui.mapping_widget_state import is_manual_value, mapping_base

RESPONSIBLE_FILE = 'bling_app_zero/ui/ai_review_step.py'
AI_REVIEW_RESULT_KEY = 'ai_real_review_result'
AI_REVIEW_APPLIED_SIGNATURE_KEY = 'ai_real_review_applied_signature'


def _safe_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item or '') for key, item in value.items()}


def _target_columns(df_modelo: pd.DataFrame | None) -> list[str]:
    if not isinstance(df_modelo, pd.DataFrame):
        return []
    return [str(column) for column in df_modelo.columns]


def _source_columns(df_source: pd.DataFrame | None) -> set[str]:
    if not isinstance(df_source, pd.DataFrame):
        return set()
    return {str(column) for column in df_source.columns}


def _review_signature(df_source: pd.DataFrame, df_modelo: pd.DataFrame, mapping: dict[str, str]) -> str:
    targets = _target_columns(df_modelo)
    mapping_text = '|'.join(f'{target}={mapping.get(target, "")}' for target in targets)
    return f'{df_signature(df_source)}:{"|".join(targets)}:{mapping_text}'


def _mapping_key_for(df_source: pd.DataFrame, target_columns: list[str]) -> str:
    signature = df_signature(df_source) + ':' + '|'.join(target_columns)
    return mapping_base('cad_map_', signature)


def _suggestions_from_result(result_data: dict[str, Any]) -> list[dict[str, Any]]:
    suggestions = result_data.get('suggestions')
    return suggestions if isinstance(suggestions, list) else []


def _mapping_from_result(result_data: dict[str, Any]) -> dict[str, str]:
    mapping = result_data.get('mapping')
    return {str(key): str(value or '') for key, value in mapping.items()} if isinstance(mapping, dict) else {}


def _safe_improvements(
    *,
    current_mapping: dict[str, str],
    ai_mapping: dict[str, str],
    df_source: pd.DataFrame,
    df_modelo: pd.DataFrame,
) -> dict[str, str]:
    source_set = _source_columns(df_source)
    target_set = set(_target_columns(df_modelo))
    improvements: dict[str, str] = {}

    for target, source in ai_mapping.items():
        target_name = str(target or '').strip()
        source_name = str(source or '').strip()
        if not target_name or target_name not in target_set:
            continue
        if not source_name or source_name not in source_set:
            continue
        current = str(current_mapping.get(target_name, '') or '').strip()
        if current == source_name:
            continue
        if is_manual_value(current):
            continue
        improvements[target_name] = source_name
    return improvements


def _render_suggestions_table(
    *,
    suggestions: list[dict[str, Any]],
    improvements: dict[str, str],
) -> None:
    rows: list[dict[str, str]] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        target = str(item.get('target_column') or '').strip()
        source = str(item.get('source_column') or '').strip()
        rows.append(
            {
                'Campo do modelo': target,
                'Origem sugerida': source or '—',
                'Confiança': str(item.get('confidence') or ''),
                'Ação': 'Pode melhorar' if target in improvements else 'Sem alteração',
                'Motivo': str(item.get('reason') or '')[:180],
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=280)


def _apply_ai_improvements(
    *,
    improvements: dict[str, str],
    df_source: pd.DataFrame,
    df_modelo: pd.DataFrame,
    current_mapping: dict[str, str],
    signature: str,
) -> None:
    target_columns = _target_columns(df_modelo)
    mapping_key = _mapping_key_for(df_source, target_columns)
    updated_mapping = dict(current_mapping)
    updated_mapping.update(improvements)

    df_preview = build_cadastro_preview(df_source, df_modelo, updated_mapping, target_columns, mapping_key)
    st.session_state[mapping_key] = updated_mapping
    st.session_state['mapping_cadastro'] = updated_mapping
    st.session_state['df_final_cadastro'] = df_preview
    st.session_state[AI_REVIEW_APPLIED_SIGNATURE_KEY] = signature
    st.session_state.pop('df_final_cadastro_preview_rules_applied', None)

    add_audit_event(
        'ai_real_review_applied',
        area='AI',
        step='regras',
        status='OK',
        details={
            'improvements_count': len(improvements),
            'targets': list(improvements.keys()),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def render_ai_real_review_step(
    *,
    df_source: pd.DataFrame | None,
    df_modelo: pd.DataFrame | None,
    mapping: dict[str, str] | None,
) -> None:
    st.markdown('#### IA Real pós-mapeamento')
    st.caption('A IA Real roda somente depois do mapeamento confirmado e usa a chave configurada no Secrets do app.')

    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        st.warning('IA Real aguardando os dados da origem.')
        return
    if not isinstance(df_modelo, pd.DataFrame) or not len(df_modelo.columns):
        st.warning('IA Real aguardando o modelo de destino.')
        return

    current_mapping = _safe_mapping(mapping)
    if not current_mapping:
        st.warning('IA Real aguardando o mapeamento confirmado.')
        return

    settings = get_ai_settings()
    if not settings.ready:
        st.warning('IA Real indisponível: configure a chave OpenAI no Secrets do app.')
        return

    st.success(f'IA Real pronta via Secrets · Modelo: {settings.model}')
    signature = _review_signature(df_source, df_modelo, current_mapping)
    cached = st.session_state.get(AI_REVIEW_RESULT_KEY)

    col_run, col_clear = st.columns(2)
    with col_run:
        run_clicked = st.button('Rodar IA Real na revisão', use_container_width=True, key='ai_real_review_run')
    with col_clear:
        if st.button('Limpar revisão da IA', use_container_width=True, key='ai_real_review_clear'):
            st.session_state.pop(AI_REVIEW_RESULT_KEY, None)
            st.session_state.pop(AI_REVIEW_APPLIED_SIGNATURE_KEY, None)
            st.success('Revisão da IA limpa.')
            st.rerun()

    if run_clicked or not (isinstance(cached, dict) and cached.get('signature') == signature):
        with st.spinner('IA Real revisando o mapeamento confirmado...'):
            result = suggest_mapping_with_openai(df_source, df_modelo, operation='universal')
        result_data = result.data if isinstance(result.data, dict) else {}
        st.session_state[AI_REVIEW_RESULT_KEY] = {
            'signature': signature,
            'ok': bool(result.ok),
            'message': result.message,
            'error': result.error,
            'data': result_data,
        }
        add_audit_event(
            'ai_real_review_finished',
            area='AI',
            step='regras',
            status='OK' if result.ok else 'ERRO',
            details={
                'message': result.message,
                'error': result.error,
                'engine': result_data.get('engine') if isinstance(result_data, dict) else '',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    review = st.session_state.get(AI_REVIEW_RESULT_KEY)
    if not isinstance(review, dict) or review.get('signature') != signature:
        st.caption('Clique para rodar a IA Real nesta revisão.')
        return

    data = review.get('data') if isinstance(review.get('data'), dict) else {}
    engine = str(data.get('engine') or '')
    if engine != 'openai_validated':
        st.warning('A IA Real não retornou melhorias validadas. O mapeamento confirmado foi mantido.')
        if review.get('message'):
            st.caption(str(review.get('message')))
        return

    ai_mapping = _mapping_from_result(data)
    suggestions = _suggestions_from_result(data)
    improvements = _safe_improvements(
        current_mapping=current_mapping,
        ai_mapping=ai_mapping,
        df_source=df_source,
        df_modelo=df_modelo,
    )

    st.caption(f'{len(improvements)} melhoria(s) segura(s) encontrada(s).')
    _render_suggestions_table(suggestions=suggestions, improvements=improvements)

    if not improvements:
        st.success('IA Real conferiu o mapeamento e não encontrou melhoria segura para aplicar.')
        return

    already_applied = st.session_state.get(AI_REVIEW_APPLIED_SIGNATURE_KEY) == signature
    if already_applied:
        st.success('Melhorias da IA Real já foram aplicadas nesta revisão.')
        return

    if st.button('Aplicar melhorias seguras da IA', use_container_width=True, key='ai_real_review_apply'):
        _apply_ai_improvements(
            improvements=improvements,
            df_source=df_source,
            df_modelo=df_modelo,
            current_mapping=current_mapping,
            signature=signature,
        )
        st.success('Melhorias seguras da IA aplicadas. Confira o preview antes de baixar.')
        st.rerun()


__all__ = ['render_ai_real_review_step']