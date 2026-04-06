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
# 🔥 LIMPEZA COLUNAS
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
# 🔥 DETECÇÃO HEADER AUTOMÁTICA
# ==========================================================
def _detectar_header(df_raw):
    melhor_linha = 0
    maior_score = 0

    for i in range(min(10, len(df_raw))):
        linha = df_raw.iloc[i].astype(str).tolist()

        score = sum(
            1 for x in linha
            if str(x).strip() != "" and str(x).strip().lower() != "nan"
        )

        if score > maior_score:
            maior_score = score
            melhor_linha = i

    return melhor_linha


# ==========================================================
# 🔥 LEITURA EXCEL (XLSX / XLS)
# ==========================================================
def _ler_excel_seguro(arquivo):
    try:
        arquivo.seek(0)

        # lê bruto
        df_raw = pd.read_excel(arquivo, header=None, engine=None)

        if df_raw is None or df_raw.empty:
            return None

        header = _detectar_header(df_raw)

        arquivo.seek(0)
        df = pd.read_excel(arquivo, header=header, engine=None)

        return _limpar_nomes_colunas(df)

    except Exception as e:
        st.error(f"Erro ao ler Excel: {e}")
        return None


# ==========================================================
# 🔥 LEITURA CSV (FORTE)
# ==========================================================
def _ler_csv_seguro(arquivo):
    tentativas = [
        {"sep": ";", "encoding": "utf-8"},
        {"sep": ",", "encoding": "utf-8"},
        {"sep": ";", "encoding": "latin1"},
        {"sep": ",", "encoding": "latin1"},
        {"sep": None, "engine": "python", "encoding": "utf-8"},
        {"sep": None, "engine": "python", "encoding": "latin1"},
    ]

    for tentativa in tentativas:
        try:
            arquivo.seek(0)
            df_raw = pd.read_csv(arquivo, header=None, **tentativa)

            if df_raw is None or df_raw.empty:
                continue

            header = _detectar_header(df_raw)

            arquivo.seek(0)
            df = pd.read_csv(arquivo, header=header, **tentativa)

            return _limpar_nomes_colunas(df)

        except Exception:
            continue

    st.error("Não foi possível ler o CSV")
    return None


# ==========================================================
# 🔥 DETECTAR ESTOQUE
# ==========================================================
def _eh_coluna_estoque(nome):
    nome = str(nome).lower()

    palavras = [
        "estoque",
        "saldo",
        "quantidade",
        "qtd",
        "qty",
        "disponivel",
        "disponível",
        "stock",
        "inventory",
    ]

    return any(p in nome for p in palavras)


def _normalizar_estoque(valor):
    try:
        texto = str(valor).strip().lower()

        if "esgotado" in texto or "indisponivel" in texto:
            return 0

        if texto == "" or texto == "nan":
            return 0

        return int(float(valor))

    except Exception:
        return 0


# ==========================================================
# MAIN
# ==========================================================
def render_origem_dados():
    st.subheader("Origem dos dados")

    arquivo = st.file_uploader(
        "Envie a planilha",
        type=["xlsx", "xls", "csv"],
    )

    if not arquivo:
        return

    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        df = _ler_csv_seguro(arquivo)
    else:
        df = _ler_excel_seguro(arquivo)

    if df is None or df.empty:
        st.error("Erro ao ler a planilha")
        return

    st.dataframe(_safe_preview(df), width="stretch")

    # detectar estoque automático
    for col in df.columns:
        if _eh_coluna_estoque(col):
            df[col] = df[col].apply(_normalizar_estoque)
            st.success(f"Estoque detectado automaticamente: {col}")
            break

    excel = _exportar_df_exato_para_excel_bytes(df)

    st.download_button(
        "Baixar",
        data=excel,
        file_name="saida.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
