
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


STATUS_PUBLICO = "publico"
STATUS_LOGIN_REQUERIDO = "login_required"
STATUS_LOGIN_CAPTCHA_DETECTADO = "login_captcha_detectado"
STATUS_SESSAO_PRONTA = "session_ready"


OUTPUT_DIR = Path("bling_app_zero/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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


def _slug_fornecedor(base_url: str, fornecedor: str = "") -> str:
    slug = _safe_str(fornecedor)
    if slug:
        return re.sub(r"[^a-zA-Z0-9_\-]+", "_", slug).strip("_").lower() or "fornecedor"

    host = _hostname(base_url)
    if host:
        slug_host = host.replace("www.", "")
        slug_host = re.sub(r"[^a-zA-Z0-9_\-]+", "_", slug_host).strip("_").lower()
        if slug_host:
            return slug_host

    bruto = re.sub(r"[^a-zA-Z0-9_\-]+", "_", _safe_str(base_url)).strip("_").lower()
    return bruto or "fornecedor"


def _arquivo_storage_state(base_url: str, fornecedor: str = "") -> Path:
    slug = _slug_fornecedor(base_url, fornecedor)
    return OUTPUT_DIR / f"site_storage_state_{slug}.json"


def _arquivo_metadata(base_url: str, fornecedor: str = "") -> Path:
    slug = _slug_fornecedor(base_url, fornecedor)
    return OUTPUT_DIR / f"site_session_metadata_{slug}.json"


def _ler_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _gravar_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def detectar_login_captcha(html: str, url_atual: str = "") -> dict[str, Any]:
    page = _safe_str(html).lower()
    final_url = _safe_str(url_atual).lower()

    sinais_login = [
        "login",
        "fazer login",
        "faça login",
        "entrar",
        "senha",
        "password",
        "autenticacao",
        "autenticação",
        "minha conta",
        "acessar conta",
        "acesse sua conta",
        "insira seus dados",
    ]
    sinais_captcha = [
        "captcha",
        "g-recaptcha",
        "grecaptcha",
        "hcaptcha",
        "cloudflare",
        "verify you are human",
        "não sou um robô",
        "nao sou um robo",
    ]

    url_sugere_login = any(
        token in final_url
        for token in ["/login", "/entrar", "/auth", "/account", "/conta"]
    )

    html_sugere_login = any(token in page for token in sinais_login)
    captcha_detectado = any(token in page for token in sinais_captcha)

    has_password = 'type="password"' in page or 'name="password"' in page or "senha" in page
    has_email = (
        'type="email"' in page
        or 'name="email"' in page
        or 'name="login"' in page
        or 'name="username"' in page
        or "usuario" in page
        or "usuário" in page
        or "e-mail" in page
    )
    form_login_detectado = bool(has_password and (has_email or html_sugere_login))
    exige_login = bool(url_sugere_login or html_sugere_login or form_login_detectado)

    if exige_login and captcha_detectado:
        status = STATUS_LOGIN_CAPTCHA_DETECTADO
        mensagem = "Captcha detectado. Login assistido necessário."
    elif exige_login:
        status = STATUS_LOGIN_REQUERIDO
        mensagem = "Login detectado. Sessão autenticada necessária."
    else:
        status = STATUS_PUBLICO
        mensagem = "Nenhum bloqueio de autenticação detectado."

    motivos: list[str] = []
    if url_sugere_login:
        motivos.append("url_de_login")
    if html_sugere_login:
        motivos.append("texto_de_login")
    if form_login_detectado:
        motivos.append("formulario_de_login")
    if captcha_detectado:
        motivos.append("captcha")

    return {
        "exige_login": exige_login,
        "captcha_detectado": captcha_detectado,
        "login_detectado": exige_login,
        "status": status,
        "mensagem": mensagem,
        "motivos": motivos,
    }


def salvar_status_login_em_sessao(
    *,
    base_url: str,
    status: str,
    mensagem: str = "",
    exige_login: bool = False,
    captcha_detectado: bool = False,
    fornecedor: str = "",
) -> dict[str, Any]:
    storage_path = _arquivo_storage_state(base_url, fornecedor)
    metadata_path = _arquivo_metadata(base_url, fornecedor)

    metadata_existente = _ler_json(metadata_path)

    metadata = {
        **metadata_existente,
        "base_url": _normalize_url(base_url),
        "fornecedor": _slug_fornecedor(base_url, fornecedor),
        "status": _safe_str(status) or STATUS_PUBLICO,
        "mensagem": _safe_str(mensagem),
        "exige_login": bool(exige_login),
        "captcha_detectado": bool(captcha_detectado),
        "session_ready": bool(metadata_existente.get("session_ready", False)),
        "storage_state_path": str(storage_path),
        "metadata_path": str(metadata_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    _gravar_json(metadata_path, metadata)
    return metadata


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
    storage_path = _arquivo_storage_state(base_url, fornecedor)
    metadata_path = _arquivo_metadata(base_url, fornecedor)

    state_limpo = storage_state if isinstance(storage_state, dict) else {}
    cookies = state_limpo.get("cookies", [])
    cookies_count = len(cookies) if isinstance(cookies, list) else 0

    _gravar_json(storage_path, state_limpo)

    metadata_existente = _ler_json(metadata_path)
    metadata = {
        **metadata_existente,
        "base_url": _normalize_url(base_url),
        "fornecedor": _slug_fornecedor(base_url, fornecedor),
        "status": _safe_str(status) or STATUS_SESSAO_PRONTA,
        "mensagem": _safe_str(observacao) or "Sessão autenticada salva com sucesso.",
        "exige_login": False,
        "captcha_detectado": False,
        "session_ready": cookies_count > 0,
        "cookies_count": cookies_count,
        "products_url": _normalize_url(products_url) or _normalize_url(base_url),
        "login_url": _normalize_url(login_url),
        "storage_state_path": str(storage_path),
        "metadata_path": str(metadata_path),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _gravar_json(metadata_path, metadata)

    return {
        "ok": True,
        "storage_state_path": str(storage_path),
        "metadata_path": str(metadata_path),
        "cookies_count": cookies_count,
        "session_ready": cookies_count > 0,
    }


def montar_auth_context(base_url: str, fornecedor: str = "") -> dict[str, Any]:
    storage_path = _arquivo_storage_state(base_url, fornecedor)
    metadata_path = _arquivo_metadata(base_url, fornecedor)

    storage_state = _ler_json(storage_path)
    metadata = _ler_json(metadata_path)

    cookies = storage_state.get("cookies", []) if isinstance(storage_state, dict) else []
    headers = metadata.get("headers", {}) if isinstance(metadata, dict) else {}
    session_ready = bool(isinstance(cookies, list) and len(cookies) > 0)

    return {
        "base_url": _normalize_url(base_url),
        "fornecedor_slug": _slug_fornecedor(base_url, fornecedor),
        "cookies": cookies if isinstance(cookies, list) else [],
        "headers": headers if isinstance(headers, dict) else {},
        "cookies_count": len(cookies) if isinstance(cookies, list) else 0,
        "products_url": _safe_str(metadata.get("products_url")) or _normalize_url(base_url),
        "login_url": _safe_str(metadata.get("login_url")),
        "status": _safe_str(metadata.get("status")) or (STATUS_SESSAO_PRONTA if session_ready else STATUS_PUBLICO),
        "mensagem": _safe_str(metadata.get("mensagem")),
        "storage_state_path": str(storage_path),
        "metadata_path": str(metadata_path),
        "session_ready": session_ready,
        "auth_http_ok": session_ready,
        "manual_mode": False,
    }


def sessao_esta_pronta(base_url: str, fornecedor: str = "") -> bool:
    contexto = montar_auth_context(base_url=base_url, fornecedor=fornecedor)
    return bool(contexto.get("session_ready", False))


def iniciar_login_assistido(url_login: str) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "aguardando_login_manual",
        "url": _normalize_url(url_login),
        "mensagem": "Abra o login no navegador, conclua captcha/login e depois salve a sessão autenticada.",
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
    storage_state = {
        "cookies": cookies if isinstance(cookies, list) else [],
        "origins": [],
    }

    persistencia = salvar_storage_state(
        base_url=base_url,
        fornecedor=fornecedor,
        products_url=products_url,
        login_url=login_url,
        storage_state=storage_state,
        status=STATUS_SESSAO_PRONTA,
        observacao=observacao or "Sessão salva após login assistido.",
    )

    metadata_path = _arquivo_metadata(base_url, fornecedor)
    metadata = _ler_json(metadata_path)
    metadata["headers"] = headers if isinstance(headers, dict) else {}
    _gravar_json(metadata_path, metadata)

    return {
        "ok": True,
        "status": STATUS_SESSAO_PRONTA,
        "mensagem": "Sessão autenticada salva com sucesso.",
        **persistencia,
    }


def limpar_sessao(base_url: str, fornecedor: str = "") -> None:
    storage_path = _arquivo_storage_state(base_url, fornecedor)
    metadata_path = _arquivo_metadata(base_url, fornecedor)

    if storage_path.exists():
        storage_path.unlink()

    if metadata_path.exists():
        metadata_path.unlink()


def get_session_debug(base_url: str = "", fornecedor: str = "") -> dict[str, Any]:
    contexto = montar_auth_context(base_url=base_url, fornecedor=fornecedor) if base_url else {}
    return {
        "existe_sessao": bool(contexto),
        "session_ready": bool(contexto.get("session_ready", False)) if contexto else False,
        "cookies": int(contexto.get("cookies_count", 0) or 0) if contexto else 0,
        "status": _safe_str(contexto.get("status")) if contexto else "",
        "storage_state_path": _safe_str(contexto.get("storage_state_path")) if contexto else "",
        "metadata_path": _safe_str(contexto.get("metadata_path")) if contexto else "",
    }
