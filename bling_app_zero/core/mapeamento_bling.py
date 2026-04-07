from __future__ import annotations

import re
import unicodedata

import pandas as pd


# =========================================================
# NORMALIZAÇÃO
# =========================================================
def normalizar_texto(texto):
    if texto is None:
        return ""

    texto = str(texto).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def slug_coluna(texto):
    texto = normalizar_texto(texto)
    texto = texto.replace("/", "_")
    texto = texto.replace("-", "_")
    texto = texto.replace(" ", "_")
    texto = re.sub(r"[^a-z0-9_]", "", texto)
    texto = re.sub(r"_+", "_", texto)
    return texto.strip("_")


# =========================================================
# SINÔNIMOS
# =========================================================
SINONIMOS = {
    "codigo": [
        "codigo",
        "codigo_produto",
        "cod",
        "cod_produto",
        "sku",
        "referencia",
        "referencia_sku",
        "ref",
        "item_code",
        "product_code",
    ],
    "nome": [
        "nome",
        "nome_produto",
        "produto",
        "titulo",
        "titulo_produto",
        "name",
        "product_name",
    ],
    "descricao_curta": [
        "descricao_curta",
        "descricaocurta",
        "descricao",
        "resumo",
        "detalhes",
        "texto",
        "texto_produto",
        "short_description",
        "product_description",
    ],
    "marca": [
        "marca",
        "fabricante",
        "brand",
        "fornecedor_marca",
    ],
    "preco": [
        "preco",
        "preco_venda",
        "valor",
        "valor_venda",
        "price",
        "preco_cheio",
        "preco_final",
        "preco_de_venda",
    ],
    "estoque": [
        "estoque",
        "saldo",
        "saldo_estoque",
        "quantidade",
        "qtde",
        "qtd",
        "stock",
        "inventory",
    ],
    "imagem": [
        "imagem",
        "imagem_1",
        "imagem_principal",
        "foto",
        "foto_principal",
        "img",
        "image",
        "url_imagem",
        "link_imagem",
    ],
    "link_externo": [
        "link_externo",
        "link_produto",
        "url_produto",
        "url",
        "site",
        "pagina_produto",
        "product_url",
        "external_link",
    ],
    "categoria": [
        "categoria",
        "departamento",
        "secao",
        "secao_produto",
        "category",
    ],
    "peso": [
        "peso",
        "peso_liquido",
        "peso_bruto",
        "weight",
    ],
    "gtin": [
        "gtin",
        "ean",
        "barcode",
        "codigo_barras",
        "cod_barras",
        "codbarras",
    ],
    "unidade": [
        "unidade",
        "und",
        "un",
        "unit",
    ],
    "situacao": [
        "situacao",
        "status",
        "ativo",
        "situacao_produto",
    ],
    "deposito": [
        "deposito",
        "depósito",
        "warehouse",
        "almoxarifado",
        "local_estoque",
    ],
}


# =========================================================
# CAMPOS BLING
# =========================================================
def campos_cadastro_bling():
    return [
        "id",
        "codigo",
        "nome",
        "unidade",
        "preco",
        "situacao",
        "marca",
        "descricao_curta",
        "descricao",
        "video",
        "imagem_1",
        "imagem_2",
        "imagem_3",
        "imagem_4",
        "imagem_5",
        "link_externo",
        "categoria",
        "peso_liquido",
        "gtin",
    ]


def campos_estoque_bling():
    return [
        "id",
        "codigo",
        "nome",
        "estoque",
        "deposito",
    ]


