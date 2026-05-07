from __future__ import annotations

"""Colunas reais da origem/captura para o mapeamento.

Regra: o dropdown do mapeamento deve refletir a planilha/captura do site,
nunca as colunas do modelo Bling nem o dataframe final já mapeado.

No fluxo com modelo anexado pelo usuário, a planilha de referência pode ser
cadastro ou estoque. Ela deve servir como estrutura de destino, mas as opções
de preenchimento precisam vir da captura real que está em operação no momento.
"""

import pandas as pd

from bling_app_zero.ui.mapeamento.columns_guard import (
    colunas_unicas_reais,
    normalizar_coluna,
)

normalizar_nome_coluna = normalizar_coluna


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
    "df_modelo_unido",
    "df_modelo_unidos",
    "df_preview_modelo",
}

_SINAIS_CAPTURA_SITE = {
    "url do produto",
    "url produto",
    "link produto",
    "fonte captura",
    "fonte de captura",
    "imagens",
    "imagem",
    "url imagens externas",
    "estoque",
    "quantidade",
    "preco unitario",
    "preco",
    "gtin",
    "sku",
    "codigo",
    "nome",
    "produto",
}


def _safe_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def _score_df_origem(chave: str, df: pd.DataFrame, operacao: str = "") -> int:
    colunas_norm = {normalizar_coluna(c) for c in df.columns.tolist()}
    score = len(df.columns)

    if "site" in chave or "captura" in chave or "capturado" in chave:
        score += 200
    elif "upload" in chave or "origem" in chave or "dados" in chave:
        score += 120
    elif "xml" in chave:
        score += 80

    if "modelo" in chave or "final" in chave or "saida" in chave:
        score -= 1000

    score += sum(30 for sinal in _SINAIS_CAPTURA_SITE if normalizar_coluna(sinal) in colunas_norm)

    if operacao == "estoque":
        if {"quantidade", "estoque", "saldo", "qtd"} & colunas_norm:
            score += 120
        if {"url do produto", "fonte captura", "imagens", "preco unitario"} & colunas_norm:
            score += 60

    return score


def escolher_df_origem_captura(session_state, operacao: str = "") -> pd.DataFrame:
    """Busca a base real capturada/enviada pelo usuário, sem usar saída/modelo."""

    melhor_df = pd.DataFrame()
    melhor_score = -10_000

    for chave in _CHAVES_ORIGEM_PREFERIDAS:
        if chave in _CHAVES_PROIBIDAS_COMO_ORIGEM:
            continue

        df = session_state.get(chave)
        if not _safe_df(df):
            continue

        score = _score_df_origem(chave, df, operacao)
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

    vistas: set[str] = set()
    finais: list[str] = []

    for coluna in colunas:
        chave = normalizar_coluna(coluna)
        if chave in vistas:
            continue
        vistas.add(chave)
        finais.append(coluna)

    return ([""] if incluir_vazio else []) + finais
