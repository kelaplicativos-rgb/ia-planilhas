from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from bling_app_zero.core.fetcher import fetch_url

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(_msg: str, _nivel: str = "INFO") -> None:
        return None


try:
    from bling_app_zero.core.playwright_fetcher import fetch_playwright_payload
except Exception:
    fetch_playwright_payload = None


try:
    from bling_app_zero.core.fornecedores_adaptativos_storage import (
        carregar_fornecedor,
        extrair_dominio,
    )
except Exception:
    carregar_fornecedor = None

    def extrair_dominio(url: str) -> str:
        try:
            host = urlparse(str(url or "").strip()).netloc.lower()
            return host.replace("www.", "")
        except Exception:
            return ""


ROUTER_VERSION = "V6_PROVIDER_AWARE_THREE_SUPPLIERS"


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


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or 0.0)
    except Exception:
        return default


def _normalizar_url(url: str) -> str:
    url = _safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _dominio(url: str) -> str:
    try:
        dominio = extrair_dominio(url)
        if dominio:
            return dominio
    except Exception:
        pass

    try:
        return urlparse(_normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


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
    if len(h) < 2500 and any(s in h for s in sinais_login):
        return True

    return False


def _merge_dicts(base: dict[str, Any] | None, extra: dict[str, Any] | None) -> dict[str, Any]:
    resultado = dict(base or {})
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(resultado.get(k), dict):
            resultado[k] = _merge_dicts(resultado[k], v)
        else:
            resultado[k] = v
    return resultado


def _preset_obaobamix(dominio: str) -> dict[str, Any]:
    return {
        "dominio": dominio,
        "tipo": "api_datatables_auth",
        "origem": "router_local_preset",
        "confianca": 0.99,
        "links": {
            "painel": ["/admin/products"],
            "api_produtos": ["/admin/products"],
            "api_modo": ["datatables_server_side"],
            "api_paginacao": ["start_length"],
            "api_campo_lista": ["data"],
            "api_campo_total": ["recordsTotal"],
            "api_campo_filtrado": ["recordsFiltered"],
        },
        "seletores": {
            "codigo": ["data[].sku"],
            "nome": ["data[].name"],
            "modelo": ["data[].model"],
            "gtin": ["data[].ean"],
            "preco": ["data[].price", "data[].price_of"],
            "estoque": ["data[].inventory"],
            "imagem": ["data[].photo"],
            "marca": ["data[].brand.name", "data[].brand_name"],
            "cor": ["data[].color.name"],
            "id_externo": ["data[].id"],
        },
    }


def _preset_stoqui(dominio: str) -> dict[str, Any]:
    return {
        "dominio": dominio,
        "tipo": "api_supabase_auth",
        "origem": "router_local_preset",
        "confianca": 0.99,
        "links": {
            "painel": ["/products", "/products/{id}"],
            "api_produtos": [
                "https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/produto"
            ],
            "api_categorias": [
                "https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/categoria"
            ],
            "api_variacoes": [
                "https://bvwsyolgpsbvflhbqily.supabase.co/rest/v1/produto_variacao"
            ],
            "api_modo": ["supabase_postgrest"],
            "api_metodo_dados": ["GET"],
            "api_metodo_contagem": ["HEAD"],
            "api_headers_obrigatorios": [
                "apikey",
                "authorization",
                "accept-profile",
                "x-client-info",
            ],
        },
        "seletores": {
            "codigo": ["codigo", "sku", "referencia"],
            "nome": ["nome", "titulo"],
            "descricao": ["descricao"],
            "preco": ["preco", "preco_venda", "valor"],
            "estoque": ["estoque", "quantidade", "saldo"],
            "imagem": ["imagem_url", "foto_url", "imagem"],
            "categoria": ["categoria_id"],
            "id_externo": ["id"],
        },
    }


def _preset_wbuy(dominio: str) -> dict[str, Any]:
    return {
        "dominio": dominio,
        "tipo": "html_wbuy",
        "origem": "router_local_preset",
        "confianca": 0.96,
        "links": {
            "painel": [],
            "api_produtos": ["global.php"],
            "api_modo": ["html_ajax_wbuy"],
            "ajax_funcoes_hint": [
                "global.php",
                "ajax.php",
                "search.php",
            ],
        },
        "seletores": {
            "cards_produto": [
                ".product",
                ".produto",
                ".item-product",
                ".product-item",
                ".box-produto",
                ".vitrine-produtos li",
                ".products-grid li",
            ],
            "nome": [
                "h2 a",
                "h3 a",
                ".title a",
                ".product-name a",
                ".nome-produto",
            ],
            "preco": [
                ".price",
                ".preco",
                ".product_price",
                ".price-current",
                ".valor",
            ],
            "imagem": [
                "img",
                "img[data-src]",
                "img[data-original]",
            ],
            "link": [
                "a[href]",
            ],
        },
    }


def _preset_por_dominio(dominio: str) -> dict[str, Any]:
    dominio = _safe_str(dominio).lower()
    if not dominio:
        return {}

    if dominio in {"app.obaobamix.com.br", "obaobamix.com.br"}:
        return _preset_obaobamix(dominio)

    if dominio in {"app.stoqui.com.br", "stoqui.com.br"}:
        return _preset_stoqui(dominio)

    if dominio in {
        "www.atacadum.com.br",
        "atacadum.com.br",
        "cdn.sistemawbuy.com.br",
        "sistema.sistemawbuy.com.br",
    }:
        return _preset_wbuy(dominio)

    return {}


def _obter_fornecedor_context(url: str) -> dict[str, Any]:
    dominio = _dominio(url)
    contexto: dict[str, Any] = {
        "dominio": dominio,
        "fornecedor_config": {},
        "fornecedor_tipo": "",
        "fornecedor_origem": "",
        "fornecedor_confianca": 0.0,
        "usa_api_auth": False,
        "preferir_playwright_primeiro": False,
        "api_endpoint_hint": "",
        "api_headers_hint": [],
        "api_metodo_dados_hint": "",
        "api_modo_hint": "",
        "forcar_html_direto": False,
    }

    if not dominio:
        return contexto

    config: dict[str, Any] = {}

    if callable(carregar_fornecedor):
        try:
            carregado = carregar_fornecedor(dominio)
            if isinstance(carregado, dict):
                config = carregado
        except Exception as e:
            log_debug(f"[FETCH_ROUTER] falha ao carregar fornecedor adaptativo: {e}", "WARNING")

    if not config:
        config = _preset_por_dominio(dominio)

    fornecedor_tipo = _safe_str(config.get("tipo"))
    fornecedor_origem = _safe_str(config.get("origem"))
    fornecedor_confianca = _safe_float(config.get("confianca"), 0.0)

    links = config.get("links") or {}
    if not isinstance(links, dict):
        links = {}

    api_produtos = links.get("api_produtos") or []
    if isinstance(api_produtos, str):
        api_produtos = [api_produtos]
    elif not isinstance(api_produtos, list):
        api_produtos = []

    api_headers = links.get("api_headers_obrigatorios") or []
    if isinstance(api_headers, str):
        api_headers = [api_headers]
    elif not isinstance(api_headers, list):
        api_headers = []

    api_metodo_dados = links.get("api_metodo_dados") or []
    if isinstance(api_metodo_dados, str):
        api_metodo_dados = [api_metodo_dados]
    elif not isinstance(api_metodo_dados, list):
        api_metodo_dados = []

    api_modo = links.get("api_modo") or []
    if isinstance(api_modo, str):
        api_modo = [api_modo]
    elif not isinstance(api_modo, list):
        api_modo = []

    usa_api_auth = (
        fornecedor_tipo in {
            "api_datatables_auth",
            "api_auth",
            "api_json_auth",
            "api_supabase_auth",
        }
        or bool(api_produtos and fornecedor_tipo != "html_wbuy")
    )

    forcar_html_direto = fornecedor_tipo in {"html_wbuy"}

    preferir_playwright_primeiro = bool(
        usa_api_auth or fornecedor_tipo in {"api_datatables_auth", "api_supabase_auth"}
    )

    api_endpoint_hint = _safe_str(api_produtos[0]) if api_produtos else ""
    api_metodo_dados_hint = _safe_str(api_metodo_dados[0]) if api_metodo_dados else ""
    api_modo_hint = _safe_str(api_modo[0]) if api_modo else ""

    contexto.update(
        {
            "fornecedor_config": config,
            "fornecedor_tipo": fornecedor_tipo,
            "fornecedor_origem": fornecedor_origem,
            "fornecedor_confianca": fornecedor_confianca,
            "usa_api_auth": usa_api_auth,
            "preferir_playwright_primeiro": preferir_playwright_primeiro,
            "api_endpoint_hint": api_endpoint_hint,
            "api_headers_hint": api_headers,
            "api_metodo_dados_hint": api_metodo_dados_hint,
            "api_modo_hint": api_modo_hint,
            "forcar_html_direto": forcar_html_direto,
        }
    )
    return contexto


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


def _metadata_provider_context(
    provider_context: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider_context = provider_context or {}
    metadata = {
        "provider_domain": _safe_str(provider_context.get("dominio")),
        "provider_type": _safe_str(provider_context.get("fornecedor_tipo")),
        "provider_origin": _safe_str(provider_context.get("fornecedor_origem")),
        "provider_confidence": provider_context.get("fornecedor_confianca"),
        "provider_uses_api_auth": bool(provider_context.get("usa_api_auth")),
        "provider_force_html": bool(provider_context.get("forcar_html_direto")),
        "api_endpoint_hint": _safe_str(provider_context.get("api_endpoint_hint")),
        "api_headers_hint": provider_context.get("api_headers_hint") or [],
        "api_method_data_hint": _safe_str(provider_context.get("api_metodo_dados_hint")),
        "api_mode_hint": _safe_str(provider_context.get("api_modo_hint")),
        "provider_config": provider_context.get("fornecedor_config") or {},
    }
    return _merge_dicts(metadata, extra or {})


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
    payload["metadata"] = _merge_dicts(payload.get("metadata") or {}, metadata or {})
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
        auth_config.get("precisa_login") if "precisa_login" in auth_config else precisa_login
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


def _fetch_requests(
    url: str,
    *,
    extra_headers: dict[str, Any] | None = None,
    auth_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_context = auth_context or {}

    try:
        html = fetch_url(
            url,
            extra_headers=extra_headers,
            usuario=_safe_str(auth_context.get("usuario")),
            senha=_safe_str(auth_context.get("senha")),
            precisa_login=bool(auth_context.get("precisa_login")),
            auth_config=auth_context,
        )
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


def _fetch_playwright(
    url: str,
    *,
    auth_context: dict[str, Any] | None = None,
    provider_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_context = auth_context or {}
    provider_context = provider_context or {}

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
            metadata={
                "provider_domain": _safe_str(provider_context.get("dominio")),
                "provider_type": _safe_str(provider_context.get("fornecedor_tipo")),
                "api_endpoint_hint": _safe_str(provider_context.get("api_endpoint_hint")),
            },
        )

    try:
        try:
            payload = fetch_playwright_payload(
                url,
                usuario=_safe_str(auth_context.get("usuario")),
                senha=_safe_str(auth_context.get("senha")),
                precisa_login=bool(auth_context.get("precisa_login")),
                auth_config=auth_context,
            ) or {}
        except TypeError:
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
            metadata={
                "provider_domain": _safe_str(provider_context.get("dominio")),
                "provider_type": _safe_str(provider_context.get("fornecedor_tipo")),
                "api_endpoint_hint": _safe_str(provider_context.get("api_endpoint_hint")),
            },
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
            metadata={
                "provider_domain": _safe_str(provider_context.get("dominio")),
                "provider_type": _safe_str(provider_context.get("fornecedor_tipo")),
                "api_endpoint_hint": _safe_str(provider_context.get("api_endpoint_hint")),
            },
        )


def _deve_forcar_playwright(
    *,
    preferir_js: bool,
    auth_context: dict[str, Any] | None = None,
    provider_context: dict[str, Any] | None = None,
) -> bool:
    auth_context = auth_context or {}
    provider_context = provider_context or {}

    if provider_context.get("forcar_html_direto"):
        return bool(preferir_js)

    if preferir_js:
        return True

    if bool(auth_context.get("auth_used")):
        return True

    if bool(provider_context.get("preferir_playwright_primeiro")):
        return True

    return False


def _deve_tentar_playwright_apos_requests(
    payload_requests: dict[str, Any] | None,
    *,
    auth_context: dict[str, Any] | None = None,
    provider_context: dict[str, Any] | None = None,
) -> bool:
    auth_context = auth_context or {}
    provider_context = provider_context or {}
    payload_requests = payload_requests or {}

    if provider_context.get("forcar_html_direto"):
        html = _safe_str(payload_requests.get("html"))
        return _html_ruim(html)

    if bool(auth_context.get("auth_used")):
        return True

    if bool(provider_context.get("preferir_playwright_primeiro")):
        return True

    html = _safe_str(payload_requests.get("html"))
    if _html_ruim(html):
        return True

    if not payload_requests.get("ok"):
        return True

    return False


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
    provider_context = _obter_fornecedor_context(url)

    if provider_context.get("usa_api_auth") and not auth_context.get("precisa_login"):
        auth_context["precisa_login"] = True
        auth_context["auth_mode"] = _safe_str(auth_context.get("auth_mode")) or "none"

    log_debug(
        (
            f"[FETCH_ROUTER] START | url={url} | preferir_js={preferir_js} | "
            f"dominio={provider_context.get('dominio')} | "
            f"fornecedor_tipo={provider_context.get('fornecedor_tipo')} | "
            f"usa_api_auth={provider_context.get('usa_api_auth')} | "
            f"forcar_html_direto={provider_context.get('forcar_html_direto')} | "
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

    if _deve_forcar_playwright(
        preferir_js=preferir_js,
        auth_context=auth_context,
        provider_context=provider_context,
    ):
        log_debug("[FETCH_ROUTER] FORCANDO PLAYWRIGHT", "INFO")

        payload_pw = _fetch_playwright(
            url,
            auth_context=auth_context,
            provider_context=provider_context,
        )
        if payload_pw.get("ok") and not _html_ruim(payload_pw.get("html")):
            log_debug("[FETCH_ROUTER] PLAYWRIGHT OK", "INFO")
            return _merge_payload_context(
                payload_pw,
                auth_used=bool(auth_context.get("auth_used")),
                auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
                login_required=bool(auth_context.get("precisa_login")),
                login_configured=bool(auth_context.get("login_configured")),
                metadata=_metadata_provider_context(
                    provider_context,
                    {
                        "path": "playwright_primeiro",
                        "strategy": "provider_aware",
                    },
                ),
            )

        log_debug("[FETCH_ROUTER] PLAYWRIGHT FALHOU, tentando requests", "WARNING")

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
            metadata=_metadata_provider_context(
                provider_context,
                {
                    "path": "requests_ok",
                    "strategy": "provider_aware",
                },
            ),
        )

    if _deve_tentar_playwright_apos_requests(
        payload_requests,
        auth_context=auth_context,
        provider_context=provider_context,
    ):
        log_debug("[FETCH_ROUTER] REQUESTS FRACO → PLAYWRIGHT", "WARNING")

        payload_pw = _fetch_playwright(
            url,
            auth_context=auth_context,
            provider_context=provider_context,
        )
        if payload_pw.get("ok") and not _html_ruim(payload_pw.get("html")):
            log_debug("[FETCH_ROUTER] PLAYWRIGHT OK NO FALLBACK", "INFO")
            return _merge_payload_context(
                payload_pw,
                auth_used=bool(auth_context.get("auth_used")),
                auth_mode=_safe_str(auth_context.get("auth_mode")) or "none",
                login_required=bool(auth_context.get("precisa_login")),
                login_configured=bool(auth_context.get("login_configured")),
                metadata=_metadata_provider_context(
                    provider_context,
                    {
                        "path": "requests_fallback_playwright",
                        "strategy": "provider_aware",
                    },
                ),
            )

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
        metadata=_metadata_provider_context(
            provider_context,
            {
                "path": "falha_total",
                "strategy": "provider_aware",
            },
        ),
    )
