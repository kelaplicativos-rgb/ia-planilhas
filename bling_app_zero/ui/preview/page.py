from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import ir_para_etapa, normalizar_texto, safe_df_estrutura, voltar_etapa_anterior
from bling_app_zero.ui.preview.align import alinhar_ao_modelo_bling, colunas_iguais_ao_modelo
from bling_app_zero.ui.preview.merge import mesclar_preservando_manual
from bling_app_zero.ui.preview.update import normalizar_preview, obter_preview_atualizado
from bling_app_zero.ui.preview_final_ai_descricao import render_ai_descricao
from bling_app_zero.ui.preview_final_bling import render_painel_bling
from bling_app_zero.ui.preview_final_estoque_inteligente import render_estoque_inteligente_final
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


def _sem_df() -> None:
    st.warning("O resultado final ainda não foi gerado a partir do modelo Bling anexado.")
    if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview_sem_df"):
        st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
        voltar_etapa_anterior()


def _sem_modelo() -> None:
    st.error("Preview bloqueado: envie primeiro o modelo oficial do Bling.")
    if st.button("⬅️ Voltar para origem e anexar modelo", use_container_width=True, key="btn_voltar_origem_sem_modelo_preview"):
        st.session_state["_ultima_etapa_sincronizada_url"] = "origem"
        ir_para_etapa("origem")
        st.rerun()


def _navegacao() -> None:
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_preview"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "mapeamento"
            voltar_etapa_anterior()
    with c2:
        if st.button("↺ Reabrir origem", use_container_width=True, key="btn_ir_origem_preview"):
            st.session_state["_ultima_etapa_sincronizada_url"] = "origem"
            ir_para_etapa("origem")


def _salvar_alinhado(df: pd.DataFrame, df_modelo: pd.DataFrame) -> pd.DataFrame:
    df = alinhar_ao_modelo_bling(df, df_modelo)
    st.session_state["df_final"] = df
    return df


def render_preview_final() -> None:
    garantir_etapa_preview_ativa()
    inicializar_estado_preview()
    st.subheader("4. Preview Final")

    tipo_operacao = normalizar_texto(st.session_state.get("tipo_operacao") or "cadastro") or "cadastro"
    deposito_nome = sincronizar_deposito_nome()
    df_modelo = st.session_state.get("df_modelo")
    if not safe_df_estrutura(df_modelo):
        _sem_modelo()
        return

    df_final = obter_df_final_exclusivo()
    df_session = st.session_state.get("df_final")
    if isinstance(df_session, pd.DataFrame) and safe_df_estrutura(df_session):
        df_final = df_session.copy() if not safe_df_estrutura(df_final) else mesclar_preservando_manual(df_final.copy().fillna(""), df_session.copy().fillna(""))

    if not safe_df_estrutura(df_final):
        _sem_df()
        return

    df_final = _salvar_alinhado(df_final, df_modelo)
    if not colunas_iguais_ao_modelo(df_final, df_modelo):
        st.error("Preview bloqueado: as colunas finais não correspondem ao modelo Bling anexado.")
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="btn_voltar_mapeamento_colunas_divergentes"):
            ir_para_etapa("mapeamento")
            st.rerun()
        return

    df_final = normalizar_preview(df_final, tipo_operacao, deposito_nome)
    df_final = _salvar_alinhado(df_final, df_modelo)
    sincronizar_estado_quando_df_mudar(df_final)

    validacao_ok, _ = render_resumo_validacao(df_final, tipo_operacao)
    df_final = obter_preview_atualizado(df_final, tipo_operacao, deposito_nome)
    df_final = _salvar_alinhado(df_final, df_modelo)

    df_final = render_ai_descricao(df_final)
    df_final = obter_preview_atualizado(df_final, tipo_operacao, deposito_nome)
    df_final = _salvar_alinhado(df_final, df_modelo)

    st.success("Preview final gerado sobre o modelo Bling anexado.")
    df_final = render_estoque_inteligente_final(df_final)
    df_final = _salvar_alinhado(df_final, df_modelo)
    sincronizar_estado_quando_df_mudar(df_final)

    render_preview_dataframe(df_final)
    render_download(df_final, validacao_ok)
    render_painel_bling(df_final, tipo_operacao, deposito_nome, validacao_ok)
    render_colunas_detectadas_sync(df_final)
    render_origem_site_metadata()
    render_bloco_fluxo_site()
    _navegacao()
