
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

BLING_AUTHORIZE_URL = "https://www.bling.com.br/Api/v3/oauth/authorize"
BLING_TOKEN_URL = "https://www.bling.com.br/Api/v3/oauth/token"
BLING_REVOKE_URL = "https://www.bling.com.br/Api/v3/oauth/revoke"

OUTPUT_DIR = Path("bling_app_zero/output")
TOKENS_FILE = OUTPUT_DIR / "bling_tokens.json"
STATE_FILE = OUTPUT_DIR / "oauth_state.json"

DEFAULT_SCOPES = [
    "produtos",
    "estoques",
    "contatos",
]


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    scope: str
    created_at: str
    expires_at: str
    raw: dict[str, Any]

    def is_expired(self, safety_seconds: int = 60) -> bool:
        try:
            dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) >= (dt - timedelta(seconds=safety_seconds))
        except Exception:
            return True


# ============================================================
# HELPERS GERAIS
# ============================================================

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalizar_texto(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat"}:
        return ""
    return texto


def _safe_json_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _safe_json_save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_user_key(valor: str) -> str:
    texto = _normalizar_texto(valor)
    if not texto:
        texto = "default"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:32]


def _headers_json(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "enable-jwt": "1",
    }
    if extra:
        headers.update(extra)
    return headers


# ============================================================
# SECRETS / PARAMS
# ============================================================

def _get_secret(nome: str, default: str = "") -> str:
    try:
        valor = st.secrets.get(nome, default)
        return _normalizar_texto(valor)
    except Exception:
        return default


def get_client_id() -> str:
    for chave in [
        "BLING_CLIENT_ID",
        "bling_client_id",
        "CLIENT_ID_BLING",
        "client_id_bling",
    ]:
        valor = _get_secret(chave)
        if valor:
            return valor
    return ""


def get_client_secret() -> str:
    for chave in [
        "BLING_CLIENT_SECRET",
        "bling_client_secret",
        "CLIENT_SECRET_BLING",
        "client_secret_bling",
    ]:
        valor = _get_secret(chave)
        if valor:
            return valor
    return ""


def get_redirect_uri() -> str:
    for chave in [
        "BLING_REDIRECT_URI",
        "bling_redirect_uri",
        "REDIRECT_URI_BLING",
        "redirect_uri_bling",
    ]:
        valor = _get_secret(chave)
        if valor:
            return valor

    try:
        qp = st.query_params
        origin = _normalizar_texto(qp.get("app_base_url", ""))
        if origin:
            return origin
    except Exception:
        pass

    return ""


def get_scope() -> str:
    for chave in [
        "BLING_SCOPE",
        "bling_scope",
    ]:
        valor = _get_secret(chave)
        if valor:
            return valor

    return " ".join(DEFAULT_SCOPES)


def credenciais_configuradas() -> bool:
    return bool(get_client_id() and get_client_secret() and get_redirect_uri())


# ============================================================
# USER KEY / STORAGE
# ============================================================

def get_user_key() -> str:
    """
    Chave por usuário/sessão.
    Prioridade:
    1) query param bi
    2) session_state
    3) gera uma nova
    """
    try:
        bi = _normalizar_texto(st.query_params.get("bi", ""))
        if bi:
            st.session_state["bling_user_key"] = _hash_user_key(bi)
            return st.session_state["bling_user_key"]
    except Exception:
        pass

    user_key = _normalizar_texto(st.session_state.get("bling_user_key", ""))
    if user_key:
        return user_key

    novo = _hash_user_key(secrets.token_urlsafe(24))
    st.session_state["bling_user_key"] = novo
    return novo


def _load_all_tokens() -> dict[str, Any]:
    return _safe_json_load(TOKENS_FILE)


def _save_all_tokens(data: dict[str, Any]) -> None:
    _safe_json_save(TOKENS_FILE, data)


def _load_all_states() -> dict[str, Any]:
    return _safe_json_load(STATE_FILE)


def _save_all_states(data: dict[str, Any]) -> None:
    _safe_json_save(STATE_FILE, data)


def _get_user_tokens_raw() -> dict[str, Any]:
    all_tokens = _load_all_tokens()
    return all_tokens.get(get_user_key(), {}) or {}


def _save_user_tokens_raw(data: dict[str, Any]) -> None:
    all_tokens = _load_all_tokens()
    all_tokens[get_user_key()] = data
    _save_all_tokens(all_tokens)


def _clear_user_tokens() -> None:
    all_tokens = _load_all_tokens()
    all_tokens.pop(get_user_key(), None)
    _save_all_tokens(all_tokens)


def _save_oauth_state(state: str, payload: dict[str, Any]) -> None:
    all_states = _load_all_states()
    all_states[state] = payload
    _save_all_states(all_states)


def _pop_oauth_state(state: str) -> dict[str, Any]:
    all_states = _load_all_states()
    payload = all_states.pop(state, {})
    _save_all_states(all_states)
    return payload or {}


