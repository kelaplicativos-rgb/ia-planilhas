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
    except:
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
            except:
                pass

        if tipo == "texto":
            if len(txt) > 5:
                return txt

    return ""


# =========================
# CADASTRO BLING
# =========================
def mapear_cadastro_bling(df_origem, modelo, colunas_detectadas):

    saida = []

    for _, row in df_origem.iterrows():

        codigo = _get(row, colunas_detectadas.get("codigo"))
        nome = _get(row, colunas_detectadas.get("nome"))
        preco = _get(row, colunas_detectadas.get("preco"))
        descricao = _get(row, colunas_detectadas.get("descricao_curta"))

        if not nome:
            nome = _fallback(row, "texto")

        if not preco:
            preco = _fallback(row, "numero")

        preco = _numero(preco)

        unidade = "UN"
        situacao = "Ativo"
        ncm = "00000000"

        nova = {c: "" for c in modelo.columns}

        for col in modelo.columns:
            n = _normalizar(col)

            # 🔥 CODIGO PAI SEMPRE VAZIO
            if "pai" in n:
                nova[col] = ""

            elif "codigo" in n or "sku" in n or n == "id":
                nova[col] = codigo

            elif "nome" in n:
                nova[col] = nome

            elif "preco" in n or "valor" in n:
                nova[col] = preco

            elif "descricao" in n:
                nova[col] = descricao or nome

            elif "unidade" in n:
                nova[col] = unidade

            elif "situacao" in n or "status" in n:
                nova[col] = situacao

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

            # 🔥 CODIGO PAI SEMPRE VAZIO
            if "pai" in n:
                nova[col] = ""

            elif "codigo" in n:
                nova[col] = codigo

            elif "deposito" in n or "localizacao" in n:
                nova[col] = deposito_padrao

            elif "balanco" in n or "saldo" in n or "estoque" in n:
                nova[col] = estoque

            elif "preco" in n or "valor" in n:
                nova[col] = preco

        if codigo:
            saida.append(nova)

    return pd.DataFrame(saida, columns=modelo.columns)

def detectar_colunas(df):
    resultado = {}
    colunas = list(df.columns)

    for col in colunas:
        nome = _normalizar(col)

        if "codigo" in nome or "sku" in nome:
            resultado["codigo"] = col

        elif "nome" in nome or "descricao" in nome:
            resultado["nome"] = col

        elif "preco" in nome or "valor" in nome:
            resultado["preco"] = col

        elif "estoque" in nome or "saldo" in nome:
            resultado["estoque"] = col

        elif "imagem" in nome or "url" in nome:
            resultado["imagem"] = col

        elif "marca" in nome:
            resultado["marca"] = col

    return resultado
