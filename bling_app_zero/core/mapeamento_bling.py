import pandas as pd


# =========================
# POSSÍVEIS NOMES (IA SIMPLES)
# =========================
MAPEAMENTO_INTELIGENTE = {
    "codigo": ["codigo", "sku", "id", "ref"],
    "nome": ["nome", "produto", "titulo", "descricao"],
    "preco": ["preco", "valor", "price"],
    "descricao_curta": ["descricao", "desc", "detalhes"],
    "marca": ["marca", "brand"],
    "imagem": ["imagem", "image", "foto", "url_imagem"],
}


def encontrar_coluna(df, possibilidades):
    for col in df.columns:
        nome = col.lower()
        for p in possibilidades:
            if p in nome:
                return col
    return None


def mapear_produtos(df: pd.DataFrame, modelo: pd.DataFrame) -> pd.DataFrame:
    """
    Preenche modelo do Bling com base na planilha enviada
    """

    df_saida = modelo.copy()

    # =========================
    # DETECÇÃO AUTOMÁTICA
    # =========================
    col_codigo = encontrar_coluna(df, MAPEAMENTO_INTELIGENTE["codigo"])
    col_nome = encontrar_coluna(df, MAPEAMENTO_INTELIGENTE["nome"])
    col_preco = encontrar_coluna(df, MAPEAMENTO_INTELIGENTE["preco"])
    col_desc = encontrar_coluna(df, MAPEAMENTO_INTELIGENTE["descricao_curta"])
    col_marca = encontrar_coluna(df, MAPEAMENTO_INTELIGENTE["marca"])
    col_img = encontrar_coluna(df, MAPEAMENTO_INTELIGENTE["imagem"])

    # =========================
    # LOOP DE PREENCHIMENTO
    # =========================
    linhas = []

    for _, row in df.iterrows():
        nova_linha = {}

        for col in df_saida.columns:
            nome_col = col.lower()

            if "codigo" in nome_col and col_codigo:
                nova_linha[col] = row[col_codigo]

            elif "nome" in nome_col and col_nome:
                nova_linha[col] = row[col_nome]

            elif "preco" in nome_col and col_preco:
                nova_linha[col] = row[col_preco]

            elif "descricao" in nome_col and col_desc:
                nova_linha[col] = row[col_desc]

            elif "marca" in nome_col and col_marca:
                nova_linha[col] = row[col_marca]

            elif "imagem" in nome_col and col_img:
                nova_linha[col] = row[col_img]

            else:
                nova_linha[col] = ""

        linhas.append(nova_linha)

    df_final = pd.DataFrame(linhas)

    return df_final
