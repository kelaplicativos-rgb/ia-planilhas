from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import requests


class BlingAPIClient:
    BASE_URL = "https://www.bling.com.br/Api/v3"

    def __init__(self, user_key: str = "default") -> None:
        self.user_key = user_key
        self.access_token = self._get_token()

    # =========================
    # TOKEN
    # =========================
    def _get_token(self) -> str:
        """
        Busca token de forma segura e sem quebrar fora do Streamlit.
        Prioridade:
        1) streamlit.session_state["bling_access_token"]
        2) streamlit.secrets["BLING_ACCESS_TOKEN"]
        3) variável de ambiente BLING_ACCESS_TOKEN
        """
        token = ""

        try:
            import streamlit as st

            token = (
                st.session_state.get("bling_access_token")
                or st.secrets.get("BLING_ACCESS_TOKEN", "")
                or ""
            )
        except Exception:
            token = ""

        if not token:
            token = os.getenv("BLING_ACCESS_TOKEN", "") or ""

        return str(token).strip()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        return headers

    # =========================
    # HELPERS
    # =========================
    def _normalizar_endpoint(self, endpoint: str) -> str:
        endpoint = str(endpoint or "").strip()
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
    # REQUEST BASE
    # =========================
    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any]:
        if not self.access_token:
            return False, {
                "status": 401,
                "erro": "Token de acesso do Bling não configurado.",
            }

        url = f"{self.BASE_URL}{self._normalizar_endpoint(endpoint)}"

        try:
            response = requests.request(
                method=str(method or "GET").upper(),
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

            return False, {
                "status": response.status_code,
                "erro": data,
            }

        except requests.Timeout:
            return False, {
                "status": 408,
                "erro": "Tempo limite excedido ao comunicar com a API do Bling.",
            }
        except requests.RequestException as e:
            return False, {
                "status": 500,
                "erro": f"Erro de conexão com a API do Bling: {str(e)}",
            }
        except Exception as e:
            return False, {
                "status": 500,
                "erro": str(e),
            }

    # =========================
    # PRODUTO
    # =========================
    def upsert_product(self, data: Dict[str, Any]) -> Tuple[bool, Any]:
        payload = {
            "produto": {
                "codigo": str(data.get("codigo") or data.get("sku") or "").strip(),
                "nome": str(data.get("nome") or data.get("descricao") or "").strip(),
                "preco": data.get("preco")
                if data.get("preco") is not None
                else data.get("preco_venda"),
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
        payload: Dict[str, Any] = {
            "produto": {
                "codigo": str(codigo or "").strip(),
                "estoque": estoque,
            }
        }

        if deposito_id:
            payload["produto"]["deposito"] = {"id": str(deposito_id).strip()}

        if preco is not None:
            payload["produto"]["preco"] = preco

        return self._request("PUT", "/produtos/estoques", json=payload)
