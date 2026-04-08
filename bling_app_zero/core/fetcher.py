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


# 🔥 desativa warning de SSL inseguro quando houver fallback verify=False
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
]


# ==========================================================
# HELPERS
# ==========================================================
def _normalizar_url(url: str) -> str:
    return str(url or "").strip()


def _dominio(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _get_headers(url: str, referer: str | None = None) -> dict[str, str]:
    host = _dominio(url)
    origem = f"https://{host}" if host else url

    return {
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


def _criar_session() -> requests.Session:
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

    if "<html" in t or "<body" in t:
        return True

    if "<!doctype html" in t:
        return True

    if "<head" in t and "</head>" in t:
        return True

    return False


def _detectar_bloqueio(texto: str, status_code: int) -> bool:
    t = (texto or "").lower()

    if status_code in {401, 403, 429, 503}:
        return True

    return any(chave in t for chave in BLOCK_HINTS)


def _delay_tentativa(tentativa: int) -> None:
    base = BACKOFF_BASE * (tentativa + 1)
    jitter = random.uniform(0.4, 1.2)
    time.sleep(base + jitter)


def _resumo_exc(exc: Exception) -> str:
    try:
        return f"{type(exc).__name__}: {exc}"
    except Exception:
        return "erro desconhecido"


# ==========================================================
# FETCH PRINCIPAL
# ==========================================================
def fetch_url(url: str) -> str | None:
    """
    Faz download do HTML de uma URL com mais robustez e logs úteis.

    Regras:
    - mantém assinatura simples: retorna `str | None`
    - tenta com sessão persistente
    - tenta com SSL normal e fallback verify=False
    - registra status e motivo real da falha
    """
    url = _normalizar_url(url)
    if not url:
        log_debug("fetch_url recebeu URL vazia.", "WARNING")
        return None

    session = _criar_session()
    ultimo_erro = ""
    ultimo_status: int | None = None

    for tentativa in range(RETRIES):
        headers = _get_headers(url)

        for verify_ssl in (True, False):
            try:
                log_debug(
                    (
                        f"Fetch tentativa {tentativa + 1}/{RETRIES} | "
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

                texto = _response_text(response)
                tamanho = len(texto)

                log_debug(
                    (
                        f"Fetch resposta | status={response.status_code} | "
                        f"bytes={len(response.content) if response.content else 0} | "
                        f"chars={tamanho} | final_url={response.url}"
                    ),
                    "INFO",
                )

                if response.status_code == 200:
                    if not texto.strip():
                        ultimo_erro = "Resposta 200 vazia."
                        log_debug(
                            f"Fetch 200 porém conteúdo vazio | url={url}",
                            "WARNING",
                        )
                    elif _detectar_bloqueio(texto, response.status_code):
                        ultimo_erro = "Conteúdo indica bloqueio/challenge."
                        log_debug(
                            f"Fetch bloqueado por challenge/captcha | url={url}",
                            "WARNING",
                        )
                    elif not _parece_html_valido(texto):
                        # alguns sites podem responder texto parcial/minificado;
                        # ainda assim devolvemos se tiver conteúdo suficiente.
                        if len(texto.strip()) >= 120:
                            log_debug(
                                f"Fetch retornou conteúdo não padrão, mas utilizável | url={url}",
                                "INFO",
                            )
                            return texto
                        ultimo_erro = "Conteúdo sem estrutura HTML suficiente."
                        log_debug(
                            f"Fetch sem HTML válido | url={url}",
                            "WARNING",
                        )
                    else:
                        return texto

                elif response.status_code in (301, 302, 303, 307, 308):
                    # normalmente allow_redirects já resolve; deixado aqui por segurança
                    ultimo_erro = f"Redirecionamento não resolvido: {response.status_code}"
                    log_debug(
                        f"Fetch redirecionamento não resolvido | status={response.status_code} | url={url}",
                        "WARNING",
                    )
                elif response.status_code in (403, 429, 503):
                    ultimo_erro = f"Bloqueio do servidor: HTTP {response.status_code}"
                    log_debug(
                        f"Fetch bloqueado | status={response.status_code} | url={url}",
                        "WARNING",
                    )
                else:
                    ultimo_erro = f"HTTP {response.status_code}"
                    log_debug(
                        f"Fetch falhou | status={response.status_code} | url={url}",
                        "WARNING",
                    )

            except requests.exceptions.SSLError as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"Erro SSL no fetch | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )
                # tenta verify=False na mesma rodada
                if verify_ssl:
                    continue

            except requests.exceptions.Timeout as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"Timeout no fetch | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except requests.exceptions.TooManyRedirects as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"Redirecionamentos excessivos | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except requests.exceptions.ConnectionError as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"Erro de conexão no fetch | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except requests.RequestException as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"Erro requests no fetch | url={url} | detalhe={ultimo_erro}",
                    "WARNING",
                )

            except Exception as exc:
                ultimo_erro = _resumo_exc(exc)
                log_debug(
                    f"Erro inesperado no fetch | url={url} | detalhe={ultimo_erro}",
                    "ERROR",
                )

        if tentativa < RETRIES - 1:
            _delay_tentativa(tentativa)

    log_debug(
        (
            f"Fetch esgotado sem sucesso | url={url} | "
            f"ultimo_status={ultimo_status} | ultimo_erro={ultimo_erro or 'desconhecido'}"
        ),
        "ERROR",
    )
    return None


# ==========================================================
# FETCH AVANÇADO OPCIONAL
# ==========================================================
def fetch_url_response(url: str) -> dict[str, Any]:
    """
    Helper opcional para debug futuro sem quebrar o sistema atual.
    """
    html = fetch_url(url)
    return {
        "url": _normalizar_url(url),
        "ok": bool(html),
        "html": html,
        "html_len": len(html) if isinstance(html, str) else 0,
                }
