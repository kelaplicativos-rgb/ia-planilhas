from __future__ import annotations

from datetime import datetime
from urllib.parse import quote, urlparse

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug

RESPONSIBLE_FILE = 'bling_app_zero/ui/guided_login_panel.py'
CONFIG_KEY = 'guided_login_capture_config'
PROMPT_KEY = 'guided_login_capture_prompt'
LAST_PREPARED_KEY = 'guided_login_capture_last_prepared_at'
SECURITY_RESOLVED_KEY = 'guided_login_security_resolved'
LOGIN_CONFIRMED_KEY = 'guided_login_confirmed_logged_in'
PAGE_READY_KEY = 'guided_login_products_page_ready'
MODE_KEY = 'guided_login_capture_mode'

DEFAULT_LOGIN_URL = 'https://app.stoqui.com.br/products'


def _is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _safe_config(login_url: str, username: str, operation: str, capture_mode: str) -> dict[str, object]:
    clean_url = login_url.strip()
    return {
        'login_url': clean_url,
        'domain': urlparse(clean_url).netloc if clean_url else '',
        'username_filled': bool(username.strip()),
        'operation': operation,
        'capture_mode': capture_mode,
        'security_resolved': bool(st.session_state.get(SECURITY_RESOLVED_KEY, False)),
        'login_confirmed': bool(st.session_state.get(LOGIN_CONFIRMED_KEY, False)),
        'products_page_ready': bool(st.session_state.get(PAGE_READY_KEY, False)),
        'prepared_at': datetime.now().isoformat(timespec='seconds'),
        'responsible_file': RESPONSIBLE_FILE,
        'password_saved': False,
        'security_code_saved': False,
    }


def _build_guided_login_prompt(config: dict[str, object]) -> str:
    return f'''BLINGCRAWLER CAPTURA AUTENTICADA COMPACTA

Página informada:
{config.get('login_url')}

Domínio:
{config.get('domain')}

Operação:
{config.get('operation')}

Modo:
{config.get('capture_mode')}

Página de produtos confirmada:
{config.get('products_page_ready')}

Credenciais:
NÃO FORAM SALVAS E NÃO DEVEM SER EXIBIDAS EM LOGS.

Regras:
- Só executar captura após confirmação manual de que a página de produtos/catálogo está aberta.
- Usar motor autenticado independente.
- Não misturar com busca pública.
- Não salvar dados protegidos da sessão.
- Cadastro: capturar dados completos quando possível.
- Estoque: preencher somente colunas da planilha modelo.
- Se não encontrar informação, deixar vazio.
'''


def _current_operation() -> str:
    for key in ('tipo_operacao_site', 'operacao_final', 'tipo_operacao_final', 'home_slim_flow_operation'):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value in {'cadastro', 'estoque'}:
            return value
    return 'cadastro'


