from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site


# ==========================================================
# HELPERS
# ==========================================================
def _safe_df(df):
    try:
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def _render_preview(df) -> None:
    try:
        st.dataframe(
            df.head(10),
            use_container_width=True,
            height=260,
        )
    except Exception as e:
        log_debug(f"Erro ao renderizar preview: {e}", "ERROR")
        st.dataframe(df.head(10), use_container_width=True)


def _reset_fluxo_origem() -> None:
    for chave in [
        "df_origem",
        "df_final",
        "etapa_origem",
        "operacao_tipo",
        "operacao_label",
        "mapeamento_origem",
        "mapeamento_origem_confirmado",
        "mapeamento_origem_hash",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


def _salvar_operacao_escolhida(valor: str) -> None:
    st.session_state["operacao_tipo"] = valor
    if valor == "cadastro":
        st.session_state["operacao_label"] = "Cadastro / atualização de produtos"
    elif valor == "estoque":
        st.session_state["operacao_label"] = "Atualização de estoque"
    else:
        st.session_state["operacao_label"] = ""


# ==========================================================
# MAIN UI
# ==========================================================
def render_origem_dados() -> None:
    # se já estiver no mapeamento, não redesenha o bloco de origem
    etapa_origem = st.session_state.get("etapa_origem", "upload")
    if etapa_origem != "upload":
        return

    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    # =========================
    # PLANILHA
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            log_debug("Iniciando leitura da planilha")
            df_origem = ler_planilha_segura(arquivo)

            if _safe_df(df_origem) is None:
                log_debug("Erro planilha", "ERROR")
                st.error("Erro ao ler planilha")
                return

    # =========================
    # XML
    # =========================
    elif origem == "XML":
        st.warning("XML ainda em construção")
        return

    # =========================
    # SITE
    # =========================
    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception as e:
            log_debug(f"Erro na origem por site: {e}", "ERROR")
            st.error("Erro ao buscar dados do site")
            return

    if _safe_df(df_origem) is None:
        return

    st.session_state["df_origem"] = df_origem

    # ==========================================================
    # PREVIEW
    # ==========================================================
    st.divider()
    st.subheader("Pré-visualização dos dados")

    try:
        _render_preview(df_origem)
        st.success(f"{len(df_origem)} registros carregados")
    except Exception as e:
        log_debug(f"Erro ao gerar preview: {e}", "ERROR")
        st.error("Erro ao gerar preview")
        return

    # ==========================================================
    # FLUXO ORIGINAL APÓS ANEXAR PLANILHA
    # ==========================================================
    st.divider()
    st.subheader("Selecione a operação antes de tudo")

    valor_atual = st.session_state.get("operacao_tipo", "cadastro")

    opcoes = {
        "Cadastro / atualização de produtos": "cadastro",
        "Atualização de estoque": "estoque",
    }

    labels = list(opcoes.keys())
    indice_padrao = 0 if valor_atual != "estoque" else 1

    escolha_label = st.radio(
        "O que será feito?",
        options=labels,
        index=indice_padrao,
        key="operacao_radio_fluxo",
    )

    escolha_valor = opcoes[escolha_label]
    _salvar_operacao_escolhida(escolha_valor)

    if escolha_valor == "cadastro":
        st.info("Fluxo selecionado: Cadastro / atualização de produtos")
    else:
        st.info("Fluxo selecionado: Atualização de estoque")

    # ==========================================================
    # AÇÕES
    # ==========================================================
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "➡️ Continuar para mapeamento",
            use_container_width=True,
            key="btn_continuar_mapeamento",
        ):
            try:
                st.session_state["df_final"] = df_origem.copy()
                st.session_state["etapa_origem"] = "mapeamento"
                log_debug(
                    f"Fluxo liberado para mapeamento | operação={st.session_state.get('operacao_tipo', '')}",
                    "SUCCESS",
                )
                st.rerun()
            except Exception as e:
                log_debug(f"Erro ao preparar mapeamento: {e}", "ERROR")
                st.error("Erro ao avançar para o mapeamento")

    with col2:
        if st.button(
            "🧹 Limpar dados carregados",
            use_container_width=True,
            key="btn_limpar_origem",
        ):
            _reset_fluxo_origem()
            log_debug("Fluxo de origem resetado", "INFO")
            st.rerun()
