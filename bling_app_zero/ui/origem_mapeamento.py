from __future__ import annotations

from collections.abc import Callable

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


NavCallback = Callable[[], None] | None


def _navegar(destino: str, callback: NavCallback = None) -> None:
    if callable(callback):
        callback()
        return

    set_etapa_mapeamento(destino)
    st.rerun()


def render_origem_mapeamento(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
) -> None:
    garantir_estado_mapeamento()

    if get_etapa_mapeamento() != "mapeamento":
        return

    df_fonte = obter_df_fonte_mapeamento()
    df_modelo = obter_df_modelo_mapeamento()

    if df_fonte is None or df_modelo is None:
        st.warning("Dados inválidos.")
        return

    col_topo_1, col_topo_2 = st.columns(2)

    with col_topo_1:
        if st.button("⬅️ Voltar para origem", use_container_width=True, key="mapeamento_btn_voltar_topo"):
            _navegar("origem", on_back)

    with col_topo_2:
        st.caption("Revise os campos e avance somente quando o preview estiver correto.")

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
        _navegar("final", on_continue)

    if voltar:
        _navegar("origem", on_back)
        
