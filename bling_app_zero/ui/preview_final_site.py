from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.preview_final_state import (
    fonte_descoberta_label,
    origem_site_ativa,
    url_site_atual,
    varredura_site_concluida,
)


def render_origem_site_metadata() -> None:
    with st.expander("Origem da descoberta", expanded=False):
        if not origem_site_ativa():
            st.caption("A origem atual não veio da busca por site do fornecedor.")
            return

        url_site = url_site_atual()
        fonte = fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))
        total_descobertos = int(st.session_state.get("site_busca_diagnostico_total_descobertos", 0) or 0)
        total_validos = int(st.session_state.get("site_busca_diagnostico_total_validos", 0) or 0)
        total_rejeitados = int(st.session_state.get("site_busca_diagnostico_total_rejeitados", 0) or 0)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Fonte descoberta", fonte)
        with c2:
            st.metric("Descobertos", total_descobertos)
        with c3:
            st.metric("Válidos", total_validos)
        with c4:
            st.metric("Rejeitados", total_rejeitados)

        if url_site:
            st.write(f"**URL monitorada:** {url_site}")


def render_bloco_fluxo_site() -> None:
    with st.expander("Varredura do site e conversão GPT", expanded=False):
        if not origem_site_ativa():
            st.caption("A origem atual não veio da busca por site.")
            return

        url_site = url_site_atual()
        modo_auto = st.session_state.get("bling_sync_auto_mode", "manual")
        interval_value = st.session_state.get("bling_sync_interval_value", 15)
        interval_unit = st.session_state.get("bling_sync_interval_unit", "minutos")
        loop_ativo = bool(st.session_state.get("site_auto_loop_ativo", False))
        loop_status = str(st.session_state.get("site_auto_status", "inativo") or "inativo")
        ultima_execucao = str(st.session_state.get("site_auto_ultima_execucao", "") or "")
        fonte_descoberta = fonte_descoberta_label(st.session_state.get("site_busca_fonte_descoberta", ""))

        if varredura_site_concluida():
            st.success("Varredura do site concluída. Produtos localizados e prontos para seguir para o Bling.")
        else:
            st.warning(
                "A conexão OAuth e o envio só serão liberados depois da varredura do site terminar com dados válidos."
            )

        if url_site:
            st.write(f"**URL monitorada:** {url_site}")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Loop", "Ativo" if loop_ativo else "Inativo")
        with c2:
            st.metric("Status", loop_status.title())
        with c3:
            st.metric("Última busca", ultima_execucao if ultima_execucao else "-")
        with c4:
            st.metric("Fonte descoberta", fonte_descoberta)

        if modo_auto == "periodico":
            st.info(f"Modo periódico configurado: **{interval_value} {interval_unit}**.")
