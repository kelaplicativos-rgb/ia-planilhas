from __future__ import annotations

"""Amostras visuais compactas para a tela de mapeamento."""

import html as html_lib

import pandas as pd
import streamlit as st


MAX_HINT_CHARS = 120


def _limpar_valor(valor: object, limite: int = MAX_HINT_CHARS) -> str:
    texto = " ".join(str(valor or "").replace("\n", " ").replace("\r", " ").split()).strip()
    if len(texto) > limite:
        return texto[: limite - 3].rstrip() + "..."
    return texto


def primeira_amostra_coluna(df_base: pd.DataFrame, coluna_origem: str) -> str:
    if not isinstance(df_base, pd.DataFrame) or df_base.empty:
        return ""
    coluna = str(coluna_origem or "").strip()
    if not coluna or coluna not in df_base.columns:
        return ""
    try:
        serie = df_base[coluna].fillna("").astype(str)
        for valor in serie.tolist():
            amostra = _limpar_valor(valor)
            if amostra:
                return amostra
    except Exception:
        return ""
    return ""


def render_amostra_vermelha(df_base: pd.DataFrame, coluna_origem: str, *, prefixo: str = "Prévia") -> None:
    amostra = primeira_amostra_coluna(df_base, coluna_origem)
    if not amostra:
        return

    st.markdown(
        """
        <div style="
            color:#DC2626;
            font-size:11px;
            line-height:1.25;
            margin:-4px 0 6px 2px;
            font-weight:600;
            word-break:break-word;
        ">
            <span style="opacity:.86;">%s:</span> %s
        </div>
        """ % (html_lib.escape(prefixo), html_lib.escape(amostra)),
        unsafe_allow_html=True,
    )
