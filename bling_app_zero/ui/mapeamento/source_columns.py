from __future__ import annotations

"""Colunas reais da origem/captura para o mapeamento.

Regra: o dropdown do mapeamento deve refletir a planilha/captura do site,
nunca as colunas do modelo Bling nem o dataframe final já mapeado.
"""

import pandas as pd

from bling_app_zero.ui.mapeamento.columns_guard import (
    colunas_unicas_reais,
    normalizar_coluna,
)


_CHAVES_ORIGEM_PREFERIDAS = (
    "df_origem_site",
    "df_site",
    "df_captura_site",
    "df_capturado_site",
    "df_produtos_site",
    "df_origem_upload",
    "df_upload",
    "df_origem_xml",
    "df_origem_pdf",
    "df_origem",
    "df_dados",
)


_CHAVES_PROIBIDAS_COMO_ORIGEM = {
    "df_final",
    "df_saida",
    "df_modelo",
    "df_modelo_cadastro",
    "df_modelo_estoque",
}


def _safe_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def escolher_df_origem_captura(session_state) -> pd.DataFrame:
    """Busca a base real capturada/enviada pelo usuário, sem usar saída final."""

    melhor_df = pd.DataFrame()
    melhor_score = -1

    for chave in _CHAVES_ORIGEM_PREFERIDAS:
        if chave in _CHAVES_PROIBIDAS_COMO_ORIGEM:
            continue

        df = session_state.get(chave)
        if not _safe_df(df):
            continue

        score = len(df.columns)

        # Prioriza fortemente capturas reais do site/upload.
        if "site" in chave:
            score += 100
        elif "upload" in chave:
            score += 80
        elif "xml" in chave:
            score += 60

        if score > melhor_score:
            melhor_df = df.copy()
            melhor_score = score

    return melhor_df


def colunas_reais_da_origem(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame | None = None,
    *,
    bloquear_video: bool = True,
    video_checker=None,
) -> list[str]:
    if not isinstance(df_base, pd.DataFrame):
        return []

    return colunas_unicas_reais(
        df_base.columns.tolist(),
        df_modelo=df_modelo,
        bloquear_video=bloquear_video,
        video_checker=video_checker,
    )


def opcoes_origem_mapeamento(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame | None = None,
    *,
    incluir_vazio: bool = True,
    bloquear_video: bool = True,
    video_checker=None,
) -> list[str]:
    colunas = colunas_reais_da_origem(
        df_base,
        df_modelo,
        bloquear_video=bloquear_video,
        video_checker=video_checker,
    )

    # Blindagem final anti-duplicidade visual.
    vistas: set[str] = set()
    finais: list[str] = []

    for coluna in colunas:
        chave = normalizar_coluna(coluna)
        if chave in vistas:
            continue
        vistas.add(chave)
        finais.append(coluna)

    return ([""] if incluir_vazio else []) + finais
