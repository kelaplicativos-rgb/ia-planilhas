import streamlit as st
import pandas as pd

from ..utils.excel import (
    ler_planilha,
    limpar_valores_vazios,
    normalizar_colunas,
    bloco_toggle,
)


# =========================
# 📥 CARREGAR PLANILHA
# =========================
def carregar_planilha(arquivo):
    if arquivo is None:
        return None

    df = ler_planilha(arquivo)
    df = limpar_valores_vazios(df)
    df = normalizar_colunas(df)

    return df


# =========================
# ✅ VALIDAR PLANILHA
# =========================
def validar_planilha_basica(df):
    if df is None:
        return False, "Nenhuma planilha carregada."

    if not isinstance(df, pd.DataFrame):
        return False, "Arquivo inválido."

    if df.empty:
        return False, "A planilha está vazia."

    return True, "Planilha válida."


# =========================
# 👀 PREVIEW COMPLETO CONTROLADO
# =========================
def preview(
    df,
    nome="Planilha",
    colunas_detectadas=None,
    mapeamento_manual=None,
    mapeamento_final=None,
):
    st.subheader(f"📄 {nome}")

    if df is None or df.empty:
        st.warning("⚠️ Planilha vazia")
        return

    chave_base = nome.strip().lower().replace(" ", "_")

    # =====================================
    # 👀 PREVIEW
    # =====================================
    abrir_preview = bloco_toggle(
        "Preview",
        f"{chave_base}_preview_aberto"
    )

    if abrir_preview:
        st.info("👀 Preview")
        st.dataframe(df.head(1), use_container_width=True)

    # =====================================
    # 🔎 COLUNAS IDENTIFICADAS AUTOMATICAMENTE
    # =====================================
    abrir_colunas = bloco_toggle(
        "Colunas identificadas automaticamente",
        f"{chave_base}_colunas_aberto"
    )

    if abrir_colunas:
        st.success("🔎 Colunas identificadas automaticamente")

        if colunas_detectadas is None:
            colunas_detectadas = list(df.columns)

        if isinstance(colunas_detectadas, dict):
            st.json(colunas_detectadas)
        else:
            st.write(colunas_detectadas)

    # =====================================
    # 🛠️ AJUSTE MANUAL DAS COLUNAS
    # =====================================
    abrir_ajuste_manual = bloco_toggle(
        "Ajuste manual das colunas",
        f"{chave_base}_ajuste_manual_aberto"
    )

    if abrir_ajuste_manual:
        st.warning("🛠️ Ajuste manual das colunas")

        if not mapeamento_manual:
            st.caption("Nenhum ajuste manual disponível no momento.")
        else:
            st.write(mapeamento_manual)

    # =====================================
    # ✅ MAPEAMENTO FINAL QUE SERÁ USADO
    # =====================================
    abrir_mapeamento_final = bloco_toggle(
        "Mapeamento final que será usado",
        f"{chave_base}_mapeamento_final_aberto"
    )

    if abrir_mapeamento_final:
        st.success("✅ Mapeamento final que será usado")

        if not mapeamento_final:
            st.caption("Nenhum mapeamento final disponível no momento.")
        else:
            st.write(mapeamento_final)
