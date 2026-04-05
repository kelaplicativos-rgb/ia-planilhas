from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from bling_app_zero.core.bling_auth import BlingAuthManager


class BlingAPIClient:
    def __init__(self, user_key: str = "default") -> None:
        self.auth = BlingAuthManager(user_key=user_key)
        self.base_url = self.auth.settings.api_base_url.rstrip("/")

    def _headers(self, access_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "enable-jwt": "1",
        }

    @staticmethod
    def _unwrap_data(payload: Any) -> Any:
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    @staticmethod
    def _as_list(payload: Any) -> List[Dict[str, Any]]:
        data = BlingAPIClient._unwrap_data(payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("data"), list):
                return [item for item in data["data"] if isinstance(item, dict)]
            return [data]
        return []

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Tuple[bool, Any]:
        ok, token_or_msg = self.auth.get_valid_access_token()
        if not ok:
            return False, token_or_msg

        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._headers(token_or_msg)

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )

                if resp.status_code == 401:
                    refresh_ok, refresh_msg = self.auth.refresh_access_token()
                    if not refresh_ok:
                        return False, refresh_msg

                    ok2, token_or_msg2 = self.auth.get_valid_access_token()
                    if not ok2:
                        return False, token_or_msg2

                    headers = self._headers(token_or_msg2)
                    resp = client.request(
                        method.upper(),
                        url,
                        headers=headers,
                        params=params,
                        json=json,
                    )

            content_type = resp.headers.get("content-type", "")
            payload = (
                resp.json() if "application/json" in content_type else {"raw": resp.text}
            )

            if resp.status_code >= 400:
                return False, {
                    "status_code": resp.status_code,
                    "error": payload,
                    "url": url,
                    "params": params,
                    "body": json,
                }

            return True, payload
        except Exception as exc:
            return False, f"Erro de comunicação com o Bling: {exc}"

    def paginate(
        self,
        path: str,
        *,
        page_size: int = 100,
        max_pages: int = 10,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        itens: List[Dict[str, Any]] = []
        params_base = dict(extra_params or {})
        pagina = 1

        while pagina <= max_pages:
            params = {"pagina": pagina, "limite": page_size, **params_base}
            ok, payload = self.request("GET", path, params=params)
            if not ok:
                return False, payload

            lote = self._as_list(payload)
            if not lote:
                break

            itens.extend(lote)

            if len(lote) < page_size:
                break
            pagina += 1

        return True, itens

    def list_products(
        self,
        *,
        page_size: int = 100,
        max_pages: int = 5,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        return self.paginate("/produtos", page_size=page_size, max_pages=max_pages)

    def list_stocks(
        self,
        *,
        page_size: int = 100,
        max_pages: int = 5,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        ok, produtos = self.list_products(page_size=page_size, max_pages=max_pages)
        if not ok:
            return False, produtos

        linhas: List[Dict[str, Any]] = []
        for item in produtos:
            produto = item.get("produto") if isinstance(item.get("produto"), dict) else item
            if not isinstance(produto, dict):
                continue

            codigo = produto.get("codigo")
            nome = produto.get("nome")
            estoque = (
                produto.get("estoque")
                or produto.get("saldo")
                or produto.get("estoqueAtual")
                or produto.get("saldoVirtualTotal")
            )
            linhas.append(
                {
                    "id": produto.get("id"),
                    "codigo": codigo,
                    "nome": nome,
                    "estoque": estoque,
                }
            )
        return True, linhas

    def get_product_by_code(self, codigo: str) -> Tuple[bool, Any]:
        codigo = str(codigo or "").strip()
        if not codigo:
            return False, "Código vazio para consulta de produto."

        tentativas = [
            {"codigo": codigo},
            {"criterio": 2, "tipo": 2, "valor": codigo},
        ]
        for params in tentativas:
            ok, payload = self.request("GET", "/produtos", params=params)
            if ok:
                itens = self._as_list(payload)
                for item in itens:
                    produto = item.get("produto") if isinstance(item.get("produto"), dict) else item
                    if not isinstance(produto, dict):
                        continue
                    cod_item = str(produto.get("codigo", "")).strip()
                    if cod_item == codigo:
                        return True, produto
        return False, f"Produto com código '{codigo}' não encontrado."

    @staticmethod
    def _first_non_empty(*values: Any) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return None

    def _produto_payload(self, row: Dict[str, Any]) -> Dict[str, Any]:
        codigo = self._first_non_empty(row.get("codigo"), row.get("sku"), "")
        nome = self._first_non_empty(row.get("nome"), "")
        descricao_curta = self._first_non_empty(row.get("descricao_curta"), "")
        descricao = self._first_non_empty(row.get("descricao"), descricao_curta, nome, "")
        preco = float(row.get("preco") or 0)
        preco_custo = row.get("preco_custo")
        estoque = row.get("estoque")
        gtin = self._first_non_empty(row.get("gtin"), "")
        marca = self._first_non_empty(row.get("marca"), "")
        categoria = self._first_non_empty(row.get("categoria"), "")

        payload: Dict[str, Any] = {
            "codigo": str(codigo).strip(),
            "nome": str(nome).strip(),
            "tipo": "P",
            "situacao": "A",
            "formato": "S",
            "preco": preco,
            "descricaoCurta": str(descricao_curta).strip(),
            "descricaoComplementar": str(descricao).strip(),
        }

        if preco_custo is not None:
            try:
                payload["precoCusto"] = float(preco_custo)
            except Exception:
                pass

        if estoque is not None:
            try:
                payload["estoque"] = float(estoque)
            except Exception:
                pass

        if gtin:
            payload["gtin"] = str(gtin).strip()

        if marca:
            payload["marca"] = str(marca).strip()

        if categoria:
            payload["descricaoCategoria"] = str(categoria).strip()

        return payload

    def create_product(self, row: Dict[str, Any]) -> Tuple[bool, Any]:
        payload = self._produto_payload(row)
        return self.request("POST", "/produtos", json=payload)

    def update_product(self, product_id: Any, row: Dict[str, Any]) -> Tuple[bool, Any]:
        payload = self._produto_payload(row)
        return self.request("PUT", f"/produtos/{product_id}", json=payload)

    def upsert_product(self, row: Dict[str, Any]) -> Tuple[bool, Any]:
        codigo = str(row.get("codigo") or row.get("sku") or "").strip()
        if not codigo:
            return False, "Produto sem código para envio."

        ok, produto = self.get_product_by_code(codigo)
        if ok and isinstance(produto, dict) and produto.get("id"):
            return self.update_product(produto["id"], row)

        return self.create_product(row)

    def update_stock(
        self,
        *,
        codigo: str,
        estoque: float,
        deposito_id: Optional[str] = None,
        preco: Optional[float] = None,
    ) -> Tuple[bool, Any]:
        ok, produto = self.get_product_by_code(codigo)
        if not ok:
            return False, produto

        product_id = produto.get("id")
        if not product_id:
            return False, f"Produto '{codigo}' encontrado sem ID."

        payloads: List[Tuple[str, str, Dict[str, Any]]] = []

        body_a: Dict[str, Any] = {"estoque": float(estoque)}
        if deposito_id:
            body_a["deposito"] = {"id": int(str(deposito_id))}
        if preco is not None:
            body_a["preco"] = float(preco)
        payloads.append(("PATCH", f"/produtos/{product_id}/estoques", body_a))

        body_b: Dict[str, Any] = {"quantidade": float(estoque)}
        if deposito_id:
            body_b["deposito"] = {"id": int(str(deposito_id))}
        if preco is not None:
            body_b["preco"] = float(preco)
        payloads.append(("POST", f"/estoques", {"produto": {"id": product_id}, **body_b}))

        ultimo_erro: Any = None
        for method, path, body in payloads:
            ok_req, payload = self.request(method, path, json=body)
            if ok_req:
                return True, payload
            ultimo_erro = payload

        return False, ultimo_erro

    @staticmethod
    def products_to_dataframe(items: Iterable[Dict[str, Any]]):
        import pandas as pd

        linhas: List[Dict[str, Any]] = []
        for item in items:
            produto = item.get("produto") if isinstance(item.get("produto"), dict) else item
            if not isinstance(produto, dict):
                continue
            linhas.append(
                {
                    "id": produto.get("id"),
                    "codigo": produto.get("codigo"),
                    "nome": produto.get("nome"),
                    "preco": produto.get("preco"),
                    "marca": produto.get("marca"),
                    "gtin": produto.get("gtin"),
                    "categoria": produto.get("descricaoCategoria") or produto.get("categoria"),
                    "situacao": produto.get("situacao"),
                }
            )
        return pd.DataFrame(linhas)

    @staticmethod
    def stocks_to_dataframe(items: Iterable[Dict[str, Any]]):
        import pandas as pd

        return pd.DataFrame(list(items))
