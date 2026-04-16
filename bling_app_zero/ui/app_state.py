
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_dataframe import garantir_dataframe, safe_df_dados
from bling_app_zero.ui.app_text import normalizar_texto


def _agent_state_disponivel() -> bool:
    try:
        import bling_app_zero.agent.agent_memory  # noqa: F401
        return True
    except Exception:
        return False


def get_agent_state_safe():
    if not _agent_state_disponivel():
        return None

    try:
        from bling_app_zero.agent.agent_memory import get_agent_state
        return get_agent_state()
    except Exception:
        return None


def _safe_save_agent_state(state) -> None:
    if state is None:
        return

    try:
        from bling_app_zero.agent.agent_memory import save_agent_state
        save_agent_state(state)
    except Exception:
        pass


def _safe_set_agent_stage(etapa: str) -> None:
    state = get_agent_state_safe()
    if state is None:
        return

    etapa_limpa = normalizar_texto(etapa) or "ia_orquestrador"
    state.etapa_atual = etapa_limpa

    if etapa_limpa == "final":
        state.status_execucao = "final_pronto"
    elif etapa_limpa == "mapeamento":
        state.status_execucao = "mapeamento_pronto"
    elif etapa_limpa == "validacao":
        state.status_execucao = "revisao"
    elif etapa_limpa == "precificacao":
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "base_pronta"
    elif etapa_limpa == "ia_orquestrador":
        if normalizar_texto(getattr(state, "status_execucao", "")) == "":
            state.status_execucao = "idle"

    _safe_save_agent_state(state)


def sincronizar_etapa_global(etapa: str) -> None:
    etapa_limpa = normalizar_texto(etapa) or "ia_orquestrador"

    st.session_state["etapa"] = etapa_limpa
    st.session_state["etapa_origem"] = etapa_limpa
    st.session_state["etapa_fluxo"] = etapa_limpa

    if etapa_limpa == "ia_orquestrador":
        st.session_state["modo_execucao"] = "ia_orquestrador"

    _safe_set_agent_stage(etapa_limpa)


def voltar_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)


def ir_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)
    st.rerun()


def _limpar_chaves_estado(chaves: list[str]) -> None:
    for chave in chaves:
        st.session_state.pop(chave, None)


def limpar_estado_fluxo() -> None:
    _limpar_chaves_estado(
        [
            "df_origem",
            "df_normalizado",
            "df_precificado",
            "df_mapeado",
            "df_saida",
            "df_final",
            "df_calc_precificado",
            "df_preview_mapeamento",
            "df_modelo",
            "origem_upload_nome",
            "origem_upload_bytes",
            "origem_upload_tipo",
            "origem_upload_ext",
            "modelo_upload_nome",
            "modelo_upload_bytes",
            "modelo_upload_tipo",
            "modelo_upload_ext",
            "site_fornecedor_url",
            "site_fornecedor_diagnostico",
            "site_busca_diagnostico_df",
            "site_busca_diagnostico_total_descobertos",
            "site_busca_diagnostico_total_validos",
            "site_busca_diagnostico_total_rejeitados",
        ]
    )

    for chave in [
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
    ]:
        st.session_state[chave] = {}

    for chave in [
        "ia_plano_preview",
        "ia_erro_execucao",
    ]:
        st.session_state[chave] = ""

    if _agent_state_disponivel():
        try:
            from bling_app_zero.agent.agent_memory import reset_agent_state

            reset_agent_state(
                preserve_dataframe_keys=False,
                preserve_operacao=False,
                preserve_deposito=False,
            )
        except Exception:
            pass

    sincronizar_etapa_global("ia_orquestrador")


def obter_df_fluxo_preferencial() -> pd.DataFrame:
    state = get_agent_state_safe()

    if state is not None:
        for chave in [
            getattr(state, "df_final_key", ""),
            getattr(state, "df_mapeado_key", ""),
            getattr(state, "df_normalizado_key", ""),
            getattr(state, "df_origem_key", ""),
        ]:
            chave_limpa = normalizar_texto(chave)
            if not chave_limpa:
                continue

            df = st.session_state.get(chave_limpa)
            if safe_df_dados(df):
                return garantir_dataframe(df)

    for chave in [
        "df_final",
        "df_saida",
        "df_mapeado",
        "df_precificado",
        "df_calc_precificado",
        "df_normalizado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return garantir_dataframe(df)

    return pd.DataFrame()
