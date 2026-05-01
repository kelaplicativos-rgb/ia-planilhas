from __future__ import annotations

from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

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
MAX_FLASH_CATALOG_URLS = 160
MAX_FLASH_CATEGORY_URLS = 70
MAX_FLASH_PAGES_PER_CATEGORY = 8
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}
BAD_DISCOVERY_HINTS = (
    "login",
    "conta",
    "account",
    "checkout",
    "carrinho",
    "cart",
    "whatsapp",
    "facebook",
    "instagram",
    "youtube",
    "politica",
    "termos",
    "privacy",
    "contato",
    "atendimento",
    "blog",
    "faq",
    "javascript:",
    "mailto:",
    "tel:",
)
PRODUCT_HINTS = ("produto", "product", "/p/", "/prod/", "/item/", "products/")
CATALOG_HINTS = (
    "categoria",
    "category",
    "departamento",
    "collection",
    "collections",
    "catalogo",
    "catálogo",
    "loja",
    "produtos",
    "shop",
    "store",
)


def _safe_df(valor: Any) -> pd.DataFrame:
    if isinstance(valor, pd.DataFrame) and not valor.empty:
        return valor.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _normalizar_url(url: str) -> str:
    texto = str(url or "").strip()
    if not texto:
        return ""
    if not texto.lower().startswith(("http://", "https://")):
        texto = "https://" + texto.lstrip("/")
    parsed = urlparse(texto)
    parsed = parsed._replace(fragment="")
    return urlunparse(parsed)


def _mesmo_dominio(url: str, base_url: str) -> bool:
    try:
        host = urlparse(url).netloc.replace("www.", "").lower()
        base_host = urlparse(base_url).netloc.replace("www.", "").lower()
        return bool(host and base_host and host == base_host)
    except Exception:
        return False


def _fetch_html_leve(url: str, timeout: int = 12) -> str:
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text or ""
    except Exception:
        return ""


def _limpar_query_tracking(url: str) -> str:
    parsed = urlparse(url)
    pares = []
    for chave, valor in parse_qsl(parsed.query, keep_blank_values=True):
        chave_l = chave.lower().strip()
        if chave_l.startswith("utm_") or chave_l in {"fbclid", "gclid", "_gl"}:
            continue
        pares.append((chave, valor))
    return urlunparse(parsed._replace(query=urlencode(pares), fragment=""))


def _url_parece_catalogo(url: str, texto_link: str = "") -> bool:
    u = str(url or "").lower()
    texto = str(texto_link or "").lower()
    if not u:
        return False
    if any(bad in u for bad in BAD_DISCOVERY_HINTS):
        return False
    if any(hint in u for hint in CATALOG_HINTS) or any(hint in texto for hint in CATALOG_HINTS):
        return True
    if any(hint in u for hint in PRODUCT_HINTS):
        return False
    path = urlparse(u).path.strip("/")
    partes = [p for p in path.split("/") if p]
    if 1 <= len(partes) <= 3 and len(path) >= 3:
        return True
    return False


def _url_parece_produto(url: str) -> bool:
    u = str(url or "").lower()
    if any(bad in u for bad in BAD_DISCOVERY_HINTS):
        return False
    return any(hint in u for hint in PRODUCT_HINTS)


def _com_query_pagina(url: str, pagina: int) -> str:
    parsed = urlparse(url)
    pares = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in {"page", "pagina", "p"}]
    pares.append(("page", str(pagina)))
    return urlunparse(parsed._replace(query=urlencode(pares), fragment=""))


def _com_path_page(url: str, pagina: int) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path.lower().endswith(f"/page/{pagina}"):
        return url
    return urlunparse(parsed._replace(path=f"{path}/page/{pagina}", fragment=""))


def _descobrir_urls_catalogo(url: str, progress_callback: Callable[[int, str, int], None] | None = None, indice_url: int = 1) -> list[str]:
    """Descobre categorias/listagens antes do Flash.

    O bug principal era capturar só a primeira vitrine encontrada. Em lojas com
    milhares de itens é necessário abrir categorias e páginas de listagem. Esta
    descoberta é leve: lê menus/links da home e adiciona variações de paginação
    comuns sem entrar produto por produto.
    """
    base_url = _normalizar_url(url)
    if not base_url:
        return []

    if progress_callback:
        progress_callback(4, "FLASH AMPLO: descobrindo categorias e páginas do catálogo", indice_url)

    html = _fetch_html_leve(base_url)
    descobertas: list[str] = [base_url]
    produto_links: list[str] = []

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = str(a.get("href") or "").strip()
            texto = " ".join(a.get_text(" ", strip=True).split())
            if not href:
                continue
            absoluto = _limpar_query_tracking(urljoin(base_url, href))
            absoluto = _normalizar_url(absoluto)
            if not absoluto or not _mesmo_dominio(absoluto, base_url):
                continue
            if _url_parece_catalogo(absoluto, texto):
                descobertas.append(absoluto)
            elif _url_parece_produto(absoluto):
                produto_links.append(absoluto)

    unicas: list[str] = []
    vistos: set[str] = set()
    for item in descobertas:
        if item not in vistos:
            vistos.add(item)
            unicas.append(item)
        if len(unicas) >= MAX_FLASH_CATEGORY_URLS:
            break

    if len(unicas) <= 2 and produto_links:
        for item in produto_links[:40]:
            if item not in vistos:
                vistos.add(item)
                unicas.append(item)

    expandidas: list[str] = []
    vistos_expandidos: set[str] = set()
    for categoria in unicas:
        if categoria not in vistos_expandidos:
            vistos_expandidos.add(categoria)
            expandidas.append(categoria)
        for pagina in range(2, MAX_FLASH_PAGES_PER_CATEGORY + 1):
            for candidato in (_com_query_pagina(categoria, pagina), _com_path_page(categoria, pagina)):
                candidato = _normalizar_url(candidato)
                if candidato and candidato not in vistos_expandidos:
                    vistos_expandidos.add(candidato)
                    expandidas.append(candidato)
                if len(expandidas) >= MAX_FLASH_CATALOG_URLS:
                    break
            if len(expandidas) >= MAX_FLASH_CATALOG_URLS:
                break
        if len(expandidas) >= MAX_FLASH_CATALOG_URLS:
            break

    if progress_callback:
        progress_callback(8, f"FLASH AMPLO: {len(expandidas)} páginas de catálogo/listagem preparadas", indice_url)

    return expandidas or [base_url]


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


