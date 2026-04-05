# bling_app_zero/utils/excel.py

import pandas as pd
from io import BytesIO
import unicodedata
import re


# =========================
# NORMALIZAÇÃO
# =========================

def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""

    texto = texto.lower()
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
        if str(arquivo.name).endswith(".csv"):
            return pd.read_csv(arquivo)
        else:
            return pd.read_excel(arquivo)
    except Exception as e:
        raise Exception(f"Erro ao ler planilha: {e}")


# =========================
# LIMPEZA DE VALORES
# =========================

def limpar_valores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    return df


# =========================
# NORMALIZAR COLUNAS
# =========================

def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalizar_texto(col) for col in df.columns]
    return df


# =========================
# EXPORTAR PARA EXCEL
# =========================

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()


# =========================
# MAPEAMENTO PADRÃO COLUNAS
# =========================

MAPEAMENTO_COLUNAS = {
    "nome": ["nome", "descricao", "descricao produto"],
    "descricao_html": ["descricao_html", "descricao_completa"],
    "preco": ["preco", "valor", "valor venda"],
    "custo": ["custo", "valor custo"],
    "sku": ["sku", "codigo", "referencia"],
    "gtin": ["gtin", "ean", "codigo barras"],
    "ncm": ["ncm"],
    "marca": ["marca"],
    "estoque": ["estoque", "quantidade"],
    "categoria": ["categoria"],
    "peso": ["peso"]
}
