from __future__ import annotations

from typing import Any

from bling_app_zero.core.fetcher import fetch_url

# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(_msg: str, _nivel: str = "INFO") -> None:
        return None


# ==========================================================
# PLAYWRIGHT
# ==========================================================
try:
    from bling_app_zero.core.playwright_fetcher import fetch_playwright_payload
except Exception:
    fetch_playwright_payload = None


# ==========================================================
# VERSION (DEBUG)
# ==========================================================
ROUTER_VERSION = "V3_AUTH_READY_COMPAT"


# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(v: Any) -> str:
    try:
        return str(v or "").strip()
    except Exception:
        return ""


def _safe_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    texto = _safe_str(v).lower()
    return texto in {"1", "true", "sim", "yes", "y", "on"}


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _html_ruim(html: str | None) -> bool:
    if not html:
        return True

    html = str(html).strip()
    if not html:
        return True

    if len(html) > 2000:
        return False

    h = html.lower()

    sinais_bloqueio = [
        "captcha",
        "cloudflare",
        "access denied",
        "forbidden",
        "enable javascript",
        "javascript required",
        "please enable javascript",
        "blocked",
        "verify you are human",
    ]

    if any(s in h for s in sinais_bloqueio):
        return True

    sinais_login = [
        'type="password"',
        'name="password"',
        'autocomplete="current-password"',
        "esqueci minha senha",
        "fazer login",
        "entrar",
        "sign in",
        "login",
    ]

    # Só considera "ruim" por login quando a página é muito curta.
    if len(h) < 2500 and any(s in h for s in sinais_login):
        return True

    return False


def _montar_payload_base(
    *,
    ok: bool,
    engine: str,
    url: str,
    html: str = "",
    error: str = "",
    final_url: str = "",
    status_code: int | None = None,
    auth_used: bool = False,
    auth_mode: str = "none",
    login_required: bool = False,
    login_configured: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "engine": _safe_str(engine),
        "url": _safe_str(url),
        "final_url": _safe_str(final_url) or _safe_str(url),
        "html": html or "",
        "error": _safe_str(error),
        "status_code": status_code,
        "auth_used": bool(auth_used),
        "auth_mode": _safe_str(auth_mode) or "none",
        "login_required": bool(login_required),
        "login_configured": bool(login_configured),
        "metadata": metadata or {},
        "router_version": ROUTER_VERSION,
    }


