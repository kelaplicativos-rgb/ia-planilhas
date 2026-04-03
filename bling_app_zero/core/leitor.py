import pandas as pd
import streamlit as st

from ..utils.excel import ler_planilha


def carregar_planilha(arquivo):
    if arquivo is None:
        return None
    return ler_planilha(arquivo)


def validar_planilha(df):
    if df is None:
        return False, "Nenhuma planilha carregada."
    if df.empty:
        return False, "A planilha está vazia."
    return True, "Planilha válida."


def _init_toggle(chave: str):
    if chave not in st.session_state:
        st.session_state[chave] = False


def _bloco_toggle(titulo: str, chave_base: str):
    _init_toggle(chave_base)

    col1, col2 = st.columns(2)

    with col1:
        if st.button(f"👁️ Mostrar {titulo}", key=f"btn_show_{chave_base}"):
            st.session_state[chave_base] = True

    with col2:
        if st.button(f"❌ Ocultar {titulo}", key=f"btn_hide_{chave_base}"):
            st.session_state[chave_base] = False

    return st.session_state[chave_base]


def preview(df, nome="Planilha"):
    st.subheader(f"📄 {nome}")

    if df is None or df.empty:
        st.warning("⚠️ Planilha vazia")
        return

    # =========================
    # 👀 PREVIEW
    # =========================
    mostrar_preview = _bloco_toggle(
        titulo="Preview",
        chave_base=f"{nome}_preview"
    )

    if mostrar_preview:
        st.info("🔍 Preview (1 linha):")
        st.dataframe(df.head(1), use_container_width=True)

    # =========================
    # 🔎 COLUNAS IDENTIFICADAS
    # =========================
    mostrar_colunas = _bloco_toggle(
        titulo="Colunas identificadas automaticamente",
        chave_base=f"{nome}_colunas"
    )

    if mostrar_colunas:
        st.success("🔎 Colunas identificadas automaticamente")
        st.write(list(df.columns))

    # =========================
    # 🛠️ AJUSTE MANUAL DAS COLUNAS
    # =========================
    mostrar_ajuste = _bloco_toggle(
        titulo="Ajuste manual das colunas",
        chave_base=f"{nome}_ajuste_manual"
    )

    if mostrar_ajuste:
        st.warning("🛠️ Ajuste manual das colunas")
        st.caption("Aqui entra a interface manual de seleção/mapeamento das colunas.")

    # =========================
    # ✅ MAPEAMENTO FINAL
    # =========================
    mostrar_mapeamento = _bloco_toggle(
        titulo="Mapeamento final que será usado",
        chave_base=f"{nome}_mapeamento_final"
    )

    if mostrar_mapeamento:
        st.success("✅ Mapeamento final que será usado")
        st.caption("Aqui entra o resultado final do mapeamento aplicado no processamento.")
