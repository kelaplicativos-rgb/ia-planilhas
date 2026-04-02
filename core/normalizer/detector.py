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
    # 1) tenta igualdade exata
    for alvo in possiveis:
        alvo = limpar_nome_coluna(alvo)
        for col in colunas:
            nome = limpar_nome_coluna(col)
            if nome == alvo:
                return col

    # 2) tenta "contém"
    for alvo in possiveis:
        alvo = limpar_nome_coluna(alvo)
        for col in colunas:
            nome = limpar_nome_coluna(col)
            if alvo in nome:
                return col

    return None


def detectar_colunas_inteligente(df):
    colunas = list(df.columns)
    mapa = {}

    for chave, variacoes in MAPEAMENTO.items():
        mapa[chave] = encontrar_coluna(colunas, variacoes)

    return mapa
