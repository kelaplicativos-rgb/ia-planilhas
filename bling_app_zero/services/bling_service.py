from __future__ import annotations

from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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
    # RETRY AUTOMÁTICO
    # =========================
    def _executar_com_retry(self, func, tentativas=3, delay=1):
        ultimo_erro = None

        for _ in range(tentativas):
            ok, resp = func()

            if ok:
                return True, resp

            ultimo_erro = resp
            time.sleep(delay)

        return False, ultimo_erro

    # =========================
    # EXECUÇÃO PARALELA
    # =========================
    def _executar_paralelo(self, tarefas, max_workers=5):
        resultados = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(t) for t in tarefas]

            for future in as_completed(futures):
                try:
                    resultados.append(future.result())
                except Exception as e:
                    resultados.append((False, str(e)))

        return resultados

    # =========================
    # ENVIO DE PRODUTOS (TURBO)
    # =========================
    def enviar_produtos_df(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        if df is None or df.empty:
            return False, {"erro": "DataFrame vazio para envio de produtos."}

        tarefas = []

        for _, row in df.iterrows():
            row_dict = row.to_dict()

            def task(r=row_dict):
                return self._executar_com_retry(
                    lambda: self.client.upsert_product(r)
                )

            tarefas.append(task)

        resultados = self._executar_paralelo(tarefas)

        return self._consolidar_resultados(resultados, df, "produto")

    # =========================
    # ENVIO DE ESTOQUE (TURBO)
    # =========================
    def enviar_estoque_df(
        self,
        df: pd.DataFrame,
        deposito_padrao: str | None = None,
    ) -> Tuple[bool, Dict[str, Any]]:

        if df is None or df.empty:
            return False, {"erro": "DataFrame vazio para envio de estoque."}

        tarefas = []

        for _, row in df.iterrows():
            row_dict = row.to_dict()

            def task(r=row_dict):
                codigo = r.get("codigo")
                saldo = r.get("saldo") or r.get("estoque") or 0
                deposito = r.get("deposito_id") or deposito_padrao

                return self._executar_com_retry(
                    lambda: self.client.update_stock(
                        codigo=codigo,
                        estoque=saldo,
                        deposito_id=deposito,
                    )
                )

            tarefas.append(task)

        resultados = self._executar_paralelo(tarefas)

        return self._consolidar_resultados(resultados, df, "estoque")

    # =========================
    # CONSOLIDADOR
    # =========================
    def _consolidar_resultados(self, resultados, df, tipo):
        logs = []
        sucesso = 0
        erro = 0

        for ok, resp in resultados:
            if ok:
                sucesso += 1
                logs.append(self._log("sucesso", f"{tipo} OK"))
            else:
                erro += 1
                logs.append(self._log("erro", f"{tipo} erro", resp))

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