# ============================================================
# TOKEN MODEL
# ============================================================

def _bundle_from_token_response(data: dict[str, Any]) -> TokenBundle:
    expires_in = int(data.get("expires_in", 0) or 0)
    created_at = _now_utc()
    expires_at = created_at + timedelta(seconds=max(expires_in, 0))

    return TokenBundle(
        access_token=_normalizar_texto(data.get("access_token")),
        refresh_token=_normalizar_texto(data.get("refresh_token")),
        expires_in=expires_in,
        token_type=_normalizar_texto(data.get("token_type") or "Bearer"),
        scope=_normalizar_texto(data.get("scope")),
        created_at=_iso_utc(created_at),
        expires_at=_iso_utc(expires_at),
        raw=data,
    )


def _bundle_to_dict(bundle: TokenBundle) -> dict[str, Any]:
    return {
        "access_token": bundle.access_token,
        "refresh_token": bundle.refresh_token,
        "expires_in": bundle.expires_in,
        "token_type": bundle.token_type,
        "scope": bundle.scope,
        "created_at": bundle.created_at,
        "expires_at": bundle.expires_at,
        "raw": bundle.raw,
    }


def get_token_bundle() -> TokenBundle | None:
    raw = _get_user_tokens_raw()
    if not raw:
        return None

    try:
        return TokenBundle(
            access_token=_normalizar_texto(raw.get("access_token")),
            refresh_token=_normalizar_texto(raw.get("refresh_token")),
            expires_in=int(raw.get("expires_in", 0) or 0),
            token_type=_normalizar_texto(raw.get("token_type") or "Bearer"),
            scope=_normalizar_texto(raw.get("scope")),
            created_at=_normalizar_texto(raw.get("created_at")),
            expires_at=_normalizar_texto(raw.get("expires_at")),
            raw=raw.get("raw", {}) or {},
        )
    except Exception:
        return None


def save_token_bundle(bundle: TokenBundle) -> None:
    _save_user_tokens_raw(_bundle_to_dict(bundle))
    st.session_state["bling_conectado"] = True
    st.session_state["bling_status_texto"] = "Conectado"


# ============================================================
# AUTH HEADER / REQUESTS
# ============================================================

def _basic_auth_header() -> str:
    client_id = get_client_id()
    client_secret = get_client_secret()
    token = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"


def _post_token(data: dict[str, Any]) -> dict[str, Any]:
    if not credenciais_configuradas():
        raise RuntimeError("Credenciais do Bling não configuradas em st.secrets.")

    response = requests.post(
        BLING_TOKEN_URL,
        headers=_headers_json({"Authorization": _basic_auth_header()}),
        data=data,
        timeout=30,
    )

    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text}

    if response.status_code >= 400:
        raise RuntimeError(f"Falha ao obter token no Bling: {payload}")

    return payload


# ============================================================
# OAUTH FLOW
# ============================================================

def gerar_state() -> str:
    state = secrets.token_urlsafe(32)
    _save_oauth_state(
        state,
        {
            "user_key": get_user_key(),
            "created_at": _iso_utc(_now_utc()),
            "redirect_uri": get_redirect_uri(),
        },
    )
    return state


def gerar_link_autorizacao() -> str:
    if not credenciais_configuradas():
        raise RuntimeError("Client ID, Client Secret ou Redirect URI do Bling não configurados.")

    params = {
        "response_type": "code",
        "client_id": get_client_id(),
        "redirect_uri": get_redirect_uri(),
        "state": gerar_state(),
    }

    scope = get_scope()
    if scope:
        params["scope"] = scope

    return f"{BLING_AUTHORIZE_URL}?{urlencode(params)}"


def iniciar_oauth_bling() -> str:
    """
    Retorna a URL de autorização e salva no session_state.
    """
    link = gerar_link_autorizacao()
    st.session_state["bling_auth_url"] = link
    return link


def trocar_code_por_token(code: str) -> TokenBundle:
    code = _normalizar_texto(code)
    if not code:
        raise RuntimeError("Authorization code do Bling não informado.")

    payload = _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": get_redirect_uri(),
        }
    )

    bundle = _bundle_from_token_response(payload)
    if not bundle.access_token:
        raise RuntimeError(f"Resposta de token inválida do Bling: {payload}")

    save_token_bundle(bundle)
    return bundle


def refresh_access_token(refresh_token: str | None = None) -> TokenBundle:
    current = get_token_bundle()
    refresh = _normalizar_texto(refresh_token) or _normalizar_texto(
        current.refresh_token if current else ""
    )

    if not refresh:
        raise RuntimeError("Refresh token do Bling não encontrado.")

    payload = _post_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
        }
    )

    bundle = _bundle_from_token_response(payload)
    if not bundle.access_token:
        raise RuntimeError(f"Resposta de refresh inválida do Bling: {payload}")

    save_token_bundle(bundle)
    return bundle


