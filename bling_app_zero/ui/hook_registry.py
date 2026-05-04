from __future__ import annotations

from bling_app_zero.ui.hook_bus import register


def load_hooks() -> None:
    register(
        "preview.before_download",
        "bling_app_zero.ui.preview_final_estoque_inteligente:aplicar_estoque_inteligente_final",
    )
