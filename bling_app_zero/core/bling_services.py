from __future__ import annotations

from typing import Any, Dict, List, Optional

import time

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
    def _safe_float(valor: Any) -> float:
        try:
            if valor is None or valor == "":
                return 0.0

            texto = str(valor).replace("R$", "").replace(" ", "")
            texto = texto.replace(".", "").replace(",", ".")

            return float(texto)
        except Exception:
            return 0.0

    # =========================
    # PRODUTOS
    # =========================
    def enviar_produtos(
        self,
        rows: List[Dict[str, Any]],
        delay: float = 0.1,  # evita bloqueio API
    ) -> Dict[str, Any]:

        sucesso = 0
        erro = 0
        detalhes: List[Any] = []

        for idx, row in enumerate(rows):
            codigo = self._pick(row, "codigo", "sku")

            if not codigo:
                erro += 1
                detalhes.append({"linha": idx, "erro": "Código vazio"})
                continue

            ok, resp = self.api.upsert_product(row)

            if ok:
                sucesso += 1
            else:
                erro += 1
                detalhes.append({
                    "linha": idx,
                    "codigo": codigo,
                    "erro": resp,
                })

            # 🔥 proteção anti rate limit
            if delay > 0:
                time.sleep(delay)

        return {
            "sucesso": sucesso,
            "erro": erro,
            "detalhes": detalhes,
        }

    # =========================
    # ESTOQUE
    # =========================
    def enviar_estoque(
        self,
        rows: List[Dict[str, Any]],
        deposito_id: Optional[str] = None,
        delay: float = 0.1,
    ) -> Dict[str, Any]:

        sucesso = 0
        erro = 0
        detalhes: List[Any] = []

        for idx, row in enumerate(rows):
            codigo = self._pick(row, "codigo", "sku")
            estoque = self._pick(row, "estoque", "saldo", "quantidade")

            if not codigo:
                erro += 1
                detalhes.append({"linha": idx, "erro": "Código vazio"})
                continue

            ok, resp = self.api.update_stock(
                codigo=str(codigo),
                estoque=self._safe_float(estoque),
                deposito_id=deposito_id,
            )

            if ok:
                sucesso += 1
            else:
                erro += 1
                detalhes.append({
                    "linha": idx,
                    "codigo": codigo,
                    "erro": resp,
                })

            if delay > 0:
                time.sleep(delay)

        return {
            "sucesso": sucesso,
            "erro": erro,
            "detalhes": detalhes,
        }