def _merge_payload_context(
    payload: dict[str, Any] | None,
    *,
    auth_used: bool,
    auth_mode: str,
    login_required: bool,
    login_configured: bool,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    payload["auth_used"] = bool(auth_used)
    payload["auth_mode"] = _safe_str(auth_mode) or "none"
    payload["login_required"] = bool(login_required)
    payload["login_configured"] = bool(login_configured)
    payload["metadata"] = metadata or payload.get("metadata") or {}
    payload["router_version"] = ROUTER_VERSION
    return payload


def _resolver_auth_context(
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_config = auth_config or {}

    usuario_final = _safe_str(auth_config.get("usuario") or auth_config.get("username") or usuario)
    senha_final = _safe_str(auth_config.get("senha") or auth_config.get("password") or senha)
    precisa_login_final = _safe_bool(
        auth_config.get("precisa_login")
        if "precisa_login" in auth_config
        else precisa_login
    )

    login_configured = bool(usuario_final and senha_final)
    auth_used = bool(precisa_login_final and login_configured)
    auth_mode = "login_password" if auth_used else "none"

    return {
        "usuario": usuario_final,
        "senha": senha_final,
        "precisa_login": precisa_login_final,
        "login_configured": login_configured,
        "auth_used": auth_used,
        "auth_mode": auth_mode,
    }


# ==========================================================
# REQUESTS
# ==========================================================
def _fetch_requests(
    url: str,
    *,
    extra_headers: dict[str, Any] | None = None,
    auth_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_context = auth_context or {}

    try:
        html = fetch_url(url, extra_headers=extra_headers)
        html = _safe_str(html)

        return _montar_payload_base(
            ok=bool(html),
            engine="requests",
            url=url,
            html=html,
            error="" if html else "html_vazio",
            auth_used=bool(auth_context.get("auth_used")),
            auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
            login_required=bool(auth_context.get("precisa_login")),
            login_configured=bool(auth_context.get("login_configured")),
        )
    except Exception as e:
        return _montar_payload_base(
            ok=False,
            engine="requests",
            url=url,
            html="",
            error=str(e),
            auth_used=bool(auth_context.get("auth_used")),
            auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
            login_required=bool(auth_context.get("precisa_login")),
            login_configured=bool(auth_context.get("login_configured")),
        )


# ==========================================================
# PLAYWRIGHT
# ==========================================================
def _fetch_playwright(
    url: str,
    *,
    auth_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_context = auth_context or {}

    if not fetch_playwright_payload:
        return _montar_payload_base(
            ok=False,
            engine="playwright",
            url=url,
            html="",
            error="playwright_indisponivel",
            auth_used=bool(auth_context.get("auth_used")),
            auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
            login_required=bool(auth_context.get("precisa_login")),
            login_configured=bool(auth_context.get("login_configured")),
        )

    try:
        # Compatível com a base atual:
        # a função existente aceita só a URL.
        # Mantemos o contexto de autenticação no retorno do router,
        # deixando o módulo playwright_fetcher pronto para ser ampliado
        # sem quebrar este contrato.
        payload = fetch_playwright_payload(url) or {}
        html = _safe_str(payload.get("html"))
        final_url = _safe_str(payload.get("final_url") or url)
        error = _safe_str(payload.get("error"))

        return _montar_payload_base(
            ok=bool(html),
            engine="playwright",
            url=url,
            final_url=final_url,
            html=html,
            error=error if not html else error,
            auth_used=bool(auth_context.get("auth_used")),
            auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
            login_required=bool(auth_context.get("precisa_login")),
            login_configured=bool(auth_context.get("login_configured")),
        )
    except Exception as e:
        return _montar_payload_base(
            ok=False,
            engine="playwright",
            url=url,
            html="",
            error=str(e),
            auth_used=bool(auth_context.get("auth_used")),
            auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
            login_required=bool(auth_context.get("precisa_login")),
            login_configured=bool(auth_context.get("login_configured")),
        )


# ==========================================================
# REGRAS DE DECISÃO
# ==========================================================
def _deve_forcar_playwright(
    *,
    preferir_js: bool,
    auth_context: dict[str, Any] | None = None,
) -> bool:
    auth_context = auth_context or {}

    if preferir_js:
        return True

    if bool(auth_context.get("auth_used")):
        return True

    return False


def _deve_tentar_playwright_apos_requests(
    payload_requests: dict[str, Any] | None,
    *,
    auth_context: dict[str, Any] | None = None,
) -> bool:
    auth_context = auth_context or {}
    payload_requests = payload_requests or {}

    if bool(auth_context.get("auth_used")):
        return True

    html = _safe_str(payload_requests.get("html"))
    if _html_ruim(html):
        return True

    if not payload_requests.get("ok"):
        return True

    return False


# ==========================================================
# MAIN ROUTER
# ==========================================================
def fetch_payload_router(
    url: str,
    preferir_js: bool = False,
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
    extra_headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Router de captura compatível com a base atual e preparado para:
    - requests normal;
    - fallback Playwright;
    - contexto de login/senha no retorno;
    - futura expansão do playwright_fetcher para login autenticado.

    Assinatura antiga continua funcionando:
        fetch_payload_router(url, preferir_js=False)

    Nova forma:
        fetch_payload_router(
            url,
            preferir_js=True,
            usuario="login",
            senha="senha",
            precisa_login=True,
        )
    """
    url = _normalizar_url(url)
    if not url:
        return _montar_payload_base(
            ok=False,
            engine="none",
            url="",
            html="",
            error="url_invalida",
        )

    auth_context = _resolver_auth_context(
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
    )

    log_debug(
        (
            f"[FETCH_ROUTER] START | url={url} | preferir_js={preferir_js} | "
            f"precisa_login={auth_context['precisa_login']} | "
            f"login_configured={auth_context['login_configured']} | "
            f"auth_used={auth_context['auth_used']}"
        ),
        "INFO",
    )

    if auth_context["precisa_login"] and not auth_context["login_configured"]:
        log_debug(
            "[FETCH_ROUTER] site marcado com login, mas usuário/senha não foram informados",
            "WARNING",
        )

    # ======================================================
    # PRIORIDADE PLAYWRIGHT
    # ======================================================
    if _deve_forcar_playwright(
        preferir_js=preferir_js,
        auth_context=auth_context,
    ):
        log_debug("[FETCH_ROUTER] FORCANDO PLAYWRIGHT", "INFO")

        payload_pw = _fetch_playwright(
            url,
            auth_context=auth_context,
        )

        if payload_pw.get("ok") and not _html_ruim(payload_pw.get("html")):
            log_debug("[FETCH_ROUTER] PLAYWRIGHT OK", "INFO")
            return _merge_payload_context(
                payload_pw,
                auth_used=bool(auth_context.get("auth_used")),
                auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
                login_required=bool(auth_context.get("precisa_login")),
                login_configured=bool(auth_context.get("login_configured")),
                metadata={"path": "playwright_primeiro"},
            )

        log_debug("[FETCH_ROUTER] PLAYWRIGHT FALHOU, tentando requests", "WARNING")

    # ======================================================
    # REQUESTS
    # ======================================================
    payload_requests = _fetch_requests(
        url,
        extra_headers=extra_headers,
        auth_context=auth_context,
    )

    if payload_requests.get("ok") and not _html_ruim(payload_requests.get("html")):
        log_debug("[FETCH_ROUTER] REQUESTS OK", "INFO")
        return _merge_payload_context(
            payload_requests,
            auth_used=bool(auth_context.get("auth_used")),
            auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
            login_required=bool(auth_context.get("precisa_login")),
            login_configured=bool(auth_context.get("login_configured")),
            metadata={"path": "requests_ok"},
        )

    # ======================================================
    # FALLBACK PLAYWRIGHT
    # ======================================================
    if _deve_tentar_playwright_apos_requests(
        payload_requests,
        auth_context=auth_context,
    ):
        log_debug("[FETCH_ROUTER] REQUESTS FRACO → PLAYWRIGHT", "WARNING")

        payload_pw = _fetch_playwright(
            url,
            auth_context=auth_context,
        )

        if payload_pw.get("ok") and not _html_ruim(payload_pw.get("html")):
            log_debug("[FETCH_ROUTER] PLAYWRIGHT OK NO FALLBACK", "INFO")
            return _merge_payload_context(
                payload_pw,
                auth_used=bool(auth_context.get("auth_used")),
                auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
                login_required=bool(auth_context.get("precisa_login")),
                login_configured=bool(auth_context.get("login_configured")),
                metadata={"path": "requests_fallback_playwright"},
            )

    # ======================================================
    # FALHA TOTAL
    # ======================================================
    log_debug("[FETCH_ROUTER] FALHA TOTAL", "ERROR")

    erro_final = _safe_str(payload_requests.get("error")) or "falha_total_fetch"

    return _montar_payload_base(
        ok=False,
        engine="none",
        url=url,
        html="",
        error=erro_final,
        auth_used=bool(auth_context.get("auth_used")),
        auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
        login_required=bool(auth_context.get("precisa_login")),
        login_configured=bool(auth_context.get("login_configured")),
        metadata={"path": "falha_total"},
    )
