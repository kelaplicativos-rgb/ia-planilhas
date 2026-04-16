
from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import ir_para_etapa, log_debug, safe_df_dados
from bling_app_zero.ui.origem_dados_handlers import (
    consolidar_saida_da_origem,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_ui import (
    render_bloco_acoes_origem,
    render_origem_entrada,
)

NavCallback = Callable[[], None] | None


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        texto = str(valor).strip()
        if texto.lower() in {"none", "nan", "nat"}:
            return ""
        return texto
    except Exception:
        return ""


def _resolver_df_origem_atual(df_origem_render: pd.DataFrame | None) -> pd.DataFrame | None:
    if safe_df_dados(df_origem_render):
        return _safe_copy_df(df_origem_render)

    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        return _safe_copy_df(df_origem)

    for chave in ["df_saida", "df_final", "df_precificado", "df_calc_precificado"]:
        df_alt = st.session_state.get(chave)
        if safe_df_dados(df_alt):
            try:
                st.session_state["df_origem"] = df_alt.copy()
            except Exception:
                st.session_state["df_origem"] = df_alt
            return _safe_copy_df(df_alt)

    return None


def _persistir_origem(df_origem: pd.DataFrame | None) -> pd.DataFrame | None:
    if not safe_df_dados(df_origem):
        return None

    df_base = _safe_copy_df(df_origem)
    sincronizar_estado_com_origem(df_base, log_debug)

    df_saida = consolidar_saida_da_origem(df_base)

    st.session_state["df_origem"] = _safe_copy_df(df_base)
    st.session_state["df_saida"] = _safe_copy_df(df_saida)
    st.session_state["df_final"] = _safe_copy_df(df_saida)

    return df_saida


def _render_resumo_curto(df_origem: pd.DataFrame | None = None) -> None:
    operacao = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("tipo_operacao_radio")
        or st.session_state.get("tipo_operacao_bling")
    )
    origem = _safe_str(
        st.session_state.get("origem_dados_tipo")
        or st.session_state.get("origem_dados_radio")
        or st.session_state.get("origem_tipo")
        or st.session_state.get("origem_tipo_radio")
    )
    deposito = _safe_str(st.session_state.get("deposito_nome"))
    linhas = 0

    if safe_df_dados(df_origem):
        try:
            linhas = int(len(df_origem))
        except Exception:
            linhas = 0

    detalhes = [
        f"Operação: {operacao or 'Não definida'}",
        f"Origem: {origem or 'Não definida'}",
        f"Linhas carregadas: {linhas}",
    ]
    if deposito:
        detalhes.append(f"Depósito: {deposito}")

    st.info(" | ".join(detalhes))


def _render_preview_origem(df_origem: pd.DataFrame | None) -> None:
    if not safe_df_dados(df_origem):
        return

    with st.expander("Preview da origem", expanded=False):
        st.dataframe(df_origem.head(8), use_container_width=True, hide_index=True)
        st.caption(f"{len(df_origem)} linha(s) | {len(df_origem.columns)} coluna(s)")


def _render_cabecalho_origem() -> None:
    st.subheader("Origem dos dados")

    origem = _safe_str(st.session_state.get("origem_tipo")).lower()
    operacao = _safe_str(st.session_state.get("tipo_operacao_bling")).lower()

    mapa_origem = {
        "site": "Site",
        "planilha": "Planilha fornecedora",
        "xml": "XML da nota fiscal",
    }
    mapa_operacao = {
        "cadastro": "Cadastro de Produtos",
        "estoque": "Atualização de Estoque",
    }

    texto_origem = mapa_origem.get(origem, "Origem não definida")
    texto_operacao = mapa_operacao.get(operacao, "Operação não definida")

    st.caption(f"Fluxo atual: {texto_operacao} → {texto_origem}")


def render_origem_dados() -> pd.DataFrame | None:
    _render_cabecalho_origem()

    df_origem_render = render_origem_entrada()
    df_origem = _resolver_df_origem_atual(df_origem_render)
    df_saida = _persistir_origem(df_origem)

    _render_resumo_curto(df_origem)
    _render_preview_origem(df_origem)

    render_bloco_acoes_origem(df_origem)

    if safe_df_dados(df_saida):
        log_debug(
            f"[ORIGEM_DADOS] etapa concluída com {len(df_saida)} linha(s) prontas para precificação.",
            "INFO",
        )

    return df_saida


def continuar_para_precificacao() -> None:
    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        ir_para_etapa("precificacao")
