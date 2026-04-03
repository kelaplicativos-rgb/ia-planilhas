import os
import pandas as pd


def caminho_modelo_cadastro():
    caminhos = [
        "modelos/cadastro/produtos.xlsx",
        "modelos/cadastro/produtos.xls",
        "modelos/cadastro/produtos.csv",
    ]
    for caminho in caminhos:
        if os.path.exists(caminho):
            return caminho
    return None


def caminho_modelo_estoque():
    caminhos = [
        "modelos/estoque/saldo_estoque.xlsx",
        "modelos/estoque/saldo_estoque.xls",
        "modelos/estoque/saldo_estoque.csv",
    ]
    for caminho in caminhos:
        if os.path.exists(caminho):
            return caminho
    return None


def ler_modelo_padrao(caminho):
    if not caminho:
        return None, None

    nome = os.path.basename(caminho).lower()
    ext = os.path.splitext(nome)[1].lower()

    if ext == ".csv":
        try:
            df = pd.read_csv(
                caminho,
                sep=None,
                engine="python",
                encoding="utf-8",
                on_bad_lines="skip"
            )
        except Exception:
            df = pd.read_csv(
                caminho,
                sep=None,
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(caminho)
    else:
        return None, None

    return df, ext
