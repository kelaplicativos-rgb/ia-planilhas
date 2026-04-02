from core.normalizer.mappers import MAPEAMENTO


def limpar_nome_coluna(col):
    return (
        str(col)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("\\", " ")
    )


def _pontuar_coluna(nome_coluna, variacoes):
    """
    Retorna uma pontuação para escolher a melhor coluna.
    Quanto maior, melhor.
    """
    nome = limpar_nome_coluna(nome_coluna)
    score = 0

    for alvo in variacoes:
        alvo = limpar_nome_coluna(alvo)

        if nome == alvo:
            score = max(score, 100)
        elif nome.startswith(alvo):
            score = max(score, 90)
        elif alvo in nome:
            score = max(score, 70)

    return score


def _escolher_melhor_coluna(colunas, variacoes):
    melhor_coluna = None
    melhor_score = 0

    for col in colunas:
        score = _pontuar_coluna(col, variacoes)
        if score > melhor_score:
            melhor_score = score
            melhor_coluna = col

    return melhor_coluna


def _resolver_codigo(colunas):
    """
    SKU/código é crítico.
    Nunca prioriza 'ID' puro.
    """
    prioridades = [
        "sku",
        "codigo do produto",
        "código do produto",
        "codigo interno",
        "código interno",
        "codigo sku",
        "código sku",
        "referencia",
        "referência",
        "ref",
        "codigo",
        "código",
        "cod produto",
        "cod_produto",
    ]

    # tenta primeiro com prioridades estritas
    melhor = _escolher_melhor_coluna(colunas, prioridades)
    if melhor:
        nome = limpar_nome_coluna(melhor)
        if nome != "id":
            return melhor

    # fallback: procura qualquer coluna relevante menos ID puro
    for col in colunas:
        nome = limpar_nome_coluna(col)
        if nome == "id":
            continue
        if any(chave in nome for chave in [
            "sku",
            "codigo",
            "código",
            "referencia",
            "referência",
            "ref",
        ]):
            return col

    return None


def _resolver_gtin(colunas):
    prioridades = [
        "gtin/ean",
        "gtin",
        "ean",
        "codigo de barras",
        "código de barras",
        "barcode",
    ]
    return _escolher_melhor_coluna(colunas, prioridades)


def _resolver_produto(colunas):
    prioridades = [
        "descricao do produto",
        "descrição do produto",
        "nome do produto",
        "produto",
        "descricao",
        "descrição",
        "nome",
        "titulo",
        "title",
    ]
    return _escolher_melhor_coluna(colunas, prioridades)


def detectar_colunas_inteligente(df, mapa_ia=None):
    colunas = list(df.columns)
    mapa = {}

    # 1) usa IA se existir
    if mapa_ia:
        for chave, coluna in mapa_ia.items():
            if coluna in colunas:
                # trava anti-ID para código
                if chave == "codigo" and limpar_nome_coluna(coluna) == "id":
                    continue
                mapa[chave] = coluna

    # 2) resoluções especiais críticas
    if "codigo" not in mapa or not mapa["codigo"]:
        mapa["codigo"] = _resolver_codigo(colunas)

    if "gtin" not in mapa or not mapa["gtin"]:
        mapa["gtin"] = _resolver_gtin(colunas)

    if "produto" not in mapa or not mapa["produto"]:
        mapa["produto"] = _resolver_produto(colunas)

    # 3) demais campos pelo mapeamento padrão
    for chave, variacoes in MAPEAMENTO.items():
        if chave in mapa and mapa[chave]:
            continue

        melhor = _escolher_melhor_coluna(colunas, variacoes)
        mapa[chave] = melhor

    return mapa
