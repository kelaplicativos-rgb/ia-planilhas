from __future__ import annotations

from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.site_engines.field_resolver import build_model_limited_dataframe
from bling_app_zero.core.site_engines.model_columns import get_requested_columns
from bling_app_zero.ui.flash_amplo_execution import executar_flash_amplo_pagina_por_pagina

ProgressCallback = Callable[..., None]


def executar_site_cadastro_engine(
    urls: Iterable[str] | str,
    *,
    model_df: pd.DataFrame | None,
    progress_callback: ProgressCallback | None = None,
    max_products: int = 500,
    max_workers: int = 12,
    show_progress: bool = True,
) -> pd.DataFrame:
    requested_columns = get_requested_columns(model_df)
    if not requested_columns:
        return pd.DataFrame()

    if progress_callback:
        progress_callback(1, "Cadastro: lendo paginas de produto", 1)

    raw_df = executar_flash_amplo_pagina_por_pagina(
        urls,
        max_products=max_products,
        max_workers=max_workers,
        show_progress=show_progress,
    )

    if raw_df.empty:
        return pd.DataFrame(columns=requested_columns)

    if progress_callback:
        progress_callback(85, "Cadastro: montando resultado nas colunas do modelo", 1)

    limited = build_model_limited_dataframe(
        raw_df,
        requested_columns,
        operation="cadastro",
        deposito_nome="",
    )

    if progress_callback:
        progress_callback(100, "Cadastro: finalizado", 1)

    return limited.fillna("")
