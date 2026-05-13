from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.browser_remote import RemoteBrowserConfig, open_remote_browser_snapshot
from bling_app_zero.core.debug import add_debug

RESPONSIBLE_FILE = 'bling_app_zero/ui/guided_login_panel.py'
CONFIG_KEY = 'guided_login_capture_config'
PROMPT_KEY = 'guided_login_capture_prompt'
LAST_PREPARED_KEY = 'guided_login_capture_last_prepared_at'
SECURITY_RESOLVED_KEY = 'guided_login_security_resolved'
LOGIN_CONFIRMED_KEY = 'guided_login_confirmed_logged_in'
PAGE_READY_KEY = 'guided_login_products_page_ready'
MODE_KEY = 'guided_login_capture_mode'
REMOTE_SNAPSHOT_URL_KEY = 'guided_login_remote_snapshot_url'
REMOTE_SNAPSHOT_FINAL_URL_KEY = 'guided_login_remote_snapshot_final_url'
REMOTE_SNAPSHOT_TITLE_KEY = 'guided_login_remote_snapshot_title'
REMOTE_SNAPSHOT_OK_KEY = 'guided_login_remote_snapshot_ok'

DEFAULT_SUPPLIER_URL = 'https://app.obaobamix.com.br/admin'
LEGACY_EXTERNAL_LOGIN_KEYS = (
    'guided_login_username',
    'guided_login_password_ephemeral',
    'guided_login_security_code',
    'guided_login_security_code_ephemeral',
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
        'remote_browser_snapshot': True,
    }


def _build_guided_login_prompt(config: dict[str, object]) -> str:
    return f'''BLINGCRAWLER CAPTURA POR NAVEGADOR REAL DO SISTEMA

Página preparada:
{config.get('supplier_url') or config.get('login_url')}

Domínio:
{config.get('domain')}

Operação:
{config.get('operation')}

Modo:
Navegador real do sistema via Playwright/Chromium. O sistema abre a URL no servidor,
valida a página renderizada e usa o motor de captura por blocos/DOM.

Regras:
- Não usar iframe como fonte de verdade.
- Não assumir que aba externa do celular compartilha sessão com o servidor.
- Não pedir campos externos de login.
- Não salvar credenciais.
- Só preparar captura quando o snapshot do navegador real abrir a página correta.
- Se o fornecedor exigir login interativo não suportado, usar compatibilidade universal.
- Cadastro: capturar dados completos quando possível.
- Estoque: preencher somente colunas da planilha modelo.
- Se não encontrar informação, deixar vazio.
'''


