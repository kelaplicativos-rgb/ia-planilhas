
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_state, save_agent_state
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    dataframe_para_csv_bytes,
    log_debug,
    render_debug_panel,
    render_resumo_fluxo,
    safe_df_dados,
    sincronizar_etapa_global,
    validar_df_para_download,
)


def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _safe_bool(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return False
    return _safe_str(valor).lower() in {"1", "true", "sim", "yes", "on"}


def _debug_habilitado() -> bool:
    return any(
        [
            _safe_bool(st.session_state.get("modo_debug")),
            _safe_bool(st.session_state.get("debug")),
            _safe_bool(st.session_state.get("debug_ia")),
            _safe_bool(st.session_state.get("mostrar_debug")),
            _safe_bool(st.session_state.get("mostrar_debug_ia")),
        ]
    )


def _get_df_final_fluxo() -> pd.DataFrame | None:
    """
    Corrige o problema principal do fluxo novo:
    preview final não pode mais cair em df_origem.
    Só aceita dataframes realmente transformados para o modelo final.
    """
    for chave in [
        "df_final",
        "df_saida",
        "df_mapeado",
        "df_precificado",
        "df_calc_precificado",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


def _nome_arquivo_saida(tipo_operacao_bling: str) -> str:
    tipo = _safe_str(tipo_operacao_bling).lower()
    if tipo == "estoque":
        return "bling_export_estoque.csv"
    return "bling_export_cadastro.csv"


def _mostrar_alertas_validacao(erros: list[str]) -> None:
    if not erros:
        return
    st.error("A planilha final ainda tem pendências.")
    for erro in erros:
        texto = _safe_str(erro)
        if texto:
            st.caption(f"• {texto}")


def _render_resumo_saida(df_blindado: pd.DataFrame, valido: bool) -> None:
    st.markdown("#### Resumo da saída")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Linhas", len(df_blindado))
    with col2:
        st.metric("Colunas", len(df_blindado.columns))
    with col3:
        st.metric("Status", "Válido" if valido else "Pendente")


def _render_preview_tabela(df_blindado: pd.DataFrame) -> None:
    st.markdown("#### Estrutura final")
    with st.expander("Visualizar planilha final", expanded=False):
        st.dataframe(df_blindado.head(200), use_container_width=True)


def render_preview_final() -> None:
    st.markdown("### Preview final")

    state = get_agent_state()

    tipo_operacao_bling = _safe_str(
        st.session_state.get("tipo_operacao")
        or st.session_state.get("operacao")
        or state.operacao
        or "cadastro"
    ).lower()

    deposito_nome = _safe_str(
        st.session_state.get("deposito_nome")
        or state.deposito_nome
    )

    render_resumo_fluxo()

    df_base = _get_df_final_fluxo()
    if not safe_df_dados(df_base):
        st.warning(
            "Ainda não existe planilha final pronta. "
            "O fluxo precisa gerar df_final, df_saida, df_mapeado ou df_precificado antes do download."
        )
        if _debug_habilitado():
            render_debug_panel("Debug do preview final")
        return

    df_blindado = blindar_df_para_bling(
        df=df_base,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )

    valido, erros = validar_df_para_download(
        df=df_blindado,
        tipo_operacao_bling=tipo_operacao_bling,
    )

    st.session_state["df_final"] = df_blindado.copy()
    state.df_final_key = "df_final"
    state.operacao = tipo_operacao_bling
    state.deposito_nome = deposito_nome
    state.etapa_atual = "final"
    state.status_execucao = "final_pronto" if valido else "validacao_pendente"
    state.simulacao_aprovada = bool(valido)
    save_agent_state(state)

    _render_resumo_saida(df_blindado, valido)
    _mostrar_alertas_validacao(erros)
    _render_preview_tabela(df_blindado)

    csv_bytes = dataframe_para_csv_bytes(df_blindado)
    st.download_button(
        "Baixar planilha final",
        data=csv_bytes,
        file_name=_nome_arquivo_saida(tipo_operacao_bling),
        mime="text/csv",
        use_container_width=True,
        key="download_preview_final_bling",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Voltar para mapeamento", use_container_width=True):
            sincronizar_etapa_global("mapeamento")
            log_debug("[PREVIEW_FINAL] retorno manual para mapeamento.", "INFO")
            st.rerun()

    with col2:
        if st.button("Revalidar saída final", use_container_width=True):
            log_debug("[PREVIEW_FINAL] revalidação manual da saída final.", "INFO")
            st.rerun()

    if _debug_habilitado():
        render_debug_panel("Debug do preview final")
        
