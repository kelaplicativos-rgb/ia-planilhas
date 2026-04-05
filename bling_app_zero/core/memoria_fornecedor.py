import hashlib
from typing import Dict, List


def gerar_hash_fornecedor(colunas: List[str]) -> str:
    """
    Gera uma assinatura estável do fornecedor baseada nas colunas.
    Usa md5 para que a mesma estrutura gere sempre a mesma chave,
    mesmo após reiniciar o app.
    """
    colunas_normalizadas = sorted(str(c).strip().lower() for c in colunas if c is not None)
    base = "|".join(colunas_normalizadas)
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def salvar_mapeamento(memoria: Dict, colunas: List[str], mapeamento: Dict) -> None:
    """
    Salva o mapeamento na memória usando a chave estável do fornecedor.
    """
    if memoria is None:
        return

    chave = gerar_hash_fornecedor(colunas)
    memoria[chave] = dict(mapeamento or {})


def recuperar_mapeamento(memoria: Dict, colunas: List[str]) -> Dict:
    """
    Recupera o mapeamento salvo para a estrutura de colunas informada.
    """
    if not memoria:
        return {}

    chave = gerar_hash_fornecedor(colunas)
    mapeamento = memoria.get(chave, {})
    return dict(mapeamento or {})
