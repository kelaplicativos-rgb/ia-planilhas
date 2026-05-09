from __future__ import annotations


def inject_global_layout_guard() -> None:
    """Ponte de compatibilidade para o tema maestro global.

    O layout do sistema inteiro agora e comandado por
    bling_app_zero.ui.layout.theme. Este arquivo permanece para nao quebrar
    imports antigos, mas nao injeta CSS proprio.
    """
    from bling_app_zero.ui.layout.theme import inject_app_layout

    inject_app_layout()
