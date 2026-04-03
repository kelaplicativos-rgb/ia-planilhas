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
        "valor venda", "preco unitario", "preço unitário"
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
        "disponível", "inventory", "stock"
    ],
    "deposito": [
        "deposito", "depósito", "armazem", "armazém", "local", "warehouse"
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
    """
    Detecta automaticamente as colunas de uma planilha qualquer.
    Retorna um dicionário com o campo lógico e a coluna encontrada.
    """
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

        if melhor_score >= 60:
            resultado[campo] = melhor_coluna
        else:
            resultado[campo] = None

    return resultado


def _valor_seguro(row: pd.Series, coluna: str | None, padrao: str = ""):
    if not coluna:
        return padrao
    valor = row.get(coluna, padrao)
    if pd.isna(valor):
        return padrao
    return str(valor).strip()


def mapear_cadastro_bling(
    df_origem: pd.DataFrame,
    modelo: pd.DataFrame,
    colunas_detectadas: dict
) -> pd.DataFrame:
    """
    Preenche o modelo de cadastro do Bling com base na planilha de origem.
    """
    linhas_saida = []

    for _, row in df_origem.iterrows():
        nova_linha = {col: "" for col in modelo.columns}

        for col_modelo in modelo.columns:
            nome_modelo = _normalizar_texto(col_modelo)

            if "codigo" in nome_modelo or "sku" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("codigo"))

            elif "nome" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("nome"))

            elif "preco" in nome_modelo or "preco de venda" in nome_modelo or "valor" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("preco"))

            elif "descricao curta" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("descricao_curta"))

            elif nome_modelo == "descricao" or "descricao completa" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("descricao_curta"))

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

        linhas_saida.append(nova_linha)

    return pd.DataFrame(linhas_saida, columns=modelo.columns)


def mapear_estoque_bling(
    df_origem: pd.DataFrame,
    modelo: pd.DataFrame,
    colunas_detectadas: dict,
    deposito_padrao: str
) -> pd.DataFrame:
    """
    Preenche o modelo de estoque do Bling com base na planilha de origem.
    """
    linhas_saida = []

    for _, row in df_origem.iterrows():
        nova_linha = {col: "" for col in modelo.columns}

        for col_modelo in modelo.columns:
            nome_modelo = _normalizar_texto(col_modelo)

            if "codigo" in nome_modelo or "sku" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("codigo"))

            elif "saldo" in nome_modelo or "estoque" in nome_modelo or "quantidade" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("estoque"))

            elif "deposito" in nome_modelo or "deposito" == nome_modelo:
                origem_deposito = _valor_seguro(row, colunas_detectadas.get("deposito"))
                nova_linha[col_modelo] = origem_deposito if origem_deposito else deposito_padrao

            elif "nome" in nome_modelo:
                nova_linha[col_modelo] = _valor_seguro(row, colunas_detectadas.get("nome"))

        linhas_saida.append(nova_linha)

    return pd.DataFrame(linhas_saida, columns=modelo.columns)
