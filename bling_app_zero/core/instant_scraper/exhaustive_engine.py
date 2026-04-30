from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

import pandas as pd

from .auth_fetcher import fetch_html_with_auth
from .domain_crawler import descobrir_urls_produto
from .instant_dom_engine import instant_extract
from .playwright_engine import browser_extract
from .self_healing import auto_heal_dataframe, diagnosticar_dataframe


CHECKPOINT_DIR = Path("bling_app_zero/output/site_capture_checkpoints")


@dataclass
class ExhaustiveConfig:
    max_product_urls: int = 5000
    max_base_pages: int = 300
    max_browser_pages: int = 80
    min_score: int = 45
    save_every: int = 25


@dataclass
class ExhaustiveResult:
    dataframe: pd.DataFrame = field(default_factory=pd.DataFrame)
    urls_discovered: int = 0
    urls_processed: int = 0
    status: str = ""
    checkpoint_path: str = ""


def _domain(url: str) -> str:
    try:
        host = urlparse(str(url or "").strip()).netloc.lower().replace("www.", "")
        return host or "site"
    except Exception:
        return "site"


def _checkpoint_path(url: str) -> Path:
    safe = _domain(url).replace("/", "_").replace(":", "_")
    return CHECKPOINT_DIR / f"{safe}_checkpoint.csv"


def _meta_path(url: str) -> Path:
    safe = _domain(url).replace("/", "_").replace(":", "_")
    return CHECKPOINT_DIR / f"{safe}_meta.json"


def _safe_df(df: object) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _score(df: pd.DataFrame) -> int:
    try:
        return int(diagnosticar_dataframe(df).get("score", 0))
    except Exception:
        return 0


def _normalize_final(df: pd.DataFrame, url: str, fonte: str) -> pd.DataFrame:
    base = _safe_df(df)
    if base.empty:
        return pd.DataFrame()
    base = auto_heal_dataframe(base, url)
    base = _safe_df(base)
    if base.empty:
        return pd.DataFrame()
    base["agente_estrategia"] = fonte
    base["agente_score"] = str(_score(base))
    return base.reset_index(drop=True)


def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    base = _safe_df(df)
    if base.empty:
        return pd.DataFrame()
    if "url_produto" in base.columns and "nome" in base.columns:
        return base.drop_duplicates(subset=["url_produto", "nome"], keep="first").reset_index(drop=True)
    if "URL" in base.columns:
        return base.drop_duplicates(subset=["URL"], keep="first").reset_index(drop=True)
    if "nome" in base.columns and "preco" in base.columns:
        return base.drop_duplicates(subset=["nome", "preco"], keep="first").reset_index(drop=True)
    return base.drop_duplicates(keep="first").reset_index(drop=True)


def _save_checkpoint(url: str, df: pd.DataFrame, meta: dict) -> str:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(url)
    meta_file = _meta_path(url)
    base = _safe_df(df)
    if not base.empty:
        base.to_csv(path, index=False, sep=";", encoding="utf-8-sig")
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_checkpoint(url: str) -> pd.DataFrame:
    path = _checkpoint_path(url)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    except Exception:
        return pd.DataFrame()


def _fetch(url: str, auth_context: dict | None = None) -> str:
    return fetch_html_with_auth(url, auth_context=auth_context)


def _extract_http(url: str, auth_context: dict | None = None) -> pd.DataFrame:
    html = _fetch(url, auth_context)
    if not html:
        return pd.DataFrame()
    return instant_extract(html, url, min_score=25)


def run_exhaustive_capture(
    url: str,
    *,
    auth_context: dict | None = None,
    config: ExhaustiveConfig | None = None,
    progress_callback: Callable[[int, str, int], None] | None = None,
) -> ExhaustiveResult:
    config = config or ExhaustiveConfig()
    url = str(url or "").strip()
    if not url:
        return ExhaustiveResult(status="url_vazia")

    frames: list[pd.DataFrame] = []
    processed = 0

    def progress(percent: int, message: str, total: int = 0) -> None:
        if progress_callback:
            try:
                progress_callback(percent, message, total)
            except Exception:
                pass

    checkpoint = load_checkpoint(url)
    if not checkpoint.empty:
        frames.append(checkpoint)
        progress(2, f"Checkpoint carregado com {len(checkpoint)} produto(s).", len(checkpoint))

    progress(5, "Captura exaustiva: lendo página inicial.", len(checkpoint))
    initial = _normalize_final(_extract_http(url, auth_context), url, "exhaustive_initial_http")
    if not initial.empty:
        frames.append(initial)

    browser_initial = browser_extract(url, max_clicks=20, progress_callback=progress).dataframe
    browser_initial = _normalize_final(browser_initial, url, "exhaustive_initial_browser")
    if not browser_initial.empty:
        frames.append(browser_initial)

    partial = _dedup(pd.concat(frames, ignore_index=True, sort=False)) if frames else pd.DataFrame()
    _save_checkpoint(url, partial, {"stage": "initial", "updated_at": datetime.now().isoformat(), "rows": len(partial)})

    progress(25, "Descobrindo URLs por sitemap, categorias e links internos.", len(partial))
    crawl = descobrir_urls_produto(
        url,
        lambda candidate: _fetch(candidate, auth_context),
        max_urls=int(config.max_product_urls),
        max_paginas_base=int(config.max_base_pages),
    )
    product_urls = list(dict.fromkeys(crawl.urls or []))[: int(config.max_product_urls)]

    for idx, product_url in enumerate(product_urls, start=1):
        processed = idx
        percent = 25 + int((idx / max(len(product_urls), 1)) * 70)
        progress(percent, f"Captura exaustiva: produto {idx}/{len(product_urls)}", idx)

        df_product = _normalize_final(_extract_http(product_url, auth_context), url, "exhaustive_product_http")
        if df_product.empty and idx <= int(config.max_browser_pages):
            df_product = _normalize_final(browser_extract(product_url, max_clicks=3).dataframe, url, "exhaustive_product_browser")
        if not df_product.empty:
            frames.append(df_product)

        if idx % max(1, int(config.save_every)) == 0:
            partial = _dedup(pd.concat(frames, ignore_index=True, sort=False)) if frames else pd.DataFrame()
            _save_checkpoint(
                url,
                partial,
                {
                    "stage": "processing",
                    "updated_at": datetime.now().isoformat(),
                    "processed": idx,
                    "discovered": len(product_urls),
                    "rows": len(partial),
                },
            )

    final = _dedup(pd.concat(frames, ignore_index=True, sort=False)) if frames else pd.DataFrame()
    checkpoint_path = _save_checkpoint(
        url,
        final,
        {
            "stage": "done",
            "updated_at": datetime.now().isoformat(),
            "processed": processed,
            "discovered": len(product_urls),
            "rows": len(final),
            "crawl_motivo": getattr(crawl, "motivo", ""),
        },
    )
    progress(100, f"Captura exaustiva finalizada com {len(final)} produto(s).", len(final))
    return ExhaustiveResult(
        dataframe=final,
        urls_discovered=len(product_urls),
        urls_processed=processed,
        status="ok" if not final.empty else "sem_resultado",
        checkpoint_path=checkpoint_path,
    )