def revoke_token(token: str | None = None) -> dict[str, Any]:
    bundle = get_token_bundle()
    token_alvo = _normalizar_texto(token) or _normalizar_texto(
        bundle.refresh_token if bundle else ""
    ) or _normalizar_texto(bundle.access_token if bundle else "")

    if not token_alvo:
        raise RuntimeError("Nenhum token disponível para revogar.")

    response = requests.post(
        BLING_REVOKE_URL,
        headers=_headers_json({"Authorization": _basic_auth_header()}),
        data={"token": token_alvo},
        timeout=30,
    )

    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": response.text}

    if response.status_code >= 400:
        raise RuntimeError(f"Falha ao revogar token no Bling: {payload}")

    _clear_user_tokens()
    st.session_state["bling_conectado"] = False
    st.session_state["bling_status_texto"] = "Desconectado"
    return payload


# ============================================================
# CALLBACK / SESSÃO
# ============================================================

def processar_callback_se_existir() -> dict[str, Any]:
    """
    Lê query params do retorno OAuth e conclui a autenticação.
    Pode ser chamada no app.py a cada carregamento.
    """
    try:
        qp = st.query_params
    except Exception:
        return {"ok": False, "executado": False, "mensagem": "query_params indisponível"}

    code = _normalizar_texto(qp.get("code", ""))
    state = _normalizar_texto(qp.get("state", ""))
    error = _normalizar_texto(qp.get("error", ""))
    error_description = _normalizar_texto(qp.get("error_description", ""))

    if error:
        return {
            "ok": False,
            "executado": True,
            "mensagem": f"Erro retornado pelo Bling: {error} {error_description}".strip(),
        }

    if not code:
        return {"ok": False, "executado": False, "mensagem": "Sem code na URL"}

    if not state:
        return {"ok": False, "executado": True, "mensagem": "State do OAuth ausente."}

    saved = _pop_oauth_state(state)
    if not saved:
        return {"ok": False, "executado": True, "mensagem": "State do OAuth inválido ou expirado."}

    try:
        bundle = trocar_code_por_token(code)
    except Exception as exc:
        return {"ok": False, "executado": True, "mensagem": str(exc)}

    # limpa code/state da URL, mas preserva etapa/bi se existirem
    try:
        etapa = _normalizar_texto(qp.get("etapa", "origem"))
        bi = _normalizar_texto(qp.get("bi", ""))
        novos = {"etapa": etapa}
        if bi:
            novos["bi"] = bi
        st.query_params.clear()
        for k, v in novos.items():
            st.query_params[k] = v
    except Exception:
        pass

    return {
        "ok": True,
        "executado": True,
        "mensagem": "Conexão com Bling concluída com sucesso.",
        "expires_at": bundle.expires_at,
    }


def usuario_conectado_bling() -> bool:
    bundle = get_token_bundle()
    return bool(bundle and bundle.access_token)


def tem_token_valido() -> bool:
    bundle = get_token_bundle()
    if not bundle:
        return False

    if bundle.is_expired():
        try:
            refresh_access_token(bundle.refresh_token)
            return True
        except Exception:
            return False

    return True


def obter_access_token() -> str:
    bundle = get_token_bundle()
    if not bundle:
        return ""

    if bundle.is_expired():
        try:
            bundle = refresh_access_token(bundle.refresh_token)
        except Exception:
            return ""

    return bundle.access_token


def get_access_token() -> str:
    return obter_access_token()


def get_valid_access_token() -> str:
    return obter_access_token()


def access_token_valido() -> str:
    return obter_access_token()


# ============================================================
# HELPERS DE UI
# ============================================================

def render_conectar_bling() -> None:
    """
    Render simples para usar em painéis como preview_final.py.
    """
    if not credenciais_configuradas():
        st.error("Credenciais do Bling não configuradas em st.secrets.")
        return

    if usuario_conectado_bling() and tem_token_valido():
        st.success("Conta Bling conectada.")
        if st.button("Desconectar do Bling", use_container_width=True, key="btn_desconectar_bling"):
            try:
                revoke_token()
                st.success("Conexão com o Bling removida.")
                st.rerun()
            except Exception as exc:
                st.error(f"Falha ao desconectar do Bling: {exc}")
        return

    try:
        link = iniciar_oauth_bling()
    except Exception as exc:
        st.error(f"Falha ao preparar OAuth do Bling: {exc}")
        return

    st.link_button("🔗 Conectar com Bling", link, use_container_width=True)


def obter_resumo_conexao() -> dict[str, Any]:
    bundle = get_token_bundle()
    if not bundle:
        return {
            "conectado": False,
            "status": "Desconectado",
            "expires_at": "",
            "scope": "",
        }

    return {
        "conectado": tem_token_valido(),
        "status": "Conectado" if tem_token_valido() else "Token expirado",
        "expires_at": bundle.expires_at,
        "scope": bundle.scope,
  }
