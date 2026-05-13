from __future__ import annotations

"""Wrapper oficial do fluxo Preços Multiloja.

BLINGCLEAN #ALL SAFE:
- `ui.py` continua sendo o motor base do Multiloja e não deve ser apagado.
- `ui_plus.py` é a entrada oficial chamada pela Home.
- Este wrapper adiciona origem complementar por site/importação sem reescrever o
  motor original, reduzindo risco de quebrar cálculo, CSV, ZIP e auditoria.
"""

from collections.abc import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.v2.price_multistore.source_origin_panel import (
    get_multistore_source_origin_df,
    render_multistore_source_origin_panel,
    should_use_multistore_complementary_source,
)
from bling_app_zero.v2.price_multistore import ui as original_ui
from bling_app_zero.v2.session_store import get_state, widget_key


_ORIGINAL_READ: Callable[[object], pd.DataFrame | None] = original_ui._read
SUGGESTED_PRICE_COLUMN_STATE = 'multistore_source_suggested_price_column'
SOURCE_UPLOAD_WIDGET = 'multistore_source_upload'
COST_COLUMN_WIDGET = 'multistore_cost_column'


def _patched_read_factory():
    """Cria um leitor temporário para injetar a origem complementar como Planilha 2.

    O motor base chama `_read()` duas vezes: Planilha 1 do Bling e Planilha 2 de
    custo. Este patch só interfere quando não há upload da Planilha 2 e o usuário
    escolheu usar captura por site/importação como origem complementar.
    """
    call_index = {'value': 0}

    def _patched_read(uploaded_file) -> pd.DataFrame | None:
        call_index['value'] += 1
        if uploaded_file is not None:
            return _ORIGINAL_READ(uploaded_file)
        if call_index['value'] >= 2 and should_use_multistore_complementary_source():
            source_df = get_multistore_source_origin_df()
            if isinstance(source_df, pd.DataFrame) and not source_df.empty:
                return source_df.copy().fillna('')
        return None

    return _patched_read


def _prime_cost_column_from_complementary_source(source_df: pd.DataFrame | None) -> None:
    """Preenche a coluna de custo sugerida antes do módulo base renderizar o selectbox.

    O motor base espera upload da Planilha 2. Quando o wrapper injeta uma origem
    complementar por site/importação, o usuário não deve precisar escolher de novo a
    coluna que o painel complementar já detectou como preço/custo provável.
    """
    if not should_use_multistore_complementary_source():
        return
    if not isinstance(source_df, pd.DataFrame) or source_df.empty:
        return
    suggested = str(get_state(SUGGESTED_PRICE_COLUMN_STATE) or '').strip()
    if not suggested or suggested not in [str(column) for column in source_df.columns]:
        return
    cost_key = widget_key(COST_COLUMN_WIDGET)
    source_upload_key = widget_key(SOURCE_UPLOAD_WIDGET)
    if st.session_state.get(source_upload_key) is None:
        st.session_state[cost_key] = suggested


def render_price_multistore_v2() -> None:
    """Renderiza o Multiloja oficial com origem complementar segura.

    A Home deve chamar esta função. O motor base (`original_ui`) continua cuidando
    do cálculo, auditoria, CSV e ZIP; este wrapper apenas prepara a origem extra.
    """
    st.markdown('### Origem complementar')
    source_df = render_multistore_source_origin_panel()
    if should_use_multistore_complementary_source():
        if isinstance(source_df, pd.DataFrame) and not source_df.empty:
            _prime_cost_column_from_complementary_source(source_df)
            st.caption('A origem complementar escolhida será usada como Planilha 2 neste cálculo.')
        else:
            st.caption('Você escolheu usar origem complementar, mas ainda precisa capturar/importar os dados do fornecedor.')
    else:
        st.caption('Upload normal da Planilha 2 ativo. Capturas por site ficam disponíveis, mas não substituem a planilha automaticamente.')
    st.divider()

    previous_read = original_ui._read
    original_ui._read = _patched_read_factory()
    try:
        original_ui.render_price_multistore_v2()
    finally:
        original_ui._read = previous_read


__all__ = ['render_price_multistore_v2']
