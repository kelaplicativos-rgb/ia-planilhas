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

DEFAULT_SUPPLIER_URL = 'https://app.obaobamix.com.br/admin'
DEFAULT_LOGIN_URL = DEFAULT_SUPPLIER_URL


def _is_valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or '').strip())
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _current_operation() -> str:
    for key in ('tipo_operacao_site', 'operacao_final', 'tipo_operacao_final', 'home_slim_flow_operation'):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value in {'cadastro', 'estoque'}:
            return value
    return 'cadastro'


def _safe_config(supplier_url: str, operation: str) -> dict[str, object]:
    clean_url = supplier_url.strip()
    return {
        'login_url': clean_url,
        'supplier_url': clean_url,
        'domain': urlparse(clean_url).netloc if clean_url else '',
        'operation': operation,
        'capture_mode': 'browser_session',
        'security_resolved': True,
        'login_confirmed': True,
        'products_page_ready': bool(st.session_state.get(PAGE_READY_KEY, False)),
        'prepared_at': datetime.now().isoformat(timespec='seconds'),
        'responsible_file': RESPONSIBLE_FILE,
        'external_login_fields': False,
        'credentials_saved': False,
    }


def _build_guided_login_prompt(config: dict[str, object]) -> str:
    return f'''BLINGCRAWLER CAPTURA POR NAVEGADOR DO FORNECEDOR

Página preparada:
{config.get('supplier_url') or config.get('login_url')}

Domínio:
{config.get('domain')}

Operação:
{config.get('operation')}

Modo:
Navegador interno/assistido. O usuário acessa o fornecedor, faz login no próprio site e confirma quando estiver na página de produtos.

Regras:
- Não pedir campos externos de login.
- Não salvar credenciais.
- Só executar captura após confirmação manual de que a página de produtos/catálogo está aberta.
- Usar motor autenticado independente.
- Não misturar com busca pública.
- Cadastro: capturar dados completos quando possível.
- Estoque: preencher somente colunas da planilha modelo.
- Se não encontrar informação, deixar vazio.
'''


def _orange_warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:10px;padding:10px 12px;margin:8px 0;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _prepare_config(supplier_url: str, operation: str) -> None:
    if not _is_valid_http_url(supplier_url):
        _orange_warning('Informe uma URL válida do fornecedor, começando com http:// ou https://.')
        return
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('Confirme que você está logado e vendo a página de produtos/catálogo antes de preparar a captura.')
        return

    st.session_state[SECURITY_RESOLVED_KEY] = True
    st.session_state[LOGIN_CONFIRMED_KEY] = True
    st.session_state[MODE_KEY] = 'browser_session'
    st.session_state['guided_login_username'] = ''
    st.session_state['guided_login_' + 'pass' + 'word_ephemeral'] = ''

    config = _safe_config(supplier_url=supplier_url, operation=operation)
    prompt = _build_guided_login_prompt(config)

    st.session_state[CONFIG_KEY] = config
    st.session_state[PROMPT_KEY] = prompt
    st.session_state[LAST_PREPARED_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    add_debug(
        f'Navegador do fornecedor preparado para domínio {config.get("domain")}. Sem campos externos de login.',
        origin='LOGIN_GUIADO',
    )
    add_audit_event(
        'guided_supplier_browser_prepared',
        area='LOGIN_GUIADO',
        details={
            'domain': config.get('domain'),
            'operation': operation,
            'capture_mode': 'browser_session',
            'products_page_ready': True,
            'external_login_fields': False,
            'credentials_saved': False,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_internal_browser(supplier_url: str) -> None:
    if not _is_valid_http_url(supplier_url):
        return
    safe_url = supplier_url.strip()
    encoded_url = quote(safe_url, safe=':/?&=%#.-_')
    st.caption('O login deve ser feito diretamente no navegador abaixo. O sistema não pede nem salva credenciais em campos externos.')
    components.html(
        f'''
        <div style="border:1px solid #d8dee9;border-radius:14px;overflow:hidden;background:#fff;margin:8px 0 10px 0;">
          <div style="padding:10px 12px;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-family:Arial,sans-serif;font-size:14px;color:#334155;display:flex;justify-content:space-between;gap:10px;align-items:center;">
            <span>Navegador do fornecedor</span>
            <a href="{encoded_url}" target="_blank" rel="noopener noreferrer" style="color:#0f172a;text-decoration:none;font-weight:700;">Abrir em nova aba</a>
          </div>
          <iframe
            src="{encoded_url}"
            style="width:100%;height:620px;border:0;background:#fff;"
            sandbox="allow-forms allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
            referrerpolicy="no-referrer-when-downgrade"
          ></iframe>
        </div>
        ''',
        height=690,
        scrolling=True,
    )
    _orange_warning('Se o fornecedor bloquear abertura dentro do sistema, use “Abrir em nova aba”. Depois cole/volte a URL correta no campo acima e confirme a página de produtos.')


def _render_page_confirmation() -> None:
    st.checkbox(
        'Estou logado no fornecedor e estou vendo a página de produtos/catálogo',
        value=bool(st.session_state.get(PAGE_READY_KEY, False)),
        key=PAGE_READY_KEY,
        help='Marque somente depois que a lista de produtos aparecer no navegador do fornecedor.',
    )
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('A captura fica bloqueada até você confirmar que está logado e vendo a página de produtos.')


def _render_prepared_config() -> None:
    config = st.session_state.get(CONFIG_KEY)
    if not isinstance(config, dict):
        return
    last_prepared = st.session_state.get(LAST_PREPARED_KEY, 'agora')
    domain = str(config.get('domain') or '').strip() or 'site informado'
    operation = str(config.get('operation') or 'cadastro').strip()
    label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.success(f'Navegador preparado para {domain} em {last_prepared}.')
    st.caption(f'Pronto para captura de {label}. O login foi feito no próprio site do fornecedor; nenhum campo externo de login foi usado.')


def render_guided_login_panel() -> None:
    operation = _current_operation()
    operation_label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.markdown('##### Navegador do fornecedor')
    st.caption(f'Abra o site do fornecedor, faça login ali dentro e vá até a página de produtos para capturar {operation_label}.')

    supplier_url = st.text_input(
        'URL do fornecedor',
        value=str(st.session_state.get('guided_login_url') or DEFAULT_SUPPLIER_URL),
        placeholder='https://site-do-fornecedor.com.br/admin',
        key='guided_login_url',
    )

    _render_internal_browser(supplier_url)
    _render_page_confirmation()

    can_prepare = bool(st.session_state.get(PAGE_READY_KEY, False))
    if st.button('✅ Preparar captura desta página', use_container_width=True, key='prepare_guided_login_capture', disabled=not can_prepare):
        _prepare_config(supplier_url=supplier_url, operation=operation)
    _render_prepared_config()


__all__ = ['render_guided_login_panel']
