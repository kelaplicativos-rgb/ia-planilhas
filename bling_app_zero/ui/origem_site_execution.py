from __future__ import annotations

"""Executor único da captura por site.

Regra atual:
- A planilha modelo manda na captura.
- Cadastro e Atualização de estoque usam motores independentes.
- Estoque por site NÃO chama Flash Amplo legado.
- A busca por site retorna somente as colunas solicitadas pelo modelo Bling.
- Campo solicitado e não encontrado fica vazio.

Este arquivo mantém aliases antigos para não quebrar telas que importam nomes
legados, mas todos os aliases apontam para `executar_captura_site`, que chama
exclusivamente `executar_motor_site_por_operacao`.
"""

from typing import Any, Callable, Iterable

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_engines import executar_motor_site_por_operacao
from bling_app_zero.ui.debug_panel import add_debug_log


def _extract_urls_from_args(*args: Any, **kwargs: Any) -> Iterable[str] | str:
    for key in (
        "urls",
        "seed_urls",
        "site_urls",
        "product_urls",
        "links",
        "url",
        "site_url",
        "categoria_url",
        "category_url",
    ):
        value = kwargs.get(key)
        if value:
            return value

    for arg in args:
        if isinstance(arg, (str, list, tuple, set)):
            return arg

    value = st.session_state.get("urls_site") or st.session_state.get("site_urls") or st.session_state.get("url_site")
    return value or []


def _extract_model_df(kwargs: dict[str, Any]) -> pd.DataFrame | None:
    for key in ("model_df", "df_modelo", "modelo_df", "modelo_bling"):
        value = kwargs.get(key)
        if isinstance(value, pd.DataFrame):
            return value
    for key in ("df_modelo", "stable_df_modelo", "modelo_bling_df"):
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame):
            return value
    return None


def _extract_progress_callback(kwargs: dict[str, Any]) -> Callable[..., None] | None:
    callback = kwargs.get("progress_callback") or kwargs.get("callback_progresso")
    return callback if callable(callback) else None


def _save_capture_state(df: pd.DataFrame) -> None:
    cleaned = df.copy().fillna("") if isinstance(df, pd.DataFrame) else pd.DataFrame()
    st.session_state["df_origem"] = cleaned.copy()
    st.session_state["df_origem_site"] = cleaned.copy()
    st.session_state["df_capturado_site"] = cleaned.copy()
    st.session_state["df_saida"] = cleaned.copy()
    st.session_state["df_precificado"] = cleaned.copy()
    st.session_state["df_preview_inteligente"] = cleaned.copy()
    st.session_state["df_preview_site_modelo_bling"] = cleaned.copy()
    st.session_state["origem_site_preview_modelo_bling"] = True
    st.session_state.pop("df_final", None)


def executar_captura_site(*args: Any, **kwargs: Any) -> pd.DataFrame:
    urls = _extract_urls_from_args(*args, **kwargs)
    model_df = _extract_model_df(kwargs)
    operation = str(
        kwargs.get("operation")
        or kwargs.get("tipo_operacao")
        or st.session_state.get("modelo_bling_tipo_reconhecido")
        or st.session_state.get("tipo_operacao")
        or st.session_state.get("stable_tipo")
        or "cadastro"
    ).strip().lower()
    deposito_nome = str(
        kwargs.get("deposito_nome")
        or st.session_state.get("stable_deposito_mapeamento")
        or st.session_state.get("deposito_nome")
        or st.session_state.get("deposito_nome_input")
        or ""
    ).strip()
    max_products = int(kwargs.get("max_products") or kwargs.get("limite") or kwargs.get("limit") or 500)
    max_workers = int(kwargs.get("max_workers") or kwargs.get("workers") or 12)
    show_progress = bool(kwargs.get("show_progress", True))
    progress_callback = _extract_progress_callback(kwargs)

    if model_df is None or len(model_df.columns) == 0:
        st.error("Anexe primeiro a planilha modelo do Bling para a captura por site saber quais campos buscar.")
        add_debug_log("Captura por site bloqueada: modelo ausente.", origem="SITE_EXECUTION")
        return pd.DataFrame()

    add_debug_log(
        "Captura por site usando somente roteador novo.",
        payload={"operation": operation, "colunas_modelo": list(model_df.columns), "max_products": max_products, "max_workers": max_workers},
        origem="SITE_EXECUTION",
    )

    df = executar_motor_site_por_operacao(
        urls,
        model_df=model_df,
        operation=operation,
        deposito_nome=deposito_nome,
        progress_callback=progress_callback,
        max_products=max_products,
        max_workers=max_workers,
        show_progress=show_progress,
    )

    if isinstance(df, pd.DataFrame):
        _save_capture_state(df)

    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


# Aliases legados mantidos, todos apontando para o motor novo.
execute_site_capture = executar_captura_site
executar_site_capture = executar_captura_site
run_site_capture = executar_captura_site
capturar_site = executar_captura_site
capturar_produtos_site = executar_captura_site
executar_captura_por_site = executar_captura_site
executar_origem_site = executar_captura_site
run_origem_site = executar_captura_site
executar_busca = executar_captura_site
run = executar_captura_site
main = executar_captura_site


def __getattr__(name: str) -> Callable[..., pd.DataFrame]:
    lowered = name.lower()
    if any(token in lowered for token in ("busca", "captura", "capture", "crawler", "site", "produto", "product", "run", "execut")):
        return executar_captura_site
    if "flash" in lowered:
        raise AttributeError(f"{name} foi removido deste executor; use executar_captura_site")
    raise AttributeError(name)


__all__ = [
    "executar_captura_site",
    "execute_site_capture",
    "executar_site_capture",
    "run_site_capture",
    "capturar_site",
    "capturar_produtos_site",
    "executar_captura_por_site",
    "executar_origem_site",
    "run_origem_site",
    "executar_busca",
    "run",
    "main",
]
