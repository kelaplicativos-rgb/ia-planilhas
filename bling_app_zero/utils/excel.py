# bling_app_zero/utils/excel.py

from __future__ import annotations

from io import BytesIO
import re
import unicodedata

import pandas as pd


# =========================
# NORMALIZAÇÃO
# =========================
def normalizar_texto(texto: str) -> str:
    if not texto:
        return ""

    texto = str(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# =========================
# LEITURA PLANILHA
# =========================
def ler_planilha(arquivo) -> pd.DataFrame:
    """
    Lê CSV/XLS/XLSX com segurança, sempre tentando devolver strings
    para reduzir problemas de inferência de tipo no mapeamento.
    """
    if arquivo is None:
        return pd.DataFrame()

    nome = str(getattr(arquivo, "name", "") or "").lower()

    try:
        if hasattr(arquivo, "seek"):
            arquivo.seek(0)

        if nome.endswith(".csv"):
            try:
                return pd.read_csv(arquivo, dtype=str)
            except Exception:
                if hasattr(arquivo, "seek"):
                    arquivo.seek(0)
                return pd.read_csv(arquivo, dtype=str, sep=";")

        return pd.read_excel(arquivo, dtype=str)
    except Exception as e:
        raise Exception(f"Erro ao ler planilha: {e}") from e


# =========================
# LIMPEZA DE VALORES
# =========================
def limpar_valores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in df.columns:
        df[col] = (
            df[col]
            .fillna("")
            .astype(str)
            .str.replace("\r", " ", regex=False)
            .str.replace("\n", " ", regex=False)
            .str.strip()
        )

    return df


def limpar_valores_vazios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mantido por compatibilidade com o roteador_entrada.py.
    """
    return limpar_valores(df)


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
def df_to_excel_bytes(df: pd.DataFrame, nome_aba: str = "dados") -> bytes:
    """
    Exporta usando openpyxl para evitar dependência extra de xlsxwriter.
    Aceita nome_aba opcional para manter compatibilidade com chamadas já existentes.
    """
    output = BytesIO()

    nome_aba_limpo = str(nome_aba or "dados").strip()[:31] or "dados"

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba_limpo)

    output.seek(0)
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
    "peso": ["peso"],
}
