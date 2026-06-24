from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.adapters.streamlit_action_executor import FLOW_MENU_KEY, LOG_MENU_KEY, execute_app_action, hard_reset_session
from bling_app_zero.adapters.streamlit_shortcut_executor import execute_shortcut, go_home
from bling_app_zero.core.app_actions import BOTTOM_BAR_ACTIONS
from bling_app_zero.core.diagnostics_model import build_diagnostic_snapshot
from bling_app_zero.ui.master_reset import master_reset_to_home, reusable_origin_available, reuse_origin_for_new_operation
from bling_app_zero.ui.support_diagnostic_panel import render_support_diagnostic_panel_content

RESPONSIBLE_FILE = 'bling_app_zero/ui/bottom_nav_modern.py'
BLING_IMPORTADOR_PRODUTOS_URL = 'https://www.bling.com.br/' + 'importador.produtos.php'
BLING_IMPORTADOR_ESTOQUE_URL = 'https://www.bling.com.br/' + 'importador.saldos.estoque.php'
BLING_IMPORTADOR_PRECOS_MULTILOJA_URL = 'https://www.bling.com.br/' + 'importador.precos.produtos.multiloja.php'
BLING_MODELO_PRODUTOS_URL = 'https://www.bling.com.br/downloads/produtos.zip'
BLING_MODELO_SALDO_ESTOQUE_URL = 'https://www.bling.com.br/downloads/saldo_estoque.csv.zip'
RESET_CONFIRM_KEY = 'sidebar_new_operation_reset_confirmation'


def _run_sidebar_action(action: object) -> None:
    result = execute_app_action(action)
    if result.needs_rerun:
        st.rerun()


def _render_operation_controls() -> None:
    st.markdown('### Operação')
    st.caption('Inicie do zero ou use novamente os produtos já carregados.')

    origin_ready = reusable_origin_available(st.session_state)
    if st.button(
        'Reutilizar dados da origem',
        use_container_width=True,
        key='sidebar_reuse_origin_operation',
        disabled=not origin_ready,
        help='Mantém os produtos carregados e limpa modelo, preços, mapeamento e resultados anteriores.',
    ):
        st.session_state.pop(RESET_CONFIRM_KEY, None)
        if reuse_origin_for_new_operation():
            st.rerun()
        st.warning('Não encontrei dados de origem válidos para reaproveitar.')

    if not origin_ready:
        st.caption('Disponível depois que um arquivo ou uma busca por site carregar produtos.')

    if st.button(
        'Nova operação do zero',
        use_container_width=True,
        key='sidebar_new_operation_from_zero',
        type='secondary',
        help='Apaga os dados do fluxo atual, mas mantém a conexão com o Bling.',
    ):
        st.session_state[RESET_CONFIRM_KEY] = True

    if bool(st.session_state.get(RESET_CONFIRM_KEY)):
        st.warning('Esta ação apagará origem, modelo, mapeamento, preços e resultados da operação atual.')
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button('Confirmar limpeza', use_container_width=True, key='sidebar_confirm_new_operation'):
                st.session_state.pop(RESET_CONFIRM_KEY, None)
                master_reset_to_home()
                st.rerun()
        with cancel_col:
            if st.button('Cancelar', use_container_width=True, key='sidebar_cancel_new_operation'):
                st.session_state.pop(RESET_CONFIRM_KEY, None)
                st.rerun()

    st.divider()


def render_persistent_operation_controls() -> None:
    """Renderiza cedo somente os dois comandos essenciais e leves."""
    with st.sidebar:
        _render_operation_controls()


def _render_sidebar_action_buttons() -> None:
    st.caption('Ferramentas rápidas do sistema.')
    for action in BOTTOM_BAR_ACTIONS:
        if st.button(action.title, use_container_width=True, key=f'sidebar_system_action_{action.key}'):
            _run_sidebar_action(action.key)
    st.link_button('📥 Importar produtos no Bling', BLING_IMPORTADOR_PRODUTOS_URL, use_container_width=True)
    st.link_button('📄 Baixar modelo oficial de produtos', BLING_MODELO_PRODUTOS_URL, use_container_width=True)
    st.link_button('📄 Baixar modelo saldo de estoque', BLING_MODELO_SALDO_ESTOQUE_URL, use_container_width=True)
    st.link_button('📦 Importar saldos de estoque no Bling', BLING_IMPORTADOR_ESTOQUE_URL, use_container_width=True)
    st.link_button('💰 Importar preços multiloja no Bling', BLING_IMPORTADOR_PRECOS_MULTILOJA_URL, use_container_width=True)


def _render_shortcuts_menu() -> None:
    if not bool(st.session_state.get(FLOW_MENU_KEY)):
        return
    with st.expander('⚡ Atalhos rápidos', expanded=True):
        st.caption('Acesse rapidamente as principais ações do sistema.')
        from bling_app_zero.core.app_shortcuts import grouped_shortcuts

        for group, shortcuts in grouped_shortcuts():
            st.markdown(f'##### {group}')
            columns = st.columns(min(2, max(1, len(shortcuts))))
            for index, shortcut in enumerate(shortcuts):
                with columns[index % len(columns)]:
                    if st.button(shortcut.title, use_container_width=True, key=f'sidebar_shortcut_{shortcut.key}'):
                        result = execute_shortcut(shortcut, home_callback=go_home)
                        if result.needs_rerun:
                            st.rerun()


def _render_diagnostic_menu() -> None:
    if not bool(st.session_state.get(LOG_MENU_KEY)):
        return
    with st.expander('🧪 Diagnóstico', expanded=True):
        render_support_diagnostic_panel_content(namespace='bottom_nav')
        st.divider()
        snapshot = build_diagnostic_snapshot(dict(st.session_state))
        st.caption(
            f'Caminho atual: {snapshot.active_flow} · Etapa: {snapshot.step} · '
            f'Operação: {snapshot.operation} · Origem: {snapshot.origin}'
        )
        rows = [{'dado': item.label, 'tamanho': item.value} for item in snapshot.data_items]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption('Nenhum dado principal carregado nesta sessão.')
        if st.button('🧹 Limpeza total da sessão', use_container_width=True, key='sidebar_hard_reset_confirm'):
            hard_reset_session(after_reset=go_home)
            st.rerun()


def render_bottom_nav() -> None:
    """Renderiza ferramentas secundárias após o conteúdo principal."""
    with st.sidebar:
        st.markdown('### Sistema')
        _render_sidebar_action_buttons()
        _render_shortcuts_menu()
        _render_diagnostic_menu()


__all__ = [
    'BLING_IMPORTADOR_ESTOQUE_URL',
    'BLING_IMPORTADOR_PRECOS_MULTILOJA_URL',
    'BLING_IMPORTADOR_PRODUTOS_URL',
    'BLING_MODELO_PRODUTOS_URL',
    'BLING_MODELO_SALDO_ESTOQUE_URL',
    'render_bottom_nav',
    'render_persistent_operation_controls',
]
