from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.self_healing import diagnosticar_dataframe


COLUNAS_PRIORIDADE_VISUAL = [
    "Código",
    "SKU",
    "Descrição",
    "Descrição complementar",
    "Preço unitário (OBRIGATÓRIO)",
    "Preço unitário",
    "Preço",
    "Estoque",
    "GTIN/EAN",
    "GTIN",
    "Marca",
    "Categoria",
    "NCM",
    "URL do produto",
    "URL origem da busca",
    "URL das imagens",
    "Imagens",
    "agente_estrategia",
    "agente_score",
    "origem_site_motor",
    "origem_site_status",
]


RUINS_COLUNAS_VISUAIS = {
    "",
    "unnamed: 0",
    "index",
    "level_0",
}


def _txt(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and pd.isna(valor):
        return ""
    return " ".join(str(valor).replace("\x00", " ").split()).strip()


def _norm(valor: Any) -> str:
    texto = _txt(valor).lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _score_visual(df: pd.DataFrame) -> dict[str, Any]:
    base = _safe_df(df)
    if base.empty:
        return {"score": 0, "status": "sem_dados", "linhas": 0}

    try:
        diag = diagnosticar_dataframe(base)
        score = int(diag.get("score", 0) or 0)
        status = str(diag.get("status", "") or "")
    except Exception:
        score = 0
        status = "sem_diagnostico"

    # Reforço para DataFrame já normalizado para Bling.
    colunas_norm = {_norm(c) for c in base.columns}
    if "descricao" in colunas_norm:
        score += 12
    if "preco unitario obrigatorio" in colunas_norm or "preco unitario" in colunas_norm:
        score += 12
    if "url das imagens" in colunas_norm or "imagens" in colunas_norm:
        score += 8
    if "gtin ean" in colunas_norm or "gtin" in colunas_norm:
        score += 5

    score = min(max(score, 0), 100)
    if score >= 80:
        status = "excelente"
    elif score >= 60:
        status = "bom"
    elif score >= 40:
        status = "revisar"
    else:
        status = "fraco"

    return {"score": score, "status": status, "linhas": len(base)}


def _colunas_ordenadas(df: pd.DataFrame) -> list[str]:
    colunas = [str(c) for c in df.columns.tolist() if _norm(c) not in RUINS_COLUNAS_VISUAIS]
    prioridade = []
    for alvo in COLUNAS_PRIORIDADE_VISUAL:
        for col in colunas:
            if col not in prioridade and _norm(col) == _norm(alvo):
                prioridade.append(col)

    restantes = [c for c in colunas if c not in prioridade]
    return prioridade + restantes


def _resumo_colunas(df: pd.DataFrame) -> pd.DataFrame:
    base = _safe_df(df)
    if base.empty:
        return pd.DataFrame(columns=["Coluna", "Preenchidos", "Exemplo"])

    linhas = []
    total = max(len(base), 1)
    for col in _colunas_ordenadas(base):
        serie = base[col].astype(str).fillna("")
        preenchidos = int(serie.str.strip().ne("").sum())
        exemplo = ""
        for valor in serie.tolist():
            texto = _txt(valor)
            if texto:
                exemplo = texto[:120]
                break
        linhas.append(
            {
                "Coluna": col,
                "Preenchidos": f"{preenchidos}/{total}",
                "Exemplo": exemplo,
            }
        )
    return pd.DataFrame(linhas)


def render_origem_site_visual_preview(df: Any, *, expanded: bool = True) -> None:
    base = _safe_df(df)
    if base.empty:
        return

    diag = _score_visual(base)
    score = int(diag.get("score", 0) or 0)
    status = str(diag.get("status", "") or "")

    st.markdown("### 👁️ Preview visual da captura")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Produtos", len(base))
    with c2:
        st.metric("Colunas", len(base.columns))
    with c3:
        st.metric("Score IA", f"{score}/100")
    with c4:
        st.metric("Status", status.title())

    if score >= 80:
        st.success("Captura forte: estrutura parece pronta para o mapeamento Bling.")
    elif score >= 60:
        st.info("Captura boa: revise rapidamente as colunas antes de avançar.")
    else:
        st.warning("Captura fraca/revisar: confira se o site carregou os produtos certos.")

    colunas = _colunas_ordenadas(base)
    preview = base[colunas].head(80)

    with st.expander("Tabela detectada automaticamente", expanded=expanded):
        st.dataframe(preview, use_container_width=True, hide_index=True)

    with st.expander("Resumo das colunas detectadas", expanded=False):
        st.dataframe(_resumo_colunas(base), use_container_width=True, hide_index=True)

    with st.expander("Ações visuais", expanded=False):
        st.caption("Use isso quando a captura trouxe colunas claramente inúteis antes de seguir para o modelo Bling.")
        colunas_remover = st.multiselect(
            "Ocultar/remover colunas da base capturada",
            options=colunas,
            default=[],
            key="origem_site_visual_cols_remover",
        )
        if st.button("Aplicar limpeza visual", key="btn_origem_site_aplicar_limpeza_visual", use_container_width=True):
            limpo = base.drop(columns=[c for c in colunas_remover if c in base.columns], errors="ignore")
            st.session_state["df_origem"] = limpo
            st.session_state["df_saida"] = limpo.copy()
            st.success("Base visual limpa aplicada ao fluxo.")
            st.rerun()


__all__ = ["render_origem_site_visual_preview"]
