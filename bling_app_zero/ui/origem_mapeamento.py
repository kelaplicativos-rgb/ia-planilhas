from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    safe_df_dados,
    safe_df_estrutura,
    voltar_etapa_anterior,
)
from bling_app_zero.ui.gtin_panel import render_gtin_panel
from bling_app_zero.ui.origem_mapeamento_actions import (
    _render_botoes_fluxo,
    _render_resumo_agente,
    _render_sugestao_agente,
)
from bling_app_zero.ui.origem_mapeamento_confidence import _render_revisao_manual
from bling_app_zero.ui.origem_mapeamento_helpers import (
    _executar_ia_autonoma,
    _garantir_etapa_mapeamento_ativa,
    _inicializar_mapping,
    _obter_df_base,
    _obter_df_modelo,
    _preview_mapping,
    _render_status_base,
    _sincronizar_deposito_nome,
    _detectar_operacao,
)


def render_origem_mapeamento() -> None:
    _garantir_etapa_mapeamento_ativa()

    st.subheader("3. Mapeamento com IA")

    df_base = _obter_df_base()
    df_modelo = _obter_df_modelo()
    operacao = _detectar_operacao()

    if not safe_df_dados(df_base):
        st.warning("Conclua a precificação antes de seguir para o mapeamento.")
        if st.button(
            "⬅️ Voltar para precificação",
            use_container_width=True,
            key="btn_voltar_precificacao_mapping",
        ):
            voltar_etapa_anterior()
        return

    if not safe_df_estrutura(df_modelo):
        st.warning("Carregue primeiro o modelo padrão antes de seguir para o mapeamento.")
        if st.button(
            "⬅️ Voltar para origem",
            use_container_width=True,
            key="btn_voltar_origem_sem_modelo_mapping",
        ):
            ir_para_etapa("origem")
        return

    _sincronizar_deposito_nome()
    _inicializar_mapping(df_base, df_modelo)
    _executar_ia_autonoma(df_base, df_modelo, operacao)

    _render_status_base(df_base, df_modelo)
    _render_sugestao_agente(df_base, df_modelo)
    _render_resumo_agente()

    with st.expander("Revisão manual opcional", expanded=False):
        _render_revisao_manual(df_base, df_modelo, operacao)

    df_preview = st.session_state.get("df_final")
    if safe_df_estrutura(df_preview):
        _preview_mapping(df_preview)

        st.markdown("### Tratamento de GTIN")
        st.caption("Faça aqui a limpeza ou geração de GTIN antes de seguir para o preview final.")
        render_gtin_panel(df_preview)

    _render_botoes_fluxo(df_base, df_modelo)

    st.markdown("---")
    if st.button(
        "⬅️ Voltar para precificação",
        use_container_width=True,
        key="btn_voltar_precificacao_no_rodape_mapping",
    ):
        voltar_etapa_anterior()
