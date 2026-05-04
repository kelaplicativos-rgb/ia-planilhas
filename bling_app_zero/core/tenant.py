from __future__ import annotations

import hashlib
import os
import re

import streamlit as st


def _slug(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "default"


def get_workspace_id() -> str:
    raw = (
        st.session_state.get("workspace_id")
        or st.query_params.get("workspace")
        or os.getenv("BLING_WORKSPACE")
        or "default"
    )
    return _slug(str(raw))


def set_workspace_id(value: str) -> str:
    workspace = _slug(value)
    st.session_state["workspace_id"] = workspace
    return workspace


def workspace_hash(workspace_id: str) -> str:
    return hashlib.sha1(workspace_id.encode("utf-8")).hexdigest()[:10]
