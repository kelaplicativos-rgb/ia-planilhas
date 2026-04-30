from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.instant_scraper import run_scraper
from bling_app_zero.core.instant_scraper.exhaustive_engine import run_exhaustive_capture
from bling_app_zero.core.site_crawler import crawl_site
from bling_app_zero.ui.origem_site_config import (
    MOTOR_EXAUSTIVO,
    MOTOR_FALLBACK,
    MOTOR_GOD,
    MOTOR_RAPIDO,
    MOTORES_SITE,
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


def _executar_god(url: str, preset: ScraperPreset, progress_callback: Callable[[int, str, int], None] | None = None) -> pd.DataFrame:
    auth_context = get_site_auth_context()
    try:
        df = run_scraper(
            url,
            auth_context=auth_context,
            config=exhaustive_config_from_preset(preset),
            progress_callback=progress_callback,
        )
    except TypeError:
        try:
            df = run_scraper(url, auth_context=auth_context)
        except TypeError:
            df = run_scraper(url)
    except Exception:
        df = pd.DataFrame()

    base = _safe_df(df)
    if not base.empty:
        base["origem_site_status"] = "blinggod_ok"
        base["origem_site_motor"] = MOTOR_GOD
    return base


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
        df["origem_site_motor"] = MOTOR_EXAUSTIVO
        df["origem_site_checkpoint"] = resultado.checkpoint_path
        df["origem_site_urls_descobertas"] = str(resultado.urls_discovered)
        df["origem_site_urls_processadas"] = str(resultado.urls_processed)
    return df


def _executar_agente_rapido(url: str, preset: ScraperPreset) -> pd.DataFrame:
    try:
        df = run_scraper(url, config=exhaustive_config_from_preset(preset))
    except TypeError:
        df = run_scraper(url)
    except Exception:
        df = pd.DataFrame()

    base = _safe_df(df)
    if not base.empty:
        base["origem_site_status"] = "agente_rapido_ok"
        base["origem_site_motor"] = MOTOR_RAPIDO
    return base


def _executar_fallback(url: str, preset: ScraperPreset) -> pd.DataFrame:
    try:
        df = crawl_site(url, config_from_preset(preset))
    except TypeError:
        df = crawl_site(url)
    except Exception:
        df = pd.DataFrame()

    base = _safe_df(df)
    if not base.empty:
        base["origem_site_status"] = "fallback_ok"
        base["origem_site_motor"] = MOTOR_FALLBACK
    return base


def _executar_motor(
    url: str,
    preset: ScraperPreset,
    motor: str,
    progress_callback: Callable[[int, str, int], None] | None = None,
) -> pd.DataFrame:
    if motor == MOTOR_GOD:
        return _executar_god(url, preset, progress_callback=progress_callback)
    if motor == MOTOR_EXAUSTIVO:
        return _executar_exaustivo(url, preset, progress_callback=progress_callback)
    if motor == MOTOR_RAPIDO:
        return _executar_agente_rapido(url, preset)
    if motor == MOTOR_FALLBACK:
        return _executar_fallback(url, preset)
    return _executar_god(url, preset, progress_callback=progress_callback)


def _chave_dedup(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    candidatos = [
        "Código",
        "SKU",
        "GTIN",
        "GTIN/EAN",
        "url_produto",
        "URL",
        "URL origem da busca",
        "Descrição",
        "Nome",
        "descricao",
        "nome",
    ]
    return [c for c in candidatos if c in df.columns]


def _juntar_resultados(resultados: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [_safe_df(df) for df in resultados if isinstance(df, pd.DataFrame) and not df.empty]
    if not frames:
        return pd.DataFrame()
    saida = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    chaves = _chave_dedup(saida)
    if chaves:
        saida = saida.drop_duplicates(subset=chaves, keep="first")
    else:
        saida = saida.drop_duplicates(keep="first")
    return saida.reset_index(drop=True)


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

            if motor == "AUTO_TODOS":
                frames_url: list[pd.DataFrame] = []
                for motor_atual in MOTORES_SITE:
                    if progress_callback:
                        progress_callback(5, f"Executando {motor_atual} na URL {indice}/{len(urls_lista)}", indice)
                    bruto = _executar_motor(url, preset, motor_atual, progress_callback=progress_callback)
                    normalizado = _normalizar_saida(bruto, url)
                    if isinstance(normalizado, pd.DataFrame) and not normalizado.empty:
                        normalizado["URL origem da busca"] = url
                        normalizado["Motor usado"] = motor_atual
                        frames_url.append(normalizado)
                df = _juntar_resultados(frames_url)
            else:
                bruto = _executar_motor(url, preset, motor, progress_callback=progress_callback)
                df = _normalizar_saida(bruto, url)
        except Exception:
            df = pd.DataFrame()

        if isinstance(df, pd.DataFrame) and not df.empty:
            df["URL origem da busca"] = url
            resultados.append(df)

    return _juntar_resultados(resultados)
