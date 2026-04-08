from __future__ import annotations

import random
import time
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================================
# CONFIG
# ==========================================================
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 20
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

RETRIES = 4
BACKOFF_BASE = 0.8

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
]

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==========================================================
# LOG
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
# HELPERS
# ==========================================================
def _safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _get_headers(extra_headers: dict[str, Any] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    if isinstance(extra_headers, dict):
        for chave, valor in extra_headers.items():
            chave = _safe_str(chave)
            valor = _safe_str(valor)
            if chave and valor:
                headers[chave] = valor

    return headers


def _criar_session() -> requests.Session:
    session = requests.Session()

    retry_strategy = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["HEAD", "GET", "OPTIONS"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def _parece_html_valido(html: str) -> bool:
    html = _safe_str(html)
    if not html:
        return False

    if len(html) < 80:
        return False

    h = html.lower()

    sinais_html = [
        "<html",
        "<body",
        "<head",
        "<title",
        "<main",
        "<div",
        "<section",
        "<script",
    ]

    return any(sinal in h for sinal in sinais_html)


def _montar_payload(
    *,
    ok: bool,
    url: str,
    final_url: str = "",
    status_code: int | None = None,
    html: str = "",
    error: str = "",
    headers: dict[str, Any] | None = None,
    elapsed_ms: int | None = None,
    verify_ssl: bool = True,
    tentativa: int | None = None,
) -> dict[str, Any]:
    return {
        "ok": bool(ok),
        "engine": "requests",
        "url": _normalizar_url(url),
        "final_url": _normalizar_url(final_url or url),
        "status_code": status_code if isinstance(status_code, int) else None,
        "html": html if isinstance(html, str) else "",
        "error": _safe_str(error),
        "headers": headers if isinstance(headers, dict) else {},
        "elapsed_ms": elapsed_ms if isinstance(elapsed_ms, int) else None,
        "verify_ssl": bool(verify_ssl),
        "tentativa": tentativa if isinstance(tentativa, int) else None,
    }


def _delay_tentativa(tentativa: int) -> None:
    try:
        espera = BACKOFF_BASE * tentativa + random.uniform(0.2, 0.8)
        time.sleep(max(0.0, espera))
    except Exception:
        return None


def _resposta_para_payload(
    *,
    url: str,
    response: requests.Response,
    tentativa: int,
    verify_ssl: bool,
) -> dict[str, Any]:
    try:
        html = response.text if isinstance(response.text, str) else ""
    except Exception:
        html = ""

    try:
        headers = dict(response.headers or {})
    except Exception:
        headers = {}

    try:
        elapsed_ms = int((response.elapsed.total_seconds() or 0) * 1000)
    except Exception:
        elapsed_ms = None

    html_ok = _parece_html_valido(html)
    status_ok = response.status_code == 200

    erro = ""
    if not status_ok:
        erro = f"status_{response.status_code}"
    elif not html_ok:
        erro = "html_invalido"

    return _montar_payload(
        ok=status_ok and html_ok,
        url=url,
        final_url=_safe_str(getattr(response, "url", "") or url),
        status_code=response.status_code,
        html=html,
        error=erro,
        headers=headers,
        elapsed_ms=elapsed_ms,
        verify_ssl=verify_ssl,
        tentativa=tentativa,
    )


def _executar_request(
    session: requests.Session,
    *,
    url: str,
    headers: dict[str, str],
    verify_ssl: bool,
    tentativa: int,
) -> dict[str, Any]:
    inicio = time.perf_counter()

    response = session.get(
        url,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        verify=verify_ssl,
        allow_redirects=True,
    )

    payload = _resposta_para_payload(
        url=url,
        response=response,
        tentativa=tentativa,
        verify_ssl=verify_ssl,
    )

    if payload["ok"]:
        log_debug(
            (
                f"[FETCHER] OK | status={payload.get('status_code')} | "
                f"ssl={verify_ssl} | tentativa={tentativa} | "
                f"html_len={len(payload.get('html') or '')} | "
                f"final_url={payload.get('final_url')}"
            ),
            "INFO",
        )
    else:
        decorrido_ms = int((time.perf_counter() - inicio) * 1000)
        payload["elapsed_ms"] = payload.get("elapsed_ms") or decorrido_ms

        log_debug(
            (
                f"[FETCHER] RESPOSTA FRACA | status={payload.get('status_code')} | "
                f"ssl={verify_ssl} | tentativa={tentativa} | "
                f"erro={payload.get('error')} | "
                f"html_len={len(payload.get('html') or '')}"
            ),
            "WARNING",
        )

    return payload


# ==========================================================
# FETCH TÉCNICO
# ==========================================================
def fetch_url_response(
    url: str,
    *,
    extra_headers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = _normalizar_url(url)

    if not url:
        return _montar_payload(
            ok=False,
            url="",
            error="url_invalida",
        )

    session = _criar_session()
    ultimo_payload: dict[str, Any] | None = None

    try:
        for tentativa in range(1, RETRIES + 1):
            headers = _get_headers(extra_headers)

            # --------------------------------------------------
            # 1) tentativa normal com SSL
            # --------------------------------------------------
            try:
                payload = _executar_request(
                    session,
                    url=url,
                    headers=headers,
                    verify_ssl=True,
                    tentativa=tentativa,
                )

                if payload["ok"]:
                    return payload

                ultimo_payload = payload

                status_code = payload.get("status_code")
                if isinstance(status_code, int) and status_code in {403, 404, 410}:
                    return payload

            except requests.exceptions.SSLError as e:
                log_debug(
                    f"[FETCHER] SSL ERROR | tentativa={tentativa} | url={url} | {e}",
                    "WARNING",
                )

                # ----------------------------------------------
                # 2) fallback SSL desligado
                # ----------------------------------------------
                try:
                    payload_ssl_off = _executar_request(
                        session,
                        url=url,
                        headers=headers,
                        verify_ssl=False,
                        tentativa=tentativa,
                    )

                    if payload_ssl_off["ok"]:
                        return payload_ssl_off

                    ultimo_payload = payload_ssl_off

                    status_code = payload_ssl_off.get("status_code")
                    if isinstance(status_code, int) and status_code in {403, 404, 410}:
                        return payload_ssl_off

                except Exception as e_ssl_off:
                    ultimo_payload = _montar_payload(
                        ok=False,
                        url=url,
                        error=f"ssl_fallback_error: {e_ssl_off}",
                        verify_ssl=False,
                        tentativa=tentativa,
                    )
                    log_debug(
                        (
                            f"[FETCHER] SSL FALLBACK ERROR | tentativa={tentativa} | "
                            f"url={url} | {e_ssl_off}"
                        ),
                        "WARNING",
                    )

            except requests.exceptions.Timeout as e:
                ultimo_payload = _montar_payload(
                    ok=False,
                    url=url,
                    error=f"timeout: {e}",
                    tentativa=tentativa,
                )
                log_debug(
                    f"[FETCHER] TIMEOUT | tentativa={tentativa} | url={url} | {e}",
                    "WARNING",
                )

            except requests.exceptions.RequestException as e:
                ultimo_payload = _montar_payload(
                    ok=False,
                    url=url,
                    error=f"request_error: {e}",
                    tentativa=tentativa,
                )
                log_debug(
                    f"[FETCHER] REQUEST ERROR | tentativa={tentativa} | url={url} | {e}",
                    "WARNING",
                )

            except Exception as e:
                ultimo_payload = _montar_payload(
                    ok=False,
                    url=url,
                    error=f"erro_inesperado: {e}",
                    tentativa=tentativa,
                )
                log_debug(
                    f"[FETCHER] ERRO INESPERADO | tentativa={tentativa} | url={url} | {e}",
                    "ERROR",
                )

            if tentativa < RETRIES:
                _delay_tentativa(tentativa)

    finally:
        try:
            session.close()
        except Exception:
            pass

    return ultimo_payload or _montar_payload(
        ok=False,
        url=url,
        error="falha_total_requests",
    )


# ==========================================================
# COMPATIBILIDADE
# ==========================================================
def fetch_url(
    url: str,
    *,
    extra_headers: dict[str, Any] | None = None,
) -> str | None:
    payload = fetch_url_response(url, extra_headers=extra_headers)
    html = _safe_str(payload.get("html"))

    if payload.get("ok") and html:
        return html

    return None
