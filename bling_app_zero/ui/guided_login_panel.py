from __future__ import annotations

from datetime import datetime
from urllib.parse import quote, urlparse

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.remote_desktop_panel import render_remote_desktop_panel

RESPONSIBLE_FILE = 'bling_app_zero/ui/guided_login_panel.py'
CONFIG_KEY = 'guided_login_capture_config'
PROMPT_KEY = 'guided_login_capture_prompt'
LAST_PREPARED_KEY = 'guided_login_capture_last_prepared_at'
SECURITY_RESOLVED_KEY = 'guided_login_security_resolved'
LOGIN_CONFIRMED_KEY = 'guided_login_confirmed_logged_in'
PAGE_READY_KEY = 'guided_login_products_page_ready'
MODE_KEY = 'guided_login_capture_mode'
REMOTE_DESKTOP_READY_KEY = 'guided_login_remote_desktop_ready'
REMOTE_DESKTOP_URL_READY_KEY = 'guided_login_remote_desktop_url_ready'

DEFAULT_SUPPLIER_URL = 'https://app.obaobamix.com.br/admin'
LEGACY_EXTERNAL_LOGIN_KEYS = (
    'guided_login_username',
    'guided_login_password_ephemeral',
    'guided_login_security_code',
    'guided_login_security_code_ephemeral',
    'guided_login_remote_snapshot_url',
    'guided_login_remote_snapshot_final_url',
    'guided_login_remote_snapshot_title',
    'guided_login_remote_snapshot_ok',
    'guided_login_remote_snapshot_png',
    'guided_login_remote_last_click_nonce',
)


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


