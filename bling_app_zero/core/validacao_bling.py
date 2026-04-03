import pandas as pd


def _coluna_por_trecho(df: pd.DataFrame, trechos: list[str]):
    for col in df.columns:
        nome = str(col).lower().strip()
        for trecho in trechos:
            if trecho in nome:
                return col
    return None


def validar_cadastro_bling(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    erros = []
    avisos = []

    col_codigo = _coluna_por_trecho(df, ["codigo", "sku", "id"])
    col_codigo_pai = _coluna_por_trecho(df, ["codigo pai", "id pai"])
    col_unidade = _coluna_por_trecho(df, ["unidade"])
    col_ncm = _coluna_por_trecho(df, ["ncm"])
    col_preco = _coluna_por_trecho(df, ["preco", "valor"])
    col_nome = _coluna_por_trecho(df, ["nome", "descricao"])

    if col_codigo is None:
        erros.append("Coluna de código do produto não foi encontrada.")
    if col_unidade is None:
        erros.append("Coluna de unidade não foi encontrada.")
    if col_ncm is None:
        erros.append("Coluna de NCM não foi encontrada.")
    if col_preco is None:
        erros.append("Coluna de preço não foi encontrada.")

    if erros:
        return erros, avisos

    for i, row in df.iterrows():
        linha = i + 2

        codigo = str(row.get(col_codigo, "")).strip()
        unidade = str(row.get(col_unidade, "")).strip()
        ncm = str(row.get(col_ncm, "")).strip()
        preco = str(row.get(col_preco, "")).strip()
        nome = str(row.get(col_nome, "")).strip() if col_nome else ""

        if not codigo:
            erros.append(f"Linha {linha}: código do produto vazio.")

        if col_codigo_pai:
            codigo_pai = str(row.get(col_codigo_pai, "")).strip()
            if codigo_pai:
                erros.append(f"Linha {linha}: código pai deve ficar vazio.")

        if not unidade:
            erros.append(f"Linha {linha}: unidade vazia.")

        if not ncm:
            erros.append(f"Linha {linha}: NCM vazio.")

        if not preco:
            erros.append(f"Linha {linha}: preço vazio.")

        try:
            preco_float = float(preco.replace(".", "").replace(",", ".")) if "," in preco and "." in preco else float(preco.replace(",", "."))
            if preco_float <= 0:
                avisos.append(f"Linha {linha}: preço igual ou menor que zero.")
        except Exception:
            erros.append(f"Linha {linha}: preço inválido.")

        if not nome:
            avisos.append(f"Linha {linha}: nome/descrição parece vazio.")

    return erros, avisos


def validar_estoque_bling(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    erros = []
    avisos = []

    col_codigo = _coluna_por_trecho(df, ["codigo produto", "codigo", "sku"])
    col_codigo_pai = _coluna_por_trecho(df, ["codigo pai", "id pai"])
    col_deposito = _coluna_por_trecho(df, ["deposito", "localizacao"])
    col_balanco = _coluna_por_trecho(df, ["balanco", "balanço", "saldo", "estoque"])
    col_preco = _coluna_por_trecho(df, ["preco unitario", "preco unitário", "valor"])

    if col_codigo is None:
        erros.append("Coluna de código do produto não foi encontrada.")
    if col_deposito is None:
        erros.append("Coluna de depósito não foi encontrada.")
    if col_balanco is None:
        erros.append("Coluna de balanço/estoque não foi encontrada.")
    if col_preco is None:
        erros.append("Coluna de preço unitário não foi encontrada.")

    if erros:
        return erros, avisos

    for i, row in df.iterrows():
        linha = i + 2

        codigo = str(row.get(col_codigo, "")).strip()
        deposito = str(row.get(col_deposito, "")).strip()
        balanco = str(row.get(col_balanco, "")).strip()
        preco = str(row.get(col_preco, "")).strip()

        if not codigo:
            erros.append(f"Linha {linha}: código do produto vazio.")

        if col_codigo_pai:
            codigo_pai = str(row.get(col_codigo_pai, "")).strip()
            if codigo_pai:
                erros.append(f"Linha {linha}: código pai deve ficar vazio.")

        if not deposito:
            erros.append(f"Linha {linha}: depósito vazio.")

        if not balanco:
            erros.append(f"Linha {linha}: balanço vazio.")

        if not preco:
            erros.append(f"Linha {linha}: preço unitário vazio.")

        try:
            balanco_float = float(balanco.replace(".", "").replace(",", ".")) if "," in balanco and "." in balanco else float(balanco.replace(",", "."))
            if balanco_float < 0:
                avisos.append(f"Linha {linha}: balanço negativo.")
        except Exception:
            erros.append(f"Linha {linha}: balanço inválido.")

        try:
            preco_float = float(preco.replace(".", "").replace(",", ".")) if "," in preco and "." in preco else float(preco.replace(",", "."))
            if preco_float < 0:
                avisos.append(f"Linha {linha}: preço unitário negativo.")
        except Exception:
            erros.append(f"Linha {linha}: preço unitário inválido.")

    return erros, avisos
