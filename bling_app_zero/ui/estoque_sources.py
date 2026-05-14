from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.flows.site_as_source import get_site_source_for_operation
from bling_app_zero.ui.home_shared import read_upload_fast
from bling_app_zero.ui.smart_upload import render_smart_upload_box


def file_name(file: Any) -> str:
    return str(getattr(file, 'name', 'arquivo')).strip()


def safe_read_source(file: Any) -> pd.DataFrame | None:
    try:
        return read_upload_fast(file)
    except Exception as exc:
        st.warning(f'Não consegui ler {file_name(file)}: {exc}')
        return None


def source_files_from_upload(upload) -> list[Any]:
    attachments = list(upload.attachments or [])
    if not attachments:
        return []

    sources: list[Any] = []
    for file in attachments:
        if upload.model_file is not None and file is upload.model_file:
            continue
        if upload.cadastro_model_file is not None and file is upload.cadastro_model_file:
            continue
        if upload.estoque_model_file is not None and file is upload.estoque_model_file:
            continue
        sources.append(file)

    if not sources and upload.source_file is not None:
        sources.append(upload.source_file)

    return sources


def get_estoque_site_source() -> pd.DataFrame | None:
    df_origem_site = get_site_source_for_operation('estoque')
    return df_origem_site if isinstance(df_origem_site, pd.DataFrame) else None


def render_estoque_upload(home_model_loaded: bool):
    return render_smart_upload_box(
        title='📎 Origem do estoque',
        operation='estoque',
        key='smart_upload_estoque',
        allow_model=not home_model_loaded,
        required_model=not home_model_loaded,
        accepted_types=['xlsx', 'xls', 'csv', 'html', 'htm', 'mht', 'mhtml'],
    )
