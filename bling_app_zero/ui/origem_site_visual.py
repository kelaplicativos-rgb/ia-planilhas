from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def _safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def render_origem_site_visual_preview(df: Any, *, expanded: bool = False) -> None:
    """Preview bruto desativado para manter o fluxo limpo.

    A busca por site agora usa diretamente a planilha de preview baseada no modelo
    Bling anexado como ponto de revisão/mapeamento. Mantemos esta função para
    compatibilidade com os imports existentes, mas ela não renderiza mais os
    blocos antigos: tabela detectada, resumo de colunas, BLINGAI PRO e ações
    visuais.
    """
    base = _safe_df(df)
    if base.empty:
        return

    st.caption(
        f"✅ Captura por site concluída: {len(base)} linha(s) detectada(s). "
        "Revise e siga pela planilha de preview baseada no modelo Bling abaixo."
    )


__all__ = ["render_origem_site_visual_preview"]
