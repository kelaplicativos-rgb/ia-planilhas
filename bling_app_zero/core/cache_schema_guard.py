from __future__ import annotations

from datetime import datetime
from typing import Iterable

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/core/cache_schema_guard.py'
CACHE_SCHEMA_VERSION = '2026-06-22_origem_unica_site_panel_v6_url_produto'
CACHE_SCHEMA_KEY = '_mapeia_cache_schema_version'
CACHE_SCHEMA_LAST_CLEAR_KEY = '_mapeia_cache_schema_last_clear'
CACHE_SCHEMA_NOTICE_KEY = '_mapeia_cache_schema_notice'
CACHE_SCHEMA_REMOVED_COUNT_KEY = '_mapeia_cache_schema_removed_count'
CACHE_SCHEMA_GLOBAL_CLEAR_ALLOWED_KEY = '_mapeia_cache_schema_allow_global_clear'
CACHE_SCHEMA_RERUN_MARKER_KEY = '_mapeia_cache_schema_guard_rerun_done'

# Chaves que não podem ser apagadas em autolimpeza: conexão/tokens, identidade e
# metadados do próprio guardião. O objetivo é matar cache/estado velho de fluxo,
# sem obrigar o usuário a reconectar ao Bling a cada BLINGFIX.
PRESERVE_EXACT_KEYS = {
    CACHE_SCHEMA_KEY,
    CACHE_SCHEMA_LAST_CLEAR_KEY,
    CACHE_SCHEMA_NOTICE_KEY,
    CACHE_SCHEMA_REMOVED_COUNT_KEY,
    CACHE_SCHEMA_GLOBAL_CLEAR_ALLOWED_KEY,
    CACHE_SCHEMA_RERUN_MARKER_KEY,
    'bling_oauth_user_session_id',
    'bling_oauth_token_response',
    'bling_oauth_connected_at',
    'token_store_mode',
    'app_device_hint_v1',
    'mobile_connected_bling_auto_entry_done_v1',
    'app_layout_mode',
    'app_theme_mode',
}

PRESERVE_PREFIXES = (
    '_mapeia_cache_schema_',
    'bling_oauth_',
    'oauth_',
    'user_context',
)

# Estado antigo que mais causa erro depois de deploy: origem, modelos, mapeamento,
# preview, motor de busca por site, flow spine e flags de operação.
CLEAR_PREFIXES = (
    'df_',
    'site_',
    'blingsmartscan_',
    'mapeiaai_universal_',
    'flow_spine_',
    'active_feature_',
    'source_first_',
    'origem_',
    'modelo_',
    'mapping_',
    'neutral_',
    'cadastro_',
    'estoque_',
    'preview_',
    'final_',
    'smart_',
    'home_modelo_',
    'home_detected_',
    'home_slim_',
    'home_active_',
    'home_allow_',
    'mapear_planilha_',
    'api_site_',
    'unified_api_site_',
    'stock_api_',
    'site_api_',
    'operation_site',
    'tipo_operacao_',
    'operacao_final',
    'blingfix_runtime_patches_installed_',
)

CLEAR_EXACT_KEYS = {
    'operation_v2',
    'step',
    'flow_kind',
    'mapeiaai_flow_kind',
    'api_flow_active',
    'home_bling_connected_same_flow_api_send',
    'bling_connected_api_flow_active',
    'direct_bling_api_contract_active',
    'direct_bling_operation_applied',
    'direct_bling_api_contract_df',
    'bling_api_operation',
    'api_operation',
    'home_bling_api_operation_choice',
    'bling_connected_api_operation',
    'flow_spine_sender_operation',
    'source_first_selected_operation',
    'source_first_operation_user_confirmed',
    'source_first_operation_pending_choice',
    'bling_api_required_selector',
    'bling_api_final_action',
    'bling_api_manual_mapping_required',
    'bling_api_must_run_ai_check',
    'df_site_bruto',
    'df_origem_site_como_planilha',
    'df_origem_unificada',
    'df_origem_site',
    'df_origem_arquivo',
    'blingfix_runtime_patches_installed_v7',
    'blingfix_runtime_patches_installed_v8',
}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'


