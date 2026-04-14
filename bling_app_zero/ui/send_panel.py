from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_auth import BlingAuthManager
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


def _resolver_bling_user_key() -> str:
    for chave in ["bling_user_key", "user_key", "bi"]:
        valor = str(st.session_state.get(chave) or "").strip()
        if valor:
            return valor
    return "default"


def _sanear_estado_bling_invalido(motivo: str = "") -> None:
    if motivo:
        log_debug(f"[SEND_PANEL] limpando estado inválido do Bling: {motivo}", "WARNING")

    st.session_state["bling_conectado"] = False
    st.session_state["bling_conexao_ok"] = False
    st.session_state["bling_connection_checked"] = False
    st.session_state["bling_connection_source"] = ""
    st.session_state["bling_ultimo_status"] = "invalid"

    if motivo:
        st.session_state["bling_connection_message"] = motivo


def _token_bling_valido_real() -> bool:
    try:
        auth = BlingAuthManager(user_key=_resolver_bling_user_key())
        ok, token = auth.get_token()
        token = str(token or "").strip()

        if ok and token:
            st.session_state["bling_conectado"] = True
            st.session_state["bling_conexao_ok"] = True
            st.session_state["bling_connection_checked"] = True
            st.session_state["bling_connection_source"] = "token_real"
            st.session_state["bling_ultimo_status"] = "connected"
            return True

        _sanear_estado_bling_invalido("Sem token real salvo para este usuário.")
        return False
    except Exception as e:
        _sanear_estado_bling_invalido(f"Falha ao validar token real: {e}")
        log_debug(f"[SEND_PANEL] erro ao validar token real: {e}", "ERROR")
        return False


def _get_auth_manager() -> BlingAuthManager:
    return BlingAuthManager(user_key=_resolver_bling_user_key())


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
    """Salva apenas para envio — NÃO altera df_final/df_saida."""
    try:
        st.session_state["df_envio"] = df_envio.copy()
    except Exception:
        st.session_state["df_envio"] = df_envio


def _render_status_conexao() -> None:
    conectado_real = _token_bling_valido_real()
    mensagem = str(st.session_state.get("bling_connection_message") or "").strip()
    ultimo_status = str(st.session_state.get("bling_ultimo_status") or "").strip().lower()

    if conectado_real:
        st.success("✅ Conta Bling conectada com token real válido.")
        return

    if ultimo_status == "error" and mensagem:
        st.error(f"❌ {mensagem}")
        return

    if mensagem:
        st.warning(f"⚠️ {mensagem}")
        return

    st.info("ℹ️ Nenhuma conexão válida encontrada. Conecte com o Bling para liberar o envio real.")


def _render_botao_oauth_same_tab(auth_url: str) -> None:
    auth_url_safe = html.escape(auth_url, quote=True)
    st.markdown(
        f"""
<a
    href="{auth_url_safe}"
    target="_self"
    style="
        display:block;
        width:100%;
        text-align:center;
        padding:0.75rem 1rem;
        border-radius:0.5rem;
        background:#16a34a;
        color:white;
        text-decoration:none;
        font-weight:600;
        margin-bottom:0.25rem;
    "
>
    🔐 Conectar com Bling
</a>
""",
        unsafe_allow_html=True,
    )


def _render_diagnostico_conexao(auth: BlingAuthManager) -> None:
    with st.expander("Diagnóstico da conexão", expanded=False):
        st.write(f"**Usuário OAuth:** `{_resolver_bling_user_key()}`")
        st.write(f"**Configuração carregada:** {'Sim' if auth.is_configured() else 'Não'}")

        debug_redirect = str(st.session_state.get("_bling_debug_redirect_uri") or "").strip()
        debug_auth_url = str(st.session_state.get("_bling_debug_auth_url") or "").strip()
        debug_auth_error = str(st.session_state.get("_bling_debug_auth_error") or "").strip()

        if debug_redirect:
            st.caption("Redirect URI")
            st.code(debug_redirect, language="text")

        if debug_auth_url:
            st.caption("Auth URL")
            st.code(debug_auth_url, language="text")

        if debug_auth_error:
            st.error(debug_auth_error)

        if st.button(
            "🧹 Limpar estado sujo da conexão",
            use_container_width=True,
            key="btn_clear_dirty_bling_state",
        ):
            _sanear_estado_bling_invalido("Estado de conexão limpo manualmente.")
            st.session_state["bling_primeiro_acesso_decidido"] = False
            st.session_state["bling_primeiro_acesso_escolha"] = ""
            st.rerun()


