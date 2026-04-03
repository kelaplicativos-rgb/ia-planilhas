import pandas as pd
import streamlit as st

from ..utils.excel import (
    ler_planilha,
    limpar_valores_vazios,
    normalizar_colunas,
    bloco_toggle,
)


# =========================================================
# CARREGAR PLANILHA
# =========================================================
def carregar_planilha(arquivo):
    if arquivo is None:
        return None

    df = ler_planilha(arquivo)

    if df is None:
        return None

    df = limpar_valores_vazios(df)
    df = normalizar_colunas(df)

    return df


# =========================================================
# VALIDAÇÃO BÁSICA
# =========================================================
def validar_planilha_basica(df):
    if df is None:
        return False, "Nenhuma planilha carregada."

    if not isinstance(df, pd.DataFrame):
        return False, "Arquivo inválido."

    if df.empty:
        return False, "A planilha está vazia."

    if len(df.columns) == 0:
        return False, "A planilha não possui colunas."

    return True, "Planilha válida."


# =========================================================
# HELPERS INTERNOS
# =========================================================
def _normalizar_nome_chave(nome):
    return str(nome).strip().lower().replace(" ", "_")


def _render_colunas_detectadas(colunas_detectadas, df):
    st.success("🔎 Colunas identificadas automaticamente")

    if not colunas_detectadas:
        st.caption("Nenhuma coluna detectada automaticamente.")
        return

    if isinstance(colunas_detectadas, dict):
        df_cols = pd.DataFrame(
            [
                {"campo_destino": campo, "coluna_origem": coluna}
                for campo, coluna in colunas_detectadas.items()
            ]
        )

        if df_cols.empty:
            st.caption("Nenhuma coluna detectada automaticamente.")
        else:
            st.dataframe(df_cols, use_container_width=True, hide_index=True)
        return

    if isinstance(colunas_detectadas, list):
        if len(colunas_detectadas) == 0:
            st.caption("Nenhuma coluna detectada automaticamente.")
        else:
            st.write(colunas_detectadas)
        return

    st.write(list(df.columns))


def _render_ajuste_manual(mapeamento_manual):
    st.warning("🛠️ Ajuste manual das colunas")

    if not mapeamento_manual:
        st.caption("Nenhum ajuste manual aplicado no momento.")
        return

    df_manual = pd.DataFrame(
        [
            {"campo_destino": campo, "coluna_origem": coluna}
            for campo, coluna in mapeamento_manual.items()
        ]
    )

    if df_manual.empty:
        st.caption("Nenhum ajuste manual aplicado no momento.")
        return

    st.dataframe(df_manual, use_container_width=True, hide_index=True)


def _render_mapeamento_final(mapeamento_final):
    st.success("✅ Mapeamento final que será usado")

    if not mapeamento_final:
        st.caption("Nenhum mapeamento final disponível no momento.")
        return

    df_final = pd.DataFrame(
        [
            {"campo_destino": campo, "coluna_origem": coluna}
            for campo, coluna in mapeamento_final.items()
        ]
    )

    if df_final.empty:
        st.caption("Nenhum mapeamento final disponível no momento.")
        return

    st.dataframe(df_final, use_container_width=True, hide_index=True)


# =========================================================
# PREVIEW BLINDADO
# =========================================================
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

    chave_base = _normalizar_nome_chave(nome)

    # =====================================================
    # 👀 PREVIEW
    # =====================================================
    abrir_preview = bloco_toggle(
        "Preview",
        f"{chave_base}_preview_aberto"
    )

    if abrir_preview:
        st.info("👀 Preview")
        st.dataframe(df.head(1), use_container_width=True)

    # =====================================================
    # 🔎 COLUNAS IDENTIFICADAS AUTOMATICAMENTE
    # =====================================================
    abrir_colunas = bloco_toggle(
        "Colunas identificadas automaticamente",
        f"{chave_base}_colunas_aberto"
    )

    if abrir_colunas:
        _render_colunas_detectadas(colunas_detectadas, df)

    # =====================================================
    # 🛠️ AJUSTE MANUAL DAS COLUNAS
    # =====================================================
    abrir_ajuste_manual = bloco_toggle(
        "Ajuste manual das colunas",
        f"{chave_base}_ajuste_manual_aberto"
    )

    if abrir_ajuste_manual:
        _render_ajuste_manual(mapeamento_manual)

    # =====================================================
    # ✅ MAPEAMENTO FINAL QUE SERÁ USADO
    # =====================================================
    abrir_mapeamento_final = bloco_toggle(
        "Mapeamento final que será usado",
        f"{chave_base}_mapeamento_final_aberto"
    )

    if abrir_mapeamento_final:
        _render_mapeamento_final(mapeamento_final)