def _orange_warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _clear_legacy_external_login_state() -> None:
    removed: list[str] = []
    for key in LEGACY_EXTERNAL_LOGIN_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    st.session_state[MODE_KEY] = 'remote_desktop'
    if removed:
        add_audit_event(
            'supplier_browser_legacy_snapshot_state_cleared',
            area='LOGIN_GUIADO',
            status='OK',
            details={'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
        )


def _safe_config(supplier_url: str, operation: str) -> dict[str, object]:
    clean_url = supplier_url.strip()
    return {
        'login_url': clean_url,
        'supplier_url': clean_url,
        'domain': urlparse(clean_url).netloc if clean_url else '',
        'operation': operation,
        'capture_mode': 'remote_desktop',
        'security_resolved': True,
        'login_confirmed': True,
        'products_page_ready': bool(st.session_state.get(PAGE_READY_KEY, False)),
        'prepared_at': datetime.now().isoformat(timespec='seconds'),
        'responsible_file': RESPONSIBLE_FILE,
        'external_login_fields': False,
        'credentials_saved': False,
        'remote_desktop': True,
        'novnc_browser': True,
    }


def _build_guided_login_prompt(config: dict[str, object]) -> str:
    return f'''BLINGCRAWLER CAPTURA POR NAVEGADOR REMOTO REAL

Página preparada:
{config.get('supplier_url') or config.get('login_url')}

Domínio:
{config.get('domain')}

Operação:
{config.get('operation')}

Modo:
Navegador remoto real via Chrome/Chromium + noVNC. O usuário opera o navegador diretamente,
com clique e teclado reais dentro do desktop remoto. Este modo substitui snapshot, clique por
coordenada e painel espelhado quando o fornecedor exige login forte, CAPTCHA ou interação humana.

Regras:
- Não usar iframe clone de fornecedor como fonte de sessão.
- Não tentar copiar movimentos de iframe de outro domínio.
- Não salvar credenciais no app.
- O usuário deve fazer login manualmente no desktop remoto.
- O usuário deve resolver CAPTCHA manualmente quando o navegador remoto permitir.
- Só preparar captura quando a página de produtos/catálogo estiver aberta no desktop remoto.
- Cadastro: capturar dados completos quando possível.
- Estoque: preencher somente colunas da planilha modelo.
- Se o fornecedor não permitir automação/captura após login, usar compatibilidade universal/exportação/importação.
'''


def _prepare_config(supplier_url: str, operation: str) -> None:
    if not _is_valid_http_url(supplier_url):
        _orange_warning('Informe uma URL válida do fornecedor, começando com http:// ou https://.')
        return
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('Confirme primeiro que você chegou na página de produtos/catálogo dentro do navegador remoto real.')
        return

    _clear_legacy_external_login_state()
    st.session_state[SECURITY_RESOLVED_KEY] = True
    st.session_state[LOGIN_CONFIRMED_KEY] = True
    st.session_state[REMOTE_DESKTOP_READY_KEY] = True

    config = _safe_config(supplier_url=supplier_url, operation=operation)
    prompt = _build_guided_login_prompt(config)

    st.session_state[CONFIG_KEY] = config
    st.session_state[PROMPT_KEY] = prompt
    st.session_state[LAST_PREPARED_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    add_debug(
        f'Navegador remoto real preparado para domínio {config.get("domain")}. Fluxo noVNC/desktop remoto.',
        origin='LOGIN_GUIADO',
    )
    add_audit_event(
        'remote_desktop_supplier_browser_prepared',
        area='LOGIN_GUIADO',
        status='OK',
        details={
            'domain': config.get('domain'),
            'operation': operation,
            'capture_mode': 'remote_desktop',
            'products_page_ready': True,
            'credentials_saved': False,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_page_confirmation() -> None:
    st.checkbox(
        'Estou logado no navegador remoto real e vendo a página de produtos/catálogo',
        value=bool(st.session_state.get(PAGE_READY_KEY, False)),
        key=PAGE_READY_KEY,
        help='Marque somente depois de operar o Chrome remoto/noVNC e chegar na página que será capturada.',
    )
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('A captura fica bloqueada até você confirmar que está na página correta dentro do navegador remoto real.')


def _render_prepared_config() -> None:
    config = st.session_state.get(CONFIG_KEY)
    if not isinstance(config, dict):
        return
    last_prepared = st.session_state.get(LAST_PREPARED_KEY, 'agora')
    domain = str(config.get('domain') or '').strip() or 'site informado'
    operation = str(config.get('operation') or 'cadastro').strip()
    label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.success(f'Navegador remoto real preparado para {domain} em {last_prepared}.')
    st.caption(f'Pronto para captura de {label}.')


def _render_remote_desktop_setup_hint() -> None:
    st.markdown('##### Como ativar o navegador vivo')
    st.caption('Para clicar e digitar diretamente no navegador, configure um serviço Chrome remoto/noVNC e informe a URL nos secrets do Streamlit.')
    st.code(
        '[remote_desktop]\nurl = "https://SEU-NOVNC/vnc.html?autoconnect=true&resize=scale"',
        language='toml',
    )
    _orange_warning('Sem essa URL noVNC, o Streamlit não consegue hospedar um desktop gráfico completo sozinho. O painel mostra o que falta configurar sem criar falsa sensação de navegador vivo.')


def _render_supplier_browser_above(supplier_url: str) -> None:
    st.markdown('##### Navegador do fornecedor')
    st.caption('Este é o navegador visual do fornecedor que fica acima do BLINGREMOTE DESKTOP. Ele serve como apoio rápido; alguns fornecedores podem bloquear iframe/login/CAPTCHA por segurança.')

    if not _is_valid_http_url(supplier_url):
        _orange_warning('Informe uma URL válida para abrir o navegador do fornecedor.')
        return

    safe_url = quote(supplier_url, safe=':/?&=%#.-_')
    st.markdown(f'[Abrir fornecedor em nova aba]({supplier_url})')
    components.html(
        f'''
        <div style="border:1px solid #d8dee9;border-radius:16px;overflow:hidden;background:#f8fafc;margin:8px 0 16px 0;">
          <div style="display:flex;gap:8px;align-items:center;background:#111827;color:#e5e7eb;padding:10px 12px;font-family:Arial,sans-serif;font-size:13px;">
            <span style="width:10px;height:10px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
            <span style="width:10px;height:10px;border-radius:50%;background:#f59e0b;display:inline-block;"></span>
            <span style="width:10px;height:10px;border-radius:50%;background:#22c55e;display:inline-block;"></span>
            <strong style="margin-left:8px;">Fornecedor / iframe visual</strong>
            <span style="opacity:.72;margin-left:auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{safe_url}</span>
          </div>
          <iframe
            src="{safe_url}"
            style="width:100%;height:560px;border:0;background:#ffffff;"
            allow="clipboard-read; clipboard-write; fullscreen"
            referrerpolicy="no-referrer-when-downgrade"
          ></iframe>
        </div>
        ''',
        height=640,
        scrolling=True,
    )
    _orange_warning('Se esse navegador aparecer em branco, cortado ou não permitir login/CAPTCHA, use o BLINGREMOTE DESKTOP abaixo ou abra em nova aba. Muitos sites bloqueiam iframe por segurança.')


def render_guided_login_panel() -> None:
    _clear_legacy_external_login_state()
    operation = _current_operation()
    operation_label = 'estoque' if operation == 'estoque' else 'cadastro'

    st.markdown('##### BLINGREMOTE DESKTOP')
    st.caption(f'Navegador remoto real para login forte, CAPTCHA e captura de {operation_label}.')

    supplier_url = st.text_input(
        'URL inicial do fornecedor ou da página de produtos',
        value=str(st.session_state.get('guided_login_url') or DEFAULT_SUPPLIER_URL),
        placeholder='https://site-do-fornecedor.com.br/admin',
        key='guided_login_url',
    )

    _render_supplier_browser_above(supplier_url)

    has_remote_desktop = render_remote_desktop_panel(supplier_url=supplier_url, operation=operation)
    st.session_state[REMOTE_DESKTOP_URL_READY_KEY] = bool(has_remote_desktop)
    if not has_remote_desktop:
        _render_remote_desktop_setup_hint()

    _render_page_confirmation()

    can_prepare = bool(st.session_state.get(PAGE_READY_KEY, False)) and _is_valid_http_url(supplier_url)
    if st.button('Preparar captura desta página', use_container_width=True, key='prepare_guided_login_capture', disabled=not can_prepare):
        _prepare_config(supplier_url=supplier_url, operation=operation)
    if not can_prepare:
        st.caption('Para liberar este botão, informe uma URL válida e confirme que a página de produtos/catálogo está aberta no navegador remoto.')
    _render_prepared_config()


__all__ = ['render_guided_login_panel']
