from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from bling_app_zero.services.bling.bling_api_client import BlingAPIClient


class BlingServices:
    def __init__(self, user_key: str = "default") -> None:
        self.api = BlingAPIClient(user_key=user_key)

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _pick(d: Dict[str, Any], *keys: str) -> Any:
        if not isinstance(d, dict):
            return None

        for key in keys:
            if key in d and d.get(key) not in (None, ""):
                return d.get(key)
        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None

            texto = str(value).strip()
            if not texto:
                return None

            texto = texto.replace("R$", "").replace(" ", "")

            # trata formatos:
            # 1.234,56 -> 1234.56
            # 1234,56  -> 1234.56
            # 1234.56  -> 1234.56
            if "," in texto and "." in texto:
                texto = texto.replace(".", "").replace(",", ".")
            elif "," in texto:
                texto = texto.replace(",", ".")

            return float(texto)
        except Exception:
            return None

    @staticmethod
    def _codigo_valido(row: Dict[str, Any]) -> Optional[str]:
        if not isinstance(row, dict):
            return None

        codigo = str(row.get("codigo") or row.get("sku") or "").strip()
        return codigo if codigo else None

    @staticmethod
    def _normalizar_rows(rows: Any) -> List[Dict[str, Any]]:
        if isinstance(rows, pd.DataFrame):
            try:
                return rows.fillna("").to_dict(orient="records")
            except Exception:
                return []

        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]

        return []

    # =========================
    # PRODUTOS
    # =========================
    def upsert_products(self, rows: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        registros = self._normalizar_rows(rows)

        if not registros:
            return False, {
                "ok": False,
                "operacao": "upsert_products",
                "total": 0,
                "sucesso": 0,
                "erro": 0,
                "erros": ["Nenhum produto válido recebido."],
            }

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in registros:
            codigo = self._codigo_valido(row)
            if not codigo:
                erro += 1
                erros.append({"erro": "codigo vazio", "row": row})
                continue

            try:
                ok, resp = self.api.upsert_product(row)
            except Exception as e:
                ok, resp = False, str(e)

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(resp)

        resultado = {
            "ok": erro == 0 and sucesso > 0,
            "operacao": "upsert_products",
            "total": len(registros),
            "sucesso": sucesso,
            "erro": erro,
            "erros": erros,
        }
        return resultado["ok"], resultado

    # =========================
    # ESTOQUE
    # =========================
    def update_stocks(
        self,
        rows: List[Dict[str, Any]],
        deposito_id: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        registros = self._normalizar_rows(rows)

        if not registros:
            return False, {
                "ok": False,
                "operacao": "update_stocks",
                "total": 0,
                "sucesso": 0,
                "erro": 0,
                "erros": ["Nenhum estoque válido recebido."],
                "detalhes": {"deposito_id": deposito_id},
            }

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in registros:
            codigo = self._codigo_valido(row)
            if not codigo:
                erro += 1
                erros.append({"erro": "codigo vazio", "row": row})
                continue

            estoque = self._pick(row, "estoque", "saldo", "quantidade")
            preco = self._pick(
                row,
                "preco",
                "preco_venda",
                "valor",
                "valor_venda",
            )

            try:
                ok, resp = self.api.update_stock(
                    codigo=codigo,
                    estoque=self._to_float(estoque) or 0,
                    deposito_id=deposito_id,
                    preco=self._to_float(preco),
                )
            except Exception as e:
                ok, resp = False, str(e)

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(resp)

        resultado = {
            "ok": erro == 0 and sucesso > 0,
            "operacao": "update_stocks",
            "total": len(registros),
            "sucesso": sucesso,
            "erro": erro,
            "erros": erros,
            "detalhes": {"deposito_id": deposito_id},
        }
        return resultado["ok"], resultado

    # =========================
    # DATAFRAME
    # =========================
    def produtos_to_df(self, payload: Any) -> pd.DataFrame:
        if not isinstance(payload, list):
            return pd.DataFrame()

        rows: List[Dict[str, Any]] = []

        for item in payload:
            if not isinstance(item, dict):
                continue

            rows.append(
                {
                    "id": self._pick(item, "id"),
                    "codigo": self._pick(item, "codigo"),
                    "nome": self._pick(item, "nome"),
                    "preco": self._pick(item, "preco"),
                }
            )

        return pd.DataFrame(rows)
