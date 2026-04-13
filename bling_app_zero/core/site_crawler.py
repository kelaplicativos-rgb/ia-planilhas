from __future__ import annotations

import pandas as pd

from bling_app_zero.core.site_crawler_helpers import MAX_PAGINAS, MAX_THREADS

from .site_crawler_runtime import executar_pipeline_crawler
from .site_crawler_shared import safe_int


def executar_crawler(
    url: str,
    max_paginas: int = MAX_PAGINAS,
    max_threads: int = MAX_THREADS,
    padrao_disponivel: int = 10,
) -> pd.DataFrame:
    if not url:
        return pd.DataFrame()

    max_paginas = safe_int(max_paginas, MAX_PAGINAS)
    max_threads = safe_int(max_threads, MAX_THREADS)
    padrao_disponivel = safe_int(padrao_disponivel, 10)

    max_threads = min(max_threads, 5)

    return executar_pipeline_crawler(
        url=url,
        max_paginas=max_paginas,
        max_threads=max_threads,
        padrao_disponivel=padrao_disponivel,
    )
