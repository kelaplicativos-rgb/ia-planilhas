from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


ETAPAS_ORDEM = ["origem", "precificacao", "mapeamento", "preview_final", "ia"]


def log_debug(msg: str, nivel: str = "INFO") -> None:
    if "logs_debug" not in st.session_state:
        st.session_state["logs_debug"] = []
    if "debug_logs" not in st.session_state:
        st.session_state["debug_logs"] = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{timestamp}] [{nivel}] {msg}"
    st.session_state["logs_debug"].append(linha)
    st.session_state["debug_logs"].append(linha)


def obter_logs() -> str:
    logs = st.session_state.get("logs_debug") or st.session_state.get("debug_logs") or []
    if isinstance(logs, list):
        return "\n".join(str(item) for item in logs)
    return str(logs or "")


def limpar_logs() -> None:
    st.session_state["logs_debug"] = []
    st.session_state["debug_logs"] = []


def render_log_debug() -> None:
    with st.expander("Logs de debug", expanded=False):
        logs_txt = obter_logs()
        if logs_txt.strip():
            st.text_area("Histórico", value=logs_txt, height=220, key="debug_log_area")
            st.download_button(
                label="Baixar log debug",
                data=logs_txt,
                file_name="debug_log.txt",
                mime="text/plain",
                use_container_width=True,
            )
        else:
            st.info("Nenhum log registrado ainda.")


def render_debug_panel() -> None:
    render_log_debug()


def render_botao_download_logs() -> None:
    logs_txt = obter_logs()
    if logs_txt.strip():
        st.download_button(
            label="Baixar log debug",
            data=logs_txt,
            file_name="debug_log.txt",
            mime="text/plain",
            use_container_width=False,
        )


def safe_df_dados(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def safe_df_estrutura(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def get_etapa(default: str = "origem") -> str:
    etapa = str(st.session_state.get("etapa", default) or default).strip()
    return etapa if etapa in ETAPAS_ORDEM else default


def _indice_etapa(etapa: str) -> int:
    try:
        return ETAPAS_ORDEM.index(etapa)
    except ValueError:
        return 0


def sincronizar_etapa_global(etapa: str) -> None:
    etapa = etapa if etapa in ETAPAS_ORDEM else "origem"
    st.session_state["etapa"] = etapa
    st.session_state["etapa_fluxo"] = etapa
    st.session_state["wizard_etapa_atual"] = etapa

    etapa_maxima = str(st.session_state.get("wizard_etapa_maxima", "origem") or "origem")
    if etapa_maxima not in ETAPAS_ORDEM:
        etapa_maxima = "origem"
    if _indice_etapa(etapa) > _indice_etapa(etapa_maxima):
        st.session_state["wizard_etapa_maxima"] = etapa

    try:
        st.query_params["etapa"] = etapa
    except Exception:
        pass


def ir_para_etapa(etapa: str) -> None:
    sincronizar_etapa_global(etapa)


def voltar_etapa_anterior() -> None:
    etapa_atual = get_etapa()
    indice = max(_indice_etapa(etapa_atual) - 1, 0)
    sincronizar_etapa_global(ETAPAS_ORDEM[indice])


def avancar_etapa() -> None:
    etapa_atual = get_etapa()
    indice = min(_indice_etapa(etapa_atual) + 1, len(ETAPAS_ORDEM) - 1)
    sincronizar_etapa_global(ETAPAS_ORDEM[indice])


def sincronizar_etapa_da_url() -> None:
    try:
        etapa_url = st.query_params.get("etapa", None)
    except Exception:
        etapa_url = None
    if isinstance(etapa_url, list):
        etapa_url = etapa_url[0] if etapa_url else None
    etapa = str(etapa_url or st.session_state.get("etapa", "origem") or "origem").strip()
    if etapa not in ETAPAS_ORDEM:
        etapa = "origem"
    st.session_state["etapa"] = etapa
    if "wizard_etapa_atual" not in st.session_state:
        st.session_state["wizard_etapa_atual"] = etapa


def garantir_estado_base() -> None:
    defaults = {
        "etapa": "origem",
        "etapa_fluxo": "origem",
        "wizard_etapa_atual": "origem",
        "wizard_etapa_maxima": "origem",
        "tipo_operacao": "cadastro",
        "tipo_operacao_bling": "cadastro",
        "deposito_nome": "",
        "logs_debug": [],
        "debug_logs": [],
    }
    for chave, valor in defaults.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    for chave_df in ["df_origem", "df_precificado", "df_modelo", "df_final", "df_saida", "df_mapeado"]:
        if chave_df not in st.session_state or st.session_state.get(chave_df) is None:
            st.session_state[chave_df] = pd.DataFrame()
