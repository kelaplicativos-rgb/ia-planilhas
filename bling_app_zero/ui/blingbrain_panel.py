from __future__ import annotations

import streamlit as st

from bling_app_zero.ai_tools import build_blingbrain_response


EXAMPLES = [
    'Revisar descrições antes do download final',
    'Reformular títulos dos produtos',
    'Procurar a palavra bluetooth nas descrições',
    'Sugerir NCM para revisão manual',
    'Verificar GTINs inválidos e gerar SKU interno quando faltar código',
]


def _current_context() -> tuple[str, str]:
    etapa = str(
        st.session_state.get('etapa_fluxo')
        or st.session_state.get('etapa')
        or st.session_state.get('home_slim_step')
        or 'etapa atual'
    )
    operacao = str(
        st.session_state.get('tipo_operacao')
        or st.session_state.get('operacao_final')
        or st.session_state.get('home_slim_flow_operation')
        or 'fluxo atual'
    )
    return etapa, operacao


def _render_examples() -> None:
    with st.expander('Exemplos de pedidos para o BlingBrain', expanded=False):
        for example in EXAMPLES:
            st.markdown(f'- {example}')


def render_blingbrain_panel() -> None:
    st.markdown('##### 🧠 BlingBrain')
    st.caption('Peça ajuda da IA nos fluxos. Ela orienta e prepara revisões sem alterar o CSV automaticamente.')

    etapa, operacao = _current_context()
    st.caption(f'Contexto detectado: {operacao} · {etapa}')

    prompt = st.text_area(
        'O que você quer que a IA ajude a fazer?',
        key='blingbrain_prompt',
        height=90,
        placeholder='Ex: reformule as descrições antes do download final',
    )
    _render_examples()

    if st.button('Pedir ajuda ao BlingBrain', use_container_width=True, key='blingbrain_ask'):
        st.session_state['blingbrain_response'] = build_blingbrain_response(prompt, etapa=etapa, operacao=operacao)

    response = st.session_state.get('blingbrain_response')
    if not response:
        st.info('Digite uma solicitação para receber um plano seguro de ação.')
        return

    st.success(response.title)
    st.caption(response.safety)
    st.markdown('**Plano sugerido:**')
    for step in response.steps:
        st.markdown(f'- {step}')

    if response.action_type in {'descricao', 'titulo', 'ncm', 'gtin'}:
        st.warning('Primeira versão: orientação segura. A aplicação automática em massa deve entrar em uma próxima etapa com preview antes/depois.')