# ==========================================================
# PAINEL DE CONEXÃO INICIAL
# ==========================================================
def render_bling_primeiro_acesso(
    on_skip=None,
    on_continue=None,
) -> None:
    st.subheader("Conectar ao Bling")
    st.caption(
        "Conecte sua conta Bling para envio automático. "
        "Se preferir, você ainda pode seguir sem integração."
    )

    auth = _get_auth_manager()
    conectado_real = _token_bling_valido_real()

    _render_status_conexao()

    col1, col2 = st.columns(2)

    with col1:
        if conectado_real:
            if st.button(
                "✅ Continuar com Bling conectado",
                use_container_width=True,
                type="primary",
                key="btn_continue_bling_connected",
            ):
                st.session_state["bling_primeiro_acesso_decidido"] = True
                st.session_state["bling_primeiro_acesso_escolha"] = "conectado"
                log_debug("[SEND_PANEL] usuário continuou com conexão Bling válida.", "INFO")
                if callable(on_continue):
                    on_continue()
        else:
            if not auth.is_configured():
                st.error("OAuth do Bling não está configurado no secrets.toml.")
                log_debug("[SEND_PANEL] OAuth não configurado para exibir botão de conexão.", "ERROR")
            else:
                auth_url = auth.generate_auth_url()
                if auth_url:
                    st.session_state["_oauth_pending_user_key"] = _resolver_bling_user_key()
                    st.session_state["bling_connection_message"] = "Redirecionando para o login do Bling..."
                    log_debug("[SEND_PANEL] URL OAuth gerada. Login abrirá na mesma aba.", "INFO")
                    _render_botao_oauth_same_tab(auth_url)
                    st.caption(
                        "Ao clicar, o login do Bling abrirá na mesma aba e, ao voltar, "
                        "o sistema seguirá automaticamente."
                    )
                else:
                    st.error("Não foi possível gerar a URL de autorização do Bling.")
                    log_debug("[SEND_PANEL] falha ao gerar auth_url do Bling.", "ERROR")

    with col2:
        if conectado_real:
            if st.button(
                "➡️ Ir para origem",
                use_container_width=True,
                key="btn_go_origem_when_connected",
            ):
                st.session_state["bling_primeiro_acesso_decidido"] = True
                st.session_state["bling_primeiro_acesso_escolha"] = "conectado"
                log_debug("[SEND_PANEL] usuário foi para origem com conexão válida.", "INFO")
                if callable(on_continue):
                    on_continue()
        else:
            with st.expander("Seguir sem conectar agora", expanded=False):
                st.caption(
                    "Use esta opção apenas se quiser trabalhar sem integração Bling nesta etapa."
                )
                if st.button(
                    "➡️ Continuar sem conectar",
                    use_container_width=True,
                    key="btn_continue_without_bling_explicit",
                ):
                    st.session_state["bling_primeiro_acesso_decidido"] = True
                    st.session_state["bling_primeiro_acesso_escolha"] = "sem_conexao"
                    log_debug("[SEND_PANEL] usuário optou por seguir sem travar pela conexão.", "INFO")
                    if callable(on_skip):
                        on_skip()

    if not conectado_real:
        _render_diagnostico_conexao(auth)


# ==========================================================
# PAINEL DE ENVIO
# ==========================================================
def render_send_panel() -> None:
    st.subheader("Envio para o Bling")

    conectado_real = _token_bling_valido_real()
    if conectado_real:
        st.success("✅ Conexão com Bling confirmada por token real.")
    else:
        st.warning(
            "⚠️ Nenhum token real do Bling foi encontrado. "
            "O painel continua disponível, mas o envio seguirá somente como simulação "
            "até a conexão ser válida."
        )

    df_base = _get_df_base_envio()
    if not _safe_df(df_base):
        st.warning("Nenhum dado disponível para envio.")
        log_debug("[SEND_PANEL] nenhum DataFrame disponível para envio.", "ERROR")
        return

    df_envio = _safe_copy_df(df_base)
    _persistir_df_envio(df_envio)

    st.caption("Os dados abaixo são apenas para envio. O download não será afetado.")

    with st.expander("Visualizar dados de envio", expanded=False):
        st.dataframe(df_envio.head(20), use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        label_envio = "🚀 Enviar para Bling" if conectado_real else "🧪 Simular envio"
        tipo_botao = "primary" if conectado_real else "secondary"

        if st.button(
            label_envio,
            use_container_width=True,
            type=tipo_botao,
            key="btn_enviar_bling_real_ou_simulado",
        ):
            try:
                total = len(df_envio)

                if conectado_real:
                    log_debug(
                        f"[SEND_PANEL] envio pronto para integração real com {total} registro(s).",
                        "INFO",
                    )
                    st.success(f"Conexão válida detectada. Base pronta para envio real ({total} registros).")
                else:
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
            key="btn_atualizar_dados_envio",
        ):
            df_base = _get_df_base_envio()
            if _safe_df(df_base):
                _persistir_df_envio(df_base)
                log_debug("[SEND_PANEL] dados de envio atualizados.", "INFO")
            st.rerun()

    st.markdown("---")
    st.info("⚠️ O envio utiliza uma cópia dos dados. O download final permanece intacto.")
  
