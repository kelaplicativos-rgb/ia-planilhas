
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass
class SupplierProfile:
    slug: str
    nome: str
    dominio_match: tuple[str, ...]
    login_url: str
    products_url: str
    login_required: bool = False
    supports_requests_login: bool = False
    supports_playwright_login: bool = True
    captcha_expected: bool = False
    username_field_candidates: tuple[str, ...] = ("email", "username", "login")
    password_field_candidates: tuple[str, ...] = ("password", "senha")
    submit_field_candidates: tuple[str, ...] = ("submit", "entrar", "login")
    login_path_hints: tuple[str, ...] = ("/login", "/entrar", "/account/login")
    products_path_hints: tuple[str, ...] = ("/admin/products", "/produtos", "/catalogo", "/catalog")
    requires_assisted_login: bool = False
    public_entry_allowed: bool = True
    notes: str = ""


DEFAULT_PROFILE = SupplierProfile(
    slug="generic_public",
    nome="Fornecedor genérico",
    dominio_match=(),
    login_url="",
    products_url="",
    login_required=False,
    supports_requests_login=False,
    supports_playwright_login=False,
    captcha_expected=False,
    requires_assisted_login=False,
    public_entry_allowed=True,
    notes="Fornecedor público sem necessidade de autenticação.",
)

GENERIC_LOGIN_PROFILE = SupplierProfile(
    slug="generic_login",
    nome="Fornecedor genérico com login",
    dominio_match=(),
    login_url="",
    products_url="",
    login_required=True,
    supports_requests_login=False,
    supports_playwright_login=True,
    captcha_expected=False,
    requires_assisted_login=False,
    public_entry_allowed=False,
    notes="Fornecedor com indício de autenticação, sem regra dedicada por domínio.",
)

GENERIC_CAPTCHA_PROFILE = SupplierProfile(
    slug="generic_captcha",
    nome="Fornecedor genérico com captcha",
    dominio_match=(),
    login_url="",
    products_url="",
    login_required=True,
    supports_requests_login=False,
    supports_playwright_login=True,
    captcha_expected=True,
    requires_assisted_login=True,
    public_entry_allowed=False,
    notes="Fornecedor com indício de captcha. O fluxo recomendado é login assistido com sessão persistente.",
)

OBA_OBA_MIX_PROFILE = SupplierProfile(
    slug="obaobamix",
    nome="Oba Oba Mix",
    dominio_match=("app.obaobamix.com.br", "obaobamix.com.br"),
    login_url="https://app.obaobamix.com.br/login",
    products_url="https://app.obaobamix.com.br/admin/products",
    login_required=True,
    supports_requests_login=False,
    supports_playwright_login=True,
    captcha_expected=True,
    username_field_candidates=("email", "login", "username"),
    password_field_candidates=("password", "senha"),
    submit_field_candidates=("entrar", "login", "submit"),
    login_path_hints=("/login", "/entrar", "/account/login"),
    products_path_hints=("/admin/products", "/products", "/catalogo"),
    requires_assisted_login=True,
    public_entry_allowed=False,
    notes=(
        "Catálogo autenticado. Há indício de captcha na tela de login. "
        "O fluxo recomendado é sessão autenticada com navegador automatizado "
        "e reaproveitamento de estado."
    ),
)

_PROFILES = (
    OBA_OBA_MIX_PROFILE,
)


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize_url(url: str) -> str:
    raw = _safe_str(url)
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw.strip()


def _hostname(url: str) -> str:
    try:
        return (urlparse(_normalize_url(url)).hostname or "").strip().lower()
    except Exception:
        return ""


def _same_or_subdomain(host: str, domain: str) -> bool:
    host = _safe_str(host).lower()
    domain = _safe_str(domain).lower()
    if not host or not domain:
        return False
    return host == domain or host.endswith(f".{domain}")


def _join_base_and_path(url: str, path: str) -> str:
    base = _normalize_url(url)
    path = _safe_str(path)
    if not base:
        return ""
    if not path:
        return base
    parsed = urlparse(base)
    root = f"{parsed.scheme}://{parsed.netloc}"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{root}{path}"


def get_supplier_profile(url: str) -> SupplierProfile:
    host = _hostname(url)
    if not host:
        return DEFAULT_PROFILE

    for profile in _PROFILES:
        if any(_same_or_subdomain(host, dominio) for dominio in profile.dominio_match):
            return profile

    return DEFAULT_PROFILE


def infer_supplier_profile_from_detection(
    *,
    url: str,
    requires_login: bool = False,
    captcha_detected: bool = False,
) -> SupplierProfile:
    profile = get_supplier_profile(url)
    if profile.slug != DEFAULT_PROFILE.slug:
        return profile

    if captcha_detected:
        return build_runtime_profile(
            base_profile=GENERIC_CAPTCHA_PROFILE,
            url=url,
        )

    if requires_login:
        return build_runtime_profile(
            base_profile=GENERIC_LOGIN_PROFILE,
            url=url,
        )

    return build_runtime_profile(
        base_profile=DEFAULT_PROFILE,
        url=url,
    )


def build_runtime_profile(
    *,
    base_profile: SupplierProfile,
    url: str,
    login_url: str = "",
    products_url: str = "",
) -> SupplierProfile:
    resolved_login_url = _safe_str(login_url) or _safe_str(base_profile.login_url)
    resolved_products_url = _safe_str(products_url) or _safe_str(base_profile.products_url)

    if not resolved_login_url and base_profile.login_required and base_profile.login_path_hints:
        resolved_login_url = _join_base_and_path(url, base_profile.login_path_hints[0])

    if not resolved_products_url and base_profile.products_path_hints:
        resolved_products_url = _join_base_and_path(url, base_profile.products_path_hints[0])

    if not resolved_products_url:
        resolved_products_url = _normalize_url(url)

    return SupplierProfile(
        slug=base_profile.slug,
        nome=base_profile.nome,
        dominio_match=base_profile.dominio_match,
        login_url=resolved_login_url,
        products_url=resolved_products_url,
        login_required=base_profile.login_required,
        supports_requests_login=base_profile.supports_requests_login,
        supports_playwright_login=base_profile.supports_playwright_login,
        captcha_expected=base_profile.captcha_expected,
        username_field_candidates=base_profile.username_field_candidates,
        password_field_candidates=base_profile.password_field_candidates,
        submit_field_candidates=base_profile.submit_field_candidates,
        login_path_hints=base_profile.login_path_hints,
        products_path_hints=base_profile.products_path_hints,
        requires_assisted_login=base_profile.requires_assisted_login,
        public_entry_allowed=base_profile.public_entry_allowed,
        notes=base_profile.notes,
    )


def resolve_profile_urls(
    *,
    url: str,
    profile: SupplierProfile,
    login_url: str = "",
    products_url: str = "",
) -> dict[str, str]:
    runtime = build_runtime_profile(
        base_profile=profile,
        url=url,
        login_url=login_url,
        products_url=products_url,
    )

    return {
        "login_url": runtime.login_url,
        "products_url": runtime.products_url,
    }


def supplier_profile_to_dict(profile: SupplierProfile) -> dict[str, Any]:
    return asdict(profile)
