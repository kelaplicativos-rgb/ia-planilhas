from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    blindar_df_para_download,
    exportar_csv_bytes,
    gerar_nome_arquivo_download,
    log_debug,
    validar_campos_obrigatorios,
)


def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _get_df_fluxo() -> pd.DataFrame | None:
    """
    Ordem de prioridade do fluxo final:
    1) df_final
    2) df_saida
    3) df_precificado
    4) df_calc_precificado
    5) df_origem
    """
    for chave in [
        "df_final",
        "df_saida",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            try:
                return df.copy()
            except Exception:
                return df
    return None


def _normalizar_validacao(resultado_validacao) -> bool:
    try:
        if isinstance(resultado_validacao, bool):
            return resultado_validacao
        if resultado_validacao is None:
            return True
        if isinstance(resultado_validacao, dict):
            return len(resultado_validacao) == 0
        if isinstance(resultado_validacao, (list, tuple, set)):
            return len(resultado_validacao) == 0
        return bool(resultado_validacao)
    except Exception:
        return False


def _sincronizar_df_final(df_download: pd.DataFrame) -> None:
    try:
        st.session_state["df_final"] = df_download.copy()
    except Exception:
        st.session_state["df_final"] = df_download

    try:
        st.session_state["df_saida"] = df_download.copy()
    except Exception:
        st.session_state["df_saida"] = df_download


def render_preview_final() -> None:
    st.subheader("Preview final")

    df_fluxo = _get_df_fluxo()
    if not _safe_df(df_fluxo):
        st.warning("Nenhum dado disponível para o preview final.")
        log_debug("Preview final sem DataFrame disponível", "ERROR")
        return

    try:
        log_debug(
            f"Preview final carregado com {len(df_fluxo)} linha(s) e {len(df_fluxo.columns)} coluna(s)",
            "INFO",
        )
    except Exception:
        pass

    try:
        df_download = blindar_df_para_download(df_fluxo.copy())
    except Exception as e:
        log_debug(f"Erro na blindagem extra do preview final: {e}", "ERROR")
        try:
            df_download = df_fluxo.copy()
        except Exception:
            df_download = df_fluxo

    if not _safe_df(df_download):
        st.error("Não foi possível preparar os dados finais para visualização.")
        log_debug("Preview final ficou inválido após blindagem", "ERROR")
        return

    _sincronizar_df_final(df_download)

    with st.expander("Ver dados finais", expanded=False):
        st.dataframe(df_download.head(20), use_container_width=True)

    try:
        validacao_ok = _normalizar_validacao(validar_campos_obrigatorios(df_download))
    except Exception as e:
        log_debug(f"Erro na validação de campos obrigatórios: {e}", "ERROR")
        validacao_ok = False

    if not validacao_ok:
        st.error("Preencha os campos obrigatórios antes do download.")
        return

    try:
        # Blindagem final extra imediatamente antes do download
        df_download = blindar_df_para_download(df_download.copy())
        _sincronizar_df_final(df_download)
    except Exception as e:
        log_debug(f"Erro na segunda blindagem do download final: {e}", "ERROR")

    try:
        csv_bytes = exportar_csv_bytes(df_download)
    except Exception as e:
        log_debug(f"Erro ao gerar CSV final: {e}", "ERROR")
        st.error("Não foi possível gerar a planilha final em CSV.")
        return

    if not csv_bytes:
        st.error("Não foi possível gerar a planilha final em CSV.")
        log_debug("CSV final vazio no preview_final.py", "ERROR")
        return

    st.download_button(
        "⬇️ Baixar planilha final",
        data=csv_bytes,
        file_name=gerar_nome_arquivo_download(),
        mime="text/csv",
        use_container_width=True,
        key="btn_download_preview_final_csv",
    )

    # Mantém apenas ação interna de atualização de preview.
    # Navegação entre etapas fica centralizada no app.py
    if st.button(
        "Atualizar preview",
        use_container_width=True,
        key="btn_atualizar_preview_final",
    ):
        _sincronizar_df_final(df_download)
        st.rerun()
