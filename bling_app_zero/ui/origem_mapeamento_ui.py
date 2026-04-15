
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_mapeamento_core import (
    aplicar_mapeamento_automatico_preco,
    aplicar_mapeamento_automatico_quantidade,
    is_coluna_balanco,
)
from bling_app_zero.ui.origem_mapeamento_validacao import (
    is_coluna_deposito,
    is_coluna_id,
    opcoes_select_mapeamento,
    safe_str,
)


def render_cabecalho_mapeamento() -> None:
    st.subheader("Mapeamento de colunas")
    st.text_input(
        "Nome do Depósito (Bling)",
        value=str(st.session_state.get("deposito_nome", "") or ""),
        key="deposito_nome",
        placeholder="Ex: ifood, geral, principal",
    )


def _render_campo_bloqueado(rotulo: str, valor: str, chave: str) -> None:
    st.text_input(
        rotulo,
        value=valor,
        disabled=True,
        key=chave,
    )


def render_formulario_mapeamento(
    df_fonte: pd.DataFrame,
    df_modelo: pd.DataFrame,
    mapping: dict,
) -> dict:
    mapping_local = aplicar_mapeamento_automatico_preco(mapping, df_modelo, df_fonte)
    mapping_local = aplicar_mapeamento_automatico_quantidade(mapping_local, df_modelo, df_fonte)

    for col_modelo in df_modelo.columns:
        col_modelo = str(col_modelo)

        if is_coluna_id(col_modelo):
            _render_campo_bloqueado(
                col_modelo,
                "(Automático / Bloqueado)",
                f"id_lock_{col_modelo}",
            )
            mapping_local[col_modelo] = ""
            continue

        if is_coluna_deposito(col_modelo):
            _render_campo_bloqueado(
                col_modelo,
                safe_str(st.session_state.get("deposito_nome")) or "(Depósito padrão do sistema)",
                f"deposito_lock_{col_modelo}",
            )
            mapping_local[col_modelo] = ""
            continue

        if is_coluna_balanco(col_modelo):
            _render_campo_bloqueado(
                col_modelo,
                "S (Automático / Bloqueado)",
                f"balanco_lock_{col_modelo}",
            )
            mapping_local[col_modelo] = ""
            continue

        opcoes = opcoes_select_mapeamento(df_fonte, mapping_local, col_modelo)
        valor_atual = safe_str(mapping_local.get(col_modelo))

        valor = st.selectbox(
            col_modelo,
            opcoes,
            index=opcoes.index(valor_atual) if valor_atual in opcoes else 0,
            key=f"map_{col_modelo}",
        )
        mapping_local[col_modelo] = valor

    return mapping_local


def render_preview_mapeamento(
    df_saida: pd.DataFrame,
    duplicidades: dict[str, list[str]],
) -> None:
    if duplicidades:
        mensagens = []
        for coluna_origem, colunas_modelo in duplicidades.items():
            mensagens.append(
                f"'{coluna_origem}' usada em: {', '.join([str(c) for c in colunas_modelo])}"
            )
        st.error("❌ Existe coluna sendo usada mais de uma vez.\n\n" + "\n".join(mensagens))

    st.dataframe(df_saida.head(15), use_container_width=True)


def render_acoes_mapeamento(erro: bool) -> tuple[bool, bool]:
    col1, col2 = st.columns(2)
    avancar = False
    voltar = False

    with col1:
        avancar = st.button("➡️ Avançar", use_container_width=True, disabled=erro)

    with col2:
        voltar = st.button("⬅️ Voltar", use_container_width=True)

    return avancar, voltar
    
