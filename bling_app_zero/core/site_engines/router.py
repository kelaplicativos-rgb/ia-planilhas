from __future__ import annotations

from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.site_engines.cadastro_engine import executar_site_cadastro_engine
from bling_app_zero.core.site_engines.estoque_engine import executar_site_estoque_engine
from bling_app_zero.core.site_engines.model_columns import detect_operation_from_model, get_requested_columns, operation_label

ProgressCallback = Callable[..., None]


def executar_motor_site_por_operacao(
    urls: Iterable[str] | str,
    *,
    model_df: pd.DataFrame | None,
    operation: str = "",
    deposito_nome: str = "",
    progress_callback: ProgressCallback | None = None,
    max_products: int = 500,
    max_workers: int = 12,
    show_progress: bool = True,
) -> pd.DataFrame:
    requested_columns = get_requested_columns(model_df)
    if not requested_columns:
        return pd.DataFrame()

    detected_operation = detect_operation_from_model(model_df, fallback=operation or "cadastro")

    if progress_callback:
        progress_callback(1, f"Motor selecionado: {operation_label(detected_operation)}", 1)

    if detected_operation == "estoque":
        return executar_site_estoque_engine(
            urls,
            model_df=model_df,
            deposito_nome=deposito_nome,
            progress_callback=progress_callback,
            max_products=max_products,
            max_workers=max_workers,
            show_progress=show_progress,
        )

    return executar_site_cadastro_engine(
        urls,
        model_df=model_df,
        progress_callback=progress_callback,
        max_products=max_products,
        max_workers=max_workers,
        show_progress=show_progress,
    )
