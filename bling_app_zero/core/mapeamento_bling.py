import re
import unicodedata
import pandas as pd


def _normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _get(row, col):
    if col and col in row and not pd.isna(row[col]):
        return str(row[col]).strip()
    return ""


def _numero(valor, padrao="0.00"):
    if not valor:
        return padrao

    texto = str(valor).replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return f"{float(texto):.2f}"
    except Exception:
        return padrao


def _fallback(row, tipo):
    for v in row.values:
        if pd.isna(v):
            continue

        txt = str(v).strip()
        if not txt:
            continue

        if tipo == "numero":
            try:
                float(txt.replace(",", "."))
                return txt
            except Exception:
                pass

        if tipo == "texto":
            if len(txt) > 5:
                return txt

        if tipo == "imagem":
            t = txt.lower()
            if t.startswith("http") and any(ext in t for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return txt

    return ""


# =========================
# CADASTRO BLING
# REGRAS FIXAS:
# 1) descrição vai SOMENTE em "descrição curta"
# 2) coluna "vídeo" fica SEMPRE vazia
# =========================
def mapear_cadastro_bling(df_origem, modelo, colunas_detectadas):

    saida = []

    for _, row in df_origem.iterrows():

        codigo = _get(row, colunas_detectadas.get("codigo"))
        nome = _get(row, colunas_detectadas.get("nome"))
        preco = _get(row, colunas_detectadas.get("preco"))
        descricao_curta = _get(row, colunas_detectadas.get("descricao_curta"))
        imagem = _get(row, colunas_detectadas.get("imagem"))
        marca = _get(row, colunas_detectadas.get("marca"))

        if not nome:
            nome = _fallback(row, "texto")

        if not preco:
            preco = _fallback(row, "numero")

        if not descricao_curta:
            descricao_curta = nome

        if not imagem:
            imagem = _fallback(row, "imagem")

        preco = _numero(preco)

        unidade = "UN"
        situacao = "Ativo"
        ncm = "00000000"

        nova = {c: "" for c in modelo.columns}

        for col in modelo.columns:
            n = _normalizar(col)

            # código pai sempre vazio
            if "pai" in n:
                nova[col] = ""

            # código principal
            elif ("codigo" in n or "sku" in n or n == "id") and "pai" not in n:
                nova[col] = codigo

            # nome
            elif "nome" in n:
                nova[col] = nome

            # preço
            elif "preco" in n or "valor" in n:
                nova[col] = preco

            # REGRA FIXA: descrição curta recebe a descrição
            elif "descricao curta" in n or "descricao curta" in n:
                nova[col] = descricao_curta

            # REGRA FIXA: coluna descrição comum fica sempre vazia
            elif n == "descricao" or ("descricao" in n and "curta" not in n):
                nova[col] = ""

            # marca
            elif "marca" in n:
                nova[col] = marca

            # links apenas nas colunas de imagem
            elif "imagem" in n or ("url" in n and "video" not in n):
                nova[col] = imagem

            # REGRA FIXA: vídeo sempre vazio
            elif "video" in n or "vídeo" in n:
                nova[col] = ""

            # unidade
            elif "unidade" in n:
                nova[col] = unidade

            # situação
            elif "situacao" in n or "status" in n:
                nova[col] = situacao

            # ncm
            elif "ncm" in n:
                nova[col] = ncm

        if codigo or nome:
            saida.append(nova)

    return pd.DataFrame(saida, columns=modelo.columns)


# =========================
# ESTOQUE BLING
# =========================
def mapear_estoque_bling(df_origem, modelo, colunas_detectadas, deposito_padrao):

    saida = []

    for _, row in df_origem.iterrows():

        codigo = _get(row, colunas_detectadas.get("codigo"))
        estoque = _get(row, colunas_detectadas.get("estoque"))
        preco = _get(row, colunas_detectadas.get("preco"))

        if not estoque:
            estoque = _fallback(row, "numero")

        if not preco:
            preco = _fallback(row, "numero")

        estoque = _numero(estoque)
        preco = _numero(preco)

        nova = {c: "" for c in modelo.columns}

        for col in modelo.columns:
            n = _normalizar(col)

            # código pai sempre vazio
            if "pai" in n:
                nova[col] = ""

            elif "codigo" in n:
                nova[col] = codigo

            elif "deposito" in n or "localizacao" in n:
                nova[col] = deposito_padrao

            elif "balanco" in n or "balanço" in n or "saldo" in n or "estoque" in n:
                nova[col] = estoque

            elif "preco" in n or "valor" in n:
                nova[col] = preco

        if codigo:
            saida.append(nova)

    return pd.DataFrame(saida, columns=modelo.columns)


# =========================
# DETECÇÃO DE COLUNAS
# =========================
def detectar_colunas(df):
    resultado = {}
    colunas = list(df.columns)

    for col in colunas:
        nome = _normalizar(col)

        if "codigo" in nome or "código" in nome or "sku" in nome:
            resultado["codigo"] = col

        elif "nome" in nome or "produto" in nome:
            resultado["nome"] = col

        elif "preco" in nome or "preço" in nome or "valor" in nome:
            resultado["preco"] = col

        elif "descricao curta" in nome or "descrição curta" in nome:
            resultado["descricao_curta"] = col

        elif "descricao" in nome or "descrição" in nome:
            if "descricao_curta" not in resultado:
                resultado["descricao_curta"] = col

        elif "estoque" in nome or "saldo" in nome or "quantidade" in nome:
            resultado["estoque"] = col

        elif "imagem" in nome or "url" in nome or "foto" in nome:
            resultado["imagem"] = col

        elif "marca" in nome or "fabricante" in nome:
            resultado["marca"] = col

    return resultado
