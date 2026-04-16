
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_state, save_agent_state
from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    dataframe_para_csv_bytes,
    garantir_colunas_modelo,
    log_debug,
    render_debug_panel,
    render_resumo_fluxo,
    safe_df_dados,
    sincronizar_etapa_global,
    validar_df_para_download,
)


# ============================================================
# HELPERS
# ============================================================
def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _get_df_by_key(chave: str) -> pd.DataFrame | None:
    if not chave:
        return None
    df = st.session_state.get(chave)
    if safe_df_dados(df):
        return df.copy()
    return None


def _get_df_final_fluxo() -> pd.DataFrame | None:
    """
    Prioriza o estado do novo agente.
    Só depois cai nas chaves históricas do fluxo para evitar tela vazia
    durante a transição.
    """
    state = get_agent_state()

    for chave in [
        state.df_final_key,
        state.df_mapeado_key,
        state.df_normalizado_key,
        state.df_origem_key,
        "df_final",
        "df_mapeado",
        "df_normalizado",
        "df_origem",
    ]:
        df = _get_df_by_key(_safe_str(chave))
        if safe_df_dados(df):
            return df

    return None


def _get_tipo_operacao() -> str:
    state = get_agent_state()
    tipo = _safe_str(state.operacao or st.session_state.get("tipo_operacao_bling") or st.session_state.get("tipo_operacao") or "cadastro").lower()
    return tipo if tipo in {"cadastro", "estoque"} else "cadastro"


def _get_deposito_nome() -> str:
    state = get_agent_state()
    return _safe_str(state.deposito_nome or st.session_state.get("deposito_nome"))


def _nome_arquivo_saida(tipo_operacao_bling: str) -> str:
    if _safe_str(tipo_operacao_bling).lower() == "estoque":
        return "bling_export_estoque.csv"
    return "bling_export_cadastro.csv"


def _mostrar_alertas_validacao(erros: list[str]) -> None:
    if not erros:
        return
    st.error("A planilha final ainda tem pendências.")
    for erro in erros:
        st.caption(f"• {erro}")


def _salvar_estado_final(df_blindado: pd.DataFrame, valido: bool, erros: list[str]) -> None:
    st.session_state["df_final"] = df_blindado.copy()
    st.session_state["df_saida"] = df_blindado.copy()

    state = get_agent_state()
    state.df_final_key = "df_final"
    state.simulacao_aprovada = bool(valido)
    state.etapa_atual = "final" if valido else "validacao"
    state.status_execucao = "final_pronto" if valido else "revisao_final"
    state.clear_erros()
    state.clear_avisos()

    for erro in erros:
        state.add_erro(erro)

    state.add_log(f"Preview final atualizado. valido={valido} linhas={len(df_blindado)}")
    save_agent_state(state)


def _render_resumo_agente_final() -> None:
    state = get_agent_state()

    with st.expander("Estado do agente no preview final", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Etapa", _safe_str(state.etapa_atual) or "-")
        with col2:
            st.metric("Status", _safe_str(state.status_execucao) or "-")
        with col3:
            st.metric("Operação", _safe_str(state.operacao) or "-")
        with col4:
            st.metric("Simulação", "Aprovada" if state.simulacao_aprovada else "Pendente")

        if state.erros:
            for erro in state.erros:
                st.error(erro)

        if state.avisos:
            for aviso in state.avisos:
                st.warning(aviso)


# ============================================================
# RENDER
# ============================================================
def render_preview_final() -> None:
    st.markdown("### Preview final")
    st.caption("Revise a planilha final, valide os campos obrigatórios e faça o download para importar no Bling.")

    render_resumo_fluxo()

    df_base = _get_df_final_fluxo()
    tipo_operacao_bling = _get_tipo_operacao()
    deposito_nome = _get_deposito_nome()

    if not safe_df_dados(df_base):
        st.warning("Nenhum dado disponível para gerar o preview final.")
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True):
            sincronizar_etapa_global("mapeamento")
            st.rerun()
        return

    df_blindado = blindar_df_para_bling(
        df=df_base,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )
    df_blindado = garantir_colunas_modelo(df_blindado, tipo_operacao_bling)

    valido, erros = validar_df_para_download(df_blindado, tipo_operacao_bling)
    _salvar_estado_final(df_blindado, valido, erros)

    st.markdown("#### Estrutura final")
    st.dataframe(df_blindado.head(100), use_container_width=True)

    st.markdown("#### Resumo da saída")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Linhas", len(df_blindado))
    with col2:
        st.metric("Colunas", len(df_blindado.columns))
    with col3:
        st.metric("Status", "Válido" if valido else "Pendente")
    with col4:
        st.metric("Simulação", "Aprovada" if valido else "Revisar")

    if not valido:
        _mostrar_alertas_validacao(erros)
    else:
        st.success("Planilha final validada com sucesso para exportação.")

    csv_bytes = dataframe_para_csv_bytes(df_blindado)
    nome_arquivo = _nome_arquivo_saida(tipo_operacao_bling)

    with st.expander("Preview completo da saída", expanded=False):
        st.dataframe(df_blindado, use_container_width=True)

    _render_resumo_agente_final()

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            sincronizar_etapa_global("mapeamento")
            st.rerun()

    with col2:
        st.download_button(
            "⬇️ Baixar planilha final",
            data=csv_bytes,
            file_name=nome_arquivo,
            mime="text/csv",
            use_container_width=True,
            disabled=not valido,
        )

    render_debug_panel()
    log_debug("Preview final renderizado pelo fluxo do agente", "INFO")