def _audit(event: str, *, status: str = 'INFO', details: dict | None = None) -> None:
    try:
        from bling_app_zero.core.audit import add_audit_event

        add_audit_event(
            event,
            area='APP',
            status=status,
            details={'responsible_file': RESPONSIBLE_FILE, **(details or {})},
        )
    except Exception:
        pass


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '').strip().lower()
        return str(value or '').strip().lower()
    except Exception:
        return ''


def _starts_with_any(key: str, prefixes: Iterable[str]) -> bool:
    return any(key.startswith(prefix) for prefix in prefixes)


def _should_preserve_key(key: str) -> bool:
    if key in PRESERVE_EXACT_KEYS:
        return True
    if _starts_with_any(key, PRESERVE_PREFIXES):
        return True
    # Segurança extra: nunca apagar tokens por heurística.
    low = key.lower()
    if 'token' in low or 'oauth' in low or 'refresh_token' in low or 'access_token' in low:
        return True
    return False


def _should_clear_key(key: str) -> bool:
    if _should_preserve_key(key):
        return False
    if key in CLEAR_EXACT_KEYS:
        return True
    return _starts_with_any(key, CLEAR_PREFIXES)


def _clear_global_streamlit_cache_if_allowed(reason: str) -> bool:
    allowed_query = _query_value('clear_global_cache') in {'1', 'true', 'sim', 'yes'}
    allowed_state = bool(st.session_state.get(CACHE_SCHEMA_GLOBAL_CLEAR_ALLOWED_KEY))
    if not (allowed_query or allowed_state):
        return False
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    _audit('cache_schema_global_streamlit_cache_cleared', status='OK', details={'reason': reason})
    return True


def enforce_cache_schema_guard(app_version: str = '', *, schema_version: str = CACHE_SCHEMA_VERSION) -> bool:
    """Autodestrói estado antigo quando muda o schema crítico do fluxo.

    Retorna True quando limpou a sessão atual. O guardião limpa dados de fluxo,
    modelos, mapeamento, origem e captura por site, preservando conexão OAuth.
    """
    current_schema = str(schema_version or CACHE_SCHEMA_VERSION).strip()
    previous_schema = str(st.session_state.get(CACHE_SCHEMA_KEY) or '').strip()
    if previous_schema == current_schema:
        return False

    removed: list[str] = []
    for key in list(st.session_state.keys()):
        text_key = str(key)
        if _should_clear_key(text_key):
            st.session_state.pop(key, None)
            removed.append(text_key)

    # Mesmo se não achou chaves prefixadas, grava a versão para não limpar a cada rerun.
    st.session_state[CACHE_SCHEMA_KEY] = current_schema
    st.session_state[CACHE_SCHEMA_LAST_CLEAR_KEY] = _now()
    st.session_state[CACHE_SCHEMA_REMOVED_COUNT_KEY] = len(removed)
    st.session_state[CACHE_SCHEMA_NOTICE_KEY] = (
        'Sistema atualizado: cache antigo de fluxo removido automaticamente. '
        'A conexão com o Bling foi preservada.'
    )
    global_cleared = _clear_global_streamlit_cache_if_allowed(f'schema_changed:{previous_schema}->{current_schema}')
    _audit(
        'cache_schema_guard_autodestructed_old_state',
        status='OK',
        details={
            'previous_schema': previous_schema,
            'current_schema': current_schema,
            'app_version': str(app_version or ''),
            'removed_count': len(removed),
            'removed_keys_sample': removed[:80],
            'global_cache_cleared': global_cleared,
            'oauth_preserved': True,
        },
    )
    return True


def render_cache_schema_notice() -> None:
    notice = str(st.session_state.get(CACHE_SCHEMA_NOTICE_KEY) or '').strip()
    if not notice:
        return
    removed = int(st.session_state.get(CACHE_SCHEMA_REMOVED_COUNT_KEY) or 0)
    st.info(f'{notice} Itens limpos: {removed}.')
    st.session_state.pop(CACHE_SCHEMA_NOTICE_KEY, None)


__all__ = ['CACHE_SCHEMA_VERSION', 'enforce_cache_schema_guard', 'render_cache_schema_notice']