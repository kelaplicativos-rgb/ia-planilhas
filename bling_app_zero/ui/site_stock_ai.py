from __future__ import annotations

import re
from typing import Any

import pandas as pd


ZERO_STOCK_MARKERS = [
    "sem estoque",
    "indisponivel",
    "indisponível",
    "produto indisponivel",
    "produto indisponível",
    "esgotado",
    "fora de estoque",
    "não disponível",
    "nao disponivel",
    "avise-me",
]

IN_STOCK_MARKERS = [
    "em estoque",
    "disponivel",
    "disponível",
    "comprar",
    "adicionar ao carrinho",
    "add to cart",
    "in stock",
]

STOCK_COLUMN_HINTS = [
    "estoque",
    "stock",
    "quantidade",
    "qtd",
    "saldo",
    "availability",
    "disponibilidade",
    "balanco",
    "balanço",
]


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return " ".join(str(valor).replace("\x00", " ").split()).strip()


def _norm(valor: Any) -> str:
    texto = _texto(valor).lower()
    tabela = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    texto = texto.translate(tabela)
    return texto


def _somente_numero(valor: Any) -> str:
    texto = _texto(valor)
    if not texto:
        return ""
    match = re.search(r"\d+", texto)
    return match.group(0) if match else ""


def _colunas_estoque(df: pd.DataFrame) -> list[str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    encontradas: list[str] = []
    for coluna in df.columns:
        nome = _norm(coluna)
        if any(hint in nome for hint in STOCK_COLUMN_HINTS):
            encontradas.append(str(coluna))
    return encontradas


def inferir_estoque_linha(row: pd.Series, estoque_col: str | None = None) -> str:
    if estoque_col and estoque_col in row.index:
        valor = _texto(row.get(estoque_col, ""))
        numero = _somente_numero(valor)
        if numero:
            return numero
        texto_valor = _norm(valor)
        if any(marker in texto_valor for marker in ZERO_STOCK_MARKERS):
            return "0"
        if any(marker in texto_valor for marker in IN_STOCK_MARKERS):
            return "1"

    texto_total = _norm(" ".join(_texto(row.get(col, "")) for col in row.index))

    for marker in ZERO_STOCK_MARKERS:
        if marker in texto_total:
            return "0"

    patterns = [
        r"(?:estoque|stock|quantidade|qtd|saldo)\s*[:#\-]?\s*(\d+)",
        r"(\d+)\s*(?:unidades|unidade|pecas|peças|itens)\s*(?:em estoque|disponiveis|disponíveis)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, texto_total, flags=re.I)
        if match:
            return str(int(match.group(1)))

    if any(marker in texto_total for marker in IN_STOCK_MARKERS):
        return "1"

    return ""


def aplicar_estoque_real(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    base = df.copy().fillna("")
    colunas = _colunas_estoque(base)
    estoque_col = colunas[0] if colunas else None

    valores = []
    confiancas = []
    for _, row in base.iterrows():
        valor = inferir_estoque_linha(row, estoque_col)
        valores.append(valor)
        confiancas.append("alto" if valor == "0" or valor.isdigit() else "baixo")

    base["Estoque real"] = valores
    base["Estoque confiança"] = confiancas

    if "Estoque" in base.columns:
        base["Estoque"] = [novo if novo != "" else antigo for novo, antigo in zip(base["Estoque real"], base["Estoque"].astype(str))]
    else:
        base["Estoque"] = base["Estoque real"]

    return base.fillna("")
