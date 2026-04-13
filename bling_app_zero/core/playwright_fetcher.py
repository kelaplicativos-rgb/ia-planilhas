from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# ==========================================================
# GARANTE CHROMIUM NO AMBIENTE
# ==========================================================
try:
    subprocess.run(
        ["playwright", "install", "chromium"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
except Exception:
    pass

# ==========================================================
# LOG (BLINDADO)
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    try:
        from bling_app_zero.utils.excel import log_debug
    except Exception:
        def log_debug(_msg: str, _nivel: str = "INFO") -> None:
            return None

# ==========================================================
# IMPORT PLAYWRIGHT
# ==========================================================
try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception


# ==========================================================
# CONFIG
# ==========================================================
PLAYWRIGHT_DEFAULT_TIMEOUT_MS = 30000
PLAYWRIGHT_NAV_TIMEOUT_MS = 45000
PLAYWRIGHT_WAIT_AFTER_LOAD_MS = 2500
PLAYWRIGHT_MAX_SCROLLS = 6
PLAYWRIGHT_SCROLL_PAUSE_MS = 800
PLAYWRIGHT_HTML_MAX_CHARS = 6_000_000
PLAYWRIGHT_MAX_NETWORK_RECORDS = 120

USER_AGENT_CHROMIUM = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

LOGIN_INPUT_SELECTORS = [
    'input[type="email"]',
    'input[name="email"]',
    'input[name="usuario"]',
    'input[name="user"]',
    'input[name="login"]',
    'input[name="username"]',
    'input[id*="email"]',
    'input[id*="user"]',
    'input[id*="login"]',
    'input[autocomplete="username"]',
    'input[type="text"]',
]

PASSWORD_INPUT_SELECTORS = [
    'input[type="password"]',
    'input[name="senha"]',
    'input[name="password"]',
    'input[id*="senha"]',
    'input[id*="password"]',
    'input[autocomplete="current-password"]',
]

SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Entrar")',
    'button:has-text("Login")',
    'button:has-text("Acessar")',
    'button:has-text("Continuar")',
    'a:has-text("Entrar")',
]

LOGIN_PAGE_HINTS = [
    'type="password"',
    'name="password"',
    'name="senha"',
    'autocomplete="current-password"',
    "fazer login",
    "entrar",
    "sign in",
    "login",
]

# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        return str(valor).strip()
    except Exception:
        return ""


def _safe_bool(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    texto = _safe_str(valor).lower()
    return texto in {"1", "true", "sim", "yes", "y", "on"}


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _dominio(url: str) -> str:
    try:
        return urlparse(_normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _arquivo_temp(prefixo: str, sufixo: str) -> str:
    pasta = Path(tempfile.gettempdir()) / "ia_planilhas_playwright"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = f"{prefixo}_{int(time.time() * 1000)}{sufixo}"
    return str(pasta / nome)


def _normalizar_html(html: str) -> str:
    html = html or ""
    if len(html) > PLAYWRIGHT_HTML_MAX_CHARS:
        return html[:PLAYWRIGHT_HTML_MAX_CHARS]
    return html


def _parece_bloqueio(texto: str) -> bool:
    t = (texto or "").lower()
    sinais = [
        "access denied",
        "forbidden",
        "captcha",
        "cloudflare",
        "attention required",
        "security check",
        "verify you are human",
        "robot or human",
        "cf-browser-verification",
        "please enable cookies",
    ]
    return any(s in t for s in sinais)


def _parece_pagina_login(texto: str) -> bool:
    t = (texto or "").lower()
    return any(s in t for s in LOGIN_PAGE_HINTS)


def _contexto_opcoes(storage_state_path: str | None = None) -> dict[str, Any]:
    opcoes: dict[str, Any] = {
        "user_agent": USER_AGENT_CHROMIUM,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "ignore_https_errors": True,
        "java_script_enabled": True,
        "viewport": {"width": 1440, "height": 2200},
        "extra_http_headers": {
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "DNT": "1",
        },
    }
    if storage_state_path and os.path.exists(storage_state_path):
        opcoes["storage_state"] = storage_state_path
    return opcoes


def _auto_scroll(page: Any, max_scrolls: int = PLAYWRIGHT_MAX_SCROLLS) -> None:
    try:
        altura_anterior = -1
        for i in range(max_scrolls):
            try:
                altura_atual = page.evaluate("() => document.body.scrollHeight")
            except Exception:
                altura_atual = None

            page.evaluate(
                """
                () => {
                    window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' });
                }
                """
            )
            page.wait_for_timeout(PLAYWRIGHT_SCROLL_PAUSE_MS)

            if altura_atual == altura_anterior:
                log_debug(f"[PLAYWRIGHT] Scroll estabilizado na iteração {i + 1}")
                break

            altura_anterior = altura_atual
    except Exception as exc:
        log_debug(
            f"[PLAYWRIGHT] Falha no auto scroll: {type(exc).__name__}: {exc}",
            "WARNING",
        )


def _esperar_estabilidade_basica(page: Any) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=PLAYWRIGHT_NAV_TIMEOUT_MS)
    except Exception:
        pass

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    try:
        page.wait_for_timeout(PLAYWRIGHT_WAIT_AFTER_LOAD_MS)
    except Exception:
        pass


def _serializar_json_seguro(valor: Any) -> str:
    try:
        return json.dumps(valor, ensure_ascii=False)
    except Exception:
        try:
            return str(valor)
        except Exception:
            return ""


def _limpar_texto_curto(texto: Any, limite: int = 500) -> str:
    s = re.sub(r"\s+", " ", _safe_str(texto))
    if len(s) > limite:
        return s[:limite]
    return s


def _extrair_json_de_response(response: Any) -> Any:
    try:
        request = response.request
        resource_type = _safe_str(getattr(request, "resource_type", ""))
        headers = getattr(response, "headers", {}) or {}
        content_type = _safe_str(headers.get("content-type", "")).lower()
        url = _safe_str(getattr(response, "url", ""))

        if "json" in content_type or resource_type in {"xhr", "fetch"} or url.endswith(".json"):
            try:
                return response.json()
            except Exception:
                try:
                    return response.text()
                except Exception:
                    return None
    except Exception:
        return None

    return None


def _resolver_auth_context(
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_config = auth_config or {}

    usuario_final = _safe_str(
        auth_config.get("usuario")
        or auth_config.get("username")
        or auth_config.get("email")
        or usuario
    )
    senha_final = _safe_str(
        auth_config.get("senha")
        or auth_config.get("password")
        or senha
    )
    precisa_login_final = _safe_bool(
        auth_config.get("precisa_login")
        if "precisa_login" in auth_config
        else precisa_login
    )

    login_url = _normalizar_url(
        auth_config.get("login_url") or auth_config.get("url_login") or ""
    )
    wait_selector_login = _safe_str(auth_config.get("wait_selector_login"))
    wait_selector_pos_login = _safe_str(auth_config.get("wait_selector_pos_login"))
    usuario_selector = _safe_str(auth_config.get("usuario_selector") or auth_config.get("username_selector"))
    senha_selector = _safe_str(auth_config.get("senha_selector") or auth_config.get("password_selector"))
    submit_selector = _safe_str(auth_config.get("submit_selector"))

    login_configured = bool(usuario_final and senha_final)
    auth_used = bool(precisa_login_final and login_configured)

    return {
        "usuario": usuario_final,
        "senha": senha_final,
        "precisa_login": precisa_login_final,
        "login_configured": login_configured,
        "auth_used": auth_used,
        "auth_mode": "login_password" if auth_used else "none",
        "login_url": login_url,
        "wait_selector_login": wait_selector_login,
        "wait_selector_pos_login": wait_selector_pos_login,
        "usuario_selector": usuario_selector,
        "senha_selector": senha_selector,
        "submit_selector": submit_selector,
    }


# ==========================================================
# NETWORK
# ==========================================================
def _preparar_captura_network(page: Any, registros: list[dict[str, Any]]) -> None:
    def _on_response(response: Any) -> None:
        if len(registros) >= PLAYWRIGHT_MAX_NETWORK_RECORDS:
            return

        try:
            request = response.request
            item: dict[str, Any] = {
                "url": _safe_str(getattr(response, "url", "")),
                "method": _safe_str(getattr(request, "method", "")),
                "resource_type": _safe_str(getattr(request, "resource_type", "")),
                "status": int(getattr(response, "status", 0) or 0),
                "content_type": _safe_str(
                    (getattr(response, "headers", {}) or {}).get("content-type", "")
                ).lower(),
            }

            data = _extrair_json_de_response(response)
            if data is not None:
                item["json"] = data
                item["json_preview"] = _limpar_texto_curto(_serializar_json_seguro(data), 800)

            registros.append(item)
        except Exception:
            pass

    page.on("response", _on_response)


# ==========================================================
# LOGIN
# ==========================================================
def _aguardar_primeiro_seletor(page: Any, seletores: list[str], timeout: int = 6000) -> str:
    for seletor in seletores:
        try:
            page.wait_for_selector(seletor, timeout=timeout, state="visible")
            return seletor
        except Exception:
            continue
    return ""


def _preencher_input(page: Any, seletor: str, valor: str) -> bool:
    try:
        el = page.locator(seletor).first
        el.click(timeout=3000)
        try:
            el.fill("")
        except Exception:
            pass
        el.fill(valor, timeout=5000)
        return True
    except Exception:
        try:
            page.fill(seletor, valor, timeout=5000)
            return True
        except Exception:
            return False


def _clicar_submit(page: Any, seletor: str = "") -> bool:
    if seletor:
        try:
            page.locator(seletor).first.click(timeout=5000)
            return True
        except Exception:
            pass

    for s in SUBMIT_SELECTORS:
        try:
            page.locator(s).first.click(timeout=4000)
            return True
        except Exception:
            continue

    try:
        page.keyboard.press("Enter")
        return True
    except Exception:
        return False


def _detectar_html_login(page: Any) -> str:
    try:
        return _safe_str(page.content())
    except Exception:
        return ""


def _executar_login(
    page: Any,
    *,
    url_destino: str,
    auth_context: dict[str, Any],
) -> dict[str, Any]:
    resultado = {
        "ok": False,
        "login_attempted": False,
        "login_success": False,
        "login_error": "",
        "login_url_final": "",
    }

    if not auth_context.get("precisa_login"):
        resultado["ok"] = True
        return resultado

    if not auth_context.get("login_configured"):
        resultado["login_error"] = "login_requerido_sem_credenciais"
        return resultado

    resultado["login_attempted"] = True

    login_url = _safe_str(auth_context.get("login_url")) or url_destino

    try:
        log_debug(f"[PLAYWRIGHT] LOGIN START | login_url={login_url}", "INFO")
        page.goto(login_url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_NAV_TIMEOUT_MS)
        _esperar_estabilidade_basica(page)

        wait_selector_login = _safe_str(auth_context.get("wait_selector_login"))
        if wait_selector_login:
            try:
                page.wait_for_selector(wait_selector_login, timeout=10000, state="visible")
            except Exception:
                pass

        usuario_selector = _safe_str(auth_context.get("usuario_selector"))
        senha_selector = _safe_str(auth_context.get("senha_selector"))
        submit_selector = _safe_str(auth_context.get("submit_selector"))

        if not usuario_selector:
            usuario_selector = _aguardar_primeiro_seletor(page, LOGIN_INPUT_SELECTORS)
        if not senha_selector:
            senha_selector = _aguardar_primeiro_seletor(page, PASSWORD_INPUT_SELECTORS)

        if not usuario_selector:
            resultado["login_error"] = "campo_usuario_nao_encontrado"
            return resultado

        if not senha_selector:
            resultado["login_error"] = "campo_senha_nao_encontrado"
            return resultado

        ok_usuario = _preencher_input(page, usuario_selector, _safe_str(auth_context.get("usuario")))
        ok_senha = _preencher_input(page, senha_selector, _safe_str(auth_context.get("senha")))

        if not ok_usuario or not ok_senha:
            resultado["login_error"] = "falha_preenchimento_login"
            return resultado

        if not _clicar_submit(page, submit_selector):
            resultado["login_error"] = "falha_submit_login"
            return resultado

        _esperar_estabilidade_basica(page)

        wait_selector_pos_login = _safe_str(auth_context.get("wait_selector_pos_login"))
        if wait_selector_pos_login:
            try:
                page.wait_for_selector(wait_selector_pos_login, timeout=12000, state="visible")
            except Exception:
                pass

        html_pos_login = _detectar_html_login(page)
        url_pos_login = _safe_str(page.url)

        resultado["login_url_final"] = url_pos_login

        if _parece_pagina_login(html_pos_login):
            resultado["login_error"] = "login_parece_nao_concluido"
            return resultado

        if _parece_bloqueio(html_pos_login):
            resultado["login_error"] = "bloqueio_apos_login"
            return resultado

        # se login foi numa página diferente da URL de destino, volta para o alvo
        if _normalizar_url(url_pos_login) != _normalizar_url(url_destino):
            try:
                page.goto(url_destino, wait_until="domcontentloaded", timeout=PLAYWRIGHT_NAV_TIMEOUT_MS)
                _esperar_estabilidade_basica(page)
            except Exception as exc:
                resultado["login_error"] = f"falha_ir_para_url_destino_apos_login: {exc}"
                return resultado

        resultado["ok"] = True
        resultado["login_success"] = True
        log_debug("[PLAYWRIGHT] LOGIN OK", "INFO")
        return resultado

    except Exception as exc:
        resultado["login_error"] = f"{type(exc).__name__}: {exc}"
        log_debug(f"[PLAYWRIGHT] LOGIN ERROR | {resultado['login_error']}", "ERROR")
        return resultado


# ==========================================================
# FETCH PRINCIPAL
# ==========================================================
def fetch_url_playwright(
    url: str,
    wait_selector: str | None = None,
    storage_state_path: str | None = None,
    screenshot_on_error: bool = True,
    headless: bool = True,
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> str | None:
    resultado = fetch_playwright_payload(
        url=url,
        wait_selector=wait_selector,
        storage_state_path=storage_state_path,
        screenshot_on_error=screenshot_on_error,
        headless=headless,
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
    )
    html = resultado.get("html")
    return html if isinstance(html, str) and html.strip() else None


def fetch_playwright_payload(
    url: str,
    wait_selector: str | None = None,
    storage_state_path: str | None = None,
    screenshot_on_error: bool = True,
    headless: bool = True,
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = _normalizar_url(url)
    auth_context = _resolver_auth_context(
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
    )

    payload: dict[str, Any] = {
        "ok": False,
        "url": url,
        "final_url": url,
        "html": None,
        "title": "",
        "status_hint": None,
        "blocked_hint": False,
        "network_records": [],
        "screenshot_path": None,
        "storage_state_path": storage_state_path,
        "error": "",
        "engine": "playwright",
        "auth_used": bool(auth_context.get("auth_used")),
        "auth_mode": _safe_str(auth_context.get("auth_mode")) or "none",
        "login_required": bool(auth_context.get("precisa_login")),
        "login_configured": bool(auth_context.get("login_configured")),
        "login_attempted": False,
        "login_success": False,
        "login_error": "",
        "login_url_final": "",
        "router_ready": True,
    }

    if not url:
        payload["error"] = "URL vazia."
        log_debug("[PLAYWRIGHT] URL vazia recebida.", "ERROR")
        return payload

    if not sync_playwright:
        payload["error"] = "Playwright não instalado"
        log_debug("[PLAYWRIGHT] Biblioteca Playwright indisponível.", "ERROR")
        return payload

    browser = None
    context = None
    page = None

    try:
        log_debug(
            (
                f"[PLAYWRIGHT] Iniciando | url={url} | "
                f"precisa_login={payload['login_required']} | "
                f"login_configured={payload['login_configured']}"
            ),
            "INFO",
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = browser.new_context(**_contexto_opcoes(storage_state_path))
            context.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT_MS)
            context.set_default_navigation_timeout(PLAYWRIGHT_NAV_TIMEOUT_MS)

            page = context.new_page()

            try:
                page.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdri
