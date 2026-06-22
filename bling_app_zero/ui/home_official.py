from __future__ import annotations

import html

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
import bling_app_zero.ui.home_router as legacy
import bling_app_zero.ui.home_router_v2 as router_v2

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_official.py'
OFFICIAL_HOME_SCHEMA = 'official_dual_card_home_20260622_v1'

ROUTE_PARAMS_TO_CLEAR = (
    'step',
    'flow',
    'origem',
    'operacao',
    'operation',
)

FLOW_STATE_KEYS_TO_RESET_ON_LANDING = (
    'home_single_page_flow_active',
    'price_multistore_independent_route_active',
    'mapear_planilha_sem_api_active',
    'mapeiaai_home_entry_path',
)


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ''
    if isinstance(value, list):
        return str(value[0] if value else '').strip()
    return str(value or '').strip()


def _has_explicit_operation_route() -> bool:
    return bool(_query_param('operation_v2').strip())


def _reset_to_official_landing() -> None:
    """Garante que a primeira tela não herde fluxo/cache antigo.

    A Home oficial é sempre o ponto neutro de escolha entre:
    1) Anexar Modelo / Mapear Planilha sem API
    2) Conectar ao Bling com API
    """
    previous_flow = str(st.session_state.get(router_v2.ACTIVE_FLOW_KEY) or '').strip()
    st.session_state[router_v2.ACTIVE_FLOW_KEY] = router_v2.FLOW_HOME
    st.session_state[router_v2.HOME_ALLOW_FLOW_KEY] = False
    st.session_state['mapeiaai_home_schema'] = OFFICIAL_HOME_SCHEMA
    st.session_state['api_flow_active'] = False

    for key in FLOW_STATE_KEYS_TO_RESET_ON_LANDING:
        st.session_state.pop(key, None)

    try:
        for key in ROUTE_PARAMS_TO_CLEAR:
            st.query_params.pop(key, None)
    except Exception:
        pass

    if previous_flow and previous_flow != router_v2.FLOW_HOME:
        add_audit_event(
            'official_home_reset_stale_flow_to_dual_cards',
            area='HOME',
            status='OK',
            details={
                'previous_flow': previous_flow,
                'schema': OFFICIAL_HOME_SCHEMA,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )


def _bling_is_connected() -> bool:
    try:
        status = legacy._effective_bling_status(try_sync=True)
    except Exception as exc:
        add_audit_event(
            'official_home_bling_status_check_failed',
            area='HOME',
            status='AVISO',
            details={'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
        )
        return False
    return bool(status.get('connected')) if isinstance(status, dict) else False


def _render_bling_connection_panel() -> None:
    try:
        auth_url = legacy.build_authorization_url({'return_to': 'mapeiaai_home_bling', 'open_mode': 'android_safe'})
    except Exception as exc:
        auth_url = ''
        st.warning(f'Não consegui preparar o link do Bling agora: {exc}')
    legacy._render_bling_connection(auth_url)


def _safe_container_with_border():
    try:
        return st.container(border=True)
    except TypeError:
        return st.container()


def _install_official_home_css() -> None:
    st.markdown(
        '''
<style>
.mapeiaai-official-home-wrap{
  max-width: 760px;
  margin: .15rem auto 1rem auto;
}
.mapeiaai-official-card-body{
  border:1px solid rgba(15,23,42,.08);
  background:#fff;
  border-radius:18px;
  padding:1rem 1.05rem;
  margin:.1rem 0 .6rem 0;
}
.mapeiaai-official-card-title{
  font-size:1.08rem;
  line-height:1.2;
  font-weight:900;
  color:#0f172a;
  margin:0 0 .55rem 0;
}
.mapeiaai-official-card-text{
  font-size:.96rem;
  line-height:1.72;
  color:#64748b;
  margin:0;
}
@media (max-width: 768px), (pointer: coarse) and (max-width: 980px){
  .mapeiaai-official-home-wrap{max-width:100%;margin:.05rem 0 .8rem 0;}
  .mapeiaai-official-card-body{padding:1rem .95rem;border-radius:18px;}
  .mapeiaai-official-card-title{font-size:1.05rem;}
  .mapeiaai-official-card-text{font-size:.94rem;line-height:1.78;}
}
</style>
''',
        unsafe_allow_html=True,
    )


def _render_card(title: str, body: str, button_label: str, button_key: str) -> bool:
    with _safe_container_with_border():
        st.markdown(
            '<div class="mapeiaai-official-card-body">'
            f'<div class="mapeiaai-official-card-title">{html.escape(title)}</div>'
            f'<p class="mapeiaai-official-card-text">{html.escape(body)}</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return st.button(button_label, use_container_width=True, key=button_key)


def _start_mapear_planilha() -> None:
    try:
        router_v2._clear_universal_operation_state(keep_model=False)
    except Exception:
        pass
    router_v2.start_mapear_planilha_flow()
    add_audit_event(
        'official_home_start_mapear_planilha',
        area='HOME',
        status='OK',
        details={'schema': OFFICIAL_HOME_SCHEMA, 'responsible_file': RESPONSIBLE_FILE},
    )
    st.rerun()


def _start_or_show_bling_connection(*, connected: bool) -> None:
    if connected:
        router_v2.start_bling_api_flow()
        add_audit_event(
            'official_home_start_bling_api_connected',
            area='HOME',
            status='OK',
            details={'schema': OFFICIAL_HOME_SCHEMA, 'first_step': 'origem', 'responsible_file': RESPONSIBLE_FILE},
        )
        st.rerun()
        return

    st.session_state['home_show_bling_connection_panel_v2'] = True
    add_audit_event(
        'official_home_show_bling_connection_panel',
        area='HOME',
        status='OK',
        details={'schema': OFFICIAL_HOME_SCHEMA, 'responsible_file': RESPONSIBLE_FILE},
    )
    st.rerun()


def _render_official_landing() -> None:
    _reset_to_official_landing()
    _install_official_home_css()
    connected = _bling_is_connected()

    st.markdown('<div class="mapeiaai-official-home-wrap">', unsafe_allow_html=True)

    if _render_card(
        'Anexar Modelo / Mapear',
        'Sem API. Primeiro anexe o modelo final, depois busque origem por site ou arquivo, use toggles opcionais, veja o preview e baixe a planilha idêntica.',
        '📄 Anexar Modelo / Mapear Planilha',
        'official_home_mapear_planilha_v1',
    ):
        _start_mapear_planilha()

    st.markdown('<div style="height:.55rem"></div>', unsafe_allow_html=True)

    if _render_card(
        'Conectar ao Bling',
        'Com API. Conecta ao Bling, cai em origem de dados, escolhe Atualizar Estoque, Cadastro ou Atualizar Produtos, revisa e envia.',
        '🔗 Conectar ao Bling',
        'official_home_connect_bling_v1',
    ):
        _start_or_show_bling_connection(connected=connected)

    if bool(st.session_state.get('home_show_bling_connection_panel_v2')) and not connected:
        st.markdown('---')
        st.markdown('### Conectar ao Bling')
        _render_bling_connection_panel()

    st.markdown('</div>', unsafe_allow_html=True)

    add_audit_event(
        'official_home_rendered_dual_cards',
        area='HOME',
        status='OK',
        details={
            'schema': OFFICIAL_HOME_SCHEMA,
            'connected': connected,
            'cards': ['Anexar Modelo / Mapear', 'Conectar ao Bling'],
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def render_home() -> None:
    if _has_explicit_operation_route():
        router_v2.render_home()
        return
    _render_official_landing()


__all__ = ['render_home']
