from __future__ import annotations

import pandas as pd
import streamlit as st


# ==========================================================
# IMPORTS (PROTEGIDOS)
# ==========================================================
try:
    from bling_app_zero.core.bling_api import BlingAPIClient
except Exception:
    BlingAPIClient = None

try:
    from bling_app_zero.core.bling_auth import BlingAuthManager
except Exception:
    BlingAuthManager = None

try:
    from bling_app_zero.core.bling_user_session import (
        ensure_current_user_defaults,
        get_current_user_key,
        get_current_user_label,
        set_pending_oauth_user,
    )
except Exception:
    ensure_current_user_defaults = None
    get_current_user_key = None
    get_current_user_label = None
    set_pending_oauth_user = None

try:
    from bling_app_zero.ui.bling_panel_helpers import (
        bloquear_importacao,
        bloquear_painel_principal,
        clear_callback_params,
        has_callback_params,
        safe_df,
        status_texto,
    )
except Exception:
    def bloquear_importacao():
        return False

    def bloquear_painel_principal():
        return False

    def clear_callback_params():
        return None

    def has_callback_params():
        return False

    def safe_df(x):
        return x

    def status_texto(x):
        return str(x)

try:
    from bling_app_zero.ui.bling_panel_usuario import (
        processar_callback_oauth,
        render_usuario_bling,
    )
except Exception:
    def processar_callback_oauth(*args, **kwargs):
        return False

    def render_usuario_bling():
        return None


# ==========================================================
# SAFE SESSION
# ==========================================================
def _safe_session() -> bool:
    try:
        if not hasattr(st, "session_state"):
            return False
        _ = st.session_state
        return True
    except Exception:
        return False


def _safe_status_dict(auth) -> dict:
    """
    Blindagem para cenários em que a classe BlingAuthManager
    ainda não expõe get_connection_status().
    """
    try:
        if auth is None:
            return {"connected": False, "configured": False}

        if hasattr(auth, "get_connection_status") and callable(auth.get_connection_status):
            status = auth.get_connection_status()
            if isinstance(status, dict):
                return status

        token_info = None
        for nome_attr in [
            "get_token_info",
            "load_tokens",
            "load_token_data",
            "get_tokens",
        ]:
            try:
                if hasattr(auth, nome_attr):
                    metodo = getattr(auth, nome_attr)
                    if callable(metodo):
                        token_info = metodo()
                        break
            except Exception:
                continue

        connected = False
        if isinstance(token_info, dict):
            connected = bool(
                token_info.get("access_token")
                or token_info.get("refresh_token")
                or token_info.get("connected")
            )

        return {
            "connected": connected,
            "configured": bool(getattr(auth, "is_configured", lambda: False)()),
        }
    except Exception:
        return {"connected": False, "configured": False}


# ==========================================================
# ENVIO PRO
# ==========================================================
def _enviar_produtos(df: pd.DataFrame, client: BlingAPIClient):
    total = len(df)
    progresso = st.progress(0)
    log_area = st.empty()
    sucesso = 0
    erros = []

    for i, row in df.iterrows():
        ok, resp = client.upsert_product(row.to_dict())

        if ok:
            sucesso += 1
        else:
            erros.append({"linha": i, "erro": resp})

        progresso.progress((i + 1) / total)
        log_area.write(f"Processando {i + 1}/{total}")

    st.success(f"{sucesso}/{total} produtos enviados com sucesso.")

    if erros:
        st.warning(f"{len(erros)} erros encontrados.")
        st.dataframe(pd.DataFrame(erros), use_container_width=True, hide_index=True)


def _enviar_estoque(df: pd.DataFrame, client: BlingAPIClient):
    total = len(df)
    progresso = st.progress(0)
    sucesso = 0
    erros = []

    for i, row in df.iterrows():
        ok, resp = client.update_stock(
            codigo=row.get("codigo"),
            estoque=row.get("saldo"),
            deposito_id=row.get("deposito_id"),
            preco=row.get("preco"),
        )

        if ok:
            sucesso += 1
        else:
            erros.append({"linha": i, "erro": resp})

        progresso.progress((i + 1) / total)

    st.success(f"{sucesso}/{total} estoques enviados.")

    if erros:
        st.warning(f"{len(erros)} erros.")
        st.dataframe(pd.DataFrame(erros), use_container_width=True, hide_index=True)


