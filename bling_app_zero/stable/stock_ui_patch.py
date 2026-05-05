from __future__ import annotations

import re
from typing import Any

import streamlit as st

from bling_app_zero.stable import stable_app as base_app
from bling_app_zero.stable import sitefix_patch


def _tipo() -> str:
    return str(st.session_state.get("stable_tipo", "cadastro") or "cadastro").strip().lower()


def _norm(v: object) -> str:
    t = str(v or "").strip().lower()
    t = t.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _unique(options: Any) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for item in list(options or []):
        key = "__blank__" if item == "" else _norm(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out or [""]


def run_stable_app() -> None:
    original_selectbox = st.selectbox
    original_price = base_app._is_price_target

    def selectbox(label: str, options, *args: Any, **kwargs: Any):
        old = list(options or [])
        new = _unique(old)
        idx = int(kwargs.get("index", 0) or 0)
        selected = old[idx] if 0 <= idx < len(old) else new[0]
        kwargs["index"] = new.index(selected) if selected in new else 0
        return original_selectbox(label, new, *args, **kwargs)

    def is_price(target: object) -> bool:
        if _tipo() == "estoque":
            return False
        return original_price(target)

    st.selectbox = selectbox
    base_app._is_price_target = is_price
    try:
        sitefix_patch.run_stable_app()
    finally:
        st.selectbox = original_selectbox
        base_app._is_price_target = original_price
