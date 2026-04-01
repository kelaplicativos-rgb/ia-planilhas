import pandas as pd

def preencher_modelo_estoque(modelo, df, depositos):
    linhas = []

    for _, row in df.iterrows():
        for dep in depositos:
            nova = {col: "" for col in modelo.columns}

            for col in modelo.columns:
                c = col.lower()

                if "codigo" in c:
                    nova[col] = row["Código"]

                elif "descrição" in c:
                    nova[col] = row["Produto"]

                elif "deposito" in c:
                    nova[col] = dep

                elif "saldo" in c or "balan" in c:
                    nova[col] = row["Estoque"]

                elif "preço" in c:
                    nova[col] = row["Preço"]

            linhas.append(nova)

    return pd.DataFrame(linhas)


def preencher_modelo_cadastro(modelo, df):
    linhas = []

    for _, row in df.iterrows():
        nova = {col: "" for col in modelo.columns}

        for col in modelo.columns:
            c = col.lower()

            if c == "código":
                nova[col] = row["Código"]

            elif "descrição" in c:
                nova[col] = row["Produto"]

            elif "preço" in c:
                nova[col] = row["Preço"]

            elif "descricao curta" in c:
                nova[col] = row["Descrição Curta"]

            elif "url" in c:
                nova[col] = row["Imagem"]

            elif "link externo" in c:
                nova[col] = row["Link"]

            elif "marca" in c:
                nova[col] = row["Marca"]

            elif "situação" in c:
                nova[col] = "Ativo"

            elif "tipo" in c:
                nova[col] = "Produto"

            elif "unidade" in c:
                nova[col] = "UN"

        linhas.append(nova)

    return pd.DataFrame(linhas)
