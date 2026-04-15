
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import safe_df_dados
from bling_app_zero.ui.origem_dados_handlers import safe_str
from bling_app_zero.ui.origem_mapeamento_core import (
    colunas_bloqueadas,
    construir_df_mapeado,
    inicializar_mapeamento,
)


def render_header_mapeamento(df_origem: pd.DataFrame, df_modelo: pd.DataFrame) -> None:
    st.markdown("### Etapa de mapeamento")
    st.caption(
        f"Base de origem: {len(df_origem)} linha(s) | "
        f"Modelo de destino: {len(df_modelo.columns)} coluna(s)"
    )


def render_resumo_colunas(df_origem: pd.DataFrame) -> None:
    with st.expander("Colunas disponíveis da origem", expanded=False):
        st.write(", ".join([safe_str(c) for c in df_origem.columns]))


def render_tabela_mapeamento(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping_atual: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    colunas_origem = [""] + [safe_str(c) for c in df_origem.columns]
    bloqueadas = colunas_bloqueadas()
    usados: set[str] = set()
    mapping_novo: dict[str, str] = {}
    defaults_novos: dict[str, str] = {}

    for destino in df_modelo.columns:
        st.markdown(f"**{destino}**")

        c1, c2 = st.columns([2, 1])

        with c1:
            valor_inicial = safe_str(mapping_atual.get(destino))
            if valor_inicial not in colunas_origem:
                valor_inicial = ""

            opcoes = colunas_origem.copy()

            if destino not in bloqueadas:
                opcoes_filtradas = [""]
                for opcao in colunas_origem[1:]:
                    if opcao == valor_inicial or opcao not in usados:
                        opcoes_filtradas.append(opcao)
                opcoes = opcoes_filtradas

            escolha = st.selectbox(
                f"Origem para {destino}",
                options=opcoes,
                index=opcoes.index(valor_inicial) if valor_inicial in opcoes else 0,
                key=f"map_src_{destino}",
                disabled=destino in bloqueadas,
                label_visibility="collapsed",
            )

        with c2:
            default_value = st.text_input(
                f"Default {destino}",
                value=safe_str(st.session_state.get(f"map_default_{destino}", "")),
                key=f"map_default_{destino}",
                label_visibility="collapsed",
                disabled=destino in bloqueadas,
                placeholder="Valor fixo",
            )

        if destino in bloqueadas:
            escolha = ""
            if destino == "Deposito (OBRIGATÓRIO)":
                default_value = safe_str(st.session_state.get("deposito_nome"))

        if escolha:
            usados.add(escolha)

        mapping_novo[destino] = escolha
        defaults_novos[destino] = default_value

    return mapping_novo, defaults_novos


def render_preview_mapeamento(df_preview: pd.DataFrame) -> None:
    if not safe_df_dados(df_preview):
        return

    with st.expander("Preview do mapeamento", expanded=False):
        st.dataframe(df_preview.head(5), use_container_width=True, hide_index=True)


def render_bloco_mapeamento(
    df_origem: pd.DataFrame,
    df_modelo: pd.DataFrame,
) -> tuple[dict[str, str], dict[str, str], pd.DataFrame]:
    mapping_atual = inicializar_mapeamento(df_origem, df_modelo)
    render_header_mapeamento(df_origem, df_modelo)
    render_resumo_colunas(df_origem)

    mapping_novo, defaults_novos = render_tabela_mapeamento(df_origem, df_modelo, mapping_atual)
    df_preview = construir_df_mapeado(df_origem, df_modelo, mapping_novo, defaults_novos)
    render_preview_mapeamento(df_preview)

    st.session_state["mapping_origem_rascunho"] = mapping_novo.copy()
    return mapping_novo, defaults_novos, df_preview
