from __future__ import annotations

import streamlit as st

from .app_core_config import ETAPAS_ORDEM, ETAPAS_LABELS


def render_header():
    st.title("🚀 IA Planilhas → Bling")
    st.caption("Fluxo limpo: origem → precificação → mapeamento → preview final")


def render_nav(etapa_atual, etapa_maxima, on_click):
    st.markdown("### Etapas")
    cols = st.columns(len(ETAPAS_ORDEM))

    etapa_atual = etapa_atual if etapa_atual in ETAPAS_ORDEM else "origem"
    etapa_maxima = etapa_maxima if etapa_maxima in ETAPAS_ORDEM else "origem"

    for col, etapa in zip(cols, ETAPAS_ORDEM):
        liberada = ETAPAS_ORDEM.index(etapa) <= ETAPAS_ORDEM.index(etapa_maxima)
        atual = etapa == etapa_atual

        with col:
            clicou = st.button(
                ETAPAS_LABELS.get(etapa, etapa),
                use_container_width=True,
                disabled=not liberada,
                type="primary" if atual else "secondary",
                key=f"app_core_nav_{etapa}",
            )
            if clicou and liberada and not atual:
                on_click(etapa)
                st.rerun()
