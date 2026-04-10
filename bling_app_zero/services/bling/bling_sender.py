from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from bling_app_zero.services.bling.bling_sync import BlingSync


class BlingSender:
    def __init__(self, user_key: str = "default") -> None:
        self.user_key = str(user_key or "default").strip() or "default"
        self.sync = BlingSync(user_key=self.user_key)

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
    def _build_result(
        *,
        ok: bool,
        operacao: str,
        total: int = 0,
        sucesso: int = 0,
        erro: int = 0,
        erros: Optional[list] = None,
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
    def _df_tem_dados(df: pd.DataFrame) -> bool:
        try:
            return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
        except Exception:
            return False

    # =========================
    # ENVIO POR TIPO
    # =========================
    def enviar_dataframe(
        self,
        df: pd.DataFrame,
        *,
        tipo: str,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        df_local = self._safe_df(df)
        tipo_normalizado = self._clean_str(tipo).lower()

        if not self._df_tem_dados(df_local):
            return self._build_result(
                ok=False,
                operacao="enviar_dataframe",
                erros=["DataFrame vazio para envio ao Bling."],
                detalhes={
                    "tipo": tipo,
                    "deposito_id": deposito_id,
                },
            )

        if tipo_normalizado not in {"cadastro", "estoque"}:
            return self._build_result(
                ok=False,
                operacao="enviar_dataframe",
                total=len(df_local),
                erros=[f"Tipo inválido para envio: {tipo}"],
                detalhes={
                    "tipo": tipo,
                    "deposito_id": deposito_id,
                },
            )

        try:
            resultado = self.sync.sync_dataframe(
                df_local,
                tipo=tipo_normalizado,
                deposito_id=deposito_id,
            )
        except Exception as e:
            return self._build_result(
                ok=False,
                operacao="enviar_dataframe",
                total=len(df_local),
                erro=len(df_local),
                erros=[str(e)],
                detalhes={
                    "tipo": tipo,
                    "deposito_id": deposito_id,
                },
            )

        if not isinstance(resultado, dict):
            return self._build_result(
                ok=False,
                operacao="enviar_dataframe",
                total=len(df_local),
                erro=len(df_local),
                erros=["Resposta inválida no envio para o Bling."],
                detalhes={
                    "tipo": tipo,
                    "deposito_id": deposito_id,
                },
            )

        resultado["operacao"] = "enviar_dataframe"

        detalhes = resultado.get("detalhes", {})
        if not isinstance(detalhes, dict):
            detalhes = {}

        detalhes["tipo"] = tipo_normalizado
        detalhes["deposito_id"] = deposito_id
        resultado["detalhes"] = detalhes

        return resultado

    # =========================
    # ENVIO DE CADASTRO
    # =========================
    def enviar_cadastro(self, df: pd.DataFrame) -> Dict[str, Any]:
        return self.enviar_dataframe(
            df,
            tipo="cadastro",
            deposito_id=None,
        )

    # =========================
    # ENVIO DE ESTOQUE
    # =========================
    def enviar_estoque(
        self,
        df: pd.DataFrame,
        *,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.enviar_dataframe(
            df,
            tipo="estoque",
            deposito_id=deposito_id,
        )

    # =========================
    # ENVIO AUTOMÁTICO PELO TIPO
    # =========================
    def enviar_por_tipo(
        self,
        *,
        tipo: str,
        df_cadastro: Optional[pd.DataFrame] = None,
        df_estoque: Optional[pd.DataFrame] = None,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tipo_normalizado = self._clean_str(tipo).lower()

        if tipo_normalizado == "cadastro":
            return self.enviar_cadastro(self._safe_df(df_cadastro))

        if tipo_normalizado == "estoque":
            return self.enviar_estoque(
                self._safe_df(df_estoque),
                deposito_id=deposito_id,
            )

        return self._build_result(
            ok=False,
            operacao="enviar_por_tipo",
            erros=[f"Tipo inválido para envio: {tipo}"],
            detalhes={"tipo": tipo, "deposito_id": deposito_id},
        )

    # =========================
    # ENVIO COMPLETO
    # =========================
    def enviar_tudo(
        self,
        *,
        df_cadastro: Optional[pd.DataFrame] = None,
        df_estoque: Optional[pd.DataFrame] = None,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        df_cadastro_local = self._safe_df(df_cadastro)
        df_estoque_local = self._safe_df(df_estoque)

        tem_cadastro = self._df_tem_dados(df_cadastro_local)
        tem_estoque = self._df_tem_dados(df_estoque_local)

        if not tem_cadastro and not tem_estoque:
            return self._build_result(
                ok=False,
                operacao="enviar_tudo",
                erros=["Nenhum DataFrame válido disponível para envio."],
                detalhes={"deposito_id": deposito_id},
            )

        resultado_cadastro = (
            self.enviar_cadastro(df_cadastro_local) if tem_cadastro else None
        )

        resultado_estoque = (
            self.enviar_estoque(df_estoque_local, deposito_id=deposito_id)
            if tem_estoque
            else None
        )

        total = 0
        sucesso = 0
        erro = 0
        erros = []

        for resultado in [resultado_cadastro, resultado_estoque]:
            if not isinstance(resultado, dict):
                continue

            total += int(resultado.get("total", 0) or 0)
            sucesso += int(resultado.get("sucesso", 0) or 0)
            erro += int(resultado.get("erro", 0) or 0)

            lista_erros = resultado.get("erros", [])
            if isinstance(lista_erros, list):
                erros.extend(lista_erros)

        return self._build_result(
            ok=erro == 0 and sucesso > 0,
            operacao="enviar_tudo",
            total=total,
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={
                "cadastro": resultado_cadastro,
                "estoque": resultado_estoque,
                "deposito_id": deposito_id,
            },
        )
