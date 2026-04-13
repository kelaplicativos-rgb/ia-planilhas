from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

from bling_app_zero.core.fetch_router import fetch_payload_router
from bling_app_zero.core.site_crawler_helpers import link_parece_produto_crawler

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        pass


def safe_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def safe_int(valor: Any, padrao: int) -> int:
    try:
        n = int(valor)
        return n if n > 0 else padrao
    except Exception:
        return padrao


def mesmo_dominio(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(str(url_base or "")).netloc.replace("www.", "").lower()
        d2 = urlparse(str(url or "")).netloc.replace("www.", "").lower()
        if not d1 or not d2:
            return False
        return d1 == d2 or d2.endswith("." + d1) or d1.endswith("." + d2)
    except Exception:
        return False


def normalizar_link(base_url: str, href: Any) -> str:
    try:
        href = str(href or "").strip()
        if not href:
            return ""

        href_low = href.lower()
        if href_low.startswith(("javascript:", "mailto:", "tel:", "data:")):
            return ""

        url = urljoin(base_url, href).strip()
        if not url.startswith(("http://", "https://")):
            return ""

        return url
    except Exception:
        return ""


def eh_link_ruim(url: str) -> bool:
    try:
        u = str(url or "").strip().lower()
        if not u:
            return True

        bloqueados = [
            "#",
            "/cart",
            "/carrinho",
            "/checkout",
            "/login",
            "/entrar",
            "/conta",
            "/account",
            "/register",
            "/cadastro",
            "/favoritos",
            "/wishlist",
            "/politica",
            "/privacy",
            "/termos",
            "/terms",
            "/atendimento",
            "/contato",
            "/contact",
            "/blog",
            "/noticia",
            "/news",
            "/pagina/",
            "?page=",
            "&page=",
            "?pagina=",
            "&pagina=",
            "/categoria/",
            "/category/",
            "/collections/",
            "/search",
            "/busca",
            "whatsapp",
            "instagram",
            "facebook",
            "youtube",
        ]
        return any(item in u for item in bloqueados)
    except Exception:
        return True


def parece_link_produto_flexivel(url: str) -> bool:
    try:
        if not url or eh_link_ruim(url):
            return False

        low = url.lower()

        try:
            if link_parece_produto_crawler(url):
                return True
        except Exception:
            pass

        sinais_fortes = [
            "/produto",
            "/product",
            "/prod/",
            "/item/",
            "/p/",
            "/sku/",
            "-p",
            "produto-",
            "product-",
            "/loja/",
        ]
        if any(s in low for s in sinais_fortes):
            return True

        path = urlparse(low).path or ""
        partes = [p for p in path.split("/") if p.strip()]
        if len(partes) >= 2 and len(path) >= 12:
            return True

        return False
    except Exception:
        return False


def fetch_inteligente(url: str) -> dict[str, Any]:
    try:
        payload = fetch_payload_router(url=url, preferir_js=True) or {}
        html = str(payload.get("html") or "").strip()

        if not html:
            log_debug(f"[CRAWLER] HTML vazio: {url}", "WARNING")
            return payload

        if len(html) < 2000:
            log_debug(
                f"[CRAWLER] HTML suspeito (pequeno={len(html)}): {url}",
                "WARNING",
            )

        engine = str(payload.get("engine") or "")
        log_debug(
            f"[CRAWLER] FETCH OK | engine={engine or 'desconhecido'} | url={url}",
            "INFO",
        )
        return payload
    except Exception as e:
        log_debug(f"[CRAWLER] Erro fetch: {url} | {e}", "ERROR")
        return {}
