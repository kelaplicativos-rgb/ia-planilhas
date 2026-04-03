import pandas as pd
import streamlit as st

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
        return df
    except:
        try:
            df = pd.read_csv(
                arquivo,
                sep=";",
                engine="python",
                encoding="latin-1",
                on_bad_lines="skip"
            )
            return df
        except:
            df = pd.read_excel(arquivo)
            return df


# =========================
# 👁️ PREVIEW INTELIGENTE
# =========================
def mostrar_preview(df, nome="Planilha"):
    st.subheader(f"📄 {nome}")

    if df is None or df.empty:
        st.warning("⚠️ Planilha vazia")
        return

    # =========================
    # 🧠 COLUNAS DETECTADAS
    # =========================
    st.success("✅ Colunas identificadas automaticamente:")
    st.write(list(df.columns))

    # =========================
    # 👁️ PREVIEW (1 LINHA)
    # =========================
    st.info("🔍 Preview (1 linha):")
    st.dataframe(df.head(1), use_container_width=True)

    # =========================
    # 🔘 BOTÃO EXPANDIR
    # =========================
    if "mostrar_tudo_" + nome not in st.session_state:
        st.session_state["mostrar_tudo_" + nome] = False

    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"👁️ Ver tudo ({nome})"):
            st.session_state["mostrar_tudo_" + nome] = True

    with col2:
        if st.button(f"❌ Ocultar ({nome})"):
            st.session_state["mostrar_tudo_" + nome] = False

    # =========================
    # 📊 MOSTRAR COMPLETO
    # =========================
    if st.session_state["mostrar_tudo_" + nome]:
        st.success("📊 Visualização completa:")
        st.dataframe(df, use_container_width=True)
