from __future__ import annotations

"""Patch vivo para o fluxo stable.

Além dos ajustes de preview/mapeamento, este patch substitui a captura antiga do
Flash Amplo direto pelo roteador novo de motores independentes:
- cadastro -> cadastro_engine;
- estoque -> estoque_engine + motor especialista de valor real + feed/XML.

Também adiciona Preview de origem nascendo fechado logo antes do mapeamento.
"""

from html import escape
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_engines import executar_motor_site_por_operacao
from bling_app_zero.stable import stable_app as base
from bling_app_zero.ui.debug_panel import add_debug_log

MAPPING_UI_VERSION = "2026-05-07-site-engines-origin-preview-v2"

_ORIGINAL_SOURCE_OPTIONS = base._source_options_for_target
_ORIGINAL_SHOW_LINE_METRICS = base._show_line_metrics
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


def _stable_modelo() -> pd.DataFrame | None:
    try:
        modelo = base.restaurar_df("stable_df_modelo")
        return modelo if isinstance(modelo, pd.DataFrame) else None
    except Exception:
        return None


def _stable_tipo(modelo: pd.DataFrame | None) -> str:
    try:
        return str(st.session_state.get("stable_tipo") or base._detect_tipo_by_model(modelo) or "cadastro")
    except Exception:
        return str(st.session_state.get("stable_tipo") or "cadastro")


def _deposito_nome() -> str:
    return str(
        st.session_state.get("stable_deposito_mapeamento")
        or st.session_state.get("deposito_nome")
        or st.session_state.get("deposito_nome_input")
        or ""
    ).strip()


def _render_preview_origem_fechado(df: pd.DataFrame) -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return
    if bool(getattr(base, "_origin_preview_rendered_current_run", False)):
        return
    base._origin_preview_rendered_current_run = True

    with st.expander("👁️ Preview de origem", expanded=False):
        st.caption(f"Origem capturada: {len(df)} linhas × {len(df.columns)} colunas. Este preview nasce fechado para não ocupar a tela.")
        st.dataframe(df.fillna(""), use_container_width=True, hide_index=True)


def _show_line_metrics_with_origin_preview(df_origem: pd.DataFrame, df_final: pd.DataFrame | None = None) -> None:
    _render_preview_origem_fechado(df_origem)
    _ORIGINAL_SHOW_LINE_METRICS(df_origem, df_final)


def _salvar_origem_site_stable(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame()
    cleaned = df.copy().fillna("")

    st.session_state["df_origem"] = cleaned.copy()
    st.session_state["df_origem_site"] = cleaned.copy()
    st.session_state["df_capturado_site"] = cleaned.copy()
    st.session_state["df_saida"] = cleaned.copy()
    st.session_state["df_precificado"] = cleaned.copy()
    st.session_state["df_preview_inteligente"] = cleaned.copy()
    st.session_state["stable_df_origem"] = cleaned.copy()
    st.session_state["stable_site_engine_capture_ok"] = bool(not cleaned.empty)
    st.session_state["stable_site_engine_rows"] = int(len(cleaned))
    st.session_state.pop("stable_df_export", None)
    st.session_state.pop("df_final", None)

    try:
        base.guardar_df("stable_df_origem", cleaned)
    except Exception:
        pass

    add_debug_log(
        "Captura stable por site salva como origem.",
        payload={"linhas": len(cleaned), "colunas": list(cleaned.columns)},
        origem="STABLE_SITE",
    )
    return cleaned


def _executar_site_por_motores_stable(
    urls: Iterable[str] | str,
    *,
    max_products: int = 5000,
    max_workers: int = 12,
    show_progress: bool = True,
) -> pd.DataFrame:
    modelo = _stable_modelo()
    tipo = _stable_tipo(modelo)

    if modelo is None or len(modelo.columns) == 0:
        st.error("Anexe primeiro o modelo Bling para o sistema saber quais campos buscar no site.")
        add_debug_log("Captura stable bloqueada: modelo ausente.", origem="STABLE_SITE")
        return pd.DataFrame()

    progress_bar = st.progress(0) if show_progress else None
    status = st.empty() if show_progress else None

    def progress_callback(percent: int, message: str, done: int = 0) -> None:
        if not show_progress:
            return
        try:
            progress_value = max(0.0, min(1.0, float(percent or 0) / 100.0))
        except Exception:
            progress_value = 0.0
        if progress_bar is not None:
            progress_bar.progress(progress_value)
        if status is not None:
            status.caption(str(message or "Processando captura por site..."))

    add_debug_log(
        "Captura stable por site roteada para motores independentes.",
        payload={"tipo": tipo, "colunas_modelo": list(modelo.columns), "max_products": max_products, "max_workers": max_workers},
        origem="STABLE_SITE",
    )

    df = executar_motor_site_por_operacao(
        urls,
        model_df=modelo,
        operation=tipo,
        deposito_nome=_deposito_nome(),
        progress_callback=progress_callback,
        max_products=max_products,
        max_workers=max_workers,
        show_progress=show_progress,
    )

    cleaned = _salvar_origem_site_stable(df)

    if show_progress:
        if progress_bar is not None:
            progress_bar.progress(1.0)
        if status is not None:
            if cleaned.empty:
                status.warning("Captura por site finalizada, mas nenhuma linha foi encontrada.")
            else:
                status.success(f"Captura por site concluída: {len(cleaned)} linha(s) prontas para mapeamento.")

    return cleaned


def run_stable_app() -> None:
    base._live_mapping_counter = 0
    base._origin_preview_rendered_current_run = False
    base._render_source_preview = _render_source_preview_real
    base._selectbox_mapping = _selectbox_mapping_live
    base._source_options_for_target = _source_options_allow_id
    base._show_line_metrics = _show_line_metrics_with_origin_preview
    base.executar_flash_amplo_pagina_por_pagina = _executar_site_por_motores_stable
    base.MAPPING_UI_VERSION = MAPPING_UI_VERSION
    base.run_stable_app()
