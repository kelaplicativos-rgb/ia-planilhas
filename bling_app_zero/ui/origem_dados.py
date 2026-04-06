from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica


# ==========================================================
# HELPERS
# ==========================================================
def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def _safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


# ==========================================================
# 🔥 INTELIGÊNCIA DE COLUNAS (NOVO)
# ==========================================================
def _eh_coluna_estoque(nome_coluna: str) -> bool:
    nome = str(nome_coluna).lower()

    palavras = [
        "estoque",
        "saldo",
        "quantidade",
        "qtd",
        "qty",
        "disponivel",
        "disponível",
        "inventory",
        "stock",
    ]

    return any(p in nome for p in palavras)


def _normalizar_estoque(valor, padrao=0):
    try:
        texto = str(valor).strip().lower()

        if "esgotado" in texto or "indisponivel" in texto or "indisponível" in texto:
            return 0

        if texto == "" or texto == "nan":
            return padrao

        return int(float(valor))
    except Exception:
        return padrao


# ==========================================================
# GTIN
# ==========================================================
def _normalizar_gtin(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    texto = "".join(ch for ch in texto if ch.isdigit())

    if len(texto) in (8, 12, 13, 14):
        return texto

    return ""


def _limpar_gtin(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        nome_col = str(col).lower()
        if "gtin" in nome_col or "ean" in nome_col:
            df[col] = df[col].apply(_normalizar_gtin)
    return df


# ==========================================================
# LIMPEZA COLUNAS
# ==========================================================
def _limpar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    novas = []
    usados = {}

    for col in df.columns:
        nome = str(col).strip()

        if nome == "" or nome.lower() == "nan":
            nome = "SEM_NOME"

        base = nome
        contador = usados.get(base, 0)

        if contador > 0:
            nome = f"{base}_{contador}"

        usados[base] = contador + 1
        novas.append(nome)

    df.columns = novas
    return df


# ==========================================================
# LEITURA INTELIGENTE
# ==========================================================
def _ler_excel_seguro(arquivo):
    try:
        arquivo.seek(0)
        df_raw = pd.read_excel(arquivo, header=None)

        melhor_linha = 0
        maior_score = 0

        for i in range(min(5, len(df_raw))):
            linha = df_raw.iloc[i].astype(str).tolist()

            score = sum(
                1 for x in linha
                if str(x).strip() != "" and str(x).strip().lower() != "nan"
            )

            if score > maior_score:
                maior_score = score
                melhor_linha = i

        arquivo.seek(0)
        df = pd.read_excel(arquivo, header=melhor_linha)

        return _limpar_nomes_colunas(df)

    except Exception as e:
        st.error(f"Erro ao ler Excel: {e}")
        return None


def _ler_csv_seguro(arquivo):
    try:
        arquivo.seek(0)
        df = pd.read_csv(arquivo, sep=None, engine="python")
        return _limpar_nomes_colunas(df)
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")
        return None


# ==========================================================
# MAIN
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    arquivo = st.file_uploader("Envie a planilha", type=["xlsx", "csv"])

    if not arquivo:
        return

    if arquivo.name.endswith(".csv"):
        df_origem = _ler_csv_seguro(arquivo)
    else:
        df_origem = _ler_excel_seguro(arquivo)

    if df_origem is None or df_origem.empty:
        return

    st.markdown("### Preview")
    st.dataframe(_safe_preview(df_origem), width="stretch")

    st.markdown("### Mapeamento automático inteligente")

    # 🔥 Detectar coluna de estoque automaticamente
    coluna_estoque_detectada = None

    for col in df_origem.columns:
        if _eh_coluna_estoque(col):
            coluna_estoque_detectada = col
            break

    if coluna_estoque_detectada:
        st.success(f"Coluna de estoque detectada: {coluna_estoque_detectada}")

        df_origem[coluna_estoque_detectada] = df_origem[
            coluna_estoque_detectada
        ].apply(lambda x: _normalizar_estoque(x, 10))

    else:
        st.warning("Nenhuma coluna de estoque detectada automaticamente")

    df_origem = _limpar_gtin(df_origem)

    excel = _exportar_df_exato_para_excel_bytes(df_origem)

    st.download_button(
        "Baixar planilha tratada",
        data=excel,
        file_name="saida.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
