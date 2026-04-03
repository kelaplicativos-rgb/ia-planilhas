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

    # =========================
    # 🧹 LIMPEZA EXTREMA (SEM WARNING)
    # =========================
    df = df.fillna("").infer_objects(copy=False)

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
    # 🔘 CONTROLE DE ESTADO
    # =========================
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

    # =========================
    # 📊 MOSTRAR COMPLETO
    # =========================
    if st.session_state[chave]:
        st.success("📊 Visualização completa:")
        st.dataframe(df, use_container_width=True)
