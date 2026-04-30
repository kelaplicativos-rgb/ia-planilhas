from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.instant_scraper import run_flash, run_scraper
from bling_app_zero.core.instant_scraper.exhaustive_engine import run_exhaustive_capture
from bling_app_zero.core.site_crawler import crawl_site
from bling_app_zero.ui.origem_site_config import (
    MOTOR_EXAUSTIVO,
    MOTOR_FALLBACK,
    MOTOR_GOD,
    MOTOR_RAPIDO,
    MOTORES_SITE,
    PRESETS,
    ScraperPreset,
    config_from_preset,
    exhaustive_config_from_preset,
)
from bling_app_zero.ui.site_auth_panel import get_site_auth_context
from bling_app_zero.ui.site_capture_normalizer import normalizar_captura_site_para_bling

FLASH_MIN_ROWS_TO_SKIP_HEAVY = 8


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


def _executar_flash(
    url: str,
    progress_callback: Callable[[int, str, int], None] | None = None,
    indice_url: int = 1,
    total_urls: int = 1,
) -> pd.DataFrame:
    try:
        df = run_flash(
            url,
            progress_callback=progress_callback,
            indice_url=indice_url,
            total_urls=total_urls,
        )
    except Exception:
        df = pd.DataFrame()

    base = _safe_df(df)
    if not base.empty:
        base["origem_site_status"] = base.get("origem_site_status", "flash_ok").replace("", "flash_ok")
        base["origem_site_motor"] = base.get("origem_site_motor", "FLASH_INSTANT").replace("", "FLASH_INSTANT")
    return base


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


def _executar_auto_total_url(
    url: str,
    progress_callback: Callable[[int, str, int], None] | None = None,
    indice_url: int = 1,
    total_urls: int = 1,
) -> pd.DataFrame:
    frames_url: list[pd.DataFrame] = []

    if progress_callback:
        progress_callback(2, f"FLASH: iniciando captura instantânea na URL {indice_url}/{total_urls}", indice_url)

    flash = _normalizar_saida(_executar_flash(url, progress_callback, indice_url, total_urls), url)
    if isinstance(flash, pd.DataFrame) and not flash.empty:
        flash["URL origem da busca"] = url
        flash["Modo usado"] = "Flash Instant"
        flash["Motor usado"] = "FLASH_INSTANT"
        frames_url.append(flash)

        if len(flash) >= FLASH_MIN_ROWS_TO_SKIP_HEAVY:
            if progress_callback:
                progress_callback(96, f"FLASH: {len(flash)} produtos detectados; pulando motores pesados", indice_url)
            return _juntar_resultados(frames_url)

    if progress_callback:
        progress_callback(22, "FLASH encontrou pouco dado; ativando reforço seletivo", indice_url)

    preset_reforco = PRESETS.get("Seguro") or next(iter(PRESETS.values()))
    for motor_atual in (MOTOR_RAPIDO, MOTOR_FALLBACK):
        if progress_callback:
            progress_callback(35, f"Reforço seletivo {motor_atual} na URL {indice_url}/{total_urls}", indice_url)
        bruto = _executar_motor(url, preset_reforco, motor_atual, progress_callback=progress_callback)
        normalizado = _normalizar_saida(bruto, url)
        if isinstance(normalizado, pd.DataFrame) and not normalizado.empty:
            normalizado["URL origem da busca"] = url
            normalizado["Modo usado"] = "Reforço seletivo"
            normalizado["Motor usado"] = motor_atual
            frames_url.append(normalizado)

    return _juntar_resultados(frames_url)


def executar_busca(
    urls,
    preset: ScraperPreset | None,
    motor: str,
    progress_callback: Callable[[int, str, int], None] | None = None,
) -> pd.DataFrame:
    resultados: list[pd.DataFrame] = []
    urls_lista = [str(url or "").strip() for url in (urls or []) if str(url or "").strip()]

    for indice, url in enumerate(urls_lista, start=1):
        try:
            if progress_callback:
                progress_callback(1, f"Iniciando URL {indice}/{len(urls_lista)}", indice)

            if motor == "AUTO_TOTAL":
                df = _executar_auto_total_url(url, progress_callback=progress_callback, indice_url=indice, total_urls=len(urls_lista))
            elif motor == "AUTO_TODOS":
                df_flash = _normalizar_saida(_executar_flash(url, progress_callback, indice, len(urls_lista)), url)
                if isinstance(df_flash, pd.DataFrame) and len(df_flash) >= FLASH_MIN_ROWS_TO_SKIP_HEAVY:
                    df_flash["URL origem da busca"] = url
                    df_flash["Motor usado"] = "FLASH_INSTANT"
                    df = df_flash
                else:
                    preset_base = preset or PRESETS.get("Seguro") or next(iter(PRESETS.values()))
                    frames_url: list[pd.DataFrame] = []
                    if isinstance(df_flash, pd.DataFrame) and not df_flash.empty:
                        df_flash["URL origem da busca"] = url
                        df_flash["Motor usado"] = "FLASH_INSTANT"
                        frames_url.append(df_flash)
                    for motor_atual in (MOTOR_RAPIDO, MOTOR_FALLBACK):
                        if progress_callback:
                            progress_callback(5, f"Executando {motor_atual} na URL {indice}/{len(urls_lista)}", indice)
                        bruto = _executar_motor(url, preset_base, motor_atual, progress_callback=progress_callback)
                        normalizado = _normalizar_saida(bruto, url)
                        if isinstance(normalizado, pd.DataFrame) and not normalizado.empty:
                            normalizado["URL origem da busca"] = url
                            normalizado["Motor usado"] = motor_atual
                            frames_url.append(normalizado)
                    df = _juntar_resultados(frames_url)
            else:
                preset_base = preset or PRESETS.get("Seguro") or next(iter(PRESETS.values()))
                bruto = _executar_motor(url, preset_base, motor, progress_callback=progress_callback)
                df = _normalizar_saida(bruto, url)
        except Exception:
            df = pd.DataFrame()

        if isinstance(df, pd.DataFrame) and not df.empty:
            df["URL origem da busca"] = url
            resultados.append(df)

    return _juntar_resultados(resultados)
