from io import BytesIO
import pandas as pd


# =========================
# MODELO PADRÃO BLING
# =========================
COLUNAS_PADRAO_BLING = [
    "codigo",
    "nome",
    "descricao_curta",
    "descricao_complementar",
    "marca",
    "categoria",
    "preco",
    "preco_custo",
    "estoque",
    "peso",
    "gtin",
    "ncm",
]


# =========================
# NORMALIZADOR FINAL
# =========================
def padronizar_dataframe_bling(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUNAS_PADRAO_BLING)

    df = df.copy()

    # Renomeações padrão internas → Bling
    rename_map = {
        "sku": "codigo",
        "custo": "preco_custo",
    }

    df = df.rename(columns=rename_map)

    # Garante todas as colunas do modelo
    for col in COLUNAS_PADRAO_BLING:
        if col not in df.columns:
            df[col] = None

    # Remove colunas extras
    df = df[COLUNAS_PADRAO_BLING]

    return df


# =========================
# EXPORTAÇÃO EXCEL
# =========================
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    df_final = padronizar_dataframe_bling(df)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_final.to_excel(writer, index=False, sheet_name="Produtos")

    return output.getvalue()
