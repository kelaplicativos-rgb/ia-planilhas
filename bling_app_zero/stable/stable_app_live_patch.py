from __future__ import annotations

"""Patch vivo para o fluxo stable.

Objetivo: recuperar o comportamento simples e real do mapeamento:
- o texto abaixo do select mostra SEMPRE a coluna selecionada agora;
- mostra somente a primeira amostra real da coluna;
- remove textos longos/falsos de confiança;
- usa keys versionadas para escapar do session_state antigo do Streamlit.
"""

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base

MAPPING_UI_VERSION = "2026-05-06-blue-preview-v4"

base.MAPPING_UI_VERSION = MAPPING_UI_VERSION


def _norm_key(value: Any) -> str:
    try:
        return base._norm(value).replace(" ", "_")
    except Exception:
        return str(value or "").strip().lower().replace(" ", "_")


def _first_value(df: pd.DataFrame, col: str) -> str:
    try:
        value = base._first_non_empty_value(df, col)
        return str(value or "").strip()
    except Exception:
        return ""


def _render_source_preview_real(df: pd.DataFrame, target: str, selected_col: str, auto_100: bool = False) -> None:
    selected_col = str(selected_col or "").strip()
    if not selected_col:
        st.markdown(
            "<div style='margin-top:-0.65rem;margin-bottom:0.75rem;color:#b91c1c;font-size:0.88rem;'>"
            "⚠️ Selecione a coluna correta."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    value = _first_value(df, selected_col) or "sem valor preenchido"
    st.markdown(
        "<div style='margin-top:-0.65rem;margin-bottom:0.75rem;line-height:1.25;'>"
        f"<div style='color:#2563eb;font-size:0.86rem;font-weight:700;'>Coluna selecionada: {escape(selected_col)}</div>"
        f"<div style='color:#047857;font-size:0.84rem;font-weight:700;'>{escape(value)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _selectbox_mapping_live(campo: str, options: list[str], default_value: str) -> str:
    campo = str(campo or "").strip()
    options = [str(opt or "") for opt in options]
    default_value = str(default_value or "").strip()

    ordem = int(getattr(base, "_live_mapping_counter", 0) or 0)
    base._live_mapping_counter = ordem + 1

    # limpa somente chaves antigas que prendiam o widget em estado obsoleto
    st.session_state.pop(f"stable_map_{campo}", None)

    key = f"stable_map_live_{MAPPING_UI_VERSION}_{ordem}_{_norm_key(campo)}"
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state.pop(key, None)

    index = options.index(default_value) if default_value in options else 0
    st.selectbox(campo, options, index=index, key=key)
    return str(st.session_state.get(key, "") or "").strip()


def run_stable_app() -> None:
    base._live_mapping_counter = 0
    base._render_source_preview = _render_source_preview_real
    base._selectbox_mapping = _selectbox_mapping_live
    base.MAPPING_UI_VERSION = MAPPING_UI_VERSION
    base.run_stable_app()
