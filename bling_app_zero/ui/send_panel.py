from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import log_debug


# ==========================================================
# HELPERS
# ==========================================================
def _safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def _safe_copy_df(df):
    try:
        return df.copy()
    except Exception:
        return df


def _get_df_base_envio() -> pd.DataFrame | None:
    """
    EXTREMAMENTE IMPORTANTE:
    Nunca modificar df_final ou df_saida direto.
    Sempre trabalhar com cópia isolada.
    """
    for chave in ["df_final", "df_saida"]:
        df = st.session_state.get(chave)
        if _safe_df(df):
            log_debug(f"[SEND_PANEL] base de envio carregada de '{chave}'", "INFO")
            return _safe_copy_df(df)
    return None


def _persistir_df_envio(df_envio: pd.DataFrame) -> None:
    """
    Salva apenas para envio — NÃO altera df_final/df_saida
    """
    try:
        st.session_state["df_envio"] = df_envio.copy()
    except Exception:
        st.session_state["df_envio"] = df_envio


def _get_etapa_atual() -> str:
    """
    Lê a etapa atual do fluxo de forma tolerante.
    Isso blinda o botão de conexão para aparecer apenas no início.
    """
    for chave in ("etapa_origem", "etapa", "etapa_fluxo"):
        valor = str(st.session_state.get(chave) or "").strip().lower()
        if valor:
            return valor
    return ""


# ==========================================================
# UI
# ==========================================================
def render_send_panel() -> None:
    st.subheader("Envio para o Bling")

    df_base = _get_df_base_envio()
    if not _safe_df(df_base):
        st.warning("Nenhum dado disponível para envio.")
        log_debug("[SEND_PANEL] nenhum DataFrame disponível para envio.", "ERROR")
        return

    # CRIA CÓPIA ISOLADA PARA ENVIO
    df_envio = _safe_copy_df(df_base)
    _persistir_df_envio(df_envio)

    st.caption(
        "Os dados abaixo são apenas para envio. "
        "A conexão com o Bling pertence ao início do fluxo e o download não será afetado."
    )

    with st.expander("Visualizar dados de envio", expanded=False):
        st.dataframe(df_envio.head(20), use_container_width=True)

    st.markdown("---")

    # ==========================================================
    # SIMULAÇÃO DE ENVIO (placeholder API)
    # ==========================================================
    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "📤 Enviar para Bling",
            use_container_width=True,
            type="primary",
        ):
            try:
                # Aqui entra futura integração com API
                total = len(df_envio)
                log_debug(
                    f"[SEND_PANEL] envio simulado iniciado com {total} registro(s).",
                    "INFO",
                )
                st.success(f"Envio simulado com sucesso ({total} registros).")
            except Exception as e:
                log_debug(f"[SEND_PANEL] erro no envio: {e}", "ERROR")
                st.error("Erro ao enviar para o Bling.")

    with col2:
        if st.button(
            "🔄 Atualizar dados de envio",
            use_container_width=True,
        ):
            df_base = _get_df_base_envio()
            if _safe_df(df_base):
                _persistir_df_envio(df_base)
                log_debug("[SEND_PANEL] dados de envio atualizados.", "INFO")
                st.rerun()

    st.markdown("---")
    st.info(
        "⚠️ O envio utiliza uma cópia dos dados. "
        "O download final permanece intacto."
    )


# ==========================================================
# PRIMEIRO ACESSO
# ==========================================================
def render_bling_primeiro_acesso(
    on_skip=None,
    on_continue=None,
) -> None:
    """
    Tela de conexão do início do fluxo.

    Blindagem:
    - Só renderiza quando a etapa atual for realmente 'conexao'.
    - Se por qualquer motivo essa função for chamada no final/envio,
      ela não mostra novamente a opção de conectar.
    """
    etapa_atual = _get_etapa_atual()
    if etapa_atual and etapa_atual != "conexao":
        log_debug(
            f"[SEND_PANEL] render_bling_primeiro_acesso bloqueado fora da etapa inicial "
            f"(etapa atual: {etapa_atual}).",
            "INFO",
        )
        return

    st.subheader("Conectar ao Bling")
    st.caption(
        "Conecte sua conta Bling para envio automático ou continue sem integração."
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🔗 Conectar com Bling",
            use_container_width=True,
            type="primary",
        ):
            log_debug("[SEND_PANEL] conexão com Bling acionada.", "INFO")
            # Aqui entrará OAuth real
            st.success("Conexão simulada com sucesso.")

            if callable(on_continue):
                on_continue()

    with col2:
        if st.button(
            "➡️ Continuar sem conectar",
            use_container_width=True,
        ):
            log_debug(
                "[SEND_PANEL] usuário optou por continuar sem conexão.",
                "INFO",
            )
            if callable(on_skip):
                on_skip()
                
