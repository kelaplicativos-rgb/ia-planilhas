from __future__ import annotations

import traceback
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.file_reader import read_uploaded_table
from bling_app_zero.ui.debug_panel import add_debug_log, render_debug_panel
from bling_app_zero.ui.site_stock_capture import render_site_stock_capture
from bling_app_zero.ui.smart_clip_uploader import render_smart_clip_uploader


MODELO_KEYS = {
    "cadastro": "df_modelo_cadastro",
    "estoque": "df_modelo_estoque",
}


def _registrar_erro_origem(exc: Exception) -> None:
    add_debug_log("Erro ao ler origem", str(exc))
    st.error("Não foi possível ler a origem.")
    st.warning("Detalhe técnico do erro real:")
    st.code(str(exc))
    with st.expander("Ver traceback completo", expanded=False):
        st.code(traceback.format_exc())


def _ler_upload(uploaded: Any, state_key: str, log_label: str) -> pd.DataFrame | None:
    if uploaded is None:
        return st.session_state.get(state_key)

    try:
        add_debug_log(log_label, getattr(uploaded, "name", "sem_nome"))
        result = read_uploaded_table(uploaded)
        df = result.dataframe

        if df is None or df.empty:
            raise ValueError("A planilha foi lida, mas não possui linhas válidas.")

        st.session_state[state_key] = df
        st.session_state["tipo_origem"] = "arquivo"
        add_debug_log(
            f"{log_label} lido com sucesso",
            f"linhas={len(df)} colunas={len(df.columns)} tipo={result.file_type}",
        )
        st.success(f"{log_label} reconhecido com sucesso ({result.file_type}) | {result.detail}")
        st.caption(f"Linhas: {len(df)} | Colunas: {len(df.columns)}")
        return df
    except Exception as exc:
        _registrar_erro_origem(exc)
        return None


def _set_operacao(tipo: str) -> None:
    st.session_state["tipo_operacao"] = tipo
    add_debug_log("Fluxo", f"Operação selecionada: {tipo}")


def _modelo_state_key(tipo_operacao: str) -> str:
    return MODELO_KEYS.get(tipo_operacao, "df_modelo_cadastro")


def _render_operacao() -> str:
    st.subheader("O que você quer gerar?")
    atual = st.session_state.get("tipo_operacao", "cadastro")
    opcoes = {
        "cadastro": "Cadastro de produtos",
        "estoque": "Atualização de estoque",
    }
    escolha = st.radio(
        "Escolha o destino do arquivo final",
        options=list(opcoes.keys()),
        format_func=lambda k: opcoes[k],
        horizontal=True,
        index=list(opcoes.keys()).index(atual) if atual in opcoes else 0,
        label_visibility="collapsed",
    )
    if escolha != atual:
        _set_operacao(escolha)
    else:
        st.session_state["tipo_operacao"] = escolha
    return escolha


def _render_preview(label: str, df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info(f"{label}: nenhum arquivo carregado ainda.")
        return
    st.caption(f"{label}: {len(df)} linhas × {len(df.columns)} colunas")
    st.dataframe(df.head(30), use_container_width=True)


def _pode_mapear(df_origem: pd.DataFrame | None) -> bool:
    return df_origem is not None and not df_origem.empty


def render_origem_dados() -> None:
    render_debug_panel()

    st.title("1. Origem + preview")
    st.caption(
        "Anexe o arquivo do fornecedor como se fosse um clipe de mensagem ou gere a base de estoque por site. "
        "O sistema tenta reconhecer automaticamente Excel, CSV, TXT, HTML, JSON e outros formatos tabulares."
    )

    tipo_operacao = _render_operacao()

    deposito = ""
    if tipo_operacao == "estoque":
        deposito = st.text_input(
            "Nome do depósito",
            value=str(st.session_state.get("deposito_nome", "")),
            placeholder="Ex.: Depósito Geral",
            help="Esse nome será reaproveitado no mapeamento e na exportação de estoque.",
        ).strip()
        st.session_state["deposito_nome"] = deposito

    st.divider()

    col_origem, col_modelo = st.columns(2)

    with col_origem:
        uploaded_origem = render_smart_clip_uploader(
            label="Arquivo do fornecedor",
            key="upload_origem_fornecedor",
            help_text="Anexe a tabela do fornecedor. Pode ser Excel, CSV, TXT, TSV, ODS, HTML ou JSON.",
        )
        df_origem = _ler_upload(uploaded_origem, "df_origem", "Arquivo de origem")

        if tipo_operacao == "estoque":
            df_site = render_site_stock_capture(deposito=deposito)
            if isinstance(df_site, pd.DataFrame) and not df_site.empty:
                df_origem = df_site

        with st.expander("Preview da planilha de origem", expanded=False):
            _render_preview("Origem", df_origem)

    with col_modelo:
        modelo_key = _modelo_state_key(tipo_operacao)
        uploaded_modelo = render_smart_clip_uploader(
            label="Modelo Bling de referência",
            key=f"upload_modelo_{tipo_operacao}",
            help_text="Opcional. Anexe o modelo de cadastro ou estoque do Bling para respeitar as colunas reais.",
        )
        df_modelo = _ler_upload(uploaded_modelo, modelo_key, "Modelo Bling")
        with st.expander("Preview do modelo Bling", expanded=False):
            _render_preview("Modelo Bling", df_modelo)

    st.divider()

    df_origem = st.session_state.get("df_origem")
    df_modelo = st.session_state.get(_modelo_state_key(tipo_operacao))

    c1, c2, c3 = st.columns(3)
    c1.metric("Origem", "OK" if _pode_mapear(df_origem) else "Pendente")
    c2.metric("Modelo Bling", "Anexado" if df_modelo is not None and not df_modelo.empty else "Opcional")
    c3.metric("Operação", "Cadastro" if tipo_operacao == "cadastro" else "Estoque")

    if not _pode_mapear(df_origem):
        if tipo_operacao == "estoque":
            st.warning("Anexe o arquivo do fornecedor ou gere a base por site para liberar o mapeamento.")
        else:
            st.warning("Anexe o arquivo do fornecedor para liberar o mapeamento.")
        return

    if tipo_operacao == "estoque" and not str(st.session_state.get("deposito_nome", "")).strip():
        st.warning("Informe o nome do depósito para avançar na atualização de estoque.")
        return

    st.success("Arquivo pronto para mapeamento. Você já pode revisar as colunas e seguir direto.")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🧭 Ir direto para o mapeamento", type="primary", use_container_width=True):
            st.session_state["wizard_etapa_atual"] = "mapeamento"
            st.session_state["wizard_etapa_maxima"] = "mapeamento"
            st.rerun()
    with col_b:
        if st.button("🧹 Limpar origem e modelos", use_container_width=True):
            for key in ["df_origem", "df_modelo_cadastro", "df_modelo_estoque", "df_mapeado", "tipo_origem", "site_urls_raw"]:
                st.session_state.pop(key, None)
            st.session_state["wizard_etapa_atual"] = "origem"
            st.session_state["wizard_etapa_maxima"] = "origem"
            st.rerun()
