from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import httpx

from bling_app_zero.core.bling_auth import BlingAuthManager


class BlingAPIClient:
    def __init__(self, user_key: str = "default") -> None:
        self.auth = BlingAuthManager(user_key=user_key)
        self.base_url = self.auth.settings.api_base_url.rstrip("/")

        # 🔥 CLIENTE REUTILIZÁVEL (performance + estabilidade)
        self._client = httpx.Client(timeout=30.0, follow_redirects=True)

    # =========================
    # PADRÃO DE RESPOSTA
    # =========================
    def _ok(self, data: Any) -> Tuple[bool, Dict[str, Any]]:
        return True, {"ok": True, "data": data}

    def _error(self, message: str, extra: Any = None) -> Tuple[bool, Dict[str, Any]]:
        return False, {
            "ok": False,
            "erro": message,
            "detalhes": extra,
        }

    def _headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "enable-jwt": "1",
        }

    @staticmethod
    def _parse_response_payload(resp: httpx.Response) -> Any:
        content_type = str(resp.headers.get("content-type", "")).lower()

        if "application/json" in content_type:
            try:
                return resp.json()
            except Exception:
                return {
                    "raw_text": resp.text,
                    "parse_error": "Falha ao interpretar JSON da resposta.",
                }

        return resp.text

    @staticmethod
    def _clean_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _normalize_situacao(value: Any) -> str:
        texto = BlingAPIClient._clean_str(value).lower()

        if not texto:
            return "A"

        mapa_ativo = {"a", "ativo", "active", "1", "true", "sim"}
        mapa_inativo = {"i", "inativo", "inactive", "0", "false", "nao", "não", "desativado"}

        if texto in mapa_ativo:
            return "A"
        if texto in mapa_inativo:
            return "I"

        return BlingAPIClient._clean_str(value).upper() or "A"

    @staticmethod
    def _safe_float(valor: Any) -> Optional[float]:
        try:
            if valor is None or valor == "":
                return None

            texto = str(valor).replace("R$", "").replace(" ", "")
            texto = texto.replace(".", "").replace(",", ".")

            return float(texto)
        except Exception:
            return None

    # =========================
    # REQUEST BASE (ANTI DUPLICAÇÃO + REFRESH)
    # =========================
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any]:

        ok, token_or_msg = self.auth.get_valid_access_token()
        if not ok:
            return self._error("Erro de autenticação", token_or_msg)

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._headers(token_or_msg)

        try:
            resp = self._client.request(
                method.upper(),
                url,
                headers=headers,
                params=params,
                json=json,
            )

            # 🔥 REFRESH AUTOMÁTICO
            if resp.status_code == 401:
                refresh_ok, refresh_msg = self.auth.refresh_access_token()
                if not refresh_ok:
                    return self._error("Erro ao renovar token", refresh_msg)

                ok2, token_or_msg2 = self.auth.get_valid_access_token()
                if not ok2:
                    return self._error("Erro após refresh do token", token_or_msg2)

                headers = self._headers(token_or_msg2)

                resp = self._client.request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )

            payload = self._parse_response_payload(resp)

            if resp.status_code >= 400:
                return self._error(
                    f"Erro HTTP {resp.status_code}",
                    {"payload": payload, "url": url},
                )

            return self._ok(payload)

        except httpx.TimeoutException as exc:
            return self._error("Timeout com Bling", str(exc))
        except httpx.RequestError as exc:
            return self._error("Erro de conexão", str(exc))
        except Exception as exc:
            return self._error("Erro inesperado", str(exc))

    # =========================
    # NORMALIZAÇÃO PRODUTO
    # =========================
    def _normalize_product_payload(self, row: Dict[str, Any]) -> Dict[str, Any]:
        nome = self._clean_str(row.get("nome") or row.get("descricao"))
        codigo = self._clean_str(row.get("codigo") or row.get("sku"))

        if not nome or not codigo:
            return {}

        payload: Dict[str, Any] = {
            "nome": nome,
            "codigo": codigo,
            "tipo": "P",
            "formato": "S",
            "situacao": self._normalize_situacao(row.get("situacao")),
            "unidade": "UN",
        }

        preco = row.get("preco") or row.get("preco_venda")
        preco_float = self._safe_float(preco)

        if preco_float is not None:
            payload["preco"] = preco_float

        return payload

    # =========================
    # UPSERT PRODUTO (SEM DUPLICIDADE)
    # =========================
    def upsert_product(
        self,
        row: Dict[str, Any],
        *,
        force_create: bool = False,
    ) -> Tuple[bool, Any]:

        payload = self._normalize_product_payload(row)

        if not payload:
            return self._error("Produto inválido ou incompleto", row)

        # 🔥 MODO TURBO / CADASTRO DIRETO
        if force_create:
            return self.request("POST", "/produtos", json=payload)

        codigo = payload.get("codigo")

        ok, resp = self.request(
            "GET",
            "/produtos",
            params={"codigo": codigo},
        )

        if ok:
            data = resp.get("data")

            lista = []
            if isinstance(data, dict):
                lista = data.get("data") or data.get("produtos") or []
            elif isinstance(data, list):
                lista = data

            if lista:
                produto_id = lista[0].get("id")
                if produto_id:
                    return self.request(
                        "PUT",
                        f"/produtos/{produto_id}",
                        json=payload,
                    )

        return self.request("POST", "/produtos", json=payload)

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

        if not codigo:
            return self._error("Código vazio")

        body = {
            "codigo": codigo,
            "saldo": float(estoque or 0),
        }

        if preco is not None:
            body["preco"] = float(preco)

        if deposito_id:
            try:
                body["deposito"] = {"id": int(deposito_id)}
            except Exception:
                return self._error("deposito_id inválido", deposito_id)

        return self.request("POST", "/estoques", json=body)
