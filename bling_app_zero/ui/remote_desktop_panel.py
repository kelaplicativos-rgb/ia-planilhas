from __future__ import annotations

from urllib.parse import quote, urlparse

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/remote_desktop_panel.py'
REMOTE_DESKTOP_URL_KEYS = (
    'remote_desktop_url',
    'novnc_url',
    'browser_desktop_url',
)


def _secret_value(*keys: str) -> str:
    for key in keys:
        try:
            value = st.secrets.get(key, '')
            if value:
                return str(value).strip()
        except Exception:
            pass
    try:
        remote = st.secrets.get('remote_desktop', {})
        if isinstance(remote, dict):
            for key in keys:
                value = remote.get(key, '')
                if value:
                    return str(value).strip()
    except Exception:
        pass
    return ''


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(str(value or '').strip())
    except Exception:
        return False
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _remote_desktop_url() -> str:
    for key in REMOTE_DESKTOP_URL_KEYS:
        session_value = str(st.session_state.get(key) or '').strip()
        if session_value:
            return session_value
    return _secret_value('url', 'remote_desktop_url', 'novnc_url', 'browser_desktop_url')


def _with_autoconnect(url: str) -> str:
    clean = str(url or '').strip()
    if not clean:
        return ''
    separator = '&' if '?' in clean else '?'
    if 'autoconnect=' not in clean:
        clean = f'{clean}{separator}autoconnect=true'
        separator = '&'
    if 'resize=' not in clean:
        clean = f'{clean}{separator}resize=scale'
    return clean


def render_remote_desktop_panel(*, supplier_url: str, operation: str) -> bool:
    """Renderiza um navegador remoto real via noVNC quando configurado.

    Retorna True quando a URL noVNC está configurada e o painel foi exibido.
    Retorna False quando ainda falta configurar o serviço externo de desktop remoto.
    """
    desktop_url = _remote_desktop_url()
    st.markdown('##### Navegador remoto real')
    st.caption('Use esta opção para login forte, CAPTCHA e sites que precisam de clique/teclado humano real.')

    if not _is_http_url(desktop_url):
        st.markdown(
            '<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;">⚠️ BLINGREMOTE DESKTOP ainda não está conectado a um serviço noVNC. Configure <b>[remote_desktop].url</b> nos secrets apontando para um Chrome remoto/noVNC.</div>',
            unsafe_allow_html=True,
        )
        st.code(
            '[remote_desktop]\nurl = "https://SEU-NOVNC/websockify-ou-vnc.html?autoconnect=true&resize=scale"',
            language='toml',
        )
        st.caption('Depois disso, esta área vira um navegador vivo: você clica e digita diretamente nele. Sem snapshot, sem coordenada, sem iframe clone.')
        return False

    final_desktop_url = _with_autoconnect(desktop_url)
    encoded_supplier = quote(str(supplier_url or ''), safe=':/?&=%#.-_')

    st.success('Navegador remoto real disponível. Use a tela abaixo para login, CAPTCHA e navegação até produtos.')
    st.caption('Quando terminar o login e chegar na página de produtos, volte ao fluxo e marque que a página está pronta para captura/importação.')
    components.html(
        f'''
        <div style="border:1px solid #d8dee9;border-radius:16px;overflow:hidden;background:#0f172a;box-shadow:0 14px 34px rgba(15,23,42,.22);">
          <div style="display:flex;gap:8px;align-items:center;background:#111827;color:#e5e7eb;padding:10px 12px;font-family:Arial,sans-serif;font-size:13px;">
            <span style="width:10px;height:10px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
            <span style="width:10px;height:10px;border-radius:50%;background:#f59e0b;display:inline-block;"></span>
            <span style="width:10px;height:10px;border-radius:50%;background:#22c55e;display:inline-block;"></span>
            <strong style="margin-left:8px;">Chrome remoto / noVNC</strong>
            <span style="opacity:.72;margin-left:auto;">Fornecedor: {encoded_supplier}</span>
          </div>
          <iframe
            src="{final_desktop_url}"
            style="width:100%;height:860px;border:0;background:#111827;"
            allow="clipboard-read; clipboard-write; fullscreen"
            referrerpolicy="no-referrer-when-downgrade"
          ></iframe>
        </div>
        ''',
        height=930,
        scrolling=True,
    )
    add_audit_event(
        'remote_desktop_panel_rendered',
        area='LOGIN_GUIADO',
        status='OK',
        details={'operation': operation, 'has_supplier_url': bool(supplier_url), 'responsible_file': RESPONSIBLE_FILE},
    )
    return True


__all__ = ['render_remote_desktop_panel']
