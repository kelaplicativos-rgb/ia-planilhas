from __future__ import annotations

import base64
import time
from datetime import datetime
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.browser_remote import (
    RemoteBrowserCommand,
    RemoteBrowserConfig,
    open_remote_browser_snapshot,
    run_remote_browser_command,
)
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
REMOTE_SNAPSHOT_PNG_KEY = 'guided_login_remote_snapshot_png'
REMOTE_LAST_CLICK_NONCE_KEY = 'guided_login_remote_last_click_nonce'
REMOTE_VIEWPORT_WIDTH = 1366
REMOTE_VIEWPORT_HEIGHT = 900
REMOTE_CLICK_X_PARAM = 'bling_remote_click_x'
REMOTE_CLICK_Y_PARAM = 'bling_remote_click_y'
REMOTE_CLICK_NONCE_PARAM = 'bling_remote_click_nonce'

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


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(',', '.')))
    except Exception:
        return default


def _current_operation() -> str:
    for key in ('tipo_operacao_site', 'operacao_final', 'tipo_operacao_final', 'home_slim_flow_operation'):
        value = str(st.session_state.get(key) or '').strip().lower()
        if value in {'cadastro', 'estoque'}:
            return value
    return 'cadastro'


def _state_namespace() -> str:
    return f'{_current_operation()}_supplier_remote_browser'


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
        'remote_browser_control': True,
        'clickable_snapshot': True,
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
permite comandos guiados, snapshot clicável, valida a página renderizada e usa o motor de captura por blocos/DOM.

Regras:
- Não usar iframe como fonte de verdade.
- Não assumir que aba externa do celular compartilha sessão com o servidor.
- Não pedir campos externos de login.
- Não salvar credenciais.
- Só preparar captura quando o snapshot do navegador real abrir a página correta.
- Se o fornecedor exigir captcha/2FA/bloqueio humano forte, usar compatibilidade universal.
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


def _current_remote_url(fallback_url: str) -> str:
    return str(st.session_state.get(REMOTE_SNAPSHOT_FINAL_URL_KEY) or fallback_url or '').strip()


def _render_clickable_snapshot(supplier_url: str) -> None:
    png = st.session_state.get(REMOTE_SNAPSHOT_PNG_KEY)
    if not isinstance(png, (bytes, bytearray)) or not png:
        return
    title = str(st.session_state.get(REMOTE_SNAPSHOT_TITLE_KEY) or st.session_state.get(REMOTE_SNAPSHOT_FINAL_URL_KEY) or supplier_url)
    encoded = base64.b64encode(bytes(png)).decode('ascii')
    html = f'''
    <div style="font-family:Arial,sans-serif;margin:8px 0 12px 0;">
      <div style="background:#f8fafc;border:1px solid #dbe3ef;border-radius:12px 12px 0 0;padding:8px 10px;color:#334155;font-size:13px;">
        Clique/toque diretamente no snapshot para enviar o clique ao navegador real do sistema. Coordenada original: {REMOTE_VIEWPORT_WIDTH}x{REMOTE_VIEWPORT_HEIGHT}.
      </div>
      <div style="position:relative;border:1px solid #dbe3ef;border-top:0;border-radius:0 0 12px 12px;overflow:hidden;background:#0f172a;">
        <img id="blingRemoteBrowserImage" src="data:image/png;base64,{encoded}" alt="{title}" style="width:100%;display:block;cursor:crosshair;user-select:none;-webkit-user-select:none;" />
        <div id="blingRemoteBrowserPoint" style="display:none;position:absolute;width:18px;height:18px;margin-left:-9px;margin-top:-9px;border:2px solid #fb8c00;border-radius:50%;background:rgba(251,140,0,.18);pointer-events:none;"></div>
      </div>
      <div id="blingRemoteBrowserStatus" style="font-size:12px;color:#475569;margin-top:6px;">Aguardando clique no snapshot...</div>
    </div>
    <script>
      const img = document.getElementById('blingRemoteBrowserImage');
      const point = document.getElementById('blingRemoteBrowserPoint');
      const status = document.getElementById('blingRemoteBrowserStatus');
      img.addEventListener('click', function(event) {{
        const rect = img.getBoundingClientRect();
        const px = event.clientX - rect.left;
        const py = event.clientY - rect.top;
        const x = Math.max(0, Math.min({REMOTE_VIEWPORT_WIDTH - 1}, Math.round(px * {REMOTE_VIEWPORT_WIDTH} / rect.width)));
        const y = Math.max(0, Math.min({REMOTE_VIEWPORT_HEIGHT - 1}, Math.round(py * {REMOTE_VIEWPORT_HEIGHT} / rect.height)));
        point.style.left = px + 'px';
        point.style.top = py + 'px';
        point.style.display = 'block';
        status.textContent = 'Clique enviado: X=' + x + ' Y=' + y + '. Atualizando navegador...';
        const url = new URL(window.parent.location.href);
        url.searchParams.set('{REMOTE_CLICK_X_PARAM}', String(x));
        url.searchParams.set('{REMOTE_CLICK_Y_PARAM}', String(y));
        url.searchParams.set('{REMOTE_CLICK_NONCE_PARAM}', String(Date.now()));
        window.parent.location.href = url.toString();
      }});
    </script>
    '''
    components.html(html, height=760, scrolling=True)


