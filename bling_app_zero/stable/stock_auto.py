from __future__ import annotations

import re

import pandas as pd


ESTOQUE_DISPONIVEL_PADRAO = 1000
ESTOQUE_INDISPONIVEL_PADRAO = 0

PALAVRAS_DISPONIVEL = [
    "disponivel",
    "disponível",
    "em estoque",
    "instock",
    "in stock",
    "available",
    "comprar",
    "adicionar ao carrinho",
    "pronta entrega",
    "sim",
    "true",
]

PALAVRAS_INDISPONIVEL = [
    "indisponivel",
    "indisponível",
    "sem estoque",
    "esgotado",
    "outofstock",
    "out of stock",
    "fora de estoque",
    "avise-me",
    "aviseme",
    "não disponível",
    "nao disponivel",
    "não",
    "nao",
    "false",
]

COLUNAS_ESTOQUE = [
    "estoque",
    "quantidade",
    "qtd",
    "saldo",
    "stock",
    "inventory",
    "available stock",
    "available_stock",
    "inventory quantity",
    "inventory_quantity",
]

COLUNAS_DISPONIBILIDADE = [
    "disponibilidade",
    "disponivel",
    "disponível",
    "status",
    "situacao",
    "situação",
    "availability",
    "available",
    "estoque status",
    "stock status",
]


def _norm(value: object) -> str:
    text = str(value or "").strip().lower()
    repl = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    text = text.translate(repl)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_int(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    if re.search(r"sem estoque|indispon|esgot", text, flags=re.IGNORECASE):
        return 0
    found = re.search(r"\d+", text.replace(".", ""))
    if not found:
        return None
    try:
        return max(0, int(found.group(0)))
    except Exception:
        return None


def _classificar_disponibilidade(value: object) -> int | None:
    text = _norm(value)
    if not text:
        return None

    if any(_norm(term) in text for term in PALAVRAS_INDISPONIVEL):
        return ESTOQUE_INDISPONIVEL_PADRAO
    if any(_norm(term) in text for term in PALAVRAS_DISPONIVEL):
        return ESTOQUE_DISPONIVEL_PADRAO
    return None


def _colunas_por_alias(df: pd.DataFrame, aliases: list[str]) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    aliases_norm = [_norm(a) for a in aliases]
    encontradas: list[str] = []
    for col in df.columns:
        ncol = _norm(col)
        if any(alias == ncol or alias in ncol or ncol in alias for alias in aliases_norm):
            encontradas.append(str(col))
    return encontradas


def resolver_estoque_linha(row: pd.Series, estoque_cols: list[str], disponibilidade_cols: list[str]) -> tuple[int, str]:
    for col in estoque_cols:
        valor = _parse_int(row.get(col, ""))
        if valor is not None:
            return int(valor), "REAL"

    for col in disponibilidade_cols:
        valor = _classificar_disponibilidade(row.get(col, ""))
        if valor is not None:
            return int(valor), "DISPONIBILIDADE_AUTO" if valor > 0 else "INDISPONIVEL_AUTO"

    texto_linha = " ".join(str(v or "") for v in row.tolist())
    valor = _classificar_disponibilidade(texto_linha)
    if valor is not None:
        return int(valor), "DISPONIBILIDADE_AUTO" if valor > 0 else "INDISPONIVEL_AUTO"

    return 0, "NAO_INFORMADO"


def aplicar_estoque_automatico(df: pd.DataFrame) -> pd.DataFrame:
    """Preenche Estoque/Quantidade automaticamente para reduzir interação humana.

    Regra:
    - se houver número real em coluna de estoque/quantidade, usa esse número;
    - se houver disponibilidade positiva, usa 1000;
    - se houver indisponibilidade, usa 0;
    - se não houver sinal confiável, usa 0.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    out = df.copy().fillna("")
    out.columns = [str(c).replace("\ufeff", "").strip() for c in out.columns]

    estoque_cols = _colunas_por_alias(out, COLUNAS_ESTOQUE)
    disponibilidade_cols = _colunas_por_alias(out, COLUNAS_DISPONIBILIDADE)

    valores: list[int] = []
    origens: list[str] = []
    for _, row in out.iterrows():
        estoque, origem = resolver_estoque_linha(row, estoque_cols, disponibilidade_cols)
        valores.append(int(estoque))
        origens.append(origem)

    if "Estoque" not in out.columns:
        out["Estoque"] = valores
    else:
        out["Estoque"] = valores

    if "Quantidade" not in out.columns:
        out["Quantidade"] = valores
    else:
        out["Quantidade"] = valores

    out["Origem do estoque"] = origens
    return out.fillna("")
