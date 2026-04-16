
from __future__ import annotations

import streamlit as st
import pandas as pd


# ============================================================
# HELPERS
# ============================================================

def _ensure(key: str, default):
    if key not in st.session_state:
        st.session_state[key] = default


def _ensure_df(key: str):
    if key not in st.session_state or st.session_state.get(key) is None:
        st.session_state[key] = pd.DataFrame()


# ============================================================
# INIT PRINCIPAL
# ============================================================

def init_app_state() -> None:
    # -----------------------------
    # CONTROLE GERAL
    # -----------------------------
    _ensure("app_version", "")
    _ensure("modo_execucao", "fluxo_manual")  # fluxo_manual | ia_orquestrador

    # -----------------------------
    # ETAPAS DO FLUXO
    # -----------------------------
    _ensure("etapa", "origem")
    _ensure("etapa_origem", "origem")

    # -----------------------------
    # TIPO DE OPERAÇÃO
    # -----------------------------
    _ensure("tipo_operacao", "Cadastro de Produtos")
    _ensure("tipo_operacao_radio", "Cadastro de Produtos")
    _ensure("tipo_operacao_bling", "cadastro")  # cadastro | estoque

    # -----------------------------
    # DATAFRAMES PRINCIPAIS
    # -----------------------------
    _ensure_df("df_origem")
    _ensure_df("df_saida")
    _ensure_df("df_precificado")
    _ensure_df("df_calc_precificado")
    _ensure_df("df_mapeado")
    _ensure_df("df_preview_mapeamento")
    _ensure_df("df_final")

    # modelo base da operação (cadastro / estoque)
    _ensure_df("df_modelo_operacao")

    # -----------------------------
    # ORIGEM
    # -----------------------------
    _ensure("origem_tipo", "")
    _ensure("origem_tipo_radio", "")
    _ensure("origem_site_url", "")
    _ensure("origem_categoria_api", "")
    _ensure("padrao_disponivel_site", 10)

    # upload controle
    _ensure("origem_upload_fornecedor", None)
    _ensure("origem_upload_xml", None)

    # -----------------------------
    # FORNECEDOR (API)
    # -----------------------------
    _ensure("origem_fornecedor_api", "")
    _ensure("fornecedor_ia", "")

    # -----------------------------
    # DEPÓSITO (ESTOQUE)
    # -----------------------------
    _ensure("deposito_nome", "")

    # -----------------------------
    # PRECIFICAÇÃO
    # -----------------------------
    _ensure("usar_calculadora_precificacao", False)
    _ensure("precificacao_margem", 0.0)
    _ensure("precificacao_impostos", 0.0)
    _ensure("precificacao_custo_fixo", 0.0)
    _ensure("precificacao_taxa_extra", 0.0)

    # -----------------------------
    # MAPEAMENTO
    # -----------------------------
    _ensure("mapping_origem", {})
    _ensure("mapping_origem_rascunho", {})
    _ensure("mapping_origem_defaults", {})

    # -----------------------------
    # IA ORQUESTRADOR
    # -----------------------------
    _ensure("ia_comando_usuario", "")
    _ensure("ia_plano_execucao", {})
    _ensure("ia_plano_preview", {})
    _ensure("ia_erro_execucao", "")
    _ensure("origem_tipo_ia", "")
    _ensure("categoria_ia", "")

    # -----------------------------
    # FLAGS DE CONTROLE
    # -----------------------------
    _ensure("app_pronto", True)
