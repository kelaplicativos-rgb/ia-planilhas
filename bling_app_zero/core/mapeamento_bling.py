import re
import unicodedata

import pandas as pd


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
}


def _normalizar_texto(texto: str) -> str:
    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def detectar_colunas(df: pd.DataFrame) -> dict:
    resultado = {}
    colunas_normalizadas = {col: _normalizar_texto(col) for col in df.columns}

    for campo, sinonimos in SINONIMOS.items():
        melhor_coluna = None
        melhor_score = -1

        for coluna_original, coluna_norm in colunas_normalizadas.items():
            score = 0

            for sinonimo in sinonimos:
                sinonimo_norm = _normalizar_texto(sinonimo)

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


def _valor_seguro(row: pd.Series, coluna: str | None, padrao: str = "") -> str:
    if not coluna:
        return padrao
    valor = row.get(coluna, padrao)
    if pd.isna(valor):
        return padrao
    return str(valor).strip()


def _numero_seguro(valor, padrao: str = "0.00") -> str:
    if valor is None:
        return padrao

    texto = str(valor).strip()

    if texto == "" or texto.lower() in {"nan", "none", "null"}:
        return padrao

    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        numero = float(texto)
        return f"{numero:.2f}"
    except Exception:
        return padrao


def _buscar_por_conteudo(row: pd.Series, tipo: str) -> str:
    for valor in row.values:
        if pd.isna(valor):
            continue

        texto = str(valor).strip()
        if not texto:
            continue

        if tipo == "numero":
            bruto = texto.replace("R$", "").replace(" ", "")
            if "," in bruto and "." in bruto:
                bruto = bruto.replace(".", "").replace(",", ".")
            elif "," in bruto:
                bruto = bruto.replace(",", ".")
            try:
                float(bruto)
                return texto
            except Exception:
                continue

        if tipo == "imagem":
            texto_lower = texto.lower()
            if texto_lower.startswith("http") and any(ext in texto_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return texto

        if tipo == "texto":
            if len(texto) > 5:
                return texto

    return ""


def _tem_algum(nome_modelo: str, opcoes: list[str]) -> bool:
    return any(opcao in nome_modelo for opcao in opcoes)


def mapear_cadastro_bling(
    df_origem: pd.DataFrame,
    modelo: pd.DataFrame,
    colunas_detectadas: dict
) -> pd.DataFrame:
    linhas_saida = []

    for _, row in df_origem.iterrows():
        valor_codigo = _valor_seguro(row, colunas_detectadas.get("codigo"))
        valor_nome = _valor_seguro(row, colunas_detectadas.get("nome"))
        valor_preco = _valor_seguro(row, colunas_detectadas.get("preco"))
        valor_desc = _valor_seguro(row, colunas_detectadas.get("descricao_curta"))
        valor_marca = _valor_seguro(row, colunas_detectadas.get("marca"))
        valor_imagem = _valor_seguro(row, colunas_detectadas.get("imagem"))
        valor_situacao = _valor_seguro(row, colunas_detectadas.get("situacao"))
        valor_unidade = _valor_seguro(row, colunas_detectadas.get("unidade"))

        if not valor_nome:
            valor_nome = _buscar_por_conteudo(row, "texto")

        if not valor_preco:
            valor_preco = _buscar_por_conteudo(row, "numero")

        if not valor_desc:
            valor_desc = valor_nome

        if not valor_imagem:
            valor_imagem = _buscar_por_conteudo(row, "imagem")

        valor_preco = _numero_seguro(valor_preco, "0.00")
        valor_situacao = valor_situacao or "Ativo"
        valor_unidade = valor_unidade or "UN"

        nova_linha = {col: "" for col in modelo.columns}

        for col_modelo in modelo.columns:
            nome_modelo = _normalizar_texto(col_modelo)

            if _tem_algum(nome_modelo, ["codigo", "sku"]):
                nova_linha[col_modelo] = valor_codigo

            elif "nome" in nome_modelo:
                nova_linha[col_modelo] = valor_nome

            elif _tem_algum(nome_modelo, ["preco", "valor"]):
                nova_linha[col_modelo] = valor_preco

            elif "descricao curta" in nome_modelo:
                nova_linha[col_modelo] = valor_desc

            elif "descricao completa" in nome_modelo or nome_modelo == "descricao":
                nova_linha[col_modelo] = valor_desc

            elif "marca" in nome_modelo:
                nova_linha[col_modelo] = valor_marca

            elif "imagem" in nome_modelo or "url" in nome_modelo:
                nova_linha[col_modelo] = valor_imagem

            elif "situacao" in nome_modelo or "status" in nome_modelo:
                nova_linha[col_modelo] = valor_situacao

            elif "unidade" in nome_modelo:
                nova_linha[col_modelo] = valor_unidade

        if valor_codigo or valor_nome:
            linhas_saida.append(nova_linha)

    return pd.DataFrame(linhas_saida, columns=modelo.columns)


def mapear_estoque_bling(
    df_origem: pd.DataFrame,
    modelo: pd.DataFrame,
    colunas_detectadas: dict,
    deposito_padrao: str
) -> pd.DataFrame:
    linhas_saida = []

    for _, row in df_origem.iterrows():
        valor_codigo = _valor_seguro(row, colunas_detectadas.get("codigo"))
        valor_nome = _valor_seguro(row, colunas_detectadas.get("nome"))
        valor_estoque = _valor_seguro(row, colunas_detectadas.get("estoque"))
        valor_preco = _valor_seguro(row, colunas_detectadas.get("preco"))
        valor_deposito = _valor_seguro(row, colunas_detectadas.get("deposito"))

        if not valor_estoque:
            valor_estoque = _buscar_por_conteudo(row, "numero")

        if not valor_preco:
            valor_preco = _buscar_por_conteudo(row, "numero")

        if not valor_deposito:
            valor_deposito = deposito_padrao.strip()

        valor_estoque = _numero_seguro(valor_estoque, "0.00")
        valor_preco = _numero_seguro(valor_preco, "0.00")

        nova_linha = {col: "" for col in modelo.columns}

        for col_modelo in modelo.columns:
            nome_modelo = _normalizar_texto(col_modelo)

            if _tem_algum(nome_modelo, ["codigo produto", "codigo", "sku"]):
                nova_linha[col_modelo] = valor_codigo

            elif _tem_algum(nome_modelo, ["deposito", "localizacao", "localizacao deposito"]):
                nova_linha[col_modelo] = valor_deposito

            elif _tem_algum(nome_modelo, ["balanco", "balanço", "estoque", "saldo", "quantidade"]):
                nova_linha[col_modelo] = valor_estoque

            elif _tem_algum(nome_modelo, ["preco unitario", "preco unitário", "valor unitario", "valor unitário", "preco", "valor"]):
                nova_linha[col_modelo] = valor_preco

            elif "nome" in nome_modelo or nome_modelo == "descricao":
                nova_linha[col_modelo] = valor_nome

        if valor_codigo:
            linhas_saida.append(nova_linha)

    return pd.DataFrame(linhas_saida, columns=modelo.columns)
