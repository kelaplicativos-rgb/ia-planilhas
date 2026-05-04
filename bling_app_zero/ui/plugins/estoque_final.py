from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.preview_final_estoque_inteligente import aplicar_estoque_inteligente_final


def before_download(df: pd.DataFrame, **ctx) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    disponivel = int(st.session_state.get("estoque_padrao_disponivel", 5) or 5)
    baixo = int(st.session_state.get("estoque_padrao_baixo", 1) or 1)
    sobrescrever = bool(st.session_state.get("preview_estoque_sobrescrever_capturado", True))
    return aplicar_estoque_inteligente_final(df, disponivel, baixo, sobrescrever)
