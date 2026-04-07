from __future__ import annotations

import streamlit as st

from bling_app_zero.core.bling_auth import BlingAuthManager
from bling_app_zero.core.bling_user_session import (
    clear_pending_oauth_user,
    ensure_current_user_defaults,
    get_current_user_key,
    get_current_user_label,
    get_pending_oauth_user_key,
    get_pending_oauth_user_label,
    set_current_user,
)


# ==========================================================
# USUÁRIO
# ==========================================================
def render_usuario_bling() -> None:
    ensure_current_user_defaults()

    with st.expander("Usuário Bling", expanded=False):
        identificador_atual = get_current_user_key()
        apelido_atual = get_current_user_label()

        identificador = st.text_input(
            "ID do usuário",
            value=identificador_atual,
            key="bling_user_identificador",
        )

        apelido = st.text_input(
            "Nome exibido",
            value=apelido_atual,
            key="bling_user_apelido",
        )

        if st.button(
            "Aplicar usuário",
            use_container_width=True,
            key="btn_aplicar_usuario_bling",
        ):
            identificador_limpo = (identificador or "").strip()
            apelido_limpo = (apelido or "").strip()

            if not identificador_limpo:
                st.error("Informe o identificador.")
                return

            set_current_user(
                identificador_limpo,
                apelido_limpo or identificador_limpo,
            )
            st.success("Usuário atualizado.")
            st.rerun()

        st.caption(f"Atual: {get_current_user_label()} ({get_current_user_key()})")


def processar_callback_oauth(
    has_callback_params_func,
    clear_callback_params_func,
) -> bool:
    """
    Processa callback OAuth quando existir.
    Retorna True se o fluxo foi tratado e houve rerun/saída lógica.
    """
    try:
        if not has_callback_params_func():
            return False

        user_key = get_pending_oauth_user_key() or get_current_user_key()
        user_label = get_pending_oauth_user_label() or get_current_user_label()

        auth_callback = BlingAuthManager(user_key=user_key)
        result = auth_callback.handle_oauth_callback()

        if result.get("status") == "success":
            set_current_user(user_key, user_label)
            clear_pending_oauth_user()
            clear_callback_params_func()
            st.success("Conectado com sucesso.")
            st.rerun()
            return True

        if result.get("status") == "error":
            clear_pending_oauth_user()
            clear_callback_params_func()
            st.error(result.get("message", "Erro OAuth"))
            st.rerun()
            return True

    except Exception as e:
        st.error(f"Erro OAuth: {e}")
        return True

    return False
