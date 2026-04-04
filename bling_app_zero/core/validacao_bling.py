from __future__ import annotations

import re
import unicodedata
import pandas as pd


def _normalizar_texto(texto) -> str:
    if texto is None:
        return ""

    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _slug(texto) -> str:
    texto = _normalizar_texto(texto)
    texto = texto.replace("/", " ")
    texto = texto.replace("\\", " ")
    texto = texto.replace("-", " ")
    texto = texto.replace("_", " ")
    texto = re.sub(r"[^a-z0-9 ]+", "", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def _coluna_por_trecho(df: pd.DataFrame, trechos: list[str]):
    if df is None or df.empty:
        return None

    mapa = {col: _slug(col) for col in df.columns}
    trechos_norm = [_slug(t) for t in trechos if _slug(t)]

    for trecho in trechos_norm:
        for col, nome in mapa.items():
            if nome == trecho:
                return col

    for trecho in trechos_norm:
        for col, nome in mapa.items():
            if trecho in nome:
                return col

    return None


def _texto(valor) -> str:
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    return str(valor).strip()


def _numero(valor):
    texto = _texto(valor)

    if not texto:
        return None

    texto = re.sub(r"[^\d,.\-]", "", texto)

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")

    if texto in {"", "-", ".", "-.", ".-", "--"}:
        return None

    try:
        return float(texto)
    except Exception:
        return None


def _limpar_gtin(valor) -> str:
    return re.sub(r"\D+", "", _texto(valor))


def _gtin_valido(gtin: str) -> bool:
    gtin = _limpar_gtin(gtin)

    if not gtin:
        return False

    if len(gtin) not in (8, 12, 13, 14):
        return False

    numeros = [int(c) for c in gtin]
    digito_informado = numeros[-1]
    corpo = numeros[:-1]

    soma = 0
    peso = 3

    for n in reversed(corpo):
        soma += n * peso
        peso = 1 if peso == 3 else 3

    digito_calculado = (10 - (soma % 10)) % 10
    return digito_calculado == digito_informado


def _contar_urls_invalidas_multiplas(valor: str) -> bool:
    texto = _texto(valor)
    if not texto:
        return False

    partes = [p.strip() for p in texto.split("|") if p.strip()]
    if not partes:
        return False

    for parte in partes:
        if not re.match(r"^https?://", parte, flags=re.IGNORECASE):
            return True

    return False


def validar_cadastro_bling(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    erros = []
    avisos = []

    if df is None or df.empty:
        erros.append("A planilha de cadastro está vazia.")
        return erros, avisos

    col_codigo = _coluna_por_trecho(df, ["codigo", "sku", "codigo produto"])
    col_codigo_pai = _coluna_por_trecho(df, ["codigo pai", "id pai"])
    col_unidade = _coluna_por_trecho(df, ["unidade", "und", "un"])
    col_ncm = _coluna_por_trecho(df, ["ncm"])
    col_preco = _coluna_por_trecho(df, ["preco", "valor", "preco venda"])
    col_nome = _coluna_por_trecho(df, ["nome", "produto"])
    col_descricao = _coluna_por_trecho(df, ["descricao"])
    col_descricao_curta = _coluna_por_trecho(df, ["descricao curta"])
    col_video = _coluna_por_trecho(df, ["video"])
    col_link_externo = _coluna_por_trecho(df, ["link externo", "url produto", "link produto"])
    col_gtin = _coluna_por_trecho(df, ["gtin", "ean", "codigo barras", "codigo de barras"])

    col_imagem_1 = _coluna_por_trecho(df, ["imagem 1", "imagem1"])
    col_imagem_2 = _coluna_por_trecho(df, ["imagem 2", "imagem2"])
    col_imagem_3 = _coluna_por_trecho(df, ["imagem 3", "imagem3"])
    col_imagem_4 = _coluna_por_trecho(df, ["imagem 4", "imagem4"])
    col_imagem_5 = _coluna_por_trecho(df, ["imagem 5", "imagem5"])
    col_imagem_unica = _coluna_por_trecho(df, ["imagem", "imagens"])

    if col_codigo is None:
        erros.append("Coluna de código do produto não foi encontrada.")
    if col_unidade is None:
        erros.append("Coluna de unidade não foi encontrada.")
    if col_ncm is None:
        erros.append("Coluna de NCM não foi encontrada.")
    if col_preco is None:
        erros.append("Coluna de preço não foi encontrada.")
    if col_nome is None and col_descricao is None:
        erros.append("Coluna de nome/título do produto não foi encontrada.")
    if col_descricao_curta is None:
        avisos.append("Coluna de descrição curta não foi encontrada.")

    if erros:
        return erros, avisos

    for i, row in df.iterrows():
        linha = i + 2

        codigo = _texto(row.get(col_codigo, ""))
        unidade = _texto(row.get(col_unidade, ""))
        ncm = _texto(row.get(col_ncm, ""))
        preco = _texto(row.get(col_preco, ""))
        nome = _texto(row.get(col_nome, "")) if col_nome else ""
        descricao = _texto(row.get(col_descricao, "")) if col_descricao else ""
        descricao_curta = _texto(row.get(col_descricao_curta, "")) if col_descricao_curta else ""
        video = _texto(row.get(col_video, "")) if col_video else ""
        link_externo = _texto(row.get(col_link_externo, "")) if col_link_externo else ""
        gtin = _texto(row.get(col_gtin, "")) if col_gtin else ""

        if not codigo:
            erros.append(f"Linha {linha}: código do produto vazio.")

        if col_codigo_pai:
            codigo_pai = _texto(row.get(col_codigo_pai, ""))
            if codigo_pai:
                erros.append(f"Linha {linha}: código pai deve ficar vazio.")

        if not unidade:
            erros.append(f"Linha {linha}: unidade vazia.")

        if not ncm:
            erros.append(f"Linha {linha}: NCM vazio.")

        if not preco:
            erros.append(f"Linha {linha}: preço vazio.")
        else:
            preco_float = _numero(preco)
            if preco_float is None:
                erros.append(f"Linha {linha}: preço inválido.")
            elif preco_float <= 0:
                avisos.append(f"Linha {linha}: preço igual ou menor que zero.")

        if not nome and not descricao:
            erros.append(f"Linha {linha}: nome/título do produto vazio.")

        if not descricao_curta:
            avisos.append(f"Linha {linha}: descrição curta vazia.")

        if video:
            erros.append(f"Linha {linha}: coluna de vídeo deve ficar vazia.")

        if link_externo:
            erros.append(f"Linha {linha}: coluna de link externo deve ficar vazia.")

        if gtin:
            gtin_limpo = _limpar_gtin(gtin)
            if len(gtin_limpo) not in (8, 12, 13, 14):
                erros.append(f"Linha {linha}: GTIN/EAN com comprimento inválido.")
            elif not _gtin_valido(gtin_limpo):
                erros.append(f"Linha {linha}: GTIN/EAN inválido.")

        for col_imagem in [col_imagem_1, col_imagem_2, col_imagem_3, col_imagem_4, col_imagem_5]:
            if col_imagem:
                valor = _texto(row.get(col_imagem, ""))
                if valor and not re.match(r"^https?://", valor, flags=re.IGNORECASE):
                    erros.append(f"Linha {linha}: {col_imagem} não contém URL válida.")

        if col_imagem_unica:
            valor = _texto(row.get(col_imagem_unica, ""))
            if _contar_urls_invalidas_multiplas(valor):
                erros.append(f"Linha {linha}: coluna de imagens possui URL inválida.")

    return erros, avisos


def validar_estoque_bling(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    erros = []
    avisos = []

    if df is None or df.empty:
        erros.append("A planilha de estoque está vazia.")
        return erros, avisos

    col_codigo = _coluna_por_trecho(df, ["codigo produto", "codigo", "sku"])
    col_codigo_pai = _coluna_por_trecho(df, ["codigo pai", "id pai"])
    col_deposito = _coluna_por_trecho(df, ["deposito", "localizacao", "almoxarifado"])
    col_balanco = _coluna_por_trecho(df, ["balanco", "balanco estoque", "saldo", "estoque", "quantidade"])
    col_preco = _coluna_por_trecho(df, ["preco unitario", "preco unitario produto", "preco", "valor"])
    col_nome = _coluna_por_trecho(df, ["nome", "produto", "descricao produto"])

    if col_codigo is None:
        erros.append("Coluna de código do produto não foi encontrada.")
    if col_deposito is None:
        erros.append("Coluna de depósito não foi encontrada.")
    if col_balanco is None:
        erros.append("Coluna de balanço/estoque não foi encontrada.")

    if erros:
        return erros, avisos

    for i, row in df.iterrows():
        linha = i + 2

        codigo = _texto(row.get(col_codigo, ""))
        deposito = _texto(row.get(col_deposito, ""))
        balanco = _texto(row.get(col_balanco, ""))
        preco = _texto(row.get(col_preco, "")) if col_preco else ""
        nome = _texto(row.get(col_nome, "")) if col_nome else ""

        if not codigo:
            erros.append(f"Linha {linha}: código do produto vazio.")

        if col_codigo_pai:
            codigo_pai = _texto(row.get(col_codigo_pai, ""))
            if codigo_pai:
                erros.append(f"Linha {linha}: código pai deve ficar vazio.")

        if not deposito:
            erros.append(f"Linha {linha}: depósito vazio.")

        if not balanco:
            erros.append(f"Linha {linha}: balanço/estoque vazio.")
        else:
            balanco_float = _numero(balanco)
            if balanco_float is None:
                erros.append(f"Linha {linha}: balanço/estoque inválido.")
            elif balanco_float < 0:
                avisos.append(f"Linha {linha}: balanço/estoque negativo.")

        if col_preco:
            if not preco:
                avisos.append(f"Linha {linha}: preço unitário vazio.")
            else:
                preco_float = _numero(preco)
                if preco_float is None:
                    erros.append(f"Linha {linha}: preço unitário inválido.")
                elif preco_float < 0:
                    avisos.append(f"Linha {linha}: preço unitário negativo.")

        if col_nome and not nome:
            avisos.append(f"Linha {linha}: nome do produto vazio.")

    return erros, avisos
