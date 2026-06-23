from __future__ import annotations

import json
from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.openai_error_monitor import (
    DIAGNOSTIC_CONTEXT_KEY,
    DIAGNOSTIC_MODEL_KEY,
    DIAGNOSTIC_RESULT_KEY,
    analyze_current_session_with_openai,
    build_diagnostic_context,
    openai_monitor_config_status,
)

RESPONSIBLE_FILE = 'bling_app_zero/ui/openai_diagnostics_panel.py'
MODEL_OPTIONS = ('gpt-5.4-mini', 'gpt-5.5', 'gpt-5.4')


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str).encode('utf-8')


def _render_config_status() -> None:
    status = openai_monitor_config_status(st.session_state)
    if status.get('configured'):
        st.success('Diagnóstico IA configurado.')
    else:
        st.warning('Diagnóstico IA sem chave configurada.')
        st.caption('Configure a chave nos Secrets do app ou variável de ambiente do servidor.')
    st.caption(f'Modelo: {status.get("model")}')


def _render_model_selector() -> None:
    current = str(st.session_state.get(DIAGNOSTIC_MODEL_KEY) or openai_monitor_config_status(st.session_state).get('model') or MODEL_OPTIONS[0])
    options = list(dict.fromkeys([current, *MODEL_OPTIONS]))
    selected = st.selectbox('Modelo do diagnóstico', options=options, index=options.index(current), key='openai_error_monitor_model_selectbox')
    st.session_state[DIAGNOSTIC_MODEL_KEY] = selected


def _render_result() -> None:
    result = st.session_state.get(DIAGNOSTIC_RESULT_KEY)
    if isinstance(result, dict) and result:
        if result.get('ok'):
            st.success('Diagnóstico IA concluído.')
        else:
            st.error(f'Diagnóstico IA não concluiu: {result.get("status")}')
        st.markdown(str(result.get('message') or 'Sem mensagem.'))
        st.download_button(
            '⬇️ Baixar diagnóstico IA completo',
            data=_json_bytes(result),
            file_name='mapeiaai_openai_diagnostico.json',
            mime='application/json; charset=utf-8',
            use_container_width=True,
            key='download_openai_error_monitor_result',
        )
        return

    context = st.session_state.get(DIAGNOSTIC_CONTEXT_KEY)
    if isinstance(context, dict) and context:
        st.download_button(
            '⬇️ Baixar contexto sanitizado',
            data=_json_bytes(context),
            file_name='mapeiaai_contexto_sanitizado.json',
            mime='application/json; charset=utf-8',
            use_container_width=True,
            key='download_openai_error_monitor_context_only',
        )


def render_openai_diagnostics_panel() -> None:
    with st.sidebar.expander('🤖 Diagnóstico IA', expanded=False):
        st.caption('Analisa logs, estado do fluxo e eventos técnicos sem expor token, senha ou secrets.')
        _render_config_status()
        _render_model_selector()

        if st.button('Capturar contexto agora', use_container_width=True, key='openai_error_monitor_capture_context'):
            st.session_state[DIAGNOSTIC_CONTEXT_KEY] = build_diagnostic_context(state=st.session_state, reason='manual_capture')
            add_audit_event('openai_error_monitor_context_captured', area='OPENAI_DIAGNOSTICO', status='OK', details={'responsible_file': RESPONSIBLE_FILE})
            st.success('Contexto sanitizado capturado.')

        if st.button('Analisar erros com IA', use_container_width=True, key='openai_error_monitor_run_analysis'):
            with st.spinner('Analisando diagnóstico técnico...'):
                analyze_current_session_with_openai(state=st.session_state, reason='manual_sidebar')

        st.caption('A análise usa apenas dados resumidos: etapas, nomes de colunas, tamanhos de DataFrame, logs e erros sanitizados.')
        _render_result()


__all__ = ['render_openai_diagnostics_panel']
