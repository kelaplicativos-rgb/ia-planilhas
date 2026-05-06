from __future__ import annotations

"""Exports seguros da etapa de mapeamento.

O Preview da origem foi removido do fluxo. Este pacote agora apenas encaminha
para a tela real de mapeamento e nunca tenta importar/renderizar
`bling_app_zero.ui.origem_preview`.
"""

from importlib import import_module
from typing import Callable, Optional

import streamlit as st


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


def render_mapeamento() -> None:
    render_fn = _resolver_page_render()

    if render_fn is None:
        st.error("A tela modular de mapeamento não foi localizada automaticamente.")
        return

    try:
        render_fn()
    except Exception as exc:  # noqa: BLE001
        st.error("Erro ao abrir o mapeamento.")
        st.exception(exc)


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
