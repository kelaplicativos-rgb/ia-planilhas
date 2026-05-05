from __future__ import annotations

"""Exports seguros da etapa de mapeamento.

Este pacote convive com versões antigas do projeto que usavam
`bling_app_zero/ui/mapeamento.py` e versões novas que usam
`bling_app_zero/ui/mapeamento/page.py`.

O objetivo aqui é garantir que imports como estes não quebrem:

    from bling_app_zero.ui.mapeamento import render_mapeamento
    from bling_app_zero.ui.mapeamento import render_page
    from bling_app_zero.ui.mapeamento import render

Mesmo que o nome real dentro de `page.py` mude, tentamos localizar uma função
de renderização conhecida e, se não existir, mostramos um aviso seguro em vez de
quebrar o app.
"""

from importlib import import_module
from typing import Callable, Optional

import streamlit as st

from bling_app_zero.ui.origem_preview import render_origem_preview


_RENDER_NAMES: tuple[str, ...] = (
    "render_mapeamento_page",
    "render_mapeamento",
    "render_page",
    "render",
    "main",
)


def _resolver_page_render() -> Optional[Callable[[], None]]:
    try:
        page = import_module("bling_app_zero.ui.mapeamento.page")
    except Exception:
        return None

    for name in _RENDER_NAMES:
        attr = getattr(page, name, None)
        if callable(attr):
            return attr

    return None


def _preview_origem_fallback(max_rows: int = 30) -> None:
    render_origem_preview(title="Preview da origem", max_rows=max_rows)


def render_mapeamento() -> None:
    render_fn = _resolver_page_render()

    if render_fn is None:
        st.warning(
            "A tela modular de mapeamento não foi localizada automaticamente. "
            "A prévia da origem foi preservada para conferência."
        )
        _preview_origem_fallback()
        return

    try:
        render_fn()
    except Exception as exc:  # noqa: BLE001
        st.error("Erro ao abrir o mapeamento. A prévia da origem foi preservada abaixo.")
        st.exception(exc)
        _preview_origem_fallback()


render = render_mapeamento
render_page = render_mapeamento
render_mapeamento_page = render_mapeamento
main = render_mapeamento

__all__ = [
    "render",
    "render_page",
    "render_mapeamento",
    "render_mapeamento_page",
    "main",
]
