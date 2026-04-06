from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_sync import BlingSyncService
from bling_app_zero.utils.excel import df_to_excel_bytes


def _sanitize_label(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _ensure_bling_user_key() -> str:
    session_key = str(st.session_state.get("bling_user_key", "")).strip()
    query_key = str(st.query_params.get("bi", "")).strip()

    final_key = session_key or query_key
    if not final_key:
        final_key = f"bling_user_{__import__('secrets').token_hex(8)}"

    st.session_state["bling_user_key"] = final_key

    try:
        st.query_params["bi"] = final_key
    except Exception:
        pass

    return final_key


def _show_last_message() -> None:
    msg = str(st.session_state.get("bling_last_message", "")).strip()
    msg_type = str(st.session_state.get("bling_last_message_type", "")).strip()

    if not msg:
        return

    if msg_type == "success":
        st.success(msg)
    elif msg_type == "error":
        st.error(msg)
    else:
        st.info(msg)


def _set_last_message(message: str, message_type: str = "info") -> None:
    st.session_state["bling_last_message"] = str(message or "")
    st.session_state["bling_last_message_type"] = str(message_type or "info")


def render_bling_panel() -> None:
    st.subheader("Integração com o Bling")

    user_key = _ensure_bling_user_key()
    auth = BlingAuthManager(user_key=user_key)

    callback_result = auth.handle_oauth_callback()
    if callback_result["status"] == "success":
        _set_last_message(callback_result["message"], "success")
    elif callback_result["status"] == "error":
        _set_last_message(callback_result["message"], "error")

    _show_last_message()

    if not auth.is_configured():
        st.error(
            "A integração fixa do app ainda não foi configurada no servidor.\n\n"
            "Preencha as credenciais em `st.secrets[\"bling\"]` com: "
            "`client_id`, `client_secret` e `redirect_uri`."
        )
        return

    status = auth.get_connection_status()
    connected = bool(status.get("connected"))

    st.caption(
        "Neste fluxo o usuário final não precisa informar Client ID, Client Secret "
        "nem Redirect URI. Essas credenciais ficam fixas no app e o token é salvo "
        "de forma individual por instalação/usuário."
    )

    descricao = st.text_input(
        "Descrição da conta",
        value=str(st.session_state.get("bling_account_label", "")),
        placeholder="Ex.: Conta principal / Operação Mega Center",
    )
    st.session_state["bling_account_label"] = _sanitize_label(descricao)

    c1, c2, c3 = st.columns(3)

    authorize_url = auth.build_authorize_url(force_reauth=connected)

    with c1:
        if authorize_url:
            st.link_button(
                "Conectar com Bling" if not connected else "Reconectar com Bling",
                authorize_url,
                width="stretch",
            )
        else:
            st.button("Conectar com Bling", width="stretch", disabled=True)

    with c2:
        if st.button("Atualizar status", width="stretch"):
            ok, msg = auth.get_valid_access_token()
            if ok:
                _set_last_message("Status atualizado com sucesso.", "success")
            else:
                _set_last_message(msg, "error")
            st.rerun()

    with c3:
        if st.button("Desconectar", width="stretch", disabled=not connected):
            ok, msg = auth.disconnect()
            _set_last_message(msg, "success" if ok else "error")
            st.rerun()

    nome_exibicao = (
        str(status.get("company_name") or "").strip()
        or str(st.session_state.get("bling_account_label", "")).strip()
        or "Conta sem descrição"
    )

    with st.expander("Status da conexão", expanded=True):
        st.write(f"**Status:** {'Conectado' if connected else 'Desconectado'}")
        st.write(f"**Conta:** {nome_exibicao}")
        st.write(f"**Última autenticação:** {status.get('last_auth_at') or '-'}")
        st.write(f"**Expira em:** {status.get('expires_at') or '-'}")

        if not connected:
            st.info(
                "Clique em **Conectar com Bling** para autorizar a conta. "
                "Após o retorno do Bling, o token ficará salvo automaticamente "
                "para esta instalação/usuário."
            )


def render_bling_import_panel() -> None:
    st.subheader("Importar dados do Bling")

    user_key = _ensure_bling_user_key()
    auth = BlingAuthManager(user_key=user_key)
    sync = BlingSyncService(user_key=user_key)

    status = auth.get_connection_status()
    connected = bool(status.get("connected"))

    if not connected:
        st.info("Conecte uma conta Bling para liberar a importação de produtos e estoque.")
        return

    tab1, tab2 = st.tabs(["Produtos", "Estoque"])

    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            pagina_produtos = st.number_input(
                "Página de produtos",
                min_value=1,
                value=1,
                step=1,
            )
        with col_b:
            limite_produtos = st.number_input(
                "Limite de produtos",
                min_value=1,
                max_value=200,
                value=50,
                step=1,
            )

        if st.button("Importar produtos do Bling", width="stretch"):
            ok, payload = sync.importar_produtos(
                pagina=int(pagina_produtos),
                limite=int(limite_produtos),
            )
            if ok:
                df = pd.DataFrame(payload)
                st.session_state["bling_produtos_df"] = df
                _set_last_message("Produtos importados com sucesso.", "success")
            else:
                st.session_state["bling_produtos_df"] = None
                _set_last_message(f"Falha ao importar produtos: {payload}", "error")
            st.rerun()

        df_prod = st.session_state.get("bling_produtos_df")
        if isinstance(df_prod, pd.DataFrame) and not df_prod.empty:
            st.dataframe(df_prod, width="stretch")
            st.download_button(
                "Baixar produtos do Bling em Excel",
                data=df_to_excel_bytes(df_prod, "produtos_bling"),
                file_name="produtos_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

    with tab2:
        col_c, col_d, col_e = st.columns(3)
        with col_c:
            pagina_estoque = st.number_input(
                "Página de estoque",
                min_value=1,
                value=1,
                step=1,
            )
        with col_d:
            limite_estoque = st.number_input(
                "Limite de estoque",
                min_value=1,
                max_value=200,
                value=50,
                step=1,
            )
        with col_e:
            deposito_id = st.text_input(
                "ID do depósito (opcional)",
                value="",
                placeholder="Ex.: 1",
            ).strip()

        if st.button("Importar estoque do Bling", width="stretch"):
            ok, payload = sync.importar_estoques(
                pagina=int(pagina_estoque),
                limite=int(limite_estoque),
                id_deposito=deposito_id or None,
            )
            if ok:
                df = pd.DataFrame(payload)
                st.session_state["bling_estoque_df"] = df
                _set_last_message("Estoque importado com sucesso.", "success")
            else:
                st.session_state["bling_estoque_df"] = None
                _set_last_message(f"Falha ao importar estoque: {payload}", "error")
            st.rerun()

        df_est = st.session_state.get("bling_estoque_df")
        if isinstance(df_est, pd.DataFrame) and not df_est.empty:
            st.dataframe(df_est, width="stretch")
            st.download_button(
                "Baixar estoque do Bling em Excel",
                data=df_to_excel_bytes(df_est, "estoque_bling"),
                file_name="estoque_bling.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
