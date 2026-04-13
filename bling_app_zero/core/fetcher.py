from __future__ import annotations

import random
import time
from typing import Any
from urllib.parse import urlparse

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================================
# LOG OPCIONAL / BLINDAGEM
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug  # type: ignore
except Exception:
    try:
        from bling_app_zero.utils.excel import log_debug  # type: ignore
    except Exception:
        def log_debug(_msg: str, _nivel: str = "INFO") -> None:
            return None

# desativa warning de SSL inseguro quando houver fallback verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================================
# CONFIG
# ==========================================================
TIMEOUT = 20
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 20
RETRIES = 4
BACKOFF_BASE = 0.8
MAX_CONTENT_CHARS = 5_000_000

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; SM-S911B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
]

# Alguns padrões comuns de bloqueio/challenge
BLOCK_HINTS = [
    "access denied",
    "forbidden",
    "temporarily unavailable",
    "captcha",
    "cf-browser-verification",
    "cloudflare",
    "attention required",
    "bot verification",
    "security check",
    "request unsuccessful",
    "please enable cookies",
    "verify you are human",
]

LOGIN_HINTS = [
    'type="password"',
    'name="password"',
    'name="senha"',
    'autocomplete="current-password"',
    "fazer login",
    "entrar",
    "sign in",
    "login",
]

FETCHER_VERSION = "V3_AUTH_READY_COMPAT"

# ==========================================================
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
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
        return "https://" + url
    return url


def _dominio(url: str) -> str:
    try:
        return urlparse(_normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


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

    login_configured = bool(usuario_final and senha_final)
    auth_used = bool(precisa_login_final and login_configured)

    return {
        "usuario": usuario_final,
        "senha": senha_final,
        "precisa_login": precisa_login_final,
        "login_configured": login_configured,
        "auth_used": auth_used,
        "auth_mode": "login_password" if auth_used else "none",
    }


def _get_headers(
    url: str,
    referer: str | None = None,
    extra_headers: dict[str, Any] | None = None,
) -> dict[str, str]:
    host = _dominio(url)
    origem = f"https://{host}" if host else url

    headers: dict[str, str] = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
        "Referer": referer or origem,
        "Origin": origem,
    }

    if isinstance(extra_headers, dict):
        for chave, valor in extra_headers.items():
            chave_s = _safe_str(chave)
            if not chave_s:
                continue
            headers[chave_s] = _safe_str(valor)

    return headers


