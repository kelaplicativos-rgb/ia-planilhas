from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_links_panel.py'

LINKS_STATE_KEY = 'bling_post_download_links_v2'
LINKS_EDIT_MODE_KEY = 'bling_post_download_links_edit_mode'
LINKS_FORM_LABEL_KEY = 'bling_post_download_link_label'
LINKS_FORM_URL_KEY = 'bling_post_download_link_url'
LINKS_FORM_HINT_KEY = 'bling_post_download_link_hint'

HOME_ACTIVE_OPERATION_KEY = 'home_active_operation_v2'
HOME_ALLOW_OPERATION_KEY = 'home_allow_operation_v2_session'
FLOW_PRICE_MULTISTORE = 'price_multistore_v2'
VALID_OPERATIONS = {'cadastro', 'estoque'}

DEFAULT_POST_DOWNLOAD_LINKS: list[dict[str, str]] = [
    {
        'label': 'Importar / atualizar produtos no Bling',
        'url': 'https://www.bling.com.br/importador.produtos.php',
        'hint': 'Use este caminho quando o CSV final for para cadastro ou atualização de produtos.',
        'operation': 'cadastro',
        'kind': 'bling',
    },
    {
        'label': 'Importar / atualizar estoque no Bling',
        'url': 'https://www.bling.com.br/importador.saldos.estoque.php',
        'hint': 'Use este caminho quando o CSV final for para saldo, balanço ou atualização de estoque.',
        'operation': 'estoque',
        'kind': 'bling',
    },
    {
        'label': 'Atualizar preços / vínculos multiloja no Bling',
        'url': 'https://www.bling.com.br/importador.precos.produtos.multiloja.php',
        'hint': 'Use depois do cadastro quando precisar importar preços por loja, canal ou multiloja.',
        'operation': 'cadastro',
        'kind': 'bling',
    },
    {
        'label': 'Central de ajuda do Bling',
        'url': 'https://ajuda.bling.com.br/hc/pt-br',
        'hint': 'Consulte a documentação oficial se o Bling mudar alguma tela de importação.',
        'operation': 'todos',
        'kind': 'help',
    },
]


def _normalize_text(value: object) -> str:
    return str(value or '').strip()


def _normalize_operation(value: object) -> str:
    text = _normalize_text(value).lower()
    if text in VALID_OPERATIONS:
        return text
    if 'estoque' in text:
        return 'estoque'
    return 'cadastro'


def _current_operation() -> str:
    for key in (
        'df_final_download_operation',
        'tipo_operacao_site',
        'operacao_final',
        'tipo_operacao_final',
        'home_slim_flow_operation',
        'home_detected_operation',
    ):
        operation = _normalize_operation(st.session_state.get(key))
        if operation in VALID_OPERATIONS:
            return operation

    try:
        operation = _normalize_operation(st.query_params.get('operacao', ''))
        if operation in VALID_OPERATIONS:
            return operation
    except Exception:
        pass

    return 'cadastro'


def _normalize_url(value: object) -> str:
    url = _normalize_text(value)
    if not url:
        return ''
    if not url.startswith(('http://', 'https://')):
        url = f'https://{url}'
    return url


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)
    except Exception:
        return False


def _copy_default_links() -> list[dict[str, str]]:
    return [dict(item) for item in DEFAULT_POST_DOWNLOAD_LINKS]


def _sanitize_link(item: object) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None

    label = _normalize_text(item.get('label'))[:90]
    url = _normalize_url(item.get('url'))
    hint = _normalize_text(item.get('hint'))[:180]
    operation = _normalize_text(item.get('operation')).lower() or 'todos'
    kind = _normalize_text(item.get('kind')).lower() or 'custom'

    if operation not in {'cadastro', 'estoque', 'todos'}:
        operation = 'todos'

    if not label or not url or not _is_valid_url(url):
        return None

    return {
        'label': label,
        'url': url,
        'hint': hint or 'Link personalizado do usuário.',
        'operation': operation,
        'kind': kind,
    }


def _dedupe_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    clean_links: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in links:
        clean = _sanitize_link(item)
        if not clean:
            continue

        identity = (clean['label'].lower(), clean['url'].lower())
        if identity in seen:
            continue

        seen.add(identity)
        clean_links.append(clean)

    return clean_links


