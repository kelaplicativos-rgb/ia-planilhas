from __future__ import annotations

"""Compatibilidade para chamadas antigas de origem_mapeamento.

O fluxo atual do projeto usa o módulo `bling_app_zero.ui.mapeamento`, mas
algumas telas/rotas antigas ainda podem tentar importar
`bling_app_zero.ui.origem_mapeamento`. Este arquivo evita quebra de importação
e centraliza uma blindagem simples para o preview da origem antes do mapeamento.
"""

from typing import Iterable, Optional

import pandas as pd
import streamlit as st


_ORIGEM_KEYS: tuple[str, ...] = (
    "df_origem",
    "df_origem_site",
    "df_origem_upload",
    "df_origem_xml",
    "df_capturado_site",
    "df_preview_origem",
    "df_saida",
    "df_final",
)


def _is_valid_dataframe(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty


def obter_dataframe_origem(keys: Iterable[str] = _ORIGEM_KEYS) -> Optional[pd.DataFrame]:
    """Retorna o primeiro DataFrame de origem válido salvo na sessão."""
    for key in keys:
        value = st.session_state.get(key)
        if _is_valid_dataframe(value):
            return value.copy()
    return None


def render_preview_origem_mapeamento(max_rows: int = 30) -> Optional[pd.DataFrame]:
    """Renderiza uma prévia segura da origem usada no mapeamento.

    Nunca lança erro para DataFrame ausente/vazio. Em vez disso, mostra um aviso
    amigável e deixa o usuário voltar para a origem dos dados.
    """
    df = obter_dataframe_origem()

    if df is None:
        st.warning(
            "Nenhum dado de origem foi encontrado para mapear. "
            "Volte para Origem dos dados e carregue/capture os produtos novamente."
        )
        return None

    st.caption(f"Prévia da origem para mapeamento: {len(df)} linhas × {len(df.columns)} colunas")
    st.dataframe(df.head(max_rows), use_container_width=True, hide_index=True)
    return df


def render_origem_mapeamento() -> None:
    """Entrada compatível com o nome antigo do fluxo."""
    try:
        from bling_app_zero.ui.mapeamento import render_mapeamento

        render_mapeamento()
    except Exception as exc:  # noqa: BLE001
        st.error("Erro ao abrir o mapeamento. A prévia da origem foi preservada abaixo.")
        st.exception(exc)
        render_preview_origem_mapeamento()


# Aliases usados em versões antigas do app.
render = render_origem_mapeamento
render_page = render_origem_mapeamento
