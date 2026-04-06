from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site
from bling_app_zero.core.precificacao import aplicar_precificacao_automatica


def _safe_df_dados(df) -> bool:
    try:
        if df is None:
            return False
        if not hasattr(df, "columns"):
            return False
        if len(df.columns) == 0:
            return False
        if getattr(df, "empty", True):
            return False
        return True
    except Exception:
        return False


def _safe_float(valor, default: float = 0.0) -> float:
    try:
        if valor is None or valor == "":
            return default
        return float(valor)
    except Exception:
        return default


def _coletar_parametros_precificacao():
    return {
        "percentual_impostos": _safe_float(st.session_state.get("perc_impostos", 0)),
        "margem_lucro": _safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": _safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa_extra": _safe_float(st.session_state.get("taxa_extra", 0)),
    }


def _aplicar_precificacao_com_fallback(df_base, coluna_preco):
    kwargs = _coletar_parametros_precificacao()

    try:
        return aplicar_precificacao_automatica(
            df_base.copy(),
            coluna_preco=coluna_preco,
            **kwargs,
        )
    except TypeError:
        return aplicar_precificacao_automatica(
            df_base.copy(),
            **kwargs,
        )


def _carregar_modelo_bling(arquivo, tipo_modelo: str) -> bool:
    """
    Lê o modelo anexado e salva no session_state na chave esperada
    pelo fluxo de mapeamento.
    """
    if arquivo is None:
        return False

    try:
        df_modelo = ler_planilha_segura(arquivo)

        if not _safe_df_dados(df_modelo):
            st.error("Não foi possível ler o modelo Bling anexado.")
            return False

        if tipo_modelo == "cadastro":
            st.session_state["df_modelo_cadastro"] = df_modelo.copy()
            st.session_state["modelo_cadastro_nome"] = getattr(arquivo, "name", "modelo_cadastro")
            log_debug(
                f"Modelo de cadastro carregado: {getattr(arquivo, 'name', 'arquivo')} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )
        else:
            st.session_state["df_modelo_estoque"] = df_modelo.copy()
            st.session_state["modelo_estoque_nome"] = getattr(arquivo, "name", "modelo_estoque")
            log_debug(
                f"Modelo de estoque carregado: {getattr(arquivo, 'name', 'arquivo')} "
                f"({len(df_modelo)} linha(s), {len(df_modelo.columns)} coluna(s))"
            )

        return True

    except Exception as e:
        st.error("Erro ao carregar o modelo Bling.")
        log_debug(f"Erro ao carregar modelo Bling ({tipo_modelo}): {e}", "ERRO")
        return False


def _obter_modelo_ativo():
    tipo = st.session_state.get("tipo_operacao_bling")
    if tipo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def _render_modelo_bling(operacao: str) -> None:
    st.markdown("### Modelos Bling")

    if operacao == "Cadastro de Produtos":
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de cadastro",
            type=["xlsx", "xls", "xlsm", "xlsb", "csv"],
            key="modelo_cadastro",
        )

        if arquivo_modelo is not None:
            _carregar_modelo_bling(arquivo_modelo, "cadastro")

        df_modelo = st.session_state.get("df_modelo_cadastro")
        if _safe_df_dados(df_modelo):
            with st.expander("📘 Prévia do modelo de cadastro", expanded=False):
                st.dataframe(df_modelo.head(5), width="stretch")

    else:
        arquivo_modelo = st.file_uploader(
            "Anexar modelo de estoque",
            type=["xlsx", "xls", "xlsm", "xlsb", "csv"],
            key="modelo_estoque",
        )

        if arquivo_modelo is not None:
            _carregar_modelo_bling(arquivo_modelo, "estoque")

        df_modelo = st.session_state.get("df_modelo_estoque")
        if _safe_df_dados(df_modelo):
            with st.expander("📘 Prévia do modelo de estoque", expanded=False):
                st.dataframe(df_modelo.head(5), width="stretch")


def _render_origem_entrada():
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
            key="arquivo_origem_planilha",
        )

        if arquivo:
            try:
                df_origem = ler_planilha_segura(arquivo)
                log_debug(
                    f"Planilha de origem carregada: {getattr(arquivo, 'name', 'arquivo')} "
                    f"({len(df_origem)} linha(s), {len(df_origem.columns)} coluna(s))"
                )
            except Exception as e:
                log_debug(f"Erro ao ler planilha de origem: {e}", "ERRO")
                st.error("Não foi possível ler a planilha enviada.")
                return None

    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception as e:
            log_debug(f"Erro na origem por site: {e}", "ERRO")
            st.error("Erro ao buscar dados do site.")
            return None

    elif origem == "XML":
        st.info("XML em construção")
        return None

    return df_origem


