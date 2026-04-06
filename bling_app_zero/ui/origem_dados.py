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


def _normalizar_coluna_numerica(df, coluna):
    if coluna not in df.columns:
        return df

    df_saida = df.copy()

    try:
        serie = df_saida[coluna].astype(str).str.strip()
        serie = serie.str.replace("R$", "", regex=False)
        serie = serie.str.replace("r$", "", regex=False)
        serie = serie.str.replace(" ", "", regex=False)

        # remove separador de milhar e ajusta decimal
        serie = serie.str.replace(".", "", regex=False)
        serie = serie.str.replace(",", ".", regex=False)

        # limpa valores inválidos comuns
        serie = serie.replace(
            {
                "": None,
                "nan": None,
                "None": None,
                "null": None,
                "-": None,
            }
        )

        df_saida[coluna] = serie.astype(float)
    except Exception:
        try:
            df_saida[coluna] = (
                df_saida[coluna]
                .astype(str)
                .str.replace("R$", "", regex=False)
                .str.replace(",", ".", regex=False)
                .astype(float)
            )
        except Exception:
            pass

    return df_saida


def _aplicar_precificacao_com_fallback(df_base, coluna_preco):
    """
    Tenta aplicar a precificação passando a coluna escolhida.
    Se a função do core ainda não aceitar 'coluna_preco',
    faz fallback sem quebrar o fluxo.
    """
    df_temp = df_base.copy()
    df_temp = _normalizar_coluna_numerica(df_temp, coluna_preco)

    kwargs = {
        "percentual_impostos": st.session_state.get("perc_impostos", 0),
        "margem_lucro": st.session_state.get("margem_lucro", 0),
        "custo_fixo": st.session_state.get("custo_fixo", 0),
        "taxa_extra": st.session_state.get("taxa_extra", 0),
    }

    try:
        return aplicar_precificacao_automatica(
            df_temp,
            coluna_preco=coluna_preco,
            **kwargs,
        )
    except TypeError:
        # fallback para versões antigas da função
        return aplicar_precificacao_automatica(
            df_temp,
            **kwargs,
        )


def _render_precificacao(df_base):
    """
    Calculadora com seleção de coluna + botão explícito para gerar preço.
    Mantém o resultado em session_state para o fluxo seguinte.
    """
    st.markdown("### Precificação")

    if not _safe_df_dados(df_base):
        st.info("Carregue os dados de origem para habilitar a precificação.")
        return

    colunas = list(df_base.columns)
    if not colunas:
        st.info("Nenhuma coluna disponível para precificação.")
        return

    # sugestão automática de coluna de preço/custo
    coluna_sugerida = 0
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

    with st.expander("💰 Configurar precificação", expanded=True):
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

    if st.button("💰 Gerar precificação", key="btn_gerar_precificacao", use_container_width=True):
        try:
            df_precificado = _aplicar_precificacao_com_fallback(df_base, coluna_preco)

            if _safe_df_dados(df_precificado):
                st.session_state["df_precificado"] = df_precificado
                st.session_state["preco_gerado"] = True
                st.session_state["coluna_preco_base_aplicada"] = coluna_preco
                st.success("✅ Precificação aplicada com sucesso!")
            else:
                st.session_state["preco_gerado"] = False
                st.error("Não foi possível gerar a precificação.")
        except Exception as e:
            st.session_state["preco_gerado"] = False
            st.error(f"Erro na precificação: {e}")
            log_debug(f"Erro na precificação manual: {e}")

    if st.session_state.get("preco_gerado"):
        df_preview = st.session_state.get("df_precificado")

        if _safe_df_dados(df_preview):
            with st.expander("👁️ Prévia da precificação", expanded=False):
                st.dataframe(df_preview.head(10), width="stretch")
    else:
        st.info("Escolha a coluna de custo e clique em 'Gerar precificação' para aplicar o preço antes do mapeamento.")


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
        # PRIORIDADE TOTAL PARA DF PRECIFICADO
        if st.session_state.get("preco_gerado"):
            df_saida = st.session_state.get("df_precificado")

            if not _safe_df_dados(df_saida):
                st.error("Erro: precificação foi gerada mas os dados são inválidos.")
                return

            df_saida = df_saida.copy()

        else:
            st.warning("⚠️ Gere a precificação antes de continuar.")
            return

        # 1) Depósito antes do mapeamento
        deposito_final = st.session_state.get("deposito_nome", "").strip()
        if tipo == "estoque":
            df_saida = _aplicar_deposito(df_saida, deposito_final)

        if df_saida is None or not _safe_df_dados(df_saida):
            st.error("Erro nos dados. Não é possível continuar.")
            return

        st.session_state["df_saida"] = df_saida

        # Campos preenchidos automaticamente devem ficar bloqueados no mapeamento
        st.session_state["bloquear_campos_auto"] = {
            "deposito": bool(deposito_final),
            "preco": bool(st.session_state.get("preco_gerado")),
        }

        st.session_state["etapa_origem"] = "mapeamento"

        log_debug(
            "Fluxo OK → calculadora exibida antes do mapeamento, com seleção de coluna de custo, botão para gerar precificação e aplicação antes de seguir"
        )

        st.rerun()
