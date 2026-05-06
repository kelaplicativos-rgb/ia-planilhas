from __future__ import annotations

"""Patch vivo para o fluxo stable.

Objetivo: deixar o preview do mapeamento simples e real:
- abaixo do select aparece somente o conteúdo real da primeira linha da coluna selecionada;
- não aparece título da coluna no preview;
- não aparece porcentagem, confiança ou texto fake;
- usa on_change para sincronizar o preview com o selectbox imediatamente;
- usa keys versionadas para escapar do session_state antigo do Streamlit.
"""

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.stable import stable_app as base

MAPPING_UI_VERSION = "2026-05-06-live-select-preview-v7"

_ORIGINAL_SOURCE_OPTIONS = base._source_options_for_target
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
        serie = df[col].fillna("").astype(str)
        if len(serie) == 0:
            return ""
        value = str(serie.iloc[0] or "").strip()
        if value.lower() in {"nan", "none", "null"}:
            return ""
        return value[:350]
    except Exception:
        return ""


def _selected_store() -> dict[str, str]:
    store = st.session_state.setdefault("stable_live_selected_columns", {})
    return store if isinstance(store, dict) else {}


def _sync_selected(campo: str, key: str) -> None:
    store = _selected_store()
    store[str(campo or "").strip()] = str(st.session_state.get(key, "") or "").strip()
    st.session_state["stable_live_selected_columns"] = store


def _selected_for(campo: str, fallback: str = "") -> str:
    store = _selected_store()
    return str(store.get(str(campo or "").strip(), fallback) or "").strip()


def _render_source_preview_real(df: pd.DataFrame, target: str, selected_col: str, auto_100: bool = False) -> None:
    target = str(target or "").strip()
    selected_col = _selected_for(target, selected_col)
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

    stored_value = _selected_for(campo, default_value)
    initial_value = stored_value if stored_value in options else default_value
    index = options.index(initial_value) if initial_value in options else 0

    selected = st.selectbox(
        campo,
        options,
        index=index,
        key=key,
        on_change=_sync_selected,
        args=(campo, key),
    )
    selected = str(selected or "").strip()
    _sync_selected(campo, key)
    return selected


def _source_options_allow_id(target: str, df: pd.DataFrame, model_cols: list[str]) -> list[str]:
    try:
        opcoes = _ORIGINAL_SOURCE_OPTIONS(target, df, model_cols)
    except Exception:
        opcoes = []

    extras: list[str] = []
    if isinstance(df, pd.DataFrame):
        for col in df.columns:
            nome = str(col or "").strip()
            if nome and nome not in opcoes and nome not in extras:
                extras.append(nome)

    final = [""]
    for item in list(opcoes) + extras:
        item = str(item or "").strip()
        if item and item not in final:
            final.append(item)
    return final


def run_stable_app() -> None:
    base._live_mapping_counter = 0
    base._render_source_preview = _render_source_preview_real
    base._selectbox_mapping = _selectbox_mapping_live
    base._source_options_for_target = _source_options_allow_id
    base.MAPPING_UI_VERSION = MAPPING_UI_VERSION
    base.run_stable_app()
