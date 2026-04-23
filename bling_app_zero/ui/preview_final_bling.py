from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.preview_final_bling_connection import render_conexao_bling
from bling_app_zero.ui.preview_final_bling_result import render_resultado_envio_visual
from bling_app_zero.ui.preview_final_bling_send import enviar_para_bling
from bling_app_zero.ui.preview_final_state import (
    obter_status_conexao_bling,
    oauth_liberado,
    origem_site_ativa,
    varredura_site_concluida,
)


def _render_status_conexao(liberado: bool) -> tuple[bool, str]:
    conectado, status = obter_status_conexao_bling()

    st.session_state["bling_conectado"] = conectado
    st.session_state["bling_status_texto"] = status

    c1, c2 = st.columns([1, 1])
    with c1:
        st.info(f"Status da conexão: **{status}**")
    with c2:
        if not conectado:
            render_conexao_bling(liberado)
        else:
            st.success("Conta Bling pronta para envio real.")

    return conectado, status


def _render_pre_requisitos(validacao_ok: bool) -> bool:
    if not st.session_state.get("preview_download_realizado", False):
        st.warning("Confirme primeiro o download da planilha final para liberar a conexão e o envio.")
        return False

    if not validacao_ok:
        st.warning("A validação final precisa estar OK para liberar o envio ao Bling.")
        return False

    if origem_site_ativa() and not varredura_site_concluida():
        st.warning("Finalize a varredura do site do fornecedor antes de conectar e enviar ao Bling.")
        return False

    return True


def _render_configuracoes_envio() -> None:
    st.markdown("#### Estratégia de sincronização")
    st.radio(
        "Como deseja enviar os produtos?",
        options=["inteligente", "cadastrar_novos", "atualizar_existentes"],
        format_func=lambda x: {
            "inteligente": "Cadastrar novos e atualizar existentes",
            "cadastrar_novos": "Cadastrar apenas novos",
            "atualizar_existentes": "Atualizar apenas existentes",
        }.get(x, x),
        key="bling_sync_strategy",
    )

    st.markdown("#### Atualização automática")
    modo_auto = st.radio(
        "Modo de atualização",
        options=["manual", "instantaneo", "periodico"],
        format_func=lambda x: {
            "manual": "Manual",
            "instantaneo": "Instantânea",
            "periodico": "Periódica",
        }.get(x, x),
        horizontal=True,
        key="bling_sync_auto_mode",
    )

    if modo_auto == "periodico":
        cc1, cc2 = st.columns(2)
        with cc1:
            st.number_input("Intervalo", min_value=1, step=1, key="bling_sync_interval_value")
        with cc2:
            st.selectbox("Unidade", options=["minutos", "horas", "dias"], key="bling_sync_interval_unit")

    if origem_site_ativa():
        st.caption(
            "Quando a origem vier do site do fornecedor, o envio respeita a sequência: "
            "captura/validação → download → conexão Bling → envio por API."
        )


def _render_botao_envio(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str, conectado: bool, liberado: bool) -> None:
    liberar_envio = bool(conectado and liberado)

    if st.button(
        "🚀 Enviar produtos ao Bling",
        use_container_width=True,
        key="btn_enviar_produtos_bling",
        disabled=not liberar_envio or bool(st.session_state.get("preview_envio_em_execucao", False)),
    ):
        enviar_para_bling(
            df_final=df_final.copy(),
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
        )

    if not conectado:
        st.caption("Depois da validação e da confirmação do download, conecte sua conta do Bling para liberar o envio real.")
    elif not liberar_envio:
        st.caption("Ainda existem pré-requisitos pendentes antes do envio.")


def render_painel_bling(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str, validacao_ok: bool) -> None:
    st.markdown("### Conectar e enviar ao Bling")

    liberado = oauth_liberado(validacao_ok)
    conectado, _ = _render_status_conexao(liberado)

    if not _render_pre_requisitos(validacao_ok):
        return

    _render_configuracoes_envio()
    _render_botao_envio(df_final, tipo_operacao, deposito_nome, conectado, liberado)

    resultado = st.session_state.get("bling_envio_resultado")
    if resultado:
        render_resultado_envio_visual(resultado)
