from __future__ import annotations

class AtualizacaoEstoqueService:
    """
    Motor isolado do fluxo de atualização de estoque.

    Regras:
    - não enriquecer dados
    - não buscar campos desnecessários
    - seguir exatamente o modelo da planilha
    - deixar vazio o que não encontrar
    """

    FLOW_NAME = "atualizacao_estoque"

    @staticmethod
    def is_estoque() -> bool:
        return True
