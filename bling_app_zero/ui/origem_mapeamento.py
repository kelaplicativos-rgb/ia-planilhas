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
from bling_app_zero.ui.origem_mapeamento_validacao import (
    detectar_duplicidades_mapping,
)
from bling_app_zero.ui.origem_mapeamento_ui import (
    render_cabecalho_mapeamento,
    render_formulario_mapeamento,
    render_preview_mapeamento,
)

NavCallback = Callable[[], None] | None


def _safe_dict(valor) -> dict:
    try:
        return dict(valor or {})
    except Exception:
        return {}


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _tem_estrutura_df(df) -> bool:
    try:
        return df is not None and hasattr(df, "columns") and len(df.columns) > 0
    except Exception:
        return False


def _persistir_df_saida(df_saida) -> None:
    if not _tem_estrutura_df(df_saida):
        return

    st.session_state["df_saida"] = _safe_copy_df(df_saida)
    st.session_state["df_final"] = _safe_copy_df(df_saida)
    st.session_state["df_preview_mapeamento"] = _safe_copy_df(df_saida)


def _persistir_mapping(mapping: dict) -> None:
    st.session_state["mapping_origem"] = _safe_dict(mapping)
    st.session_state["mapping_origem_rascunho"] = _safe_dict(mapping)


def _restaurar_mapping_inicial() -> dict:
    mapping_salvo = _safe_dict(st.session_state.get("mapping_origem"))
    if mapping_salvo:
        return mapping_salvo

    mapping_rascunho = _safe_dict(st.session_state.get("mapping_origem_rascunho"))
    if mapping_rascunho:
        return mapping_rascunho

    return {}


def _navegar(destino: str, callback: NavCallback = None) -> None:
    if callable(callback):
        callback()
        return

    set_etapa_mapeamento(destino)
    st.rerun()


def _voltar_preservando_estado(on_back: NavCallback = None) -> None:
    mapping_atual = _safe_dict(st.session_state.get("mapping_origem_rascunho"))
    if mapping_atual:
        st.session_state["mapping_origem"] = mapping_atual

    df_preview = st.session_state.get("df_preview_mapeamento")
    if _tem_estrutura_df(df_preview):
        st.session_state["df_saida"] = _safe_copy_df(df_preview)
        st.session_state["df_final"] = _safe_copy_df(df_preview)

    st.session_state["mapeamento_retorno_preservado"] = True
    _navegar("origem", on_back)


def _continuar_para_final(
    on_continue: NavCallback = None,
    *,
    erro: bool,
    df_saida=None,
) -> None:
    if erro:
        st.warning("Corrija os campos duplicados antes de continuar.")
        return

    if not _tem_estrutura_df(df_saida):
        st.warning("Nenhum preview válido foi gerado para continuar.")
        return

    _persistir_df_saida(df_saida)
    st.session_state["mapeamento_retorno_preservado"] = True
    _navegar("final", on_continue)


def _render_botoes_mapeamento(
    *,
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
    erro: bool = False,
    topo: bool = False,
    df_saida=None,
) -> None:
    suffix = "topo" if topo else "rodape"
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅️ Voltar para origem",
            use_container_width=True,
            key=f"mapeamento_btn_voltar_{suffix}",
        ):
            _voltar_preservando_estado(on_back)

    with col2:
        if st.button(
            "➡️ Continuar para preview final",
            use_container_width=True,
            type="primary",
            disabled=erro,
            key=f"mapeamento_btn_continuar_{suffix}",
        ):
            _continuar_para_final(
                on_continue,
                erro=erro,
                df_saida=df_saida,
            )


def render_origem_mapeamento(
    on_back: NavCallback = None,
    on_continue: NavCallback = None,
) -> None:
    garantir_estado_mapeamento()

    if get_etapa_mapeamento() != "mapeamento":
        return

    df_fonte = obter_df_fonte_mapeamento()
    df_modelo = obter_df_modelo_mapeamento()

    if not _tem_estrutura_df(df_fonte) or not _tem_estrutura_df(df_modelo):
        st.warning("Dados inválidos para o mapeamento.")
        _render_botoes_mapeamento(
            on_back=on_back,
            on_continue=on_continue,
            erro=True,
            topo=False,
            df_saida=None,
        )
        return

    col_topo_1, col_topo_2 = st.columns(2)

    with col_topo_1:
        if st.button(
            "⬅️ Voltar para origem",
            use_container_width=True,
            key="mapeamento_btn_voltar_header",
        ):
            _voltar_preservando_estado(on_back)

    with col_topo_2:
        st.caption("Revise os campos e avance somente quando o preview estiver correto.")

    render_cabecalho_mapeamento()

    mapping_inicial = _restaurar_mapping_inicial()
    mapping_atualizado = render_formulario_mapeamento(
        df_fonte,
        df_modelo,
        mapping_inicial,
    )

    mapping_atualizado = _safe_dict(mapping_atualizado)
    st.session_state["mapping_origem_rascunho"] = _safe_dict(mapping_atualizado)

    duplicidades = detectar_duplicidades_mapping(mapping_atualizado)
    erro = bool(duplicidades)

    if erro:
        st.warning("Existem campos de origem repetidos no mapeamento. Ajuste antes de avançar.")
    else:
        _persistir_mapping(mapping_atualizado)

    df_saida = montar_df_saida_mapeado(df_fonte, df_modelo, mapping_atualizado)

    if _tem_estrutura_df(df_saida):
        _persistir_df_saida(df_saida)

    render_preview_mapeamento(df_saida, duplicidades)

    _render_botoes_mapeamento(
        on_back=on_back,
        on_continue=on_continue,
        erro=erro,
        topo=True,
        df_saida=df_saida,
    )

    st.markdown("---")

    _render_botoes_mapeamento(
        on_back=on_back,
        on_continue=on_continue,
        erro=erro,
        topo=False,
        df_saida=df_saida,
    )
    
