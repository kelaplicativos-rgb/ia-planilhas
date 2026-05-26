from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.user_bling_models_store import (
    MODEL_LABELS,
    MODEL_TYPES,
    get_user_model,
    remove_user_model,
    save_user_model,
)


def _show_model(model_type: str) -> None:
    label = MODEL_LABELS.get(model_type, model_type)
    st.markdown(f'##### {label}')
    df, info = get_user_model(model_type)
    if df is not None and info:
        st.success('Modelo salvo')
        st.caption(str(info.get('name') or ''))
        st.caption('Colunas: ' + str(len(df.columns)))
        if st.button('Remover', key=f'remove_{model_type}', use_container_width=True):
            remove_user_model(model_type)
            st.rerun()

    st.caption('No celular, o seletor fica aberto para evitar arquivo CSV/XLSX cinza ou bloqueado. A validação do formato acontece após anexar.')
    uploaded = st.file_uploader('Anexar modelo', key=f'upload_{model_type}')
    if uploaded is not None:
        try:
            save_user_model(model_type, uploaded.name, uploaded.getvalue())
            st.success('Salvo')
            st.rerun()
        except Exception as exc:
            st.error(f'Arquivo não aceito: {exc}')


def render_modelos_bling_user_screen() -> None:
    st.markdown('### Bling')
    st.caption('Modelos base do usuario')
    tabs = st.tabs(['Cadastro', 'Estoque', 'Precos'])
    for tab, model_type in zip(tabs, MODEL_TYPES):
        with tab:
            _show_model(model_type)


__all__ = ['render_modelos_bling_user_screen']