def _criar_session(
    *,
    extra_headers: dict[str, Any] | None = None,
) -> requests.Session:
    session = requests.Session()

    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.6,
        status_forcelist=[403, 408, 409, 425, 429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=20,
        pool_maxsize=20,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"})

    if isinstance(extra_headers, dict):
        limpos = {str(k): _safe_str(v) for k, v in extra_headers.items() if _safe_str(k)}
        if limpos:
            session.headers.update(limpos)

    return session


def _response_text(response: requests.Response) -> str:
    try:
        if not response.encoding:
            response.encoding = response.apparent_encoding or "utf-8"
    except Exception:
        try:
            response.encoding = "utf-8"
        except Exception:
            pass

    try:
        texto = response.text or ""
    except Exception:
        try:
            texto = response.content.decode("utf-8", errors="ignore")
        except Exception:
            texto = ""

    if len(texto) > MAX_CONTENT_CHARS:
        return texto[:MAX_CONTENT_CHARS]

    return texto


def _parece_html_valido(texto: str) -> bool:
    t = (texto or "").strip().lower()
    if not t:
        return False

    if "<html" in t or "<body" in t or "<head" in t:
        return True

    if len(t) >= 120:
        return True

    return False


def _detectar_bloqueio(texto: str, status_code: int) -> bool:
    t = (texto or "").lower()

    if status_code in {401, 403, 429, 503}:
        return True

    return any(chave in t for chave in BLOCK_HINTS)


def _detectar_login(texto: str) -> bool:
    t = (texto or "").lower()
    if len(t) > 15000:
        return False
    return any(chave in t for chave in LOGIN_HINTS)


def _delay_tentativa(tentativa: int) -> None:
    base = BACKOFF_BASE * (tentativa + 1)
    jitter = random.uniform(0.4, 1.2)
    time.sleep(base + jitter)


def _resumo_exc(exc: Exception) -> str:
    try:
        return f"{type(exc).__name__}: {exc}"
    except Exception:
        return "erro desconhecido"


def _montar_payload(
    *,
    ok: bool,
    url: str,
    html: str | None = None,
    final_url: str | None = None,
    status_code: int | None = None,
    error: str = "",
    blocked_hint: bool = False,
    login_page_hint: bool = False,
    auth_context: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_context = auth_context or {}
    html = html if isinstance(html, str) else None

    return {
        "ok": bool(ok),
        "url": _normalizar_url(url),
        "final_url": _safe_str(final_url) or _normalizar_url(url),
        "html": html,
        "html_len": len(html) if isinstance(html, str) else 0,
        "status_code": status_code,
        "error": _safe_str(error),
        "blocked_hint": bool(blocked_hint),
        "login_page_hint": bool(login_page_hint),
        "auth_used": bool(auth_context.get("auth_used")),
        "auth_mode": _safe_str(auth_context.get("auth_mode")) or "none",
        "login_required": bool(auth_context.get("precisa_login")),
        "login_configured": bool(auth_context.get("login_configured")),
        "metadata": metadata or {},
        "fetcher_version": FETCHER_VERSION,
    }


# ==========================================================
# FETCH PRINCIPAL
# ==========================================================
def fetch_url(
    url: str,
    extra_headers: dict[str, Any] | None = None,
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> str | None:
    """
    Faz download do HTML de uma URL com mais robustez e logs úteis.

    Compatível com a assinatura antiga:
        fetch_url(url)

    Compatível com a nova cadeia:
        fetch_url(
            url,
            extra_headers={"Referer": "..."},
            usuario="...",
            senha="...",
            precisa_login=True,
        )

    Observação:
    - requests puro não executa login interativo em formulário JS.
    - quando `precisa_login=True`, este fetcher só sinaliza o contexto;
      o login real deve ser feito no Playwright.
    """
    payload = fetch_url_response(
        url=url,
        extra_headers=extra_headers,
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
    )

    html = payload.get("html")
    return html if isinstance(html, str) and html.strip() else None


# ==========================================================
# FETCH AVANÇADO / DEBUG
# ==========================================================
def fetch_url_response(
    url: str,
    extra_headers: dict[str, Any] | None = None,
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Retorno estruturado para debug e roteamento.

    Útil para:
    - detectar bloqueio;
    - detectar tela de login;
    - devolver status/final_url;
    - carregar contexto de autenticação sem quebrar a base atual.
    """
    url = _normalizar_url(url)

    auth_context = _resolver_auth_context(
        usuario=usuario,
        senha=senha,
        precisa_login=precisa_login,
        auth_config=auth_config,
    )

    if not url:
        log_debug("fetch_url_response recebeu URL vazia.", "WARNING")
        return _montar_payload(
            ok=False,
            url="",
            html=None,
            error="url_vazia",
            auth_context=auth_context,
        )

    if auth_context.get("precisa_login"):
        log_debug(
            (
                f"[FETCHER] contexto com login detectado | "
                f"login_configured={auth_context['login_configured']} | "
                f"auth_used={auth_context['auth_used']}"
            ),
            "INFO",
        )

    session = _criar_session(extra_headers=extra_headers)

    ultimo_erro = ""
    ultimo_status: int | None = None
    ultima_final_url = url
    ultimo_html: str | None = None
    ultimo_blocked = False
    ultimo_login_hint = False

    for tentativa in range(RETRIES):
        headers = _get_headers(url, extra_headers=extra_headers)

        for verify_ssl in (True, False):
            try:
                log_debug(
                    (
                        f"[FETCHER] tentativa {tentativa + 1}/{RETRIES} | "
                        f"verify_ssl={verify_ssl} | url={url}"
                    ),
                    "INFO",
                )

                response = session.get(
                    url,
                    headers=headers,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    allow_redirects=True,
                    verify=verify_ssl,
                )

                ultimo_status = int(response.status_code)
                ultima_final_url = _safe_str(response.url) or url
                texto = _response_text(response)
                ultimo_html = texto
                ultimo_blocked = _detectar_bloqueio(texto, response.status_code)
                ultimo_login_hint = _detectar_login(texto)

                log_debug(
                    (
                        f"[FETCHER] resposta | status={response.status_code} | "
                        f"bytes={len(response.content) if response.content else 0} | "
                        f"chars={len(texto)} | final_url={response.url} | "
                        f"blocked={ultimo_blocked} | login_hint={ultimo_login_hint}"
                    ),
                    "INFO",
                )

                if response.status_code == 200:
                    if not texto.strip():
                        ultimo_erro = "Resposta 200 vazia."
                        log_debug(
                            f"[FETCHER] 200 porém conteúdo vazio | url={url}",
                            "WARNING",
                        )

                    elif ultimo_blocked:
                        ultimo_erro = "Conteúdo indica bloqueio/challenge."
                        log_debug(
                            f"[FETCHER] bloqueado por challenge/captcha | url={url}",
                            "WARNING",
                        )

                    elif auth_context.get("precisa_login") and ultimo_login_hint:
                        ultimo_erro = "Página de login detectada em fetch requests."
                        log_debug(
                            f"[FETCHER] página de login detectada | url={url}",
                            "WARNING",
                        )

                    elif not _parece_html_valido(texto):
                        if len(texto.strip()) >= 120:
                            log_debug(
                                f"[FETCHER] conteúdo não padrão, mas utilizável | url={url}",
                                "INFO",
                            )
                            return _montar_payload(
                                ok=True,
                                url=url,
                                html=texto,
                                final_url=ultima_final_url,
                                status_code=ultimo_status,
                                blocked_hint=ultimo_blocked,
                                login_page_hint=ultimo_login_hint,
                                auth_context=auth_context,
                                metadata={"path": "requests_len_minimo"},
                            )

                        ultimo_erro = "Conteúdo sem estrutura HTML suficiente."
                        log_debug(
                            f"[FETCHER] sem HTML válido | url={url}",
                            "WARNING",
                        )
                    else:
                        return _montar_payload(
                            ok=True,
                            url=url,
                            html=texto,
                            final_url=ultima_final_url,
                            status_code=ultimo_status,
                            blocked_hint=ultimo_blocked,
                            login_page_hint=ultimo_login_hint,
                            auth_context=auth_context,
                            metadata={"path": "requests_ok"},
                        )

                elif response.status_code in (301, 302, 303, 307, 308):
                    ultimo_erro = f"Redirecionamento não resolvido: {response.status_code}"
                    log_debug(
                        (
                            f"[FETCHER] redirecionamento não resolvido | "
                            f"status={response.status_code} | url={url}"
                        ),
                        "WARNING",
                    )

                elif response.status_code in (401, 403, 429, 503):
                    ultimo_erro = f"Bloqueio do servidor: HTTP {response.status_code}"
                    log_debug(
                        f"[FETCHER] bloqueado | status={response.status_code} | url={url}",
                        "WARNING",
                    )

                else:
                    ultimo_erro = f"HTTP {response.status_code}"
                    log_debug(
                        f"[FETCHER] falhou | status={response.status_code} | url={url}",
                        "WARNING",
                    )

            except requests.exceptions.SSLError as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"[FETCHER] erro SSL | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )
                if verify_ssl:
                    continue

            except requests.exceptions.Timeout as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"[FETCHER] timeout | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except requests.exceptions.TooManyRedirects as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"[FETCHER] redirecionamentos excessivos | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except requests.exceptions.ConnectionError as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"[FETCHER] erro de conexão | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except requests.RequestException as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"[FETCHER] erro requests | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except Exception as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"[FETCHER] erro inesperado | url={url} | detalhe={ultimo_erro}",
                    "ERROR",
                )

        if tentativa < RETRIES - 1:
            _delay_tentativa(tentativa)

    log_debug(
        (
            f"[FETCHER] esgotado sem sucesso | url={url} | "
            f"ultimo_status={ultimo_status} | "
            f"ultimo_erro={ultimo_erro or 'desconhecido'} | "
            f"login_hint={ultimo_login_hint} | blocked={ultimo_blocked}"
        ),
        "ERROR",
    )

    return _montar_payload(
        ok=False,
        url=url,
        html=ultimo_html,
        final_url=ultima_final_url,
        status_code=ultimo_status,
        error=ultimo_erro or "falha_total_fetch_requests",
        blocked_hint=ultimo_blocked,
        login_page_hint=ultimo_login_hint,
        auth_context=auth_context,
        metadata={"path": "requests_fail"},
)
