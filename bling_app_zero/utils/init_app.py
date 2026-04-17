
from __future__ import annotations

import streamlit as st


def init_app() -> None:
    """
    Inicialização global do estado do app.

    PRIORIDADE 1:
    - garantir etapa inicial correta
    - alinhar nomes de estado
    - evitar quebra de fluxo no primeiro render
    """

    # ============================================================
    # ETAPA PRINCIPAL (WIZARD)
    # ============================================================

    if "etapa" not in st.session_state:
        st.session_state["etapa"] = "origem"

    if "etapa_origem" not in st.session_state:
        st.session_state["etapa_origem"] = "origem"

    if "etapa_fluxo" not in st.session_state:
        st.session_state["etapa_fluxo"] = "origem"

    # histórico CORRETO (alinhado com app_helpers)
    if "etapa_historico" not in st.session_state:
        st.session_state["etapa_historico"] = []

    # ============================================================
    # CONTROLE DE URL / RERUN (CRÍTICO)
    # ============================================================

    if "_etapa_url_inicializada" not in st.session_state:
        st.session_state["_etapa_url_inicializada"] = False

    if "_ultima_etapa_sincronizada_url" not in st.session_state:
        st.session_state["_ultima_etapa_sincronizada_url"] = "origem"

    # ============================================================
    # DADOS PRINCIPAIS DO FLUXO
    # ============================================================

    defaults_df = [
        "df_origem",
        "df_normalizado",
        "df_precificado",
        "df_mapeado",
        "df_saida",
        "df_final",
        "df_calc_precificado",
        "df_preview_mapeamento",
        "df_modelo",
    ]

    for chave in defaults_df:
        if chave not in st.session_state:
            st.session_state[chave] = None

    # ============================================================
    # ORIGEM / UPLOAD
    # ============================================================

    if "origem_upload_nome" not in st.session_state:
        st.session_state["origem_upload_nome"] = ""

    if "origem_upload_bytes" not in st.session_state:
        st.session_state["origem_upload_bytes"] = None

    if "origem_upload_tipo" not in st.session_state:
        st.session_state["origem_upload_tipo"] = ""

    if "origem_upload_ext" not in st.session_state:
        st.session_state["origem_upload_ext"] = ""

    if "modelo_upload_nome" not in st.session_state:
        st.session_state["modelo_upload_nome"] = ""

    if "modelo_upload_bytes" not in st.session_state:
        st.session_state["modelo_upload_bytes"] = None

    if "modelo_upload_tipo" not in st.session_state:
        st.session_state["modelo_upload_tipo"] = ""

    if "modelo_upload_ext" not in st.session_state:
        st.session_state["modelo_upload_ext"] = ""

    # ============================================================
    # CONFIGURAÇÃO GERAL
    # ============================================================

    if "tipo_operacao" not in st.session_state:
        st.session_state["tipo_operacao"] = ""

    if "tipo_operacao_bling" not in st.session_state:
        st.session_state["tipo_operacao_bling"] = ""

    if "deposito_nome" not in st.session_state:
        st.session_state["deposito_nome"] = ""

    # ============================================================
    # PRECIFICAÇÃO
    # ============================================================

    defaults_precificacao = {
        "pricing_coluna_custo": "",
        "pricing_custo_fixo": 0.0,
        "pricing_frete_fixo": 0.0,
        "pricing_taxa_extra": 0.0,
        "pricing_impostos_percent": 0.0,
        "pricing_margem_percent": 0.0,
        "pricing_outros_percent": 0.0,
        "pricing_valor_teste": 0.0,
        "pricing_df_preview": None,
        "pricing_aplicada_ok": False,
    }

    for chave, valor in defaults_precificacao.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

    # ============================================================
    # MAPEAMENTO
    # ============================================================

    if "mapping_manual" not in st.session_state:
        st.session_state["mapping_manual"] = {}

    if "mapping_sugerido" not in st.session_state:
        st.session_state["mapping_sugerido"] = {}

    if "mapping_hash_base" not in st.session_state:
        st.session_state["mapping_hash_base"] = ""

    if "mapping_hash_modelo" not in st.session_state:
        st.session_state["mapping_hash_modelo"] = ""

    # ============================================================
    # BLING (CONEXÃO / ENVIO)
    # ============================================================

    if "bling_conectado" not in st.session_state:
        st.session_state["bling_conectado"] = False

    if "bling_status_texto" not in st.session_state:
        st.session_state["bling_status_texto"] = "Desconectado"

    if "bling_envio_resultado" not in st.session_state:
        st.session_state["bling_envio_resultado"] = None

    # ============================================================
    # FLAGS DE CONTROLE DE FLUXO
    # ============================================================

    if "_fluxo_inicializado" not in st.session_state:
        st.session_state["_fluxo_inicializado"] = True