def _ensure_links_state() -> None:
    current = st.session_state.get(LINKS_STATE_KEY)
    if not isinstance(current, list):
        st.session_state[LINKS_STATE_KEY] = _copy_default_links()
        add_audit_event(
            'post_download_links_initialized',
            area='DOWNLOAD_LINKS',
            status='OK',
            details={
                'links_count': len(DEFAULT_POST_DOWNLOAD_LINKS),
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return

    st.session_state[LINKS_STATE_KEY] = _dedupe_links(current)


def _get_links() -> list[dict[str, str]]:
    _ensure_links_state()
    return list(st.session_state.get(LINKS_STATE_KEY) or [])


def _save_links(links: list[dict[str, str]], event_name: str = 'post_download_links_saved') -> None:
    clean_links = _dedupe_links(links)
    st.session_state[LINKS_STATE_KEY] = clean_links
    add_audit_event(
        event_name,
        area='DOWNLOAD_LINKS',
        status='OK',
        details={
            'links_count': len(clean_links),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _reset_links() -> None:
    _save_links(_copy_default_links(), event_name='post_download_links_reset')


def _visible_links_for_operation(operation: str) -> list[tuple[int, dict[str, str]]]:
    visible: list[tuple[int, dict[str, str]]] = []
    for index, item in enumerate(_get_links()):
        item_operation = _normalize_text(item.get('operation')).lower() or 'todos'
        if item_operation in {'todos', operation}:
            visible.append((index, item))
    return visible


def _recommended_links(operation: str) -> list[tuple[int, dict[str, str]]]:
    visible = _visible_links_for_operation(operation)
    if operation == 'estoque':
        return sorted(visible, key=lambda pair: 0 if pair[1].get('operation') == 'estoque' else 1)
    return sorted(visible, key=lambda pair: 0 if pair[1].get('operation') == 'cadastro' else 1)


def _start_price_multistore_flow() -> None:
    st.session_state[HOME_ACTIVE_OPERATION_KEY] = FLOW_PRICE_MULTISTORE
    st.session_state[HOME_ALLOW_OPERATION_KEY] = True
    st.session_state['home_single_page_flow_active'] = True

    try:
        st.query_params['operation_v2'] = FLOW_PRICE_MULTISTORE
        st.query_params.pop('step', None)
        st.query_params.pop('operacao', None)
        st.query_params.pop('origem', None)
        st.query_params.pop('flow', None)
    except Exception:
        pass

    add_audit_event(
        'post_download_price_multistore_opened',
        area='DOWNLOAD_LINKS',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE},
    )
    st.rerun()


def _render_next_flow_card(operation: str) -> None:
    st.markdown('#### Continuar no sistema')

    if operation == 'cadastro':
        st.info(
            'Depois de baixar o CSV de cadastro, o próximo passo comum é atualizar preços/vínculos por loja ou importar o arquivo no Bling.',
            icon='➡️',
        )
        if st.button(
            'Abrir fluxo de atualizar preços multiloja',
            use_container_width=True,
            key='post_download_open_price_multistore',
        ):
            _start_price_multistore_flow()
    else:
        st.info(
            'Depois de baixar o CSV de estoque, importe o arquivo no Bling pelo importador de saldos/estoque.',
            icon='➡️',
        )


def _render_link_button(item: dict[str, str], index: int) -> None:
    label = _normalize_text(item.get('label')) or 'Abrir link'
    url = _normalize_url(item.get('url'))
    hint = _normalize_text(item.get('hint'))

    with st.container(border=True):
        if url and _is_valid_url(url):
            st.link_button(label, url, use_container_width=True)
        else:
            st.warning(f'Link inválido: {label}')

        if hint:
            st.caption(hint)

        add_debug(
            f'Link pós-download exibido: index={index}; label={label}',
            origin='DOWNLOAD_LINKS',
            level='INFO',
        )


def _add_custom_link(label: str, url: str, hint: str, operation: str) -> tuple[bool, str]:
    label = _normalize_text(label)
    url = _normalize_url(url)
    hint = _normalize_text(hint)

    if not label:
        return False, 'Informe o nome do link.'
    if not url or not _is_valid_url(url):
        return False, 'Informe uma URL válida.'

    links = _get_links()
    links.append(
        {
            'label': label,
            'url': url,
            'hint': hint or 'Link personalizado do usuário.',
            'operation': operation if operation in VALID_OPERATIONS else 'todos',
            'kind': 'custom',
        }
    )
    _save_links(links, event_name='post_download_custom_link_added')
    return True, 'Link adicionado aos próximos passos.'


def _delete_link(index: int) -> None:
    links = _get_links()
    if index < 0 or index >= len(links):
        return

    removed = links.pop(index)
    _save_links(links, event_name='post_download_link_deleted')
    add_debug(
        f'Link pós-download excluído: {removed.get("label", "")}',
        origin='DOWNLOAD_LINKS',
        level='INFO',
    )


def _move_link(index: int, delta: int) -> None:
    links = _get_links()
    target = index + delta
    if index < 0 or target < 0 or index >= len(links) or target >= len(links):
        return

    links[index], links[target] = links[target], links[index]
    _save_links(links, event_name='post_download_link_reordered')


def _render_add_link_form(operation: str) -> None:
    with st.form('post_download_add_link_form', clear_on_submit=True):
        st.markdown('##### Adicionar link útil')
        label = st.text_input('Nome do botão', key=LINKS_FORM_LABEL_KEY, placeholder='Ex: Meu tutorial de importação')
        url = st.text_input('Link', key=LINKS_FORM_URL_KEY, placeholder='https://...')
        hint = st.text_input('Descrição curta', key=LINKS_FORM_HINT_KEY, placeholder='Explique quando usar este link')
        scope_label = 'Somente este fluxo' if operation in VALID_OPERATIONS else 'Todos os fluxos'
        use_current_flow = st.checkbox(scope_label, value=True, key='post_download_link_current_flow_only')
        submitted = st.form_submit_button('Adicionar aos próximos passos', use_container_width=True)

    if submitted:
        link_operation = operation if use_current_flow else 'todos'
        ok, message = _add_custom_link(label, url, hint, link_operation)
        if ok:
            st.success(message)
            st.rerun()
        st.warning(message)


def _render_edit_links_panel(operation: str) -> None:
    st.markdown('#### Personalizar links úteis')
    st.caption('Mesmo sem conta de usuário, estes links ficam personalizados nesta sessão. O usuário pode adicionar, excluir ou reordenar.')

    _render_add_link_form(operation)

    links = _get_links()
    if not links:
        st.warning('Nenhum link cadastrado. Você pode adicionar um link ou restaurar os padrões.')
    else:
        st.markdown('##### Links cadastrados')

    for index, item in enumerate(links):
        label = _normalize_text(item.get('label')) or 'Link sem nome'
        url = _normalize_url(item.get('url'))
        hint = _normalize_text(item.get('hint'))
        item_operation = _normalize_text(item.get('operation')) or 'todos'

        with st.container(border=True):
            st.markdown(f'**{label}**')
            st.caption(f'Fluxo: {item_operation}')
            if hint:
                st.caption(hint)
            st.code(url, language=None)

            col_up, col_down, col_delete = st.columns([1, 1, 2])
            with col_up:
                if st.button('↑', key=f'post_download_link_up_{index}', use_container_width=True):
                    _move_link(index, -1)
                    st.rerun()
            with col_down:
                if st.button('↓', key=f'post_download_link_down_{index}', use_container_width=True):
                    _move_link(index, 1)
                    st.rerun()
            with col_delete:
                if st.button('Excluir', key=f'post_download_link_delete_{index}', use_container_width=True):
                    _delete_link(index)
                    st.rerun()

    st.markdown('---')
    if st.button('Restaurar links padrão', use_container_width=True, key='post_download_reset_default_links'):
        _reset_links()
        st.rerun()


def render_bling_links_panel() -> None:
    """Mostra os próximos passos logo após o download final.

    BLINGFIX:
    - este painel não fica na sidebar;
    - ele aparece no fim do fluxo, logo após o botão de download;
    - dá sequência para importação/atualização no Bling;
    - permite ao usuário final adicionar, excluir e reordenar links úteis mesmo sem contas reais;
    - inclui entrada direta para o fluxo interno de atualização de preços multiloja.
    """
    operation = _current_operation()
    operation_label = 'Atualização de estoque' if operation == 'estoque' else 'Cadastro / atualização de produtos'

    st.markdown('### Próximos passos depois do download')
    st.caption(f'Fluxo detectado: {operation_label}. Baixe o CSV e continue pelo caminho correto abaixo.')

    with st.container(border=True):
        _render_next_flow_card(operation)

    st.markdown('#### Abrir no Bling')
    recommended = _recommended_links(operation)
    if not recommended:
        st.warning('Nenhum link útil cadastrado para este fluxo.')
    else:
        for index, item in recommended:
            _render_link_button(item, index)

    edit_mode = st.toggle(
        'Editar links úteis deste final de fluxo',
        value=bool(st.session_state.get(LINKS_EDIT_MODE_KEY, False)),
        key=LINKS_EDIT_MODE_KEY,
    )
    if edit_mode:
        _render_edit_links_panel(operation)

    add_audit_event(
        'post_download_links_rendered',
        area='DOWNLOAD_LINKS',
        status='OK',
        details={
            'operation': operation,
            'links_visible': len(recommended),
            'edit_mode': edit_mode,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


USEFUL_BLING_LINKS = DEFAULT_POST_DOWNLOAD_LINKS

__all__ = ['DEFAULT_POST_DOWNLOAD_LINKS', 'USEFUL_BLING_LINKS', 'render_bling_links_panel']
