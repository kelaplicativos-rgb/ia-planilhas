from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        return None


SITE_CRAWLER_VERSION = "V4_MODULAR"


def safe_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def safe_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def safe_int(valor: Any, padrao: int) -> int:
    try:
        n = int(valor)
        return n if n >= 0 else padrao
    except Exception:
        return padrao


def safe_bool(valor: Any) -> bool:
    if isinstance(valor, bool):
        return valor
    try:
        texto = str(valor or "").strip().lower()
    except Exception:
        return False
    return texto in {"1", "true", "sim", "yes", "y", "on"}


def safe_str(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def normalizar_url(url: str) -> str:
    url = safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def dominio(url: str) -> str:
    try:
        return urlparse(normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def mesmo_dominio(url_a: str, url_b: str) -> bool:
    return bool(dominio(url_a)) and dominio(url_a) == dominio(url_b)


def normalizar_estoque_df(valor: Any) -> int:
    try:
        if valor is None or isinstance(valor, bool):
            return 0

        texto = safe_str(valor)
        if not texto:
            return 0

        texto_lower = texto.lower()
        if any(
            token in texto_lower
            for token in [
                "sem estoque",
                "esgotado",
                "indisponível",
                "indisponivel",
                "zerado",
                "sold out",
                "out of stock",
            ]
        ):
            return 0

        numero = int(float(texto.replace(".", "").replace(",", ".")))
        return max(numero, 0)
    except Exception:
        return 0


def eh_url_imagem_invalida(url: str) -> bool:
    try:
        u = safe_str(url).lower()
        if not u:
            return True

        tokens_ruins = [
            "facebook.com/tr",
            "facebook.net",
            "doubleclick.net",
            "google-analytics.com",
            "googletagmanager.com",
            "/pixel",
            "/track",
            "/tracking",
            "/collect",
            "fbclid=",
            "gclid=",
            "utm_",
            "sprite",
            "icon",
            "logo",
            "banner",
            "avatar",
            "placeholder",
            "spacer",
            "blank.",
            "loader",
            "loading",
            "favicon",
            "lazyload",
            "thumb",
            "thumbnail",
            "mini",
            "small",
        ]

        if any(token in u for token in tokens_ruins):
            return True

        if not u.startswith(("http://", "https://")):
            return True

        return False
    except Exception:
        return True


def normalizar_url_imagem(url: str, base_url: str = "") -> str:
    try:
        txt = safe_str(url)
        if not txt or txt.startswith("data:image"):
            return ""

        if "," in txt:
            partes = [p.strip() for p in txt.split(",") if p.strip()]
            for parte in partes:
                primeira = parte.split(" ")[0].strip()
                if primeira:
                    txt = primeira
                    break

        absoluto = urljoin(base_url, txt).strip() if base_url else txt.strip()
        if not absoluto.startswith(("http://", "https://")):
            return ""

        if eh_url_imagem_invalida(absoluto):
            return ""

        return absoluto
    except Exception:
        return ""


def lista_imagens_para_pipe(valor: Any, base_url: str = "") -> str:
    itens: list[str] = []

    if isinstance(valor, list):
        origem = valor
    else:
        texto = safe_str(valor)
        origem = [p.strip() for p in texto.replace(";", ",").split(",") if p.strip()] if texto else []

    vistos: set[str] = set()

    for item in origem:
        img = normalizar_url_imagem(item, base_url=base_url)
        if not img or img in vistos:
            continue
        vistos.add(img)
        itens.append(img)

    return "|".join(itens)


def resolver_auth_config(
    *,
    usuario: str = "",
    senha: str = "",
    precisa_login: bool = False,
    auth_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    auth_config = safe_dict(auth_config)

    usuario_final = safe_str(
        auth_config.get("usuario")
        or auth_config.get("username")
        or auth_config.get("email")
        or usuario
    )
    senha_final = safe_str(
        auth_config.get("senha")
        or auth_config.get("password")
        or senha
    )
    precisa_login_final = safe_bool(
        auth_config["precisa_login"] if "precisa_login" in auth_config else precisa_login
    )

    saida = dict(auth_config)
    saida["usuario"] = usuario_final
    saida["senha"] = senha_final
    saida["precisa_login"] = precisa_login_final
    return saida
