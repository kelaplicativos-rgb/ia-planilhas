from __future__ import annotations

"""Colunas reais da origem/captura para o mapeamento.

Regra: o dropdown do mapeamento deve refletir a planilha/captura do site,
nunca as colunas do modelo Bling nem o dataframe final já mapeado.
"""

import re

import pandas as pd


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

_COLUNAS_INTERNAS_EXATAS = {
    "df final",
    "df saida",
    "mapping manual",
    "modelo bling",
    "modelo cadastro",
    "modelo estoque",
}

_FRAGMENTOS_DESTINO_OU_INTERNO = (
    "obrigatorio",
    "obrigatoria",
    "campo bling",
    "campo destino",
    "destino bling",
    "coluna destino",
    "mapeamento",
    "calculado automaticamente",
)


def normalizar_nome_coluna(valor: object) -> str:
    texto = str(valor or "").strip().lower()
    texto = texto.translate(str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc"))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _safe_df(df: object) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def escolher_df_origem_captura(session_state) -> pd.DataFrame:
    """Busca a base real capturada/enviada pelo usuário, sem usar saída final."""
    for chave in _CHAVES_ORIGEM_PREFERIDAS:
        df = session_state.get(chave)
        if _safe_df(df):
            return df.copy()
    return pd.DataFrame()


def _nomes_modelo(df_modelo: pd.DataFrame | None) -> set[str]:
    if not isinstance(df_modelo, pd.DataFrame):
        return set()
    return {normalizar_nome_coluna(c) for c in df_modelo.columns.tolist() if str(c).strip()}


def _parece_destino_ou_interna(coluna: object, nomes_modelo: set[str]) -> bool:
    nome = normalizar_nome_coluna(coluna)
    if not nome:
        return True
    if nome in _COLUNAS_INTERNAS_EXATAS:
        return True
    if any(fragmento in nome for fragmento in _FRAGMENTOS_DESTINO_OU_INTERNO):
        return True

    # Quando a coluna é exatamente uma coluna do modelo Bling, ela não deve aparecer
    # como origem, exceto nomes simples que fornecedores/capturas usam de verdade.
    simples_permitidos = {
        "preco",
        "preco unitario",
        "valor",
        "price",
        "nome",
        "produto",
        "descricao",
        "codigo",
        "sku",
        "gtin",
        "ean",
        "estoque",
        "quantidade",
        "marca",
        "categoria",
    }
    if nome in nomes_modelo and nome not in simples_permitidos:
        return True
    return False


def colunas_reais_da_origem(
    df_base: pd.DataFrame,
    df_modelo: pd.DataFrame | None = None,
    *,
    bloquear_video: bool = True,
    video_checker=None,
) -> list[str]:
    if not isinstance(df_base, pd.DataFrame):
        return []

    nomes_modelo = _nomes_modelo(df_modelo)
    resultado: list[str] = []
    vistos: set[str] = set()

    for coluna in df_base.columns.tolist():
        col = str(coluna or "").strip()
        chave = normalizar_nome_coluna(col)
        if not col or chave in vistos:
            continue
        if bloquear_video and callable(video_checker) and video_checker(col):
            continue
        if _parece_destino_ou_interna(col, nomes_modelo):
            continue
        vistos.add(chave)
        resultado.append(col)

    return resultado


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
    return ([""] if incluir_vazio else []) + colunas
