from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from bling_app_zero.core.bling_api import BlingAPIClient
from bling_app_zero.core.bling_auth import BlingAuthManager


class BlingSyncService:
    def __init__(self, user_key: str = "default") -> None:
        self.client = BlingAPIClient(user_key=user_key)
        self.auth = BlingAuthManager(user_key=user_key)

    def test_connection(self) -> Tuple[bool, Any]:
        return self.client.request("GET", "/produtos", params={"pagina": 1, "limite": 1})

    def importar_produtos(self, pagina: int = 1, limite: int = 50) -> Tuple[bool, Any]:
        ok, payload = self.client.request(
            "GET",
            "/produtos",
            params={"pagina": pagina, "limite": limite},
        )
        if not ok:
            return False, payload

        itens = self._extract_items(payload)
        linhas: List[Dict[str, Any]] = []

        for item in itens:
            linhas.append(
                {
                    "id": self._pick(item, ["id"]),
                    "codigo": self._pick(item, ["codigo"]),
                    "nome": self._pick(item, ["nome", "descricao"]),
                    "descricao_curta": self._pick(item, ["descricaoCurta", "descricao_curta"]),
                    "preco": self._pick(item, ["preco"]),
                    "preco_custo": self._pick(item, ["precoCusto", "preco_custo"]),
                    "estoque": self._pick(item, ["estoque", "saldo"]),
                    "gtin": self._pick(item, ["gtin", "ean"]),
                    "marca": self._pick(item, ["marca"]),
                    "categoria": self._pick(item, ["categoria"]),
                    "situacao": self._pick(item, ["situacao"]),
                }
            )

        return True, linhas

    def importar_estoques(
        self,
        pagina: int = 1,
        limite: int = 50,
        id_deposito: Optional[str] = None,
    ) -> Tuple[bool, Any]:
        path = f"/estoques/saldos/{id_deposito}" if id_deposito else "/estoques/saldos"
        ok, payload = self.client.request(
            "GET",
            path,
            params={"pagina": pagina, "limite": limite},
        )
        if not ok:
            return False, payload

        itens = self._extract_items(payload)
        linhas: List[Dict[str, Any]] = []

        for item in itens:
            linhas.append(
                {
                    "produto_id": self._pick(item, ["produto.id", "idProduto", "produtoId"]),
                    "codigo": self._pick(item, ["produto.codigo", "codigo"]),
                    "nome": self._pick(item, ["produto.nome", "produto.descricao", "nome", "descricao"]),
                    "deposito_id": self._pick(item, ["deposito.id", "idDeposito", "depositoId"]),
                    "deposito": self._pick(item, ["deposito.descricao", "deposito.nome", "deposito"]),
                    "saldo": self._pick(item, ["saldoFisicoTotal", "saldoFisico", "saldo"]),
                    "saldo_virtual": self._pick(item, ["saldoVirtualTotal", "saldoVirtual"]),
                }
            )

        return True, linhas

    def enviar_cadastros(self, rows: List[Dict[str, Any]], dry_run: bool = True) -> Tuple[bool, List[Dict[str, Any]]]:
        logs: List[Dict[str, Any]] = []
        overall_ok = True

        for i, row in enumerate(rows, start=1):
            codigo = str(row.get("codigo") or "").strip()
            nome = str(row.get("nome") or "").strip()

            if not codigo or not nome:
                overall_ok = False
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "status": "erro",
                        "mensagem": "Código e nome são obrigatórios para cadastro.",
                    }
                )
                continue

            payload = self._build_product_payload(row)

            if dry_run:
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "status": "validado",
                        "mensagem": "Linha validada com sucesso.",
                        "payload": payload,
                    }
                )
                continue

            ok, resp = self.client.request("POST", "/produtos", json=payload)
            if ok:
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "status": "enviado",
                        "mensagem": "Produto enviado com sucesso.",
                        "retorno": resp,
                    }
                )
            else:
                overall_ok = False
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "status": "erro",
                        "mensagem": "Falha ao enviar produto.",
                        "retorno": resp,
                    }
                )

        return overall_ok, logs

    def enviar_estoques(self, rows: List[Dict[str, Any]], dry_run: bool = True) -> Tuple[bool, List[Dict[str, Any]]]:
        logs: List[Dict[str, Any]] = []
        overall_ok = True

        stock_path = self.auth.settings.stock_write_path or "/estoques"

        for i, row in enumerate(rows, start=1):
            codigo = str(row.get("codigo") or "").strip()
            deposito_id = str(row.get("deposito_id") or "").strip()
            estoque = row.get("estoque")

            if not codigo:
                overall_ok = False
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "status": "erro",
                        "mensagem": "Código é obrigatório para estoque.",
                    }
                )
                continue

            if estoque is None:
                overall_ok = False
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "status": "erro",
                        "mensagem": "Quantidade de estoque ausente.",
                    }
                )
                continue

            payload = self._build_stock_payload(row)

            if dry_run:
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "status": "validado",
                        "mensagem": "Linha de estoque validada com sucesso.",
                        "payload": payload,
                    }
                )
                continue

            ok, resp = self.client.request("POST", stock_path, json=payload)
            if ok:
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "deposito_id": deposito_id,
                        "status": "enviado",
                        "mensagem": "Estoque enviado com sucesso.",
                        "retorno": resp,
                    }
                )
            else:
                overall_ok = False
                logs.append(
                    {
                        "linha": i,
                        "codigo": codigo,
                        "deposito_id": deposito_id,
                        "status": "erro",
                        "mensagem": "Falha ao enviar estoque.",
                        "retorno": resp,
                    }
                )

        return overall_ok, logs

    def _build_product_payload(self, row: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "codigo": row.get("codigo"),
            "nome": row.get("nome"),
        }

        if row.get("descricao_curta"):
            payload["descricaoCurta"] = row.get("descricao_curta")
        if row.get("preco") is not None:
            payload["preco"] = row.get("preco")
        if row.get("preco_custo") is not None:
            payload["precoCusto"] = row.get("preco_custo")
        if row.get("gtin"):
            payload["gtin"] = row.get("gtin")
        if row.get("marca"):
            payload["marca"] = row.get("marca")
        if row.get("categoria"):
            payload["categoria"] = row.get("categoria")
        if row.get("estoque") is not None:
            payload["estoque"] = row.get("estoque")

        return payload

    def _build_stock_payload(self, row: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "produto": {
                "codigo": row.get("codigo"),
            },
            "quantidade": row.get("estoque"),
        }

        if row.get("deposito_id"):
            payload["deposito"] = {"id": row.get("deposito_id")}
        if row.get("preco") is not None:
            payload["preco"] = row.get("preco")

        return payload

    def _extract_items(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            for key in ("data", "items", "itens", "produtos", "estoques", "saldos"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [x for x in value if isinstance(x, dict)]
            if "data" in payload and isinstance(payload["data"], dict):
                nested = payload["data"]
                for key in ("items", "itens", "produtos", "estoques", "saldos"):
                    value = nested.get(key)
                    if isinstance(value, list):
                        return [x for x in value if isinstance(x, dict)]
        return []

    def _pick(self, obj: Dict[str, Any], paths: List[str]) -> Any:
        for path in paths:
            value = self._deep_get(obj, path)
            if value is not None:
                return value
        return None

    def _deep_get(self, obj: Any, dotted_path: str) -> Any:
        cur = obj
        for part in dotted_path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur
