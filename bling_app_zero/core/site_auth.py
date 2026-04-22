from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from bling_app_zero.core.site_supplier_profiles import (
    DEFAULT_PROFILE,
    SupplierProfile,
    get_supplier_profile,
    infer_supplier_profile_from_detection,
    supplier_profile_to_dict,
)

try:
    from bling_app_zero.core.site_supplier_store import (
        get_site_supplier_by_slug,
        list_site_suppliers,
    )
except Exception:
    get_site_supplier_by_slug = None
    list_site_suppliers = None

try:
    from bling_app_zero.core.session_manager import (
        STATUS_LOGIN_CAPTCHA_DETECTADO,
        STATUS_LOGIN_REQUERIDO,
        STATUS_PUBLICO,
        STATUS_SESSAO_PRONTA,
        detectar_login_captcha,
        montar_auth_context,
        salvar_status_login_em_sessao,
        salvar_storage_state,
        sessao_esta_pronta,
    )
except Exception:
    STATUS_PUBLICO = "publico"
    STATUS_LOGIN_CAPTCHA_DETECTADO = "login_captcha_detectado"
    STATUS_LOGIN_REQUERIDO = "login_required"
    STATUS_SESSAO_PRONTA = "session_ready"

    def detectar_login_captcha(html: str, url_atual: str = "") -> dict[str, Any]:
        page = str(html or "").lower()
        final_url = str(url_atual or "").lower()

        has_login = any(
            token in page
            for token in [
                "login",
                "fazer login",
                "faça login",
                "entrar",
                "senha",
                "autenticacao",
                "autenticação",
            ]
        ) or any(
            token in final_url
            for token in ["/login", "/entrar", "/account", "/auth", "/conta"]
        )

        has_captcha = any(
            token in page
            for token in [
                "captcha",
                "g-recaptcha",
                "grecaptcha",
                "hcaptcha",
                "cloudflare",
                "não sou um robô",
                "nao sou um robo",
            ]
        )

        status = STATUS_PUBLICO
        if has_login and has_captcha:
            status = STATUS_LOGIN_CAPTCHA_DETECTADO
        elif has_login:
            status = STATUS_LOGIN_REQUERIDO

        return {
            "exige_login": has_login,
            "captcha_detectado": has_captcha,
            "login_detectado": has_login,
            "status": status,
            "motivos": [],
        }

    def montar_auth_context(base_url: str, fornecedor: str = "") -> dict[str, Any]:
        return {}

    def salvar_storage_state(
        *,
        base_url: str,
        storage_state: dict[str, Any],
        fornecedor: str = "",
        products_url: str = "",
        login_url: str = "",
        status: str = STATUS_SESSAO_PRONTA,
        observacao: str = "",
    ) -> dict[str, Any]:
        return {"ok": False}

    def salvar_status_login_em_sessao(
        *,
        base_url: str,
        status: str,
        mensagem: str = "",
        exige_login: bool = False,
        captcha_detectado: bool = False,
        fornecedor: str = "",
    ) -> None:
        return None

    def sessao_esta_pronta(base_url: str, fornecedor: str = "") -> bool:
        return False


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
    detected_whatsapp_code: bool = False
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


