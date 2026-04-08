from __future__ import annotations

from typing import Any

from bling_app_zero.core.fetcher import fetch_url

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
# PLAYWRIGHT
# ==========================================================
try:
    from bling_app_zero.core.playwright_fetcher import fetch_playwright_payload
except Exception:
    fetch_playwright_payload = None


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


def _payload_padrao(
    *,
    ok: bool,
    engine: str,
    url: str,
    final_url: str | None = None,
    html: str | None = None,
    network_records: list[Any] | None = None,
    error: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = _normalizar_url(url)
    final_url = _normalizar_url(final_url or url)

    return {
        "ok": bool(ok),
        "engine": _safe_str(engine),
        "url": url,
        "final_url": final_url,
        "html": html if isinstance(html, str) else "",
        "network_records": network_records if isinstance(network_records, list) else [],
        "error": _safe_str(error),
        "meta": meta if isinstance(meta, dict) else {},
    }


def _payload_requests(
    url: str,
    html: str | None,
    error: str = "",
    motivo: str = "",
) -> dict[str, Any]:
    html = html if isinstance(html, str) else ""
    return _payload_padrao(
        ok=bool(html),
        engine="requests",
        url=url,
        final_url=url,
        html=html,
        network_records=[],
        error=error if error else ("" if html else "Falha no fetch via requests."),
        meta={
            "source": "fetcher",
            "motivo": _safe_str(motivo),
            "html_len": len(html),
        },
    )


def _payload_playwright_invalido(url: str, motivo: str = "") -> dict[str, Any]:
    return _payload_padrao(
        ok=False,
        engine="playwright",
        url=url,
        final_url=url,
        html="",
        network_records=[],
        error="Falha no fetch via Playwright.",
        meta={"motivo": _safe_str(motivo)},
    )


def _padronizar_payload_playwright(url: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _payload_playwright_invalido(url, "payload_invalido")

    html = payload.get("html")
    html = html if isinstance(html, str) else ""

    final_url = payload.get("final_url") or payload.get("url") or url
    network_records = payload.get("network_records")
    error = _safe_str(payload.get("error"))
    ok = bool(payload.get("ok")) or bool(html)

    return _payload_padrao(
        ok=ok,
        engine=_safe_str(payload.get("engine")) or "playwright",
        url=url,
        final_url=final_url,
        html=html,
        network_records=network_records if isinstance(network_records, list) else [],
        error=error,
        meta=payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
    )


def _html_parece_ruim(html: str | None) -> tuple[bool, str]:
    if not html:
        return True, "html_vazio"

    html = str(html).strip()
    if not html:
        return True, "html_vazio"

    html_lower = html.lower()
    html_len = len(html)

    if html_len < 500:
        return True, "html_muito_curto"

    sinais_bloqueio = [
        "access denied",
        "forbidden",
        "captcha",
        "cloudflare",
        "verify you are human",
        "attention required",
        "blocked",
        "request blocked",
        "bot detection",
        "temporarily unavailable",
    ]
    if any(s in html_lower for s in sinais_bloqueio):
        return True, "bloqueio_detectado"

    sinais_js = [
        "javascript required",
        "enable javascript",
        "please enable javascript",
        "you need to enable javascript",
        "app-root",
        "loading...",
        "carregando",
    ]
    if any(s in html_lower for s in sinais_js):
        return True, "dependencia_js"

    # HTML "grande" mas pobre em conteúdo útil.
    sinais_uteis = [
        "<title",
        "<h1",
        "<main",
        "<article",
        "<section",
        "<body",
        "product",
        "produto",
        "price",
        "preço",
    ]
    achou_sinal_util = any(s in html_lower for s in sinais_uteis)
    if html_len < 2000 and not achou_sinal_util:
        return True, "html_fraco"

    return False, ""


def _deve_fazer_fallback_js(
    html: str | None,
    preferir_js: bool = False,
) -> tuple[bool, str]:
    if preferir_js:
        return True, "preferir_js"

    ruim, motivo = _html_parece_ruim(html)
    if ruim:
        return True, motivo

    return False, ""


def _executar_playwright(url: str, motivo: str = "") -> dict[str, Any]:
    if not fetch_playwright_payload:
        log_debug(
            f"[FETCH_ROUTER] Playwright indisponível | motivo={motivo or 'nao_informado'}",
            "WARNING",
        )
        return _payload_playwright_invalido(url, motivo or "playwright_indisponivel")

    try:
        log_debug(
            f"[FETCH_ROUTER] PLAYWRIGHT START | motivo={motivo or 'nao_informado'} | url={url}",
            "INFO",
        )
        payload_js = fetch_playwright_payload(url)
        payload_padronizado = _padronizar_payload_playwright(url, payload_js)

        html_js = payload_padronizado.get("html") or ""
        ruim, motivo_html = _html_parece_ruim(html_js)

        if html_js and not ruim:
            log_debug(
                f"[FETCH_ROUTER] PLAYWRIGHT OK | motivo={motivo or 'nao_informado'} | html_len={len(html_js)}",
                "INFO",
            )
            return payload_padronizado

        log_debug(
            f"[FETCH_ROUTER] PLAYWRIGHT HTML SUSPEITO | motivo={motivo_html or motivo or 'desconhecido'} | html_len={len(html_js)}",
            "WARNING",
        )

        if not payload_padronizado.get("error"):
            payload_padronizado["error"] = "HTML insuficiente no Playwright."

        meta = payload_padronizado.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}
        meta["motivo"] = motivo_html or motivo or "html_suspeito"
        meta["html_len"] = len(html_js)
        payload_padronizado["meta"] = meta

        return payload_padronizado

    except Exception as e:
        log_debug(f"[FETCH_ROUTER] erro playwright: {e}", "WARNING")
        return _payload_playwright_invalido(url, f"erro_playwright: {e}")


# ==========================================================
# MAIN
# ==========================================================
def fetch_payload_router(
    url: str,
    preferir_js: bool = False,
) -> dict[str, Any]:
    url = _normalizar_url(url)

    if not url:
        return _payload_requests("", None, "URL inválida.", "url_invalida")

    log_debug(f"[FETCH_ROUTER] START | url={url} | preferir_js={preferir_js}", "INFO")

    # ======================================================
    # 1) PRIORIDADE PLAYWRIGHT, SE FORÇADO
    # ======================================================
    if preferir_js:
        payload_js = _executar_playwright(url, "preferir_js")
        html_js = _safe_str(payload_js.get("html"))
        ruim_js, _ = _html_parece_ruim(html_js)

        if html_js and not ruim_js:
            return payload_js

        log_debug(
            "[FETCH_ROUTER] Playwright forçado não retornou HTML confiável; tentando requests.",
            "WARNING",
        )

    # ======================================================
    # 2) REQUESTS
    # ======================================================
    html_requests: str | None = None
    erro_requests = ""

    try:
        html_requests = fetch_url(url)
    except Exception as e:
        erro_requests = f"erro_requests: {e}"
        log_debug(f"[FETCH_ROUTER] erro requests: {e}", "WARNING")

    if html_requests:
        html_requests = str(html_requests).strip()

    if html_requests:
        ruim, motivo = _html_parece_ruim(html_requests)

        if not ruim:
            log_debug(
                f"[FETCH_ROUTER] REQUESTS OK | html_len={len(html_requests)}",
                "INFO",
            )
            return _payload_requests(url, html_requests, "", "requests_ok")

        log_debug(
            f"[FETCH_ROUTER] HTML suspeito via requests | motivo={motivo} | html_len={len(html_requests)}",
            "WARNING",
        )

        payload_js = _executar_playwright(url, motivo)
        html_js = _safe_str(payload_js.get("html"))
        ruim_js, _ = _html_parece_ruim(html_js)

        if html_js and not ruim_js:
            return payload_js

        return _payload_requests(
            url,
            html_requests,
            payload_js.get("error") or "",
            f"requests_html_suspeito:{motivo}",
        )

    log_debug("[FETCH_ROUTER] REQUESTS sem HTML útil", "WARNING")

    # ======================================================
    # 3) FALLBACK TOTAL PLAYWRIGHT
    # ======================================================
    payload_js = _executar_playwright(url, "requests_sem_html")
    html_js = _safe_str(payload_js.get("html"))
    ruim_js, motivo_js = _html_parece_ruim(html_js)

    if html_js and not ruim_js:
        return payload_js

    log_debug("[FETCH_ROUTER] FALHA TOTAL", "ERROR")

    erro_final = payload_js.get("error") or erro_requests or "Falha total no fetch."
    return _payload_requests(url, html_requests, erro_final, motivo_js or "falha_total")
