from __future__ import annotations

from bling_app_zero.ui import origem_dados as _origem_dados


def render_origem_dados() -> None:
    """
    Renderiza a Origem dos dados sem o bloco antigo de Estoque inteligente.

    O Estoque inteligente agora fica no Preview Final, imediatamente antes
    do download, para sobrescrever o df_final já alinhado ao modelo Bling.
    """
    _origem_dados._render_estoque_inteligente = lambda: None
    _origem_dados.render_origem_dados()
