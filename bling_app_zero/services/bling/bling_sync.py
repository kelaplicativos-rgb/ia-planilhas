from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from bling_app_zero.services.bling.api import BlingServices


class BlingSync:
    def __init__(self, user_key: str = "default") -> None:
        self.user_key = self._safe_str(user_key) or "default"
        self.services = BlingServices(user_key=self.user_key)

    # =========================
    # CONFIG PRO
    # =========================
    BATCH_SIZE = 50

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _safe_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _safe_df(df: Any) -> pd.DataFrame:
        if isinstance(df, pd.DataFrame):
            try:
                return df.copy()
            except Exception:
                return df
        return pd.DataFrame()

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
    def _chunk(lista: List[Any], size: int) -> Iterable[List[Any]]:
        if size <= 0:
            size = 1

        for i in range(0, len(lista), size):
            yield lista[i : i + size]

    @classmethod
    def _registro_valido(cls, row: Dict[str, Any]) -> bool:
        if not isinstance(row, dict):
            return False

        codigo = cls._safe_str(
            row.get("codigo")
            or row.get("sku")
            or row.get("Código")
            or row.get("Codigo")
        )
        id_produto = cls._safe_str(
            row.get("id")
            or row.get("id_produto")
            or row.get("ID")
        )

        return bool(codigo or id_produto)

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
    def _extrair_lista_erros(payload: Any) -> List[Any]:
        if isinstance(payload, dict):
            erros = payload.get("erros", [])
            if isinstance(erros, list):
                return erros
            if erros not in (None, ""):
                return [erros]
            return []

        if isinstance(payload, list):
            return payload

        if payload not in (None, ""):
            return [payload]

        return []

    @staticmethod
    def _merge_detalhes(base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        resultado: Dict[str, Any] = {}

        if isinstance(base, dict):
            resultado.update(base)

        if isinstance(extra, dict):
            for chave, valor in extra.items():
                if chave not in resultado or resultado.get(chave) in (None, "", [], {}):
                    resultado[chave] = valor
                elif isinstance(resultado.get(chave), dict) and isinstance(valor, dict):
                    combinado = dict(resultado[chave])
                    combinado.update(valor)
                    resultado[chave] = combinado

        return resultado

    @classmethod
    def _resultado_from_service(
        cls,
        *,
        fallback_operacao: str,
        fallback_total: int,
        fallback_detalhes: Optional[Dict[str, Any]] = None,
        service_ok: bool,
        service_resp: Any,
    ) -> Dict[str, Any]:
        if isinstance(service_resp, dict):
            return cls._build_result(
                ok=bool(service_resp.get("ok", service_ok)),
                operacao=cls._safe_str(service_resp.get("operacao")) or fallback_operacao,
                total=int(service_resp.get("total", fallback_total) or fallback_total),
                sucesso=int(service_resp.get("sucesso", 0) or 0),
                erro=int(service_resp.get("erro", 0) or 0),
                erros=cls._extrair_lista_erros(service_resp),
                detalhes=cls._merge_detalhes(fallback_detalhes, service_resp.get("detalhes")),
            )

        erros = cls._extrair_lista_erros(service_resp)

        return cls._build_result(
            ok=bool(service_ok),
            operacao=fallback_operacao,
            total=int(fallback_total or 0),
            sucesso=int(fallback_total if service_ok else 0),
            erro=int(0 if service_ok else fallback_total),
            erros=erros,
            detalhes=fallback_detalhes or {},
        )

    @classmethod
    def _consolidar_lotes(
        cls,
        *,
        operacao: str,
        total_esperado: int,
        resultados: List[Dict[str, Any]],
        detalhes_finais: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        sucesso = 0
        erro = 0
        erros: List[Any] = []
        detalhes: Dict[str, Any] = {}

        for resultado in resultados:
            if not isinstance(resultado, dict):
                continue

            sucesso += int(resultado.get("sucesso", 0) or 0)
            erro += int(resultado.get("erro", 0) or 0)

            lista_erros = resultado.get("erros", [])
            if isinstance(lista_erros, list):
                erros.extend(lista_erros)
            elif lista_erros not in (None, ""):
                erros.append(lista_erros)

            detalhes = cls._merge_detalhes(detalhes, resultado.get("detalhes"))

        detalhes = cls._merge_detalhes(detalhes, detalhes_finais)

        total_real = sucesso + erro
        if total_real <= 0:
            total_real = int(total_esperado or 0)

        return cls._build_result(
            ok=(erro == 0 and sucesso > 0),
            operacao=operacao,
            total=total_real,
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes=detalhes,
        )

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

        resultados_lotes: List[Dict[str, Any]] = []

        for lote in self._chunk(registros, self.BATCH_SIZE):
            try:
                ok, resp = self.services.upsert_products(lote)
            except Exception as e:
                ok, resp = False, str(e)

            resultado_lote = self._resultado_from_service(
                fallback_operacao="upsert_products",
                fallback_total=len(lote),
                fallback_detalhes={},
                service_ok=ok,
                service_resp=resp,
            )
            resultados_lotes.append(resultado_lote)

        return self._consolidar_lotes(
            operacao="produtos",
            total_esperado=len(registros),
            resultados=resultados_lotes,
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

        deposito_id = self._safe_str(deposito_id)

        if not registros:
            return self._build_result(
                ok=False,
                operacao="estoques",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum estoque válido para sincronizar."],
                detalhes={"deposito_id": deposito_id or None},
            )

        resultados_lotes: List[Dict[str, Any]] = []

        for lote in self._chunk(registros, self.BATCH_SIZE):
            try:
                ok, resp = self.services.update_stocks(
                    lote,
                    deposito_id=deposito_id or None,
                )
            except Exception as e:
                ok, resp = False, str(e)

            resultado_lote = self._resultado_from_service(
                fallback_operacao="update_stocks",
                fallback_total=len(lote),
                fallback_detalhes={"deposito_id": deposito_id or None},
                service_ok=ok,
                service_resp=resp,
            )
            resultados_lotes.append(resultado_lote)

        return self._consolidar_lotes(
            operacao="estoques",
            total_esperado=len(registros),
            resultados=resultados_lotes,
            detalhes_finais={"deposito_id": deposito_id or None},
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

        tipo_normalizado = self._safe_str(tipo).lower()

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

        for resultado in (resultado_produtos, resultado_estoques):
            if not isinstance(resultado, dict):
                continue

            total += int(resultado.get("total", 0) or 0)
            sucesso += int(resultado.get("sucesso", 0) or 0)
            erro += int(resultado.get("erro", 0) or 0)

            lista_erros = resultado.get("erros", [])
            if isinstance(lista_erros, list):
                erros.extend(lista_erros)
            elif lista_erros not in (None, ""):
                erros.append(lista_erros)

        return self._build_result(
            ok=(erro == 0 and total > 0 and sucesso > 0),
            operacao="sync_tudo",
            total=total,
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={
                "produtos": resultado_produtos,
                "estoques": resultado_estoques,
                "deposito_id": self._safe_str(deposito_id) or None,
            },
        )


# Alias para compatibilidade com o core
BlingSyncService = BlingSync
