import pandas as pd
import streamlit as st
from io import BytesIO


# =========================
# 📥 LEITURA INTELIGENTE
# =========================
def ler_planilha(arquivo):
    try:
        df = pd.read_csv(
            arquivo,
            sep=None,
            engine="python",
            encoding="utf-8",
            on_bad_lines="skip"
        )
    except Exception:
        try:
            df = pd.read_csv(
                arquivo,
                sep=";",
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )
        except Exception:
            df = pd.read_excel(arquivo)

    df = limpar_valores_vazios(df)
    df = normalizar_colunas(df)

    return df


# =========================
# 🧹 LIMPAR VALORES VAZIOS
# =========================
def limpar_valores_vazios(df):
    return df.fillna("").infer_objects(copy=False)


# =========================
# 🔤 NORMALIZAR COLUNAS
# =========================
def normalizar_colunas(df):
    df = df.copy()
    df.columns = (
        pd.Index(df.columns)
        .map(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )
    return df


# =========================
# 💾 SALVAR EXCEL EM BYTES
# =========================
def salvar_excel_bytes(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    output.seek(0)
    return output.getvalue()


# =========================
# 🔘 BOTÃO ABRIR/FECHAR BLOCO
# =========================
def bloco_toggle(titulo, chave):
    if chave not in st.session_state:
        st.session_state[chave] = False

    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"👁️ Mostrar {titulo}", key=f"mostrar_{chave}"):
            st.session_state[chave] = True

    with col2:
        if st.button(f"❌ Ocultar {titulo}", key=f"ocultar_{chave}"):
            st.session_state[chave] = False

    return st.session_state[chave]
