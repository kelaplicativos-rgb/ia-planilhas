from __future__ import annotations

import pandas as pd


# =========================
# 📦 PADRÃO BLING - CADASTRO
# =========================
COLUNAS_CADASTRO = [
    "codigo",
    "nome",
    "unidade",
    "preco",
    "situacao",
    "marca",
    "descricao_curta",
    "url_imagens",
    "link_externo"
]


# =========================
# 📦 PADRÃO BLING - ESTOQUE
# =========================
COLUNAS_ESTOQUE = [
    "codigo",
    "deposito",
    "estoque"
]


# =========================
# 🧠 MAPEAMENTO INTELIGENTE
# =========================
MAPEAMENTO_PADRAO = {
    "codigo": ["codigo", "sku", "id", "ref"],
    "nome": ["nome", "produto", "descricao", "titulo"],
    "unidade": ["unidade", "und"],
    "preco": ["preco", "valor", "price"],
    "situacao": ["situacao", "status"],
    "marca": ["marca", "brand"],
    "descricao_curta": ["descricao_curta", "descricao", "desc"],
    "url_imagens": ["imagem", "imagens", "image", "foto"],
    "link_externo": ["link", "url", "produto_url"]
}


# =========================
# 🔎 FUNÇÃO DE DETECÇÃO
# =========================
def detectar_coluna(df: pd.DataFrame, possiveis_nomes: list[str]) -> str | None:
    for col in df.columns:
        if col in possiveis_nomes:
            return col
    return None


# =========================
# 🧱 MONTAR CADASTRO
# =========================
def montar_planilha_cadastro(df: pd.DataFrame) -> pd.DataFrame:
    resultado = pd.DataFrame(columns=COLUNAS_CADASTRO)

    for coluna_final, possiveis in MAPEAMENTO_PADRAO.items():
        col_origem = detectar_coluna(df, possiveis)

        if col_origem:
            resultado[coluna_final] = df[col_origem]
        else:
            resultado[coluna_final] = ""

    # valores padrão obrigatórios
    if "situacao" in resultado.columns:
        resultado["situacao"] = resultado["situacao"].replace("", "Ativo")

    if "unidade" in resultado.columns:
        resultado["unidade"] = resultado["unidade"].replace("", "UN")

    return resultado


# =========================
# 🧱 MONTAR ESTOQUE
# =========================
def montar_planilha_estoque(
    df: pd.DataFrame,
    deposito_padrao: str = "Geral"
) -> pd.DataFrame:

    resultado = pd.DataFrame(columns=COLUNAS_ESTOQUE)

    # código
    col_codigo = detectar_coluna(df, MAPEAMENTO_PADRAO["codigo"])
    if col_codigo:
        resultado["codigo"] = df[col_codigo]
    else:
        resultado["codigo"] = ""

    # estoque
    possiveis_estoque = ["estoque", "quantidade", "qtd", "stock"]
    col_estoque = detectar_coluna(df, possiveis_estoque)

    if col_estoque:
        resultado["estoque"] = df[col_estoque]
    else:
        resultado["estoque"] = 0

    # depósito (manual)
    resultado["deposito"] = deposito_padrao

    return resultado
