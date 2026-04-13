from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from bling_app_zero.services.bling.bling_api_client import BlingAPIClient


class BlingServices:
    def __init__(self, user_key: str = "default") -> None:
        self.user_key = self._safe_str(user_key) or "default"
        self.api = BlingAPIClient(user_key=self.user_key)

    # =========================
    # CONFIG PRO
    # =========================
    BATCH_SIZE = 50

    # =========================
    # HELPERS BASE
    # =========================
    @staticmethod
    def _safe_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

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

            if "," in texto and "." in texto:
                texto = texto.replace(".", "").replace(",", ".")
            elif "," in texto:
                texto = texto.replace(",", ".")

            return float(texto)
        except Exception:
            return None

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)

    @classmethod
    def _codigo_valido(cls, row: Dict[str, Any]) -> Optional[str]:
        if not isinstance(row, dict):
            return None

        codigo = cls._safe_str(
            row.get("codigo")
            or row.get("sku")
            or row.get("Código")
            or row.get("Codigo")
        )

        return codigo or None

    @staticmethod
    def _normalizar_rows(rows: Any) -> List[Dict[str, Any]]:
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
    def _normalizar_row_produto(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        codigo = cls._codigo_valido(row)
        nome = cls._safe_str(
            cls._pick(
                row,
                "nome",
                "descricao",
                "descrição",
                "Descrição",
                "Descrição Curta",
                "descricao_curta",
                "titulo",
                "title",
            )
        )

        preco = cls._to_float(
            cls._pick(
                row,
                "preco",
                "preço",
                "preco_venda",
                "preço de venda",
                "Preço de venda",
                "valor",
                "valor_venda",
            )
        )

        return {
            "codigo": codigo,
            "nome": nome or (codigo or ""),
            "preco": preco,
            "raw": row,
        }

    @classmethod
    def _normalizar_row_estoque(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        codigo = cls._codigo_valido(row)

        estoque = cls._to_float(
            cls._pick(
                row,
                "estoque",
                "saldo",
                "quantidade",
                "Quantidade",
                "Saldo",
            )
        )

        preco = cls._to_float(
            cls._pick(
                row,
                "preco",
                "preço",
                "preco_venda",
                "preço de venda",
                "Preço de venda",
                "valor",
                "valor_venda",
                "Preço unitário (OBRIGATÓRIO)",
            )
        )

        return {
            "codigo": codigo,
            "estoque": estoque if estoque is not None else 0.0,
            "preco": preco,
            "raw": row,
        }

    @staticmethod
    def _resultado_base(
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
    def _erro_registro(
        *,
        mensagem: str,
        row: Optional[Dict[str, Any]] = None,
        codigo: Optional[str] = None,
        resposta: Any = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "erro": str(mensagem or "").strip() or "Erro desconhecido",
        }

        if codigo:
            payload["codigo"] = codigo

        if isinstance(row, dict):
            payload["row"] = row

        if resposta not in (None, ""):
            payload["resposta"] = resposta

        return payload

    # =========================
    # PRODUTOS
    # =========================
    def upsert_products(self, rows: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        registros = self._normalizar_rows(rows)

        if not registros:
            resultado = self._resultado_base(
                ok=False,
                operacao="upsert_products",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum produto válido recebido."],
            )
            return False, resultado

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for lote in self._chunk(registros, self.BATCH_SIZE):
            for row in lote:
                row_norm = self._normalizar_row_produto(row)
                codigo = self._safe_str(row_norm.get("codigo"))

                if not codigo:
                    erro += 1
                    erros.append(
                        self._erro_registro(
                            mensagem="Código vazio para cadastro.",
                            row=row,
                        )
                    )
                    continue

                payload = {
                    "codigo": codigo,
                    "nome": self._safe_str(row_norm.get("nome")) or codigo,
                    "preco": row_norm.get("preco"),
                }

                try:
                    ok_api, resp = self.api.upsert_product(payload)
                except Exception as e:
                    ok_api, resp = False, str(e)

                if ok_api:
                    sucesso += 1
                else:
                    erro += 1
                    erros.append(
                        self._erro_registro(
                            mensagem="Falha ao enviar produto para o Bling.",
                            row=row,
                            codigo=codigo,
                            resposta=resp,
                        )
                    )

        resultado = self._resultado_base(
            ok=(erro == 0 and sucesso > 0),
            operacao="upsert_products",
            total=len(registros),
            sucesso=sucesso,
            erro=erro,
            erros=erros,
        )
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
        deposito_id = self._safe_str(deposito_id)

        if not registros:
            resultado = self._resultado_base(
                ok=False,
                operacao="update_stocks",
                total=0,
                sucesso=0,
                erro=0,
                erros=["Nenhum estoque válido recebido."],
                detalhes={"deposito_id": deposito_id or None},
            )
            return False, resultado

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for lote in self._chunk(registros, self.BATCH_SIZE):
            for row in lote:
                row_norm = self._normalizar_row_estoque(row)
                codigo = self._safe_str(row_norm.get("codigo"))

                if not codigo:
                    erro += 1
                    erros.append(
                        self._erro_registro(
                            mensagem="Código vazio para estoque.",
                            row=row,
                        )
                    )
                    continue

                try:
                    ok_api, resp = self.api.update_stock(
                        codigo=codigo,
                        estoque=row_norm.get("estoque") or 0.0,
                        deposito_id=deposito_id or None,
                        preco=row_norm.get("preco"),
                    )
                except Exception as e:
                    ok_api, resp = False, str(e)

                if ok_api:
                    sucesso += 1
                else:
                    erro += 1
                    erros.append(
                        self._erro_registro(
                            mensagem="Falha ao atualizar estoque no Bling.",
                            row=row,
                            codigo=codigo,
                            resposta=resp,
                        )
                    )

        resultado = self._resultado_base(
            ok=(erro == 0 and sucesso > 0),
            operacao="update_stocks",
            total=len(registros),
            sucesso=sucesso,
            erro=erro,
            erros=erros,
            detalhes={"deposito_id": deposito_id or None},
        )
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
