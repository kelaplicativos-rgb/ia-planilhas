from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from bling_app_zero.services.bling.api import BlingServices


class BlingSync:
    def __init__(self, user_key: str = "default") -> None:
        self.user_key = str(user_key or "default").strip() or "default"
        self.services = BlingServices(user_key=self.user_key)

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _safe_df(df: Any) -> pd.DataFrame:
        if isinstance(df, pd.DataFrame):
            return df.copy()
        return pd.DataFrame()

    @staticmethod
    def _clean_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _normalize_rows(rows: Any) -> List[Dict[str, Any]]:
        if isinstance(rows, pd.DataFrame):
            try:
                df = rows.copy()
                df = df.fillna("")
                return df.to_dict(orient="records")
            except Exception:
                return []

        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]

        return []

    @staticmethod
    def _build_result(
        *,
        ok: bool,
        operacao: str,
        total: int,
        sucesso: int,
        erro: int,
        erros: Optional[List[Any]] = None,
        detalhes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "ok": bool(ok),
            "operacao": operacao,
            "total": int(total or 0),
            "sucesso": int(sucesso or 0),
            "erro": int(erro or 0),
            "erros": erros or [],
            "detalhes": detalhes or {},
        }

    @staticmethod
    def _registro_valido(row: Dict[str, Any]) -> bool:
        if not isinstance(row, dict):
            return False

        codigo = str(row.get("codigo") or row.get("sku") or "").strip()
        id_produto = str(row.get("id") or row.get("id_produto") or "").strip()

        return bool(codigo or id_produto)

    # =========================
    # PRODUTOS
    # =========================
    def sync_produtos(self, rows: Any) -> Dict[str, Any]:
        registros = self._normalize_rows(rows)
        registros = [r for r in registros if self._registro_valido(r)]

        if not registros:
            return self._build_result(
                ok=False,
                operacao="produtos",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum produto válido para sincronizar."],
            )

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in registros:
            try:
                ok, resp = self.services.upsert_products([row])
            except Exception as e:
                ok, resp = False, str(e)

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(resp)

        return self._build_result(
            ok=erro == 0 and sucesso > 0,
            operacao="produtos",
            total=len(registros),
            sucesso=sucesso,
            erro=erro,
            erros=erros,
        )

    # =========================
    # ESTOQUE
    # =========================
    def sync_estoques(
        self,
        rows: Any,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        registros = self._normalize_rows(rows)
        registros = [r for r in registros if self._registro_valido(r)]

        if not registros:
            return self._build_result(
                ok=False,
                operacao="estoques",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum estoque válido para sincronizar."],
            )

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in registros:
            try:
                ok, resp = self.services.update_stocks(
                    [row],
                    deposito_id=deposito_id,
                )
            except Exception as e:
                ok, resp = False, str(e)

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(resp)

        return self._build_result(
            ok=erro == 0 and sucesso > 0,
            operacao="estoques",
            total=len(registros),
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={"deposito_id": deposito_id},
        )

    # =========================
    # DATAFRAME
    # =========================
    def sync_dataframe(
        self,
        df: pd.DataFrame,
        *,
        tipo: str,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        df_local = self._safe_df(df)

        if df_local.empty:
            return self._build_result(
                ok=False,
                operacao="dataframe",
                total=0,
                sucesso=0,
                erro=0,
                erros=["DataFrame vazio para sincronização."],
                detalhes={"tipo": tipo},
            )

        tipo_normalizado = self._clean_str(tipo).lower()

        if tipo_normalizado == "cadastro":
            return self.sync_produtos(df_local)

        if tipo_normalizado == "estoque":
            return self.sync_estoques(df_local, deposito_id=deposito_id)

        return self._build_result(
            ok=False,
            operacao="dataframe",
            total=len(df_local),
            sucesso=0,
            erro=0,
            erros=[f"Tipo inválido: {tipo}"],
            detalhes={"tipo": tipo},
        )

    # =========================
    # FLUXO COMPLETO
    # =========================
    def sync_tudo(
        self,
        *,
        df_produtos: Optional[pd.DataFrame] = None,
        df_estoques: Optional[pd.DataFrame] = None,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resultado_produtos = (
            self.sync_produtos(df_produtos)
            if isinstance(df_produtos, pd.DataFrame) and not df_produtos.empty
            else None
        )

        resultado_estoques = (
            self.sync_estoques(df_estoques, deposito_id=deposito_id)
            if isinstance(df_estoques, pd.DataFrame) and not df_estoques.empty
            else None
        )

        total = 0
        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for r in [resultado_produtos, resultado_estoques]:
            if not isinstance(r, dict):
                continue

            total += int(r.get("total", 0) or 0)
            sucesso += int(r.get("sucesso", 0) or 0)
            erro += int(r.get("erro", 0) or 0)

            lista_erros = r.get("erros", [])
            if isinstance(lista_erros, list):
                erros.extend(lista_erros)

        return self._build_result(
            ok=erro == 0 and total > 0 and sucesso > 0,
            operacao="sync_tudo",
            total=total,
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={
                "produtos": resultado_produtos,
                "estoques": resultado_estoques,
                "deposito_id": deposito_id,
            },
        )
