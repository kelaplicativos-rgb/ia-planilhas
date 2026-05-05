from __future__ import annotations

"""Compatibilidade para chamadas antigas de origem_mapeamento.

O fluxo atual pode usar módulos diferentes para a etapa de mapeamento:
- `bling_app_zero.ui.mapeamento.py` em versões mais antigas;
- pacote `bling_app_zero.ui.mapeamento` + `page.py` em versões modularizadas.

Este arquivo existe para impedir quebra quando algum trecho antigo ainda chamar
`bling_app_zero.ui.origem_mapeamento` e para manter um preview seguro da origem.
"""

from importlib import import_module
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_preview import (
    ORIGEM_PREVIEW_KEYS,
    get_origem_preview_dataframe,
    render_origem_preview,
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


def obter_dataframe_origem(keys: tuple[str, ...] = ORIGEM_PREVIEW_KEYS) -> Optional[pd.DataFrame]:
    """Retorna o primeiro DataFrame de origem válido salvo na sessão."""
    result = get_origem_preview_dataframe(keys)
    if result is None:
        return None
    return result.dataframe.copy()


def render_preview_origem_mapeamento(max_rows: int = 30) -> Optional[pd.DataFrame]:
    """Renderiza uma prévia segura da origem usada no mapeamento."""
    return render_origem_preview(title="Preview da origem", max_rows=max_rows)


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