def _normalize_base_root(url: str) -> str:
    parsed = urlparse(_normalize_url(url))
    if not parsed.scheme or not parsed.netloc:
        return _normalize_url(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _hostname(url: str) -> str:
    try:
        return (urlparse(_normalize_url(url)).hostname or "").strip().lower()
    except Exception:
        return ""


def _same_host(url_a: str, url_b: str) -> bool:
    host_a = _hostname(url_a)
    host_b = _hostname(url_b)
    return bool(host_a and host_b and host_a == host_b)


def _fornecedor_slug(url: str, profile: SupplierProfile | None = None) -> str:
    if profile and _safe_str(profile.slug):
        return _safe_str(profile.slug)

    host = _hostname(url)
    if host:
        slug = host.replace("www.", "")
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        if slug:
            return slug

    bruto = _safe_str(url).lower()
    bruto = re.sub(r"^https?://", "", bruto)
    bruto = re.sub(r"[^a-z0-9]+", "_", bruto)
    bruto = re.sub(r"_+", "_", bruto).strip("_")
    return bruto or "fornecedor"


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
        "storage_state_path": "",
        "metadata_path": "",
        "detected_whatsapp_code": False,
        "requires_whatsapp_code": False,
        "source_kind": "",
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


def _listar_fornecedores_salvos() -> list[dict[str, Any]]:
    if list_site_suppliers is None:
        return []
    try:
        fornecedores = list_site_suppliers()
        return fornecedores if isinstance(fornecedores, list) else []
    except Exception:
        return []


def _get_saved_supplier(*, slug: str = "", url: str = "") -> dict[str, Any] | None:
    slug = _safe_str(slug)
    url = _normalize_url(url)

    if slug and get_site_supplier_by_slug is not None:
        try:
            fornecedor = get_site_supplier_by_slug(slug)
            if isinstance(fornecedor, dict) and fornecedor:
                return fornecedor
        except Exception:
            pass

    if not url:
        return None

    base_root = _normalize_base_root(url)
    host = _hostname(url)

    for item in _listar_fornecedores_salvos():
        if not isinstance(item, dict):
            continue

        item_url = _normalize_url(item.get("url_base", ""))
        item_login = _normalize_url(item.get("login_url", ""))
        item_products = _normalize_url(item.get("products_url", ""))

        if item_url and _normalize_base_root(item_url) == base_root:
            return item
        if item_login and _same_host(item_login, url):
            return item
        if item_products and _same_host(item_products, url):
            return item
        if host and _hostname(item_url) == host:
            return item

    return None


def _profile_from_saved_supplier(saved_supplier: dict[str, Any] | None, url: str) -> SupplierProfile:
    base_profile = get_supplier_profile(url)
    if not saved_supplier:
        return base_profile if base_profile else DEFAULT_PROFILE

    base = base_profile if base_profile else DEFAULT_PROFILE
    nome = _safe_str(saved_supplier.get("nome")) or _safe_str(getattr(base, "nome", "")) or "Fornecedor"
    slug = _safe_str(saved_supplier.get("slug")) or _safe_str(getattr(base, "slug", "")) or _fornecedor_slug(url)
    login_url = _normalize_url(saved_supplier.get("login_url")) or _safe_str(getattr(base, "login_url", ""))
    products_url = _normalize_url(saved_supplier.get("products_url")) or _safe_str(getattr(base, "products_url", ""))
    auth_mode = _safe_str(saved_supplier.get("auth_mode")) or _safe_str(getattr(base, "auth_mode", "")) or "public"
    observacoes = _safe_str(saved_supplier.get("observacoes"))

    login_required = bool(
        getattr(base, "login_required", False)
        or auth_mode in {"login", "captcha", "whatsapp_code"}
        or bool(login_url)
    )
    captcha_expected = bool(getattr(base, "captcha_expected", False) or auth_mode == "captcha")
    requires_whatsapp_code = bool(getattr(base, "requires_whatsapp_code", False) or auth_mode == "whatsapp_code")

    try:
        return SupplierProfile(
            slug=slug,
            nome=nome,
            auth_mode=auth_mode,
            login_required=login_required,
            captcha_expected=captcha_expected,
            requires_whatsapp_code=requires_whatsapp_code,
            login_url=login_url,
            products_url=products_url,
            login_path_hints=list(getattr(base, "login_path_hints", []) or []),
            products_path_hints=list(getattr(base, "products_path_hints", []) or []),
            username_field_candidates=list(getattr(base, "username_field_candidates", []) or ["email"]),
            password_field_candidates=list(getattr(base, "password_field_candidates", []) or ["password"]),
            source_kind=_safe_str(getattr(base, "source_kind", "")) or "saved_supplier",
            observacoes=observacoes or _safe_str(getattr(base, "observacoes", "")),
        )
    except TypeError:
        # fallback conservador caso a dataclass tenha mudado
        return base


def _resolve_saved_supplier_profile(url: str, fornecedor: str = "") -> tuple[SupplierProfile, dict[str, Any] | None]:
    saved_supplier = _get_saved_supplier(slug=fornecedor, url=url)
    profile = _profile_from_saved_supplier(saved_supplier, url)
    return profile, saved_supplier


def _merge_auth_state_with_session_manager(
    state: dict[str, Any],
    *,
    base_url: str = "",
    fornecedor: str = "",
) -> dict[str, Any]:
    base = _auth_state_default()
    base.update(state or {})

    requested_url = _normalize_url(base_url)
    requested_slug = _safe_str(fornecedor)

    profile, saved_supplier = _resolve_saved_supplier_profile(
        requested_url or _safe_str(base.get("products_url")) or _safe_str(base.get("login_url")),
        requested_slug or _safe_str(base.get("provider_slug")),
    )

    if saved_supplier:
        base["provider_slug"] = _safe_str(saved_supplier.get("slug")) or _safe_str(base.get("provider_slug"))
        base["provider_name"] = _safe_str(saved_supplier.get("nome")) or _safe_str(base.get("provider_name"))
        base["login_url"] = _normalize_url(saved_supplier.get("login_url")) or _safe_str(base.get("login_url"))
        base["products_url"] = _normalize_url(saved_supplier.get("products_url")) or _safe_str(base.get("products_url"))
        base["auth_mode"] = _safe_str(saved_supplier.get("auth_mode")) or _safe_str(base.get("auth_mode")) or "public"

    if not _safe_str(base.get("provider_slug")):
        base["provider_slug"] = _safe_str(getattr(profile, "slug", "")) or requested_slug
    if not _safe_str(base.get("provider_name")):
        base["provider_name"] = _safe_str(getattr(profile, "nome", ""))
    if not _safe_str(base.get("login_url")):
        base["login_url"] = _safe_str(getattr(profile, "login_url", ""))
    if not _safe_str(base.get("products_url")):
        base["products_url"] = _safe_str(getattr(profile, "products_url", ""))
    if not _safe_str(base.get("auth_mode")):
        base["auth_mode"] = _safe_str(getattr(profile, "auth_mode", "")) or "public"

    contexto_base = (
        requested_url
        or _safe_str(base.get("products_url"))
        or _safe_str(base.get("login_url"))
    )
    contexto_fornecedor = requested_slug or _safe_str(base.get("provider_slug"))

    if not contexto_base:
        return base

    try:
        contexto = montar_auth_context(base_url=contexto_base, fornecedor=contexto_fornecedor)
    except Exception:
        contexto = {}

    if isinstance(contexto, dict) and contexto:
        base["storage_state_path"] = _safe_str(contexto.get("storage_state_path")) or _safe_str(base.get("storage_state_path"))
        base["metadata_path"] = _safe_str(contexto.get("metadata_path")) or _safe_str(base.get("metadata_path"))
        base["products_url"] = _safe_str(contexto.get("products_url")) or _safe_str(base.get("products_url"))
        base["login_url"] = _safe_str(contexto.get("login_url")) or _safe_str(base.get("login_url"))
        base["session_ready"] = bool(contexto.get("session_ready", base.get("session_ready", False)))
        base["status"] = _safe_str(contexto.get("status")) or _safe_str(base.get("status"))
        base["provider_slug"] = _safe_str(contexto.get("provider_slug")) or _safe_str(base.get("provider_slug"))
        base["provider_name"] = _safe_str(contexto.get("provider_name")) or _safe_str(base.get("provider_name"))

        if bool(contexto.get("session_ready", False)):
            base["cookies"] = contexto.get("cookies", []) or base.get("cookies", [])
            base["headers"] = contexto.get("headers", {}) or base.get("headers", {})

    return base


def auth_state_to_session(st) -> dict[str, Any]:
    state = _merge_auth_state_with_session_manager(load_auth_state())
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

    has_password = 'type="password"' in page or 'name="password"' in page or "senha" in page
    has_email = (
        'type="email"' in page
        or 'name="email"' in page
        or 'name="login"' in page
        or 'name="username"' in page
        or "usuário" in page
        or "usuario" in page
        or "e-mail" in page
        or "telefone" in page
        or "celular" in page
    )
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
            "código",
            "codigo",
            "verificação",
            "verificacao",
            "whatsapp",
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
            "captcha",
            "cloudflare",
        ],
    )
    redirected_to_login = any(
        token in final_url_n
        for token in ["/login", "/entrar", "/auth", "/account", "/conta"]
    )
    has_whatsapp_code = _contains_any(
        page,
        [
            "whatsapp",
            "código enviado",
            "codigo enviado",
            "confirme o código",
            "confirme o codigo",
            "verificação por whatsapp",
            "verificacao por whatsapp",
            "token enviado",
        ],
    )

    return {
        "has_password": has_password,
        "has_email": has_email,
        "has_login_text": has_login_text,
        "has_captcha": has_captcha,
        "redirected_to_login": redirected_to_login,
        "detected_form": bool((has_password or has_whatsapp_code) and (has_email or has_login_text)),
        "has_whatsapp_code": has_whatsapp_code,
    }


