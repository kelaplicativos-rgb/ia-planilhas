
from __future__ import annotations

import pandas as pd
from typing import Any

from bling_app_zero.core.session_manager import (
    STATUS_LOGIN_CAPTCHA_DETECTADO,
    STATUS_LOGIN_REQUERIDO,
    montar_auth_context,
)
from bling_app_zero.core.fetch_router import fetch_html
from bling_app_zero.core.site_crawler import crawl_site
from bling_app_zero.ui.app_helpers import log_debug


# ============================================================
# HELPERS
# ============================================================

def _log_debug(msg: str, nivel: str = "INFO"):
    try:
        log_debug(msg, nivel=nivel)
    except Exception:
        pass


def _auth_context_valido(auth_context: dict[str, Any] | None) -> bool:
    if not isinstance(auth_context, dict):
        return False

    # 🔥 LIBERA modo manual
    if auth_context.get("manual_mode"):
        return True

    return bool(auth_context.get("session_ready", False))


# ============================================================
# MAIN
# ============================================================

def executar_busca_site(
    *,
    url: str,
    fornecedor: str = "",
    usar_auth: bool = True,
) -> pd.DataFrame:

    url = (url or "").strip()
    if not url:
        _log_debug("URL vazia para busca", nivel="ERRO")
        return pd.DataFrame()

    # ========================================================
    # AUTH CONTEXT
    # ========================================================

    auth_context = {}
    if usar_auth:
        auth_context = montar_auth_context(base_url=url, fornecedor=fornecedor)

    # 🔥 LOG NOVO
    _log_debug(
        f"Auth context | manual_mode={auth_context.get('manual_mode')} | session_ready={auth_context.get('session_ready')}",
        nivel="INFO",
    )

    # ========================================================
    # FETCH INICIAL
    # ========================================================

    html, status_info = fetch_html(
        url=url,
        auth_context=auth_context,
    )

    login_status = status_info.get("status", "")
    login_status_normalizado = str(login_status).strip().lower()

    manual_mode = isinstance(auth_context, dict) and auth_context.get("manual_mode")

    # ========================================================
    # BLOQUEIO INTELIGENTE
    # ========================================================

    if (
        login_status_normalizado in {STATUS_LOGIN_CAPTCHA_DETECTADO, STATUS_LOGIN_REQUERIDO}
        and not _auth_context_valido(auth_context)
        and not manual_mode
    ):
        _log_debug(
            f"Bloqueado por login/captcha | status={login_status_normalizado}",
            nivel="WARNING",
        )
        return pd.DataFrame()

    # ========================================================
    # CRAWL
    # ========================================================

    try:
        df = crawl_site(
            base_url=url,
            auth_context=auth_context,
        )

        if df is None or df.empty:
            _log_debug("Crawler retornou vazio", nivel="WARNING")
            return pd.DataFrame()

        _log_debug(f"Produtos encontrados: {len(df)}", nivel="INFO")

        return df

    except Exception as e:
        _log_debug(f"Erro no crawler: {e}", nivel="ERRO")
        return pd.DataFrame()
