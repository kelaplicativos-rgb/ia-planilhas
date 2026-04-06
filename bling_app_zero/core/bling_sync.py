from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from bling_app_zero.core.bling_api import BlingAPIClient


MAX_RETRY = 3
RETRY_DELAY = 1.5


class BlingSyncService:
    def __init__(self, *, user_key: str = "default") -> None:
        self.user_key = user_key
        self.client = BlingAPIClient(user_key=user_key)

    # =========================
    # PRODUTOS
    # =========================
    def sync_products(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            tentativa = 0
            ultimo_erro = None

            while tentativa < MAX_RETRY:
                tentativa += 1

                ok, payload = self.client.upsert_product(row)

                if ok:
                    sucessos.append(
                        {
                            "linha": indice,
                            "codigo": row.get("codigo"),
                            "nome": row.get("nome"),
                            "retorno": payload,
                        }
                    )
                    break
                else:
                    ultimo_erro = payload
                    time.sleep(RETRY_DELAY)

            if tentativa == MAX_RETRY and ultimo_erro:
                erros.append(
                    {
                        "linha": indice,
                        "codigo": row.get("codigo"),
                        "nome": row.get("nome"),
                        "erro": ultimo_erro,
                    }
                )

        return sucessos, erros

    # =========================
    # ESTOQUE (CORRIGIDO)
    # =========================
    def sync_stocks(
        self,
        rows: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sucessos: List[Dict[str, Any]] = []
        erros: List[Dict[str, Any]] = []

        for indice, row in enumerate(rows, start=1):
            codigo = str(row.get("codigo") or "").strip()

            # 🔥 GARANTIR ESTOQUE
            try:
                estoque = int(float(row.get("estoque") or 0))
            except (TypeError, ValueError):
                estoque = 0

            # 🔥 GARANTIR DEPÓSITO
            deposito_id = str(row.get("deposito_id") or "").strip()
            if not deposito_id:
                deposito_id = "Geral"

            # 🔥 PREÇO OPCIONAL
            try:
                preco = float(row.get("preco")) if row.get("preco") else None
            except (TypeError, ValueError):
                preco = None

            tentativa = 0
            ultimo_erro = None

            while tentativa < MAX_RETRY:
                tentativa += 1

                ok, payload = self.client.update_stock(
                    codigo=codigo,
                    estoque=estoque,
                    deposito_id=deposito_id,
                    preco=preco,
                )

                if ok:
                    sucessos.append(
                        {
                            "linha": indice,
                            "codigo": codigo,
                            "estoque": estoque,
                            "deposito_id": deposito_id,
                            "retorno": payload,
                        }
                    )
                    break
                else:
                    ultimo_erro = payload
                    time.sleep(RETRY_DELAY)

            if tentativa == MAX_RETRY and ultimo_erro:
                erros.append(
                    {
                        "linha": indice,
                        "codigo": codigo,
                        "estoque": estoque,
                        "deposito_id": deposito_id,
                        "erro": ultimo_erro,
                    }
                )

        return sucessos, erros


# =========================
# WRAPPERS
# =========================
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
