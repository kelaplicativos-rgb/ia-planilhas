
from __future__ import annotations

import pandas as pd
import streamlit as st

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


def _safe_bool(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if valor is None:
        return False
    texto = _safe_str(valor).lower()
    return texto in {"1", "true", "sim", "yes", "on"}


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
    for chave in [
        "df_final",
        "df_saida",
        "df_mapeado",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
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
        st.dataframe(df_blindado.head(100), use_container_width=True)


def _render_acoes_finais(
    *,
    csv_bytes: bytes,
    nome_arquivo: str,
    valido: bool,
) -> None:
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True):
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


def _render_debug_final(df_base: pd.DataFrame, df_blindado: pd.DataFrame) -> None:
    if not _debug_habilitado():
        return

    with st.expander("Debug final", expanded=False):
        st.caption("Base original usada no preview final")
        st.dataframe(df_base.head(30), use_container_width=True)

        st.caption("Base blindada para exportação")
        st.dataframe(df_blindado.head(30), use_container_width=True)

        render_debug_panel()


# ============================================================
# RENDER
# ============================================================


def render_preview_final() -> None:
    st.markdown("### Preview final")
    st.caption(
        "Revise a planilha final, valide os campos obrigatórios e faça o download para importar no Bling."
    )

    render_resumo_fluxo()

    df_base = _get_df_final_fluxo()
    tipo_operacao_bling = st.session_state.get("tipo_operacao_bling", "cadastro")
    deposito_nome = st.session_state.get("deposito_nome", "")

    if not safe_df_dados(df_base):
        st.warning("Nenhum dado disponível para gerar o preview final.")

        if st.button("⬅️ Voltar para mapeamento", use_container_width=True):
            sincronizar_etapa_global("mapeamento")
            st.rerun()

        log_debug("Preview final sem dados disponíveis", "WARNING")
        return

    df_blindado = blindar_df_para_bling(
        df=df_base,
        tipo_operacao_bling=tipo_operacao_bling,
        deposito_nome=deposito_nome,
    )
    df_blindado = garantir_colunas_modelo(df_blindado, tipo_operacao_bling)

    st.session_state["df_final"] = df_blindado.copy()
    st.session_state["df_saida"] = df_blindado.copy()

    valido, erros = validar_df_para_download(df_blindado, tipo_operacao_bling)

    _render_preview_tabela(df_blindado)
    _render_resumo_saida(df_blindado, valido)

    if not valido:
        _mostrar_alertas_validacao(erros)
    else:
        st.success("Planilha final validada com sucesso para exportação.")

    csv_bytes = dataframe_para_csv_bytes(df_blindado)
    nome_arquivo = _nome_arquivo_saida(tipo_operacao_bling)

    _render_acoes_finais(
        csv_bytes=csv_bytes,
        nome_arquivo=nome_arquivo,
        valido=valido,
    )

    _render_debug_final(df_base, df_blindado)

    log_debug("Preview final renderizado", "INFO")
    
