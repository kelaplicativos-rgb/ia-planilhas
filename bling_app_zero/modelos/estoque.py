import pandas as pd
from datetime import datetime


# =========================
# ESTRUTURA FIXA BLING - ESTOQUE
# =========================
COLUNAS_ESTOQUE = [
    " ID Produto",
    "Codigo produto *",
    "GTIN **",
    "Descrição Produto",
    "Deposito (OBRIGATÓRIO)",
    "Balanço (OBRIGATÓRIO)",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço de Custo",
    "Observação",
    "Data"
]


# =========================
# CRIAR DATAFRAME PADRÃO
# =========================
def criar_planilha_estoque():
    df = pd.DataFrame(columns=COLUNAS_ESTOQUE)
    return df


# =========================
# PREENCHIMENTO AUTOMÁTICO
# =========================
def montar_estoque(df_origem, deposito_nome="GERAL"):
    df = pd.DataFrame()

    hoje = datetime.now().strftime("%d/%m/%Y")

    # =========================
    # MAPEAMENTO INTELIGENTE
    # =========================
    def get_col(nome_possivel):
        for col in df_origem.columns:
            if nome_possivel.lower() in col.lower():
                return col
        return None

    col_codigo = get_col("codigo") or get_col("sku")
    col_gtin = get_col("gtin") or get_col("ean")
    col_nome = get_col("nome") or get_col("produto")
    col_estoque = get_col("estoque") or get_col("quantidade")
    col_preco = get_col("preco") or get_col("valor")
    col_custo = get_col("custo")

    # =========================
    # PREENCHIMENTO
    # =========================
    df[" ID Produto"] = ""

    df["Codigo produto *"] = df_origem[col_codigo] if col_codigo else ""
    df["GTIN **"] = df_origem[col_gtin] if col_gtin else ""

    df["Descrição Produto"] = df_origem[col_nome] if col_nome else ""

    df["Deposito (OBRIGATÓRIO)"] = deposito_nome

    df["Balanço (OBRIGATÓRIO)"] = df_origem[col_estoque] if col_estoque else 0

    df["Preço unitário (OBRIGATÓRIO)"] = (
        df_origem[col_preco] if col_preco else 0
    )

    df["Preço de Custo"] = df_origem[col_custo] if col_custo else ""

    df["Observação"] = ""
    df["Data"] = hoje

    # Garante ordem correta
    df = df[COLUNAS_ESTOQUE]

    return df
