from __future__ import annotations

from typing import Any, Dict, List, Tuple


class BlingHomologacao:
    def __init__(self) -> None:
        pass

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _clean_str(value: Any) -> str:
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            texto = str(value or "").replace("R$", "").replace(" ", "")
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")
            return float(texto)
        except Exception:
            return 0.0

    # =========================
    # VALIDAÇÃO PRODUTO
    # =========================
    def validar_produto(self, row: Dict[str, Any]) -> Tuple[bool, str]:
        nome = self._clean_str(row.get("nome") or row.get("descricao"))
        codigo = self._clean_str(row.get("codigo") or row.get("sku"))

        if not nome:
            return False, "Produto sem nome"

        if not codigo:
            return False, "Produto sem código"

        return True, "OK"

    # =========================
    # VALIDAÇÃO ESTOQUE
    # =========================
    def validar_estoque(self, row: Dict[str, Any]) -> Tuple[bool, str]:
        codigo = self._clean_str(row.get("codigo") or row.get("sku"))

        if not codigo:
            return False, "Estoque sem código"

        return True, "OK"

    # =========================
    # SIMULAÇÃO PRODUTOS
    # =========================
    def simular_produtos(
        self, rows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in rows:
            ok, msg = self.validar_produto(row)

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(
                    {
                        "row": row,
                        "erro": msg,
                    }
                )

        return {
            "ok": erro == 0,
            "tipo": "produtos",
            "total": len(rows),
            "sucesso": sucesso,
            "erro": erro,
            "erros": erros,
        }

    # =========================
    # SIMULAÇÃO ESTOQUE
    # =========================
    def simular_estoques(
        self, rows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:

        sucesso = 0
        erro = 0
        erros: List[Any] = []

        for row in rows:
            ok, msg = self.validar_estoque(row)

            if ok:
                sucesso += 1
            else:
                erro += 1
                erros.append(
                    {
                        "row": row,
                        "erro": msg,
                    }
                )

        return {
            "ok": erro == 0,
            "tipo": "estoques",
            "total": len(rows),
            "sucesso": sucesso,
            "erro": erro,
            "erros": erros,
        }

    # =========================
    # FLUXO GERAL
    # =========================
    def validar(
        self,
        *,
        tipo: str,
        rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        tipo_normalizado = self._clean_str(tipo).lower()

        if tipo_normalizado == "cadastro":
            return self.simular_produtos(rows)

        if tipo_normalizado == "estoque":
            return self.simular_estoques(rows)

        return {
            "ok": False,
            "erro": f"Tipo inválido: {tipo}",
            "total": 0,
            "sucesso": 0,
            "erro_count": 0,
            "erros": [],
        }
