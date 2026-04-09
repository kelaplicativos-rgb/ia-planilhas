from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
import pandas as pd

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
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
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

                payload = self._parse_response_payload(resp)

                if resp.status_code >= 400:
                    return False, {
                        "status_code": resp.status_code,
                        "error": payload,
                        "url": url,
                        "params": params,
                        "json": json,
                    }

                return True, payload

        except httpx.TimeoutException as exc:
            return False, f"Timeout ao comunicar com o Bling: {exc}"
        except httpx.RequestError as exc:
            return False, f"Erro de comunicação com o Bling: {exc}"
        except Exception as exc:
            return False, f"Erro de comunicação com o Bling: {exc}"

    @staticmethod
    def _data_list(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                return [data]

        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        return []

    @staticmethod
    def _data_dict(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, dict):
                return data
            return payload
        return {}

    @staticmethod
    def _pick(d: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in d and d.get(key) not in (None, ""):
                return d.get(key)
        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None

        try:
            if isinstance(value, str):
                texto = value.strip()
                if not texto:
                    return None

                texto = (
                    texto.replace("R$", "")
                    .replace("r$", "")
                    .replace(" ", "")
                    .replace("\u00a0", "")
                )

                if "," in texto:
                    texto = texto.replace(".", "").replace(",", ".")
                else:
                    texto = texto.replace(",", "")

                return float(texto)

            return float(value)
        except Exception:
            return None

    def _collect_pages(
        self,
        path: str,
        *,
        page_size: int = 100,
        max_pages: int = 5,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        items: List[Dict[str, Any]] = []
        params_base = dict(extra_params or {})

        for page in range(1, max_pages + 1):
            params = dict(params_base)
            params["pagina"] = page
            params["limite"] = page_size

            ok, payload = self.request("GET", path, params=params)
            if not ok:
                return False, payload

            lote = self._data_list(payload)
            items.extend(lote)

            if len(lote) < page_size:
                break

        return True, items

    def list_products(self, page_size: int = 100, max_pages: int = 5) -> Tuple[bool, Any]:
        return self._collect_pages("/produtos", page_size=page_size, max_pages=max_pages)

    def list_stocks(self, page_size: int = 100, max_pages: int = 5) -> Tuple[bool, Any]:
        ok, produtos = self.list_products(page_size=page_size, max_pages=max_pages)
        if not ok:
            return False, produtos

        rows: List[Dict[str, Any]] = []
        for produto in produtos:
            pid = self._pick(produto, "id")
            if pid in (None, ""):
                continue

            ok_item, payload_item = self.request("GET", f"/produtos/{pid}")
            if not ok_item:
                rows.append({"id_produto": pid, "erro": payload_item})
                continue

            detalhe = self._data_dict(payload_item)
            produto_info = detalhe.get("produto") if isinstance(detalhe.get("produto"), dict) else detalhe
            estoque_info = detalhe.get("estoque") if isinstance(detalhe.get("estoque"), list) else []

            if estoque_info:
                for estoque in estoque_info:
                    if not isinstance(estoque, dict):
                        continue

                    rows.append(
                        {
                            "id_produto": self._pick(produto_info, "id", "idProduto"),
                            "codigo": self._pick(produto_info, "codigo", "codigoProduto"),
                            "nome": self._pick(produto_info, "nome", "descricao"),
                            "deposito_id": self._pick(estoque, "idDeposito", "deposito_id", "deposito"),
                            "deposito": self._pick(estoque, "deposito", "nomeDeposito"),
                            "saldo": self._pick(
                                estoque,
                                "saldoVirtualTotal",
                                "saldoFisicoTotal",
                                "saldo",
                                "estoque",
                            ),
                        }
                    )
            else:
                rows.append(
                    {
                        "id_produto": self._pick(produto_info, "id", "idProduto"),
                        "codigo": self._pick(produto_info, "codigo", "codigoProduto"),
                        "nome": self._pick(produto_info, "nome", "descricao"),
                        "deposito_id": None,
                        "deposito": None,
                        "saldo": self._pick(produto_info, "estoque", "saldo"),
                    }
                )

        return True, rows

    def products_to_dataframe(self, payload: Any) -> pd.DataFrame:
        items = self._data_list(payload) if not isinstance(payload, list) else payload
        rows: List[Dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            rows.append(
                {
                    "id": self._pick(item, "id"),
                    "codigo": self._pick(item, "codigo"),
                    "nome": self._pick(item, "nome", "descricao"),
                    "preco": self._pick(item, "preco", "precoVenda", "valor"),
                    "situacao": self._pick(item, "situacao", "status"),
                    "marca": self._pick(item, "marca"),
                    "categoria": self._pick(item, "categoria", "descricaoCategoria"),
                }
            )

        return pd.DataFrame(rows)

    def stocks_to_dataframe(self, payload: Any) -> pd.DataFrame:
        items = payload if isinstance(payload, list) else self._data_list(payload)
        rows: List[Dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            rows.append(
                {
                    "id_produto": self._pick(item, "id_produto", "id"),
                    "codigo": self._pick(item, "codigo"),
                    "nome": self._pick(item, "nome", "descricao"),
                    "deposito_id": self._pick(item, "deposito_id", "idDeposito"),
                    "deposito": self._pick(item, "deposito", "nomeDeposito"),
                    "saldo": self._pick(item, "saldo", "estoque"),
                }
            )

        return pd.DataFrame(rows)

    def _normalize_product_payload(self, row: Dict[str, Any]) -> Dict[str, Any]:
        nome = self._clean_str(
            self._pick(row, "nome", "descricao", "descricao_curta", "descrição curta")
        )
        codigo = self._clean_str(self._pick(row, "codigo", "sku"))
        preco = self._pick(
            row,
            "preco",
            "preco_venda",
            "valor",
            "preco de venda",
            "Preço de venda",
        )
        unidade = self._clean_str(self._pick(row, "unidade", "unidade_medida")) or "UN"
        situacao = self._normalize_situacao(self._pick(row, "situacao"))
        tipo = self._clean_str(self._pick(row, "tipo")).upper() or "P"
        formato = self._clean_str(self._pick(row, "formato")).upper() or "S"

        payload: Dict[str, Any] = {
            "nome": nome,
            "codigo": codigo,
            "tipo": tipo,
            "formato": formato,
            "situacao": situacao,
            "unidade": unidade,
        }

        preco_float = self._to_float(preco)
        if preco_float is not None:
            payload["preco"] = preco_float

        gtin = self._pick(row, "gtin", "ean")
        if gtin not in (None, ""):
            payload["gtin"] = self._clean_str(gtin)

        marca = self._pick(row, "marca")
        if marca not in (None, ""):
            payload["marca"] = self._clean_str(marca)

        descricao_curta = self._pick(row, "descricao_curta", "descrição curta")
        if descricao_curta not in (None, ""):
            payload["descricaoCurta"] = self._clean_str(descricao_curta)

        return payload

    def find_product_by_code(self, codigo: str) -> Tuple[bool, Any]:
        codigo = self._clean_str(codigo)
        if not codigo:
            return False, "Código vazio."

        ok, payload = self.request("GET", "/produtos", params={"codigo": codigo, "limite": 1})
        if not ok:
            return False, payload

        items = self._data_list(payload)
        if not items:
            return True, None

        return True, items[0]

    def upsert_product(self, row: Dict[str, Any]) -> Tuple[bool, Any]:
        if not isinstance(row, dict):
            return False, "Linha do produto inválida."

        codigo = self._clean_str(self._pick(row, "codigo", "sku"))
        payload = self._normalize_product_payload(row)

        if not payload.get("nome"):
            return False, "Nome do produto ausente."
        if not codigo:
            return False, "Código do produto ausente."

        ok_find, found = self.find_product_by_code(codigo)
        if not ok_find:
            return False, found

        if found:
            product_id = self._pick(found, "id")
            if product_id in (None, ""):
                return False, {"erro": "Produto localizado sem id.", "produto": found}

            return self.request("PUT", f"/produtos/{product_id}", json=payload)

        return self.request("POST", "/produtos", json=payload)

    def update_stock(
        self,
        *,
        codigo: str,
        estoque: float,
        deposito_id: Optional[str] = None,
        preco: Optional[float] = None,
    ) -> Tuple[bool, Any]:
        codigo = self._clean_str(codigo)
        if not codigo:
            return False, "Código do produto ausente para atualização de estoque."

        ok_find, found = self.find_product_by_code(codigo)
        if not ok_find:
            return False, found
        if not found:
            return False, f"Produto com código {codigo} não encontrado no Bling."

        product_id = self._pick(found, "id")
        if product_id in (None, ""):
            return False, {"erro": "Produto localizado sem id.", "produto": found}

        estoque_float = self._to_float(estoque)
        if estoque_float is None:
            estoque_float = 0.0

        body: Dict[str, Any] = {
            "produto": {"id": product_id},
            "saldo": estoque_float,
        }

        if deposito_id not in (None, ""):
            body["deposito"] = {"id": self._clean_str(deposito_id)}

        preco_float = self._to_float(preco)
        if preco_float is not None:
            body["preco"] = preco_float

        raw_candidates: Iterable[str] = (
            self.auth.settings.stock_write_path or "/estoques",
            "/estoques",
            "/produtos/estoques",
            f"/produtos/{product_id}/estoques",
        )

        candidates: List[str] = []
        vistos = set()
        for path in raw_candidates:
            path_limpo = self._clean_str(path)
            if not path_limpo or path_limpo in vistos:
                continue
            vistos.add(path_limpo)
            candidates.append(path_limpo)

        tried: List[Any] = []
        for path in candidates:
            ok, payload = self.request("POST", path, json=body)
            if ok:
                return True, payload
            tried.append({"path": path, "resultado": payload})

        return False, {
            "erro": "Falha ao atualizar estoque nas rotas testadas.",
            "tentativas": tried,
            "body": body,
        }
