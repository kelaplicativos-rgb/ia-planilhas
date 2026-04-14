from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_mapeamento_core import (
    montar_df_saida_mapeado,
    obter_df_fonte_mapeamento,
    obter_df_modelo_mapeamento,
)
from bling_app_zero.ui.origem_mapeamento_estado import (
    garantir_estado_mapeamento,
    get_etapa_mapeamento,
    set_etapa_mapeamento,
)
from bling_app_zero.ui.origem_mapeamento_validacao import detectar_duplicidades_mapping
from bling_app_zero.ui.origem_mapeamento_ui import (
    render_acoes_mapeamento,
    render_cabecalho_mapeamento,
    render_formulario_mapeamento,
    render_preview_mapeamento,
)


def render_origem_mapeamento() -> None:
    garantir_estado_mapeamento()

    if get_etapa_mapeamento() != "mapeamento":
        return

    df_fonte = obter_df_fonte_mapeamento()
    df_modelo = obter_df_modelo_mapeamento()

    if df_fonte is None or df_modelo is None:
        st.warning("Dados inválidos.")
        return

    render_cabecalho_mapeamento()

    mapping = dict(st.session_state.get("mapping_origem", {}))
    mapping_atualizado = render_formulario_mapeamento(df_fonte, df_modelo, mapping)

    duplicidades = detectar_duplicidades_mapping(mapping_atualizado)
    erro = bool(duplicidades)

    if not erro:
        st.session_state["mapping_origem"] = mapping_atualizado

    df_saida = montar_df_saida_mapeado(df_fonte, df_modelo, mapping_atualizado)

    st.session_state["df_saida"] = df_saida.copy()
    st.session_state["df_final"] = df_saida.copy()

    render_preview_mapeamento(df_saida, duplicidades)

    avancar, voltar = render_acoes_mapeamento(erro=erro)

    if avancar and not erro:
        set_etapa_mapeamento("final")
        st.rerun()

    if voltar:
        set_etapa_mapeamento("origem")
        st.rerun()
