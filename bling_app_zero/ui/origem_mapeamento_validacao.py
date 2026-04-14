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

    try:
        texto = str(valor).strip()
    except Exception:
        return ""

    if texto.lower() in {"none", "nan", "nat"}:
        return ""

    return texto


def normalizar_coluna(nome) -> str:
    texto = safe_str(nome).lower()
    texto = (
        texto.replace("ã", "a")
        .replace("á", "a")
        .replace("à", "a")
        .replace("â", "a")
        .replace("ä", "a")
        .replace("é", "e")
        .replace("ê", "e")
        .replace("ë", "e")
        .replace("í", "i")
        .replace("ï", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("õ", "o")
        .replace("ö", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ç", "c")
    )
    return " ".join(texto.split())


def normalizar_chave_origem(nome) -> str:
    return normalizar_coluna(nome)


def is_coluna_deposito(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return "deposit" in nome_normalizado


def is_coluna_id(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return nome_normalizado == "id" or "id produto" in nome_normalizado


def is_coluna_imagem(nome) -> bool:
    nome_normalizado = normalizar_coluna(nome)
    return "imagem" in nome_normalizado or "url" in nome_normalizado


def detectar_duplicidades_mapping(mapping: dict) -> dict[str, list[str]]:
    usados_normalizados: dict[str, list[str]] = {}
    rotulo_original_por_chave: dict[str, str] = {}

    for col_modelo, col_origem in dict(mapping or {}).items():
        col_modelo_limpa = safe_str(col_modelo)
        col_origem_limpa = safe_str(col_origem)

        if not col_modelo_limpa or not col_origem_limpa:
            continue

        chave = normalizar_chave_origem(col_origem_limpa)
        if not chave:
            continue

        usados_normalizados.setdefault(chave, []).append(col_modelo_limpa)
        rotulo_original_por_chave.setdefault(chave, col_origem_limpa)

    duplicados: dict[str, list[str]] = {}

    for chave, colunas_modelo in usados_normalizados.items():
        if len(colunas_modelo) > 1:
            rotulo = rotulo_original_por_chave.get(chave, chave)
            duplicados[rotulo] = colunas_modelo

    return duplicados


def colunas_usadas_por_outros(mapping: dict, coluna_atual: str) -> set[str]:
    usados_normalizados: set[str] = set()

    for col_modelo, col_origem in dict(mapping or {}).items():
        if safe_str(col_modelo) == safe_str(coluna_atual):
            continue

        col_origem_limpa = safe_str(col_origem)
        if not col_origem_limpa:
            continue

        chave = normalizar_chave_origem(col_origem_limpa)
        if chave:
            usados_normalizados.add(chave)

    return usados_normalizados


def opcoes_select_mapeamento(
    df_fonte: pd.DataFrame,
    mapping: dict,
    coluna_atual: str,
) -> list[str]:
    if not safe_df(df_fonte):
        return [""]

    atual = safe_str(dict(mapping or {}).get(coluna_atual))
    atual_normalizado = normalizar_chave_origem(atual)
    usados = colunas_usadas_por_outros(mapping, coluna_atual)

    opcoes = [""]
    adicionados_normalizados: set[str] = set()

    for col in df_fonte.columns:
        nome = safe_str(col)
        if not nome:
            continue

        chave = normalizar_chave_origem(nome)
        if not chave:
            continue

        if chave == atual_normalizado or chave not in usados:
            if chave not in adicionados_normalizados:
                opcoes.append(nome)
                adicionados_normalizados.add(chave)

    return opcoes
    
