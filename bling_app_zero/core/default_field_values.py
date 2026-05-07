from __future__ import annotations

import re
import unicodedata
from typing import Callable

import pandas as pd


# Defaults seguros para o CSV final padrão Bling.
# A regra só preenche campos vazios; nunca sobrescreve valor informado/mapeado pelo usuário.
DEFAULTS_BY_NORMALIZED_COLUMN: dict[str, str] = {
    "unidade": "UN",
    "unidade de medida": "UN",
    "situacao": "Ativo",
    "situacao do produto": "Ativo",
    "itens p caixa": "1",
    "itens por caixa": "1",
    "item p caixa": "1",
    "items p caixa": "1",
    "tipo do item": "Produto",
    "tipo item": "Produto",
    "origem": "0",
    "volumes": "1",
    "condicao do produto": "Novo",
    "frete gratis": "Não",
    "fornecedor": "Não definido",
}

EMPTY_LIKE_VALUES = {
    "",
    "nan",
    "none",
    "null",
    "na",
    "n a",
    "indefinido",
    "nao definido",
    "não definido",
}


def normalize_key(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_empty_like(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return normalize_key(text) in {normalize_key(v) for v in EMPTY_LIKE_VALUES}


def default_for_column(column_name: object) -> str:
    return DEFAULTS_BY_NORMALIZED_COLUMN.get(normalize_key(column_name), "")


def fill_default_field_values(df: pd.DataFrame, *, logger: Callable[..., None] | None = None) -> pd.DataFrame:
    """Preenche campos padrão vazios no DataFrame final.

    Esta função é propositalmente conservadora:
    - só age sobre colunas conhecidas do modelo Bling;
    - só preenche células vazias/NaN/None/null;
    - não altera valores já informados pelo usuário ou pelo mapeamento.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    base = df.copy().fillna("")
    total = 0
    detalhes: list[str] = []

    for col in base.columns:
        valor_padrao = default_for_column(col)
        if not valor_padrao:
            continue

        mask = base[col].map(is_empty_like)
        qtd = int(mask.sum())
        if qtd <= 0:
            continue

        base.loc[mask, col] = valor_padrao
        total += qtd
        detalhes.append(f"{col}={valor_padrao} ({qtd})")

    if total > 0 and callable(logger):
        logger(
            "Campos padrão vazios preenchidos automaticamente no preview/download final: " + "; ".join(detalhes),
            nivel="INFO",
        )

    return base.fillna("")
