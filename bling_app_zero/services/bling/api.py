from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from bling_app_zero.core.bling_api import BlingAPIClient


class BlingServices:
    def __init__(self, user_key: str = "default") -> None:
        self.api = BlingAPIClient(user_key=user_key)

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _pick(d: Dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in d and d.get(key) not in (None, ""):
                return d.get(key)
        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None

            texto = str(value).replace("R$", "").replace(" ", "")
            texto = texto.replace(".", "").replace(",", ".")

            return float(texto)
        except Exception:
            return None

    # =========================
    # PRODUTOS
    # =========================
    def upsert_products(self, rows: List[Dict[str, Any]]) -> Tuple[int, int, List[Any]]:
        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in rows:
            ok, resp = self.api.upsert_product(row)

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(resp)

        return sucesso, erro, erros

    # =========================
    # ESTOQUE
    # =========================
    def update_stocks(
        self,
        rows: List[Dict[str, Any]],
        deposito_id: Optional[str] = None,
    ) -> Tuple[int, int, List[Any]]:
        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in rows:
            codigo = self._pick(row, "codigo", "sku")
            estoque = self._pick(row, "estoque", "saldo", "quantidade")

            ok, resp = self.api.update_stock(
                codigo=codigo,
                estoque=self._to_float(estoque) or 0,
                deposito_id=deposito_id,
            )

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(resp)

        return sucesso, erro, erros

    # =========================
    # DATAFRAME
    # =========================
    def produtos_to_df(self, payload: Any) -> pd.DataFrame:
        if not isinstance(payload, list):
            return pd.DataFrame()

        rows = []
        for item in payload:
            rows.append(
                {
                    "id": self._pick(item, "id"),
                    "codigo": self._pick(item, "codigo"),
                    "nome": self._pick(item, "nome"),
                    "preco": self._pick(item, "preco"),
                }
            )

        return pd.DataFrame(rows)
