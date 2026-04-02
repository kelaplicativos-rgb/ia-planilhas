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
    for col in colunas:
        nome = limpar_nome_coluna(col)
        for p in possiveis:
            if p in nome:
                return col
    return None


def detectar_colunas_inteligente(df):
    colunas = list(df.columns)
    mapa = {}

    for chave, variacoes in MAPEAMENTO.items():
        mapa[chave] = encontrar_coluna(colunas, variacoes)

    return mapa