# =========================================================
# DETECÇÃO
# =========================================================
def detectar_colunas(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {}

    colunas_originais = list(df.columns)
    colunas_slug = {col: slug_coluna(col) for col in colunas_originais}
    resultado = {}

    for campo, sinonimos in SINONIMOS.items():
        for coluna_original, coluna_slug in colunas_slug.items():
            if coluna_slug in sinonimos:
                resultado[campo] = coluna_original
                break

    for campo, sinonimos in SINONIMOS.items():
        if campo in resultado:
            continue

        for coluna_original, coluna_slug in colunas_slug.items():
            if any(s in coluna_slug for s in sinonimos):
                resultado[campo] = coluna_original
                break

    return resultado


# =========================================================
# AJUSTES DE SÉRIES
# =========================================================
def valor_padrao_serie(df: pd.DataFrame, valor=""):
    return pd.Series([valor] * len(df), index=df.index)


def obter_serie(df: pd.DataFrame, mapeamento: dict, campo: str, default=""):
    coluna = mapeamento.get(campo)

    if coluna and coluna in df.columns:
        return df[coluna]

    return valor_padrao_serie(df, default)


def limpar_texto_serie(serie: pd.Series) -> pd.Series:
    return (
        serie.fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def limpar_numero_serie(serie: pd.Series, default="0") -> pd.Series:
    s = serie.fillna("").astype(str).str.strip()

    def normalizar_numero(valor):
        valor = str(valor).strip()
        if valor == "":
            return default

        valor = re.sub(r"[^0-9,.\-]", "", valor)

        if "," in valor and "." in valor:
            if valor.rfind(",") > valor.rfind("."):
                valor = valor.replace(".", "")
                valor = valor.replace(",", ".")
            else:
                valor = valor.replace(",", "")
        elif "," in valor:
            valor = valor.replace(".", "")
            valor = valor.replace(",", ".")

        if valor in ["", "-", ".", "-.", ".-", "--"]:
            return default

        return valor

    return s.apply(normalizar_numero)


def limpar_gtin_serie(serie: pd.Series) -> pd.Series:
    s = serie.fillna("").astype(str)
    s = s.str.replace(r"[^0-9]", "", regex=True)
    return s


def limpar_url_serie(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip()


# =========================================================
# MAPEAMENTO FINAL
# =========================================================
def resolver_mapeamento_final(df: pd.DataFrame, mapeamento_manual: dict | None = None) -> dict:
    automatico = detectar_colunas(df)
    final = automatico.copy()

    if mapeamento_manual:
        for campo, coluna in mapeamento_manual.items():
            if coluna and coluna != "__nenhuma__":
                final[campo] = coluna

    return final


# =========================================================
# CADASTRO BLING
# =========================================================
def mapear_cadastro_bling(
    df: pd.DataFrame,
    mapeamento_manual: dict | None = None
) -> tuple[pd.DataFrame, dict]:
    if df is None or df.empty:
        return pd.DataFrame(columns=campos_cadastro_bling()), {}

    mapeamento_final = resolver_mapeamento_final(df, mapeamento_manual)
    saida = pd.DataFrame(index=df.index)

    saida["id"] = ""
    saida["codigo"] = limpar_texto_serie(obter_serie(df, mapeamento_final, "codigo", ""))
    saida["nome"] = limpar_texto_serie(obter_serie(df, mapeamento_final, "nome", ""))
    saida["unidade"] = "UN"
    saida["preco"] = limpar_numero_serie(
        obter_serie(df, mapeamento_final, "preco", "0"),
        default="0"
    )

    situacao_origem = limpar_texto_serie(obter_serie(df, mapeamento_final, "situacao", ""))
    saida["situacao"] = "Ativo"
    if not situacao_origem.empty:
        valores_inativos = {"0", "inativo", "desativado", "desabilitado", "false"}
        mascara_inativo = situacao_origem.str.lower().isin(valores_inativos)
        saida.loc[mascara_inativo, "situacao"] = "Inativo"

    saida["marca"] = limpar_texto_serie(obter_serie(df, mapeamento_final, "marca", ""))

    nome_produto = limpar_texto_serie(
        obter_serie(df, mapeamento_final, "nome", "")
    )

    descricao_real = limpar_texto_serie(
        obter_serie(df, mapeamento_final, "descricao_curta", "")
    )

    nome_final = nome_produto.copy()
    vazios_nome = nome_final.astype(str).str.strip() == ""
    nome_final.loc[vazios_nome] = descricao_real.loc[vazios_nome]

    descricao_final = descricao_real.copy()
    vazios_desc = descricao_final.astype(str).str.strip() == ""
    descricao_final.loc[vazios_desc] = nome_final.loc[vazios_desc]

    # regra do projeto:
    # - nome/título vai em "nome"
    # - descrição real vai em "descricao_curta"
    # - "descricao" acompanha o nome para não quebrar integração legada
    saida["descricao"] = nome_final
    saida["descricao_curta"] = descricao_final

    saida["video"] = ""

    imagem_base = limpar_url_serie(obter_serie(df, mapeamento_final, "imagem", ""))
    saida["imagem_1"] = imagem_base
    saida["imagem_2"] = ""
    saida["imagem_3"] = ""
    saida["imagem_4"] = ""
    saida["imagem_5"] = ""

    # regra pedida: Link Externo deve ficar vazio
    saida["link_externo"] = ""

    # regra pedida: categoria só se vier confiante/manual; aqui mantém origem detectada
    saida["categoria"] = limpar_texto_serie(obter_serie(df, mapeamento_final, "categoria", ""))

    saida["peso_liquido"] = limpar_numero_serie(
        obter_serie(df, mapeamento_final, "peso", "0"),
        default="0"
    )
    saida["gtin"] = limpar_gtin_serie(obter_serie(df, mapeamento_final, "gtin", ""))

    saida = saida[campos_cadastro_bling()]

    return saida, mapeamento_final


# =========================================================
# ESTOQUE BLING
# =========================================================
def mapear_estoque_bling(
    df: pd.DataFrame,
    mapeamento_manual: dict | None = None
) -> tuple[pd.DataFrame, dict]:
    if df is None or df.empty:
        return pd.DataFrame(columns=campos_estoque_bling()), {}

    mapeamento_final = resolver_mapeamento_final(df, mapeamento_manual)
    saida = pd.DataFrame(index=df.index)

    saida["id"] = ""
    saida["codigo"] = limpar_texto_serie(obter_serie(df, mapeamento_final, "codigo", ""))
    saida["nome"] = limpar_texto_serie(obter_serie(df, mapeamento_final, "nome", ""))
    saida["estoque"] = limpar_numero_serie(
        obter_serie(df, mapeamento_final, "estoque", "0"),
        default="0"
    )

    deposito_manual = ""
    try:
        import streamlit as st
        deposito_manual = str(st.session_state.get("deposito_nome", "") or "").strip()
    except Exception:
        deposito_manual = ""

    if deposito_manual:
        saida["deposito"] = deposito_manual
    else:
        saida["deposito"] = limpar_texto_serie(obter_serie(df, mapeamento_final, "deposito", ""))

    saida = saida[campos_estoque_bling()]

    return saida, mapeamento_final
