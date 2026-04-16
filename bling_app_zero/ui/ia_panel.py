
from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import streamlit as st


def _ler_arquivo(upload) -> Optional[pd.DataFrame]:
    if upload is None:
        return None

    nome = (upload.name or "").lower()
    bruto = upload.getvalue()

    try:
        if nome.endswith(".csv"):
            for enc in ("utf-8", "utf-8-sig", "latin1"):
                for sep in (None, ";", ",", "\t", "|"):
                    try:
                        return pd.read_csv(io.BytesIO(bruto), encoding=enc, sep=sep, engine="python")
                    except Exception:
                        continue

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            try:
                return pd.read_excel(io.BytesIO(bruto), engine="openpyxl")
            except Exception:
                return pd.read_excel(io.BytesIO(bruto))
    except Exception:
        return None

    return None


def _normalizar_texto(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"nan", "none", "nat"}:
        return ""
    return texto


def _render_modelos() -> None:
    st.markdown("#### Modelos do Bling")

    tipo_operacao = st.radio(
        "Selecione o fluxo",
        ["Cadastro de produtos", "Atualização de estoque"],
        horizontal=True,
        key="tipo_operacao_radio",
    )

    st.session_state["tipo_operacao"] = "cadastro" if "Cadastro" in tipo_operacao else "estoque"

    cadastro_upload = st.file_uploader(
        "Modelo de cadastro",
        type=["csv", "xlsx", "xls"],
        key="modelo_cadastro_upload",
    )
    estoque_upload = st.file_uploader(
        "Modelo de estoque",
        type=["csv", "xlsx", "xls"],
        key="modelo_estoque_upload",
    )

    df_cadastro = _ler_arquivo(cadastro_upload) if cadastro_upload else None
    df_estoque = _ler_arquivo(estoque_upload) if estoque_upload else None

    if cadastro_upload is not None:
        st.session_state["modelo_cadastro_nome"] = cadastro_upload.name
    if estoque_upload is not None:
        st.session_state["modelo_estoque_nome"] = estoque_upload.name

    if st.session_state["tipo_operacao"] == "cadastro" and df_cadastro is not None:
        st.session_state["df_modelo_base"] = df_cadastro.head(0).copy()
    elif st.session_state["tipo_operacao"] == "estoque" and df_estoque is not None:
        st.session_state["df_modelo_base"] = df_estoque.head(0).copy()

    if st.session_state.get("df_modelo_base") is not None:
        st.success("Modelo base carregado para o fluxo selecionado.")


def render_ia_panel() -> None:
    st.markdown("### Origem dos dados")
    st.caption("Escolha a operação, envie a planilha de origem e também o modelo do Bling que servirá de base.")

    with st.container(border=True):
        _render_modelos()

    with st.container(border=True):
        st.markdown("#### Planilha de origem")
        origem_upload = st.file_uploader(
            "Arquivo com os produtos",
            type=["csv", "xlsx", "xls"],
            key="arquivo_origem_upload",
        )

        if origem_upload is not None:
            df_origem = _ler_arquivo(origem_upload)
            if df_origem is not None and not df_origem.empty:
                st.session_state["df_origem"] = df_origem.copy()
                st.session_state["arquivo_origem_nome"] = origem_upload.name
                st.success(f"Origem carregada com {len(df_origem)} linhas.")
                with st.expander("Ver origem", expanded=False):
                    st.dataframe(df_origem.head(50), use_container_width=True)
            else:
                st.error("Não foi possível ler a planilha de origem.")

    with st.container(border=True):
        st.markdown("#### Regras do fluxo")
        st.caption("Na próxima etapa, a precificação só avança quando todos os campos obrigatórios forem preenchidos.")
        st.caption("Depois disso, o sistema pergunta para onde vão os campos que ele não conseguir mapear sozinho.")
        st.caption("Antes do download, haverá um preview final para confirmação.")


