from __future__ import annotations

import re

import streamlit as st

CUSTOM_IMPORT_LINK_KEY = 'custom_final_import_link_url'
CUSTOM_IMPORT_LABEL_KEY = 'custom_final_import_link_label'
DEFAULT_BUTTON_LABEL = 'Abrir link personalizado'
RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_links_panel.py'

_URL_RE = re.compile(r'^https?://[^\s]+$', re.IGNORECASE)


def _clean_url(value: object) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if not text.lower().startswith(('http://', 'https://')):
        text = 'https://' + text
    return text.strip()


def _valid_url(value: str) -> bool:
    return bool(_URL_RE.match(str(value or '').strip()))


def _button_label(value: object) -> str:
    text = str(value or '').strip()
    return text or DEFAULT_BUTTON_LABEL


def render_bling_links_panel() -> None:
    """Renderiza link final configurável sem citar marca/plataforma externa.

    Regra comercial/white-label:
    - não exibir nomes comerciais fixos;
    - não manter URLs fixas para empresas específicas;
    - o usuário informa o destino desejado;
    - o destino salvo vira um botão clicável no final do fluxo.
    """
    st.markdown('#### Link final personalizado')
    st.caption('Configure aqui o link que deve aparecer como botão no final. O sistema não usa links comerciais fixos.')

    current_url = str(st.session_state.get(CUSTOM_IMPORT_LINK_KEY) or '').strip()
    current_label = str(st.session_state.get(CUSTOM_IMPORT_LABEL_KEY) or DEFAULT_BUTTON_LABEL).strip()

    with st.container(border=True):
        label = st.text_input(
            'Texto do botão',
            value=current_label,
            key='custom_final_import_link_label_input',
            placeholder='Exemplo: Abrir painel de importação',
        )
        raw_url = st.text_input(
            'Link de destino',
            value=current_url,
            key='custom_final_import_link_url_input',
            placeholder='https://...',
            help='Cole o link que você quer abrir ao clicar no botão final.',
        )

        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button('Salvar link do botão', use_container_width=True, key='custom_final_import_link_save'):
                clean_url = _clean_url(raw_url)
                if not _valid_url(clean_url):
                    st.warning('Informe um link válido começando com http:// ou https://.')
                else:
                    st.session_state[CUSTOM_IMPORT_LINK_KEY] = clean_url
                    st.session_state[CUSTOM_IMPORT_LABEL_KEY] = _button_label(label)
                    st.success('Link personalizado salvo. O botão abaixo já usa esse destino.')
        with col_clear:
            if st.button('Remover link salvo', use_container_width=True, key='custom_final_import_link_clear'):
                st.session_state.pop(CUSTOM_IMPORT_LINK_KEY, None)
                st.session_state.pop(CUSTOM_IMPORT_LABEL_KEY, None)
                st.info('Link personalizado removido.')

    saved_url = str(st.session_state.get(CUSTOM_IMPORT_LINK_KEY) or '').strip()
    saved_label = _button_label(st.session_state.get(CUSTOM_IMPORT_LABEL_KEY))
    if saved_url:
        st.link_button(saved_label, saved_url, use_container_width=True)
    else:
        st.info('Nenhum link personalizado salvo ainda. Salve um link para liberar o botão final.')


__all__ = [
    'CUSTOM_IMPORT_LABEL_KEY',
    'CUSTOM_IMPORT_LINK_KEY',
    'render_bling_links_panel',
]
