from __future__ import annotations

from typing import Any, Dict, List, Tuple

from bling_app_zero.core.bling_api import BlingAPIClient


def sync_products(
    rows: List[Dict[str, Any]],
    *,
    user_key: str = "default",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    client = BlingAPIClient(user_key=user_key)
    sucessos: List[Dict[str, Any]] = []
    erros: List[Dict[str, Any]] = []

    for indice, row in enumerate(rows, start=1):
        ok, payload = client.upsert_product(row)
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
    rows: List[Dict[str, Any]],
    *,
    user_key: str = "default",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    client = BlingAPIClient(user_key=user_key)
    sucessos: List[Dict[str, Any]] = []
    erros: List[Dict[str, Any]] = []

    for indice, row in enumerate(rows, start=1):
        codigo = str(row.get("codigo") or "").strip()
        estoque = row.get("estoque")
        deposito_id = row.get("deposito_id")
        preco = row.get("preco")

        ok, payload = client.update_stock(
            codigo=codigo,
            estoque=float(estoque or 0),
            deposito_id=str(deposito_id).strip() if deposito_id not in (None, "") else None,
            preco=float(preco) if preco not in (None, "") else None,
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
