from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_operacao,
    controlar_troca_origem,
    safe_df_dados,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_precificacao import render_precificacao
from bling_app_zero.ui.origem_dados_uploads import (
    render_modelo_bling,
    render_origem_entrada,
)
from bling_app_zero.ui.origem_dados_validacao import (
    obter_modelo_ativo,
    validar_antes_mapeamento,
)


def _df_preview_seguro(df: pd.DataFrame | None) -> pd.DataFrame | None:
    try:
        if not safe_df_dados(df):
            return df

        df_preview = df.copy()

        for col in df_preview.columns:
            try:
                df_preview[col] = df_preview[col].apply(
                    lambda x: "" if pd.isna(x) else str(x)
                )
            except Exception:
                try:
                    df_preview[col] = df_preview[col].astype(str)
                except Exception:
                    pass

        df_preview = df_preview.replace(
            {
                "nan": "",
                "None": "",
                "<NA>": "",
                "NaT": "",
            }
        )

        return df_preview
    except Exception:
        return df


def _sincronizar_df_saida_base(df_origem: pd.DataFrame) -> pd.DataFrame:
    """
    Garante uma base de saída estável sem quebrar o fluxo.
    Se a precificação já tiver gerado df_saida em session_state, respeita.
    Caso contrário, cria a partir da origem.
    """
    try:
        df_saida_state = st.session_state.get("df_saida")

        if safe_df_dados(df_saida_state):
            df_saida = df_saida_state.copy()
        else:
            df_saida = df_origem.copy()
            st.session_state["df_saida"] = df_saida.copy()

        st.session_state["df_final"] = df_saida.copy()
        return df_saida
    except Exception:
        df_saida = df_origem.copy()
        st.session_state["df_saida"] = df_saida.copy()
        st.session_state["df_final"] = df_saida.copy()
        return df_saida


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

    controlar_troca_operacao(operacao, log_debug)

    if operacao == "Cadastro de Produtos":
        st.session_state["tipo_operacao_bling"] = "cadastro"
    else:
        st.session_state["tipo_operacao_bling"] = "estoque"

    # 1) Primeiro o modelo oficial do Bling
    render_modelo_bling(operacao)

    # 2) Depois a origem dos dados
    df_origem = render_origem_entrada(
        lambda origem: controlar_troca_origem(origem, log_debug)
    )

    if not safe_df_dados(df_origem):
        st.info("Selecione a origem e carregue os dados para continuar.")
        return

    sincronizar_estado_com_origem(df_origem, log_debug)

    with st.expander("Prévia da planilha do fornecedor", expanded=False):
        try:
            df_preview = _df_preview_seguro(df_origem)
            if safe_df_dados(df_preview):
                st.dataframe(
                    df_preview.head(10),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Não há dados válidos para pré-visualização.")
        except Exception as e:
            log_debug(
                f"Erro ao renderizar prévia da planilha do fornecedor: {e}",
                "ERRO",
            )
            st.warning("Não foi possível exibir a prévia completa desta origem.")
            try:
                st.write(_df_preview_seguro(df_origem).head(10))
            except Exception:
                pass

    # 3) Precificação entra antes do mapeamento
    render_precificacao(df_origem)

    # 4) Após a precificação, sempre reconsultar df_saida da sessão
    df_saida = _sincronizar_df_saida_base(df_origem)

    modelo_ativo = obter_modelo_ativo()
    modelo_ok = safe_df_dados(modelo_ativo)

    if not modelo_ok:
        st.warning("Anexe o modelo oficial do Bling antes de continuar para o mapeamento.")

    continuar_desabilitado = not modelo_ok

    if st.button(
        "➡️ Continuar para mapeamento",
        use_container_width=True,
        key="btn_continuar_mapeamento",
        disabled=continuar_desabilitado,
    ):
        try:
            valido, erros = validar_antes_mapeamento()

            if not valido:
                for erro in erros:
                    st.warning(erro)
                return

            st.session_state["df_saida"] = df_saida.copy()
            st.session_state["df_final"] = df_saida.copy()
            st.session_state["etapa_origem"] = "mapeamento"

            log_debug("Fluxo enviado para etapa de mapeamento")
            st.rerun()
        except Exception as e:
            log_debug(f"Erro ao continuar para o mapeamento: {e}", "ERRO")
            st.error("Não foi possível seguir para o mapeamento.")
