
from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx
import streamlit as st

from bling_app_zero.core.bling_token_store import BlingTokenStore

try:
    from bling_app_zero.core.bling_user_session import (
        clear_pending_oauth_user,
        get_current_user_key,
        get_current_user_label,
        get_pending_oauth_user_key,
        get_pending_oauth_user_label,
        set_current_user,
        set_pending_oauth_user,
    )
except Exception:
    def get_current_user_key() -> str:
        return str(st.session_state.get("bling_current_user_key", "default") or "default").strip() or "default"

    def get_current_user_label() -> str:
        return str(st.session_state.get("bling_current_user_label", "Operação padrão") or "Operação padrão").strip()

    def get_pending_oauth_user_key() -> str:
        return str(st.session_state.get("bling_oauth_pending_user_key", "") or "").strip()

    def get_pending_oauth_user_label() -> str:
        return str(st.session_state.get("bling_oauth_pending_user_label", "") or "").strip()

    def set_current_user(identifier: str, display_name: Optional[str] = None) -> str:
        user_key = str(identifier or "default").strip() or "default"
        st.session_state["bling_current_user_key"] = user_key
        st.session_state["bling_current_user_label"] = str(display_name or user_key).strip() or user_key
        return user_key

    def set_pending_oauth_user(identifier: str, display_name: Optional[str] = None) -> str:
        user_key = str(identifier or "default").strip() or "default"
        st.session_state["bling_oauth_pending_user_key"] = user_key
        st.session_state["bling_oauth_pending_user_label"] = str(display_name or user_key).strip() or user_key
        return user_key

    def clear_pending_oauth_user() -> None:
        st.session_state.pop("bling_oauth_pending_user_key", None)
        st.session_state.pop("bling_oauth_pending_user_label", None)


def _safe_str(value: Any) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, list):
            return str(value[0] if value else "").strip()
        return str(value).strip()
    except Exception:
        return ""


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_json_dict(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            return _safe_str(value[0] if value else "")
        return _safe_str(value)
    except Exception:
        return ""


def _clear_query_params(*keys: str) -> None:
    for key in keys:
        try:
            if key in st.query_params:
                del st.query_params[key]
        except Exception:
            pass


def _format_dt(value: str) -> str:
    texto = _safe_str(value)
    if not texto:
        return ""
    try:
        normalizado = texto.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalizado)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return texto


@dataclass
class BlingSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    revoke_url: str
    api_base_url: str
    token_store_path: str


