from __future__ import annotations

from urllib.parse import urlparse

import streamlit as st

from bling_app_zero.core.instant_scraper.auth_fetcher import fetch_html_with_auth, normalize_cookie
from bling_app_zero.ui.app_helpers import log_debug


AUTH_KEYS = [
    "site_auth_cookie",
    "site_auth_enabled",
    "site_auth_last_test_url",
    "site_auth_last_status",
]


def _normalizar_url(url: str) -> str:
    valor = str(url or "").strip()
    if not valor:
        return ""
    if not valor.startswith(("http://", "https://")):
        valor = "https://" + valor
    return valor


def _domain(url: str) -> str:
    try:
        return urlparse(_normalizar_url(url)).netloc.replace("www.", "")
    except Exception:
        return ""


def get_site_auth_context() -> dict:
    if not st.session_state.get("site_auth_enabled", False):
        return {}
    cookie = normalize_cookie(st.session_state.get("site_auth_cookie", ""))
    if not cookie:
        return {}
    return {"cookie": cookie}


def clear_site_auth_context() -> None:
    for key in AUTH_KEYS:
        st.session_state.pop(key, None)
    log_debug("Sessão/cookie de site removido pelo usuário.", nivel="INFO")


def render_site_auth_panel(base_url: str = "") -> None:
    with st.expander("🔐 Login assistido / Cookie Bot seguro", expanded=False):
        st.caption(
            "Use para sites com WhatsApp, CAPTCHA ou área logada. "
            "O app não burla CAPTCHA nem código; você faz login no navegador e cola aqui o cookie da sua própria sessão."
        )

        dominio = _domain(base_url)
        if dominio:
            st.info(f"Domínio detectado: {dominio}")

        enabled = st.checkbox(
            "Usar sessão logada nesta captura",
            value=bool(st.session_state.get("site_auth_enabled", False)),
            key="site_auth_enabled_widget",
        )
        st.session_state["site_auth_enabled"] = bool(enabled)

        cookie_atual = str(st.session_state.get("site_auth_cookie", "") or "")
        cookie = st.text_area(
            "Cookie da sessão logada",
            value=cookie_atual,
            height=90,
            type="password",
            key="site_auth_cookie_widget",
            placeholder="Ex.: PHPSESSID=...; token=...; session=...",
            help="Cole apenas cookies da sua própria conta/sessão. Não cole senha.",
        )
        st.session_state["site_auth_cookie"] = normalize_cookie(cookie)

        c1, c2 = st.columns(2)
        with c1:
            testar = st.button("🧪 Testar sessão", use_container_width=True, key="btn_testar_cookie_site")
        with c2:
            limpar = st.button("🧹 Limpar sessão", use_container_width=True, key="btn_limpar_cookie_site")

        if limpar:
            clear_site_auth_context()
            st.success("Sessão removida.")
            st.rerun()

        if testar:
            test_url = _normalizar_url(base_url)
            if not test_url:
                st.error("Informe uma URL do site antes de testar.")
                return
            ctx = get_site_auth_context()
            if not ctx:
                st.error("Ative a sessão logada e cole um cookie válido.")
                return
            html = fetch_html_with_auth(test_url, auth_context=ctx)
            st.session_state["site_auth_last_test_url"] = test_url
            if html:
                st.session_state["site_auth_last_status"] = "ok"
                log_debug(f"Cookie Bot: sessão validada para {test_url} com HTML de {len(html)} caracteres.", nivel="INFO")
                st.success(f"Sessão validada. HTML recebido: {len(html)} caracteres.")
            else:
                st.session_state["site_auth_last_status"] = "falha"
                log_debug(f"Cookie Bot: falha ao validar sessão para {test_url}.", nivel="AVISO")
                st.warning("Não consegui validar a sessão. O cookie pode ter expirado ou o site pode exigir novo login/código.")

        status = str(st.session_state.get("site_auth_last_status", "") or "")
        if status == "ok":
            st.success("Último teste de sessão: OK")
        elif status == "falha":
            st.warning("Último teste de sessão: falhou")
