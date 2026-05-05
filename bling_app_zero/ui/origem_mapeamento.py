from __future__ import annotations

"""Compatibilidade para chamadas antigas de origem_mapeamento.

O fluxo atual pode usar módulos diferentes para a etapa de mapeamento:
- `bling_app_zero.ui.mapeamento.py` em versões mais antigas;
- pacote `bling_app_zero.ui.mapeamento` + `page.py` em versões modularizadas.

Este arquivo existe para impedir quebra quando algum trecho antigo ainda chamar
`bling_app_zero.ui.origem_mapeamento` e para manter um preview seguro da origem.
"""

from importlib import import_module
from typing import Callable, Iterable, Optional

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

_RENDER_MODULES: tuple[str, ...] = (
    "bling_app_zero.ui.mapeamento.page",
    "bling_app_zero.ui.mapeamento",
)

_RENDER_NAMES: tuple[str, ...] = (
    "render_mapeamento_page",
    "render_mapeamento",
    "render_page",
    "render",
    "main",
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
    """Renderiza uma prévia segura da origem usada no mapeamento."""
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


def _resolver_render_mapeamento() -> Optional[Callable[[], None]]:
    """Localiza dinamicamente a função real da tela de mapeamento."""
    for module_name in _RENDER_MODULES:
        try:
            module = import_module(module_name)
        except Exception:
            continue

        for attr_name in _RENDER_NAMES:
            attr = getattr(module, attr_name, None)
            if callable(attr) and attr is not render_origem_mapeamento:
                return attr

    return None


def render_origem_mapeamento() -> None:
    """Entrada compatível com o nome antigo do fluxo."""
    render_fn = _resolver_render_mapeamento()

    if render_fn is None:
        st.warning(
            "A tela de mapeamento não foi localizada automaticamente. "
            "A prévia da origem foi preservada para conferência."
        )
        render_preview_origem_mapeamento()
        return

    try:
        render_fn()
    except Exception as exc:  # noqa: BLE001
        st.error("Erro ao abrir o mapeamento. A prévia da origem foi preservada abaixo.")
        st.exception(exc)
        render_preview_origem_mapeamento()


# Aliases usados em versões antigas do app.
render = render_origem_mapeamento
render_page = render_origem_mapeamento
main = render_origem_mapeamento
