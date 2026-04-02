from core.normalizer.mappers import MAPEAMENTO


def limpar_nome_coluna(col):
    return (
        str(col)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def encontrar_coluna(colunas, possiveis):
    # 1) igualdade exata
    for alvo in possiveis:
        alvo = limpar_nome_coluna(alvo)
        for col in colunas:
            nome = limpar_nome_coluna(col)
            if nome == alvo:
                return col

    # 2) contains
    for alvo in possiveis:
        alvo = limpar_nome_coluna(alvo)
        for col in colunas:
            nome = limpar_nome_coluna(col)
            if alvo in nome:
                return col

    return None


def detectar_colunas_inteligente(df, mapa_ia=None):
    colunas = list(df.columns)
    mapa = {}

    # primeiro usa IA se existir
    if mapa_ia:
        for chave, coluna in mapa_ia.items():
            if coluna in colunas:
                mapa[chave] = coluna

    # depois completa no offline
    for chave, variacoes in MAPEAMENTO.items():
        if chave not in mapa or not mapa[chave]:
            mapa[chave] = encontrar_coluna(colunas, variacoes)

    return mapa
