import pandas as pd
import streamlit as st
import io


def ler_planilha(arquivo):
    try:
        if arquivo.name.endswith(".csv"):
            return pd.read_csv(arquivo, dtype=str)
        else:
            return pd.read_excel(arquivo, dtype=str)
    except Exception:
        return None


def limpar_valores_vazios(df):
    if df is None:
        return pd.DataFrame()

    df = df.fillna("")
    df = df.astype(str)
    return df


def normalizar_colunas(df):
    if df is None:
        return pd.DataFrame()

    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def gerar_preview(df, linhas=1):
    if df is None:
        return pd.DataFrame()
    return df.head(linhas)


def salvar_excel_bytes(df):
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    return buffer.getvalue()


def bloco_toggle(nome, chave):
    if chave not in st.session_state:
        st.session_state[chave] = False

    if st.button(f"👁️ {nome}", key=f"btn_{chave}"):
        st.session_state[chave] = not st.session_state[chave]

    return st.session_state[chave]
