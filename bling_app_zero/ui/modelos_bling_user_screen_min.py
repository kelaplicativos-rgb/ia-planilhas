from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.user_bling_models_store import (
    MODEL_LABELS,
    MODEL_TYPES,
    get_user_model,
    remove_user_model,
    save_user_model,
)

MODEL_TITLES = {
    'cadastro': 'Anexar modelo Bling cadastro',
    'estoque': 'Anexar modelo Bling estoque',
    'precos': 'Anexar modelo Bling atualizar preços',
}


def _show_model(model_type: str) -> None:
    label = MODEL_LABELS.get(model_type, model_type)
    title = MODEL_TITLES.get(model_type, f'Anexar {label}')

    st.markdown('---')
    st.markdown(f'#### {title}')

    df, info = get_user_model(model_type)
    if df is not None and info:
        st.success('Modelo salvo')
        st.caption(str(info.get('name') or ''))
        st.caption('Colunas: ' + str(len(df.columns)))
        if st.button('Remover modelo salvo', key=f'remove_{model_type}', use_container_width=True):
            remove_user_model(model_type)
            st.rerun()
    else:
        st.warning('Nenhum modelo salvo ainda.')

    uploaded = st.file_uploader(
        title,
        key=f'upload_{model_type}',
        help='No celular, o seletor fica sem filtro para evitar arquivo CSV ou XLSX cinza/bloqueado. O sistema valida o formato depois do anexo.',
    )

    if uploaded is not None:
        try:
            save_user_model(model_type, uploaded.name, uploaded.getvalue())
            st.success('Modelo salvo com sucesso')
            st.rerun()
        except Exception as exc:
            st.error(f'Arquivo não aceito: {exc}')


def render_modelos_bling_user_screen() -> None:
    st.markdown('### Bling')
    st.caption('Modelos base do usuário')
    st.info('Anexe os modelos uma vez. Eles ficarão disponíveis até você remover ou substituir.')

    for model_type in MODEL_TYPES:
        _show_model(model_type)


__all__ = ['render_modelos_bling_user_screen']
