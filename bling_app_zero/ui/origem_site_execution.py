from __future__ import annotations

import pandas as pd

from bling_app_zero.core.instant_scraper import run_scraper
from bling_app_zero.core.site_crawler import crawl_site


def executar_busca(urls, preset, motor) -> pd.DataFrame:
    resultados = []

    for url in urls:
        try:
            if motor == "Agente rápido":
                df = run_scraper(url)
            elif motor == "Fallback crawler":
                df = crawl_site(url)
            else:
                df = crawl_site(url)
        except Exception:
            df = pd.DataFrame()

        if isinstance(df, pd.DataFrame) and not df.empty:
            df["URL origem da busca"] = url
            resultados.append(df)

    if not resultados:
        return pd.DataFrame()

    return pd.concat(resultados, ignore_index=True)
