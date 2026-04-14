from __future__ import annotations

import pandas as pd


def safe_df(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def safe_df_com_linhas(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0
    except Exception:
        return False


def safe_str(valor) -> str:
    try:
        if valor is None:
            return ""
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return str(valor).strip()


def normalizar_coluna(nome) -> str:
    texto = safe_str(nome).lower()
    texto = (
        texto.replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    return texto


def is_coluna_deposito(nome) -> bool:
    return "deposit" in normalizar_coluna(nome)


def is_coluna_id(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return nome_normalizado == "id" or "id produto" in nome_normalizado


def is_coluna_imagem(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return "imagem" in nome_normalizado or "url" in nome_normalizado


def detectar_duplicidades_mapping(mapping: dict) -> dict[str, list[str]]:
    usados: dict[str, list[str]] = {}

    for col_modelo, col_origem in mapping.items():
        col_origem_limpa = safe_str(col_origem)
        if not col_origem_limpa:
            continue
        usados.setdefault(col_origem_limpa, []).append(str(col_modelo))

    return {k: v for k, v in usados.items() if len(v) > 1}


def colunas_usadas_por_outros(mapping: dict, coluna_atual: str) -> set[str]:
    usados = set()

    for col_modelo, col_origem in mapping.items():
        if str(col_modelo) == str(coluna_atual):
            continue
        col_origem_limpa = safe_str(col_origem)
        if col_origem_limpa:
            usados.add(col_origem_limpa)

    return usados


def opcoes_select_mapeamento(df_fonte: pd.DataFrame, mapping: dict, coluna_atual: str) -> list[str]:
    atual = safe_str(mapping.get(coluna_atual))
    usados = colunas_usadas_por_outros(mapping, coluna_atual)

    opcoes = [""]
    for col in df_fonte.columns:
        nome = str(col)
        if nome == atual or nome not in usados:
            opcoes.append(nome)

    return opcoes
