from __future__ import annotations

import re
from typing import Any

import streamlit as st

CUSTOM_IMPORT_LINKS_KEY = 'custom_final_import_links_v2'
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


def _empty_links() -> list[dict[str, str]]:
    return []


def _normalize_links(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return _empty_links()
    links: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        label = _button_label(item.get('label'))
        url = _clean_url(item.get('url'))
        if not _valid_url(url):
            continue
        key = (label, url)
        if key in seen:
            continue
        seen.add(key)
        links.append({'label': label, 'url': url})
    return links


def _load_links() -> list[dict[str, str]]:
    links = _normalize_links(st.session_state.get(CUSTOM_IMPORT_LINKS_KEY))

    # Migração silenciosa do formato antigo de link único para lista.
    old_url = _clean_url(st.session_state.get(CUSTOM_IMPORT_LINK_KEY))
    old_label = _button_label(st.session_state.get(CUSTOM_IMPORT_LABEL_KEY))
    if _valid_url(old_url) and not any(link['url'] == old_url for link in links):
        links.append({'label': old_label, 'url': old_url})
        st.session_state[CUSTOM_IMPORT_LINKS_KEY] = links
    return links


def _save_links(links: list[dict[str, str]]) -> None:
    st.session_state[CUSTOM_IMPORT_LINKS_KEY] = _normalize_links(links)


def _add_link(label: str, raw_url: str) -> tuple[bool, str]:
    clean_url = _clean_url(raw_url)
    if not _valid_url(clean_url):
        return False, 'Informe um link válido começando com http:// ou https://.'

    links = _load_links()
    new_item = {'label': _button_label(label), 'url': clean_url}
    if any(item['label'] == new_item['label'] and item['url'] == new_item['url'] for item in links):
        return False, 'Esse botão já está salvo.'

    links.append(new_item)
    _save_links(links)
    return True, 'Link personalizado salvo. O botão já aparece na lista.'


def _remove_link(index: int) -> None:
    links = _load_links()
    if 0 <= index < len(links):
        links.pop(index)
    _save_links(links)


def _clear_all_links() -> None:
    st.session_state.pop(CUSTOM_IMPORT_LINKS_KEY, None)
    st.session_state.pop(CUSTOM_IMPORT_LINK_KEY, None)
    st.session_state.pop(CUSTOM_IMPORT_LABEL_KEY, None)


def _render_saved_buttons(links: list[dict[str, str]]) -> None:
    if not links:
        st.info('Nenhum link personalizado salvo ainda. Adicione um link para liberar os botões finais.')
        return

    st.caption(f'{len(links)} botão(ões) personalizado(s) salvo(s).')
    for index, item in enumerate(links):
        col_link, col_remove = st.columns([4, 1])
        with col_link:
            st.link_button(item['label'], item['url'], use_container_width=True)
        with col_remove:
            if st.button('Remover', use_container_width=True, key=f'custom_final_import_link_remove_{index}'):
                _remove_link(index)
                st.rerun()


def render_bling_links_panel() -> None:
    """Renderiza botões finais configuráveis sem citar marca/plataforma externa.

    Regra comercial/white-label:
    - não exibir nomes comerciais fixos;
    - não manter URLs fixas para empresas específicas;
    - o usuário informa quantos destinos quiser;
    - cada destino salvo vira um botão clicável no final do fluxo.
    """
    st.markdown('#### Links finais personalizados')
    st.caption('Cadastre os botões que devem aparecer no final. O sistema não usa nomes nem links comerciais fixos.')

    with st.expander('Configurar links personalizados', expanded=False):
        label = st.text_input(
            'Texto do botão',
            value='',
            key='custom_final_import_link_label_input',
            placeholder='Exemplo: Abrir painel de importação',
        )
        raw_url = st.text_input(
            'Link de destino',
            value='',
            key='custom_final_import_link_url_input',
            placeholder='https://...',
            help='Cole o link que você quer abrir ao clicar no botão final.',
        )

        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button('Adicionar botão', use_container_width=True, key='custom_final_import_link_add'):
                ok, message = _add_link(label, raw_url)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.warning(message)
        with col_clear:
            if st.button('Remover todos', use_container_width=True, key='custom_final_import_link_clear_all'):
                _clear_all_links()
                st.info('Todos os links personalizados foram removidos.')
                st.rerun()

        st.divider()
        _render_saved_buttons(_load_links())

    _render_saved_buttons(_load_links())


__all__ = [
    'CUSTOM_IMPORT_LABEL_KEY',
    'CUSTOM_IMPORT_LINK_KEY',
    'CUSTOM_IMPORT_LINKS_KEY',
    'render_bling_links_panel',
]
