from __future__ import annotations

"""Preview seguro e único dos dados de origem.

Problema resolvido:
- O app possui vários fluxos de origem: planilha, site, XML, estoque e etapas
  antigas/modulares.
- Cada fluxo pode salvar o DataFrame em uma chave diferente do session_state.
- Quando a tela de mapeamento/preview procura apenas uma chave, o usuário pode
  ver preview vazio, preview errado ou cair em erro.

Regra:
- Sempre escolher o primeiro DataFrame válido em ordem de prioridade.
- Nunca quebrar a tela se não houver dados.
- Mostrar claramente qual chave foi usada para montar o preview.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

import pandas as pd
import streamlit as st


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


def ensure_df_origem_from_best_source() -> Optional[pd.DataFrame]:
    """Garante `df_origem` preenchido com a melhor origem disponível.

    Isso evita que telas antigas que só leem `df_origem` fiquem vazias quando a
    captura salvou os dados em outra chave, como `df_capturado_site`.
    """
    result = get_origem_preview_dataframe()
    if result is None:
        return None

    st.session_state["df_origem"] = result.dataframe.copy()
    st.session_state["df_preview_origem"] = result.dataframe.copy()
    st.session_state["origem_preview_key"] = result.key
    return result.dataframe.copy()


def _preview_height(row_count: int) -> int:
    """Calcula altura confortável para o preview sem ocupar a tela inteira."""
    if row_count <= 5:
        return 210
    if row_count <= 10:
        return 290
    if row_count <= 20:
        return 390
    return 460


def render_origem_preview(
    title: str = "Preview da origem",
    max_rows: int = 30,
    *,
    compact: bool = True,
) -> Optional[pd.DataFrame]:
    """Renderiza o preview da origem de forma segura e padronizada."""
    result = get_origem_preview_dataframe()

    if result is None:
        st.warning(
            "Nenhum dado de origem foi encontrado para pré-visualizar. "
            "Volte para Origem dos dados e carregue/capture os produtos novamente."
        )
        return None

    df = result.dataframe.copy()
    st.session_state["df_origem"] = df.copy()
    st.session_state["df_preview_origem"] = df.copy()
    st.session_state["origem_preview_key"] = result.key

    preview_df = df.head(max_rows).copy()

    if title:
        st.subheader(title)

    info_col, size_col = st.columns([2, 1])
    with info_col:
        st.caption(f"Fonte usada: `{result.key}`")
    with size_col:
        st.caption(f"{len(df)} linhas × {len(df.columns)} colunas")

    st.dataframe(
        preview_df,
        use_container_width=True,
        hide_index=True,
        height=_preview_height(len(preview_df)) if compact else None,
    )
    return df


def has_origem_preview_data() -> bool:
    return get_origem_preview_dataframe() is not None
