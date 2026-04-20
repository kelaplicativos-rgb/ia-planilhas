
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from bling_app_zero.core.site_supplier_profiles import (
    DEFAULT_PROFILE,
    SupplierProfile,
    get_supplier_profile,
    supplier_profile_to_dict,
)


AUTH_OUTPUT_DIR = Path("bling_app_zero/output")
AUTH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AUTH_STATE_FILE = AUTH_OUTPUT_DIR / "site_auth_state.json"


@dataclass
class AuthResult:
    ok: bool
    status: str
    provider_slug: str
    provider_name: str
    requires_login: bool
    captcha_detected: bool
    login_url: str
    products_url: str
    message: str
    auth_mode: str
    session_ready: bool
    cookies_count: int = 0
    detected_login_form: bool = False
    detected_redirect_to_login: bool = False
    detected_product_area: bool = False
    profile: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None


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


def _auth_state_default() -> dict[str, Any]:
    return {
        "status": "inativo",
        "provider_slug": "",
        "provider_name": "",
        "requires_login": False,
        "captcha_detected": False,
        "login_url": "",
        "products_url": "",
        "auth_mode": "public",
        "session_ready": False,
        "cookies": [],
        "headers": {},
        "notes": "",
        "last_message": "",
        "username_hint": "",
    }


