from __future__ import annotations

import streamlit as st

from .app_core_config import ETAPAS_ORDEM, ETAPAS_LABELS


def render_header():
    st.title("🚀 IA Planilhas → Bling")
    st.caption("Fluxo limpo: origem → precificação → mapeamento → preview final")


def render_nav(etapa_atual, etapa_maxima, on_click):
    st.markdown("### Etapas")
    cols = st.columns(len(ETAPAS_ORDEM))

    for col, etapa in zip(cols, ETAPAS_ORDEM):
        liberada = ETAPAS_ORDEM.index(etapa) <= ETAPAS_ORDEM.index(etapa_maxima)
        atual = etapa == etapa_atual

        with col:
            if st.button(
                ETAPAS_LABELS.get(etapa, etapa),
                use_container_width=True,
                disabled=not liberada,
                type="primary" if atual else "secondary",
            ):
                if liberada:
                    on_click(etapa)
