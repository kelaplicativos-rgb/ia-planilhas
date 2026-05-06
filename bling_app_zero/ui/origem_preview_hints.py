from __future__ import annotations

"""Mini amostras vermelhas para o Preview da origem."""

import html as html_lib

import pandas as pd
import streamlit as st


MAX_COLUNAS = 12
MAX_CHARS = 90


def _limpar(valor: object) -> str:
    texto = " ".join(str(valor or "").replace("\n", " ").replace("\r", " ").split()).strip()
    if len(texto) > MAX_CHARS:
        return texto[: MAX_CHARS - 3].rstrip() + "..."
    return texto


def _primeiro_valor(df: pd.DataFrame, coluna: str) -> str:
    if not isinstance(df, pd.DataFrame) or coluna not in df.columns:
        return ""
    try:
        for valor in df[coluna].fillna("").astype(str).tolist():
            texto = _limpar(valor)
            if texto:
                return texto
    except Exception:
        return ""
    return ""


def render_preview_origem_amostras_vermelhas(df: pd.DataFrame) -> None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return

    colunas = [str(c) for c in df.columns.tolist()[:MAX_COLUNAS]]
    blocos: list[str] = []
    for coluna in colunas:
        valor = _primeiro_valor(df, coluna)
        if not valor:
            continue
        blocos.append(
            """
            <div style="padding:6px 8px; border:1px solid #FECACA; border-radius:8px; background:#FFF7F7; margin:3px 0;">
                <div style="font-size:11px; font-weight:700; color:#991B1B;">%s</div>
                <div style="font-size:10px; line-height:1.25; color:#DC2626; word-break:break-word;">1ª linha: %s</div>
            </div>
            """ % (html_lib.escape(coluna), html_lib.escape(valor))
        )

    if not blocos:
        return

    st.markdown(
        """
        <div style="font-size:12px; font-weight:700; color:#991B1B; margin:8px 0 4px 0;">
            🔎 Amostras rápidas da origem para mapear
        </div>
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(155px,1fr)); gap:6px; margin-bottom:8px;">
            %s
        </div>
        """ % "\n".join(blocos),
        unsafe_allow_html=True,
    )
