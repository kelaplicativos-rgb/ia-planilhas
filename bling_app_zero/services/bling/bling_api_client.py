from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import requests

try:
    import streamlit as st
except Exception:
    st = None

try:
    from bling_app_zero.services.bling.bling_token_store import BlingTokenStore
except Exception:
    from bling_app_zero.core.bling_token_store import BlingTokenStore


class BlingAPIClient:
    def __init__(self, user_key: str = "default") -> None:
        self.user_key = self._resolver_user_key(user_key)
        self.settings = self._load_settings()
        self.store = BlingTokenStore(self.settings["token_store_path"])
        self.access_token = ""
        self._refresh_token_runtime(force=False)

    # =========================
    # SETTINGS
    # =========================
    @staticmethod
    def _safe_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    def _resolver_user_key(self, fallback: str = "default") -> str:
        try:
            if st is not None:
                qp_user = st.query_params.get("bi")
                if isinstance(qp_user, list):
                    qp_user = qp_user[0] if qp_user else ""
                qp_user = self._safe_str(qp_user)
                if qp_user:
                    return qp_user
        except Exception:
            pass
        return self._safe_str(fallback) or "default"

    def _load_settings(self) -> Dict[str, str]:
        cfg = {}
        try:
            if st is not None:
                cfg = st.secrets.get("bling", {})
        except Exception:
            cfg = {}

        api_base_url = self._safe_str(cfg.get("api_base_url", ""))
        if not api_base_url:
            api_base_url = "https://api.bling.com.br/Api/v3"

        token_url = self._safe_str(cfg.get("token_url", ""))
        if not token_url:
            token_url = "https://www.bling.com.br/Api/v3/oauth/token"

        token_store_path = self._safe_str(cfg.get("token_store_path", ""))
        if not token_store_path:
            token_store_path = "bling_app_zero/output/bling_tokens.json"

        return {
            "client_id": self._safe_str(cfg.get("client_id", "")),
            "client_secret": self._safe_str(cfg.get("client_secret", "")),
            "token_url": token_url,
            "api_base_url": api_base_url.rstrip("/"),
            "token_store_path": token_store_path,
        }

    # =========================
    # TOKEN
    # =========================
    def _basic_auth_header(self) -> str:
        raw = f'{self.settings["client_id"]}:{self.settings["client_secret"]}'.encode("utf-8")
        return f"Basic {base64.b64encode(raw).decode('utf-8')}"

    def _legacy_token_fallback(self) -> str:
        token = ""
        try:
            if st is not None:
                token = (
                    st.session_state.get("bling_access_token")
                    or st.secrets.get("BLING_ACCESS_TOKEN", "")
                    or ""
                )
        except Exception:
            token = ""

        if not token:
            token = os.getenv("BLING_ACCESS_TOKEN", "") or ""

        return self._safe_str(token)

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        texto = self._safe_str(value)
        if not texto:
            return None

        try:
            texto = texto.replace("Z", "+00:00")
            dt = datetime.fromisoformat(texto)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    def _token_expirado(self, token_data: Optional[Dict[str, Any]], leeway_seconds: int = 120) -> bool:
        if not isinstance(token_data, dict) or not token_data:
            return True

        expires_at = self._parse_datetime(token_data.get("expires_at"))
        if expires_at is None:
            expires_in = token_data.get("expires_in")
            last_auth_at = self._parse_datetime(token_data.get("last_auth_at"))
            try:
                expires_in = int(expires_in or 0)
            except Exception:
                expires_in = 0

            if last_auth_at is None or expires_in <= 0:
                return True

            expires_at = last_auth_at + timedelta(seconds=expires_in)

        now = datetime.now(timezone.utc)
        return now >= (expires_at - timedelta(seconds=leeway_seconds))

    def _save_refreshed_payload(
        self,
        payload: Dict[str, Any],
        atual: Optional[Dict[str, Any]] = None,
    ) -> None:
        atual = atual or {}
        merged = dict(payload)

        if not merged.get("refresh_token") and atual.get("refresh_token"):
            merged["refresh_token"] = atual.get("refresh_token")

        company_name = self._safe_str(atual.get("company_name")) or None
        self.store.save_token_payload(
            merged,
            user_key=self.user_key,
            company_name=company_name,
        )

    def _refresh_access_token(self) -> Tuple[bool, str]:
        atual = self.store.get(self.user_key) or {}
        refresh_token = self._safe_str(atual.get("refresh_token"))

        if not refresh_token:
            return False, "Refresh token ausente."

        client_id = self._safe_str(self.settings.get("client_id"))
        client_secret = self._safe_str(self.settings.get("client_secret"))
        token_url = self._safe_str(self.settings.get("token_url"))

        if not client_id or not client_secret or not token_url:
            return False, "Configuração OAuth do Bling incompleta."

        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "enable-jwt": "1",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        try:
            response = requests.post(
                token_url,
                headers=headers,
                data=data,
                timeout=30,
            )

            try:
                payload = response.json()
            except Exception:
                payload = {"raw": (response.text or "").strip()}

            if response.status_code >= 400:
                return False, f"Falha ao renovar token: {payload}"

            if not isinstance(payload, dict):
                return False, "Resposta inválida no refresh do token."

            self._save_refreshed_payload(payload, atual=atual)
            novo = self.store.get(self.user_key) or {}
            self.access_token = self._safe_str(novo.get("access_token"))
            return (True, "Token renovado com sucesso.") if self.access_token else (
                False,
                "Token renovado, mas access_token não foi salvo.",
            )
        except requests.RequestException as e:
            return False, f"Erro de conexão ao renovar token: {e}"
        except Exception as e:
            return False, f"Erro ao renovar token: {e}"

    def _get_token(self, force_refresh: bool = False) -> str:
        atual = self.store.get(self.user_key) or {}

        if force_refresh:
            ok, _ = self._refresh_access_token()
            if ok:
                atual = self.store.get(self.user_key) or {}

        token = self._safe_str(atual.get("access_token"))
        if token and not self._token_expirado(atual):
            return token

        if token and self._token_expirado(atual):
            ok, _ = self._refresh_access_token()
            if ok:
                refreshed = self.store.get(self.user_key) or {}
                refreshed_token = self._safe_str(refreshed.get("access_token"))
                if refreshed_token:
                    return refreshed_token

        return self._legacy_token_fallback()

    def _refresh_token_runtime(self, force: bool = False) -> None:
        novo = self._get_token(force_refresh=force)
        if novo and novo != self.access_token:
            self.access_token = novo

    def _headers(self) -> Dict[str, str]:
        self._refresh_token_runtime(force=False)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _validar_token(self) -> Tuple[bool, Dict[str, Any]]:
        self._refresh_token_runtime(force=False)

        if not self.access_token:
            return False, {
                "status": 401,
                "erro": "Token do Bling não configurado.",
            }

        return True, {}

    # =========================
    # HELPERS
    # =========================
    def _normalizar_endpoint(self, endpoint: str) -> str:
        endpoint = self._safe_str(endpoint)
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return endpoint

    def _parse_response(self, response: requests.Response) -> Any:
        try:
            return response.json()
        except Exception:
            texto = (response.text or "").strip()
            return {"raw": texto}

    # =========================
    # REQUEST BASE (PRO)
    # =========================
    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any]:
        ok_token, erro_token = self._validar_token()
        if not ok_token:
            return False, erro_token

        url = f'{self.settings["api_base_url"]}{self._normalizar_endpoint(endpoint)}'

        for tentativa in range(2):
            try:
                response = requests.request(
                    method=self._safe_str(method or "GET").upper(),
                    url=url,
                    headers=self._headers(),
                    json=json,
                    params=params,
                    timeout=30,
                )
                data = self._parse_response(response)

                if response.status_code in (200, 201, 202, 204):
                    return True, {
                        "status": response.status_code,
                        "data": data,
                    }

                if response.status_code == 401 and tentativa == 0:
                    self._refresh_token_runtime(force=True)
                    continue

                return False, {
                    "status": response.status_code,
                    "erro": data,
                    "url": url,
                }

            except requests.Timeout:
                if tentativa == 0:
                    continue
                return False, {
                    "status": 408,
                    "erro": "Timeout na API do Bling",
                    "url": url,
                }

            except requests.RequestException as e:
                if tentativa == 0:
                    continue
                return False, {
                    "status": 500,
                    "erro": f"Erro de conexão: {str(e)}",
                    "url": url,
                }

            except Exception as e:
                return False, {
                    "status": 500,
                    "erro": str(e),
                    "url": url,
                }

        return False, {
            "status": 500,
            "erro": "Falha desconhecida",
            "url": url,
        }

    # =========================
    # PRODUTO
    # =========================
    def upsert_product(self, data: Dict[str, Any]) -> Tuple[bool, Any]:
        codigo = self._safe_str(data.get("codigo") or data.get("sku"))
        nome = self._safe_str(data.get("nome") or data.get("descricao"))

        if not codigo:
            return False, {"erro": "Produto sem código"}

        if not nome:
            nome = codigo

        preco = data.get("preco")
        if preco is None:
            preco = data.get("preco_venda")

        try:
            preco = float(preco) if preco is not None and str(preco).strip() != "" else None
        except Exception:
            preco = None

        payload = {
            "produto": {
                "codigo": codigo,
                "nome": nome,
                "preco": preco,
                "tipo": "P",
            }
        }

        return self._request("POST", "/produtos", json=payload)

    # =========================
    # ESTOQUE
    # =========================
    def update_stock(
        self,
        *,
        codigo: str,
        estoque: float,
        deposito_id: Optional[str] = None,
        preco: Optional[float] = None,
    ) -> Tuple[bool, Any]:
        codigo = self._safe_str(codigo)
        if not codigo:
            return False, {"erro": "Código vazio para estoque"}

        try:
            estoque = float(estoque or 0)
        except Exception:
            estoque = 0.0

        try:
            preco = float(preco) if preco is not None and str(preco).strip() != "" else None
        except Exception:
            preco = None

        payload: Dict[str, Any] = {
            "produto": {
                "codigo": codigo,
                "estoque": estoque,
            }
        }

        if deposito_id:
            payload["produto"]["deposito"] = {"id": self._safe_str(deposito_id)}

        if preco is not None:
            payload["produto"]["preco"] = preco

        return self._request("PUT", "/produtos/estoques", json=payload)
