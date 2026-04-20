from __future__ import annotations

from dataclasses import dataclass, asdict
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
    notes="Fornecedor público sem necessidade de autenticação.",
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
    notes=(
        "Catálogo autenticado. Há indício de captcha na tela de login. "
        "O fluxo recomendado é sessão autenticada com navegador automatizado "
        "e reaproveitamento de estado."
    ),
)

_PROFILES = (
    OBA_OBA_MIX_PROFILE,
)


def _hostname(url: str) -> str:
    try:
        return (urlparse(str(url or "")).hostname or "").strip().lower()
    except Exception:
        return ""


def get_supplier_profile(url: str) -> SupplierProfile:
    host = _hostname(url)
    if not host:
        return DEFAULT_PROFILE

    for profile in _PROFILES:
        if any(host == dominio or host.endswith(f".{dominio}") for dominio in profile.dominio_match):
            return profile

    return DEFAULT_PROFILE


def supplier_profile_to_dict(profile: SupplierProfile) -> dict[str, Any]:
    return asdict(profile)