# ==========================================================
# PAINEL PRINCIPAL
# ==========================================================
def render_bling_panel():
    if not _safe_session():
        st.warning("Sessão ainda não inicializada.")
        return

    if bloquear_painel_principal():
        return

    render_usuario_bling()

    if processar_callback_oauth(has_callback_params, clear_callback_params):
        return

    if BlingAuthManager is None:
        st.warning("⚠️ Módulo de autenticação do Bling indisponível.")
        return

    if get_current_user_key is None:
        st.warning("⚠️ Sessão de usuário do Bling indisponível.")
        return

    user_key = get_current_user_key()
    auth = BlingAuthManager(user_key=user_key)

    if not auth.is_configured():
        st.warning("⚠️ Configure o Bling.")
        return

    status = _safe_status_dict(auth)

    st.markdown("### 🔗 Integração Bling")

    col1, col2, col3 = st.columns(3)

    with col1:
        try:
            url = auth.build_authorize_url(force_reauth=True)
            st.link_button("Conectar / Reconectar", url, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao gerar URL de conexão: {e}")

    with col2:
        if st.button("Atualizar Token", use_container_width=True):
            try:
                ok, msg = auth.get_valid_access_token()
                if ok:
                    st.success("Token atualizado com sucesso.")
                else:
                    st.warning(str(msg))
            except Exception as e:
                st.error(f"Erro ao atualizar token: {e}")

    with col3:
        if st.button("Desconectar", use_container_width=True):
            try:
                ok, msg = auth.disconnect()
                if ok:
                    st.success(str(msg))
                else:
                    st.warning(str(msg))
            except Exception as e:
                st.error(f"Erro ao desconectar: {e}")

    try:
        st.write(status_texto(status))
    except Exception:
        st.write(status)

    # ======================================================
    # ENVIO
    # ======================================================
    st.markdown("---")
    st.markdown("## Envio para Bling")

    if BlingAPIClient is None:
        st.warning("⚠️ API do Bling indisponível.")
        return

    try:
        ok, msg = auth.get_valid_access_token()
    except Exception as e:
        st.warning(f"Falha ao validar token do Bling: {e}")
        return

    if not ok:
        st.warning("⚠️ Conecte ao Bling antes de enviar.")
        return

    client = BlingAPIClient(user_key=user_key)

    df_final = st.session_state.get("df_resultado_final")
    if df_final is None or len(df_final) == 0:
        st.warning("⚠️ Nenhum dado para envio.")
        return

    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo == "cadastro":
        if st.button("Enviar PRODUTOS para Bling", use_container_width=True):
            _enviar_produtos(df_final, client)

    elif tipo == "estoque":
        if st.button("Enviar ESTOQUE para Bling", use_container_width=True):
            _enviar_estoque(df_final, client)

    else:
        st.info("Selecione o tipo de operação para liberar o envio.")


# ==========================================================
# IMPORTAÇÃO (mantido)
# ==========================================================
def render_bling_import_panel():
    if not _safe_session():
        return

    if bloquear_importacao():
        return

    st.markdown("### Importar do Bling")

    if ensure_current_user_defaults is not None:
        ensure_current_user_defaults()

    if BlingAuthManager is None or BlingAPIClient is None or get_current_user_key is None:
        st.warning("⚠️ Integração do Bling indisponível.")
        return

    user_key = get_current_user_key()
    auth = BlingAuthManager(user_key=user_key)

    try:
        ok, msg = auth.get_valid_access_token()
    except Exception as e:
        st.warning(f"Falha ao validar token: {e}")
        return

    if not ok:
        st.warning(str(msg))
        return

    client = BlingAPIClient(user_key=user_key)

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        if st.button("Importar produtos", use_container_width=True):
            ok, payload = client.list_products()
            if ok:
                df = safe_df(client.products_to_dataframe(payload))
                st.session_state["bling_produtos_df"] = df
                st.success(f"{len(df)} produtos")
            else:
                st.error(payload)

        df = st.session_state.get("bling_produtos_df")
        if isinstance(df, pd.DataFrame) and not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab2:
        if st.button("Importar estoque", use_container_width=True):
            ok, payload = client.list_stocks()
            if ok:
                df = safe_df(client.stocks_to_dataframe(payload))
                st.session_state["bling_estoque_df"] = df
                st.success(f"{len(df)} registros")
            else:
                st.error(payload)

        df = st.session_state.get("bling_estoque_df")
        if isinstance(df, pd.DataFrame) and not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
