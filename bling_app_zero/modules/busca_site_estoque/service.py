from __future__ import annotations

class BuscaSiteEstoqueService:
    """
    Busca mínima e determinística para atualização de estoque.

    Regra principal:
    buscar apenas os campos pedidos pelo modelo.
    """

    FLOW_NAME = "busca_site_estoque"

    @staticmethod
    def filtrar_campos(campos_modelo: list[str], dados: dict) -> dict:
        saida = {}
        for campo in campos_modelo:
            saida[campo] = dados.get(campo, "")
        return saida
