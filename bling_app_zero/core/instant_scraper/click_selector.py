# bling_app_zero/core/instant_scraper/click_selector.py

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista


COLUNAS_PADRAO = [
    "nome",
    "preco",
    "url_produto",
    "imagens",
    "descricao",
]


def _df_ok(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty


def _txt(valor: Any) -> str:
    return str(valor or "").strip()


def _normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not _df_ok(df):
        return pd.DataFrame(columns=COLUNAS_PADRAO)

    base = df.copy().fillna("")

    for col in COLUNAS_PADRAO:
        if col not in base.columns:
            base[col] = ""

    for col in base.columns:
        base[col] = base[col].map(_txt)

    base = base[COLUNAS_PADRAO + [c for c in base.columns if c not in COLUNAS_PADRAO]]

    if "url_produto" in base.columns:
        base = base.drop_duplicates(subset=["url_produto", "nome"], keep="first")
    else:
        base = base.drop_duplicates(keep="first")

    base = base.reset_index(drop=True)
    return base


def _score_dataframe(df: pd.DataFrame, score_base: int = 0) -> int:
    if not _df_ok(df):
        return 0

    score = int(score_base or 0)
    score += len(df) * 10

    if "nome" in df.columns:
        nomes_validos = df["nome"].map(lambda x: len(_txt(x)) >= 5).sum()
        score += int(nomes_validos) * 8

    if "preco" in df.columns:
        precos_validos = df["preco"].map(lambda x: "R$" in _txt(x) or any(ch.isdigit() for ch in _txt(x))).sum()
        score += int(precos_validos) * 12

    if "url_produto" in df.columns:
        links_validos = df["url_produto"].map(lambda x: _txt(x).startswith(("http://", "https://"))).sum()
        score += int(links_validos) * 6

    if "imagens" in df.columns:
        imgs_validas = df["imagens"].map(lambda x: bool(_txt(x))).sum()
        score += int(imgs_validas) * 3

    return score


def _opcao_util(df: pd.DataFrame) -> bool:
    if not _df_ok(df):
        return False

    if len(df) < 1:
        return False

    tem_nome = "nome" in df.columns and df["nome"].map(lambda x: len(_txt(x)) >= 5).any()
    tem_preco = "preco" in df.columns and df["preco"].map(lambda x: bool(_txt(x))).any()
    tem_link = "url_produto" in df.columns and df["url_produto"].map(lambda x: bool(_txt(x))).any()

    return bool(tem_nome and (tem_preco or tem_link))


def gerar_opcoes_click_scraper(html: str, base_url: str, limite: int = 8) -> List[Dict[str, Any]]:
    """
    Detecta blocos repetidos e monta opções estilo Instant Data Scraper.

    Melhorias:
    - ignora opções vazias;
    - normaliza colunas;
    - reordena por qualidade real dos dados;
    - mantém id estável para escolha na interface.
    """
    html = _txt(html)
    base_url = _txt(base_url)

    if not html:
        return []

    candidatos = detectar_blocos_repetidos(html) or []
    opcoes_brutas: List[Dict[str, Any]] = []

    for candidato in candidatos:
        elements = candidato.get("elements", []) or []

        if not elements:
            continue

        produtos = extrair_lista(elements, base_url) or []
        df = _normalizar_dataframe(pd.DataFrame(produtos))

        if not _opcao_util(df):
            continue

        score_base = int(candidato.get("score", 0) or 0)
        score_final = _score_dataframe(df, score_base=score_base)

        opcoes_brutas.append(
            {
                "score": score_final,
                "score_base": score_base,
                "pattern": candidato.get("pattern", ""),
                "total_elementos": len(elements),
                "total_produtos": len(df),
                "dataframe": df,
            }
        )

    opcoes_brutas.sort(
        key=lambda item: (
            int(item.get("total_produtos", 0) or 0),
            int(item.get("score", 0) or 0),
        ),
        reverse=True,
    )

    opcoes: List[Dict[str, Any]] = []

    for idx, opcao in enumerate(opcoes_brutas[:limite], start=1):
        opcao["id"] = idx
        opcoes.append(opcao)

    return opcoes


def extrair_por_opcao_click(
    html: str,
    base_url: str,
    opcao_id: int = 1,
) -> pd.DataFrame:
    """
    Extrai os produtos da opção escolhida pelo usuário.
    """
    opcoes = gerar_opcoes_click_scraper(html, base_url)

    if not opcoes:
        return pd.DataFrame(columns=COLUNAS_PADRAO)

    try:
        opcao_id = int(opcao_id or 1)
    except Exception:
        opcao_id = 1

    for opcao in opcoes:
        if int(opcao.get("id", 0) or 0) == opcao_id:
            df = opcao.get("dataframe")
            if isinstance(df, pd.DataFrame):
                return _normalizar_dataframe(df)

    melhor_df = opcoes[0].get("dataframe")
    if isinstance(melhor_df, pd.DataFrame):
        return _normalizar_dataframe(melhor_df)

    return pd.DataFrame(columns=COLUNAS_PADRAO)
