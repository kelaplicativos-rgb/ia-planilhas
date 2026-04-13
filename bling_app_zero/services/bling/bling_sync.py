from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from bling_app_zero.services.bling.api import BlingServices


class BlingSync:
    """
    Camada de orquestração entre o DataFrame final da aplicação
    e os serviços do Bling.

    Objetivos:
    - manter cadastro e estoque separados;
    - permitir fluxo combinado (cadastro + estoque);
    - preparar o caminho para sincronização automática futura;
    - devolver retornos consistentes para a UI.
    """

    BATCH_SIZE = 50

    def __init__(self, user_key: str = "default") -> None:
        self.user_key = str(user_key or "default").strip() or "default"
        self.services = BlingServices(user_key=self.user_key)

    # =========================================================
    # HELPERS
    # =========================================================
    @staticmethod
    def _safe_df(df: Any) -> pd.DataFrame:
        if isinstance(df, pd.DataFrame):
            try:
                return df.copy()
            except Exception:
                return df
        return pd.DataFrame()

    @staticmethod
    def _clean_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            if value is None or value == "":
                return None

            texto = str(value).strip()
            if not texto:
                return None

            texto = texto.replace("R$", "").replace(" ", "")
            if "," in texto and "." in texto:
                texto = texto.replace(".", "").replace(",", ".")
            elif "," in texto:
                texto = texto.replace(",", ".")

            return float(texto)
        except Exception:
            return None

    def _normalize_rows(self, rows: Any) -> List[Dict[str, Any]]:
        if isinstance(rows, pd.DataFrame):
            try:
                df = rows.copy().fillna("")
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

    def _pick(self, row: Dict[str, Any], *keys: str) -> Any:
        if not isinstance(row, dict):
            return None

        for key in keys:
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
        return None

    def _resolver_codigo(self, row: Dict[str, Any]) -> str:
        return self._clean_str(
            self._pick(
                row,
                "codigo",
                "Código",
                "sku",
                "SKU",
                "codigo_sku",
                "Código do produto",
            )
        )

    def _resolver_nome(self, row: Dict[str, Any]) -> str:
        return self._clean_str(
            self._pick(
                row,
                "nome",
                "Nome",
                "descricao",
                "Descrição",
                "Descrição Curta",
                "titulo",
                "Título",
            )
        )

    def _resolver_estoque(self, row: Dict[str, Any]) -> Optional[float]:
        return self._to_float(
            self._pick(
                row,
                "estoque",
                "Estoque",
                "saldo",
                "Saldo",
                "quantidade",
                "Quantidade",
            )
        )

    def _resolver_preco(self, row: Dict[str, Any]) -> Optional[float]:
        return self._to_float(
            self._pick(
                row,
                "preco",
                "Preço de venda",
                "Preço unitário (OBRIGATÓRIO)",
                "preco_venda",
                "valor",
                "valor_venda",
            )
        )

    def _registro_tem_cadastro(self, row: Dict[str, Any]) -> bool:
        codigo = self._resolver_codigo(row)
        nome = self._resolver_nome(row)
        return bool(codigo and nome)

    def _registro_tem_estoque(self, row: Dict[str, Any]) -> bool:
        codigo = self._resolver_codigo(row)
        return bool(codigo)

    @staticmethod
    def _chunk(lista: List[Any], size: int):
        for i in range(0, len(lista), size):
            yield lista[i : i + size]

    # =========================================================
    # NORMALIZAÇÃO DE LINHA
    # =========================================================
    def _normalizar_row_produto(self, row: Dict[str, Any]) -> Dict[str, Any]:
        codigo = self._resolver_codigo(row)
        nome = self._resolver_nome(row)
        preco = self._resolver_preco(row)

        normalizado: Dict[str, Any] = {
            "codigo": codigo,
            "nome": nome,
            "preco": preco if preco is not None else row.get("preco"),
            "situacao": self._pick(row, "situacao", "Situação", "status", "Status") or "ativo",
            "unidade": self._pick(row, "unidade", "Unidade") or "UN",
        }

        # Mantém campos extras importantes se existirem
        for origem, destino in [
            ("descricao_curta", "descricao_curta"),
            ("Descrição Curta", "descricao_curta"),
            ("marca", "marca"),
            ("Marca", "marca"),
            ("ncm", "ncm"),
            ("NCM", "ncm"),
            ("gtin", "gtin"),
            ("GTIN", "gtin"),
            ("ean", "gtin"),
            ("EAN", "gtin"),
        ]:
            valor = row.get(origem)
            if valor not in (None, ""):
                normalizado[destino] = valor

        return normalizado

    def _normalizar_row_estoque(self, row: Dict[str, Any]) -> Dict[str, Any]:
        codigo = self._resolver_codigo(row)
        estoque = self._resolver_estoque(row)
        preco = self._resolver_preco(row)

        return {
            "codigo": codigo,
            "estoque": 0 if estoque is None else estoque,
            "preco": preco,
        }

    # =========================================================
    # PRODUTOS
    # =========================================================
    def sync_produtos(self, rows: Any) -> Dict[str, Any]:
        registros_brutos = self._normalize_rows(rows)
        registros = [
            self._normalizar_row_produto(r)
            for r in registros_brutos
            if self._registro_tem_cadastro(r)
        ]

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

        for lote in self._chunk(registros, self.BATCH_SIZE):
            try:
                ok, resp = self.services.upsert_products(lote)
            except Exception as e:
                ok, resp = False, str(e)

            if ok:
                sucesso += len(lote)
            else:
                erro += len(lote)
                erros.append(resp)

        return self._build_result(
            ok=erro == 0 and sucesso > 0,
            operacao="produtos",
            total=len(registros),
            sucesso=sucesso,
            erro=erro,
            erros=erros,
        )

    # =========================================================
    # ESTOQUE
    # =========================================================
    def sync_estoques(
        self,
        rows: Any,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        registros_brutos = self._normalize_rows(rows)
        registros = [
            self._normalizar_row_estoque(r)
            for r in registros_brutos
            if self._registro_tem_estoque(r)
        ]

        if not registros:
            return self._build_result(
                ok=False,
                operacao="estoques",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum estoque válido para sincronizar."],
                detalhes={"deposito_id": deposito_id},
            )

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for lote in self._chunk(registros, self.BATCH_SIZE):
            try:
                ok, resp = self.services.update_stocks(
                    lote,
                    deposito_id=deposito_id,
                )
            except Exception as e:
                ok, resp = False, str(e)

            if ok:
                sucesso += len(lote)
            else:
                erro += len(lote)
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

    # =========================================================
    # FLUXO COMPLETO
    # =========================================================
    def sync_catalogo_completo(
        self,
        rows: Any,
        *,
        deposito_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fluxo que você descreveu:
        - se não existir no Bling, cadastra;
        - se já existir, atualiza;
        - depois atualiza o estoque.
        """
        registros_df = self._safe_df(rows)

        if registros_df.empty:
            return self._build_result(
                ok=False,
                operacao="catalogo_completo",
                total=0,
                sucesso=0,
                erro=0,
                erros=["DataFrame vazio para sincronização completa."],
                detalhes={"deposito_id": deposito_id},
            )

        resultado_produtos = self.sync_produtos(registros_df)
        resultado_estoques = self.sync_estoques(registros_df, deposito_id=deposito_id)

        total = int(resultado_produtos.get("total", 0) or 0)
        sucesso = int(resultado_produtos.get("sucesso", 0) or 0) + int(
            resultado_estoques.get("sucesso", 0) or 0
        )
        erro = int(resultado_produtos.get("erro", 0) or 0) + int(
            resultado_estoques.get("erro", 0) or 0
        )

        erros: List[Any] = []
        if isinstance(resultado_produtos.get("erros"), list):
            erros.extend(resultado_produtos["erros"])
        if isinstance(resultado_estoques.get("erros"), list):
            erros.extend(resultado_estoques["erros"])

        return self._build_result(
            ok=bool(resultado_produtos.get("ok")) and bool(resultado_estoques.get("ok")),
            operacao="catalogo_completo",
            total=total,
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={
                "deposito_id": deposito_id,
                "produtos": resultado_produtos,
                "estoques": resultado_estoques,
            },
        )

    # =========================================================
    # DATAFRAME
    # =========================================================
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
                detalhes={"tipo": tipo, "deposito_id": deposito_id},
            )

        tipo_normalizado = self._clean_str(tipo).lower()

        if tipo_normalizado in {"cadastro", "produto", "produtos"}:
            return self.sync_produtos(df_local)

        if tipo_normalizado in {"estoque", "estoques"}:
            return self.sync_estoques(df_local, deposito_id=deposito_id)

        if tipo_normalizado in {
            "catalogo",
            "catalogo_completo",
            "cadastro_estoque",
            "completo",
            "full",
        }:
            return self.sync_catalogo_completo(df_local, deposito_id=deposito_id)

        return self._build_result(
            ok=False,
            operacao="dataframe",
            total=len(df_local),
            sucesso=0,
            erro=0,
            erros=[f"Tipo inválido: {tipo}"],
            detalhes={"tipo": tipo, "deposito_id": deposito_id},
        )

    # =========================================================
    # FLUXO DUPLO EXPLÍCITO
    # =========================================================
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

        for resultado in [resultado_produtos, resultado_estoques]:
            if not isinstance(resultado, dict):
                continue

            total += int(resultado.get("total", 0) or 0)
            sucesso += int(resultado.get("sucesso", 0) or 0)
            erro += int(resultado.get("erro", 0) or 0)

            if isinstance(resultado.get("erros"), list):
                erros.extend(resultado["erros"])

        return self._build_result(
            ok=erro == 0 and sucesso > 0,
            operacao="sync_tudo",
            total=total,
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={
                "deposito_id": deposito_id,
                "produtos": resultado_produtos,
                "estoques": resultado_estoques,
            },
        )


# Alias de compatibilidade
BlingSyncService = BlingSync
