from __future__ import annotations

import base64
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
REMOTE_VIEWPORT_WIDTH = 1600
REMOTE_VIEWPORT_HEIGHT = 1000
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
        'mirror_panel': True,
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
Navegador real do sistema via Playwright/Chromium com tela ampla e painel espelhado.
O usuário opera por campos simples fora do navegador, e o sistema replica no Chromium.

Regras:
- Não usar iframe como fonte de verdade.
- Não assumir que aba externa do celular compartilha sessão com o servidor.
- Não salvar credenciais no sistema.
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


def _remote_config(url: str) -> RemoteBrowserConfig:
    return RemoteBrowserConfig(
        url=url,
        state_namespace=_state_namespace(),
        headless=True,
        width=REMOTE_VIEWPORT_WIDTH,
        height=REMOTE_VIEWPORT_HEIGHT,
    )


def _render_clickable_snapshot(supplier_url: str) -> None:
    png = st.session_state.get(REMOTE_SNAPSHOT_PNG_KEY)
    if not isinstance(png, (bytes, bytearray)) or not png:
        return
    title = str(st.session_state.get(REMOTE_SNAPSHOT_TITLE_KEY) or st.session_state.get(REMOTE_SNAPSHOT_FINAL_URL_KEY) or supplier_url)
    encoded = base64.b64encode(bytes(png)).decode('ascii')
    html = f'''
    <div style="font-family:Arial,sans-serif;margin:8px 0 14px 0;">
      <div style="background:#0f172a;border:1px solid #1e293b;border-radius:16px;overflow:hidden;box-shadow:0 12px 30px rgba(15,23,42,.22);">
        <div style="display:flex;align-items:center;gap:8px;background:#111827;color:#e5e7eb;padding:9px 12px;font-size:13px;">
          <span style="width:10px;height:10px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
          <span style="width:10px;height:10px;border-radius:50%;background:#f59e0b;display:inline-block;"></span>
          <span style="width:10px;height:10px;border-radius:50%;background:#22c55e;display:inline-block;"></span>
          <span style="margin-left:8px;opacity:.9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{title}</span>
        </div>
        <div style="position:relative;overflow:auto;background:#020617;max-height:820px;">
          <img id="blingRemoteBrowserImage" src="data:image/png;base64,{encoded}" alt="{title}" style="width:100%;min-width:760px;display:block;cursor:crosshair;user-select:none;-webkit-user-select:none;" />
          <div id="blingRemoteBrowserPoint" style="display:none;position:absolute;width:22px;height:22px;margin-left:-11px;margin-top:-11px;border:3px solid #fb8c00;border-radius:50%;background:rgba(251,140,0,.20);pointer-events:none;"></div>
        </div>
      </div>
      <div id="blingRemoteBrowserStatus" style="font-size:12px;color:#475569;margin-top:6px;">Tela ampla ativa: clique/toque na imagem ou use os campos espelhados abaixo.</div>
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
    components.html(html, height=920, scrolling=True)


def _store_snapshot(snapshot, supplier_url: str) -> None:
    """Salva o snapshot no estado, sem renderizar aqui.

    A renderização visual fica centralizada em _render_remote_browser_snapshot().
    Isso evita aparecerem dois navegadores na tela após abrir, clicar ou atualizar.
    """
    st.session_state[REMOTE_SNAPSHOT_OK_KEY] = bool(snapshot.ok)
    st.session_state[REMOTE_SNAPSHOT_URL_KEY] = supplier_url
    st.session_state[REMOTE_SNAPSHOT_FINAL_URL_KEY] = snapshot.final_url or supplier_url
    st.session_state[REMOTE_SNAPSHOT_TITLE_KEY] = snapshot.title or ''
    st.session_state['remote_browser_last_warnings'] = [str(w) for w in getattr(snapshot, 'warnings', [])]
    st.session_state['remote_browser_last_errors'] = [str(e) for e in getattr(snapshot, 'errors', [])]
    if getattr(snapshot, 'screenshot_png', None):
        st.session_state[REMOTE_SNAPSHOT_PNG_KEY] = bytes(snapshot.screenshot_png)


def _render_snapshot_messages() -> None:
    for warning in st.session_state.get('remote_browser_last_warnings', []) or []:
        _orange_warning(str(warning))
    errors = st.session_state.get('remote_browser_last_errors', []) or []
    if errors:
        st.error('Não consegui executar esta ação no navegador real do sistema.')
        for error in errors:
            st.caption(str(error))
        _orange_warning('Se o fornecedor exigir captcha, 2FA, popup ou bloquear robô, use a compatibilidade universal: exporte/cole/importar HTML, CSV, XLSX ou tabela.')


def _run_browser_action(supplier_url: str, command: RemoteBrowserCommand, label: str) -> None:
    current_url = _current_remote_url(supplier_url)
    if not _is_valid_http_url(current_url):
        _orange_warning('Abra primeiro uma URL válida no navegador real do sistema.')
        return
    with st.spinner(label):
        snapshot = run_remote_browser_command(_remote_config(current_url), command)
    _store_snapshot(snapshot, current_url)


def _consume_click_from_snapshot_if_needed(supplier_url: str) -> None:
    nonce = _query_param(REMOTE_CLICK_NONCE_PARAM)
    if not nonce:
        return
    if nonce == str(st.session_state.get(REMOTE_LAST_CLICK_NONCE_KEY) or ''):
        return
    x = max(0, min(_safe_int(_query_param(REMOTE_CLICK_X_PARAM), 0), REMOTE_VIEWPORT_WIDTH - 1))
    y = max(0, min(_safe_int(_query_param(REMOTE_CLICK_Y_PARAM), 0), REMOTE_VIEWPORT_HEIGHT - 1))
    st.session_state[REMOTE_LAST_CLICK_NONCE_KEY] = nonce
    _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_xy', x=x, y=y), f'Clicando no navegador em X={x} Y={y}...')


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

    add_debug(f'Navegador real espelhado preparado para domínio {config.get("domain")}.', origin='LOGIN_GUIADO')
    add_audit_event(
        'remote_mirror_supplier_browser_prepared',
        area='LOGIN_GUIADO',
        details={'domain': config.get('domain'), 'operation': operation, 'mirror_panel': True, 'responsible_file': RESPONSIBLE_FILE},
    )


def _render_mirror_panel(supplier_url: str) -> None:
    st.markdown('#### Painel espelhado')
    st.caption('Digite aqui fora do navegador. O sistema replica no Chromium acima usando reconhecimento inteligente de campos.')

    with st.container():
        login_col, pass_col = st.columns(2)
        with login_col:
            mirror_user = st.text_input('Usuário / e-mail', key='remote_mirror_user', placeholder='Digite o usuário do fornecedor')
        with pass_col:
            mirror_password = st.text_input('Senha', key='remote_mirror_password', type='password', placeholder='Digite a senha somente para enviar ao navegador')

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button('Preencher usuário', use_container_width=True, key='remote_mirror_fill_user'):
                _run_browser_action(supplier_url, RemoteBrowserCommand(action='type_smart', value='user', text=mirror_user), 'Preenchendo usuário no navegador...')
                st.rerun()
        with action_col2:
            if st.button('Preencher senha', use_container_width=True, key='remote_mirror_fill_password'):
                _run_browser_action(supplier_url, RemoteBrowserCommand(action='type_smart', value='password', text=mirror_password), 'Preenchendo senha no navegador...')
                st.rerun()
        with action_col3:
            if st.button('Entrar', use_container_width=True, key='remote_mirror_login'):
                _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_smart', value='login'), 'Tentando entrar...')
                st.rerun()

    st.divider()
    search_col, nav_col = st.columns([2, 1])
    with search_col:
        mirror_search = st.text_input('Buscar produto / termo', key='remote_mirror_search', placeholder='Nome, SKU, código ou termo de busca')
    with nav_col:
        st.write('')
        st.write('')
        if st.button('Buscar', use_container_width=True, key='remote_mirror_search_button'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='type_smart', value='search', text=mirror_search), 'Preenchendo busca...')
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='press', value='Enter'), 'Executando busca...')
            st.rerun()

    quick1, quick2, quick3, quick4 = st.columns(4)
    with quick1:
        if st.button('Ir para Produtos', use_container_width=True, key='remote_mirror_products'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_smart', value='produtos'), 'Abrindo produtos...')
            st.rerun()
    with quick2:
        if st.button('Enter', use_container_width=True, key='remote_mirror_enter'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='press', value='Enter'), 'Pressionando Enter...')
            st.rerun()
    with quick3:
        if st.button('Rolar ↓', use_container_width=True, key='remote_mirror_scroll_down'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='scroll_down'), 'Rolando página...')
            st.rerun()
    with quick4:
        if st.button('Atualizar tela', use_container_width=True, key='remote_mirror_refresh'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='snapshot'), 'Atualizando tela...')
            st.rerun()


def _render_advanced_controls(supplier_url: str) -> None:
    show_advanced = st.checkbox('Mostrar comandos avançados', value=False, key='remote_show_advanced_controls')
    if not show_advanced:
        return

    st.markdown('##### Comandos avançados')
    st.caption('Use apenas quando o painel espelhado não encontrar o campo certo. Este bloco não usa expander para evitar erro de expander aninhado no Streamlit.')
    coord_col1, coord_col2 = st.columns(2)
    with coord_col1:
        click_x = st.number_input('Clique X', min_value=0, max_value=REMOTE_VIEWPORT_WIDTH - 1, value=100, step=10, key='remote_browser_click_x')
    with coord_col2:
        click_y = st.number_input('Clique Y', min_value=0, max_value=REMOTE_VIEWPORT_HEIGHT - 1, value=100, step=10, key='remote_browser_click_y')
    if st.button('Clicar na coordenada X/Y', use_container_width=True, key='remote_click_xy'):
        _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_xy', x=int(click_x), y=int(click_y)), f'Clicando em X={int(click_x)} Y={int(click_y)}...')
        st.rerun()

    selector = st.text_input('Seletor CSS', placeholder='input[name="email"] ou button[type="submit"]', key='remote_browser_selector')
    text_value = st.text_input('Texto para digitar no seletor', key='remote_browser_type_text')
    click_text = st.text_input('Clicar em texto visível', placeholder='Entrar, Produtos, Próxima página...', key='remote_browser_click_text')
    key_value = st.text_input('Tecla', value='Enter', key='remote_browser_key_value')

    c1, c2 = st.columns(2)
    with c1:
        if st.button('Clicar seletor', use_container_width=True, key='remote_click_selector'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_selector', value=selector), 'Clicando seletor...')
            st.rerun()
        if st.button('Digitar seletor', use_container_width=True, key='remote_type_selector'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='type_selector', value=selector, text=text_value), 'Digitando seletor...')
            st.rerun()
    with c2:
        if st.button('Clicar texto', use_container_width=True, key='remote_click_text'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='click_text', value=click_text), 'Clicando texto...')
            st.rerun()
        if st.button('Pressionar tecla', use_container_width=True, key='remote_press_key'):
            _run_browser_action(supplier_url, RemoteBrowserCommand(action='press', value=key_value), 'Pressionando tecla...')
            st.rerun()


def _render_remote_browser_snapshot(supplier_url: str) -> None:
    st.caption('Navegador real do sistema em tela ampla. Use o painel espelhado abaixo para digitar sem depender do print.')
    if st.button('Abrir / atualizar navegador real', use_container_width=True, key='open_remote_supplier_browser_snapshot'):
        if not _is_valid_http_url(supplier_url):
            _orange_warning('Informe uma URL válida do fornecedor, começando com http:// ou https://.')
            return
        with st.spinner('Abrindo navegador real do sistema...'):
            snapshot = open_remote_browser_snapshot(_remote_config(supplier_url))
        _store_snapshot(snapshot, supplier_url)
        st.rerun()

    if bool(st.session_state.get(REMOTE_SNAPSHOT_OK_KEY, False)):
        title = str(st.session_state.get(REMOTE_SNAPSHOT_TITLE_KEY) or 'Tela carregada')
        final_url = str(st.session_state.get(REMOTE_SNAPSHOT_FINAL_URL_KEY) or supplier_url)
        st.success(f'Tela ativa: {title}')
        st.caption(final_url)
        _consume_click_from_snapshot_if_needed(supplier_url)
        _render_snapshot_messages()
        _render_clickable_snapshot(supplier_url)
        _render_mirror_panel(supplier_url)
        _render_advanced_controls(supplier_url)

    _orange_warning('O sistema não salva sua senha. Ela fica apenas no campo visual do Streamlit enquanto você envia ao navegador. Se houver captcha, SMS/2FA ou bloqueio humano forte, use a compatibilidade universal.')


def _render_page_confirmation() -> None:
    st.checkbox(
        'A tela acima mostra a página correta de produtos/catálogo',
        value=bool(st.session_state.get(PAGE_READY_KEY, False)),
        key=PAGE_READY_KEY,
        help='Marque somente depois que o navegador real mostrar a página que deve ser capturada.',
    )
    if not bool(st.session_state.get(PAGE_READY_KEY, False)):
        _orange_warning('A captura fica bloqueada até você confirmar que a tela mostra a página correta de produtos.')


def _render_prepared_config() -> None:
    config = st.session_state.get(CONFIG_KEY)
    if not isinstance(config, dict):
        return
    last_prepared = st.session_state.get(LAST_PREPARED_KEY, 'agora')
    domain = str(config.get('domain') or '').strip() or 'site informado'
    operation = str(config.get('operation') or 'cadastro').strip()
    label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.success(f'Navegador real preparado para {domain} em {last_prepared}.')
    st.caption(f'Pronto para captura de {label}.')


def render_guided_login_panel() -> None:
    _clear_legacy_external_login_state()
    operation = _current_operation()
    operation_label = 'estoque' if operation == 'estoque' else 'cadastro'
    st.markdown('##### Navegador real com painel espelhado')
    st.caption(f'Tela ampla em cima, campos simples embaixo. Preparando captura de {operation_label}.')

    supplier_url = st.text_input(
        'URL do fornecedor ou da página de produtos',
        value=str(st.session_state.get('guided_login_url') or DEFAULT_SUPPLIER_URL),
        placeholder='https://site-do-fornecedor.com.br/admin',
        key='guided_login_url',
    )

    _render_remote_browser_snapshot(supplier_url)
    _render_page_confirmation()

    can_prepare = bool(st.session_state.get(REMOTE_SNAPSHOT_OK_KEY, False)) and bool(st.session_state.get(PAGE_READY_KEY, False))
    if st.button('Preparar captura desta página', use_container_width=True, key='prepare_guided_login_capture', disabled=not can_prepare):
        _prepare_config(supplier_url=supplier_url, operation=operation)
    if not can_prepare:
        st.caption('Para liberar este botão, abra a tela do navegador real e confirme que ela mostra a página de produtos.')
    _render_prepared_config()


__all__ = ['render_guided_login_panel']