def load_auth_state() -> dict[str, Any]:
    if not AUTH_STATE_FILE.exists():
        return _auth_state_default()

    try:
        data = json.loads(AUTH_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _auth_state_default()

        base = _auth_state_default()
        base.update(data)
        return base
    except Exception:
        return _auth_state_default()


def save_auth_state(state: dict[str, Any]) -> None:
    base = _auth_state_default()
    base.update(state or {})
    AUTH_STATE_FILE.write_text(
        json.dumps(base, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_auth_state() -> dict[str, Any]:
    state = _auth_state_default()
    save_auth_state(state)
    return state


def auth_state_to_session(st) -> dict[str, Any]:
    state = load_auth_state()
    st.session_state["site_auth_state"] = state
    return state


def clear_auth_state_session(st) -> dict[str, Any]:
    state = clear_auth_state()
    st.session_state["site_auth_state"] = state
    return state


def _requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return session


def _contains_any(text: str, terms: list[str] | tuple[str, ...]) -> bool:
    base = _safe_str(text).lower()
    return any(term.lower() in base for term in terms)


def _detect_login_markers(html: str, final_url: str = "") -> dict[str, bool]:
    page = _safe_str(html).lower()
    final_url_n = _safe_str(final_url).lower()

    has_password = 'type="password"' in page or "name=\"password\"" in page or "senha" in page
    has_email = 'type="email"' in page or "name=\"email\"" in page or "usuário" in page or "usuario" in page
    has_login_text = _contains_any(
        page,
        [
            "acesse sua conta",
            "fazer login",
            "entrar",
            "insira seus dados",
            "login",
            "autenticação",
            "autenticacao",
        ],
    )
    has_captcha = _contains_any(
        page,
        [
            "g-recaptcha",
            "recaptcha",
            "não sou um robô",
            "nao sou um robo",
            "hcaptcha",
        ],
    )
    redirected_to_login = "/login" in final_url_n

    return {
        "has_password": has_password,
        "has_email": has_email,
        "has_login_text": has_login_text,
        "has_captcha": has_captcha,
        "redirected_to_login": redirected_to_login,
        "detected_form": bool(has_password and (has_email or has_login_text)),
    }


def _detect_product_area(html: str, final_url: str = "") -> bool:
    page = _safe_str(html).lower()
    final_url_n = _safe_str(final_url).lower()

    return any(
        [
            "/admin/products" in final_url_n,
            "products" in final_url_n and "admin" in final_url_n,
            _contains_any(page, ["produto", "produtos", "catálogo", "catalogo", "sku", "estoque"]),
        ]
    )


def inspect_site_auth(url: str) -> AuthResult:
    target_url = _normalize_url(url)
    if not target_url:
        return AuthResult(
            ok=False,
            status="erro",
            provider_slug="",
            provider_name="",
            requires_login=False,
            captcha_detected=False,
            login_url="",
            products_url="",
            message="Informe uma URL válida.",
            auth_mode="public",
            session_ready=False,
        )

    profile = get_supplier_profile(target_url)

    session = _requests_session()
    try:
        response = session.get(target_url, timeout=30, allow_redirects=True)
        html = response.text or ""
        final_url = str(response.url)
    except Exception as exc:
        return AuthResult(
            ok=False,
            status="erro",
            provider_slug=profile.slug,
            provider_name=profile.nome,
            requires_login=profile.login_required,
            captcha_detected=profile.captcha_expected,
            login_url=profile.login_url,
            products_url=profile.products_url,
            message=f"Falha ao inspecionar a URL: {exc}",
            auth_mode="login" if profile.login_required else "public",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    markers = _detect_login_markers(html, final_url=final_url)
    detected_product_area = _detect_product_area(html, final_url=final_url)

    requires_login = bool(
        profile.login_required
        or markers["redirected_to_login"]
        or markers["detected_form"]
    )
    captcha_detected = bool(profile.captcha_expected or markers["has_captcha"])

    login_url = profile.login_url or (urljoin(final_url, "/login") if requires_login else "")
    products_url = profile.products_url or target_url

    if detected_product_area and not requires_login:
        message = "Site público detectado e área de produtos acessível sem autenticação."
        status = "publico_detectado"
        auth_mode = "public"
        session_ready = True
    elif requires_login and captcha_detected:
        message = (
            "Fornecedor com login detectado e indício de captcha. "
            "Fluxo autenticado necessário."
        )
        status = "login_captcha_detectado"
        auth_mode = "login"
        session_ready = False
    elif requires_login:
        message = "Fornecedor com login detectado. Fluxo autenticado necessário."
        status = "login_detectado"
        auth_mode = "login"
        session_ready = False
    else:
        message = "Não houve bloqueio de autenticação na inspeção inicial."
        status = "publico_detectado"
        auth_mode = "public"
        session_ready = True

    return AuthResult(
        ok=True,
        status=status,
        provider_slug=profile.slug,
        provider_name=profile.nome,
        requires_login=requires_login,
        captcha_detected=captcha_detected,
        login_url=login_url,
        products_url=products_url,
        message=message,
        auth_mode=auth_mode,
        session_ready=session_ready,
        cookies_count=len(session.cookies),
        detected_login_form=markers["detected_form"],
        detected_redirect_to_login=markers["redirected_to_login"],
        detected_product_area=detected_product_area,
        profile=supplier_profile_to_dict(profile),
        extra={
            "final_url": final_url,
            "hostname": _hostname(final_url),
        },
    )


def apply_inspection_to_state(result: AuthResult) -> dict[str, Any]:
    state = load_auth_state()
    state.update(
        {
            "status": result.status,
            "provider_slug": result.provider_slug,
            "provider_name": result.provider_name,
            "requires_login": result.requires_login,
            "captcha_detected": result.captcha_detected,
            "login_url": result.login_url,
            "products_url": result.products_url,
            "auth_mode": result.auth_mode,
            "session_ready": result.session_ready,
            "notes": result.message,
            "last_message": result.message,
        }
    )
    save_auth_state(state)
    return state


def _extract_form_tokens(html: str) -> dict[str, str]:
    tokens: dict[str, str] = {}

    for name in ("_token", "csrf_token", "csrfmiddlewaretoken", "authenticity_token"):
        pattern = rf'name=["\']{re.escape(name)}["\']\s+value=["\']([^"\']+)["\']'
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            tokens[name] = match.group(1).strip()

    return tokens


def _best_login_payload(
    profile: SupplierProfile,
    username: str,
    password: str,
    html: str,
) -> dict[str, str]:
    payload: dict[str, str] = {}

    username_key = profile.username_field_candidates[0] if profile.username_field_candidates else "email"
    password_key = profile.password_field_candidates[0] if profile.password_field_candidates else "password"

    payload[username_key] = _safe_str(username)
    payload[password_key] = _safe_str(password)
    payload.update(_extract_form_tokens(html))

    return payload


def try_requests_login(
    login_url: str,
    products_url: str,
    username: str,
    password: str,
    profile: SupplierProfile | None = None,
) -> AuthResult:
    profile = profile or get_supplier_profile(login_url or products_url)

    login_url = _normalize_url(login_url)
    products_url = _normalize_url(products_url)

    if not login_url:
        return AuthResult(
            ok=False,
            status="erro",
            provider_slug=profile.slug,
            provider_name=profile.nome,
            requires_login=True,
            captcha_detected=profile.captcha_expected,
            login_url=login_url,
            products_url=products_url,
            message="URL de login inválida.",
            auth_mode="login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    if profile.captcha_expected:
        return AuthResult(
            ok=False,
            status="captcha_pendente",
            provider_slug=profile.slug,
            provider_name=profile.nome,
            requires_login=True,
            captcha_detected=True,
            login_url=login_url,
            products_url=products_url,
            message=(
                "Captcha detectado para este fornecedor. "
                "Login automático por requests não é seguro neste caso."
            ),
            auth_mode="login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    session = _requests_session()

    try:
        login_page = session.get(login_url, timeout=30, allow_redirects=True)
        html = login_page.text or ""
    except Exception as exc:
        return AuthResult(
            ok=False,
            status="erro_login",
            provider_slug=profile.slug,
            provider_name=profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message=f"Falha ao abrir login: {exc}",
            auth_mode="login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    markers = _detect_login_markers(html, final_url=str(login_page.url))
    if markers["has_captcha"]:
        return AuthResult(
            ok=False,
            status="captcha_pendente",
            provider_slug=profile.slug,
            provider_name=profile.nome,
            requires_login=True,
            captcha_detected=True,
            login_url=login_url,
            products_url=products_url,
            message="Captcha detectado na tela de login.",
            auth_mode="login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    payload = _best_login_payload(
        profile=profile,
        username=username,
        password=password,
        html=html,
    )

    try:
        response = session.post(
            login_url,
            data=payload,
            timeout=30,
            allow_redirects=True,
        )
        final_html = response.text or ""
        final_url = str(response.url)
    except Exception as exc:
        return AuthResult(
            ok=False,
            status="erro_login",
            provider_slug=profile.slug,
            provider_name=profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message=f"Falha no envio do login: {exc}",
            auth_mode="login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    product_area_ok = False
    if products_url:
        try:
            page_products = session.get(products_url, timeout=30, allow_redirects=True)
            product_area_ok = _detect_product_area(page_products.text or "", final_url=str(page_products.url))
            final_url = str(page_products.url)
        except Exception:
            product_area_ok = False
    else:
        product_area_ok = _detect_product_area(final_html, final_url=final_url)

    if product_area_ok:
        state = load_auth_state()
        state.update(
            {
                "status": "autenticado",
                "provider_slug": profile.slug,
                "provider_name": profile.nome,
                "requires_login": True,
                "captcha_detected": False,
                "login_url": login_url,
                "products_url": products_url,
                "auth_mode": "login",
                "session_ready": True,
                "cookies": [
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "domain": cookie.domain,
                        "path": cookie.path,
                    }
                    for cookie in session.cookies
                ],
                "headers": dict(session.headers),
                "username_hint": _safe_str(username),
                "last_message": "Sessão autenticada com sucesso.",
            }
        )
        save_auth_state(state)

        return AuthResult(
            ok=True,
            status="autenticado",
            provider_slug=profile.slug,
            provider_name=profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message="Sessão autenticada com sucesso.",
            auth_mode="login",
            session_ready=True,
            cookies_count=len(session.cookies),
            detected_product_area=True,
            profile=supplier_profile_to_dict(profile),
            extra={"final_url": final_url},
        )

    return AuthResult(
        ok=False,
        status="falha_autenticacao",
        provider_slug=profile.slug,
        provider_name=profile.nome,
        requires_login=True,
        captcha_detected=False,
        login_url=login_url,
        products_url=products_url,
        message=(
            "O login foi enviado, mas a área de produtos não ficou acessível. "
            "Pode haver captcha, proteção extra ou fluxo JS."
        ),
        auth_mode="login",
        session_ready=False,
        cookies_count=len(session.cookies),
        profile=supplier_profile_to_dict(profile),
        extra={"final_url": final_url},
    )


def get_auth_headers_and_cookies() -> dict[str, Any]:
    state = load_auth_state()
    return {
        "headers": state.get("headers", {}) or {},
        "cookies": state.get("cookies", []) or [],
        "session_ready": bool(state.get("session_ready", False)),
        "auth_mode": _safe_str(state.get("auth_mode", "public")) or "public",
        "provider_slug": _safe_str(state.get("provider_slug")),
        "provider_name": _safe_str(state.get("provider_name")),
        "products_url": _safe_str(state.get("products_url")),
        "login_url": _safe_str(state.get("login_url")),
        "requires_login": bool(state.get("requires_login", False)),
        "captcha_detected": bool(state.get("captcha_detected", False)),
    }


def get_profile_for_url(url: str) -> SupplierProfile:
    profile = get_supplier_profile(url)
    return profile if profile else DEFAULT_PROFILE
