from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

from bling_app_zero.core.bling_api import BlingAPIClient


class BlingService:
    def __init__(self, user_key: str = "default") -> None:
        self.client = BlingAPIClient(user_key=user_key)

    # =========================
    # LOG PADRÃO
    # =========================
    def _log(self, tipo: str, mensagem: str, extra: Any = None) -> Dict[str, Any]:
        return {
            "tipo": tipo,
            "mensagem": mensagem,
            "extra": extra,
        }

    # =========================
    # ENVIO DE PRODUTOS
    # =========================
    def enviar_produtos_df(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        if df is None or df.empty:
            return False, {"erro": "DataFrame vazio para envio de produtos."}

        logs: List[Dict[str, Any]] = []
        sucesso = 0
        erro = 0

        for i, row in df.iterrows():
            row_dict = row.to_dict()

            ok, resp = self.client.upsert_product(row_dict)

            if ok:
                sucesso += 1
                logs.append(self._log("sucesso", f"Produto enviado: {row_dict.get('codigo')}"))
            else:
                erro += 1
                logs.append(self._log("erro", "Erro ao enviar produto", resp))

        return True, {
            "total": len(df),
            "sucesso": sucesso,
            "erro": erro,
            "logs": logs,
        }

    # =========================
    # ENVIO DE ESTOQUE
    # =========================
    def enviar_estoque_df(
        self,
        df: pd.DataFrame,
        deposito_padrao: str | None = None,
    ) -> Tuple[bool, Dict[str, Any]]:

        if df is None or df.empty:
            return False, {"erro": "DataFrame vazio para envio de estoque."}

        logs: List[Dict[str, Any]] = []
        sucesso = 0
        erro = 0

        for i, row in df.iterrows():
            row_dict = row.to_dict()

            codigo = row_dict.get("codigo")
            saldo = row_dict.get("saldo") or row_dict.get("estoque") or 0
            deposito = row_dict.get("deposito_id") or deposito_padrao

            ok, resp = self.client.update_stock(
                codigo=codigo,
                estoque=saldo,
                deposito_id=deposito,
            )

            if ok:
                sucesso += 1
                logs.append(self._log("sucesso", f"Estoque enviado: {codigo}"))
            else:
                erro += 1
                logs.append(self._log("erro", f"Erro estoque: {codigo}", resp))

        return True, {
            "total": len(df),
            "sucesso": sucesso,
            "erro": erro,
            "logs": logs,
        }

    # =========================
    # ENVIO INTELIGENTE
    # =========================
    def enviar_dataframe_completo(
        self,
        df: pd.DataFrame,
        tipo: str,
        deposito_padrao: str | None = None,
    ) -> Tuple[bool, Dict[str, Any]]:

        tipo = str(tipo or "").lower().strip()

        if tipo == "cadastro":
            return self.enviar_produtos_df(df)

        if tipo == "estoque":
            return self.enviar_estoque_df(df, deposito_padrao)

        return False, {"erro": f"Tipo inválido: {tipo}"}

    # =========================
    # TESTE DE CONEXÃO
    # =========================
    def testar_conexao(self) -> Tuple[bool, Any]:
        ok, resp = self.client.request("GET", "/produtos", params={"limite": 1})

        if ok:
            return True, {"mensagem": "Conexão com Bling OK"}
        else:
            return False, resp
