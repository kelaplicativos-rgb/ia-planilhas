from __future__ import annotations

from bling_app_zero.ui.cadastro_download_step import render_cadastro_download_step
from bling_app_zero.ui.cadastro_entry_step import render_cadastro_entrada_step
from bling_app_zero.ui.cadastro_mapping_step import render_cadastro_mapeamento_step
from bling_app_zero.ui.cadastro_preview_step import render_cadastro_preview_step
from bling_app_zero.ui.cadastro_wizard_state import cadastro_context_ready, cadastro_mapping_ready

# Aliases universais: preservam compatibilidade com os módulos antigos de cadastro,
# mas permitem que o fluxo novo use nomes alinhados ao modelo final universal.
universal_context_ready = cadastro_context_ready
universal_mapping_ready = cadastro_mapping_ready
render_universal_download_step = render_cadastro_download_step
render_universal_entrada_step = render_cadastro_entrada_step
render_universal_mapeamento_step = render_cadastro_mapeamento_step
render_universal_preview_step = render_cadastro_preview_step


__all__ = [
    'cadastro_context_ready',
    'cadastro_mapping_ready',
    'render_cadastro_download_step',
    'render_cadastro_entrada_step',
    'render_cadastro_mapeamento_step',
    'render_cadastro_preview_step',
    'universal_context_ready',
    'universal_mapping_ready',
    'render_universal_download_step',
    'render_universal_entrada_step',
    'render_universal_mapeamento_step',
    'render_universal_preview_step',
]