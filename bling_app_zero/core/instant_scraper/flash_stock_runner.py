from __future__ import annotations

import pandas as pd

from .flash_scraper import run_flash_scraper as _base_run_flash_scraper
from .flash_stock_probe import enrich_dataframe_with_real_stock


def run_flash_scraper(
    url: str,
    progress_callback=None,
    indice_url: int = 1,
    total_urls: int = 1,
    simular_estoque_real: bool = True,
    limite_produtos_estoque: int = 120,
    *args,
    **kwargs,
) -> pd.DataFrame:
    """
    FLASH POINT HARD CORE.

    Executa o flash scraper atual e, em seguida, entra nas URLs dos produtos
    para tentar detectar o estoque real por HTML/JSON-LD/texto da página.

    Proteções:
    - limite máximo de produtos por rodada;
    - timeout individual no probe;
    - sem loop infinito;
    - se não encontrar estoque real, mantém a linha e registra a origem.
    """
    try:
        df = _base_run_flash_scraper(
            url,
            progress_callback=progress_callback,
            indice_url=indice_url,
            total_urls=total_urls,
        )
    except TypeError:
        df = _base_run_flash_scraper(url)
    except Exception:
        return pd.DataFrame()

    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    if not simular_estoque_real:
        return df

    try:
        return enrich_dataframe_with_real_stock(
            df,
            origem_url=url,
            progress_callback=progress_callback,
            indice_url=indice_url,
            max_products=limite_produtos_estoque,
        )
    except Exception:
        df = df.copy()
        df["Estoque real"] = ""
        df["origem_estoque_real"] = "erro_probe_estoque"
        return df
