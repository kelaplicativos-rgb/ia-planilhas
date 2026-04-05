from io import BytesIO
import re
import unicodedata

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
# NORMALIZAÇÃO
# =========================
def normalizar_texto(texto: str) -> str:
    if texto is None:
        return ""

    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# =========================
# LEITURA PLANILHA
# =========================
def ler_planilha(arquivo) -> pd.DataFrame:
    try:
        nome = str(getattr(arquivo, "name", "")).lower()

        if nome.endswith(".csv"):
            try:
                return pd.read_csv(arquivo)
            except UnicodeDecodeError:
                arquivo.seek(0)
                return pd.read_csv(arquivo, encoding="latin1")

        return pd.read_excel(arquivo)
    except Exception as e:
        raise Exception(f"Erro ao ler planilha: {e}") from e


# =========================
# LIMPEZA DE VALORES
# =========================
def limpar_valores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].fillna("").astype(str).str.strip()

    return df


# =========================
# NORMALIZAR COLUNAS
# =========================
def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalizar_texto(col) for col in df.columns]
    return df


# =========================
# PADRONIZAÇÃO FINAL BLING
# =========================
def padronizar_dataframe_bling(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUNAS_PADRAO_BLING)

    df = df.copy()

    rename_map = {
        "sku": "codigo",
        "custo": "preco_custo",
        "descricao_html": "descricao_complementar",
    }

    df = df.rename(columns=rename_map)

    # Garante todas as colunas do modelo
    for col in COLUNAS_PADRAO_BLING:
        if col not in df.columns:
            df[col] = None

    # Remove colunas extras e fixa ordem final
    df = df[COLUNAS_PADRAO_BLING]

    return df


# =========================
# EXPORTAR PARA EXCEL
# =========================
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    df_final = padronizar_dataframe_bling(df)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_final.to_excel(writer, index=False, sheet_name="Produtos")

    output.seek(0)
    return output.getvalue()


# =========================
# MAPEAMENTO PADRÃO COLUNAS
# =========================
MAPEAMENTO_COLUNAS = {
    "nome": [
        "nome",
        "descricao",
        "descricao produto",
        "produto",
        "titulo",
        "nome produto",
    ],
    "descricao_html": [
        "descricao_html",
        "descricao html",
        "descricao_completa",
        "descricao completa",
        "descricao longa",
    ],
    "preco": [
        "preco",
        "preco venda",
        "valor",
        "valor venda",
        "valor de venda",
    ],
    "custo": [
        "custo",
        "valor custo",
        "preco custo",
        "preco de custo",
        "custo compra",
    ],
    "sku": [
        "sku",
        "codigo",
        "codigo produto",
        "referencia",
        "ref",
    ],
    "gtin": [
        "gtin",
        "ean",
        "codigo barras",
        "codigo de barras",
        "barcode",
    ],
    "ncm": [
        "ncm",
    ],
    "marca": [
        "marca",
        "fabricante",
    ],
    "estoque": [
        "estoque",
        "quantidade",
        "qtd",
        "saldo",
    ],
    "categoria": [
        "categoria",
        "departamento",
        "grupo",
        "secao",
    ],
    "peso": [
        "peso",
        "peso liquido",
        "peso bruto",
    ],
}