def _display_snapshot(snapshot, supplier_url: str) -> None:
    st.session_state[REMOTE_SNAPSHOT_OK_KEY] = bool(snapshot.ok)
    st.session_state[REMOTE_SNAPSHOT_URL_KEY] = supplier_url
    st.session_state[REMOTE_SNAPSHOT_FINAL_URL_KEY] = snapshot.final_url or supplier_url
    st.session_state[REMOTE_SNAPSHOT_TITLE_KEY] = snapshot.title or ''
    for warning in snapshot.warnings:
        _orange_warning(str(warning))
    if snapshot.errors:
        st.error('Não consegui executar esta ação no navegador real do sistema.')
        for error in snapshot.errors:
            st.caption(str(error))
        _orange_warning('Se o fornecedor exigir captcha, 2FA, popup ou bloquear robô, use a compatibilidade universal: exporte/cole/importar HTML, CSV, XLSX ou tabela.')
        return
    if snapshot.screenshot_png:
        st.session_state[REMOTE_SNAPSHOT_PNG_KEY] = bytes(snapshot.screenshot_png)
        _render_clickable_snapshot(supplier_url)
    st.success('Snapshot atualizado pelo navegador real do sistema.')


def _run_browser_action(supplier_url: str, command: RemoteBrowserCommand, label: str) -> None:
    current_url = _current_remote_url(supplier_url)
    if not _is_valid_http_url(current_url):
        _orange_warning('Abra primeiro uma URL válida no navegador real do sistema.')
        return
    with st.spinner(label):
        snapshot = run_remote_browser_command(
            RemoteBrowserConfig(
                url=current_url,
                state_namespace=_state_namespace(),
                headless=True,
                width=REMOTE_VIEWPORT_WIDTH,
                height=REMOTE_VIEWPORT_HEIGHT,
            ),
            command,
        )
    _display_snapshot(snapshot, current_url)


def _consume_click_from_snapshot_if_needed(supplier_url: str) -> None:
    nonce = _query_param(REMOTE_CLICK_NONCE_PARAM)
    if not nonce:
        return
    if nonce == str(st.session_state.get(REMOTE_LAST_CLICK_NONCE_KEY) or ''):
        return
    x = max(0, min(_safe_int(_query_param(REMOTE_CLICK_X_PARAM), 0), REMOTE_VIEWPORT_WIDTH - 1))
    y = max(0, min(_safe_int(_query_param(REMOTE_CLICK_Y_PARAM), 0), REMOTE_VIEWPORT_HEIGHT - 1))
    st.session_state[REMOTE_LAST_CLICK_NONCE_KEY] = nonce
    _run_browser_action(
        supplier_url,
        RemoteBrowserCommand(action='click_xy', x=x, y=y),
        f'Clicando no navegador real em X={x} Y={y}...',
    )


