import pandas as pd

from core.utils import limpar


TERMOS_PROPAGANDA_LINK = [
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "wa.me",
    "whatsapp",
    "telegram",
    "tiktok",
    "canal",
    "inscreva-se",
    "promo",
    "cupom",
]


def _link_valido_produto(link):
    link = limpar(link)
    if not link:
        return ""

    lk = link.lower()

    if any(t in lk for t in TERMOS_PROPAGANDA_LINK):
        return ""

    if not (
        lk.startswith("http://")
        or lk.startswith("https://")
        or lk.startswith("www.")
        or "/" in lk
    ):
        return ""

    return link


def _imagem_valida(imagem):
    imagem = limpar(imagem)
    if not imagem:
        return ""

    lk = imagem.lower()

    if any(t in lk for t in TERMOS_PROPAGANDA_LINK):
        return ""

    return imagem


def _valor(row, campo, default=""):
    valor = row.get(campo, default)
    return "" if valor is None else valor


def preencher_modelo_cadastro(modelo, df):
    linhas = []

    mapa = {str(col).lower().strip(): col for col in modelo.columns}

    def encontrar_coluna(possiveis):
        for nome in possiveis:
            nome = nome.lower().strip()
            for col_norm, col_real in mapa.items():
                if nome == col_norm or nome in col_norm:
                    return col_real
        return None

    col_id = encontrar_coluna(["id"])
    col_codigo = encontrar_coluna(["código", "codigo"])
    col_descricao = encontrar_coluna(["descrição", "descricao"])
    col_tipo = encontrar_coluna(["tipo"])
    col_situacao = encontrar_coluna(["situação", "situacao"])
    col_unidade = encontrar_coluna(["unidade"])
    col_preco = encontrar_coluna(["preço", "preco"])
    col_preco_custo = encontrar_coluna(["preço de custo", "preco de custo"])
    col_gtin = encontrar_coluna(["gtin", "codigo de barras", "código de barras", "gtin/ean"])
    col_marca = encontrar_coluna(["marca"])
    col_ncm = encontrar_coluna(["ncm"])
    col_origem = encontrar_coluna(["origem"])
    col_peso_liquido = encontrar_coluna(["peso líquido", "peso liquido"])
    col_peso_bruto = encontrar_coluna(["peso bruto"])
    col_estoque_minimo = encontrar_coluna(["estoque mínimo", "estoque minimo"])
    col_estoque_maximo = encontrar_coluna(["estoque máximo", "estoque maximo"])
    col_descricao_curta = encontrar_coluna(["descrição curta", "descricao curta"])
    col_descricao_complementar = encontrar_coluna(["descrição complementar", "descricao complementar"])
    col_url_imagens = encontrar_coluna(["url imagens externas", "url imagem", "url imagens"])
    col_link_externo = encontrar_coluna(["link externo", "url produto", "link produto"])

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        codigo = limpar(_valor(row, "Código"))
        produto = limpar(_valor(row, "Produto"))
        tipo = limpar(_valor(row, "Tipo")) or "Produto"
        situacao = limpar(_valor(row, "Situação")) or "Ativo"
        unidade = limpar(_valor(row, "Unidade")) or "UN"
        preco = _valor(row, "Preço", "") or "0.01"
        preco_custo = _valor(row, "Preço Custo", "")
        gtin = limpar(_valor(row, "GTIN"))
        marca = limpar(_valor(row, "Marca"))
        ncm = limpar(_valor(row, "NCM"))
        origem = limpar(_valor(row, "Origem")) or "0"
        peso_liquido = limpar(_valor(row, "Peso Líquido"))
        peso_bruto = limpar(_valor(row, "Peso Bruto"))
        estoque_minimo = limpar(_valor(row, "Estoque Mínimo"))
        estoque_maximo = limpar(_valor(row, "Estoque Máximo"))
        descricao_curta = limpar(_valor(row, "Descrição Curta"))
        descricao_complementar = limpar(_valor(row, "Descrição Complementar"))
        imagem = _imagem_valida(_valor(row, "Imagem"))
        link = _link_valido_produto(_valor(row, "Link"))

        if not descricao_curta:
            descricao_curta = produto

        if col_id:
            nova[col_id] = ""

        if col_codigo:
            nova[col_codigo] = codigo

        if col_descricao:
            nova[col_descricao] = produto

        if col_tipo:
            nova[col_tipo] = tipo

        if col_situacao:
            nova[col_situacao] = situacao

        if col_unidade:
            nova[col_unidade] = unidade

        if col_preco:
            nova[col_preco] = preco

        if col_preco_custo:
            nova[col_preco_custo] = preco_custo

        if col_gtin:
            nova[col_gtin] = gtin

        if col_marca:
            nova[col_marca] = marca

        if col_ncm:
            nova[col_ncm] = ncm

        if col_origem:
            nova[col_origem] = origem

        if col_peso_liquido:
            nova[col_peso_liquido] = peso_liquido

        if col_peso_bruto:
            nova[col_peso_bruto] = peso_bruto

        if col_estoque_minimo:
            nova[col_estoque_minimo] = estoque_minimo

        if col_estoque_maximo:
            nova[col_estoque_maximo] = estoque_maximo

        if col_descricao_curta:
            nova[col_descricao_curta] = descricao_curta

        if col_descricao_complementar:
            nova[col_descricao_complementar] = descricao_complementar

        if col_url_imagens:
            nova[col_url_imagens] = imagem

        if col_link_externo:
            nova[col_link_externo] = link

        linhas.append(nova)

    return pd.DataFrame(linhas, columns=modelo.columns)
