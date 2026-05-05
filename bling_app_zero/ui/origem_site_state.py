from __future__ import annotations

import pandas as pd
import streamlit as st


CHAVE_DF_SITE_TRAVADO = "origem_site_df_travado"
CHAVE_DF_SITE_TRAVADO_BACKUP = "origem_site_df_travado_backup"


def _nome_preset(preset) -> str:
    nome = getattr(preset, "nome", "")
    nome = str(nome or "").strip()
    return nome or "AUTO_TOTAL"


def _df_valido(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0 and not df.empty


def guardar_resultado(df: pd.DataFrame, urls, preset, motor):
    """Guarda a captura por site em todas as chaves usadas pelo fluxo.

    Além de df_origem/df_saida, mantém um cofre próprio da busca por site.
    Assim, se o navegador atualizar, se o Streamlit fizer rerun, ou se outra etapa
    mexer nas chaves principais, a tela consegue restaurar o resultado sem obrigar
    o usuário a buscar tudo novamente.
    """
    base = df.copy().fillna("") if isinstance(df, pd.DataFrame) else pd.DataFrame()

    st.session_state["df_origem"] = base.copy()
    st.session_state["df_saida"] = base.copy()

    if _df_valido(base):
        st.session_state[CHAVE_DF_SITE_TRAVADO] = base.copy()
        st.session_state[CHAVE_DF_SITE_TRAVADO_BACKUP] = base.copy()
        st.session_state["origem_site_resultado_travado"] = True

    st.session_state["origem_site_urls"] = list(urls or [])
    st.session_state["origem_site_total_produtos"] = len(base)
    st.session_state["origem_site_config"] = {
        "preset": _nome_preset(preset),
        "motor": str(motor or "AUTO_TOTAL"),
    }


def restaurar_resultado_site_travado() -> pd.DataFrame | None:
    """Restaura o último resultado da busca por site quando df_origem/df_saida sumirem."""
    candidatos = [
        st.session_state.get(CHAVE_DF_SITE_TRAVADO),
        st.session_state.get(CHAVE_DF_SITE_TRAVADO_BACKUP),
    ]

    for candidato in candidatos:
        if _df_valido(candidato):
            base = candidato.copy().fillna("")
            st.session_state["df_origem"] = base.copy()
            st.session_state["df_saida"] = base.copy()
            st.session_state[CHAVE_DF_SITE_TRAVADO] = base.copy()
            st.session_state[CHAVE_DF_SITE_TRAVADO_BACKUP] = base.copy()
            st.session_state["origem_site_resultado_travado"] = True
            st.session_state["origem_site_total_produtos"] = len(base)
            return base

    return None


def limpar_busca_site():
    for key in [
        "df_origem",
        "df_saida",
        CHAVE_DF_SITE_TRAVADO,
        CHAVE_DF_SITE_TRAVADO_BACKUP,
        "origem_site_resultado_travado",
        "origem_site_urls",
        "origem_site_total_produtos",
        "origem_site_config",
    ]:
        st.session_state.pop(key, None)
