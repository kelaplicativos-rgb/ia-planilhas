import re
import unicodedata
import pandas as pd


def _normalizar(texto):
    texto = str(texto).lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto)


def _get(row, col):
    if col and col in row and not pd.isna(row[col]):
        return str(row[col]).strip()
    return ""


def _numero(valor):
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


def _fallback(row, tipo):
    for v in row.values:
        if pd.isna(v):
            continue

        txt = str(v).strip()

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
# CADASTRO CORRIGIDO
# =========================
def mapear_cadastro_bling(df, modelo, colunas):

    saida = []

    for _, row in df.iterrows():

        codigo = _get(row, colunas.get("codigo"))
        nome = _get(row, colunas.get("nome"))
        preco = _get(row, colunas.get("preco"))
        descricao = _get(row, colunas.get("descricao_curta"))

        if not nome:
            nome = _fallback(row, "texto")

        if not preco:
            preco = _fallback(row, "numero")

        preco = _numero(preco)

        # 🔥 CORREÇÕES BLING
        unidade = "UN"
        situacao = "Ativo"
        ncm = "00000000"

        nova = {c: "" for c in modelo.columns}

        for col in modelo.columns:
            n = _normalizar(col)

            if "codigo" in n and "pai" not in n:
                nova[col] = codigo

            elif "nome" in n:
                nova[col] = nome

            elif "preco" in n:
                nova[col] = preco

            elif "descricao" in n:
                nova[col] = descricao or nome

            elif "unidade" in n:
                nova[col] = unidade

            elif "situacao" in n:
                nova[col] = situacao

            elif "ncm" in n:
                nova[col] = ncm

            # 🚫 IMPORTANTE: NÃO PREENCHER CODIGO PAI
            elif "pai" in n:
                nova[col] = ""

        if codigo or nome:
            saida.append(nova)

    return pd.DataFrame(saida)


# =========================
# ESTOQUE CORRIGIDO
# =========================
def mapear_estoque_bling(df, modelo, colunas, deposito_padrao):

    saida = []

    for _, row in df.iterrows():

        codigo = _get(row, colunas.get("codigo"))
        estoque = _get(row, colunas.get("estoque"))
        preco = _get(row, colunas.get("preco"))

        if not estoque:
            estoque = _fallback(row, "numero")

        if not preco:
            preco = _fallback(row, "numero")

        estoque = _numero(estoque)
        preco = _numero(preco)

        nova = {c: "" for c in modelo.columns}

        for col in modelo.columns:
            n = _normalizar(col)

            if "codigo" in n:
                nova[col] = codigo

            elif "deposito" in n:
                nova[col] = deposito_padrao

            elif "balanco" in n or "saldo" in n:
                nova[col] = estoque

            elif "preco" in n:
                nova[col] = preco

        if codigo:
            saida.append(nova)

    return pd.DataFrame(saida)