def _render_precificacao(df_base):
    st.markdown("### Precificação")

    if not _safe_df_dados(df_base):
        return

    colunas = list(df_base.columns)

    if not colunas:
        return

    coluna_preco_default = 0
    candidatos = [
        "preco_custo",
        "preço_custo",
        "custo",
        "valor_custo",
        "preco",
        "preço",
        "valor",
    ]

    colunas_lower = [str(c).strip().lower() for c in colunas]
    for candidato in candidatos:
        if candidato in colunas_lower:
            coluna_preco_default = colunas_lower.index(candidato)
            break

    coluna_preco = st.selectbox(
        "Selecione a coluna de PREÇO DE CUSTO",
        options=colunas,
        index=coluna_preco_default,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Margem (%)", min_value=0.0, key="margem_lucro")
        st.number_input("Impostos (%)", min_value=0.0, key="perc_impostos")

    with col2:
        st.number_input("Custo fixo", min_value=0.0, key="custo_fixo")
        st.number_input("Taxa extra (%)", min_value=0.0, key="taxa_extra")

    recalcular = st.button(
        "💲 Aplicar precificação",
        use_container_width=True,
        key="btn_aplicar_precificacao",
    )

    if recalcular:
        try:
            df_precificado = _aplicar_precificacao_com_fallback(df_base, coluna_preco)

            if _safe_df_dados(df_precificado):
                st.session_state["df_precificado"] = df_precificado.copy()
                st.session_state["df_saida"] = df_precificado.copy()
                st.session_state["df_final"] = df_precificado.copy()
                st.session_state["bloquear_campos_auto"] = {"preco": True}

                log_debug(
                    f"Precificação aplicada com sucesso usando a coluna '{coluna_preco}'"
                )

        except Exception as e:
            log_debug(f"Erro na precificação: {e}", "ERRO")
            st.error("Erro ao aplicar a precificação.")

    df_preview_precificacao = st.session_state.get("df_precificado")
    if _safe_df_dados(df_preview_precificacao):
        with st.expander("👁️ Prévia da precificação", expanded=False):
            st.dataframe(df_preview_precificacao.head(10), width="stretch")


def render_origem_dados() -> None:
    etapa_atual = st.session_state.get("etapa_origem")

    if etapa_atual in ["mapeamento", "final"]:
        return

    st.subheader("Origem dos dados")

    operacao = st.radio(
        "Selecione a operação",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
    )

    if operacao == "Cadastro de Produtos":
        st.session_state["tipo_operacao_bling"] = "cadastro"
    else:
        st.session_state["tipo_operacao_bling"] = "estoque"

    _render_modelo_bling(operacao)

    df_origem = _render_origem_entrada()

    if not _safe_df_dados(df_origem):
        return

    st.session_state["df_origem"] = df_origem.copy()

    # garante fluxo mesmo antes da precificação
    if not _safe_df_dados(st.session_state.get("df_saida")):
        st.session_state["df_saida"] = df_origem.copy()

    if not _safe_df_dados(st.session_state.get("df_final")):
        st.session_state["df_final"] = st.session_state["df_saida"].copy()

    with st.expander("📄 Prévia da planilha do fornecedor", expanded=False):
        st.dataframe(df_origem.head(10), width="stretch")

    _render_precificacao(df_origem)

    # se ainda não houve precificação, segue com df_origem
    df_saida = st.session_state.get("df_saida")
    if not _safe_df_dados(df_saida):
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()

    modelo_ativo = _obter_modelo_ativo()

    if not _safe_df_dados(modelo_ativo):
        st.warning("Anexe o modelo oficial do Bling antes de continuar para o mapeamento.")
        return

    if st.button("➡️ Continuar para mapeamento", use_container_width=True):
        try:
            st.session_state["df_final"] = df_saida.copy()
            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["etapa_origem"] = "mapeamento"
            log_debug("Fluxo enviado para etapa de mapeamento")
            st.rerun()
        except Exception as e:
            log_debug(f"Erro ao continuar para o mapeamento: {e}", "ERRO")
            st.error("Não foi possível seguir para o mapeamento.")
