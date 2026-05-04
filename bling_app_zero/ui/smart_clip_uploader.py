from __future__ import annotations

from typing import Any

import streamlit as st


SUPPORTED_LABEL = "Excel, CSV, TXT, TSV, ODS, HTML ou JSON"


def render_smart_clip_uploader(
    *,
    label: str,
    key: str,
    help_text: str | None = None,
) -> Any | None:
    """Renderiza um anexo no estilo clipe: simples, amplo e sem limitar extensão.

    O reconhecimento real do arquivo fica no leitor central. Aqui a experiência é
    parecida com um clipe de mensagem: o usuário escolhe o arquivo e o sistema
    tenta entender o formato.
    """

    st.markdown(f"#### 📎 {label}")
    st.caption(f"Anexe qualquer arquivo tabular comum: {SUPPORTED_LABEL}.")

    uploaded = st.file_uploader(
        "📎 Tocar para anexar arquivo",
        type=None,
        key=key,
        help=help_text or "Escolha o arquivo. O sistema tentará reconhecer automaticamente o formato.",
        label_visibility="visible",
    )

    if uploaded is not None:
        name = str(getattr(uploaded, "name", "arquivo"))
        size = int(getattr(uploaded, "size", 0) or 0)
        size_mb = size / (1024 * 1024) if size else 0
        st.success(f"Arquivo anexado: {name}")
        if size:
            st.caption(f"Tamanho: {size_mb:.2f} MB")

    return uploaded
