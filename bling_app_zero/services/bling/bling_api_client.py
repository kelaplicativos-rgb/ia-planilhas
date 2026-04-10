from __future__ import annotations

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
        # 🔥 FUTURO: trocar por OAuth real
        # por enquanto usa secrets ou variável fixa
        try:
            import streamlit as st

            return st.secrets.get("BLING_ACCESS_TOKEN", "")
        except Exception:
            return ""

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    # =========================
    # REQUEST BASE
    # =========================
    def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any]:
        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=json,
                timeout=30,
            )

            if response.status_code in (200, 201):
                return True, response.json()

            return False, {
                "status": response.status_code,
                "erro": response.text,
            }

        except Exception as e:
            return False, {"erro": str(e)}

    # =========================
    # PRODUTO
    # =========================
    def upsert_product(self, data: Dict[str, Any]) -> Tuple[bool, Any]:
        payload = {
            "produto": {
                "codigo": str(data.get("codigo") or data.get("sku") or ""),
                "nome": data.get("nome") or data.get("descricao") or "",
                "preco": data.get("preco") or data.get("preco_venda"),
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
        payload = {
            "produto": {
                "codigo": codigo,
                "estoque": estoque,
            }
        }

        if deposito_id:
            payload["produto"]["deposito"] = {"id": deposito_id}

        if preco is not None:
            payload["produto"]["preco"] = preco

        return self._request("PUT", "/produtos/estoques", json=payload)
