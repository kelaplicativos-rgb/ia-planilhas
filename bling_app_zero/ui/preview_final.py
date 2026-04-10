from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    exportar_excel_bytes,
    limpar_gtin_invalido,
    log_debug,
    validar_campos_obrigatorios,
)


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _get_df_fluxo() -> pd.DataFrame | None:
    """
    Ordem de prioridade do fluxo final:
    1) df_final
    2) df_saida
    3) df_precificado
    4) df_calc_precificado
    5) df_origem
    """
    for chave in ["df_final", "df_saida", "df_precificado", "df_calc_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            return df.copy()
    return None


def _normalizar_validacao(resultado_validacao) -> bool:
    try:
        if isinstance(resultado_validacao, bool):
            return resultado_validacao
        if resultado_validacao is None:
            return True
        if isinstance(resultado_validacao, dict):
            return len(resultado_validacao) == 0
        if isinstance(resultado_validacao, (list, tuple, set)):
            return len(resultado_validacao) == 0
        return bool(resultado_validacao)
    except Exception:
        return False


def render_preview_final() -> None:
    st.subheader("Preview final")

    df_fluxo = _get_df_fluxo()
    if not _safe_df(df_fluxo):
        st.warning("Nenhum dado disponível para o preview final.")
        log_debug("Preview final sem DataFrame disponível", "ERRO")
        return

    try:
        log_debug(
            f"Preview final carregado com {len(df_fluxo)} linha(s) e {len(df_fluxo.columns)} coluna(s)"
        )
    except Exception:
        pass

    with st.expander("Ver dados finais", expanded=False):
        st.dataframe(df_fluxo.head(20), use_container_width=True)

    try:
        df_download = limpar_gtin_invalido(df_fluxo.copy())
    except Exception as e:
        log_debug(f"Erro ao limpar GTIN inválido no preview final: {e}", "ERRO")
        df_download = df_fluxo.copy()

    try:
        validacao_ok = _normalizar_validacao(validar_campos_obrigatorios(df_download))
    except Exception as e:
        log_debug(f"Erro na validação de campos obrigatórios: {e}", "ERRO")
        validacao_ok = False

    if not validacao_ok:
        st.error("Preencha os campos obrigatórios antes do download.")
        return

    try:
        excel_bytes = exportar_excel_bytes(df_download)
    except Exception as e:
        log_debug(f"Erro ao gerar Excel final: {e}", "ERRO")
        st.error("Não foi possível gerar a planilha final.")
        return

    if not excel_bytes:
        st.error("Não foi possível gerar a planilha final.")
        return

    st.download_button(
        "⬇️ Baixar planilha final",
        excel_bytes,
        "bling_final.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅️ Voltar para mapeamento",
            use_container_width=True,
            key="btn_voltar_mapeamento_preview",
        ):
            st.session_state["etapa_origem"] = "mapeamento"
            st.session_state["etapa"] = "mapeamento"
            st.session_state["etapa_fluxo"] = "mapeamento"
            st.rerun()

    with col2:
        if st.button(
            "Atualizar preview",
            use_container_width=True,
            key="btn_atualizar_preview_final",
        ):
            st.session_state["df_final"] = df_fluxo.copy()
            st.rerun()
