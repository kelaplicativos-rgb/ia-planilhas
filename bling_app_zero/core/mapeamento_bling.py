import pandas as pd

MAPEAMENTO = {
    "codigo": ["codigo", "sku", "id"],
    "nome": ["nome", "produto"],
    "preco": ["preco", "valor"],
    "descricao": ["descricao"],
    "marca": ["marca"],
    "imagem": ["imagem", "url"]
}


def encontrar(df, chaves):
    for col in df.columns:
        nome = col.lower()
        for c in chaves:
            if c in nome:
                return col
    return None


def mapear_produtos(df, modelo):

    saida = []

    c_cod = encontrar(df, MAPEAMENTO["codigo"])
    c_nome = encontrar(df, MAPEAMENTO["nome"])
    c_preco = encontrar(df, MAPEAMENTO["preco"])
    c_desc = encontrar(df, MAPEAMENTO["descricao"])
    c_marca = encontrar(df, MAPEAMENTO["marca"])
    c_img = encontrar(df, MAPEAMENTO["imagem"])

    for _, row in df.iterrows():

        nova = {}

        for col in modelo.columns:

            nome = col.lower()

            if "codigo" in nome and c_cod:
                nova[col] = row[c_cod]

            elif "nome" in nome and c_nome:
                nova[col] = row[c_nome]

            elif "preco" in nome and c_preco:
                nova[col] = row[c_preco]

            elif "descricao" in nome and c_desc:
                nova[col] = row[c_desc]

            elif "marca" in nome and c_marca:
                nova[col] = row[c_marca]

            elif "imagem" in nome and c_img:
                nova[col] = row[c_img]

            else:
                nova[col] = ""

        saida.append(nova)

    return pd.DataFrame(saida)
