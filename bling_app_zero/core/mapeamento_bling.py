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
            bruto = txt.replace("R$", "").replace(" ", "")
            if "," in bruto and "." in bruto:
                bruto = bruto.replace(".", "").replace(",", ".")
            elif "," in bruto:
                bruto = bruto.replace(",", ".")
            try:
                float(bruto)
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


SINONIMOS = {
    "codigo": [
        "codigo", "código", "sku", "ref", "referencia", "referência",
        "cod", "id produto", "id", "part number"
    ],
    "nome": [
        "nome", "produto", "descricao", "descrição", "titulo", "título",
        "nome produto", "descricao produto", "descrição produto"
    ],
    "preco": [
        "preco", "preço", "valor", "price", "preco venda", "preço venda",
        "valor venda", "preco unitario", "preço unitário", "preco unitário"
    ],
    "descricao_curta": [
        "descricao curta", "descrição curta", "descricao", "descrição",
        "detalhes", "resumo", "short description"
    ],
    "marca": [
        "marca", "brand", "fabricante", "fornecedor marca"
    ],
    "imagem": [
        "imagem", "imagens", "foto", "fotos", "url imagem", "url da imagem",
        "image", "images", "link imagem", "link da imagem"
    ],
    "estoque": [
        "estoque", "saldo", "quantidade", "qtd", "qtde", "disponivel",
        "disponível", "inventory", "stock", "balanco", "balanço"
    ],
    "deposito": [
        "deposito", "depósito", "armazem", "armazém", "local", "warehouse",
        "localizacao", "localização"
    ],
    "situacao": [
        "situacao", "situação", "status", "ativo", "status produto"
    ],
    "unidade": [
        "unidade", "und", "un", "unit", "u.m."
    ],
    "ncm": [
        "ncm", "classificacao fiscal", "classificação fiscal"
    ],
}


def detectar_colunas(df: pd.DataFrame) -> dict:
    resultado = {}
    colunas_normalizadas = {col: _normalizar(col) for col in df.columns}

    for campo, sinonimos in SINONIMOS.items():
        melhor_coluna = None
        melhor_score = -1

        for coluna_original, coluna_norm in colunas_normalizadas.items():
            score = 0

            for sinonimo in sinonimos:
                sinonimo_norm = _normalizar(sinonimo)

                if coluna_norm == sinonimo_norm:
                    score = max(score, 100)
                elif sinonimo_norm in coluna_norm:
                    score = max(score, 80)
                elif coluna_norm in sinonimo_norm:
                    score = max(score, 60)

            if score > melhor_score:
                melhor_score = score
                melhor_coluna = coluna_original

        resultado[campo] = melhor_coluna if melhor_score >= 60 else None

    return resultado


def mapear_cadastro_bling(df, modelo, colunas):
    saida = []

    for _, row in df.iterrows():
        codigo = _get(row, colunas.get("codigo"))
        nome = _get(row, colunas.get("nome"))
        preco = _get(row, colunas.get("preco"))
        descricao = _get(row, colunas.get("descricao_curta"))
        marca = _get(row, colunas.get("marca"))
        imagem = _get(row, colunas.get("imagem"))
        unidade_origem = _get(row, colunas.get("unidade"))
        situacao_origem = _get(row, colunas.get("situacao"))
        ncm_origem = _get(row, colunas.get("ncm"))

        if not nome:
            nome = _fallback(row, "texto")

        if not preco:
            preco = _fallback(row, "numero")

        if not descricao:
            descricao = nome

        if not imagem:
            imagem = _fallback(row, "imagem")

        preco = _numero(preco, "0.00")
        unidade = unidade_origem if unidade_origem else "UN"
        situacao = situacao_origem if situacao_origem else "Ativo"
        ncm = ncm_origem if ncm_origem else "00000000"

        nova = {c: "" for c in modelo.columns}

        for col in modelo.columns:
            n = _normalizar(col)

            if "codigo pai" in n or ("pai" in n and "codigo" in n) or n == "id pai":
                nova[col] = ""

            elif ("codigo" in n or "sku" in n or n == "id") and "pai" not in n:
                nova[col] = codigo

            elif "nome" in n or n == "descricao":
                nova[col] = nome

            elif "preco" in n or "valor" in n:
                nova[col] = preco

            elif "descricao curta" in n:
                nova[col] = descricao

            elif "descricao" in n:
                nova[col] = descricao

            elif "marca" in n:
                nova[col] = marca

            elif "imagem" in n or "url" in n:
                nova[col] = imagem

            elif "unidade" in n:
                nova[col] = unidade

            elif "situacao" in n or "status" in n:
                nova[col] = situacao

            elif "ncm" in n:
                nova[col] = ncm

        if codigo or nome:
            saida.append(nova)

    return pd.DataFrame(saida, columns=modelo.columns)


def mapear_estoque_bling(df, modelo, colunas, deposito_padrao):
    saida = []

    for _, row in df.iterrows():
        codigo = _get(row, colunas.get("codigo"))
        estoque = _get(row, colunas.get("estoque"))
        preco = _get(row, colunas.get("preco"))
        deposito = _get(row, colunas.get("deposito"))

        if not estoque:
            estoque = _fallback(row, "numero")

        if not preco:
            preco = _fallback(row, "numero")

        if not deposito:
            deposito = deposito_padrao

        estoque = _numero(estoque, "0.00")
        preco = _numero(preco, "0.00")

        nova = {c: "" for c in modelo.columns}

        for col in modelo.columns:
            n = _normalizar(col)

            if "codigo pai" in n or ("pai" in n and "codigo" in n) or n == "id pai":
                nova[col] = ""

            elif "codigo produto" in n or ("codigo" in n and "pai" not in n):
                nova[col] = codigo

            elif "deposito" in n or "localizacao" in n:
                nova[col] = deposito

            elif "balanco" in n or "balanço" in n or "saldo" in n or "estoque" in n:
                nova[col] = estoque

            elif "preco unitario" in n or "preco unitário" in n or "valor unitario" in n or "preco" in n or "valor" in n:
                nova[col] = preco

        if codigo:
            saida.append(nova)

    return pd.DataFrame(saida, columns=modelo.columns)
