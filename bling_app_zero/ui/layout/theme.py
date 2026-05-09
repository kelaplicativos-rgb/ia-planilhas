from __future__ import annotations

from bling_app_zero.ui.clean_layout import inject_clean_home_css
from bling_app_zero.ui.unified_light_layout import inject_unified_light_layout


def inject_app_layout() -> None:
    """Ponto único oficial para aplicar o layout global do sistema.

    Este módulo passa a ser o responsável pelo tema principal do app.
    Os arquivos antigos continuam existindo para compatibilidade, mas novos
    fluxos devem importar layout por ``bling_app_zero.ui.layout``.
    """
    inject_unified_light_layout()
