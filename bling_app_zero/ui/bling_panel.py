from __future__ import annotations

import streamlit as st
import pandas as pd


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
    def bloquear_importacao(): return False
    def bloquear_painel_principal(): return False
    def clear_callback_params(): pass
    def has_callback_params(): return False
    def safe_df(x): return x
    def status_texto(x): return str(x)

try:
    from bling_app_zero.ui.bling_panel_usuario import (
        processar_callback_oauth,
        render_usuario_bling,
    )
except Exception:
    def processar_callback_oauth(*args, **kwargs): return False
    def render_usuario_bling(): pass


# ==========================================================
# SAFE SESSION
# ==========================================================
def _safe_session():
    try:
        if not hasattr(st, "session_state"):
            return False
        _ = st.session_state
        return True
    except Exception:
        return False


# ==========================================================
# ENVIO PRO 🔥
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
        log_area.write(f"Processando {i+1}/{total}")

    st.success(f"{sucesso}/{total} produtos enviados com sucesso.")

    if erros:
        st.warning(f"{len(erros)} erros encontrados.")
        st.dataframe(pd.DataFrame(erros))


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
        st.dataframe(pd.DataFrame(erros))


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

    user_key = get_current_user_key()

    auth = BlingAuthManager(user_key=user_key)

    if not auth.is_configured():
        st.warning("Configure o Bling.")
        return

    status = auth.get_connection_status()

    st.markdown("### 🔗 Integração Bling")

    col1, col2, col3 = st.columns(3)

    with col1:
        url = auth.build_authorize_url(force_reauth=True)
        st.link_button("Conectar / Reconectar", url, use_container_width=True)

    with col2:
        if st.button("Atualizar Token"):
            ok, msg = auth.get_valid_access_token()
            st.success("OK" if ok else msg)

    with col3:
        if st.button("Desconectar"):
            ok, msg = auth.disconnect()
            st.success(msg if ok else msg)

    st.write(status_texto(status))

    # ======================================================
    # 🔥 ENVIO
    # ======================================================
    st.markdown("---")
    st.markdown("## 🚀 Envio para Bling")

    if BlingAPIClient is None:
        st.warning("API indisponível.")
        return

    ok, msg = auth.get_valid_access_token()
    if not ok:
        st.warning("Conecte ao Bling.")
        return

    client = BlingAPIClient(user_key=user_key)

    df_final = st.session_state.get("df_resultado_final")

    if df_final is None or len(df_final) == 0:
        st.warning("Nenhum dado para envio.")
        return

    tipo = st.session_state.get("tipo_operacao_bling")

    if tipo == "cadastro":
        if st.button("Enviar PRODUTOS para Bling", use_container_width=True):
            _enviar_produtos(df_final, client)

    elif tipo == "estoque":
        if st.button("Enviar ESTOQUE para Bling", use_container_width=True):
            _enviar_estoque(df_final, client)


# ==========================================================
# IMPORTAÇÃO (mantido)
# ==========================================================
def render_bling_import_panel():

    if not _safe_session():
        return

    if bloquear_importacao():
        return

    st.markdown("### Importar do Bling")

    ensure_current_user_defaults()
    user_key = get_current_user_key()

    auth = BlingAuthManager(user_key=user_key)
    ok, msg = auth.get_valid_access_token()

    if not ok:
        st.warning(msg)
        return

    client = BlingAPIClient(user_key=user_key)

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        if st.button("Importar produtos"):
            ok, payload = client.list_products()
            if ok:
                df = safe_df(client.products_to_dataframe(payload))
                st.session_state["bling_produtos_df"] = df
                st.success(f"{len(df)} produtos")
            else:
                st.error(payload)

        df = st.session_state.get("bling_produtos_df")
        if isinstance(df, pd.DataFrame) and not df.empty:
            st.dataframe(df)

    with tab2:
        if st.button("Importar estoque"):
            ok, payload = client.list_stocks()
            if ok:
                df = safe_df(client.stocks_to_dataframe(payload))
                st.session_state["bling_estoque_df"] = df
                st.success(f"{len(df)} registros")
            else:
                st.error(payload)

        df = st.session_state.get("bling_estoque_df")
        if isinstance(df, pd.DataFrame) and not df.empty:
            st.dataframe(df)
