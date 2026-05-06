from __future__ import annotations

"""Patch vivo para o fluxo stable.

Objetivo: deixar o preview do mapeamento simples e real:
- abaixo do select aparece somente o conteúdo real da primeira linha da coluna selecionada;
- não aparece título da coluna no preview;
- não aparece porcentagem, confiança ou texto fake;
- usa keys versionadas para escapar do session_state antigo do Streamlit.
"""

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base

MAPPING_UI_VERSION = "2026-05-06-value-only-preview-v6"

base.MAPPING_UI_VERSION = MAPPING_UI_VERSION


def _norm_key(value: Any) -> str:
    try:
        return base._norm(value).replace(" ", "_")
    except Exception:
        return str(value or "").strip().lower().replace(" ", "_")


def _first_value(df: pd.DataFrame, col: str) -> str:
    try:
        if not isinstance(df, pd.DataFrame) or col not in df.columns:
            return ""
        serie = df[col].astype(str).fillna("")
        if len(serie) == 0:
            return ""
        value = str(serie.iloc[0] or "").strip()
        if value.lower() in {"nan", "none", "null"}:
            return ""
        return value[:350]
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

    value = _first_value(df, selected_col) or "sem valor preenchido na primeira linha"
    st.markdown(
        "<div style='margin-top:-0.65rem;margin-bottom:0.75rem;line-height:1.25;'>"
        f"<div style='color:#047857;font-size:0.88rem;font-weight:700;'>{escape(value)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def _selectbox_mapping_live(campo: str, options: list[str], default_value: str) -> str:
    campo = str(campo or "").strip()
    options = [str(opt or "") for opt in options]
    default_value = str(default_value or "").strip()

    ordem = int(getattr(base, "_live_mapping_counter", 0) or 0)
    base._live_mapping_counter = ordem + 1

    st.session_state.pop(f"stable_map_{campo}", None)

    key = f"stable_map_live_{MAPPING_UI_VERSION}_{ordem}_{_norm_key(campo)}"
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state.pop(key, None)

    index = options.index(default_value) if default_value in options else 0
    selected = st.selectbox(campo, options, index=index, key=key)
    return str(selected or "").strip()


def _source_options_allow_id(target: str, df: pd.DataFrame, model_cols: list[str]) -> list[str]:
    try:
        return base._source_options_for_target(target, df, model_cols)
    except Exception:
        raw_cols = list(df.columns) if isinstance(df, pd.DataFrame) else []
        return [""] + [str(c).strip() for c in raw_cols if str(c).strip()]


def run_stable_app() -> None:
    base._live_mapping_counter = 0
    base._render_source_preview = _render_source_preview_real
    base._selectbox_mapping = _selectbox_mapping_live
    base._source_options_for_target = _source_options_allow_id
    base.MAPPING_UI_VERSION = MAPPING_UI_VERSION
    base.run_stable_app()
