from __future__ import annotations

from bling_app_zero.ui.mod_kernel import call


ROUTES = {
    "origem": ("bling_app_zero.ui.origem", "render_origem_dados"),
    "precificacao": ("bling_app_zero.ui.precificacao", "render_origem_precificacao"),
    "mapeamento": ("bling_app_zero.ui.mapeamento", "render_origem_mapeamento"),
    "preview_final": ("bling_app_zero.ui.preview", "render_preview_final"),
}


def render_step(step: str) -> None:
    module, name = ROUTES.get(step, ROUTES["origem"])
    call(module, name)
