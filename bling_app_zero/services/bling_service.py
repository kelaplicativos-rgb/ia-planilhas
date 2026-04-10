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
    # HELPERS
    # =========================
    def _safe_str(self, valor: Any) -> str:
        try:
            if valor is None:
                return ""
            texto = str(valor).strip()
            if texto.lower() == "nan":
                return ""
            return texto
        except Exception:
            return ""

    def _safe_float(self, valor: Any, default: float = 0.0) -> float:
        try:
            if valor is None:
                return default

            if isinstance(valor, str):
                texto = valor.strip()
                if not texto:
                    return default
                texto = texto.replace("R$", "").replace("r$", "")
                texto = texto.replace(".", "").replace(",", ".")
                valor = texto

            if pd.isna(valor):
                return default

            return float(valor)
        except Exception:
            return default

    def _get_first_value(self, row: Dict[str, Any], *keys: str) -> Any:
        if not isinstance(row, dict):
            return None

        mapa_normalizado: Dict[str, Any] = {}
        for k, v in row.items():
            try:
                mapa_normalizado[str(k).strip().lower()] = v
            except Exception:
                continue

        for key in keys:
            valor = mapa_normalizado.get(str(key).strip().lower())
            if valor is None:
                continue

            if isinstance(valor, str) and not valor.strip():
                continue

            try:
                if pd.isna(valor):
                    continue
            except Exception:
                pass

            return valor

        return None

    # =========================
    # RETRY AUTOMÁTICO
    # =========================
    def _executar_com_retry(self, func, tentativas: int = 3, delay: float = 1.0):
        ultimo_erro = None

        for tentativa in range(1, tentativas + 1):
            try:
                ok, resp = func()
            except Exception as exc:
                ok, resp = False, f"Erro interno na tentativa {tentativa}: {exc}"

            if ok:
                return True, resp

            ultimo_erro = resp

            if tentativa < tentativas:
                time.sleep(delay)

        return False, ultimo_erro

    # =========================
    # EXECUÇÃO PARALELA
    # =========================
    def _executar_paralelo(self, tarefas, max_workers: int = 5):
        resultados = []

        if not tarefas:
            return resultados

        max_workers = max(1, min(int(max_workers or 1), len(tarefas)))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(t) for t in tarefas]

            for future in as_completed(futures):
                try:
                    resultados.append(future.result())
                except Exception as exc:
                    resultados.append(
                        (
                            False,
                            {
                                "erro": f"Falha na execução paralela: {exc}",
                            },
                        )
                    )

        return resultados

    # =========================
    # ENVIO DE PRODUTOS (TURBO)
    # =========================
    def enviar_produtos_df(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return False, {"erro": "DataFrame vazio para envio de produtos."}

        tarefas = []

        for idx, row in df.iterrows():
            row_dict = row.to_dict()

            def task(r=row_dict, i=idx):
                codigo = self._safe_str(
                    self._get_first_value(r, "codigo", "Código", "sku", "SKU")
                )

                ok, resp = self._executar_com_retry(
                    lambda: self.client.upsert_product(r)
                )

                return ok, {
                    "indice": i,
                    "codigo": codigo,
                    "resposta": resp,
                }

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

        if not isinstance(df, pd.DataFrame) or df.empty:
            return False, {"erro": "DataFrame vazio para envio de estoque."}

        tarefas = []

        for idx, row in df.iterrows():
            row_dict = row.to_dict()

            def task(r=row_dict, i=idx):
                codigo = self._safe_str(
                    self._get_first_value(r, "codigo", "Código", "sku", "SKU")
                )

                saldo = self._safe_float(
                    self._get_first_value(
                        r,
                        "saldo",
                        "Saldo",
                        "estoque",
                        "Estoque",
                        "quantidade",
                        "Quantidade",
                    ),
                    default=0.0,
                )

                deposito = self._safe_str(
                    self._get_first_value(
                        r,
                        "deposito_id",
                        "depósito_id",
                        "deposito",
                        "depósito",
                    )
                ) or self._safe_str(deposito_padrao)

                preco = self._get_first_value(
                    r,
                    "preco",
                    "preço",
                    "preco unitario",
                    "preço unitário",
                    "preco de venda",
                    "preço de venda",
                )
                preco_float = self._safe_float(preco, default=0.0) if preco is not None else None

                if not codigo:
                    return False, {
                        "indice": i,
                        "codigo": "",
                        "resposta": "Código do produto ausente para atualização de estoque.",
                    }

                ok, resp = self._executar_com_retry(
                    lambda: self.client.update_stock(
                        codigo=codigo,
                        estoque=saldo,
                        deposito_id=deposito or None,
                        preco=preco_float if preco is not None else None,
                    )
                )

                return ok, {
                    "indice": i,
                    "codigo": codigo,
                    "resposta": resp,
                }

            tarefas.append(task)

        resultados = self._executar_paralelo(tarefas)

        return self._consolidar_resultados(resultados, df, "estoque")

    # =========================
    # CONSOLIDADOR
    # =========================
    def _consolidar_resultados(
        self,
        resultados: List[Tuple[bool, Any]],
        df: pd.DataFrame,
        tipo: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        logs: List[Dict[str, Any]] = []
        sucesso = 0
        erro = 0

        for ok, resp in resultados:
            extra = resp if isinstance(resp, dict) else {"resposta": resp}

            indice = extra.get("indice")
            codigo = self._safe_str(extra.get("codigo"))
            resposta_real = extra.get("resposta", extra)

            sufixo = []
            if indice is not None:
                sufixo.append(f"linha={indice}")
            if codigo:
                sufixo.append(f"codigo={codigo}")

            detalhe = f" ({', '.join(sufixo)})" if sufixo else ""

            if ok:
                sucesso += 1
                logs.append(
                    self._log(
                        "sucesso",
                        f"{tipo} OK{detalhe}",
                        resposta_real,
                    )
                )
            else:
                erro += 1
                logs.append(
                    self._log(
                        "erro",
                        f"{tipo} erro{detalhe}",
                        resposta_real,
                    )
                )

        total = len(df) if isinstance(df, pd.DataFrame) else len(resultados)
        houve_sucesso = sucesso > 0

        return houve_sucesso, {
            "total": total,
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

        tipo_normalizado = self._safe_str(tipo).lower()

        if tipo_normalizado == "cadastro":
            return self.enviar_produtos_df(df)

        if tipo_normalizado == "estoque":
            return self.enviar_estoque_df(df, deposito_padrao)

        return False, {"erro": f"Tipo inválido: {tipo}"}

    # =========================
    # TESTE DE CONEXÃO
    # =========================
    def testar_conexao(self) -> Tuple[bool, Any]:
        ok, resp = self.client.request("GET", "/produtos", params={"limite": 1})

        if ok:
            return True, {"mensagem": "Conexão com Bling OK"}

        return False, resp
