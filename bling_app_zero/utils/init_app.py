
from __future__ import annotations

import pandas as pd
import streamlit as st


def _ensure(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default


def _ensure_df(key: str):
    if key not in st.session_state or st.session_state.get(key) is None:
        st.session_state[key] = pd.DataFrame()


def _remover_chaves(chaves: list[str]) -> None:
    for chave in chaves:
        if chave in st.session_state:
            del st.session_state[chave]


def init_app_state() -> None:
    # ============================================================
    # NOVO FLUXO ÚNICO
    # ============================================================
    _ensure("app_version", "")
    _ensure("modo_execucao", "ia_orquestrador")

    _ensure("etapa", "ia")
    _ensure("etapa_origem", "ia")
    _ensure("etapa_fluxo", "ia")

    # ============================================================
    # DADOS PRINCIPAIS
    # ============================================================
    _ensure_df("df_origem")
    _ensure_df("df_saida")
    _ensure_df("df_precificado")
    _ensure_df("df_calc_precificado")
    _ensure_df("df_mapeado")
    _ensure_df("df_preview_mapeamento")
    _ensure_df("df_final")
    _ensure_df("df_modelo_operacao")

    # ============================================================
    # CONTROLE DE OPERAÇÃO
    # ============================================================
    _ensure("tipo_operacao", "Cadastro de Produtos")
    _ensure("tipo_operacao_radio", "Cadastro de Produtos")
    _ensure("tipo_operacao_bling", "cadastro")
    _ensure("deposito_nome", "")

    # ============================================================
    # IA ORQUESTRADOR
    # ============================================================
    _ensure("ia_comando_usuario", "")
    _ensure("ia_plano_execucao", {})
    _ensure("ia_plano_preview", {})
    _ensure("ia_erro_execucao", "")
    _ensure("ia_fluxo_ativo", True)
    _ensure("fornecedor_ia", "")
    _ensure("categoria_ia", "")
    _ensure("origem_tipo_ia", "")

    # ============================================================
    # APOIO DE COLETA
    # ============================================================
    _ensure("origem_site_url", "")
    _ensure("origem_categoria_api", "")
    _ensure("padrao_disponivel_site", 10)

    # ============================================================
    # MAPEAMENTO
    # ============================================================
    _ensure("mapping_origem", {})
    _ensure("mapping_origem_rascunho", {})
    _ensure("mapping_origem_defaults", {})

    # ============================================================
    # DEBUG
    # ============================================================
    _ensure("debug_logs", [])
    _ensure("app_pronto", True)

    # ============================================================
    # LIMPEZA DEFINITIVA DO FLUXO MANUAL
    # ============================================================
    _remover_chaves(
        [
            "origem_tipo",
            "origem_tipo_radio",
            "origem_upload_fornecedor",
            "origem_upload_xml",
            "origem_fornecedor_api",
            "origem_dados_radio",
            "modelo_upload",
            "modelo_tipo",
            "modelo_arquivo",
            "preview_linhas",
            "precificacao_config",
            "mapeamento_config",
            "colunas_mapeadas",
            "modo_fluxo_manual",
            "btn_modo_fluxo_manual",
        ]
    )
