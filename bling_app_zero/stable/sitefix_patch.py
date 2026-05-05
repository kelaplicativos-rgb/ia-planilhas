from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.stable import stable_app as base_app


OLD_SITE_INFO = "Captura por site está liberada neste núcleo para atualização de estoque."
NEW_SITE_INFO = "Captura por site liberada para cadastro e atualização de estoque. Cole links de produtos, categorias ou do fornecedor para criar a base inicial."


def run_stable_app() -> None:
    """Patch BLINGFIX para liberar captura por site também no cadastro.

    O fluxo base ainda desabilitava o botão quando tipo != estoque. Este patch
    mantém o núcleo estável atual, mas remove essa trava apenas do botão
    'Gerar base por site' e corrige a mensagem exibida na aba Site.
    """

    original_button = st.button
    original_info = st.info

    def patched_button(label: str, *args: Any, **kwargs: Any):
        if label == "Gerar base por site":
            # O próprio fluxo já valida se há base após clicar. Aqui removemos
            # apenas a trava indevida que bloqueava cadastro de produtos.
            kwargs["disabled"] = False
        return original_button(label, *args, **kwargs)

    def patched_info(body: Any, *args: Any, **kwargs: Any):
        if str(body) == OLD_SITE_INFO:
            body = NEW_SITE_INFO
        return original_info(body, *args, **kwargs)

    st.button = patched_button
    st.info = patched_info
    try:
        base_app.run_stable_app()
    finally:
        st.button = original_button
        st.info = original_info