def _detect_product_area(html: str, final_url: str = "") -> bool:
    page = _safe_str(html).lower()
    final_url_n = _safe_str(final_url).lower()

    return any(
        [
            "/admin/products" in final_url_n,
            "/produtos" in final_url_n,
            "/products" in final_url_n,
            "/estoque" in final_url_n,
            "products" in final_url_n and "admin" in final_url_n,
            _contains_any(page, ["produto", "produtos", "catálogo", "catalogo", "sku", "estoque", "inventory", "stock"]),
        ]
    )


def _resolve_profile_and_urls(
    *,
    url: str,
    profile: SupplierProfile,
    requires_login: bool = False,
    captcha_detected: bool = False,
    whatsapp_code_detected: bool = False,
) -> tuple[SupplierProfile, str, str]:
    resolved_profile = profile

    if resolved_profile.slug == DEFAULT_PROFILE.slug:
        resolved_profile = infer_supplier_profile_from_detection(
            url=url,
            requires_login=requires_login,
            captcha_detected=captcha_detected,
            whatsapp_code_detected=whatsapp_code_detected,
        )

    login_url = _safe_str(resolved_profile.login_url)
    products_url = _safe_str(resolved_profile.products_url)

    if not login_url and resolved_profile.login_required and resolved_profile.login_path_hints:
        login_url = urljoin(_normalize_base_root(url), resolved_profile.login_path_hints[0])

    if not products_url and resolved_profile.products_path_hints:
        products_url = urljoin(_normalize_base_root(url), resolved_profile.products_path_hints[0])

    if not products_url:
        products_url = _normalize_base_root(url)

    return resolved_profile, login_url, products_url


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

    profile, saved_supplier = _resolve_saved_supplier_profile(target_url)
    provider_slug = _safe_str(saved_supplier.get("slug")) if saved_supplier else _fornecedor_slug(target_url, profile)
    provider_name = _safe_str(saved_supplier.get("nome")) if saved_supplier else _safe_str(profile.nome)
    base_root = _normalize_base_root(target_url)

    if sessao_esta_pronta(base_url=base_root, fornecedor=provider_slug):
        contexto = montar_auth_context(base_url=base_root, fornecedor=provider_slug)
        products_url = (
            _safe_str(contexto.get("products_url"))
            or _normalize_url(saved_supplier.get("products_url") if saved_supplier else "")
            or profile.products_url
            or base_root
        )
        login_url = (
            _safe_str(contexto.get("login_url"))
            or _normalize_url(saved_supplier.get("login_url") if saved_supplier else "")
            or profile.login_url
            or urljoin(base_root, "/login")
        )

        return AuthResult(
            ok=True,
            status=STATUS_SESSAO_PRONTA,
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=bool(profile.captcha_expected),
            login_url=login_url,
            products_url=products_url,
            message="Sessão autenticada já disponível para este fornecedor.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "login")) or "login",
            session_ready=True,
            cookies_count=len(contexto.get("cookies", []) or []),
            detected_product_area=True,
            detected_whatsapp_code=bool(getattr(profile, "requires_whatsapp_code", False)),
            profile=supplier_profile_to_dict(profile),
            extra={
                "hostname": _hostname(target_url),
                "from_saved_session": True,
                "requires_whatsapp_code": bool(getattr(profile, "requires_whatsapp_code", False)),
            },
        )

    session = _requests_session()
    try:
        response = session.get(target_url, timeout=30, allow_redirects=True)
        html = response.text or ""
        final_url = str(response.url)
    except Exception as exc:
        resolved_profile, login_url, products_url = _resolve_profile_and_urls(
            url=target_url,
            profile=profile,
        )
        if saved_supplier:
            login_url = _normalize_url(saved_supplier.get("login_url")) or login_url
            products_url = _normalize_url(saved_supplier.get("products_url")) or products_url

        return AuthResult(
            ok=False,
            status="erro",
            provider_slug=provider_slug,
            provider_name=provider_name or resolved_profile.nome,
            requires_login=resolved_profile.login_required,
            captcha_detected=resolved_profile.captcha_expected,
            login_url=login_url,
            products_url=products_url,
            message=f"Falha ao inspecionar a URL: {exc}",
            auth_mode=_safe_str(getattr(resolved_profile, "auth_mode", "login" if resolved_profile.login_required else "public")) or "public",
            session_ready=False,
            profile=supplier_profile_to_dict(resolved_profile),
        )

    markers = _detect_login_markers(html, final_url=final_url)
    detected_product_area = _detect_product_area(html, final_url=final_url)
    analise = detectar_login_captcha(html=html, url_atual=final_url)

    requires_login = bool(
        profile.login_required
        or markers["redirected_to_login"]
        or markers["detected_form"]
        or analise.get("exige_login", False)
    )
    captcha_detected = bool(
        profile.captcha_expected
        or markers["has_captcha"]
        or analise.get("captcha_detectado", False)
    )
    whatsapp_code_detected = bool(
        getattr(profile, "requires_whatsapp_code", False)
        or markers["has_whatsapp_code"]
    )

    resolved_profile, login_url, products_url = _resolve_profile_and_urls(
        url=target_url,
        profile=profile,
        requires_login=requires_login,
        captcha_detected=captcha_detected,
        whatsapp_code_detected=whatsapp_code_detected,
    )

    if saved_supplier:
        login_url = _normalize_url(saved_supplier.get("login_url")) or login_url
        products_url = _normalize_url(saved_supplier.get("products_url")) or products_url

    auth_mode = _safe_str(getattr(resolved_profile, "auth_mode", "")) or ("login" if requires_login else "public")

    if detected_product_area and not requires_login:
        message = "Site público detectado e área de produtos acessível sem autenticação."
        status = STATUS_PUBLICO
        session_ready = True
    elif whatsapp_code_detected:
        message = "Fornecedor com autenticação assistida por código detectado. Fluxo manual assistido necessário."
        status = STATUS_LOGIN_REQUERIDO
        session_ready = False
    elif requires_login and captcha_detected:
        message = "Fornecedor com login detectado e indício de captcha. Fluxo autenticado necessário."
        status = STATUS_LOGIN_CAPTCHA_DETECTADO
        session_ready = False
    elif requires_login:
        message = "Fornecedor com login detectado. Fluxo autenticado necessário."
        status = STATUS_LOGIN_REQUERIDO
        session_ready = False
    else:
        message = "Não houve bloqueio de autenticação na inspeção inicial."
        status = STATUS_PUBLICO
        session_ready = True

    try:
        salvar_status_login_em_sessao(
            base_url=base_root,
            fornecedor=provider_slug,
            status=status,
            mensagem=message,
            exige_login=requires_login,
            captcha_detectado=captcha_detected,
        )
    except Exception:
        pass

    return AuthResult(
        ok=True,
        status=status,
        provider_slug=provider_slug,
        provider_name=provider_name or resolved_profile.nome,
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
        detected_whatsapp_code=whatsapp_code_detected,
        profile=supplier_profile_to_dict(resolved_profile),
        extra={
            "final_url": final_url,
            "hostname": _hostname(final_url),
            "requires_whatsapp_code": bool(getattr(resolved_profile, "requires_whatsapp_code", False)),
            "source_kind": _safe_str(getattr(resolved_profile, "source_kind", "")),
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
            "detected_whatsapp_code": result.detected_whatsapp_code,
            "requires_whatsapp_code": bool((result.profile or {}).get("requires_whatsapp_code", False)),
            "source_kind": _safe_str((result.profile or {}).get("source_kind", "")),
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


def _cookies_to_storage_state_cookies(session: requests.Session) -> list[dict[str, Any]]:
    cookies: list[dict[str, Any]] = []

    for cookie in session.cookies:
        cookies.append(
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path or "/",
                "expires": getattr(cookie, "expires", None),
                "httpOnly": False,
                "secure": bool(getattr(cookie, "secure", False)),
                "sameSite": "Lax",
            }
        )

    return cookies


def _persistir_sessao_requests(
    *,
    session: requests.Session,
    base_url: str,
    provider_slug: str,
    login_url: str,
    products_url: str,
    observacao: str,
) -> dict[str, Any]:
    storage_state = {
        "cookies": _cookies_to_storage_state_cookies(session),
        "origins": [],
    }

    return salvar_storage_state(
        base_url=base_url,
        fornecedor=provider_slug,
        login_url=login_url,
        products_url=products_url,
        storage_state=storage_state,
        status=STATUS_SESSAO_PRONTA,
        observacao=observacao,
    )


def try_requests_login(
    login_url: str,
    products_url: str,
    username: str,
    password: str,
    profile: SupplierProfile | None = None,
) -> AuthResult:
    seed_url = login_url or products_url
    saved_profile, saved_supplier = _resolve_saved_supplier_profile(seed_url)
    profile = profile or saved_profile

    login_url = _normalize_url(login_url) or _normalize_url(saved_supplier.get("login_url") if saved_supplier else "")
    products_url = _normalize_url(products_url) or _normalize_url(saved_supplier.get("products_url") if saved_supplier else "")
    base_url = _normalize_base_root(products_url or login_url)
    provider_slug = _safe_str(saved_supplier.get("slug")) if saved_supplier else _fornecedor_slug(base_url, profile)
    provider_name = _safe_str(saved_supplier.get("nome")) if saved_supplier else _safe_str(profile.nome)

    if not login_url:
        return AuthResult(
            ok=False,
            status="erro",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=profile.captcha_expected,
            login_url=login_url,
            products_url=products_url,
            message="URL de login inválida.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "login")) or "login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    if getattr(profile, "requires_whatsapp_code", False):
        try:
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=provider_slug,
                status=STATUS_LOGIN_REQUERIDO,
                mensagem="Este fornecedor exige autenticação assistida por código. Use o login assistido no navegador.",
                exige_login=True,
                captcha_detectado=False,
            )
        except Exception:
            pass

        return AuthResult(
            ok=False,
            status="codigo_assistido_pendente",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message="Este fornecedor exige autenticação assistida por código/WhatsApp. Requests não é o fluxo correto.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "whatsapp_code")) or "whatsapp_code",
            session_ready=False,
            detected_whatsapp_code=True,
            profile=supplier_profile_to_dict(profile),
        )

    if profile.captcha_expected:
        try:
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=provider_slug,
                status=STATUS_LOGIN_CAPTCHA_DETECTADO,
                mensagem="Captcha detectado para este fornecedor. Use o login assistido no navegador.",
                exige_login=True,
                captcha_detectado=True,
            )
        except Exception:
            pass

        return AuthResult(
            ok=False,
            status="captcha_pendente",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=True,
            login_url=login_url,
            products_url=products_url,
            message="Captcha detectado para este fornecedor. Login automático por requests não é seguro neste caso.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "captcha")) or "captcha",
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
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message=f"Falha ao abrir login: {exc}",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "login")) or "login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    markers = _detect_login_markers(html, final_url=str(login_page.url))
    analise_login = detectar_login_captcha(html=html, url_atual=str(login_page.url))

    if markers["has_whatsapp_code"] or getattr(profile, "requires_whatsapp_code", False):
        try:
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=provider_slug,
                status=STATUS_LOGIN_REQUERIDO,
                mensagem="Código/2FA detectado na tela de login. Use o login assistido no navegador.",
                exige_login=True,
                captcha_detectado=False,
            )
        except Exception:
            pass

        return AuthResult(
            ok=False,
            status="codigo_assistido_pendente",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message="Código/2FA detectado na tela de login.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "whatsapp_code")) or "whatsapp_code",
            session_ready=False,
            detected_whatsapp_code=True,
            profile=supplier_profile_to_dict(profile),
        )

    if markers["has_captcha"] or analise_login.get("captcha_detectado", False):
        try:
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=provider_slug,
                status=STATUS_LOGIN_CAPTCHA_DETECTADO,
                mensagem="Captcha detectado na tela de login. Use o login assistido no navegador.",
                exige_login=True,
                captcha_detectado=True,
            )
        except Exception:
            pass

        return AuthResult(
            ok=False,
            status="captcha_pendente",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=True,
            login_url=login_url,
            products_url=products_url,
            message="Captcha detectado na tela de login.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "captcha")) or "captcha",
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
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message=f"Falha no envio do login: {exc}",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "login")) or "login",
            session_ready=False,
            profile=supplier_profile_to_dict(profile),
        )

    product_area_ok = False
    if products_url:
        try:
            page_products = session.get(products_url, timeout=30, allow_redirects=True)
            final_url = str(page_products.url)
            product_area_ok = _detect_product_area(page_products.text or "", final_url=final_url)
            final_html = page_products.text or final_html
        except Exception:
            product_area_ok = False
    else:
        product_area_ok = _detect_product_area(final_html, final_url=final_url)

    analise_final = detectar_login_captcha(html=final_html, url_atual=final_url)
    markers_final = _detect_login_markers(final_html, final_url=final_url)

    if markers_final["has_whatsapp_code"]:
        try:
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=provider_slug,
                status=STATUS_LOGIN_REQUERIDO,
                mensagem="Código/2FA detectado após tentativa de login. Use o login assistido no navegador.",
                exige_login=True,
                captcha_detectado=False,
            )
        except Exception:
            pass

        return AuthResult(
            ok=False,
            status="codigo_assistido_pendente",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url,
            message="Código/2FA detectado após tentativa de login.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "whatsapp_code")) or "whatsapp_code",
            session_ready=False,
            cookies_count=len(session.cookies),
            detected_whatsapp_code=True,
            profile=supplier_profile_to_dict(profile),
            extra={"final_url": final_url},
        )

    if analise_final.get("captcha_detectado", False):
        try:
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=provider_slug,
                status=STATUS_LOGIN_CAPTCHA_DETECTADO,
                mensagem="Captcha detectado após tentativa de login. Use o login assistido no navegador.",
                exige_login=True,
                captcha_detectado=True,
            )
        except Exception:
            pass

        return AuthResult(
            ok=False,
            status="captcha_pendente",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=True,
            login_url=login_url,
            products_url=products_url,
            message="Captcha detectado após tentativa de login.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "captcha")) or "captcha",
            session_ready=False,
            cookies_count=len(session.cookies),
            profile=supplier_profile_to_dict(profile),
            extra={"final_url": final_url},
        )

    if product_area_ok:
        persistencia = _persistir_sessao_requests(
            session=session,
            base_url=base_url,
            provider_slug=provider_slug,
            login_url=login_url,
            products_url=products_url or base_url,
            observacao="Sessão validada com sucesso via requests.",
        )

        state = load_auth_state()
        state.update(
            {
                "status": "autenticado",
                "provider_slug": provider_slug,
                "provider_name": provider_name or profile.nome,
                "requires_login": True,
                "captcha_detected": False,
                "login_url": login_url,
                "products_url": products_url or base_url,
                "auth_mode": _safe_str(getattr(profile, "auth_mode", "login")) or "login",
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
                "storage_state_path": _safe_str(persistencia.get("storage_state_path")),
                "metadata_path": _safe_str(persistencia.get("metadata_path")),
                "detected_whatsapp_code": False,
                "requires_whatsapp_code": bool(getattr(profile, "requires_whatsapp_code", False)),
                "source_kind": _safe_str(getattr(profile, "source_kind", "")),
            }
        )
        save_auth_state(state)

        try:
            salvar_status_login_em_sessao(
                base_url=base_url,
                fornecedor=provider_slug,
                status=STATUS_SESSAO_PRONTA,
                mensagem="Sessão autenticada com sucesso.",
                exige_login=False,
                captcha_detectado=False,
            )
        except Exception:
            pass

        return AuthResult(
            ok=True,
            status="autenticado",
            provider_slug=provider_slug,
            provider_name=provider_name or profile.nome,
            requires_login=True,
            captcha_detected=False,
            login_url=login_url,
            products_url=products_url or base_url,
            message="Sessão autenticada com sucesso.",
            auth_mode=_safe_str(getattr(profile, "auth_mode", "login")) or "login",
            session_ready=True,
            cookies_count=len(session.cookies),
            detected_product_area=True,
            detected_whatsapp_code=False,
            profile=supplier_profile_to_dict(profile),
            extra={
                "final_url": final_url,
                "storage_state_path": _safe_str(persistencia.get("storage_state_path")),
            },
        )

    try:
        salvar_status_login_em_sessao(
            base_url=base_url,
            fornecedor=provider_slug,
            status=STATUS_LOGIN_REQUERIDO,
            mensagem=(
                "O login foi enviado, mas a área de produtos não ficou acessível. "
                "Pode haver captcha, proteção extra, JS ou 2FA."
            ),
            exige_login=True,
            captcha_detectado=False,
        )
    except Exception:
        pass

    return AuthResult(
        ok=False,
        status="falha_autenticacao",
        provider_slug=provider_slug,
        provider_name=provider_name or profile.nome,
        requires_login=True,
        captcha_detected=False,
        login_url=login_url,
        products_url=products_url,
        message=(
            "O login foi enviado, mas a área de produtos não ficou acessível. "
            "Pode haver captcha, proteção extra, JS ou 2FA."
        ),
        auth_mode=_safe_str(getattr(profile, "auth_mode", "login")) or "login",
        session_ready=False,
        cookies_count=len(session.cookies),
        profile=supplier_profile_to_dict(profile),
        extra={"final_url": final_url},
    )


def get_auth_headers_and_cookies(base_url: str = "", fornecedor: str = "") -> dict[str, Any]:
    state = _merge_auth_state_with_session_manager(
        load_auth_state(),
        base_url=base_url,
        fornecedor=fornecedor,
    )

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
        "storage_state_path": _safe_str(state.get("storage_state_path")),
        "metadata_path": _safe_str(state.get("metadata_path")),
        "detected_whatsapp_code": bool(state.get("detected_whatsapp_code", False)),
        "requires_whatsapp_code": bool(state.get("requires_whatsapp_code", False)),
        "source_kind": _safe_str(state.get("source_kind", "")),
    }


def get_profile_for_url(url: str) -> SupplierProfile:
    profile, _saved_supplier = _resolve_saved_supplier_profile(url)
    return profile if profile else DEFAULT_PROFILE
