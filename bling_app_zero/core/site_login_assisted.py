
from __future__ import annotations

from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

try:
    from bling_app_zero.core.session_manager import (
        finalizar_login_assistido,
        iniciar_login_assistido,
        montar_auth_context,
        sessao_esta_pronta,
    )
except Exception:
    def iniciar_login_assistido(url_login: str) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "aguardando_login_manual",
            "url": url_login,
            "mensagem": "Abra o login no navegador e conclua a autenticação.",
        }

    def finalizar_login_assistido(
        *,
        base_url: str,
        cookies: list[dict[str, Any]],
        headers: dict[str, Any] | None = None,
        fornecedor: str = "",
        products_url: str = "",
        login_url: str = "",
        observacao: str = "",
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "session_ready",
            "mensagem": "Sessão salva.",
        }

    def montar_auth_context(base_url: str, fornecedor: str = "") -> dict[str, Any]:
        return {}

    def sessao_esta_pronta(base_url: str, fornecedor: str = "") -> bool:
        return False


try:
    from bling_app_zero.core.site_supplier_profiles import (
        get_supplier_profile,
        supplier_profile_to_dict,
    )
except Exception:
    def get_supplier_profile(url: str):
        return None

    def supplier_profile_to_dict(profile) -> dict[str, Any]:
        if hasattr(profile, "__dict__"):
            return dict(profile.__dict__)
        if isinstance(profile, dict):
            return profile
        return {}


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize_url(url: str) -> str:
    raw = _safe_str(url)
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw.strip()


