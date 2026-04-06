from __future__ import annotations

import json

import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site
from bling_app_zero.core.precificacao import aplicar_precificacao_automatica


def _safe_df_dados(df):
    try:
        if df is None:
            return False
        if not hasattr(df, "columns"):
            return False
        if len(df.columns) == 0:
            return False
        if df.empty:
            return False
        return True
    except Exception:
        return False


def _safe_df_modelo(df):
    try:
        if df is None:
            return False
        if not hasattr(df, "columns"):
            return False
        if len(df.columns) == 0:
            return False
        return True
    except Exception:
        return False


def _detectar_coluna_deposito(df):
    for col in df.columns:
        nome = str(col).lower().strip()
        if "deposit" in nome or "depós" in nome or "deposito" in nome:
            return col
    return None


def _aplicar_deposito(df, deposito):
    if not deposito:
        return df

    df_saida = df.copy()
    col_dep = _detectar_coluna_deposito(df_saida)

    if col_dep:
        df_saida[col_dep] = deposito
    else:
        df_saida["Depósito"] = deposito

    return df_saida


def _normalizar_coluna_numerica(df, coluna):
    if coluna not in df.columns:
        return df

    df_saida = df.copy()

    try:
        serie = df_saida[coluna].astype(str).str.strip()
        serie = serie.str.replace("R$", "", regex=False)
        serie = serie.str.replace("r$", "", regex=False)
        serie = serie.str.replace(" ", "", regex=False)
        serie = serie.str.replace(".", "", regex=False)
        serie = serie.str.replace(",", ".", regex=False)

        df_saida[coluna] = serie.astype(float)
    except Exception:
        try:
            df_saida[coluna] = (
                df_saida[coluna]
                .astype(str)
                .str.replace("R$", "", regex=False)
                .str.replace("r$", "", regex=False)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
                .astype(float)
            )
        except Exception:
            pass

    return df_saida


def _coletar_parametros_precificacao():
    return {
        "percentual_impostos": float(st.session_state.get("perc_impostos", 0) or 0),
        "margem_lucro": float(st.session_state.get("margem_lucro", 0) or 0),
        "custo_fixo": float(st.session_state.get("custo_fixo", 0) or 0),
        "taxa_extra": float(st.session_state.get("taxa_extra", 0) or 0),
    }


def _aplicar_precificacao_com_fallback(df_base, coluna_preco):
    df_temp = df_base.copy()
    df_temp = _normalizar_coluna_numerica(df_temp, coluna_preco)

    kwargs = _coletar_parametros_precificacao()

    try:
        df_resultado = aplicar_precificacao_automatica(
            df_temp,
            coluna_preco=coluna_preco,
            **kwargs,
        )
    except TypeError:
        df_resultado = aplicar_precificacao_automatica(
            df_temp,
            **kwargs,
        )

    return df_resultado


def _assinatura_fluxo_precificacao(df_base, coluna_preco):
    payload = {
        "coluna_preco": str(coluna_preco),
        "margem_lucro": float(st.session_state.get("margem_lucro", 0) or 0),
        "perc_impostos": float(st.session_state.get("perc_impostos", 0) or 0),
        "custo_fixo": float(st.session_state.get("custo_fixo", 0) or 0),
        "taxa_extra": float(st.session_state.get("taxa_extra", 0) or 0),
        "linhas": int(len(df_base)) if hasattr(df_base, "__len__") else 0,
        "colunas": [str(c) for c in getattr(df_base, "columns", [])],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _render_precificacao(df_base):
    st.markdown("### Precificação")

    if not _safe_df_dados(df_base):
        st.session_state["preco_gerado"] = False
        st.session_state["df_precificado"] = None
        return

    colunas = list(df_base.columns)
    if not colunas:
        st.session_state["preco_gerado"] = False
        st.session_state["df_precificado"] = None
        return

    coluna_sugerida = 0
    coluna_preco_salva = st.session_state.get("coluna_preco_base")

    if coluna_preco_salva in colunas:
        coluna_sugerida = colunas.index(coluna_preco_salva)
    else:
        for i, col in enumerate(colunas):
            nome = str(col).lower().strip()
            if (
                "preco" in nome
                or "preço" in nome
                or "valor" in nome
                or "custo" in nome
                or "compra" in nome
            ):
                coluna_sugerida = i
                break

    coluna_preco = st.selectbox(
        "Selecione a coluna de PREÇO DE CUSTO",
        options=colunas,
        index=coluna_sugerida,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Margem (%)",
            min_value=0.0,
            step=0.1,
            key="margem_lucro",
        )
        st.number_input(
            "Impostos (%)",
            min_value=0.0,
            step=0.1,
            key="perc_impostos",
        )

    with col2:
        st.number_input(
            "Custo fixo",
            min_value=0.0,
            step=0.01,
            key="custo_fixo",
        )
        st.number_input(
            "Taxa extra (%)",
            min_value=0.0,
            step=0.1,
            key="taxa_extra",
        )

    assinatura_atual = _assinatura_fluxo_precificacao(df_base, coluna_preco)
    assinatura_anterior = st.session_state.get("assinatura_precificacao_atual")

    try:
        df_precificado = _aplicar_precificacao_com_fallback(df_base, coluna_preco)

        if _safe_df_dados(df_precificado):
            st.session_state["df_precificado"] = df_precificado.copy()
            st.session_state["preco_gerado"] = True
            st.session_state["coluna_preco_base_aplicada"] = coluna_preco
            st.session_state["assinatura_precificacao_atual"] = assinatura_atual

            # Garante que a saída usada no restante do fluxo receba sempre a versão mais atual
            st.session_state["df_saida"] = df_precificado.copy()
            st.session_state["bloquear_campos_auto"] = {
                "deposito": False,
                "preco": False,
            }

            with st.expander("👁️ Prévia da precificação", expanded=False):
                st.dataframe(st.session_state["df_precificado"].head(10), width="stretch")
        else:
            # Se a função não retornar um DF válido, limpa o estado para evitar prévia velha
            if assinatura_anterior != assinatura_atual:
                st.session_state["df_precificado"] = None
                st.session_state["preco_gerado"] = False
                st.session_state["assinatura_precificacao_atual"] = assinatura_atual

    except Exception as e:
        st.session_state["preco_gerado"] = False
        st.session_state["df_precificado"] = None
        log_debug(f"Erro na precificação automática: {e}")


def render_origem_dados() -> None:
    etapa_atual = st.session_state.get("etapa_origem")

    if etapa_atual in ["mapeamento", "final"]:
        return

    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            df_origem = ler_planilha_segura(arquivo)

    elif origem == "Site":
        df_origem = render_origem_site()

    elif origem == "XML":
        st.info("Origem XML ainda não está disponível nesta tela.")
        return

    if not _safe_df_dados(df_origem):
        return

    st.session_state["df_origem"] = df_origem

    _render_precificacao(df_origem)

    df_precificado = st.session_state.get("df_precificado")

    if _safe_df_dados(df_precificado):
        st.session_state["df_saida"] = df_precificado.copy()
        st.session_state["bloquear_campos_auto"] = {
            "deposito": False,
            "preco": False,
        }

        # AVANÇO AUTOMÁTICO REMOVIDO COMPLETAMENTE
        # O fluxo não muda mais de etapa sozinho a partir deste arquivo.
