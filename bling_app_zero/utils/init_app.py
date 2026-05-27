from __future__ import annotations

import pandas as pd
import streamlit as st


def _ensure(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default


def _ensure_df(key: str) -> None:
    if key not in st.session_state or st.session_state.get(key) is None:
        st.session_state[key] = pd.DataFrame()


def _remover_chaves(chaves: list[str]) -> None:
    for chave in chaves:
        st.session_state.pop(chave, None)


def init_app_state() -> None:
    # Estado base do fluxo principal
    _ensure("app_version", "")
    _ensure("modo_execucao", "wizard_bling")
    _ensure("etapa", "origem")
    _ensure("etapa_origem", "origem")
    _ensure("etapa_fluxo", "origem")

    # DataFrames principais
    _ensure_df("df_origem")
    _ensure_df("df_saida")
    _ensure_df("df_precificado")
    _ensure_df("df_calc_precificado")
    _ensure_df("df_mapeado")
    _ensure_df("df_preview_mapeamento")
    _ensure_df("df_final")
    _ensure_df("df_modelo")
    _ensure_df("df_modelo_operacao")

    # Operação / Bling
    _ensure("tipo_operacao", "cadastro")
    _ensure("tipo_operacao_radio", "Cadastro de Produtos")
    _ensure("tipo_operacao_bling", "cadastro")
    _ensure("deposito_nome", "")

    # Mapeamento
    _ensure("mapping_origem", {})
    _ensure("mapping_origem_rascunho", {})
    _ensure("mapping_origem_defaults", {})

    # Logs
    _ensure("debug_logs", [])
    _ensure("logs_debug", [])
    _ensure("app_pronto", True)

    # Site / busca
    _ensure("origem_site_url", "")
    _ensure("origem_categoria_api", "")
    _ensure("padrao_disponivel_site", 10)

    # Remove sobras antigas que causavam duplicidade de fluxo manual
    _remover_chaves(
        [
            "modo_fluxo_manual",
            "btn_modo_fluxo_manual",
        ]
    )


def init_app() -> None:
    init_app_state()


def inicializar_app() -> None:
    init_app_state()
