from __future__ import annotations

import html
from typing import Any, Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.flow_context import CONTEXT_BLING_API, FINISH_MODE_API

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_api_source_first_policy.py'
_PATCH_KEY = 'bling_api_source_first_policy_installed_v1'


def _patch_oauth_return_to_api_origin() -> None:
    """Garante que o callback OAuth volte para o mesmo núcleo, em modo API e na etapa Origem."""
    from bling_app_zero.core import bling_oauth

    if getattr(bling_oauth, '_blingfix_api_source_first_oauth_patch_installed', False):
        return

    def restore_api_source_first_flow(payload: dict[str, Any]) -> None:
        store = bling_oauth._state_store()
        store['home_active_operation_v2'] = bling_oauth.FLOW_WIZARD
        store['home_allow_operation_v2_session'] = True
        store['home_single_page_flow_active'] = True
        store[bling_oauth.HOME_BOOT_LOCK_KEY] = True
        store['home_entry_context'] = CONTEXT_BLING_API
        store['home_slim_entry_context'] = CONTEXT_BLING_API
        store['mapeiaai_home_entry_path'] = 'bling_api'
        store['mapeiaai_flow_kind'] = 'bling_api'
        store['flow_kind'] = 'bling_api'
        store['api_flow_active'] = True
        store['bling_connected_api_flow_active'] = True
        store[bling_oauth.UNIFIED_BLING_SEND_KEY] = True
        store['bling_finish_mode'] = FINISH_MODE_API
        store['finish_mode'] = FINISH_MODE_API
        store['bling_wizard_step'] = bling_oauth.STEP_ORIGEM
        store['home_wizard_step'] = bling_oauth.STEP_ORIGEM
        store[bling_oauth.HOME_FLOW_SCHEMA_KEY] = bling_oauth.HOME_FLOW_SCHEMA_VERSION
        store['bling_api_manual_mapping_required'] = False
        store['bling_api_mapping_locked_by_api'] = True
        store.pop('mapear_planilha_sem_api_active', None)
        store.pop('skip_direct_bling_connection_this_flow', None)
        store.pop('home_bling_auth_ready_url', None)

        qp = bling_oauth._query_params_store()
        try:
            qp['operation_v2'] = bling_oauth.FLOW_WIZARD
            qp['step'] = bling_oauth.STEP_ORIGEM
            for key in ('flow', 'origem', 'operacao', 'operation'):
                qp.pop(key, None)
        except Exception:
            pass

        add_audit_event(
            'bling_oauth_return_restored_to_api_origin',
            area='BLING_OAUTH',
            status='OK',
            details={
                'return_to': payload.get('return_to') or '',
                'source_step': payload.get('source_step') or '',
                'operation_v2': bling_oauth.FLOW_WIZARD,
                'step': bling_oauth.STEP_ORIGEM,
                'home_entry_context': CONTEXT_BLING_API,
                'finish_mode': FINISH_MODE_API,
                'manual_mapping_allowed': False,
                'schema_version': bling_oauth.HOME_FLOW_SCHEMA_VERSION,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    bling_oauth._blingfix_original_restore_unified_bling_flow = getattr(bling_oauth, '_restore_unified_bling_flow', None)
    bling_oauth._restore_unified_bling_flow = restore_api_source_first_flow
    bling_oauth._blingfix_api_source_first_oauth_patch_installed = True


def _render_auth_link_card(official: Any, legacy: Any) -> None:
    with official._safe_container_with_border():
        st.markdown(
            '<div class="mapeiaai-official-card-body">'
            '<div class="mapeiaai-official-card-title">Conectar ao Bling</div>'
            '<p class="mapeiaai-official-card-text">Com API. Autentica no Bling e volta para Origem dos dados: buscar produtos em site ou anexar arquivo. O envio pela API fica no final do mesmo fluxo.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        try:
            auth_url = legacy.build_authorization_url(
                {
                    'return_to': 'start',
                    'source_step': 'bling_connection_entry',
                    'open_mode': 'android_safe',
                    'flow': 'bling_api_source_first',
                }
            )
        except Exception as exc:
            auth_url = ''
            st.warning(f'Não consegui preparar o link do Bling agora: {exc}')

        if auth_url:
            try:
                st.link_button('🔗 Conectar ao Bling', auth_url, use_container_width=True)
            except Exception:
                pass
            safe_url = html.escape(str(auth_url), quote=True)
            st.markdown(
                f'<a href="{safe_url}" target="_top" style="display:block;width:100%;box-sizing:border-box;text-align:center;text-decoration:none;font-weight:900;margin-top:.45rem;padding:.78rem 1rem;border-radius:.78rem;border:1px solid rgba(37,99,235,.28);color:#ffffff;background:#2563eb;">Abrir conexão nesta aba</a>',
                unsafe_allow_html=True,
            )
            st.caption('Depois da autorização, o callback volta para a etapa Origem dos dados no modo API.')
            add_audit_event(
                'official_home_direct_bling_auth_link_rendered',
                area='HOME',
                status='OK',
                details={'target_after_oauth': 'origem', 'entry_context': CONTEXT_BLING_API, 'finish_mode': FINISH_MODE_API, 'responsible_file': RESPONSIBLE_FILE},
            )
        else:
            official._render_bling_connection_panel()


def _patch_official_home_connect_button() -> None:
    """Transforma o card Conectar ao Bling em link direto de OAuth quando não conectado."""
    from bling_app_zero.ui import home_official as official
    import bling_app_zero.ui.home_router as legacy

    if getattr(official, '_blingfix_api_source_first_home_patch_installed', False):
        return

    def render_official_landing_source_first() -> None:
        official._reset_to_official_landing()
        official._install_official_home_css()
        official._run_flow_simulation_audit_once()
        connected = official._bling_is_connected()

        st.markdown('<div class="mapeiaai-official-home-wrap">', unsafe_allow_html=True)
        official._render_system_title()

        if official._render_card(
            'Anexar Modelo / Mapear',
            'Sem API. Primeiro anexe o modelo final, depois busque origem por site ou arquivo, use toggles opcionais, veja o preview e baixe a planilha idêntica.',
            '📄 Anexar Modelo / Mapear Planilha',
            'official_home_mapear_planilha_v3',
        ):
            official._start_mapear_planilha()

        st.markdown('<div style="height:.55rem"></div>', unsafe_allow_html=True)

        if connected:
            if official._render_card(
                'Bling conectado',
                'Com API. Entra direto em Origem dos dados, escolhe Cadastro, Estoque ou Preços, revisa e envia pela API no final.',
                '🔗 Usar Bling conectado',
                'official_home_connect_bling_v3',
            ):
                official._start_or_show_bling_connection(connected=True)
            st.success('Bling conectado. O fluxo API começa em Origem dos dados e usa os mesmos motores do sistema.')
        else:
            _render_auth_link_card(official, legacy)

        st.markdown('</div>', unsafe_allow_html=True)

        add_audit_event(
            'official_home_rendered_source_first_api_cards',
            area='HOME',
            status='OK',
            details={
                'schema': official.OFFICIAL_HOME_SCHEMA,
                'connected': connected,
                'connect_action': 'direct_oauth_link_when_disconnected',
                'api_first_step': 'origem',
                'manual_mapping_allowed_in_api': False,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )

    official._blingfix_original_render_official_landing = getattr(official, '_render_official_landing', None)
    official._render_official_landing = render_official_landing_source_first
    official._blingfix_api_source_first_home_patch_installed = True


def _patch_api_mapping_locked_notice() -> None:
    """Deixa claro que, no modo API, o mapeamento manual está bloqueado."""
    from bling_app_zero.ui import home_wizard

    if getattr(home_wizard, '_blingfix_api_mapping_locked_notice_installed', False):
        return
    original: Callable[..., Any] | None = getattr(home_wizard, '_render_locked_bling_contract', None)
    if original is None:
        return

    def render_locked_bling_contract_with_notice() -> None:
        st.session_state['bling_api_manual_mapping_required'] = False
        st.session_state['bling_api_mapping_locked_by_api'] = True
        st.info('Modo API: o mapeamento manual fica indisponível. O sistema monta automaticamente o contrato da API do Bling usando a origem carregada, os motores e as regras internas.')
        original()

    home_wizard._blingfix_original_render_locked_bling_contract = original
    home_wizard._render_locked_bling_contract = render_locked_bling_contract_with_notice
    home_wizard._blingfix_api_mapping_locked_notice_installed = True


def install_bling_api_source_first_policy() -> bool:
    if st.session_state.get(_PATCH_KEY):
        return False
    _patch_oauth_return_to_api_origin()
    _patch_official_home_connect_button()
    _patch_api_mapping_locked_notice()
    st.session_state[_PATCH_KEY] = True
    add_audit_event(
        'bling_api_source_first_policy_installed',
        area='APP',
        status='OK',
        details={
            'connect_bling_action': 'auth_link_direct',
            'oauth_return_step': 'origem',
            'entry_context': CONTEXT_BLING_API,
            'finish_mode': FINISH_MODE_API,
            'manual_mapping_allowed_in_api': False,
            'same_flow_and_engines': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = ['install_bling_api_source_first_policy']
