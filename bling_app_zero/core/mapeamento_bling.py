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


def _numero_seguro(valor, padrao: str = "0") -> str:
    if valor is None:
        return padrao

    texto = str(valor).strip()

    if texto == "" or texto.lower() in {"nan", "none", "null"}:
        return padrao

    texto = texto.replace("R$", "").replace(" ", "")

    # 1.234,56 -> 1234.56
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    # 12,34 -> 12.34
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        numero = float(texto)
        return f"{numero:.2f}"
    except Exception:
        return padrao


def _primeiro_campo_existente(nome_modelo: str, opcoes: list[str]) -> bool:
    return any(opcao in nome_modelo for opcao in opcoes)


def mapear_cadastro_bling(
    df_origem: pd.DataFrame,
    modelo: pd.DataFrame,
    colunas_detectadas: dict
) -> pd.DataFrame:
    linhas_saida = []

    for _, row in df_origem.iterrows():
        nova_linha = {col: "" for col in modelo.columns}

        for col_modelo in modelo.columns:
            nome_modelo = _normalizar_texto(col_modelo)

            if _primeiro_campo_existente(nome_modelo, ["codigo", "sku"]):
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("codigo"))

            elif "nome" in nome_modelo or nome_modelo == "descricao":
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("nome"))

            elif _primeiro_campo_existente(nome_modelo, ["preco", "valor"]):
                nova_linha[col_modelo] = _numero_seguro(
                    _valor_seguro(row, colunas_detectadas.get("preco")),
                    padrao="0.00"
                )

            elif "descricao curta" in nome_modelo:
                valor_desc = _valor_seguro(row, colunas_detectadas.get("descricao_curta"))
                if not valor_desc:
                    valor_desc = _valor_seguro(row, colunas_detectadas.get("nome"))
                nova_linha[col_modelo] = valor_desc

            elif "descricao completa" in nome_modelo or nome_modelo == "descricao complementar":
                valor_desc = _valor_seguro(row, colunas_detectadas.get("descricao_curta"))
                if not valor_desc:
                    valor_desc = _valor_seguro(row, colunas_detectadas.get("nome"))
                nova_linha[col_modelo] = valor_desc

            elif "marca" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("marca"))

            elif "imagem" in nome_modelo or "url" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("imagem"))

            elif "situacao" in nome_modelo or "status" in nome_modelo:
                origem_situacao = _valor_seguro(row, colunas_detectadas.get("situacao"))
                nova_linha[col_modelo] = origem_situacao if origem_situacao else "Ativo"

            elif "unidade" in nome_modelo:
                origem_unidade = _valor_seguro(row, colunas_detectadas.get("unidade"))
                nova_linha[col_modelo] = origem_unidade if origem_unidade else "UN"

        codigo = str(nova_linha.get(next((c for c in modelo.columns if "codigo" in _normalizar_texto(c)), ""), "")).strip()
        nome = str(nova_linha.get(next((c for c in modelo.columns if "nome" in _normalizar_texto(c) or _normalizar_texto(c) == "descricao"), ""), "")).strip()

        if codigo or nome:
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
        nova_linha = {col: "" for col in modelo.columns}

        valor_codigo = _valor_seguro(row, colunas_detectadas.get("codigo"))
        valor_nome = _valor_seguro(row, colunas_detectadas.get("nome"))
        valor_estoque = _numero_seguro(
            _valor_seguro(row, colunas_detectadas.get("estoque")),
            padrao="0.00"
        )
        valor_preco = _numero_seguro(
            _valor_seguro(row, colunas_detectadas.get("preco")),
            padrao="0.00"
        )
        valor_deposito_origem = _valor_seguro(row, colunas_detectadas.get("deposito"))
        valor_deposito_final = valor_deposito_origem if valor_deposito_origem else deposito_padrao.strip()

        for col_modelo in modelo.columns:
            nome_modelo = _normalizar_texto(col_modelo)

            if _primeiro_campo_existente(nome_modelo, ["codigo produto", "codigo", "sku"]):
                nova_linha[col_modelo] = valor_codigo

            elif _primeiro_campo_existente(nome_modelo, ["deposito", "localizacao", "localizacao deposito"]):
                nova_linha[col_modelo] = valor_deposito_final

            elif _primeiro_campo_existente(nome_modelo, ["balanco", "balanço", "estoque", "saldo", "quantidade"]):
                nova_linha[col_modelo] = valor_estoque

            elif _primeiro_campo_existente(nome_modelo, ["preco unitario", "preco unitário", "valor unitario", "valor unitário", "preco", "valor"]):
                nova_linha[col_modelo] = valor_preco

            elif "nome" in nome_modelo or nome_modelo == "descricao":
                nova_linha[col_modelo] = valor_nome

        # só mantém linha se tiver código
        if valor_codigo:
            # garante obrigatórios mínimos mesmo se o nome da coluna do modelo variar um pouco
            for col_modelo in modelo.columns:
                nome_modelo = _normalizar_texto(col_modelo)

                if _primeiro_campo_existente(nome_modelo, ["deposito", "localizacao"]):
                    if not str(nova_linha[col_modelo]).strip():
                        nova_linha[col_modelo] = deposito_padrao.strip()

                if _primeiro_campo_existente(nome_modelo, ["balanco", "balanço", "estoque", "saldo", "quantidade"]):
                    if not str(nova_linha[col_modelo]).strip():
                        nova_linha[col_modelo] = "0.00"

                if _primeiro_campo_existente(nome_modelo, ["preco unitario", "preco unitário", "valor unitario", "valor unitário", "preco", "valor"]):
                    if not str(nova_linha[col_modelo]).strip():
                        nova_linha[col_modelo] = "0.00"

            linhas_saida.append(nova_linha)

    return pd.DataFrame(linhas_saida, columns=modelo.columns)
