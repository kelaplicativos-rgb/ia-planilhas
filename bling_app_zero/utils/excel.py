from io import BytesIO
import re
import unicodedata

import pandas as pd
from openpyxl.styles import numbers


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
# AJUSTES DE VALORES
# =========================
def _to_text(value) -> str:
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    texto = str(value).strip()

    if texto.lower() == "nan":
        return ""

    return texto


def _to_num(value):
    if value is None or pd.isna(value):
        return None

    texto = str(value).strip()
    if not texto:
        return None

    texto = texto.replace("R$", "").replace(" ", "")

    # Se vier no padrão BR com milhar e decimal
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")

    # Se vier só com vírgula, assume decimal BR
    elif "," in texto:
        texto = texto.replace(".", "").replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return None


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

    # Garante colunas mínimas
    for col in COLUNAS_PADRAO_BLING:
        if col not in df.columns:
            df[col] = ""

    # Descrição curta padrão baseada no nome, se não existir
    if "descricao_curta" in df.columns:
        vazia = df["descricao_curta"].fillna("").astype(str).str.strip() == ""
        df.loc[vazia, "descricao_curta"] = df.loc[vazia, "nome"].fillna("").astype(str)

    # Descrição complementar padrão
    if "descricao_complementar" in df.columns:
        df["descricao_complementar"] = df["descricao_complementar"].fillna("").astype(str)

    # Campos texto importantes
    colunas_texto = [
        "codigo",
        "nome",
        "descricao_curta",
        "descricao_complementar",
        "marca",
        "categoria",
        "gtin",
        "ncm",
    ]
    for col in colunas_texto:
        df[col] = df[col].apply(_to_text)

    # Evita perder zeros/códigos e remove .0 final em textos numéricos
    for col in ["codigo", "gtin", "ncm"]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
        )

    # Campos numéricos
    for col in ["preco", "preco_custo", "estoque", "peso"]:
        df[col] = df[col].apply(_to_num)

    # Valores padrão seguros
    df["preco"] = df["preco"].fillna(0.0)
    df["preco_custo"] = df["preco_custo"].fillna(0.0)
    df["estoque"] = df["estoque"].fillna(0)
    df["peso"] = df["peso"].fillna(0.0)

    # Ordem final exata do modelo
    df = df[COLUNAS_PADRAO_BLING]

    return df


# =========================
# EXPORTAR PARA EXCEL
# =========================
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    df_final = padronizar_dataframe_bling(df)
    output = BytesIO()

    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_final.to_excel(writer, index=False, sheet_name="Produtos")

            ws = writer.sheets["Produtos"]

            # Força como texto para o Excel/Bling não deformarem códigos
            colunas_texto = {"A", "K", "L"}  # codigo, gtin, ncm
            for col_letter in colunas_texto:
                for cell in ws[col_letter]:
                    cell.number_format = numbers.FORMAT_TEXT

            # Cabeçalho
            for cell in ws[1]:
                cell.number_format = numbers.FORMAT_TEXT

        output.seek(0)
        return output.getvalue()

    except Exception as e:
        raise Exception(f"Erro ao gerar Excel: {e}") from e


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
