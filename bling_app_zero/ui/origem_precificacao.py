
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug, safe_df_dados


def _sincronizar_etapa(etapa: str) -> None:
    st.session_state["etapa"] = etapa
    st.session_state["etapa_origem"] = etapa
    st.session_state["etapa_fluxo"] = etapa


def _obter_df_base() -> pd.DataFrame:
    for chave in [
        "df_saida",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return pd.DataFrame()


def _tem_preco_calculado(df: pd.DataFrame) -> bool:
    if not safe_df_dados(df):
        return False

    colunas_alvo = {
        "preco calculado",
        "preço calculado",
        "preco de venda",
        "preço de venda",
        "preco unitario (obrigatorio)",
        "preço unitário (obrigatório)",
    }

    for col in df.columns:
        if str(col).strip().lower() in colunas_alvo:
            return True

    return False


def render_origem_precificacao() -> pd.DataFrame | None:
    """
    Compatibilidade com imports antigos.

    O fluxo manual de precificação foi removido.
    A precificação agora é definida pela IA no momento da execução do fluxo.
    """
    st.markdown("### Precificação")
    st.info(
        "O fluxo manual de precificação foi removido. "
        "Agora a IA decide automaticamente se mantém o preço original "
        "ou aplica precificação antes do mapeamento."
    )

    df_base = _obter_df_base()

    if not safe_df_dados(df_base):
        st.warning("Nenhuma base foi preparada ainda. Execute a IA primeiro.")
        if st.button("Ir para IA Orquestrador", use_container_width=True, key="precificacao_ir_ia"):
            _sincronizar_etapa("ia")
            st.rerun()
        return None

    if _tem_preco_calculado(df_base):
        st.success("A base já está com preço preparado pela IA.")
    else:
        st.caption(
            "A base atual será mantida como veio da IA. "
            "Se quiser outra regra, refaça a execução com um comando diferente."
        )

    with st.expander("Preview da base atual", expanded=False):
        st.dataframe(df_base.head(50), use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para IA", use_container_width=True, key="precificacao_voltar_ia"):
            _sincronizar_etapa("ia")
            st.rerun()

    with col2:
        if st.button("Continuar para mapeamento ➜", use_container_width=True, key="precificacao_ir_mapeamento"):
            st.session_state["df_saida"] = df_base.copy()
            st.session_state["df_precificado"] = df_base.copy()
            _sincronizar_etapa("mapeamento")
            log_debug("Compatibilidade de precificação acionada. Fluxo enviado para mapeamento.", "INFO")
            st.rerun()

    return df_base