def _executar_flash_amplo_url(
    url: str,
    progress_callback: Callable[[int, str, int], None] | None = None,
    indice_url: int = 1,
    total_urls: int = 1,
) -> pd.DataFrame:
    paginas = _descobrir_urls_catalogo(url, progress_callback=progress_callback, indice_url=indice_url)
    frames_url: list[pd.DataFrame] = []
    total_paginas = max(1, len(paginas))

    for posicao, pagina_url in enumerate(paginas, start=1):
        if progress_callback:
            percentual = min(92, 8 + int((posicao / total_paginas) * 84))
            progress_callback(percentual, f"FLASH AMPLO: página/listagem {posicao}/{total_paginas}", indice_url)
        bruto = _executar_flash(pagina_url, progress_callback=None, indice_url=indice_url, total_urls=total_urls)
        normalizado = _normalizar_saida(bruto, pagina_url)
        if isinstance(normalizado, pd.DataFrame) and not normalizado.empty:
            normalizado["URL origem da busca"] = pagina_url
            normalizado["Modo usado"] = "Flash Amplo"
            normalizado["Motor usado"] = "FLASH_CATALOGO_AMPLO"
            frames_url.append(normalizado)

    return _juntar_resultados(frames_url)


def _executar_auto_total_url(
    url: str,
    progress_callback: Callable[[int, str, int], None] | None = None,
    indice_url: int = 1,
    total_urls: int = 1,
) -> pd.DataFrame:
    frames_url: list[pd.DataFrame] = []

    if progress_callback:
        progress_callback(2, f"FLASH AMPLO: iniciando captura de catálogo na URL {indice_url}/{total_urls}", indice_url)

    flash_amplo = _executar_flash_amplo_url(url, progress_callback=progress_callback, indice_url=indice_url, total_urls=total_urls)
    if isinstance(flash_amplo, pd.DataFrame) and not flash_amplo.empty:
        frames_url.append(flash_amplo)
        if len(flash_amplo) >= FLASH_MIN_ROWS_TO_SKIP_HEAVY:
            if progress_callback:
                progress_callback(96, f"FLASH AMPLO: {len(flash_amplo)} itens detectados no catálogo", indice_url)
            return _juntar_resultados(frames_url)

    if progress_callback:
        progress_callback(22, "FLASH amplo encontrou pouco dado; ativando reforço seletivo", indice_url)

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
    urls_lista = [_normalizar_url(url) for url in (urls or []) if str(url or "").strip()]
    urls_lista = [u for u in urls_lista if u]

    for indice, url in enumerate(urls_lista, start=1):
        try:
            if progress_callback:
                progress_callback(1, f"Iniciando URL {indice}/{len(urls_lista)}", indice)

            if motor == "AUTO_TOTAL":
                df = _executar_auto_total_url(url, progress_callback=progress_callback, indice_url=indice, total_urls=len(urls_lista))
            elif motor == "AUTO_TODOS":
                df_flash = _executar_flash_amplo_url(url, progress_callback=progress_callback, indice_url=indice, total_urls=len(urls_lista))
                if isinstance(df_flash, pd.DataFrame) and len(df_flash) >= FLASH_MIN_ROWS_TO_SKIP_HEAVY:
                    df_flash["URL origem da busca"] = url
                    df_flash["Motor usado"] = "FLASH_CATALOGO_AMPLO"
                    df = df_flash
                else:
                    preset_base = preset or PRESETS.get("Seguro") or next(iter(PRESETS.values()))
                    frames_url: list[pd.DataFrame] = []
                    if isinstance(df_flash, pd.DataFrame) and not df_flash.empty:
                        df_flash["URL origem da busca"] = url
                        df_flash["Motor usado"] = "FLASH_CATALOGO_AMPLO"
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
