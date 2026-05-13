from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug

RESPONSIBLE_FILE = 'bling_app_zero/ui/guided_login_panel.py'
CONFIG_KEY = 'guided_login_capture_config'
PROMPT_KEY = 'guided_login_capture_prompt'
LAST_PREPARED_KEY = 'guided_login_capture_last_prepared_at'
SECURITY_RESOLVED_KEY = 'guided_login_security_resolved'

DEFAULT_LOGIN_URL = 'https://app.obaobamix.com.br/login'


def _is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _safe_config(login_url: str, username: str, operation: str) -> dict[str, object]:
    clean_url = login_url.strip()
    return {
        'login_url': clean_url,
        'domain': urlparse(clean_url).netloc if clean_url else '',
        'username_filled': bool(username.strip()),
        'operation': operation,
        'capture_mode': 'estoque' if operation == 'estoque' else 'cadastro',
        'security_resolved': True,
        'prepared_at': datetime.now().isoformat(timespec='seconds'),
        'responsible_file': RESPONSIBLE_FILE,
        'password_saved': False,
        'security_code_saved': False,
    }


def _build_guided_login_prompt(config: dict[str, object]) -> str:
    return f'''BLINGCRAWLER LOGIN GUIADO COMPACTO

Site de login:
{config.get('login_url')}

Domínio:
{config.get('domain')}

Operação:
{config.get('operation')}

Usuário preenchido:
{config.get('username_filled')}

Senha:
NÃO FOI SALVA E NÃO DEVE SER EXIBIDA EM LOGS.

Regras:
- Usar motor autenticado independente.
- Não misturar com busca pública.
- Não salvar senha, token, cookie, código ou segredo.
- Se houver CAPTCHA/2FA, parar e pedir ação manual.
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


def _prepare_config(login_url: str, username: str, password: str, operation: str) -> None:
    if not _is_valid_http_url(login_url):
        st.warning('Informe uma URL de login válida, começando com http:// ou https://.')
        return
    if not password.strip():
        st.warning('Informe a senha apenas para esta sessão. Ela não será salva em logs nem no prompt.')
        return

    config = _safe_config(login_url=login_url, username=username, operation=operation)
    prompt = _build_guided_login_prompt(config)

    st.session_state[CONFIG_KEY] = config
    st.session_state[PROMPT_KEY] = prompt
    st.session_state[LAST_PREPARED_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    st.session_state[SECURITY_RESOLVED_KEY] = True

    add_debug(
        f'Login guiado compacto preparado para domínio {config.get("domain")}. Senha não registrada.',
        origin='LOGIN_GUIADO',
    )
    add_audit_event(
        'guided_login_capture_prepared',
        area='LOGIN_GUIADO',
        details={
            'domain': config.get('domain'),
            'operation': operation,
            'username_filled': bool(config.get('username_filled')),
            'password_saved': False,
            'security_code_saved': False,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_prepared_config() -> None:
    config = st.session_state.get(CONFIG_KEY)
    if not isinstance(config, dict):
        return
    last_prepared = st.session_state.get(LAST_PREPARED_KEY, 'agora')
    domain = str(config.get('domain') or '').strip() or 'site informado'
    operation = str(config.get('operation') or 'cadastro').strip()
    label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.success(f'Login preparado para {domain} em {last_prepared}.')
    st.caption(f'Pronto para captura autenticada de {label}. Senha não foi salva.')


def render_guided_login_panel() -> None:
    operation = _current_operation()
    operation_label = 'estoque' if operation == 'estoque' else 'cadastro'

    st.markdown('##### Login do fornecedor')
    st.caption(f'Preencha só o necessário para capturar {operation_label}.')

    login_url = st.text_input(
        'URL de login',
        value=str(st.session_state.get('guided_login_url') or DEFAULT_LOGIN_URL),
        placeholder='https://site.com.br/login',
        key='guided_login_url',
    )
    username = st.text_input(
        'Usuário ou e-mail',
        placeholder='seu usuário ou e-mail',
        key='guided_login_username',
    )
    password = st.text_input(
        'Senha da sessão',
        type='password',
        placeholder='não será salva',
        key='guided_login_password_ephemeral',
    )

    st.caption('Se aparecer CAPTCHA ou código, resolva manualmente no site. O sistema não tenta burlar proteção.')

    if st.button('🔐 Preparar login', use_container_width=True, key='prepare_guided_login_capture'):
        _prepare_config(login_url=login_url, username=username, password=password, operation=operation)

    _render_prepared_config()


__all__ = ['render_guided_login_panel']
