from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

try:
    from bling_app_zero.services.bling.api import BlingServices
except ImportError:
    from bling_app_zero.core.bling_api import BlingAPIClient


    class BlingServices:
        def __init__(self, user_key: str = "default") -> None:
            self.api = BlingAPIClient(user_key=user_key)

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

                texto = str(value).strip()
                if not texto:
                    return None

                texto = texto.replace("R$", "").replace(" ", "")
                if "," in texto:
                    texto = texto.replace(".", "").replace(",", ".")
                else:
                    texto = texto.replace(",", "")

                return float(texto)
            except Exception:
                return None

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
                preco = self._pick(row, "preco", "preco_venda", "valor", "valor_venda")

                ok, resp = self.api.update_stock(
                    codigo=str(codigo or "").strip(),
                    estoque=self._to_float(estoque) or 0,
                    deposito_id=deposito_id,
                    preco=self._to_float(preco),
                )

                if ok:
                    sucesso += 1
                else:
                    erro += 1
                    erros.append(resp)

            return sucesso, erro, erros


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
                return rows.fillna("").to_dict(orient="records")
            except Exception:
                return []

        if isinstance(rows, list):
            validos: List[Dict[str, Any]] = []
            for item in rows:
                if isinstance(item, dict):
                    validos.append(item)
            return validos

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

    # =========================
    # PRODUTOS
    # =========================
    def sync_produtos(self, rows: Any) -> Dict[str, Any]:
        registros = self._normalize_rows(rows)

        if not registros:
            return self._build_result(
                ok=False,
                operacao="produtos",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum produto válido para sincronizar."],
            )

        sucesso, erro, erros = self.services.upsert_products(registros)

        return self._build_result(
            ok=erro == 0,
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

        if not registros:
            return self._build_result(
                ok=False,
                operacao="estoques",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum estoque válido para sincronizar."],
            )

        sucesso, erro, erros = self.services.update_stocks(
            registros,
            deposito_id=deposito_id,
        )

        return self._build_result(
            ok=erro == 0,
            operacao="estoques",
            total=len(registros),
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={"deposito_id": deposito_id},
        )

    # =========================
    # FLUXO POR DATAFRAME
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
            erros=[f"Tipo de sincronização inválido: {tipo}"],
            detalhes={"tipo": tipo, "deposito_id": deposito_id},
        )

    # =========================
    # FLUXO COMBINADO
    # =========================
    def sync_tudo(
        self,
        *,
        df_produtos: Optional[pd.DataFrame] = None,
        df_estoques: Optional[pd.DataFrame] = None,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resultado_produtos = None
        resultado_estoques = None

        if isinstance(df_produtos, pd.DataFrame) and not df_produtos.empty:
            resultado_produtos = self.sync_produtos(df_produtos)

        if isinstance(df_estoques, pd.DataFrame) and not df_estoques.empty:
            resultado_estoques = self.sync_estoques(
                df_estoques,
                deposito_id=deposito_id,
            )

        total = 0
        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for resultado in (resultado_produtos, resultado_estoques):
            if not isinstance(resultado, dict):
                continue

            total += int(resultado.get("total", 0) or 0)
            sucesso += int(resultado.get("sucesso", 0) or 0)
            erro += int(resultado.get("erro", 0) or 0)

            lista_erros = resultado.get("erros") or []
            if isinstance(lista_erros, list):
                erros.extend(lista_erros)

        return self._build_result(
            ok=erro == 0 and total > 0,
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
