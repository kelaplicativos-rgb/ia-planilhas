from __future__ import annotations

"""Compatibilidade para chamadas antigas de origem_mapeamento.

Este arquivo agora é apenas uma ponte limpa para a tela real de mapeamento.
O Preview da origem foi removido do fluxo por decisão de produto: a conferência
acontece diretamente no mapeamento, com amostra vermelha da primeira linha abaixo
de cada campo.
"""

from importlib import import_module
from typing import Callable, Optional

import streamlit as st


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
        st.error("A tela de mapeamento não foi localizada. Verifique os módulos de mapeamento.")
        return

    try:
        render_fn()
    except Exception as exc:  # noqa: BLE001
        st.error("Erro ao abrir o mapeamento.")
        st.exception(exc)


render = render_origem_mapeamento
render_page = render_origem_mapeamento
main = render_origem_mapeamento
