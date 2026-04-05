from __future__ import annotations

from typing import Any, Dict, List, Tuple

from bling_app_zero.core.bling_api import BlingAPIClient


class BlingSyncService:
    def __init__(self, *, user_key: str = "default") -> None:
        self.user_key = user_key
        self.client = BlingAPIClient(user_key=user_key)

    def sync_products(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            ok, payload = self.client.upsert_product(row)
            item = {
                "linha": indice,
                "codigo": row.get("codigo"),
                "nome": row.get("nome"),
            }
            if ok:
                item["retorno"] = payload
                sucessos.append(item)
            else:
                item["erro"] = payload
                erros.append(item)

        return sucessos, erros

    def sync_stocks(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            codigo = str(row.get("codigo") or "").strip()
            estoque = row.get("estoque")
            deposito_id = row.get("deposito_id")
            preco = row.get("preco")

            try:
                estoque_float = float(estoque or 0)
            except (TypeError, ValueError):
                estoque_float = 0.0

            try:
                preco_float = float(preco) if preco not in (None, "") else None
            except (TypeError, ValueError):
                preco_float = None

            ok, payload = self.client.update_stock(
                codigo=codigo,
                estoque=estoque_float,
                deposito_id=str(deposito_id).strip()
                if deposito_id not in (None, "")
                else None,
                preco=preco_float,
            )

            item = {
                "linha": indice,
                "codigo": codigo,
                "estoque": estoque,
                "deposito_id": deposito_id,
            }
            if ok:
                item["retorno"] = payload
                sucessos.append(item)
            else:
                item["erro"] = payload
                erros.append(item)

        return sucessos, erros


def sync_products(
    rows: List[Dict[str, Any]],
    *,
    user_key: str = "default",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    service = BlingSyncService(user_key=user_key)
    return service.sync_products(rows)


def sync_stocks(
    rows: List[Dict[str, Any]],
    *,
    user_key: str = "default",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    service = BlingSyncService(user_key=user_key)
    return service.sync_stocks(rows)
