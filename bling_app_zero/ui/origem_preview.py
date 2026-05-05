from __future__ import annotations

"""Preview seguro e único dos dados de origem.

Problema resolvido:
- O app possui vários fluxos de origem: planilha, site, XML, estoque e etapas
  antigas/modulares.
- Cada fluxo pode salvar o DataFrame em uma chave diferente do session_state.
- Quando a tela de mapeamento/preview procura apenas uma chave, o usuário pode
  ver preview vazio, preview errado ou cair em erro.

Regra:
- Para cadastro de produtos via site, exigir modelo de cadastro do Bling antes
  de abrir o Preview da origem.
- Sempre escolher o primeiro DataFrame válido em ordem de prioridade.
- Nunca quebrar a tela se não houver dados.
- Mostrar claramente qual chave foi usada para montar o preview.
- Limpar valores claramente incompatíveis com o destino antes de mostrar.
- Remover dados falsos de captura, como preço `0,00` quando não for real.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd
import streamlit as st

from bling_app_zero.core.product_data_quality import normalize_product_dataframe
from bling_app_zero.ui.mapeamento.value_guard import clean_invalid_preview_mappings
from bling_app_zero.ui.modelo_bling_guard import (
    render_modelo_cadastro_required_message,
    requires_modelo_cadastro_for_preview,
)


@dataclass(frozen=True)
class OrigemPreviewResult:
    key: str
    dataframe: pd.DataFrame


ORIGEM_PREVIEW_KEYS: tuple[str, ...] = (
    # Origem principal do fluxo atual.
    "df_origem",
    # Captura por site / scraper.
    "df_origem_site",
    "df_capturado_site",
    "df_site",
    "site_df",
    # Upload de planilha.
    "df_origem_upload",
    "df_upload",
    "uploaded_df",
    # XML.
    "df_origem_xml",
    "df_xml",
    # Estoque / atualização.
    "df_estoque",
    "df_stock",
    "df_saida_estoque",
    # Prévia e saídas intermediárias.
    "df_preview_origem",
    "df_preview",
    "df_saida",
    # Último fallback: final, só para não deixar o usuário cego.
    "df_final",
)


def is_valid_dataframe(value: object) -> bool:
    return isinstance(value, pd.DataFrame) and not value.empty


def get_origem_preview_dataframe(keys: Iterable[str] = ORIGEM_PREVIEW_KEYS) -> Optional[OrigemPreviewResult]:
    """Retorna o primeiro DataFrame válido de origem encontrado na sessão."""
    for key in keys:
        value = st.session_state.get(key)
        if is_valid_dataframe(value):
            return OrigemPreviewResult(key=key, dataframe=value.copy())
    return None


def preparar_preview_origem(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica qualidade + blindagem no preview da origem."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    normalized = normalize_product_dataframe(df.copy())
    cleaned = clean_invalid_preview_mappings(normalized.copy())
    return cleaned


def ensure_df_origem_from_best_source() -> Optional[pd.DataFrame]:
    """Garante `df_origem` preenchido com a melhor origem disponível."""
    if requires_modelo_cadastro_for_preview():
        return None

    result = get_origem_preview_dataframe()
    if result is None:
        return None

    df = preparar_preview_origem(result.dataframe.copy())
    st.session_state["df_origem"] = df.copy()
    st.session_state["df_preview_origem"] = df.copy()
    st.session_state["origem_preview_key"] = result.key
    return df.copy()


def _preview_height(row_count: int) -> int:
    """Calcula altura confortável para o preview sem ocupar a tela inteira."""
    if row_count <= 5:
        return 210
    if row_count <= 10:
        return 290
    if row_count <= 20:
        return 390
    return 460


def _count_changed_cells(raw_df: pd.DataFrame, cleaned_df: pd.DataFrame) -> int:
    try:
        comparable_raw = raw_df.reindex(columns=cleaned_df.columns).fillna("").astype(str)
        comparable_clean = cleaned_df.fillna("").astype(str)
        return int((comparable_raw != comparable_clean).to_numpy().sum())
    except Exception:
        return 0


def render_origem_preview(
    title: str = "Preview da origem",
    max_rows: int = 30,
    *,
    compact: bool = True,
) -> Optional[pd.DataFrame]:
    """Renderiza o preview da origem de forma segura e padronizada."""
    if requires_modelo_cadastro_for_preview():
        render_modelo_cadastro_required_message()
        return None

    result = get_origem_preview_dataframe()

    if result is None:
        st.warning(
            "Nenhum dado de origem foi encontrado para pré-visualizar. "
            "Volte para Origem dos dados e carregue/capture os produtos novamente."
        )
        return None

    raw_df = result.dataframe.copy()
    df = preparar_preview_origem(raw_df)
    removed_cells = _count_changed_cells(raw_df, df)

    st.session_state["df_origem"] = df.copy()
    st.session_state["df_preview_origem"] = df.copy()
    st.session_state["origem_preview_key"] = result.key
    st.session_state["origem_preview_cells_cleaned"] = removed_cells

    preview_df = df.head(max_rows).copy()

    if title:
        st.subheader(title)

    info_col, size_col = st.columns([2, 1])
    with info_col:
        st.caption(f"Fonte usada: `{result.key}`")
    with size_col:
        st.caption(f"{len(df)} linhas × {len(df.columns)} colunas")

    if removed_cells > 0:
        st.info(
            f"Mapeamento automático conservador: {removed_cells} célula(s) incompatível(is) "
            "ou falsa(s) foram deixadas em branco para revisão manual."
        )

    st.dataframe(
        preview_df,
        use_container_width=True,
        hide_index=True,
        height=_preview_height(len(preview_df)) if compact else None,
    )
    return df


def has_origem_preview_data() -> bool:
    if requires_modelo_cadastro_for_preview():
        return False
    return get_origem_preview_dataframe() is not None
