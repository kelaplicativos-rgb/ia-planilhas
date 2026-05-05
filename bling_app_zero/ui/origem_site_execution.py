from __future__ import annotations

"""Executor compatível da captura por site.

BLINGFIX:
- O fluxo de cadastro de produtos via site deve usar o modo Flash Amplo página
  por página.
- Listagens/categorias apenas descobrem links.
- Cada produto é aberto em sua própria página `/produto/...`.
- Dados opcionais só vêm se forem captados de verdade.
- Estoque não é obrigatório.

Este arquivo funciona como ponte para telas antigas que ainda importam
`origem_site_execution.py` com nomes diferentes de função.
"""

from typing import Any, Callable, Iterable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.flash_amplo_execution import (
    executar_flash_amplo,
    executar_flash_amplo_pagina_por_pagina,
    run_flash_amplo_ui,
    salvar_resultado_flash_amplo,
)


def _extract_urls_from_args(*args: Any, **kwargs: Any) -> Iterable[str] | str:
    """Extrai URLs de chamadas antigas com nomes variados."""
    for key in (
        "urls",
        "seed_urls",
        "site_urls",
        "product_urls",
        "links",
        "url",
        "site_url",
        "categoria_url",
        "category_url",
    ):
        value = kwargs.get(key)
        if value:
            return value

    for arg in args:
        if isinstance(arg, (str, list, tuple, set)):
            return arg

    value = st.session_state.get("urls_site") or st.session_state.get("site_urls") or st.session_state.get("url_site")
    return value or []


def executar_captura_site(*args: Any, **kwargs: Any) -> pd.DataFrame:
    urls = _extract_urls_from_args(*args, **kwargs)
    max_products = int(kwargs.get("max_products") or kwargs.get("limite") or kwargs.get("limit") or 500)
    max_workers = int(kwargs.get("max_workers") or kwargs.get("workers") or 12)
    show_progress = bool(kwargs.get("show_progress", True))

    return executar_flash_amplo_pagina_por_pagina(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        show_progress=show_progress,
    )


# Aliases explícitos para nomes prováveis usados por telas antigas.
execute_site_capture = executar_captura_site
executar_site_capture = executar_captura_site
run_site_capture = executar_captura_site
capturar_site = executar_captura_site
capturar_produtos_site = executar_captura_site
executar_captura_por_site = executar_captura_site
executar_origem_site = executar_captura_site
run_origem_site = executar_captura_site
run = executar_captura_site
main = executar_captura_site


def __getattr__(name: str) -> Callable[..., pd.DataFrame]:
    """Fallback para imports antigos: qualquer executor de site cai no modo novo."""
    lowered = name.lower()
    if any(token in lowered for token in ("captura", "capture", "crawler", "site", "flash", "produto", "product", "run", "execut")):
        return executar_captura_site
    raise AttributeError(name)


__all__ = [
    "executar_captura_site",
    "execute_site_capture",
    "executar_site_capture",
    "run_site_capture",
    "capturar_site",
    "capturar_produtos_site",
    "executar_captura_por_site",
    "executar_origem_site",
    "run_origem_site",
    "executar_flash_amplo",
    "executar_flash_amplo_pagina_por_pagina",
    "run_flash_amplo_ui",
    "salvar_resultado_flash_amplo",
    "run",
    "main",
]
