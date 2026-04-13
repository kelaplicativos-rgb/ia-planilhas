from __future__ import annotations


CAMPOS_OBRIGATORIOS = [
    "Código",
    "Descrição",
    "Preço de venda",
]


DEFAULTS = {
    "Situação": "Ativo",
    "Unidade": "UN",
}


def aplicar_defaults(df):
    for col, val in DEFAULTS.items():
        if col in df.columns:
            df[col] = df[col].fillna(val)
    return df
