"""
SITE AGENT (ORQUESTRADOR GLOBAL)

Responsável por:
- Escolher o fornecedor correto
- Aplicar fallback inteligente
- Garantir captura de ESTOQUE (prioridade máxima)
"""

from typing import List, Dict

from bling_app_zero.core.suppliers.registry import SupplierRegistry


class SiteAgent:

    def __init__(self):
        self.registry = SupplierRegistry()

    # -------------------------------
    # EXECUÇÃO PRINCIPAL
    # -------------------------------
    def executar(self, url: str, **kwargs) -> List[Dict]:

        # ===============================
        # 1. IDENTIFICAR FORNECEDOR
        # ===============================
        fornecedor = self.registry.get_supplier(url)

        # ===============================
        # 2. EXECUTAR SCRAPER PRINCIPAL
        # ===============================
        produtos = []

        try:
            produtos = fornecedor.fetch(url, **kwargs)
        except Exception as e:
            print(f"[ERRO fornecedor específico] {e}")

        # ===============================
        # 3. FALLBACK GENÉRICO
        # ===============================
        if not produtos:
            print("[FALLBACK] usando GenericSupplier")

            fornecedor_generico = self.registry.get_generic()

            try:
                produtos = fornecedor_generico.fetch(url, **kwargs)
            except Exception as e:
                print(f"[ERRO fallback] {e}")

        # ===============================
        # 4. PÓS-PROCESSAMENTO (CRÍTICO)
        # ===============================
        produtos = self._padronizar(produtos)

        return produtos

    # -------------------------------
    # PADRONIZAÇÃO FINAL
    # -------------------------------
    def _padronizar(self, produtos: List[Dict]) -> List[Dict]:

        resultado = []

        for p in produtos:

            if not isinstance(p, dict):
                continue

            estoque = self._normalizar_estoque(p.get("estoque"))

            resultado.append({
                "url_produto": p.get("url_produto", ""),
                "nome": p.get("nome", ""),
                "sku": p.get("sku", ""),
                "estoque": estoque,
                "preco": p.get("preco", 0),
                "imagens": self._normalizar_imagens(p.get("imagens")),
            })

        return resultado

    # -------------------------------
    # NORMALIZA ESTOQUE (REGRA GLOBAL)
    # -------------------------------
    def _normalizar_estoque(self, valor):

        try:
            valor = int(valor)
        except:
            valor = 0

        # regra global
        if valor < 0:
            return 0

        return valor

    # -------------------------------
    # NORMALIZA IMAGENS
    # -------------------------------
    def _normalizar_imagens(self, imagens):

        if not imagens:
            return ""

        if isinstance(imagens, list):
            # padrão Bling → separado por |
            return "|".join(imagens)

        return str(imagens)
