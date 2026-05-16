from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    name: str = ''
    authenticated: bool = False


USER_ID_KEY = 'mapeiaai_user_id'
USER_EMAIL_KEY = 'mapeiaai_user_email'
USER_NAME_KEY = 'mapeiaai_user_name'


def get_current_user() -> CurrentUser:
    user_id = str(st.session_state.get(USER_ID_KEY) or '').strip()
    email = str(st.session_state.get(USER_EMAIL_KEY) or '').strip()
    name = str(st.session_state.get(USER_NAME_KEY) or '').strip()
    return CurrentUser(id=user_id, email=email, name=name, authenticated=bool(user_id and email))


def set_demo_user(email: str = 'teste@mapeiaai.com') -> CurrentUser:
    st.session_state[USER_ID_KEY] = 'demo-user-session'
    st.session_state[USER_EMAIL_KEY] = email
    st.session_state[USER_NAME_KEY] = 'Usuário de teste'
    return get_current_user()


def clear_current_user() -> None:
    st.session_state.pop(USER_ID_KEY, None)
    st.session_state.pop(USER_EMAIL_KEY, None)
    st.session_state.pop(USER_NAME_KEY, None)


__all__ = ['CurrentUser', 'USER_EMAIL_KEY', 'USER_ID_KEY', 'USER_NAME_KEY', 'clear_current_user', 'get_current_user', 'set_demo_user']
