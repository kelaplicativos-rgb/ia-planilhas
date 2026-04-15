
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    sincronizar_etapa_global,
)


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


def _limpar_fluxo_abaixo_da_origem() -> None:
    for chave in [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_preview_mapeamento",
        "mapping_origem",
        "mapping_origem_rascunho",
        "mapping_origem_defaults",
    ]:
        if chave in st.session_state:
            st.session_state[chave] = {} if "mapping" in chave else None


def _modelo_padrao_por_operacao(tipo_operacao_bling: str) -> pd.DataFrame:
    if tipo_operacao_bling == "estoque":
        colunas = [
            "Código",
            "Descrição",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
            "Situação",
        ]
    else:
        colunas = [
            "Código",
            "Descrição",
            "Descrição Curta",
            "Preço de venda",
            "GTIN/EAN",
            "Situação",
            "URL Imagens",
        ]
    return pd.DataFrame(columns=colunas)


def _ler_upload_arquivo(upload) -> pd.DataFrame | None:
    if upload is None:
        return None

    nome = _safe_str(getattr(upload, "name", "")).lower()

    try:
        if nome.endswith(".csv"):
            bruto = upload.getvalue()
            for sep in [";", ",", "\t"]:
                try:
                    return pd.read_csv(io.BytesIO(bruto), sep=sep, dtype=str).fillna("")
                except Exception:
                    continue
            return None

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return pd.read_excel(upload, dtype=str).fillna("")
    except Exception as e:
        log_debug(f"Erro lendo upload: {e}", "ERROR")

    return None


def _resolver_df_origem_atual() -> pd.DataFrame | None:
    for chave in ["df_origem", "df_saida", "df_final", "df_precificado", "df_calc_precificado"]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


def _set_operacao(label: str) -> None:
    if label == "Atualização de Estoque":
        st.session_state["tipo_operacao"] = "Atualização de Estoque"
        st.session_state["tipo_operacao_radio"] = "Atualização de Estoque"
        st.session_state["tipo_operacao_bling"] = "estoque"
    else:
        st.session_state["tipo_operacao"] = "Cadastro de Produtos"
        st.session_state["tipo_operacao_radio"] = "Cadastro de Produtos"
        st.session_state["tipo_operacao_bling"] = "cadastro"

    st.session_state["df_modelo_operacao"] = _modelo_padrao_por_operacao(
        st.session_state["tipo_operacao_bling"]
    )


def render_origem_dados() -> pd.DataFrame | None:
    st.markdown("### 📦 Origem dos dados")
    st.caption("Escolha a operação, carregue a base e siga para a precificação.")

    operacao_atual = _safe_str(
        st.session_state.get("tipo_operacao") or "Cadastro de Produtos"
    )
    if operacao_atual not in {"Cadastro de Produtos", "Atualização de Estoque"}:
        operacao_atual = "Cadastro de Produtos"

    st.markdown("#### O que você quer fazer?")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cadastro de Produtos", use_container_width=True, type="primary" if operacao_atual == "Cadastro de Produtos" else "secondary"):
            _set_operacao("Cadastro de Produtos")

    with col2:
        if st.button("Atualização de Estoque", use_container_width=True, type="primary" if operacao_atual == "Atualização de Estoque" else "secondary"):
            _set_operacao("Atualização de Estoque")

    if "tipo_operacao_bling" not in st.session_state:
        _set_operacao(operacao_atual)

    if st.session_state.get("tipo_operacao_bling") == "estoque":
        deposito_nome = st.text_input(
            "Nome do depósito",
            value=_safe_str(st.session_state.get("deposito_nome")),
            key="deposito_nome",
        )
        st.session_state["deposito_nome"] = deposito_nome

    st.markdown("#### Anexar planilha fornecedora")
    upload = st.file_uploader(
        "Envie CSV, XLSX ou XLS",
        type=["csv", "xlsx", "xls"],
        key="origem_upload_fornecedor",
    )

    df_novo = _ler_upload_arquivo(upload)
    if safe_df_dados(df_novo):
        st.session_state["df_origem"] = df_novo.copy()
        _limpar_fluxo_abaixo_da_origem()
        st.session_state["df_origem"] = df_novo.copy()
        log_debug("Origem carregada por upload com sucesso.", "INFO")

    df_origem = _resolver_df_origem_atual()

    if safe_df_dados(df_origem):
        st.success(f"Origem pronta com {len(df_origem)} linha(s) e {len(df_origem.columns)} coluna(s).")

        with st.expander("🔎 Preview da origem", expanded=False):
            st.dataframe(df_origem.head(20), use_container_width=True)
    else:
        st.info("Anexe a planilha para liberar o próximo passo.")

    st.markdown("---")
    pode_continuar = safe_df_dados(df_origem)

    if st.button("Continuar ➜", use_container_width=True, disabled=not pode_continuar):
        st.session_state["df_saida"] = df_origem.copy()
        sincronizar_etapa_global("precificacao")
        st.rerun()

    return df_origem