def _prepare_config(supplier_url: str, operation: str) -> None:
    final_url = _current_remote_url(supplier_url)
    if not _is_valid_http_url(final_url):
        _orange_warning('Informe uma URL válida do fornecedor, começando com http:// ou https://.')
        return
    if not bool(st.session_state.get(REMOTE_SNAPSHOT_OK_KEY, False)):
        _orange_warning('Abra primeiro o navegador real do sistema. Se ele não mostrar a página correta, use a compatibilidade universal.')
        return
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('Confirme que o snapshot mostra a página correta de produtos/catálogo antes de preparar a captura.')
        return

    _clear_legacy_external_login_state()
    st.session_state[SECURITY_RESOLVED_KEY] = True
    st.session_state[LOGIN_CONFIRMED_KEY] = True

    config = _safe_config(supplier_url=final_url, operation=operation)
    prompt = _build_guided_login_prompt(config)

    st.session_state[CONFIG_KEY] = config
    st.session_state[PROMPT_KEY] = prompt
    st.session_state[LAST_PREPARED_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    add_debug(
        f'Navegador real controlado preparado para domínio {config.get("domain")}. Sem campos externos de login.',
        origin='LOGIN_GUIADO',
    )
    add_audit_event(
        'remote_control_supplier_browser_prepared',
        area='LOGIN_GUIADO',
        details={
            'domain': config.get('domain'),
            'operation': operation,
            'capture_mode': 'browser_session',
            'products_page_ready': True,
            'external_login_fields': False,
            'credentials_saved': False,
            'remote_browser_control': True,
            'clickable_snapshot': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def _render_remote_controls(supplier_url: str) -> None:
    st.markdown('###### 🎮 Controles do navegador real')
    st.caption('Agora você pode clicar/tocar diretamente no snapshot acima. Os campos X/Y continuam como fallback fino quando precisar acertar uma posição manualmente.')

    coord_col1, coord_col2 = st.columns(2)
    with coord_col1:
        click_x = st.number_input('Clique X', min_value=0, max_value=REMOTE_VIEWPORT_WIDTH - 1, value=100, step=10, key='remote_browser_click_x')
    with coord_col2:
        click_y = st.number_input('Clique Y', min_value=0, max_value=REMOTE_VIEWPORT_HEIGHT - 1, value=100, step=10, key='remote_browser_click_y')
    if st.button('🎯 Clicar na coordenada X/Y', use_container_width=True, key='remote_click_xy'):
        _run_browser_action(
            supplier_url,
            RemoteBrowserCommand(action='click_xy', x=int(click_x), y=int(click_y)),
            f'Clicando na coordenada X={int(click_x)} Y={int(click_y)}...',
        )

    st.divider()
    selector = st.text_input('Seletor CSS para clicar ou digitar', placeholder='input[name="email"] ou button[type="submit"]', key='remote_browser_selector')
    text_value = st.text_input('Texto para digitar no seletor acima', key='remote_browser_type_text')
    click_text = st.text_input('Ou clicar em texto visível', placeholder='Entrar, Produtos, Próxima página...', key='remote_browser_click_text')
    key_value = st.text_input('Tecla para pressionar', value='Enter', key='remote_browser_key_value')

    col1, col2 = st.columns(2)
    with col1:
        if st.button('🖱️ Clicar seletor', use_container_width=True, key='remote_click_selector'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_selector', value=selector), 'Clicando no seletor...')
        if st.button('⌨️ Digitar no seletor', use_container_width=True, key='remote_type_selector'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='type_selector', value=selector, text=text_value), 'Digitando no campo...')
        if st.button('⬇️ Rolar para baixo', use_container_width=True, key='remote_scroll_down'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='scroll_down'), 'Rolando página...')
    with col2:
        if st.button('🔎 Clicar texto', use_container_width=True, key='remote_click_text'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_text', value=click_text), 'Clicando no texto...')
        if st.button('↩️ Pressionar tecla', use_container_width=True, key='remote_press_key'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='press', value=key_value), 'Pressionando tecla...')
        if st.button('⬆️ Rolar para cima', use_container_width=True, key='remote_scroll_up'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='scroll_up'), 'Rolando página...')

    if st.button('🔄 Atualizar snapshot', use_container_width=True, key='remote_refresh_snapshot'):
        _run_browser_action(supplier_url, RemoteBrowserCommand(action='snapshot'), 'Atualizando snapshot...')


def _render_remote_browser_snapshot(supplier_url: str) -> None:
    st.caption('Navegador real do sistema: o servidor abre a página em Chromium. Você pode clicar no snapshot ou usar comandos auxiliares.')
    if st.button('🌐 Abrir navegador real do sistema', use_container_width=True, key='open_remote_supplier_browser_snapshot'):
        if not _is_valid_http_url(supplier_url):
            _orange_warning('Informe uma URL válida do fornecedor, começando com http:// ou https://.')
            return
        with st.spinner('Abrindo navegador real do sistema...'):
            snapshot = open_remote_browser_snapshot(
                RemoteBrowserConfig(
                    url=supplier_url,
                    state_namespace=_state_namespace(),
                    headless=True,
                    width=REMOTE_VIEWPORT_WIDTH,
                    height=REMOTE_VIEWPORT_HEIGHT,
                )
            )
        _display_snapshot(snapshot, supplier_url)

    if bool(st.session_state.get(REMOTE_SNAPSHOT_OK_KEY, False)):
        title = str(st.session_state.get(REMOTE_SNAPSHOT_TITLE_KEY) or 'Snapshot carregado')
        final_url = str(st.session_state.get(REMOTE_SNAPSHOT_FINAL_URL_KEY) or supplier_url)
        st.success(f'Navegador real carregado: {title}')
        st.caption(final_url)
        _consume_click_from_snapshot_if_needed(supplier_url)
        _render_clickable_snapshot(supplier_url)
        _render_remote_controls(supplier_url)

    _orange_warning('Se o clique direto no snapshot não atualizar em algum navegador móvel, use os campos X/Y logo abaixo como fallback. Se houver captcha, SMS/2FA ou bloqueio humano forte, use a compatibilidade universal.')


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
    st.success(f'Navegador real controlado preparado para {domain} em {last_prepared}.')
    st.caption(f'Pronto para captura de {label}. O sistema usará Chromium/Playwright no servidor e não iframe.')


def render_guided_login_panel() -> None:
    _clear_legacy_external_login_state()
    operation = _current_operation()
    operation_label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.markdown('##### Navegador real controlado')
    st.caption(f'Use esta área para operar o Chromium do servidor por clique no snapshot, comandos auxiliares e preparar a captura de {operation_label}.')

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