class BlingAuthManager:
    def __init__(self, user_key: str = "default") -> None:
        resolved_user_key = _safe_str(user_key or "default") or "default"
        cfg = st.secrets.get("bling", {})

        self.user_key = resolved_user_key
        self.settings = BlingSettings(
            client_id=_safe_str(cfg.get("client_id")),
            client_secret=_safe_str(cfg.get("client_secret")),
            redirect_uri=_safe_str(cfg.get("redirect_uri")),
            authorize_url="https://www.bling.com.br/Api/v3/oauth/authorize",
            token_url="https://www.bling.com.br/Api/v3/oauth/token",
            revoke_url="https://www.bling.com.br/Api/v3/oauth/revoke",
            api_base_url=_safe_str(cfg.get("api_base_url")) or "https://api.bling.com.br/Api/v3",
            token_store_path=_safe_str(cfg.get("token_store_path")) or "bling_app_zero/output/bling_tokens.json",
        )
        self.store = BlingTokenStore(self.settings.token_store_path)
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass

    def __del__(self) -> None:
        self.close()

    def is_configured(self) -> bool:
        return bool(
            self.settings.client_id
            and self.settings.client_secret
            and self.settings.redirect_uri
        )

    def _basic_auth(self) -> str:
        raw = f"{self.settings.client_id}:{self.settings.client_secret}".encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('utf-8')}"

    def _headers_form(self) -> Dict[str, str]:
        return {
            "Authorization": self._basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

    def _headers_bearer(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "enable-jwt": "1",
        }

    def generate_auth_url(self, force_user_key: Optional[str] = None, user_label: Optional[str] = None) -> str:
        if not self.is_configured():
            st.session_state["_bling_debug_auth_error"] = "OAuth não configurado em secrets."
            return ""

        final_user_key = _safe_str(force_user_key) or self.user_key or "default"
        final_user_label = _safe_str(user_label) or final_user_key

        state = secrets.token_urlsafe(24)
        redirect_encoded = quote(self.settings.redirect_uri, safe="")

        st.session_state["_oauth_state"] = state
        st.session_state["_oauth_state_user_key"] = final_user_key
        st.session_state["_oauth_state_user_label"] = final_user_label

        set_pending_oauth_user(final_user_key, final_user_label)

        auth_url = (
            f"{self.settings.authorize_url}"
            f"?response_type=code"
            f"&client_id={self.settings.client_id}"
            f"&redirect_uri={redirect_encoded}"
            f"&state={state}"
        )

        st.session_state["_bling_debug_auth_url"] = auth_url
        st.session_state["_bling_debug_redirect_uri"] = self.settings.redirect_uri
        return auth_url

    def exchange_code_for_token(self, code: str) -> Tuple[bool, str]:
        code_limpo = _safe_str(code)
        if not code_limpo:
            return False, "Código OAuth ausente."

        if not self.is_configured():
            return False, "OAuth do Bling não configurado no secrets."

        data = {
            "grant_type": "authorization_code",
            "code": code_limpo,
            "redirect_uri": self.settings.redirect_uri,
        }

        try:
            response = self.client.post(
                self.settings.token_url,
                headers=self._headers_form(),
                data=data,
            )
            payload = _safe_json_dict(response.text)

            if response.status_code >= 400:
                return False, f"Erro {response.status_code} ao trocar code por token: {payload or response.text}"

            access_token = _safe_str(payload.get("access_token"))
            if not access_token:
                return False, f"Resposta sem access_token: {payload}"

            payload["created_at"] = int(time.time())
            self.store.save(self.user_key, payload)
            return True, "Token salvo com sucesso."
        except Exception as exc:
            return False, f"Falha ao trocar code por token: {exc}"

    def refresh_access_token(self) -> Tuple[bool, str]:
        atual = self.store.get(self.user_key) or {}
        refresh_token = _safe_str(atual.get("refresh_token"))
        if not refresh_token:
            return False, "Refresh token ausente."

        if not self.is_configured():
            return False, "OAuth do Bling não configurado no secrets."

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            response = self.client.post(
                self.settings.token_url,
                headers=self._headers_form(),
                data=data,
            )
            payload = _safe_json_dict(response.text)

            if response.status_code >= 400:
                return False, f"Erro {response.status_code} ao renovar token: {payload or response.text}"

            access_token = _safe_str(payload.get("access_token"))
            if not access_token:
                return False, f"Refresh sem access_token: {payload}"

            payload["created_at"] = int(time.time())
            self.store.save(self.user_key, payload)
            return True, "Token renovado com sucesso."
        except Exception as exc:
            return False, f"Falha ao renovar token: {exc}"

    def revoke_current_token(self) -> Tuple[bool, str]:
        atual = self.store.get(self.user_key) or {}
        access_token = _safe_str(atual.get("access_token"))
        refresh_token = _safe_str(atual.get("refresh_token"))
        token_para_revogar = refresh_token or access_token

        if not token_para_revogar:
            self.store.delete(self.user_key)
            return True, "Nenhum token salvo localmente."

        try:
            response = self.client.post(
                self.settings.revoke_url,
                headers=self._headers_form(),
                data={"token": token_para_revogar},
            )

            self.store.delete(self.user_key)

            if response.status_code >= 400:
                return False, f"Token local removido, mas a revogação remota retornou {response.status_code}: {response.text}"

            return True, "Conexão com o Bling removida."
        except Exception as exc:
            self.store.delete(self.user_key)
            return False, f"Token local removido, mas houve falha na revogação remota: {exc}"

    def get_token_data(self) -> Dict[str, Any]:
        data = self.store.get(self.user_key)
        return data if isinstance(data, dict) else {}

    def tem_token_valido(self) -> bool:
        data = self.get_token_data()
        if not data:
            return False
        return not self.store.is_expired(data)

    def get_valid_access_token(self) -> Tuple[bool, str]:
        data = self.get_token_data()
        access_token = _safe_str(data.get("access_token"))

        if access_token and not self.store.is_expired(data):
            return True, access_token

        if _safe_str(data.get("refresh_token")):
            ok, msg = self.refresh_access_token()
            if not ok:
                return False, msg
            refreshed = self.get_token_data()
            refreshed_token = _safe_str(refreshed.get("access_token"))
            if refreshed_token:
                return True, refreshed_token

        return False, "Nenhum token válido disponível."

    def _fetch_company_name(self, access_token: str) -> str:
        """
        Tenta enriquecer o nome da conta consultando um endpoint leve.
        Se falhar, mantém o fluxo funcionando sem quebrar.
        """
        urls_teste = [
            f"{self.settings.api_base_url}/situacao",
        ]

        for url in urls_teste:
            try:
                response = self.client.get(url, headers=self._headers_bearer(access_token))
                if response.status_code >= 400:
                    continue
                payload: Any
                try:
                    payload = response.json()
                except Exception:
                    payload = {}

                if isinstance(payload, dict):
                    for key in ("empresa", "nome", "razaoSocial", "fantasia"):
                        valor = _safe_str(payload.get(key))
                        if valor:
                            return valor
                    data = payload.get("data")
                    if isinstance(data, dict):
                        for key in ("empresa", "nome", "razaoSocial", "fantasia"):
                            valor = _safe_str(data.get(key))
                            if valor:
                                return valor
            except Exception:
                continue

        return ""

    def get_connection_status(self) -> Dict[str, Any]:
        token_data = self.get_token_data()
        connected = bool(token_data) and not self.store.is_expired(token_data)
        company_name = _safe_str(token_data.get("company_name"))

        if connected and not company_name:
            ok, token_or_msg = self.get_valid_access_token()
            if ok:
                nome = self._fetch_company_name(token_or_msg)
                if nome:
                    self.store.update_company_name(nome, self.user_key)
                    token_data = self.get_token_data()
                    company_name = _safe_str(token_data.get("company_name"))

        return {
            "connected": connected,
            "company_name": company_name or None,
            "last_auth_at": _format_dt(_safe_str(token_data.get("last_auth_at"))),
            "expires_at": _format_dt(_safe_str(token_data.get("expires_at"))),
            "user_key": self.user_key,
        }

    def handle_oauth_callback(self) -> Dict[str, str]:
        code = _query_param("code")
        state = _query_param("state")
        error = _query_param("error")
        error_description = _query_param("error_description")

        if not any([code, state, error, error_description]):
            return {"status": "idle", "message": ""}

        if error:
            _clear_query_params("code", "state", "error", "error_description")
            clear_pending_oauth_user()
            return {
                "status": "error",
                "message": f"{error}: {error_description or 'Autorização não concluída.'}",
            }

        expected_state = _safe_str(st.session_state.get("_oauth_state"))
        if expected_state and state and state != expected_state:
            _clear_query_params("code", "state", "error", "error_description")
            clear_pending_oauth_user()
            return {
                "status": "error",
                "message": "State OAuth inválido. Tente conectar novamente.",
            }

        ok, msg = self.exchange_code_for_token(code)

        _clear_query_params("code", "state", "error", "error_description")
        st.session_state.pop("_oauth_state", None)
        st.session_state.pop("_oauth_state_user_key", None)
        st.session_state.pop("_oauth_state_user_label", None)

        if ok:
            set_current_user(self.user_key, get_pending_oauth_user_label() or self.user_key)
            clear_pending_oauth_user()
            return {"status": "success", "message": "Conectado com sucesso ao Bling."}

        clear_pending_oauth_user()
        return {"status": "error", "message": msg}


def _resolver_user_key_global() -> str:
    qp_user = _query_param("bi")
    pending_user = get_pending_oauth_user_key()
    current_user = get_current_user_key()

    return _safe_str(qp_user) or _safe_str(pending_user) or _safe_str(current_user) or "default"


def _resolver_user_label_global() -> str:
    qp_user = _query_param("bi")
    pending_label = get_pending_oauth_user_label()
    current_label = get_current_user_label()

    return _safe_str(pending_label) or _safe_str(qp_user) or _safe_str(current_label) or "Operação padrão"


def processar_callback_se_existir() -> Dict[str, Any]:
    tem_callback = any(
        _query_param(chave)
        for chave in ("code", "state", "error", "error_description")
    )

    if not tem_callback:
        return {
            "executado": False,
            "ok": False,
            "mensagem": "",
        }

    user_key = _resolver_user_key_global()
    user_label = _resolver_user_label_global()
    set_current_user(user_key, user_label)

    auth = BlingAuthManager(user_key=user_key)
    resultado = auth.handle_oauth_callback()
    status = _safe_str(resultado.get("status")).lower()
    mensagem = _safe_str(resultado.get("message"))

    return {
        "executado": True,
        "ok": status == "success",
        "mensagem": mensagem,
        "status": status,
        "user_key": user_key,
    }


def usuario_conectado_bling(user_key: Optional[str] = None) -> bool:
    auth = BlingAuthManager(user_key=_safe_str(user_key) or _resolver_user_key_global())
    status = auth.get_connection_status()
    return bool(status.get("connected"))


def tem_token_valido(user_key: Optional[str] = None) -> bool:
    auth = BlingAuthManager(user_key=_safe_str(user_key) or _resolver_user_key_global())
    return auth.tem_token_valido()


def obter_resumo_conexao(user_key: Optional[str] = None) -> Dict[str, Any]:
    auth = BlingAuthManager(user_key=_safe_str(user_key) or _resolver_user_key_global())
    status = auth.get_connection_status()
    conectado = bool(status.get("connected"))

    return {
        "conectado": conectado,
        "status": "Conectado" if conectado else "Desconectado",
        "company_name": status.get("company_name"),
        "last_auth_at": status.get("last_auth_at"),
        "expires_at": status.get("expires_at"),
        "user_key": status.get("user_key"),
    }


def render_conectar_bling(user_key: Optional[str] = None, titulo: str = "Conectar com Bling") -> None:
    final_user_key = _safe_str(user_key) or _resolver_user_key_global() or "default"
    final_user_label = _resolver_user_label_global() or final_user_key

    auth = BlingAuthManager(user_key=final_user_key)
    resumo = auth.get_connection_status()
    conectado = bool(resumo.get("connected"))

    if not auth.is_configured():
        st.warning("Configure `client_id`, `client_secret` e `redirect_uri` em `.streamlit/secrets.toml`.")
        return

    if conectado:
        st.success("✅ Conectado ao Bling")
        if resumo.get("company_name"):
            st.caption(f"Conta: {resumo['company_name']}")
        if resumo.get("last_auth_at"):
            st.caption(f"Última autenticação: {resumo['last_auth_at']}")
        if resumo.get("expires_at"):
            st.caption(f"Expira em: {resumo['expires_at']}")

        if st.button("Desconectar do Bling", key=f"btn_desconectar_bling_{final_user_key}", use_container_width=True):
            ok, msg = auth.revoke_current_token()
            if ok:
                st.success(msg)
            else:
                st.warning(msg)
            st.rerun()
        return

    auth_url = auth.generate_auth_url(force_user_key=final_user_key, user_label=final_user_label)
    if not auth_url:
        st.error("Não foi possível gerar a URL de autorização do Bling.")
        return

    st.markdown(
        f"""
        <a href="{auth_url}" target="_self" style="text-decoration:none;">
            <div style="
                display:flex;
                align-items:center;
                justify-content:center;
                width:100%;
                padding:0.75rem 1rem;
                border-radius:0.75rem;
                background:#16a34a;
                color:white;
                font-weight:700;
                text-align:center;
                margin:0.25rem 0 0.5rem 0;
            ">
                🔗 {titulo}
            </div>
        </a>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Ao clicar, o app redireciona para o Bling, recebe o `code` no retorno e salva o token automaticamente.")
