from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.v2.price_multistore.ui_plus import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_MULTISTORE = 'price_multistore_v2'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'


def _set_flow(flow: str) -> None:
    previous = st.session_state.get(ACTIVE_FLOW_KEY)
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    add_audit_event(
        'home_operation_selected',
        area='HOME',
        details={'previous': previous, 'selected': flow, 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['operation_v2'] = flow
    except Exception:
        pass
    st.rerun()


def _clear_flow_query_param() -> None:
    for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass


def _current_flow() -> str:
    """Mantém a Home como tela inicial real.

    BLINGFIX HOME NASCIMENTO:
    A URL antiga com ``operation_v2`` estava fazendo o app nascer direto dentro
    do wizard, mesmo após recarregar no mobile. Agora o fluxo só abre quando o
    clique aconteceu nesta sessão. URL velha é limpa e volta para a Home.
    """
    allowed = bool(st.session_state.get(HOME_ALLOW_FLOW_KEY))
    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if allowed and flow:
        return flow

    stale_flow = st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    if stale_flow:
        add_audit_event(
            'home_stale_flow_cleared',
            area='HOME',
            details={
                'reason': 'home_must_start_on_operation_choice',
                'stale_flow': stale_flow,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    return ''


def _open_cadastro_flow() -> None:
    st.session_state['home_slim_flow_operation'] = 'cadastro'
    _set_flow(FLOW_WIZARD)


def _open_estoque_flow() -> None:
    st.session_state['home_slim_flow_operation'] = 'estoque'
    _set_flow(FLOW_WIZARD)


def _open_multistore_price_flow() -> None:
    _set_flow(FLOW_PRICE_MULTISTORE)


def _render_group_title(title: str, caption: str) -> None:
    st.markdown(f'### {title}')
    st.caption(caption)


def _render_home_operation_card(
    *,
    icon: str,
    title: str,
    description: str,
    button_label: str,
    button_key: str,
    on_click: Callable[[], None],
    badge: str | None = None,
) -> None:
    """Renderiza cada operação dentro do próprio card."""
    with st.container(border=True):
        if badge:
            st.caption(badge)
        st.markdown(f'#### {icon} {title}')
        st.caption(description)
        if st.button(button_label, use_container_width=True, key=button_key):
            on_click()


def _render_operation_choice() -> None:
    st.markdown('### O que você quer fazer?')
    st.caption('Escolha primeiro o tipo de trabalho. O fluxo principal começa pelo modelo do Bling para evitar erro de planilha no final.')

    _render_group_title(
        'Fluxo principal',
        'Use estes caminhos para gerar CSV oficial de cadastro ou estoque do Bling.',
    )
    _render_home_operation_card(
        icon='🧾',
        title='Cadastrar produtos',
        description='Usar modelo salvo ou anexar modelo do Bling, carregar produtos por planilha/XML/PDF/site, mapear campos e gerar CSV de cadastro.',
        button_label='Abrir cadastro',
        button_key='home_open_cadastro_flow',
        on_click=_open_cadastro_flow,
        badge='Fluxo principal',
    )
    _render_home_operation_card(
        icon='📦',
        title='Atualizar estoque',
        description='Usar modelo salvo ou anexar modelo de estoque, carregar origem dos dados, preencher saldo/depósito e gerar CSV de atualização.',
        button_label='Abrir estoque',
        button_key='home_open_estoque_flow',
        on_click=_open_estoque_flow,
        badge='Fluxo principal',
    )

    st.divider()
    _render_group_title(
        'Módulos adicionais',
        'Ferramentas separadas do fluxo principal. Use quando precisar de uma função específica.',
    )
    _render_home_operation_card(
        icon='🏬',
        title='Atualizar Preços Multiloja',
        description='Módulo específico para atualizar preços por marketplace com ID na Loja, Preço e Preço Promocional. Aceita upload, captura por site ou tabela/exportação importada como origem de custo.',
        button_label='Atualizar preços',
        button_key='home_open_multistore_price_flow',
        on_click=_open_multistore_price_flow,
        badge='Módulo adicional',
    )


def _render_back_to_operations() -> None:
    st.caption('Voltar aqui mantém o progresso salvo nesta sessão. Use “Recomeçar fluxo” dentro do download quando quiser limpar tudo.')
    if st.button('← Voltar para escolha da operação', use_container_width=True, key='home_back_to_operation_choice'):
        st.session_state.pop(ACTIVE_FLOW_KEY, None)
        st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
        _clear_flow_query_param()
        add_audit_event(
            'home_operation_cleared',
            area='HOME',
            details={'kept_wizard_progress': True, 'responsible_file': RESPONSIBLE_FILE},
        )
        st.rerun()


def render_home_router() -> None:
    flow = _current_flow()
    if not flow:
        _render_operation_choice()
        return

    _render_back_to_operations()
    if flow == FLOW_PRICE_MULTISTORE:
        render_price_multistore_v2()
        return

    render_home_wizard()


__all__ = ['render_home_router']
