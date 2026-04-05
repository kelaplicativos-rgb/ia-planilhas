from io import BytesIO
import pandas as pd


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Converte DataFrame para Excel (xlsx)
    """

    df = df.copy()

    # =========================
    # GARANTIR COLUNAS BASE
    # =========================

    colunas_padrao = {
        "preco": 0.0,
        "preco_custo": 0.0,
        "estoque": 0,
        "peso": 0.0,
    }

    for col, default in colunas_padrao.items():
        if col not in df.columns:
            df[col] = default

    # =========================
    # PREÇO DE CUSTO (CORREÇÃO)
    # =========================

    if "custo_fornecedor" in df.columns:
        df["preco_custo"] = df["custo_fornecedor"]

    elif "preco_compra" in df.columns:
        df["preco_custo"] = df["preco_compra"]

    # fallback inteligente (evita custo zerado)
    df["preco_custo"] = df["preco_custo"].fillna(0.0)

    # =========================
    # LIMPEZA GTIN
    # =========================

    if "gtin" in df.columns:
        df["gtin"] = df["gtin"].astype(str)

        def limpar_gtin(valor):
            if not valor.isdigit():
                return ""
            if len(valor) not in [8, 12, 13, 14]:
                return ""
            return valor

        df["gtin"] = df["gtin"].apply(limpar_gtin)

    # =========================
    # TRATAR NULOS
    # =========================

    df["preco"] = pd.to_numeric(df["preco"], errors="coerce").fillna(0.0)
    df["preco_custo"] = pd.to_numeric(df["preco_custo"], errors="coerce").fillna(0.0)
    df["estoque"] = pd.to_numeric(df["estoque"], errors="coerce").fillna(0)
    df["peso"] = pd.to_numeric(df["peso"], errors="coerce").fillna(0.0)

    # =========================
    # EXPORTAÇÃO
    # =========================

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()
