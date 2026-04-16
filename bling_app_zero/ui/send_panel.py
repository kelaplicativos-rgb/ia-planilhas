
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.agent.agent_memory import get_agent_state
from bling_app_zero.ui.app_helpers import (
    log_debug,
    render_debug_panel,
    safe_df_dados,
    sincronizar_etapa_global,
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


def _obter_df_referencia() -> pd.DataFrame | None:
    state = get_agent_state()

    chaves_prioritarias = [
        _safe_str(getattr(state, "df_final_key", "")),
        _safe_str(getattr(state, "df_mapeado_key", "")),
        _safe_str(getattr(state, "df_normalizado_key", "")),
        _safe_str(getattr(state, "df_origem_key", "")),
        "df_final",
        "df_saida",
        "df_mapeado",
        "df_normalizado",
        "df_origem",
    ]

    for chave in chaves_prioritarias:
        if not chave:
            continue
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()

    return None


def _render_resumo_contexto() -> None:
    state = get_agent_state()
    df_ref = _obter_df_referencia()

    st.markdown("#### Resumo da etapa")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Etapa", _safe_str(getattr(state, "etapa_atual", "")) or "-")

    with col2:
        st.metric("Status", _safe_str(getattr(state, "status_execucao", "")) or "-")

    with col3:
        st.metric("Operação", _safe_str(getattr(state, "operacao", "")) or "-")

    with col4:
        st.metric("Linhas disponíveis", len(df_ref) if safe_df_dados(df_ref) else 0)


def _render_debug_send_panel() -> None:
    if not _debug_habilitado():
        return

    state = get_agent_state()
    df_ref = _obter_df_referencia()

    with st.expander("Debug do painel de envio", expanded=False):
        st.caption("Este painel está em modo passivo e não altera o fluxo principal.")
        st.write(
            {
                "etapa_atual": _safe_str(getattr(state, "etapa_atual", "")),
                "status_execucao": _safe_str(getattr(state, "status_execucao", "")),
                "operacao": _safe_str(getattr(state, "operacao", "")),
                "df_final_key": _safe_str(getattr(state, "df_final_key", "")),
                "df_mapeado_key": _safe_str(getattr(state, "df_mapeado_key", "")),
                "df_normalizado_key": _safe_str(getattr(state, "df_normalizado_key", "")),
                "df_origem_key": _safe_str(getattr(state, "df_origem_key", "")),
            }
        )

        if safe_df_dados(df_ref):
            st.caption("Prévia da base encontrada para referência")
            st.dataframe(df_ref.head(30), use_container_width=True)

        render_debug_panel("Logs do sistema")


# ============================================================
# RENDER
# ============================================================


def render_send_panel(*args, **kwargs) -> None:
    st.markdown("### Envio")
    st.caption(
        "O envio automático para o Bling está fora do fluxo principal desta versão. "
        "A saída oficial continua sendo a planilha final validada para download."
    )

    _render_resumo_contexto()

    st.info(
        "Para evitar interferência no fluxo principal, esta etapa está somente em modo informativo. "
        "Ela não altera o DataFrame final, não sobrescreve a planilha validada e não reabre conexão com o Bling."
    )

    st.markdown("#### Como seguir")
    st.caption("• Use o preview final para revisar a estrutura exportável")
    st.caption("• Baixe a planilha final validada em CSV")
    st.caption("• Faça a importação no Bling pelo processo externo do seu ambiente")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar para preview final", use_container_width=True, key="send_back_final"):
            sincronizar_etapa_global("final")
            log_debug("Usuário retornou do send_panel para o preview final", "INFO")
            st.rerun()

    with col2:
        if st.button("⬅️ Voltar para mapeamento", use_container_width=True, key="send_back_mapping"):
            sincronizar_etapa_global("mapeamento")
            log_debug("Usuário retornou do send_panel para o mapeamento", "INFO")
            st.rerun()

    _render_debug_send_panel()

    log_debug("Painel de envio renderizado em modo passivo", "INFO")


def render_bling_primeiro_acesso(*args, **kwargs) -> None:
    st.markdown("### Conexão com Bling")
    st.caption(
        "A conexão direta com o Bling foi removida deste fluxo principal nesta versão."
    )

    st.info(
        "Este bloco foi mantido apenas por compatibilidade com imports antigos do projeto. "
        "Ele não inicia OAuth, não salva token e não interfere no fluxo atual."
    )

    if st.button("⬅️ Voltar para origem", use_container_width=True, key="bling_primeiro_acesso_voltar"):
        sincronizar_etapa_global("origem")
        log_debug("Usuário voltou da tela de primeiro acesso do Bling para origem", "INFO")
        st.rerun()

    _render_debug_send_panel()
    
