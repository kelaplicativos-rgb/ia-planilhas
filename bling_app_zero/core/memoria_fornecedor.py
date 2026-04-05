# bling_app_zero/core/memoria_fornecedor.py

from typing import Dict


def gerar_hash_fornecedor(colunas: list) -> str:
    """
    Gera uma assinatura do fornecedor baseada nas colunas
    """
    base = "|".join(sorted([str(c).lower() for c in colunas]))
    return str(abs(hash(base)))


def salvar_mapeamento(memoria: Dict, colunas: list, mapeamento: Dict):
    chave = gerar_hash_fornecedor(colunas)
    memoria[chave] = mapeamento


def recuperar_mapeamento(memoria: Dict, colunas: list) -> Dict:
    chave = gerar_hash_fornecedor(colunas)
    return memoria.get(chave, {})