def _orange_warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:10px;padding:10px 12px;margin:8px 0;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _clear_legacy_external_login_state() -> None:
    removed: list[str] = []
    for key in LEGACY_EXTERNAL_LOGIN_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    st.session_state[MODE_KEY] = 'browser_session'
    if removed:
        add_audit_event(
            'supplier_browser_legacy_login_state_cleared',
            area='LOGIN_GUIADO',
            status='OK',
            details={'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
        )


def _prepare_config(supplier_url: str, operation: str) -> None:
    if not _is_valid_http_url(supplier_url):
        _orange_warning('Informe uma URL válida do fornecedor, começando com http:// ou https://.')
        return
    if not bool(st.session_state.get(REMOTE_SNAPSHOT_OK_KEY, False)):
        _orange_warning('Abra primeiro o snapshot do navegador real do sistema. Se ele não mostrar a página correta, use a compatibilidade universal.')
        return
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('Confirme que o snapshot mostra a página correta de produtos/catálogo antes de preparar a captura.')
        return

    _clear_legacy_external_login_state()
    st.session_state[SECURITY_RESOLVED_KEY] = True
    st.session_state[LOGIN_CONFIRMED_KEY] = True

    final_url = str(st.session_state.get(REMOTE_SNAPSHOT_FINAL_URL_KEY) or supplier_url).strip()
    config = _safe_config(supplier_url=final_url, operation=operation)
    prompt = _build_guided_login_prompt(config)

    st.session_state[CONFIG_KEY] = config
    st.session_state[PROMPT_KEY] = prompt
    st.session_state[LAST_PREPARED_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    add_debug(
        f'Navegador real do sistema preparado para domínio {config.get("domain")}. Sem campos externos de login.',
        origin='LOGIN_GUIADO',
    )
    add_audit_event(
        'remote_supplier_browser_prepared',
        area='LOGIN_GUIADO',
        details={
            'domain': config.get('domain'),
            'operation': operation,
            'capture_mode': 'browser_session',
            'products_page_ready': True,
            'external_login_fields': False,
            'credentials_saved': False,
            'remote_browser_snapshot': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_remote_browser_snapshot(supplier_url: str) -> None:
    st.caption('Navegador real do sistema: o servidor abre a página em Chromium e mostra um snapshot. Não é iframe e não usa a aba externa do celular como sessão.')
    if st.button('🌐 Abrir snapshot no navegador real do sistema', use_container_width=True, key='open_remote_supplier_browser_snapshot'):
        if not _is_valid_http_url(supplier_url):
            _orange_warning('Informe uma URL válida do fornecedor, começando com http:// ou https://.')
            return
        with st.spinner('Abrindo navegador real do sistema...'):
            snapshot = open_remote_browser_snapshot(
                RemoteBrowserConfig(
                    url=supplier_url,
                    state_namespace=f'{_current_operation()}_supplier_remote_browser',
                    headless=True,
                )
            )
        st.session_state[REMOTE_SNAPSHOT_OK_KEY] = bool(snapshot.ok)
        st.session_state[REMOTE_SNAPSHOT_URL_KEY] = supplier_url
        st.session_state[REMOTE_SNAPSHOT_FINAL_URL_KEY] = snapshot.final_url or supplier_url
        st.session_state[REMOTE_SNAPSHOT_TITLE_KEY] = snapshot.title or ''
        for warning in snapshot.warnings:
            _orange_warning(str(warning))
        if snapshot.errors:
            st.error('Não consegui abrir esta página no navegador real do sistema.')
            for error in snapshot.errors:
                st.caption(str(error))
            _orange_warning('Se o fornecedor exigir login interativo, captcha ou bloquear robô, use a compatibilidade universal abaixo: exporte/cole/importar HTML, CSV, XLSX ou tabela.')
            return
        if snapshot.screenshot_png:
            st.image(snapshot.screenshot_png, caption=snapshot.title or snapshot.final_url or supplier_url, use_column_width=True)
        st.success('Snapshot do navegador real carregado. Confira se esta é a página correta antes de preparar a captura.')

    if bool(st.session_state.get(REMOTE_SNAPSHOT_OK_KEY, False)):
        title = str(st.session_state.get(REMOTE_SNAPSHOT_TITLE_KEY) or 'Snapshot carregado')
        final_url = str(st.session_state.get(REMOTE_SNAPSHOT_FINAL_URL_KEY) or supplier_url)
        st.success(f'Último snapshot carregado: {title}')
        st.caption(final_url)

    _orange_warning('Abrir fora do sistema no celular não compartilha login com este navegador real. Se precisar operar manualmente o site logado, use exportação/cópia/importação pela compatibilidade universal.')


def _render_page_confirmation() -> None:
    st.checkbox(
        'O snapshot mostra a página correta de produtos/catálogo',
        value=bool(st.session_state.get(PAGE_READY_KEY, False)),
        key=PAGE_READY_KEY,
        help='Marque somente depois que o snapshot do navegador real mostrar a página que deve ser capturada.',
    )
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('A captura fica bloqueada até você confirmar que o snapshot mostra a página correta de produtos.')


def _render_prepared_config() -> None:
    config = st.session_state.get(CONFIG_KEY)
    if not isinstance(config, dict):
        return
    last_prepared = st.session_state.get(LAST_PREPARED_KEY, 'agora')
    domain = str(config.get('domain') or '').strip() or 'site informado'
    operation = str(config.get('operation') or 'cadastro').strip()
    label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.success(f'Navegador real preparado para {domain} em {last_prepared}.')
    st.caption(f'Pronto para captura de {label}. O sistema usará Chromium/Playwright no servidor e não iframe.')


def render_guided_login_panel() -> None:
    _clear_legacy_external_login_state()
    operation = _current_operation()
    operation_label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.markdown('##### Navegador real do sistema')
    st.caption(f'Use esta área para abrir a página do fornecedor no Chromium do servidor e preparar a captura de {operation_label}.')

    supplier_url = st.text_input(
        'URL do fornecedor ou da página de produtos',
        value=str(st.session_state.get('guided_login_url') or DEFAULT_SUPPLIER_URL),
        placeholder='https://site-do-fornecedor.com.br/admin',
        key='guided_login_url',
    )

    _render_remote_browser_snapshot(supplier_url)
    _render_page_confirmation()

    can_prepare = bool(st.session_state.get(REMOTE_SNAPSHOT_OK_KEY, False)) and bool(st.session_state.get(PAGE_READY_KEY, False))
    if st.button('✅ Preparar captura desta página', use_container_width=True, key='prepare_guided_login_capture', disabled=not can_prepare):
        _prepare_config(supplier_url=supplier_url, operation=operation)
    if not can_prepare:
        st.caption('Para habilitar este botão, abra um snapshot válido no navegador real do sistema e confirme que ele mostra a página de produtos.')
    _render_prepared_config()


__all__ = ['render_guided_login_panel']
