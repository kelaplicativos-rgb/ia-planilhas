import re
import unicodedata
import pandas as pd


def _normalizar_texto(texto: str) -> str:
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto)


def _valor_seguro(row, coluna):
    if coluna and coluna in row and not pd.isna(row[coluna]):
        return str(row[coluna]).strip()
    return ""


def _numero_seguro(valor):
    if not valor:
        return "0.00"

    texto = str(valor).replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return f"{float(texto):.2f}"
    except:
        return "0.00"


# =========================
# FALLBACK INTELIGENTE
# =========================
def _buscar_por_conteudo(row, tipo):
    for valor in row.values:

        if pd.isna(valor):
            continue

        texto = str(valor).strip()

        # detectar preço / estoque
        if tipo == "numero":
            try:
                v = texto.replace(",", ".")
                float(v)
                return texto
            except:
                pass

        # detectar URL imagem
        if tipo == "imagem":
            if "http" in texto and (".jpg" in texto or ".png" in texto):
                return texto

        # detectar nome (texto grande)
        if tipo == "texto":
            if len(texto) > 5:
                return texto

    return ""


# =========================
# ESTOQUE INTELIGENTE
# =========================
def mapear_estoque_bling(df_origem, modelo, colunas_detectadas, deposito_padrao):
    linhas = []

    for _, row in df_origem.iterrows():

        codigo = _valor_seguro(row, colunas_detectadas.get("codigo"))
        estoque = _valor_seguro(row, colunas_detectadas.get("estoque"))
        preco = _valor_seguro(row, colunas_detectadas.get("preco"))
        deposito = _valor_seguro(row, colunas_detectadas.get("deposito"))

        # FALLBACK
        if not estoque:
            estoque = _buscar_por_conteudo(row, "numero")

        if not preco:
            preco = _buscar_por_conteudo(row, "numero")

        if not deposito:
            deposito = deposito_padrao

        estoque = _numero_seguro(estoque)
        preco = _numero_seguro(preco)

        nova = {col: "" for col in modelo.columns}

        for col in modelo.columns:
            nome = _normalizar_texto(col)

            if "codigo" in nome:
                nova[col] = codigo

            elif "deposito" in nome:
                nova[col] = deposito

            elif "balanco" in nome or "saldo" in nome:
                nova[col] = estoque

            elif "preco" in nome:
                nova[col] = preco

        if codigo:
            linhas.append(nova)

    return pd.DataFrame(linhas)


# =========================
# CADASTRO INTELIGENTE
# =========================
def mapear_cadastro_bling(df_origem, modelo, colunas_detectadas):
    linhas = []

    for _, row in df_origem.iterrows():

        codigo = _valor_seguro(row, colunas_detectadas.get("codigo"))
        nome = _valor_seguro(row, colunas_detectadas.get("nome"))
        preco = _valor_seguro(row, colunas_detectadas.get("preco"))
        descricao = _valor_seguro(row, colunas_detectadas.get("descricao_curta"))
        marca = _valor_seguro(row, colunas_detectadas.get("marca"))
        imagem = _valor_seguro(row, colunas_detectadas.get("imagem"))

        # FALLBACK INTELIGENTE
        if not nome:
            nome = _buscar_por_conteudo(row, "texto")

        if not preco:
            preco = _buscar_por_conteudo(row, "numero")

        if not descricao:
            descricao = nome

        if not imagem:
            imagem = _buscar_por_conteudo(row, "imagem")

        preco = _numero_seguro(preco)

        nova = {col: "" for col in modelo.columns}

        for col in modelo.columns:
            nome_col = _normalizar_texto(col)

            if "codigo" in nome_col:
                nova[col] = codigo

            elif "nome" in nome_col:
                nova[col] = nome

            elif "preco" in nome_col:
                nova[col] = preco

            elif "descricao" in nome_col:
                nova[col] = descricao

            elif "marca" in nome_col:
                nova[col] = marca

            elif "imagem" in nome_col:
                nova[col] = imagem

        if codigo or nome:
            linhas.append(nova)

    return pd.DataFrame(linhas)
