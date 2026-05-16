from __future__ import annotations

import streamlit as st

from bling_app_zero.ai.ai_cache import cache_clear, get_ai_cache
from bling_app_zero.ai.ai_config import (
    AI_ALLOWED_MODES,
    AI_ENABLED_KEY,
    AI_MODE_KEY,
    AI_MODEL_KEY,
    AI_USER_API_KEY,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_MODE,
    clear_ai_key,
    get_ai_settings,
)
from bling_app_zero.ai.ai_client import validate_openai_key
from bling_app_zero.ai.ai_job_queue import clear_ai_jobs, get_ai_jobs
from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/ai_sidebar.py'
MODE_LABELS = {
    'seguro': 'Seguro — só sugere',
    'assistido': 'Assistido — aplica melhorias óbvias',
    'automatico': 'Automático — alta confiança',
}
MODEL_OPTIONS = [DEFAULT_AI_MODEL, 'gpt-4o', 'gpt-4.1-mini']


def _mode_from_label(label: str) -> str:
    for key, value in MODE_LABELS.items():
        if value == label:
            return key
    return DEFAULT_AI_MODE


def _render_status() -> None:
    settings = get_ai_settings()
    if settings.ready:
        st.success('IA pronta para esta sessão.')
        st.caption(f'Modo: {MODE_LABELS.get(settings.mode, settings.mode)} · Modelo: {settings.model}')
    elif settings.enabled:
        st.warning('Informe sua chave OpenAI para ativar a IA.')
    else:
        st.caption('IA desativada. O sistema continua funcionando normalmente.')


def render_ai_sidebar() -> None:
    with st.sidebar:
        with st.expander('🤖 IA do MapeiaAI', expanded=False):
            st.caption('Use sua própria chave OpenAI. A chave não é salva no GitHub, não entra nos logs e vale apenas para a sessão atual.')

            st.toggle('Ativar IA inteligente', key=AI_ENABLED_KEY, value=bool(st.session_state.get(AI_ENABLED_KEY, False)))
            st.text_input(
                'Chave OpenAI do usuário',
                type='password',
                key=AI_USER_API_KEY,
                placeholder='sk-...',
                help='Cole aqui sua própria chave. O sistema não usa chave em Secrets como fallback.',
            )

            current_mode = str(st.session_state.get(AI_MODE_KEY) or DEFAULT_AI_MODE)
            mode_labels = [MODE_LABELS[mode] for mode in AI_ALLOWED_MODES]
            default_mode_index = AI_ALLOWED_MODES.index(current_mode) if current_mode in AI_ALLOWED_MODES else AI_ALLOWED_MODES.index(DEFAULT_AI_MODE)
            selected_mode_label = st.selectbox('Modo da IA', mode_labels, index=default_mode_index, key='mapeia_ai_mode_label')
            st.session_state[AI_MODE_KEY] = _mode_from_label(selected_mode_label)

            current_model = str(st.session_state.get(AI_MODEL_KEY) or DEFAULT_AI_MODEL)
            if current_model not in MODEL_OPTIONS:
                MODEL_OPTIONS.append(current_model)
            model_index = MODEL_OPTIONS.index(current_model)
            st.selectbox('Modelo OpenAI', MODEL_OPTIONS, index=model_index, key=AI_MODEL_KEY)

            col_validate, col_clear = st.columns(2)
            with col_validate:
                if st.button('Validar IA', use_container_width=True, key='mapeia_ai_validate_button'):
                    result = validate_openai_key()
                    if result.ok:
                        st.success(result.message)
                    else:
                        st.warning(result.message)
                    add_audit_event(
                        'ai_sidebar_validate_clicked',
                        area='AI',
                        status='OK' if result.ok else 'BLOQUEADO',
                        details={'error': result.error, 'responsible_file': RESPONSIBLE_FILE},
                    )
            with col_clear:
                if st.button('Limpar', use_container_width=True, key='mapeia_ai_clear_button'):
                    clear_ai_key()
                    clear_ai_jobs()
                    st.success('IA desligada e chave removida da sessão.')
                    add_audit_event('ai_sidebar_key_cleared', area='AI', details={'responsible_file': RESPONSIBLE_FILE})

            _render_status()

            jobs = get_ai_jobs()
            cache_size = len(get_ai_cache())
            with st.expander('Status técnico da IA', expanded=False):
                st.caption(f'Tarefas na sessão: {len(jobs)}')
                st.caption(f'Itens em cache: {cache_size}')
                if st.button('Limpar cache da IA', use_container_width=True, key='mapeia_ai_cache_clear_button'):
                    cache_clear()
                    st.success('Cache da IA limpo.')


__all__ = ['render_ai_sidebar']
