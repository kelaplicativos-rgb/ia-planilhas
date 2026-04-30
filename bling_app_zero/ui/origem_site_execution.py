from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.instant_scraper import run_scraper
from bling_app_zero.core.instant_scraper.exhaustive_engine import run_exhaustive_capture
from bling_app_zero.core.site_crawler import crawl_site
from bling_app_zero.ui.origem_site_config import (
    ScraperPreset,
    config_from_preset,
    exhaustive_config_from_preset,
)
from bling_app_zero.ui.site_auth_panel import get_site_auth_context
from bling_app_zero.ui.site_capture_normalizer import normalizar_captura_site_para_bling


def _safe_df(valor: Any) -> pd.DataFrame:
    if isinstance(valor, pd.DataFrame) and not valor.empty:
        return valor.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _normalizar_saida(df: pd.DataFrame, url: str) -> pd.DataFrame:
    base = _safe_df(df)
    if base.empty:
        return pd.DataFrame()

    normalizado = normalizar_captura_site_para_bling(base)
    if isinstance(normalizado, pd.DataFrame) and not normalizado.empty:
        normalizado["URL origem da busca"] = normalizado.get("URL origem da busca", "").replace("", url)
        return normalizado.fillna("").reset_index(drop=True)

    base["URL origem da busca"] = url
    return base.fillna("").reset_index(drop=True)


def _executar_exaustivo(url: str, preset: ScraperPreset, progress_callback: Callable[[int, str, int], None] | None = None) -> pd.DataFrame:
    auth_context = get_site_auth_context()
    resultado = run_exhaustive_capture(
        url,
        auth_context=auth_context,
        config=exhaustive_config_from_preset(preset),
        progress_callback=progress_callback,
    )
    df = _safe_df(resultado.dataframe)
    if not df.empty:
        df["origem_site_status"] = resultado.status
        df["origem_site_checkpoint"] = resultado.checkpoint_path
        df["origem_site_urls_descobertas"] = str(resultado.urls_discovered)
        df["origem_site_urls_processadas"] = str(resultado.urls_processed)
    return df


def _executar_agente_rapido(url: str, preset: ScraperPreset) -> pd.DataFrame:
    try:
        return _safe_df(run_scraper(url, config=exhaustive_config_from_preset(preset)))
    except TypeError:
        return _safe_df(run_scraper(url))
    except Exception:
        return pd.DataFrame()


def _executar_fallback(url: str, preset: ScraperPreset) -> pd.DataFrame:
    try:
        return _safe_df(crawl_site(url, config_from_preset(preset)))
    except TypeError:
        return _safe_df(crawl_site(url))
    except Exception:
        return pd.DataFrame()


def executar_busca(
    urls,
    preset: ScraperPreset,
    motor: str,
    progress_callback: Callable[[int, str, int], None] | None = None,
) -> pd.DataFrame:
    resultados: list[pd.DataFrame] = []
    urls_lista = [str(url or "").strip() for url in (urls or []) if str(url or "").strip()]

    for indice, url in enumerate(urls_lista, start=1):
        try:
            if progress_callback:
                progress_callback(1, f"Iniciando URL {indice}/{len(urls_lista)}", indice)

            if motor == "Exaustivo com checkpoint":
                df = _executar_exaustivo(url, preset, progress_callback=progress_callback)
            elif motor == "Agente rápido":
                df = _executar_agente_rapido(url, preset)
            elif motor == "Fallback crawler":
                df = _executar_fallback(url, preset)
            else:
                df = _executar_exaustivo(url, preset, progress_callback=progress_callback)

            df = _normalizar_saida(df, url)
        except Exception:
            df = pd.DataFrame()

        if isinstance(df, pd.DataFrame) and not df.empty:
            df["URL origem da busca"] = url
            resultados.append(df)

    if not resultados:
        return pd.DataFrame()

    saida = pd.concat(resultados, ignore_index=True, sort=False).fillna("")
    return saida.drop_duplicates(keep="first").reset_index(drop=True)
