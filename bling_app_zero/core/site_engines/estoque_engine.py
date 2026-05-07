from __future__ import annotations

from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.site_engines.estoque_fast_crawler import crawl_estoque_fast_dataframe
from bling_app_zero.core.site_engines.field_resolver import build_model_limited_dataframe, requested_field_profile
from bling_app_zero.core.site_engines.model_columns import get_requested_columns
from bling_app_zero.ui.debug_panel import add_debug_log

ProgressCallback = Callable[..., None]


def _normalize_urls(urls: Iterable[str] | str) -> list[str]:
    if isinstance(urls, str):
        raw_items = urls.replace("\r", "\n").split("\n")
    else:
        raw_items = list(urls)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        url = str(item or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized


def _adapt_progress(callback: ProgressCallback | None) -> Callable[[int, int, str], None] | None:
    if not callable(callback):
        return None

    def _inner(done: int, total: int, url: str) -> None:
        total_safe = max(1, int(total or 1))
        percent = min(94, max(2, int((int(done or 0) / total_safe) * 90)))
        callback(percent, f"Estoque exclusivo: {done}/{total_safe} páginas lidas", int(done or 0))

    return _inner


def executar_site_estoque_engine(
    urls: Iterable[str] | str,
    *,
    model_df: pd.DataFrame | None,
    deposito_nome: str = "",
    progress_callback: ProgressCallback | None = None,
    max_products: int = 500,
    max_workers: int = 12,
    show_progress: bool = True,
) -> pd.DataFrame:
    requested_columns = get_requested_columns(model_df)
    if not requested_columns:
        add_debug_log("Estoque engine bloqueado: modelo sem colunas.", origem="ESTOQUE_ENGINE")
        return pd.DataFrame()

    seed_urls = _normalize_urls(urls)
    if not seed_urls:
        add_debug_log("Estoque engine bloqueado: nenhuma URL válida.", origem="ESTOQUE_ENGINE")
        return pd.DataFrame(columns=requested_columns)

    requested_fields = requested_field_profile(requested_columns, operation="estoque")
    add_debug_log(
        "Estoque engine exclusivo iniciado.",
        payload={
            "urls": len(seed_urls),
            "colunas_modelo": requested_columns,
            "campos_extraidos": sorted(requested_fields),
            "crawler": "estoque_fast_crawler",
            "max_products": max_products,
            "max_workers": max_workers,
        },
        origem="ESTOQUE_ENGINE",
    )

    if progress_callback:
        campos = ", ".join(sorted(requested_fields)) or "somente campos manuais"
        progress_callback(1, f"Estoque exclusivo: buscando somente: {campos}", 1)

    raw_df = crawl_estoque_fast_dataframe(
        seed_urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=_adapt_progress(progress_callback),
        requested_fields=requested_fields,
    )

    if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
        add_debug_log("Estoque engine exclusivo finalizado sem linhas capturadas.", origem="ESTOQUE_ENGINE")
        return pd.DataFrame(columns=requested_columns)

    if progress_callback:
        progress_callback(96, "Estoque exclusivo: preenchendo exatamente o modelo", len(raw_df))

    limited = build_model_limited_dataframe(
        raw_df,
        requested_columns,
        operation="estoque",
        deposito_nome=deposito_nome,
    )

    add_debug_log(
        "Estoque engine exclusivo finalizado.",
        payload={"linhas_brutas": len(raw_df), "linhas_finais": len(limited), "colunas_finais": list(limited.columns)},
        origem="ESTOQUE_ENGINE",
    )

    if progress_callback:
        progress_callback(100, "Estoque exclusivo: finalizado", len(limited))

    return limited.fillna("")
