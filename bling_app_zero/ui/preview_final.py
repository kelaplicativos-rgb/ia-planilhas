
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    exportar_csv_bytes,
    gerar_nome_arquivo_download,
    ir_para_etapa,
    log_debug,
    safe_df_dados,
    validar_campos_obrigatorios,
)


def _resolver_df_final() -> pd.DataFrame | None:
    for chave in ["df_final", "df_saida", "df_preview_mapeamento", "df_precificado", "df_origem"]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


def _render_resumo_validacao(resultado_validacao: dict) -> None:
    if resultado_validacao.get("ok"):
        st.success("Validação básica concluída com sucesso.")
        return

    faltantes = resultado_validacao.get("faltantes", [])
    alertas = resultado_validacao.get("alertas", [])

    if faltantes:
        st.error("Campos obrigatórios pendentes: " + ", ".join([str(x) for x in faltantes]))
    for alerta in alertas:
        st.warning(str(alerta))


def render_preview_final(df_final: pd.DataFrame | None = None) -> pd.DataFrame | None:
    df_base = df_final if safe_df_dados(df_final) else _resolver_df_final()

    st.markdown("### Preview final")
    st.caption("Valide a saída final e faça o download em CSV.")

    if not safe_df_dados(df_base):
        st.warning("Nenhum DataFrame final disponível para download.")
        return None

    resultado_validacao = validar_campos_obrigatorios(df_base)
    _render_resumo_validacao(resultado_validacao)

    with st.expander("Preview da planilha final", expanded=True):
        st.dataframe(df_base.head(20), use_container_width=True, hide_index=True)
        st.caption(f"{len(df_base)} linha(s) | {len(df_base.columns)} coluna(s)")

    csv_bytes = exportar_csv_bytes(df_base)
    nome_arquivo = gerar_nome_arquivo_download()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_final_voltar"):
            ir_para_etapa("mapeamento")

    with col2:
        st.download_button(
            "Baixar CSV final",
            data=csv_bytes,
            file_name=nome_arquivo,
            mime="text/csv",
            use_container_width=True,
            key="btn_download_final_csv",
            disabled=not bool(csv_bytes),
        )

    st.session_state["df_final"] = df_base.copy()
    log_debug("[PREVIEW_FINAL] preview renderizado com sucesso.", "INFO")
    return df_base
