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
    except:
        try:
            df = pd.read_csv(
                arquivo,
                sep=";",
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )
        except:
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
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )
    return df


# =========================
# 💾 SALVAR EXCEL (BYTES)
# =========================
def salvar_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


# =========================
# 👁️ PREVIEW INTELIGENTE
# =========================
def mostrar_preview(df, nome="Planilha"):
    st.subheader(f"📄 {nome}")

    if df is None or df.empty:
        st.warning("⚠️ Planilha vazia")
        return

    st.success("✅ Colunas identificadas automaticamente:")
    st.write(list(df.columns))

    st.info("🔍 Preview (1 linha):")
    st.dataframe(df.head(1), use_container_width=True)

    chave = f"mostrar_tudo_{nome}"

    if chave not in st.session_state:
        st.session_state[chave] = False

    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"👁️ Ver tudo ({nome})", key=f"ver_{nome}"):
            st.session_state[chave] = True

    with col2:
        if st.button(f"❌ Ocultar ({nome})", key=f"ocultar_{nome}"):
            st.session_state[chave] = False

    if st.session_state[chave]:
        st.success("📊 Visualização completa:")
        st.dataframe(df, use_container_width=True)