def _base_root(url: str) -> str:
    parsed = urlparse(_normalize_url(url))
    if not parsed.scheme or not parsed.netloc:
        return _normalize_url(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _profile_for_url(url: str):
    try:
        return get_supplier_profile(url)
    except Exception:
        return None


def _profile_to_dict(profile) -> dict[str, Any]:
    try:
        return supplier_profile_to_dict(profile)
    except Exception:
        if hasattr(profile, "__dict__"):
            return asdict(profile) if hasattr(profile, "__dataclass_fields__") else dict(profile.__dict__)
        if isinstance(profile, dict):
            return dict(profile)
        return {}


def _resolved_profile_data(url: str) -> dict[str, Any]:
    profile = _profile_for_url(url)
    data = _profile_to_dict(profile)
    if not isinstance(data, dict):
        data = {}
    return data


def _provider_slug(url: str) -> str:
    profile = _resolved_profile_data(url)
    slug = _safe_str(profile.get("slug"))
    if slug:
        return slug

    host = (urlparse(_normalize_url(url)).hostname or "").strip().lower()
    host = host.replace("www.", "")
    return host.replace(".", "_") if host else "fornecedor"


def _resolved_login_url(url: str) -> str:
    profile = _resolved_profile_data(url)
    login_url = _safe_str(profile.get("login_url"))
    if login_url:
        return login_url
    return _normalize_url(url)


def _resolved_products_url(url: str) -> str:
    profile = _resolved_profile_data(url)
    products_url = _safe_str(profile.get("products_url"))
    if products_url:
        return products_url
    return _base_root(url)


def _resolved_auth_mode(url: str) -> str:
    profile = _resolved_profile_data(url)
    return _safe_str(profile.get("auth_mode")) or "public"


def _requires_assisted_login(url: str) -> bool:
    profile = _resolved_profile_data(url)
    return bool(profile.get("requires_assisted_login", False))


def _requires_whatsapp_code(url: str) -> bool:
    profile = _resolved_profile_data(url)
    return bool(profile.get("requires_whatsapp_code", False))


def _captcha_expected(url: str) -> bool:
    profile = _resolved_profile_data(url)
    return bool(profile.get("captcha_expected", False))


def iniciar_fluxo_login_assistido(url: str) -> dict[str, Any]:
    url = _normalize_url(url)
    if not url:
        return {
            "ok": False,
            "status": "erro",
            "mensagem": "Informe uma URL válida para iniciar o login assistido.",
        }

    login_url = _resolved_login_url(url)
    products_url = _resolved_products_url(url)
    provider_slug = _provider_slug(url)
    auth_mode = _resolved_auth_mode(url)
    requires_assisted = _requires_assisted_login(url)
    requires_whatsapp = _requires_whatsapp_code(url)
    captcha_expected = _captcha_expected(url)

    resposta = iniciar_login_assistido(login_url)

    mensagem = _safe_str(resposta.get("mensagem"))
    if requires_whatsapp:
        mensagem = (
            mensagem
            or "Abra o login, conclua a autenticação e confirme o código recebido no WhatsApp."
        )
    elif captcha_expected:
        mensagem = (
            mensagem
            or "Abra o login, resolva o captcha e finalize a autenticação."
        )
    elif requires_assisted:
        mensagem = (
            mensagem
            or "Abra o login no navegador e finalize a autenticação manualmente."
        )

    return {
        "ok": bool(resposta.get("ok", True)),
        "status": _safe_str(resposta.get("status")) or "aguardando_login_manual",
        "mensagem": mensagem,
        "login_url": login_url,
        "products_url": products_url,
        "provider_slug": provider_slug,
        "auth_mode": auth_mode,
        "requires_assisted_login": requires_assisted,
        "requires_whatsapp_code": requires_whatsapp,
        "captcha_expected": captcha_expected,
        "profile": _resolved_profile_data(url),
    }


def salvar_sessao_assistida(
    *,
    url: str,
    cookies: list[dict[str, Any]],
    headers: dict[str, Any] | None = None,
    observacao: str = "",
) -> dict[str, Any]:
    url = _normalize_url(url)
    if not url:
        return {
            "ok": False,
            "status": "erro",
            "mensagem": "Informe uma URL válida para salvar a sessão assistida.",
        }

    base_url = _base_root(url)
    login_url = _resolved_login_url(url)
    products_url = _resolved_products_url(url)
    provider_slug = _provider_slug(url)

    resultado = finalizar_login_assistido(
        base_url=base_url,
        cookies=cookies if isinstance(cookies, list) else [],
        headers=headers if isinstance(headers, dict) else {},
        fornecedor=provider_slug,
        products_url=products_url,
        login_url=login_url,
        observacao=observacao or "Sessão salva a partir do fluxo assistido.",
    )

    contexto = montar_auth_context(base_url=base_url, fornecedor=provider_slug)

    return {
        "ok": bool(resultado.get("ok", False)),
        "status": _safe_str(resultado.get("status")) or "session_ready",
        "mensagem": _safe_str(resultado.get("mensagem")) or "Sessão assistida salva com sucesso.",
        "provider_slug": provider_slug,
        "login_url": login_url,
        "products_url": products_url,
        "auth_context": contexto if isinstance(contexto, dict) else {},
    }


def resumo_fluxo_login_assistido(url: str) -> dict[str, Any]:
    url = _normalize_url(url)
    if not url:
        return {
            "ok": False,
            "status": "erro",
            "mensagem": "URL inválida.",
        }

    base_url = _base_root(url)
    provider_slug = _provider_slug(url)
    products_url = _resolved_products_url(url)
    login_url = _resolved_login_url(url)
    auth_mode = _resolved_auth_mode(url)
    requires_whatsapp = _requires_whatsapp_code(url)
    captcha_expected = _captcha_expected(url)

    contexto = montar_auth_context(base_url=base_url, fornecedor=provider_slug)
    session_ready = sessao_esta_pronta(base_url=base_url, fornecedor=provider_slug)

    return {
        "ok": True,
        "provider_slug": provider_slug,
        "login_url": login_url,
        "products_url": products_url,
        "auth_mode": auth_mode,
        "requires_whatsapp_code": requires_whatsapp,
        "captcha_expected": captcha_expected,
        "session_ready": bool(session_ready),
        "auth_context": contexto if isinstance(contexto, dict) else {},
        "mensagem": (
            "Sessão autenticada pronta para uso."
            if session_ready
            else "Sessão ainda não salva. É necessário concluir o login assistido."
        ),
        "profile": _resolved_profile_data(url),
    }