def _prepare_config(login_url: str, username: str, password: str, operation: str, capture_mode: str) -> None:
    if not _is_valid_http_url(login_url):
        st.warning('Informe uma URL válida, começando com http:// ou https://.')
        return
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        st.warning('Confirme que a página de produtos/catálogo está aberta antes de preparar a captura.')
        return
    if capture_mode == 'login' and not password.strip():
        st.warning('Informe a senha apenas para esta sessão ou use o modo página de produtos já aberta.')
        return

    st.session_state[SECURITY_RESOLVED_KEY] = True
    st.session_state[LOGIN_CONFIRMED_KEY] = True
    config = _safe_config(login_url=login_url, username=username, operation=operation, capture_mode=capture_mode)
    prompt = _build_guided_login_prompt(config)

    st.session_state[CONFIG_KEY] = config
    st.session_state[PROMPT_KEY] = prompt
    st.session_state[LAST_PREPARED_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    add_debug(
        f'Captura compacta preparada para domínio {config.get("domain")}. Dados protegidos não registrados.',
        origin='LOGIN_GUIADO',
    )
    add_audit_event(
        'guided_login_capture_prepared',
        area='LOGIN_GUIADO',
        details={
            'domain': config.get('domain'),
            'operation': operation,
            'capture_mode': capture_mode,
            'username_filled': bool(config.get('username_filled')),
            'products_page_ready': True,
            'password_saved': False,
            'security_code_saved': False,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_internal_browser(login_url: str) -> None:
    if not _is_valid_http_url(login_url):
        return
    open_browser = st.checkbox(
        'Abrir página dentro do sistema',
        value=True,
        key='guided_login_open_internal_browser',
        help='Abre a página do fornecedor dentro do sistema quando o site permitir.',
    )
    if not open_browser:
        return
    safe_url = login_url.strip()
    encoded_url = quote(safe_url, safe=':/?&=%#.-_')
    components.html(
        f'''
        <div style="border:1px solid #d8dee9;border-radius:14px;overflow:hidden;background:#fff;margin:8px 0 10px 0;">
          <div style="padding:10px 12px;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-family:Arial,sans-serif;font-size:14px;color:#334155;">
            Navegador interno do fornecedor
          </div>
          <iframe
            src="{encoded_url}"
            style="width:100%;height:560px;border:0;background:#fff;"
            sandbox="allow-forms allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
            referrerpolicy="no-referrer-when-downgrade"
          ></iframe>
        </div>
        ''',
        height=620,
        scrolling=True,
    )


def _render_page_confirmation() -> None:
    st.checkbox(
        'Estou vendo a página de produtos/catálogo e posso capturar agora',
        value=bool(st.session_state.get(PAGE_READY_KEY, False)),
        key=PAGE_READY_KEY,
        help='Marque somente depois que a lista de produtos aparecer no navegador interno.',
    )
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        st.markdown(
            '<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:10px;padding:10px 12px;margin:8px 0;">⚠️ A captura só será liberada depois de confirmar que a página de produtos está visível.</div>',
            unsafe_allow_html=True,
        )


def _render_prepared_config() -> None:
    config = st.session_state.get(CONFIG_KEY)
    if not isinstance(config, dict):
        return
    last_prepared = st.session_state.get(LAST_PREPARED_KEY, 'agora')
    domain = str(config.get('domain') or '').strip() or 'site informado'
    operation = str(config.get('operation') or 'cadastro').strip()
    label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.success(f'Página preparada para {domain} em {last_prepared}.')
    st.caption(f'Pronto para captura autenticada de {label}. Dados protegidos não foram salvos.')


def render_guided_login_panel() -> None:
    operation = _current_operation()
    operation_label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.markdown('##### Página do fornecedor')
    st.caption(f'Abra a página onde os produtos aparecem para capturar {operation_label}.')

    capture_mode = st.radio(
        'Modo',
        options=['products_page', 'login'],
        format_func=lambda value: 'Página de produtos já aberta' if value == 'products_page' else 'Preciso informar usuário e senha',
        horizontal=True,
        key=MODE_KEY,
    )
    login_url = st.text_input(
        'URL da página',
        value=str(st.session_state.get('guided_login_url') or DEFAULT_LOGIN_URL),
        placeholder='https://site.com.br/products',
        key='guided_login_url',
    )

    username = ''
    password = ''
    if capture_mode == 'login':
        username = st.text_input('Usuário ou e-mail', placeholder='seu usuário ou e-mail', key='guided_login_username')
        password = st.text_input('Senha da sessão', type='password', placeholder='não será salva', key='guided_login_password_ephemeral')
    else:
        st.session_state.setdefault('guided_login_username', '')
        st.session_state.setdefault('guided_login_password_ephemeral', '')

    _render_internal_browser(login_url)
    _render_page_confirmation()

    can_prepare = bool(st.session_state.get(PAGE_READY_KEY, False))
    if st.button('🔐 Preparar captura', use_container_width=True, key='prepare_guided_login_capture', disabled=not can_prepare):
        _prepare_config(login_url=login_url, username=username, password=password, operation=operation, capture_mode=capture_mode)
    _render_prepared_config()


__all__ = ['render_guided_login_panel']
