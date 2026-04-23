from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    normalizar_texto,
    safe_df_estrutura,
    voltar_etapa_anterior,
)
from bling_app_zero.ui.preview_final_bling import render_painel_bling
from bling_app_zero.ui.preview_final_data import garantir_df_final_canonico, zerar_colunas_video
from bling_app_zero.ui.preview_final_sections import (
    render_bloco_fluxo_site,
    render_colunas_detectadas_sync,
    render_download,
    render_origem_site_metadata,
    render_preview_dataframe,
    render_resumo_validacao,
)
from bling_app_zero.ui.preview_final_state import (
    garantir_etapa_preview_ativa,
    inicializar_estado_preview,
    obter_df_final_exclusivo,
    sincronizar_deposito_nome,
    sincronizar_estado_quando_df_mudar,
)


def _render_preview_sem_df() -> None:
    st.warning("O resultado final ainda não foi gerado.")
    if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview_sem_df"):
        st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
        voltar_etapa_anterior()


def _normalizar_df_preview(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    df_final = garantir_df_final_canonico(
        df=df_final,
        tipo_operacao=tipo_operacao,
        deposito_nome=deposito_nome,
    )
    df_final = zerar_colunas_video(df_final)
    st.session_state["df_final"] = df_final
    return df_final


def _obter_df_preview_atualizado(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    df_final_atualizado = st.session_state.get("df_final", df_final)
    if isinstance(df_final_atualizado, pd.DataFrame) and safe_df_estrutura(df_final_atualizado):
        df_final = df_final_atualizado.copy().fillna("")
        df_final = _normalizar_df_preview(df_final, tipo_operacao, deposito_nome)
    return df_final


def _render_navegacao_preview() -> None:
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
            voltar_etapa_anterior()

    with col2:
        if st.button("↺ Reabrir origem", use_container_width=True, key="btn_ir_origem_preview"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "origem"
            ir_para_etapa("origem")


def render_preview_final() -> None:
    garantir_etapa_preview_ativa()
    inicializar_estado_preview()

    st.subheader("4. Preview Final")

    tipo_operacao = normalizar_texto(st.session_state.get("tipo_operacao") or "cadastro") or "cadastro"
    deposito_nome = sincronizar_deposito_nome()
    df_final = obter_df_final_exclusivo()

    if not safe_df_estrutura(df_final):
        _render_preview_sem_df()
        return

    df_final = _normalizar_df_preview(df_final, tipo_operacao, deposito_nome)
    sincronizar_estado_quando_df_mudar(df_final)

    validacao_ok, _ = render_resumo_validacao(df_final, tipo_operacao)
    df_final = _obter_df_preview_atualizado(df_final, tipo_operacao, deposito_nome)

    render_preview_dataframe(df_final)
    render_download(df_final, validacao_ok)
    render_painel_bling(df_final, tipo_operacao, deposito_nome, validacao_ok)
    render_colunas_detectadas_sync(df_final)
    render_origem_site_metadata()
    render_bloco_fluxo_site()

    _render_navegacao_preview()
