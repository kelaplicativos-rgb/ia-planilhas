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


def _eh_valor_preenchido(valor) -> bool:
    if pd.isna(valor):
        return False
    if isinstance(valor, str):
        return valor.strip() != ""
    return True


def _mesclar_df_preservando_manual(
    df_base_normalizado: pd.DataFrame,
    df_manual_existente: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    Preserva no preview final tudo que já foi ajustado manualmente pelo usuário.
    Regra:
    - se houver valor manual preenchido, ele prevalece;
    - se estiver vazio no manual, usa o valor normalizado/base.
    """
    if not isinstance(df_manual_existente, pd.DataFrame) or not safe_df_estrutura(df_manual_existente):
        return df_base_normalizado.copy()

    if df_base_normalizado is None or df_base_normalizado.empty:
        return df_manual_existente.copy().fillna("")

    df_base = df_base_normalizado.copy().fillna("")
    df_manual = df_manual_existente.copy().fillna("")

    # Garante mesma quantidade de linhas para evitar desalinhamento
    if len(df_manual.index) != len(df_base.index):
        return df_base

    # Garante presença de colunas do base no manual
    for coluna in df_base.columns:
        if coluna not in df_manual.columns:
            df_manual[coluna] = ""

    # Mantém ordem/estrutura canônica do base
    df_manual = df_manual[df_base.columns.tolist()]

    for coluna in df_base.columns:
        serie_manual = df_manual[coluna]
        mascara_manual_preenchido = serie_manual.apply(_eh_valor_preenchido)
        df_base.loc[mascara_manual_preenchido, coluna] = serie_manual.loc[mascara_manual_preenchido]

    return df_base


def _normalizar_df_preview(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    """
    Normaliza o df final sem perder alterações manuais já existentes no session_state.
    """
    df_atual_manual = st.session_state.get("df_final")

    df_normalizado = garantir_df_final_canonico(
        df=df_final,
        tipo_operacao=tipo_operacao,
        deposito_nome=deposito_nome,
    )
    df_normalizado = zerar_colunas_video(df_normalizado)

    df_resultado = _mesclar_df_preservando_manual(df_normalizado, df_atual_manual).fillna("")
    st.session_state["df_final"] = df_resultado
    return df_resultado


def _obter_df_preview_atualizado(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    """
    Sempre prioriza a versão atual de df_final que esteja no session_state,
    preservando o que o usuário alterou manualmente.
    """
    df_final_atualizado = st.session_state.get("df_final", df_final)

    if isinstance(df_final_atualizado, pd.DataFrame) and safe_df_estrutura(df_final_atualizado):
        df_final_base = df_final.copy().fillna("") if isinstance(df_final, pd.DataFrame) else pd.DataFrame()
        df_final_manual = df_final_atualizado.copy().fillna("")

        # Primeiro normaliza a base atual
        df_final_base = garantir_df_final_canonico(
            df=df_final_base if safe_df_estrutura(df_final_base) else df_final_manual,
            tipo_operacao=tipo_operacao,
            deposito_nome=deposito_nome,
        )
        df_final_base = zerar_colunas_video(df_final_base)

        # Depois reaplica o manual por cima
        df_final_mesclado = _mesclar_df_preservando_manual(df_final_base, df_final_manual).fillna("")
        st.session_state["df_final"] = df_final_mesclado
        return df_final_mesclado

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

    # Se já existir um df_final manualmente trabalhado, ele passa a ser a base prioritária
    df_final_session = st.session_state.get("df_final")
    if isinstance(df_final_session, pd.DataFrame) and safe_df_estrutura(df_final_session):
        if not safe_df_estrutura(df_final):
            df_final = df_final_session.copy()
        else:
            df_final = _mesclar_df_preservando_manual(
                df_base_normalizado=df_final.copy().fillna(""),
                df_manual_existente=df_final_session.copy().fillna(""),
            )

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
