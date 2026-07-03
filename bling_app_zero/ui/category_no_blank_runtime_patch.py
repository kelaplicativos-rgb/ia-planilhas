from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.category_intelligence import PROVISIONAL_CATEGORY
from bling_app_zero.ui.mapping_visibility_runtime import install_mapping_visibility_runtime

RESPONSIBLE_FILE = 'bling_app_zero/ui/category_no_blank_runtime_patch.py'
PATCH_ATTR = '_mapeiaai_category_no_blank_runtime_patch_v1'


def _audit(event: str, **details: object) -> None:
    try:
        add_audit_event(event, area='UNIVERSAL', status='OK', details={'responsible_file': RESPONSIBLE_FILE, **details})
    except Exception:
        pass


def _valid_df(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty and len(value.columns) > 0


def _first_existing_column(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for column in candidates:
        if column in df.columns:
            return column
    return ''


def _count_unclassified(df: pd.DataFrame, category_col: str) -> int:
    if not category_col or category_col not in df.columns:
        return 0
    values = df[category_col].fillna('').astype(str).str.strip()
    return int((values == PROVISIONAL_CATEGORY).sum())


def install_category_no_blank_runtime_patch() -> bool:
    install_mapping_visibility_runtime()
    try:
        from bling_app_zero.ui import universal_category_simple_apply_runtime as runtime
    except Exception as exc:
        _audit('category_no_blank_runtime_import_failed', error=str(exc)[:220])
        return False

    if getattr(runtime, PATCH_ATTR, False):
        return False

    original_apply = getattr(runtime, 'apply_category_suggestions', None)
    if callable(original_apply):
        def apply_category_suggestions_no_blank(*args: Any, **kwargs: Any):
            kwargs['fallback_unclassified'] = True
            return original_apply(*args, **kwargs)

        runtime.apply_category_suggestions = apply_category_suggestions_no_blank

    def render_category_live_preview_no_blank(
        df: pd.DataFrame,
        *,
        applied: int,
        total: int,
        revisar: int,
        openai_applied: int = 0,
    ) -> None:
        if not _valid_df(df):
            return
        category_col = runtime.CATEGORY_COL if runtime.CATEGORY_COL in df.columns else _first_existing_column(df, ('Categoria', 'categoria', 'Categoria Produto', 'Nome da categoria', 'category'))
        if not category_col:
            return
        product_col = _first_existing_column(df, runtime.PRODUCT_COLUMNS)
        code_col = _first_existing_column(df, runtime.CODE_COLUMNS)
        columns: list[str] = []
        for column in (product_col, code_col, category_col):
            if column and column in df.columns and column not in columns:
                columns.append(column)
        if not columns:
            return
        preview = df.loc[:, columns].head(20).copy().fillna('')
        unclassified = _count_unclassified(df, category_col)
        st.markdown('##### Resultado ao vivo')
        extra = f' OpenAI real recuperou {openai_applied} categoria(s).' if openai_applied else ''
        st.success(f'Categorização automática pronta: {total} produto(s), {applied} categoria(s) preenchida(s)/corrigida(s).{extra}')
        if unclassified or revisar:
            qty = max(int(unclassified), int(revisar or 0))
            st.info(f'{qty} produto(s) sem categoria real foram enviados para **Produtos não classificados**.')
        st.dataframe(preview, use_container_width=True, hide_index=True, height=min(520, 72 + (len(preview) * 35)))

    runtime._render_category_live_preview = render_category_live_preview_no_blank
    setattr(runtime, PATCH_ATTR, True)
    _audit('category_no_blank_runtime_patch_installed', fallback_unclassified_forced=True, preview_message_fixed=True, mapping_visibility_runtime=True)
    return True


__all__ = ['install_category_no_blank_runtime_patch']
