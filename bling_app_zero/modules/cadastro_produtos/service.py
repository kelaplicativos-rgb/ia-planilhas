from __future__ import annotations

class CadastroProdutosService:
    """
    Motor isolado do fluxo de cadastro de produtos.

    Responsável exclusivamente por:
    - leitura de produtos
    - enriquecimento
    - cadastro
    - estrutura do modelo Bling
    """

    FLOW_NAME = "cadastro_produtos"

    @staticmethod
    def is_cadastro() -> bool:
        return True
