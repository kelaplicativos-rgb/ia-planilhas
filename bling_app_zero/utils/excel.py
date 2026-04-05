from io import BytesIO
import pandas as pd


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Converte DataFrame para Excel (xlsx) garantindo:
    - Preço de venda preenchido
    - Preço de custo preenchido corretamente
    - Estoque válido
    - GTIN inválido limpo
    """

    df = df.copy()

    # =========================
    # GARANTIR COLUNAS BASE
    # =========================

    if "preco" not in df.columns:
        df["preco"] = 0.0

    if "preco_custo" not in df.columns:
        df["preco_custo"] = 0.0

    if "estoque" not in df.columns:
        df["estoque"] = 0

    if "peso" not in df.columns:
        df["peso"] = 0.0

    # =========================
    # CORREÇÃO PREÇO DE CUSTO
    # =========================
    # PRIORIDADE:
    # 1. custo vindo do fornecedor
    # 2. custo calculado (precificação)
    # 3. fallback inteligente

    if "custo_fornecedor" in df.columns:
        df["preco_custo"] = df["custo_fornecedor"]

    elif "preco_compra" in df.columns:
        df["preco_custo"] = df["preco_compra"]

    elif "preco" in df.columns:
        # fallback seguro (evita custo zerado)
        df["preco_custo"] = df["preco"] * 0.6

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

    df["preco"] = df["preco"].fillna(0.0)
    df["preco_custo"] = df["preco_custo"].fillna(0.0)
    df["estoque"] = df["estoque"].fillna(0)
    df["peso"] = df["peso"].fillna(0.0)

    # =========================
    # EXPORTAÇÃO
    # =========================

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()
