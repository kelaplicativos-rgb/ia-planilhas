from __future__ import annotations

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


def _render_precificacao(df_base):
    """
    Renderiza a calculadora ANTES do mapeamento manual.
    Mantém os valores em session_state para o fluxo seguinte.
    """
    st.markdown("### Precificação")

    with st.expander("💰 Abrir calculadora de precificação", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.number_input(
                "Margem de lucro (%)",
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
                "Custo fixo (R$)",
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

        df_preview = None
        try:
            df_preview = aplicar_precificacao_automatica(
                df_base.copy(),
                percentual_impostos=st.session_state.get("perc_impostos", 0),
                margem_lucro=st.session_state.get("margem_lucro", 0),
                custo_fixo=st.session_state.get("custo_fixo", 0),
                taxa_extra=st.session_state.get("taxa_extra", 0),
            )
        except Exception as e:
            log_debug(f"Erro ao montar preview da precificação: {e}")
            df_preview = None

        if _safe_df_dados(df_preview):
            with st.expander("👁️ Prévia da precificação", expanded=False):
                st.dataframe(df_preview.head(10), width="stretch")
        else:
            st.info("Configure a calculadora para preparar o preço antes do mapeamento manual.")


def render_origem_dados() -> None:
    if st.session_state.get("etapa_origem") == "mapeamento":
        return

    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    # =========================
    # ORIGEM
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            df_origem = ler_planilha_segura(arquivo)

            if not _safe_df_dados(df_origem):
                st.error("Erro ao ler planilha")
                return

    elif origem == "Site":
        df_origem = render_origem_site()

    elif origem == "XML":
        st.info("Origem XML ainda não está disponível nesta tela.")
        return

    if not _safe_df_dados(df_origem):
        return

    st.session_state["df_origem"] = df_origem

    with st.expander("👁️ Pré-visualização dos dados", expanded=False):
        st.dataframe(df_origem.head(10), width="stretch")

    # =========================
    # OPERAÇÃO
    # =========================
    op = st.radio(
        "Operação",
        ["Cadastro", "Estoque"],
        horizontal=True,
    )

    tipo = "cadastro" if op == "Cadastro" else "estoque"
    st.session_state["tipo_operacao_bling"] = tipo

    # =========================
    # MODELO
    # =========================
    deposito = ""

    if tipo == "cadastro":
        modelo = st.file_uploader(
            "Modelo Cadastro",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="modelo_cadastro",
        )

        if modelo:
            df_modelo = ler_planilha_segura(modelo)
            if _safe_df_modelo(df_modelo):
                st.session_state["df_modelo_cadastro"] = df_modelo
            else:
                st.error("Erro ao ler o modelo de cadastro")
                return

    else:
        modelo = st.file_uploader(
            "Modelo Estoque",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="modelo_estoque",
        )

        if modelo:
            df_modelo = ler_planilha_segura(modelo)
            if _safe_df_modelo(df_modelo):
                st.session_state["df_modelo_estoque"] = df_modelo
            else:
                st.error("Erro ao ler o modelo de estoque")
                return

        deposito = st.text_input("Nome do depósito", key="deposito_nome_manual")
        st.session_state["deposito_nome"] = deposito

    # =========================
    # CALCULADORA ANTES DO MAPEAMENTO
    # =========================
    _render_precificacao(df_origem)

    # =========================
    # VALIDAÇÃO
    # =========================
    modelo_ok = (
        _safe_df_modelo(st.session_state.get("df_modelo_cadastro"))
        if tipo == "cadastro"
        else _safe_df_modelo(st.session_state.get("df_modelo_estoque"))
    )

    if not modelo_ok:
        st.warning("Anexe o modelo oficial para continuar.")
        return

    if tipo == "estoque" and not st.session_state.get("deposito_nome"):
        st.warning("Informe o nome do depósito")
        return

    # =========================
    # AÇÃO PARA SEGUIR AO MAPEAMENTO
    # =========================
    if st.button("Continuar para o mapeamento", key="btn_continuar_mapeamento", use_container_width=True):
        df_saida = df_origem.copy()

        # 1) Depósito antes do mapeamento
        deposito_final = st.session_state.get("deposito_nome", "").strip()
        if tipo == "estoque":
            df_saida = _aplicar_deposito(df_saida, deposito_final)

        # 2) Precificação antes do mapeamento
        try:
            df_saida = aplicar_precificacao_automatica(
                df_saida,
                percentual_impostos=st.session_state.get("perc_impostos", 0),
                margem_lucro=st.session_state.get("margem_lucro", 0),
                custo_fixo=st.session_state.get("custo_fixo", 0),
                taxa_extra=st.session_state.get("taxa_extra", 0),
            )
        except Exception as e:
            st.error(f"Erro ao aplicar precificação: {e}")
            log_debug(f"Erro ao aplicar precificação automática: {e}")
            return

        if df_saida is None or not _safe_df_dados(df_saida):
            st.error("Erro nos dados. Não é possível continuar.")
            return

        st.session_state["df_saida"] = df_saida

        # Campos preenchidos automaticamente devem ficar bloqueados no mapeamento
        st.session_state["bloquear_campos_auto"] = {
            "deposito": bool(deposito_final),
            "preco": True,
        }

        st.session_state["etapa_origem"] = "mapeamento"

        log_debug("Fluxo OK → calculadora exibida antes do mapeamento, depósito e preço aplicados antes de seguir")

        st.rerun()
